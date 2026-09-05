#!/usr/bin/env python3
"""
extraire_contexte.py — Étage 1 (Namaste 3), matcher v3.

QUOI : pour chacune des 2206 classes message obfusquées, la liste des SIGNATURES DE
    MÉTHODES qui la citent (paramètre, retour, générique) ailleurs dans le client — la
    classe PORTEUSE est une ancre sémantique quand elle est en clair, et une arête de
    VOISINAGE (co-occurrence) même quand tout est obfusqué. Écrit `contexte-appels.jsonl`
    et `aretes-voisinage.jsonl`.
POURQUOI (04/09/2026, brief « ancres par contexte d'appel ») : la forme
    d'imbrication seule (v1/v2) plafonne le matching — le CONTEXTE (qui cite quoi) est
    un signal supplémentaire, testé ici jusqu'à son terme mesuré (0% de porteur clair,
    §2 du docstring).
COMMENT LANCER : `python3 extraire_contexte.py` (lit `cs/il2cpp.cs` et
    `signatures-obfusquees.jsonl`, écrit les 2 fichiers ci-dessus).
GATE : logue le % de classes citées, le % à porteur clair, et le nombre d'arêtes — un
    % de porteur clair non nul doit être vérifié contre le piège namespace-texte décrit
    ci-dessous avant d'être cru.

FR : mesuré avant d'écrire le scanner (pas supposé) : nos 2206 classes cibles n'ont
     AUCUN namespace (confirmé étage 1 v1 — `Com.Ankama.Dofus.Server.*` obfusqué =
     placé en namespace global). Un objet qui les référence depuis un vrai namespace
     (`Core.*`, `Ankama.*`, tout package Unity non protocolaire) est donc, par
     construction, EXTÉRIEUR au protocole obfusqué — une ancre plus solide qu'une simple
     co-occurrence entre deux tokens obfusqués. Exemple trouvé en reconnaissance :
     `gjx : gjw<kqy>` (`SimpleChannelInboundHandler<GameMessage>`, un handler Netty) et
     `public override void bknh(IChannelHandlerContext a, kqy b);` — la classe porteuse
     `gjx`/`gjw` est ELLE-MÊME obfusquée (protocole aussi), donc ce cas précis est une
     arête de co-occurrence, pas une ancre en clair ; mais le MÊME mécanisme de
     recherche (tokenisation par mot d'une ligne de signature, intersection avec les
     2206 tokens) trouve aussi les porteurs EN CLAIR quand ils existent.
EN : measured before writing: our 2206 target classes have NO namespace (confirmed in
     v1 — obfuscated `Com.Ankama.Dofus.Server.*` sits in the global namespace). Anything
     that references them from a REAL namespace is, by construction, outside the
     obfuscated protocol — a stronger anchor than obfuscated-to-obfuscated co-occurrence.
Stdlib seule. 0 LLM.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(os.path.dirname(os.path.dirname(HERE)), "etage0-dump", "out", "il2cppinspectorredux")
CS_PATH = os.path.join(DUMP, "cs", "il2cpp.cs")
SIG_OBF_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
OUT_CONTEXTE = os.path.join(HERE, "contexte-appels.jsonl")
OUT_ARETES = os.path.join(HERE, "aretes-voisinage.jsonl")

DECL_RE = re.compile(
    r"^(?P<tabs>\t*)(?:public|private|internal|protected|sealed|abstract|static|partial|"
    r"readonly|new|unsafe|\s)*(?:class|struct|enum|interface)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r".*//\s*TypeDefIndex:\s*(?P<tdi>\d+)\s*$"
)
CLOSE_RE = re.compile(r"^(\t*)\}\s*$")
IMG_RE = re.compile(r"^// Image \d+: (\S+) - .* - Types (\d+)-(\d+)")
SECTION_RE = re.compile(r"^\t*// (Fields|Properties|Constructors|Methods|Nested types|Events|Indexer)\s*$")
WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
TARGET_ASSEMBLIES = {"Ankama.Dofus.Protocol.Game.dll", "Ankama.Dofus.Protocol.Connection.dll"}
# FR: trouvaille EN COURS DE ROUTE, bug trouvé et corrigé — le texte `namespace X` de ce
# décompilateur ne délimite RIEN : une fois émis, il « colle » à tout ce qui suit jusqu'à
# la prochaine directive, y compris des classes du protocole obfusqué qui n'ont EN VRAI
# aucun namespace (mesuré : `namespace Unity.Mathematics` attribué à tort à `hdw` et
# consorts, cf. v1 §"nearest namespace before hdw"). Le texte ment ; le TypeDefIndex/
# l'IMAGE (assembly), lui, ne ment pas — même méthode que v1/gate-g0.py. EN: bug found —
# this decompiler's `namespace X` text doesn't scope anything; it "sticks" to whatever
# follows. Text lies; TypeDefIndex/assembly image doesn't — same method as v1/gate-g0.py.
# FR: une ligne "signature" a une chance d'être une méthode/propriété/ctor citant un
# type — on la reconnaît par sa forme (parenthèses ou accolades de propriété), pas par
# sa section, pour ne rien rater d'un format légèrement différent ailleurs dans le fichier.
SIGNATURE_LINE_RE = re.compile(r"\(.*\)\s*;|\{\s*get;|\{\s*get\s*;\s*set;")


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# FR: trouvaille — 1 des 2206 tokens (TypeDefIndex 10929, Game.dll) est LITTÉRALEMENT
# nommé `int` par l'obfuscateur (collision avec le mot-clé C#, imprimé sans échappement
# `@int` par le décompilateur). Une recherche par mot ne peut PAS le distinguer du type
# primitif `int` omniprésent (11278 citations mesurées avant filtre, toutes fausses) —
# exclu de la recherche par mot, jamais silencieusement (sa fiche reste écrite, à 0
# citation, avec la raison). EN: one token is literally named `int` (keyword collision)
# — word-search can't tell it apart from the primitive type; excluded from search, its
# record stays written with 0 citations and the reason, never silently dropped.
MOTS_RESERVES_CSHARP = {
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char", "checked",
    "class", "const", "continue", "decimal", "default", "delegate", "do", "double", "else",
    "enum", "event", "explicit", "extern", "false", "finally", "fixed", "float", "for",
    "foreach", "goto", "if", "implicit", "in", "int", "interface", "internal", "is", "lock",
    "long", "namespace", "new", "null", "object", "operator", "out", "override", "params",
    "private", "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch", "this",
    "throw", "true", "try", "typeof", "uint", "ulong", "unchecked", "unsafe", "ushort",
    "using", "virtual", "void", "volatile", "while",
}


# Charge les 2206 tokens obfusqués cibles depuis signatures-obfusquees.jsonl.
# / Loads the 2206 target obfuscated tokens from signatures-obfusquees.jsonl.
def load_token_set(sig_path):
    tokens = set()
    for line in open(sig_path, encoding="utf-8"):
        tokens.add(json.loads(line)["obf_name"])
    collisions = tokens & MOTS_RESERVES_CSHARP
    if collisions:
        log(f"[contexte] {len(collisions)} token(s) collisionnant avec un mot-clé C# réservé "
            f"(recherche par mot impossible) : {sorted(collisions)} — écartés de la recherche")
    return tokens, collisions


def collect_image_ranges(cs_path):
    """FR: les en-têtes `// Image N: X.dll - ... - Types A-B` sont REGROUPÉS en tête de
    fichier (mesuré en v1) — une lecture des 500 premières lignes suffit. EN: image
    headers are grouped at file top (measured in v1) — first 500 lines are enough."""
    plages = []
    with open(cs_path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 15000:  # mesuré : le dernier en-tête `// Image` tombe à la ligne 9953
                break
            m = IMG_RE.match(line)
            if m:
                plages.append((m.group(1), int(m.group(2)), int(m.group(3))))
    return plages


# Fabrique une fonction TypeDefIndex -> nom d'assembly (recherche linéaire, ~141 plages).
# / Builds a TypeDefIndex -> assembly-name function (linear search, ~141 ranges).
def make_image_de(plages):
    # Recherche linéaire de la plage contenant tdi ; "?" si aucune (hors du dump connu).
    # / Linear search for the range containing tdi; "?" if none (outside the known dump).
    def image_de(tdi):
        for nom, a, b in plages:
            if a <= tdi <= b:
                return nom
        return "?"
    return image_de


def scan(cs_path, token_set):
    """FR: UN passage. Pile légère : (assembly_de_la_classe_top_niveau, nom, profondeur).
    « Clair » = l'assembly de la classe PORTEUSE n'est PAS une de nos 2 assemblies
    protocolaires obfusquées (déterminé par TypeDefIndex/image, PAS par le texte
    `namespace`, cf. bug trouvé et corrigé ci-dessus). EN: one pass, lightweight stack
    (top-level class's assembly, name, indent). "Clear" = carrying class's assembly is
    outside our 2 obfuscated protocol assemblies (by TypeDefIndex/image, not by the
    unreliable `namespace` text)."""
    t0 = time.time()
    plages = collect_image_ranges(cs_path)
    image_de = make_image_de(plages)
    log(f"[contexte] {len(plages)} plages d'assembly collectées")
    hits = []  # (token, top_class, assembly, is_clear, line_no, excerpt)
    class_stack = []  # [(tabs, name)]
    top_class = None
    top_assembly = "?"

    with open(cs_path, encoding="utf-8", errors="replace") as fh:
        for i, raw in enumerate(fh):
            if i % 300_000 == 0 and i:
                log(f"[contexte] {i} lignes… ({len(hits)} citations trouvées)")
            line = raw.rstrip("\n")
            if not line:
                continue

            if line[0] != "\t":
                cm = CLOSE_RE.match(line)
                if cm and class_stack:
                    class_stack.clear()
                    top_class = None
                dm = DECL_RE.match(line)
                if dm:
                    top_class = dm.group("name")
                    top_assembly = image_de(int(dm.group("tdi")))
                    class_stack = [(0, top_class)]
                continue

            cm = CLOSE_RE.match(line)
            if cm:
                tabs = len(cm.group(1))
                while class_stack and class_stack[-1][0] >= tabs:
                    class_stack.pop()
                if not class_stack:
                    top_class = None
                continue

            dm = DECL_RE.match(line)
            if dm:
                tabs = len(dm.group("tabs"))
                class_stack.append((tabs, dm.group("name")))
                continue

            if top_class is None or not SIGNATURE_LINE_RE.search(line):
                continue

            code_part = line.split("//", 1)[0]
            words = set(WORD_RE.findall(code_part))
            found = words & token_set
            if not found:
                continue
            # FR: 2e trouvaille — `Core.dll` (hors de nos 2 assemblies protocolaires)
            # PORTE AUSSI des classes obfusquées (`ebu`,`eqq`… même motif tout-minuscule
            # que nos tokens) : l'obfuscateur d'Ankama couvre plus que le protocole. Le
            # nom lui-même tranche mieux qu'une liste d'assemblies : nos tokens sont
            # SYSTÉMATIQUEMENT tout-minuscule (convention C# = PascalCase pour une
            # classe réelle) — mesuré sur les 2206 signatures (0 exception). Les DEUX
            # signaux combinés (assembly ET nom) réduisent le risque de faux clair.
            # EN: `Core.dll` ALSO carries obfuscated classes — name readability
            # discriminates better than an assembly allowlist (our tokens are always
            # all-lowercase; a real C# class name is PascalCase).
            is_clear = (top_assembly not in TARGET_ASSEMBLIES and top_class not in token_set
                        and bool(top_class) and top_class[0].isupper())
            excerpt = code_part.strip()[:160]
            for tok in found:
                hits.append((tok, top_class, top_assembly, is_clear, i + 1, excerpt))

    log(f"[contexte] scan terminé ({time.time()-t0:.1f}s), {len(hits)} citations")
    return hits


# Regroupe les citations par token (porteurs) et détecte les arêtes de co-occurrence
# (2 tokens cités sur la même ligne de signature).
# / Groups citations by token (carriers) and detects co-occurrence edges (2 tokens
# cited on the same signature line).
def build_records(hits, token_set):
    by_token = {}
    for tok, cls, asm, clear, ln, excerpt in hits:
        by_token.setdefault(tok, []).append({
            "carrying_class": cls, "carrying_assembly": asm, "carrier_is_clear": clear,
            "line": ln, "excerpt": excerpt,
        })

    edges = {}
    by_line = {}
    for tok, cls, asm, clear, ln, excerpt in hits:
        by_line.setdefault((cls, ln), []).append(tok)
    for (cls, ln), toks in by_line.items():
        uniq = sorted(set(toks))
        for a in range(len(uniq)):
            for b in range(a + 1, len(uniq)):
                key = (uniq[a], uniq[b])
                edges.setdefault(key, {"a": uniq[a], "b": uniq[b], "count": 0, "examples": []})
                e = edges[key]
                e["count"] += 1
                if len(e["examples"]) < 3:
                    e["examples"].append({"carrying_class": cls, "line": ln})

    n_with_clear = sum(1 for tok in token_set if any(h["carrier_is_clear"] for h in by_token.get(tok, [])))
    n_with_any = sum(1 for tok in token_set if by_token.get(tok))
    return by_token, edges, n_with_clear, n_with_any


# Point d'entrée : charge les tokens, scanne le dump, écrit les 2 fichiers de sortie.
# / Entry point: loads tokens, scans the dump, writes the 2 output files.
def main():
    if not os.path.exists(CS_PATH):
        log(f"ABSENT : {CS_PATH} — rien à extraire, je n'invente pas.")
        sys.exit(2)
    if not os.path.exists(SIG_OBF_PATH):
        log(f"ABSENT : {SIG_OBF_PATH} — lance d'abord extraire_signatures.py.")
        sys.exit(2)

    token_set, collisions = load_token_set(SIG_OBF_PATH)
    log(f"[contexte] {len(token_set)} tokens obfusqués cibles chargés")
    searchable = token_set - collisions

    hits = scan(CS_PATH, searchable)
    by_token, edges, n_with_clear, n_with_any = build_records(hits, token_set)

    log(f"[contexte] {n_with_any}/{len(token_set)} classes citées AU MOINS UNE FOIS ailleurs "
        f"dans le dump ({n_with_any/len(token_set):.1%})")
    log(f"[contexte] {n_with_clear}/{len(token_set)} classes avec AU MOINS UN porteur EN CLAIR "
        f"(namespace non vide, hors protocole obfusqué) ({n_with_clear/len(token_set):.1%})")
    log(f"[contexte] {len(edges)} arêtes de co-occurrence distinctes (2 tokens cités sur la même ligne)")

    with open(OUT_CONTEXTE, "w", encoding="utf-8") as f:
        for tok in sorted(token_set):
            carriers = by_token.get(tok, [])
            rec = {
                "obf_token": tok, "nb_citations": len(carriers),
                "a_un_porteur_clair": any(c["carrier_is_clear"] for c in carriers),
                "porteurs": carriers[:20],  # borné, jamais tout imprimer pour un token très cité
            }
            if tok in collisions:
                rec["note"] = "collision avec un mot-clé C# réservé — recherche par mot impossible, écarté"
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"[contexte] {len(token_set)} fiches (une par token, même sans citation) → {OUT_CONTEXTE}")

    with open(OUT_ARETES, "w", encoding="utf-8") as f:
        for e in sorted(edges.values(), key=lambda x: (-x["count"], x["a"], x["b"])):
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    log(f"[contexte] {len(edges)} arêtes → {OUT_ARETES}")


if __name__ == "__main__":
    main()
