#!/usr/bin/env python3
"""
extraire_signatures.py — Étage 1 (Namaste 3), matcher v1.

QUOI : extraction déterministe des signatures (numéro/type/répété de champ, imbrication,
    TypeDefIndex) des 2206 classes protobuf obfusquées du dump il2cppinspectorredux —
    fondation de TOUT le chantier matcher (v1/v2/v3 en dépendent). Écrit
    `signatures-obfusquees.jsonl`.
POURQUOI (04/09/2026, brief « matcher noms clairs ↔ classes obfusquées ») :
    sans cette extraction, rien de comparable n'existe côté obfusqué — 1re brique de
    toute la chaîne.
COMMENT LANCER : `python3 extraire_signatures.py` (lit `cs/il2cpp.cs`, appelle
    `verifier_motif.py` en interne, écrit `signatures-obfusquees.jsonl` +
    `extraction-stats.json`).
GATE : `verifier_motif.py` doit passer 3/3 avant l'extraction (le script s'arrête sinon,
    `sys.exit(3)`) ; logue ensuite le nombre de classes/champs résolus — 0 non-résolu
    attendu (mesuré, corrigé le 04/09, cf. RAPPORT-MATCHER.md §5).

FR : il2cpp.json (207 Mo) NE contient PAS de liste de types résolus — mesuré : son
     unique clé de haut niveau est "addressMap", dont les sous-clés (methodDefinitions,
     fields, typeInfoPointers…) sont des tables d'ADRESSES/RVA, pas des définitions de
     classe (le "fields" de 2410 entrées est un dump d'octets statiques bruts, pas des
     numéros de champ protobuf). La source RÉELLE des classes/champs/imbrications est
     cs/il2cpp.cs (55 Mo, texte), déjà prouvée lisible par gate-g0.py (étage 0, VERT).
     On y reparse un ARBRE (l'indentation en tabulations = profondeur d'imbrication),
     pas juste des lignes isolées, pour capturer nesting + champs + valeurs d'enum.
EN : il2cpp.json's only top-level key is "addressMap" — an RVA/address export table,
     NOT resolved type/field definitions (measured, not assumed — see above). The real
     source is cs/il2cpp.cs, parsed here as a TREE (tab-indentation = nesting depth).

Convention Google.Protobuf C# confirmée sur du code NON obfusqué ailleurs dans ce même
dump (TypeDefIndex 6664-6667, hors de nos plages cibles) : chaque message avec du
contenu imbriqué a un unique conteneur "Types" à profondeur 1, sous lequel vivent les
vrais sous-messages/enums (Success/Error/Failed/…) à profondeur ≥2. DANS nos plages
cibles, ce conteneur "Types" est LUI AUSSI obfusqué (0 occurrence du littéral "class
Types" dans les TypeDefIndex 9439-15069 / 38959-39073, mesuré) — donc invisible par le
nom, seulement par sa FORME (aucun champ propre, seulement des types imbriqués).

Pattern de champ protobuf généré (mesuré sur hdw/hdx/heg, stable) :
    public const int <cst> = <numéro>;
    [private static readonly FieldCodec<T> <codec>;]   ← optionnel, seulement si répété
    private [readonly] <TYPE> <backing>;                ← le champ porteur, à apparier

Loi F (compter ce qu'on écarte) : toute plage sans backing field résolu, tout type non
résolu par le registre global, est compté et imprimé — jamais silencieux.
Stdlib seule. 0 LLM. Rejouable (mêmes entrées → même JSONL, éprouvé par matcher.py).
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DUMP = os.path.join(
    os.path.dirname(os.path.dirname(HERE)),
    "etage0-dump", "out", "il2cppinspectorredux",
)
CS_PATH = os.path.join(DUMP, "cs", "il2cpp.cs")
OUT_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")

TARGET_ASSEMBLIES = {
    "Ankama.Dofus.Protocol.Game.dll",
    "Ankama.Dofus.Protocol.Connection.dll",
}

IMG_RE = re.compile(r"^// Image \d+: (\S+) - .* - Types (\d+)-(\d+)")
DECL_RE = re.compile(
    r"^(?P<tabs>\t*)"
    r"(?P<mods>(?:public|private|internal|protected|sealed|abstract|static|partial|readonly|new|unsafe)\s+)*"
    r"(?P<kind>class|struct|enum|interface)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*:\s*(?P<bases>[^\r\n]+?))?"
    r"\s*//\s*TypeDefIndex:\s*(?P<tdi>\d+)\s*$"
)
SECTION_RE = re.compile(r"^\t*// (Fields|Properties|Constructors|Methods|Nested types|Events|Indexer)\s*$")
CONST_RE = re.compile(r"^\t*public const int (\w+) = (-?\d+);")
CLOSE_RE = re.compile(r"^(\t*)\}\s*$")
ENUM_MEMBER_RE = re.compile(r"^\t*(\w+)\s*=\s*(-?\d+),?\s*$")

SKIP_BACKING_PREFIXES = ("MessageParser<", "FieldCodec<")
SKIP_BACKING_EXACT = {"UnknownFieldSet"}
MAX_FIELD_NUMBER = 100_000  # protobuf autorise jusqu'à 536 870 911 ; nos messages plafonnent << 100,
                            # mesuré — large marge sans laisser passer un `1000000000` de Duration.

SCALAR_LEAVES = {
    "int", "uint", "long", "ulong", "short", "ushort", "byte", "sbyte",
    "float", "double", "bool", "string", "char", "decimal",
    "ByteString", "Int32", "UInt32", "Int64", "UInt64", "Single", "Double",
    "Boolean", "String", "Byte", "SByte", "Int16", "UInt16",
}
WELLKNOWN_LEAVES = {
    "Any", "Timestamp", "Duration", "Struct", "Value", "ListValue", "NullValue",
    "FieldMask", "BytesValue", "StringValue", "Int32Value", "UInt32Value",
    "Int64Value", "UInt64Value", "BoolValue", "FloatValue", "DoubleValue", "Empty",
}
NOISE_NESTED_NAMES = {"__c"}  # closure protobuf générée par le compilateur, sans valeur structurelle


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Extrait les plages TypeDefIndex par assembly depuis les en-têtes "// Image N: ...".
# / Extracts TypeDefIndex ranges per assembly from the "// Image N: ..." headers.
def image_ranges(lines):
    plages = []
    for l in lines:
        m = IMG_RE.match(l)
        if m:
            plages.append((m.group(1), int(m.group(2)), int(m.group(3))))
    return plages


# Fabrique TypeDefIndex -> nom d'assembly. Plages triées, recherche linéaire suffisante
# (141 plages seulement). / Builds TypeDefIndex -> assembly name; linear search is enough (141 ranges).
def make_image_de(plages):
    # Recherche linéaire de la plage contenant tdi. / Linear search for the range containing tdi.
    def image_de(tdi):
        for nom, a, b in plages:
            if a <= tdi <= b:
                return nom
        return "?"
    return image_de


# Construit un nœud vide de l'arbre de classes (rempli au fil du parsing).
# / Builds an empty class-tree node (filled in as parsing proceeds).
def new_node(kind, name, bases, tdi, tabs, parent):
    return {
        "kind": kind, "name": name, "bases": bases or "", "tdi": tdi,
        "tabs": tabs, "parent": parent, "section": None,
        "fields": [], "nested": [], "enum_members": 0, "_pending_consts": [],
    }


def parse_backing_line(line):
    """FR: sépare TYPE et NOM d'une ligne de champ ; le NOM (dernier token, jamais
    d'espace/générique dedans) donne le point de coupe le plus sûr : rsplit(' ',1)
    marche même pour `MapField<string, string> metadata_` (mesuré).
    EN: split TYPE/NAME; the name is always the last token, so rsplit(' ',1) is safe
    even across generic args with a space after the comma (measured on MapField<K, V>)."""
    line = line.split("//", 1)[0].strip()
    if not line.endswith(";"):
        return None
    line = line[:-1].strip()
    if not line:
        return None
    mods = ("public", "private", "internal", "protected", "static", "readonly")
    while True:
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] in mods:
            line = parts[1]
        else:
            break
    if " " not in line:
        return None
    type_str, name = line.rsplit(" ", 1)
    if not re.match(r"^[A-Za-z_]\w*$", name):
        return None
    return type_str.strip(), name


# Cœur du script : un seul passage sur cs/il2cpp.cs, pile de classes imbriquées,
# résolution const->champ, sortie l'arbre top_levels + les stats de la loi F.
# / Core of the script: single pass, nested-class stack, const->field resolution,
# returns the top_levels tree + law-F stats.
def parse_tree(cs_path):
    t0 = time.time()
    with open(cs_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    lines = text.split("\n")
    log(f"[extraire] {len(lines)} lignes lues ({time.time()-t0:.1f}s)")
    plages = image_ranges(lines)
    image_de = make_image_de(plages)
    log(f"[extraire] {len(plages)} plages d'assembly")

    stack = []
    top_levels = []
    stats = {"top_level_vus": 0, "top_level_hors_cible": 0, "pending_const_non_resolu": 0,
              "const_total": 0, "const_resolus": 0, "skip_lines_backing": 0}

    n = len(lines)
    for i, line in enumerate(lines):
        if i % 200_000 == 0 and i:
            log(f"[extraire] {i}/{n} lignes… ({len(top_levels)} classes cibles ouvertes)")

        if not stack:
            # Hors d'un sous-arbre cible : seule une déclaration top-level (0 tab)
            # mérite d'être testée — tout le reste du fichier est ignoré vite.
            if not line or line[0] == "\t":
                continue
            m = DECL_RE.match(line)
            if not m:
                continue
            tdi = int(m.group("tdi"))
            img = image_de(tdi)
            if img not in TARGET_ASSEMBLIES:
                stats["top_level_hors_cible"] += 1
                continue
            stats["top_level_vus"] += 1
            node = new_node(m.group("kind"), m.group("name"), m.group("bases"), tdi, 0, None)
            node["assembly"] = img
            top_levels.append(node)
            stack.append(node)
            continue

        # Dans un sous-arbre cible : tout est inspecté.
        cur = stack[-1]
        cm = CLOSE_RE.match(line)
        if cm and len(cm.group(1)) == cur["tabs"]:
            for pc in cur["_pending_consts"]:
                stats["pending_const_non_resolu"] += 1
                cur["fields"].append({**pc, "type": None, "kind": "non_resolu",
                                       "repeated": False, "is_map": False})
            cur["_pending_consts"] = []
            stack.pop()
            continue

        dm = DECL_RE.match(line)
        if dm:
            tabs = len(dm.group("tabs"))
            if tabs == cur["tabs"] + 1:
                child = new_node(dm.group("kind"), dm.group("name"), dm.group("bases"),
                                  int(dm.group("tdi")), tabs, cur["name"])
                child["assembly"] = cur.get("assembly", "?")
                cur["nested"].append(child)
                stack.append(child)
                continue
            # profondeur inattendue : on l'ignore comme membre, mais on le signale une fois
            # (ne devrait jamais arriver vu la régularité mesurée du format).
            continue

        sm = SECTION_RE.match(line)
        if sm and len(line) - len(line.lstrip("\t")) == cur["tabs"] + 1:
            cur["section"] = sm.group(1)
            continue

        if cur["kind"] == "enum":
            em = ENUM_MEMBER_RE.match(line)
            if em:
                cur["enum_members"] += 1
            continue

        if cur["section"] != "Fields":
            continue

        cst = CONST_RE.match(line)
        if cst:
            # FR: garde trouvée en vérifiant le motif sur 3 témoins EN CLAIR (Any, Api,
            # Duration, cf. RAPPORT-MATCHER.md §7) — Duration porte des `public const
            # int` qui ne sont PAS des numéros de champ (`NanosecondsPerSecond =
            # 1000000000`). Un vrai numéro de champ protobuf reste petit pour nos
            # messages (mesuré : max << 100) ; une valeur hors plage n'est PAS mise en
            # attente d'un backing field, elle est comptée et écartée (loi F).
            # EN: guard found by checking the pattern on 3 clear witnesses (Any, Api,
            # Duration) — Duration carries `public const int` that are NOT field
            # numbers. A real field number stays small here; an out-of-range value is
            # counted and excluded, never queued as a pending field.
            champ_num = int(cst.group(2))  # PAS `n` : collision avec le compteur de lignes
                                            # de la boucle englobante — bug trouvé et corrigé.
            if not (0 <= champ_num <= MAX_FIELD_NUMBER):
                stats["const_hors_plage_ecarte"] = stats.get("const_hors_plage_ecarte", 0) + 1
                continue
            # FR: plusieurs `const` consécutifs SANS ligne de champ entre eux = un
            # groupe `oneof` (mesuré sur `hea`, TypeDefIndex 9451 : 3 const, 1 seul
            # `object` backing partagé ensuite) — on les empile, on ne les perd pas.
            # EN: consecutive consts with no field line between = a oneof group
            # (measured on `hea`/9451: 3 consts, one shared `object` backing field) —
            # queued, not dropped.
            cur["_pending_consts"].append({"const_name": cst.group(1), "number": champ_num})
            stats["const_total"] += 1
            continue

        parsed = parse_backing_line(line)
        if parsed is None:
            continue
        type_str, _backing_name = parsed
        if type_str.startswith(SKIP_BACKING_PREFIXES) or type_str in SKIP_BACKING_EXACT:
            stats["skip_lines_backing"] += 1
            continue
        if not cur["_pending_consts"]:
            continue  # champ hors numérotation (rare, ex. codec statique orphelin) — ignoré
        for pc in cur["_pending_consts"]:
            cur["fields"].append({**pc, "raw_type": type_str})
            stats["const_resolus"] += 1
        if len(cur["_pending_consts"]) > 1:
            stats["oneof_groupes"] = stats.get("oneof_groupes", 0) + 1
        cur["_pending_consts"] = []

    log(f"[extraire] parse terminé ({time.time()-t0:.1f}s) — {stats['top_level_vus']} classes "
        f"top-niveau cibles, {stats['top_level_hors_cible']} top-niveau écartées (hors assembly)")
    return top_levels, stats


# Aplatit récursivement l'arbre de classes en une liste (mutation de `out`).
# / Recursively flattens the class tree into a list (mutates `out`).
def flatten(nodes, out):
    for n in nodes:
        out.append(n)
        flatten(n["nested"], out)
    return out


def build_registry(all_nodes):
    """FR: nom (dernier segment) → nature (message/enum/other), pour résoudre les
    types de champ qui référencent une AUTRE classe (ex. `hef.hee`). Une collision de
    nom (deux classes différentes, même dernier segment) est comptée, pas cachée.
    EN: leaf-name → kind registry to resolve cross-class field type references."""
    reg = {}
    for n in all_nodes:
        leaf = n["name"]
        k = "message" if "IBufferMessage" in n["bases"] else ("enum" if n["kind"] == "enum" else "other")
        e = reg.setdefault(leaf, {"kind": k, "count": 0, "ambiguous": False})
        e["count"] += 1
        if e["kind"] != k:
            e["ambiguous"] = True
    return reg


def classify_field_type(raw_type, registry):
    """FR: `object` = champ porteur PARTAGÉ d'un `oneof` (plusieurs `const int`, un seul
    backing field) — un cas légitime du protobuf généré, pas une erreur : catégorie
    dédiée `oneof_object`, jamais fourré dans `unresolu`. `MapField<K, V>` — la clé et
    la valeur sont deux types SÉPARÉS (bug mesuré : les traiter comme une seule chaîne
    "K, V" les rend tous "unresolu" à tort ; on classe la VALEUR, on garde la clé à part).
    EN: `object` = shared oneof backing field, its own category, never miscounted as
    unresolved. MapField<K, V> — split key/value before classifying (bug measured:
    treating "K, V" as one leaf makes every map field wrongly 'unresolu')."""
    t = raw_type.strip()
    repeated, is_map, key_type = False, False, None
    inner = t
    if t.startswith("RepeatedField<") and t.endswith(">"):
        repeated = True
        inner = t[len("RepeatedField<"):-1].strip()
    elif t.startswith("MapField<") and t.endswith(">"):
        repeated, is_map = True, True
        body = t[len("MapField<"):-1].strip()
        k, _, v = body.partition(",")
        key_type, inner = k.strip(), v.strip()
    leaf = inner.split(".")[-1].split("<")[0].strip()
    if leaf == "object":
        kind = "oneof_object"
    elif leaf in SCALAR_LEAVES:
        kind = "scalar"
    elif leaf in WELLKNOWN_LEAVES:
        kind = "wellknown"
    else:
        e = registry.get(leaf)
        if e is None:
            kind = "unresolu"
        elif e["ambiguous"]:
            kind = "ambigu"
        else:
            kind = e["kind"]
    return {"raw": t, "inner": inner, "key_type": key_type, "repeated": repeated,
            "is_map": is_map, "resolved_kind": kind}


# Résout les types de champ d'un nœud via classify_field_type, compte résolus/incertains.
# / Resolves a node's field types via classify_field_type, counts resolved/uncertain.
def resolve_fields(node, registry, stats):
    resolved = []
    for f in node["fields"]:
        if f.get("type") is None and "raw_type" not in f:
            resolved.append({"number": f["number"], "const_name": f["const_name"],
                              "resolved_kind": "non_resolu", "raw": None})
            stats["champs_non_resolus"] += 1
            continue
        c = classify_field_type(f["raw_type"], registry)
        resolved.append({"number": f["number"], "const_name": f["const_name"], **c})
        stats["champs_resolus"] += 1
        if c["resolved_kind"] in ("unresolu", "ambigu"):
            stats["champs_type_incertain"] += 1
    return resolved


def nested_shape(node, registry, stats, depth=0):
    """FR: arbre récursif (nom obfusqué, nature, message?, nb membres si enum, champs
    si message) — c'est l'ANALOGUE du round-0 de Weisfeiler-Lehman côté OBFUSQUÉ, mais
    limité à ce qui est comparable au côté noms clairs : la FORME d'imbrication, pas les
    numéros de champ (les noms clairs n'en portent aucun). EN: recursive shape tree —
    the WL-round-0 analogue restricted to what's comparable across both sides: nesting
    SHAPE, not field graphs (clear names carry none)."""
    is_msg = "IBufferMessage" in node["bases"]
    entry = {
        "name": node["name"], "kind": node["kind"], "is_message": is_msg,
        "depth": depth,
    }
    if node["kind"] == "enum":
        entry["enum_members"] = node["enum_members"]
    real_children = [c for c in node["nested"] if c["name"] not in NOISE_NESTED_NAMES]
    entry["children"] = [nested_shape(c, registry, stats, depth + 1) for c in real_children]
    entry["subtree_size"] = len(entry["children"]) + sum(c["subtree_size"] for c in entry["children"])
    return entry


# Parcourt l'arbre, émet une fiche JSONL par classe IBufferMessage (top-niveau ou imbriquée).
# / Walks the tree, emits one JSONL record per IBufferMessage class (top-level or nested).
def emit_records(top_levels, registry, stats):
    records = []

    # Descente récursive : émet la fiche du nœud courant si message, puis ses enfants.
    # / Recursive descent: emits the current node's record if it's a message, then its children.
    def walk(node, depth, parent_chain, top_ancestor):
        is_msg = "IBufferMessage" in node["bases"]
        if is_msg:
            rec = {
                "typedef_index": node["tdi"],
                "obf_name": node["name"],
                "assembly": node.get("assembly", "?"),
                "depth": depth,
                "parent_chain": parent_chain,
                "top_ancestor": top_ancestor,
                "field_count": len(node["fields"]),
                "fields": resolve_fields(node, registry, stats),
                "nested_direct": [
                    {"name": c["name"], "kind": c["kind"], "is_message": "IBufferMessage" in c["bases"]}
                    for c in node["nested"] if c["name"] not in NOISE_NESTED_NAMES
                ],
                "nested_tree": nested_shape(node, registry, stats),
            }
            records.append(rec)
        real_children = [c for c in node["nested"] if c["name"] not in NOISE_NESTED_NAMES]
        for c in real_children:
            walk(c, depth + 1, parent_chain + [node["name"]], top_ancestor)

    for top in top_levels:
        walk(top, 0, [], top["name"])
    return records


# Point d'entrée : vérifie le motif (verifier_motif.py), parse, résout, écrit le JSONL.
# / Entry point: verifies the pattern, parses, resolves, writes the JSONL.
def main():
    if not os.path.exists(CS_PATH):
        log(f"ABSENT : {CS_PATH} — rien à extraire, je n'invente pas.")
        sys.exit(2)

    from verifier_motif import verifier_temoins  # import local : évite un cycle de modules
                                                  # (verifier_motif importe des primitives d'ici)
    with open(CS_PATH, encoding="utf-8", errors="replace") as fh:
        witness_lines = fh.read().split("\n")
    log("[témoin] vérification du motif const→champ sur 3 classes EN CLAIR (Any, Api, Duration)…")
    if not verifier_temoins(witness_lines):
        log("[témoin] ÉCHEC — le motif ne tient pas 3/3, les 2206 fiches obfusquées seraient suspectes. J'arrête.")
        sys.exit(3)
    log("[témoin] 3/3 — motif confirmé, extraction des classes obfusquées en confiance.")
    del witness_lines

    top_levels, parse_stats = parse_tree(CS_PATH)
    all_nodes = flatten(top_levels, [])
    log(f"[extraire] {len(all_nodes)} nœuds au total (top-niveau + imbriqués) dans les 2 assemblies cibles")

    registry = build_registry(all_nodes)
    ambig = sum(1 for e in registry.values() if e["ambiguous"])
    log(f"[extraire] registre global : {len(registry)} noms de feuille uniques, {ambig} ambigus (collision de nom)")

    kinds = {}
    for n in all_nodes:
        k = "message" if "IBufferMessage" in n["bases"] else n["kind"]
        kinds[k] = kinds.get(k, 0) + 1
    log(f"[extraire] répartition par nature : {kinds}")

    field_stats = {"champs_resolus": 0, "champs_non_resolus": 0, "champs_type_incertain": 0}
    records = emit_records(top_levels, registry, field_stats)

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for r in records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    log(f"[extraire] {len(records)} fiches IBufferMessage écrites → {OUT_PATH}")
    log(f"[extraire] champs : {field_stats['champs_resolus']} résolus, "
        f"{field_stats['champs_non_resolus']} non résolus (pas de backing field trouvé), "
        f"{field_stats['champs_type_incertain']} de type incertain (unresolu/ambigu)")
    log(f"[extraire] parse_stats: {parse_stats}")

    summary = {
        "classes_ibuffermessage": len(records),
        "noeuds_total": len(all_nodes),
        "repartition_par_nature": kinds,
        "champs": field_stats,
        "parse_stats": parse_stats,
        "registre_ambigus": ambig,
    }
    summary_path = os.path.join(HERE, "extraction-stats.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    log(f"[extraire] résumé → {summary_path}")


if __name__ == "__main__":
    main()
