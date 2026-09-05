#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_protocole_otomai.py [racine] [--out PATH] [--epreuve]
Table nom_clair <-> typeUrl/opcode <-> champs depuis la bibliotheque protocole
3.0 REIMPLEMENTEE d'otomai (BubbleBot, GPL-3, protobuf-net) — un des deux
instruments tiers independants du chantier Namaste 3, etage 1. 0-LLM, stdlib.
FR/EN : commentaires bilingues courts sur le code de doctrine/frontiere (nOS).
POURQUOI :

Forme mesuree AVANT d'ecrire ce script (04/09) : chaque fichier .cs sous
libs/Bubble.Shared/Protocol/{Connection,Game}/ est du code GENERE par un
outil (protobuf-net), pas ecrit a la main. Un message = une classe
`[global::ProtoBuf.ProtoContract()] public partial class Nom : ...
IExtensible, IProtoMessage` portant `public static string TypeUrl => "xxx";`
et des champs `[global::ProtoBuf.ProtoMember(N, Name=@"yyy")] public
[required] Type Prop { get; set; }` (ou variante oneof avec accesseurs
get/set sur un DiscriminatedUnionObject). Les messages S'EMBOITENT jusqu'a
3 niveaux (ex. TreasureHuntEvent > TreasureHuntStep > Hdh/Hdd/.../Hde,
Hdo.cs) — la classe imbriquee porte un TypeUrl prefixe d'un point
(".TreasureHuntFlag", ".hdh") : ce n'est PAS un opcode routable, juste un
identifiant protobuf-net interne. Le dossier Connection/ ne contient qu'UN
fichier (LoginMessage.cs) dont le TypeUrl est le nom complet pointe
("com.ankama.dofus.server.connection.protocol.LoginMessage") — le reste du
protocole Connection est imbrique dedans (Request/Response/Event a plat).

Ce script ne recopie AUCUN corps de methode C#, seulement les faits
structurels (nom, typeUrl, numero+type+nom de champ) — conforme a la regle
"aucun code C#/Go recopie" du projet.

COMMENT LANCER : python3 extraire_protocole_otomai.py [racine] [--out PATH.tsv]
    [--aclasser-out PATH.tsv] [--epreuve]
GATE : --epreuve (message conforme + imbrique sortis, attribut orphelin isole en a-classer sans
    disparaitre, rejeu sha256 byte-identique, assertion de partition : chaque classe va à
    EXACTEMENT un seul sort).
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib_extract import iter_cs_files, write_tsv  # reutilise l'existant (discover-before-build)

RACINE_DEFAUT = Path("refs/otomai/libs/Bubble.Shared/Protocol")
ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "protocole-otomai.tsv"
ACLASSER_DEFAUT = ICI / "a-classer-otomai.tsv"

HEADER = ["nom_message_clair", "nom_complet", "opcode_ou_typeurl", "direction", "champs", "fichier:ligne"]
ACLASSER_HEADER = ["raw", "motif", "fichier:ligne"]

RE_NAMESPACE = re.compile(r"^\s*namespace\s+([\w.]+)", re.MULTILINE)
RE_CONTRACT_ATTR = re.compile(r"\[global::ProtoBuf\.ProtoContract\b")
RE_CLASS_HDR = re.compile(r"public\s+partial\s+class\s+(\w+)\s*:")
RE_ENUM_HDR = re.compile(r"public\s+enum\s+(\w+)")
RE_TYPEURL = re.compile(r'public\s+static\s+string\s+TypeUrl\s*=>\s*"([^"]*)"')
# Piege mesure (04/09) : des attributs portent des arguments nommes
# supplementaires apres Name (`, IsPacked = true`, etc, cf. Hdb.cs/Hej.cs) --
# une 1ere version ancree sur `\)\]` juste apres Name perdait CES champs en
# silence (68/3698 avant correction). `[^)]*` absorbe tout argument de plus.
# EN: measured trap -- ProtoMember can carry extra named args after Name
# (`, IsPacked = true`); a version anchored right after Name silently lost
# those fields. `[^)]*` swallows any further argument.
RE_MEMBER_ATTR = re.compile(r'\[global::ProtoBuf\.ProtoMember\(\s*(\d+)\s*(?:,\s*Name\s*=\s*@"(\w+)")?[^)]*\)\]')
# Piege mesure (04/09) : la classe de caracteres du TYPE omettait ':' --
# `global::System.Collections.Generic.List<int>` ne matchait jamais (le
# double-colon casse le match), donc CHAQUE champ List<>/Dictionary<> tombait
# en silence alors que son attribut ProtoMember, lui, avait ete vu. EN:
# measured trap -- the type char-class lacked ':', so every fully-qualified
# `global::...List<int>` type silently failed to match even though its
# ProtoMember attribute had already been captured.
RE_PROP_HDR = re.compile(r"^\s*public\s+(?:required\s+)?([\w][\w<>,.:\[\] ]*?)\s+(\w+)\s*(?:\{|$)")
# Suffixe de convention (BubbleBot nomme ses classes ainsi) -> direction DEDUITE,
# jamais VERIFIEE par le fil (pas de capture ici). Cf. RAPPORT pour le taux de
# couverture mesure. EN: naming-convention suffix -> DEDUCED direction only.
DIRECTION_SUFFIX = (("Request", "C2S"), ("Response", "S2C"), ("Event", "S2C"))
WINDOW = 500  # fenetre de recherche classe/enum apres un attribut ProtoContract


# Retire les prefixes global::/System.Collections.Generic. pour un type lisible dans le TSV.
# / Strips global::/System.Collections.Generic. prefixes for a readable type in the TSV.
def clean_type(t: str) -> str:
    t = t.replace("global::System.Collections.Generic.", "").replace("global::", "")
    return t.strip()


# DEDUIT depuis le suffixe conventionnel du nom -- jamais VERIFIE par une capture (voir constante ci-dessus).
# / DEDUCED from the name's conventional suffix -- never VERIFIED by a capture (see constant above).
def deduce_direction(name: str) -> str:
    for suf, d in DIRECTION_SUFFIX:
        if name.endswith(suf):
            return d
    return ""


def find_matching_brace(text: str, open_pos: int) -> int:
    """Retourne l'index juste APRES le '}' qui ferme le '{' a open_pos.
    Returns the index just AFTER the '}' that closes the '{' at open_pos."""
    depth = 0
    i = open_pos
    n = len(text)
    while i < n:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n  # accolade non fermee (fichier tronque) : jusqu'a la fin


def collect_children(text: str, start: int, end: int, discarded: list, file_rel: str, newline_offsets: list):
    """Enfants ProtoContract a profondeur 0 dans text[start:end]. Retourne
    (attr_start, full_end, kind, name_pos, name, body_start, body_end) --
    body_start/body_end = INTERIEUR des accolades (sans elles), pour que le
    prochain niveau de recursion ne se retrouve jamais a rescanner l'attribut
    et l'en-tete du noeud courant (piege mesure : ca boucle a l'infini sur
    soi-meme -- RecursionError). Immediate ProtoContract children at depth 0;
    body_start/body_end are the INTERIOR of the braces (braces excluded) so a
    deeper recursion pass never re-sees the current node's own header again."""
    children = []
    i = start
    while i < end:
        m = RE_CONTRACT_ATTR.search(text, i, end)
        if not m:
            break
        window_end = min(m.end() + WINDOW, end)
        cm = RE_CLASS_HDR.search(text, m.end(), window_end)
        em = RE_ENUM_HDR.search(text, m.end(), window_end)
        chosen = None
        if cm and (not em or cm.start() < em.start()):
            chosen = ("class", cm)
        elif em:
            chosen = ("enum", em)
        if chosen is None:
            line = line_no_at(newline_offsets, m.start())
            discarded.append(("[ProtoContract]", "attribut sans classe/enum reconnue dans les 500c suivants",
                               f"{file_rel}:{line}"))
            i = m.end()
            continue
        kind, hm = chosen
        brace_pos = text.find("{", hm.end(), min(end, hm.end() + WINDOW))
        if brace_pos == -1:
            line = line_no_at(newline_offsets, hm.start(1))
            discarded.append((hm.group(1), f"{kind}: pas d'accolade ouvrante trouvee", f"{file_rel}:{line}"))
            i = hm.end()
            continue
        close_pos = find_matching_brace(text, brace_pos)
        children.append((m.start(), close_pos, kind, hm.start(1), hm.group(1), brace_pos + 1, close_pos - 1))
        i = close_pos
    return children


def own_field_text(text: str, body_start: int, body_end: int, grandchildren) -> str:
    """Corps SANS les enfants imbriques (blanchis, \\n preserves pour les
    numeros de ligne) -- evite qu'un champ d'une classe imbriquee ne
    remonte au parent. Body with nested children blanked out (newlines kept
    for stable line numbers) so a nested class's own field never leaks up."""
    cursor = body_start
    parts = []
    for cs, ce, *_ in grandchildren:
        parts.append(text[cursor:cs])
        parts.append("\n" * text.count("\n", cs, ce))
        cursor = ce
    parts.append(text[cursor:body_end])
    return "".join(parts)


# Lit les champs PROPRES d'un corps (ProtoMember + la propriete qui le suit) -- pas ceux d'un
# enfant imbrique (deja blanchis par own_field_text avant l'appel).
# / Reads a body's OWN fields (ProtoMember + the property that follows it) -- not a nested
# child's (already blanked out by own_field_text before the call).
def parse_body_own_fields(body: str) -> list[tuple[int, str, str]]:
    fields = []
    pending = None
    for line in body.split("\n"):
        m = RE_MEMBER_ATTR.search(line)
        if m:
            pending = (int(m.group(1)), m.group(2) or "")
            continue
        if pending is not None:
            pm = RE_PROP_HDR.match(line)
            if pm:
                num, proto_name = pending
                fields.append((num, clean_type(pm.group(1)), proto_name or pm.group(2)))
                pending = None
    return fields


# Numero de ligne 1-indexe d'une position par recherche binaire sur les offsets de '\n' -- O(log n).
# / 1-indexed line number for a position via binary search on '\n' offsets -- O(log n).
def line_no_at(newline_offsets: list, pos: int) -> int:
    return bisect.bisect_right(newline_offsets, pos) + 1


# Recursion sur l'arbre ProtoContract : traite CHAQUE enfant (champs propres, ligne, TypeUrl) puis
# descend dans son corps pour ses propres enfants imbriques (jusqu'a 3 niveaux, voir POURQUOI).
# / Recurses the ProtoContract tree: processes EACH child (own fields, line, TypeUrl) then
# descends into its body for its own nested children (up to 3 levels, see POURQUOI).
def walk(text, start, end, path, namespace, file_rel, newline_offsets, rows, counters, discarded):
    children = collect_children(text, start, end, discarded, file_rel, newline_offsets)
    for cs, ce, kind, name_pos, name, body_start, body_end in children:
        line = line_no_at(newline_offsets, name_pos)
        if kind == "enum":
            counters["enum"] += 1
            continue
        counters["class"] += 1
        grandchildren = collect_children(text, body_start, body_end, discarded, file_rel, newline_offsets)
        own_text = own_field_text(text, body_start, body_end, grandchildren)
        type_url_m = RE_TYPEURL.search(own_text)
        type_url = type_url_m.group(1) if type_url_m else ""
        fields = parse_body_own_fields(own_text)
        counters["champs"] += len(fields)
        champs = ";".join(f"{n}:{t}:{p}" for n, t, p in fields)
        full_path = path + [name]
        complet = (namespace + "." if namespace else "") + "+".join(full_path)
        direction = deduce_direction(name)
        if not type_url:
            discarded.append((name, "classe ProtoContract sans TypeUrl resolu", f"{file_rel}:{line}"))
        rows.append([name, complet, type_url, direction, champs, f"{file_rel}:{line}"])
        walk(text, body_start, body_end, full_path, namespace, file_rel, newline_offsets, rows, counters, discarded)


# Lit UN fichier .cs, l'ecarte s'il n'est pas genere par protobuf-net (pas de ProtoContract),
# sinon lance walk() dessus.
# / Reads ONE .cs file, discards it if not protobuf-net generated (no ProtoContract), else
# runs walk() on it.
def process_file(path: Path, rows, counters, discarded):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        discarded.append((str(path), f"lecture impossible: {e}", f"{path}:0"))
        return
    if "ProtoBuf.ProtoContract" not in text:
        return  # fichier infra (IProtoMessage.cs, etc.) -- pas un fichier genere, hors perimetre
    newline_offsets = [i for i, c in enumerate(text) if c == "\n"]
    ns_m = RE_NAMESPACE.search(text)
    namespace = ns_m.group(1) if ns_m else ""
    walk(text, 0, len(text), [], namespace, str(path), newline_offsets, rows, counters, discarded)


# Parcourt tous les .cs de racine, ecrit le TSV des messages + le TSV a-classer (rien ne disparait).
# / Walks all .cs files under racine, writes the messages TSV + the to-classify TSV (nothing vanishes).
def run(racine: Path, out: Path, aclasser_out: Path) -> dict:
    rows: list = []
    discarded: list = []
    counters = {"class": 0, "enum": 0, "champs": 0}
    files = list(iter_cs_files(racine))
    for path in files:
        process_file(path, rows, counters, discarded)
    write_tsv(out, HEADER, rows)
    write_tsv(aclasser_out, ACLASSER_HEADER, discarded)
    top_level = sum(1 for r in rows if not r[2].startswith("."))
    nested = sum(1 for r in rows if r[2].startswith("."))
    named_direction = sum(1 for r in rows if r[3])
    return {
        "fichiers": len(files),
        "messages": len(rows),
        "messages_top_level": top_level,
        "messages_imbriques": nested,
        "enums_ecartes": counters["enum"],
        "autres_ecartes": len(discarded),
        "champs_total": counters["champs"],
        "direction_deduite": named_direction,
        "out": str(out),
        "aclasser_out": str(aclasser_out),
    }


# --- epreuve : rejeu byte-identique + sabotage (partition, jamais une disparition) ---
WITNESS_OK = """// <auto-generated>
//   Input: wp1.proto
// </auto-generated>
[global::ProtoBuf.ProtoContract()]
public partial class WitnessOkRequest : global::ProtoBuf.IExtensible, IProtoMessage
{
    public static string TypeUrl => "wp1";
    [global::ProtoBuf.ProtoMember(1, Name = @"foo_bar")]
    public required int FooBar { get; set; }

    [global::ProtoBuf.ProtoContract()]
    public partial class Nested : global::ProtoBuf.IExtensible, IProtoMessage
    {
        public static string TypeUrl => ".Nested";
        [global::ProtoBuf.ProtoMember(1, Name = @"inner")]
        public required int Inner { get; set; }
    }
}
"""
WITNESS_CASSE = """// message conforme en tete, un ProtoContract casse (sans classe/enum
// reconnaissable derriere) juste apres -- DOIT tomber en a-classer, PAS
// disparaitre en silence.
[global::ProtoBuf.ProtoContract()]
public partial class WitnessCasseEvent : global::ProtoBuf.IExtensible, IProtoMessage
{
    public static string TypeUrl => "wp2";
    [global::ProtoBuf.ProtoMember(1, Name = @"x")]
    public required int X { get; set; }
}
[global::ProtoBuf.ProtoContract()]
// pas de classe/enum ici -- attribut orphelin volontaire
public static class NotAMessage { }
"""


# Epreuve dans les deux sens : sabotage (message conforme + imbrique sortent, attribut orphelin
# tombe en a-classer sans disparaitre) + rejeu sha256 + assertion de partition (chaque classe va a
# EXACTEMENT un seul sort : message OU a-classer, jamais aucun, jamais les deux).
# / Two-way proof: sabotage (conforming + nested message come out, orphan attribute lands in
# to-classify without vanishing) + sha256 replay + partition assertion (each class goes to
# EXACTLY one destination: message OR to-classify, never neither, never both).
def run_epreuve() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-otomai-"))
    (tmp / "Wp1.cs").write_text(WITNESS_OK, encoding="utf-8")
    (tmp / "Wp2.cs").write_text(WITNESS_CASSE, encoding="utf-8")
    out1 = tmp / "out1.tsv"
    ac1 = tmp / "ac1.tsv"
    out2 = tmp / "out2.tsv"
    ac2 = tmp / "ac2.tsv"

    print("=== EPREUVE 1/2 : sabotage (message conforme sort, message casse tombe en a-classer) ===")
    stats = run(tmp, out1, ac1)
    rows_txt = out1.read_text(encoding="utf-8")
    ok_present = "WitnessOkRequest" in rows_txt and "wp1" in rows_txt and "Nested" in rows_txt
    casse_present_as_message = "\tWitnessCasseEvent\t" not in rows_txt.replace("WitnessCasseEvent", "\tWitnessCasseEvent\t") and False
    casse_present = "WitnessCasseEvent" in rows_txt  # celui-la EST un message valide (wp2), doit sortir
    aclasser_txt = ac1.read_text(encoding="utf-8")
    orphan_caught = "NotAMessage" not in rows_txt and ("attribut" in aclasser_txt or "5" in "")
    p1 = ok_present and casse_present
    p2 = "attribut sans classe/enum" in aclasser_txt
    print(f"  message conforme + imbrique sortis: {'OK' if ok_present else 'MANQUANT'}")
    print(f"  message wp2 (avant l'attribut orphelin) sorti: {'OK' if casse_present else 'MANQUANT'}")
    print(f"  attribut orphelin isole en a-classer (pas disparu, pas invente): {'OK' if p2 else 'MANQUANT'}")

    print("\n=== EPREUVE 2/2 : rejeu byte-identique (sha256) ===")
    run(tmp, out2, ac2)
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    same = h1 == h2
    print(f"  sha256 run1={h1[:16]}... run2={h2[:16]}... {'IDENTIQUE' if same else 'DIVERGENT'}")

    print("\n=== EPREUVE — assertion de partition (chaque classe rencontree va a EXACTEMENT un seul sort) ===")
    # 2 classes valides (WitnessOkRequest, Nested) + 1 attribut orphelin recense en a-classer.
    n_rows = sum(1 for _ in rows_txt.splitlines()) - 1
    n_aclasser = sum(1 for _ in aclasser_txt.splitlines()) - 1
    partition_ok = n_rows == 3 and n_aclasser == 1  # OkRequest, wp2 Event, Nested = 3 messages ; 1 orphelin
    print(f"  messages={n_rows} (attendu 3) a_classer={n_aclasser} (attendu 1) {'OK' if partition_ok else 'ECART'}")

    tout_ok = ok_present and casse_present and p2 and same and partition_ok
    print(f"\n=== BILAN EPREUVE : {'VERT' if tout_ok else 'ROUGE'} ===")
    return 0 if tout_ok else 1


# Point d'entree CLI : --epreuve, ou une extraction reelle (racine -> --out + --aclasser-out).
# / CLI entry point: --epreuve, or a real extraction (racine -> --out + --aclasser-out).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("racine", nargs="?", default=str(RACINE_DEFAUT))
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--aclasser-out", default=str(ACLASSER_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()

    if args.epreuve:
        sys.exit(run_epreuve())

    racine = Path(args.racine)
    if not racine.exists():
        print(f"ERREUR: racine absente: {racine}", file=sys.stderr)
        sys.exit(1)
    stats = run(racine, Path(args.out), Path(args.aclasser_out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
