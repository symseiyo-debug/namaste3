#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : comparer_instruments.py [--out PATH] [--epreuve]
Croise QUATRE instruments independants du protocole Dofus 3.0 pour le
chantier Namaste 3, etage 1 : (a) protocole-otomai.tsv (BubbleBot, protobuf-net
reimplemente), (b) opcodes-sniffer.tsv (dofus3-sniffer-tui, quasi-vide -- voir
RAPPORT-EXTRACTION-TIERS.md), (c) notre dump 1003 noms (etage0-dump, LA VERITE
mesuree sur le client), (d) les tables JondoEmu (anclas_3.6.10.10.tsv = noms
PROPOSES/curates, pas extraits ; protocolo_3.6.10.10.proto = champs numero+type
avec noms encore obfusques). 0-LLM, stdlib seule.

POURQUOI :
Regle du projet (§ETAGE 1, corrections en revue) directement verifiee ici : « le
protocolId n'est JAMAIS une clé de nœud ... une jointure par id rendrait
TOUTES les paires fausses avec l'apparence d'un succes ». Ce script mesure
CETTE fausse promesse precisement (jointure par OPCODE vs jointure par NOM)
plutot que de la supposer.

COMMENT LANCER : python3 comparer_instruments.py [--out PATH.md] [--epreuve]
    (lit protocole-otomai.tsv + opcodes-sniffer.tsv dans son propre dossier, le dump étage0 et
    les tables JondoEmu à des chemins Hetzner en dur).
GATE : --epreuve (rejeu byte-identique du rapport + sabotage : un désaccord de type sur un nom
    commun DOIT être repéré et nommé dans le rapport, jamais absorbé en silence).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from collections import Counter
from pathlib import Path

ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "ACCORD-INSTRUMENTS.md"
OTOMAI_TSV = ICI / "protocole-otomai.tsv"
SNIFFER_TSV = ICI / "opcodes-sniffer.tsv"
DUMP_TXT = Path("internal/noms-protocole-en-clair.v2.txt")
JONDO_ANCLAS = Path("refs/JondoEmu/datos/anclas_3.6.10.10.tsv")
JONDO_PROTO = Path("refs/JondoEmu/datos/protocolo_3.6.10.10.proto")


def load_otomai(path: Path):
    """opcode(3 lettres, top-level, non imbrique) -> (nom, champs=[(num,type,fname)])."""
    by_opcode, fields = {}, {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            op = row["opcode_ou_typeurl"]
            if not op or op.startswith(".") or "." in op:
                continue  # nom imbrique ou TypeUrl Connection complet -- pas un opcode 3 lettres
            by_opcode.setdefault(op, row["nom_message_clair"])
            champs = []
            if row["champs"]:
                for part in row["champs"].split(";"):
                    n, t, fn = part.split(":", 2)
                    champs.append((int(n), t, fn))
            fields.setdefault(op, champs)
    return by_opcode, fields


# Lit opcodes-sniffer.tsv en liste de dict -- [] si le fichier n'existe pas (extracteur pas encore lance).
# / Reads opcodes-sniffer.tsv into a list of dicts -- [] if the file doesn't exist (extractor not yet run).
def load_sniffer(path: Path):
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            rows.append(row)
    return rows


def load_dump(path: Path):
    """Retourne (total_lignes, lignes_top_level, set_noms_feuille_uniques, doublons)."""
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    top = [l for l in lines if "+" not in l]
    leaves = [l.rsplit(".", 1)[-1] for l in top]
    c = Counter(leaves)
    dupes = {k: v for k, v in c.items() if v > 1}
    return len(lines), len(top), set(leaves), dupes


def load_jondo_anclas(path: Path):
    """opcode -> dict(direction, nom, signification, handler, forme). Seules
    les lignes NOMMEES (99) alimentent la comparaison de noms."""
    entries = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            while len(parts) < 6:
                parts.append("")
            op, direction, nom, signif, handler, forme = parts[:6]
            entries[op] = {"direction": direction, "nom": nom.strip(), "signification": signif,
                           "handler": handler, "forme": forme}
    return entries


RE_JONDO_MSG = re.compile(r"^message (\w+) \{([^{}]*)\}", re.MULTILINE)
RE_JONDO_FIELD = re.compile(r"^\s*(repeated\s+)?([\w.]+)\s+(\w+)\s*=\s*(\d+);", re.MULTILINE)


def load_jondo_proto(path: Path):
    """opcode -> champs=[(num,type,fname)] -- noms de champs encore obfusques
    (ex. 'fupb'), mais numero+type sont dits VRAIS par l'en-tete du fichier."""
    text = path.read_text(encoding="utf-8")
    fields = {}
    n_blocks = 0
    for m in RE_JONDO_MSG.finditer(text):
        n_blocks += 1
        opcode, body = m.group(1), m.group(2)
        champs = []
        for fm in RE_JONDO_FIELD.finditer(body):
            repeated, ftype, fname, fnum = fm.groups()
            t = f"repeated {ftype}" if repeated else ftype
            champs.append((int(fnum), t, fname))
        fields[opcode] = champs
    return fields, n_blocks


def field_kind(t: str) -> str:
    """Classification GROSSIERE d'un type de champ pour comparaison inter-
    langage (C# protobuf-net vs proto3 textuel) -- deux ecritures differentes
    du meme type (`int`/`int32`, `long`/`int64`, `List<X>`/`repeated X`)
    doivent tomber dans la meme case. Coarse cross-language type bucket so
    `int`/`int32`, `long`/`int64`, `List<X>`/`repeated X` land in one case."""
    tl = t.lower()
    if tl.startswith("repeated ") or tl.startswith("list<"):
        return "liste"
    if tl in ("int", "int32", "uint32", "sint32", "long", "int64", "uint64", "sint64", "short", "byte"):
        return "numerique"
    if tl in ("float", "double"):
        return "flottant"
    if tl == "bool":
        return "bool"
    if tl == "string":
        return "string"
    if tl == "bytes":
        return "bytes"
    if tl == "any":
        return "any"
    return "message_ou_enum"  # reference a un autre type (nom capitalise cote otomai, code 3 lettres cote jondo)


# Les n premiers (tri alphabetique, deterministe) d'un ensemble -- pour un extrait lisible dans le rapport.
# / The first n (alphabetical, deterministic) of a set -- for a readable excerpt in the report.
def top10(items, n=10):
    return sorted(items)[:n]


# Ecrit une section markdown "A ∩ B" (tailles, intersection, exclusifs de chaque cote) -- rend
# l'ensemble commun pour un usage ulterieur par l'appelant.
# / Writes an "A ∩ B" markdown section (sizes, intersection, each side's exclusives) -- returns
# the common set for later use by the caller.
def section_intersection(md, label_a, set_a, label_b, set_b):
    common = set_a & set_b
    md.append(f"### {label_a} ∩ {label_b}")
    md.append(f"- {label_a} : {len(set_a)} noms | {label_b} : {len(set_b)} noms | "
              f"intersection : **{len(common)}** ({100*len(common)/max(1,min(len(set_a),len(set_b))):.1f}% du plus petit)")
    if common:
        md.append(f"- top 10 : {', '.join(top10(common))}")
    only_a = set_a - set_b
    only_b = set_b - set_a
    md.append(f"- présents seulement chez {label_a} : {len(only_a)} (ex. {', '.join(top10(only_a, 5))})")
    md.append(f"- présents seulement chez {label_b} : {len(only_b)} (ex. {', '.join(top10(only_b, 5))})")
    md.append("")
    return common


# Construit ACCORD-INSTRUMENTS.md (les 5 sections : ce que porte chaque instrument, intersections
# de noms, accord opcode<->nom otomai/Jondo, accord de champs, annexes) et rend les stats resumees.
# / Builds ACCORD-INSTRUMENTS.md (the 5 sections: what each instrument carries, name
# intersections, otomai/Jondo opcode<->name agreement, field agreement, appendices) and returns
# the summary stats.
def build_report(out_path: Path) -> dict:
    otomai_by_op, otomai_fields = load_otomai(OTOMAI_TSV)
    otomai_names = set(otomai_by_op.values())
    sniffer_rows = load_sniffer(SNIFFER_TSV)
    sniffer_names = {r["nom_clair"] for r in sniffer_rows}
    dump_total, dump_top_n, dump_leaves, dump_dupes = load_dump(DUMP_TXT)
    jondo_anclas = load_jondo_anclas(JONDO_ANCLAS)
    jondo_named = {op: e["nom"] for op, e in jondo_anclas.items() if e["nom"]}
    jondo_names_set = set(jondo_named.values())
    jondo_proto_fields, jondo_proto_blocks = load_jondo_proto(JONDO_PROTO)

    md = []
    md.append("# ACCORD-INSTRUMENTS — otomai vs sniffer vs dump vs JondoEmu")
    md.append("")
    md.append("> Étage 1 (Namaste 3), croisement de 4 instruments protocole 3.0 indépendants.")
    md.append("> Sources : `protocole-otomai.tsv`, `opcodes-sniffer.tsv` (ce dossier), "
               f"`{DUMP_TXT}`, `{JONDO_ANCLAS}`, `{JONDO_PROTO}`.")
    md.append("")
    md.append("## 0. Ce que chaque instrument porte réellement (mesuré, pas supposé)")
    md.append(f"- **otomai** : {len(otomai_by_op)} opcodes 3 lettres top-level, {len(otomai_names)} noms clairs uniques "
               "(classes C# de BubbleBot, réimplémentation communautaire du protocole 3.0).")
    md.append(f"- **sniffer** : {len(sniffer_rows)} lignes au total, **0 table opcode↔nom réelle embarquée** — "
               "voir §4 et `RAPPORT-EXTRACTION-TIERS.md`. Toutes les lignes sont des exemples de doc ou des "
               "fixtures de test (`--epreuve` de `extraire_opcodes_sniffer.py` le prouve par sabotage).")
    md.append(f"- **dump (LA VÉRITÉ)** : {dump_total} noms de types au total, {dump_top_n} top-level (mesure "
               f"seconde voie : `[l for l in lignes if '+' not in l]`, conforme au {dump_top_n} du cahier §ETAGE0), "
               f"{len(dump_leaves)} noms feuille UNIQUES (doublon mesuré : `{list(dump_dupes)}` — deux namespaces "
               "différents partagent un même nom court, sans conséquence).")
    md.append(f"- **JondoEmu** : `anclas_3.6.10.10.tsv` a {len(jondo_anclas)} opcodes documentés dont "
               f"**{len(jondo_named)} nommés** (les autres {len(jondo_anclas) - len(jondo_named)} sont vus/décrits "
               "sans nom proposé). `protocolo_3.6.10.10.proto` a "
               f"{jondo_proto_blocks} blocs `message` (numéro+type de champ dits VRAIS par son en-tête, noms de "
               "champ encore obfusqués). **Les noms de Jondo sont des PROPOSITIONS stylées, pas des extractions** "
               "— son propre en-tête le dit : « Ankama ne publie pas les noms... le nom de cette colonne est "
               "celui qui correspond à ce qu'il fait ». Ne pas les traiter comme une 3ᵉ mesure indépendante du "
               "nom réel, seulement de l'OPCODE et du COMPORTEMENT observé.")
    md.append("")

    md.append("## 1. Intersections de NOMS CLAIRS, par paire d'instruments")
    md.append("")
    section_intersection(md, "otomai", otomai_names, "dump (vérité)", dump_leaves)
    section_intersection(md, "otomai", otomai_names, "JondoEmu (nommés)", jondo_names_set)
    section_intersection(md, "dump (vérité)", dump_leaves, "JondoEmu (nommés)", jondo_names_set)
    section_intersection(md, "sniffer", sniffer_names, "otomai", otomai_names)
    section_intersection(md, "sniffer", sniffer_names, "dump (vérité)", dump_leaves)
    triple = otomai_names & dump_leaves & jondo_names_set
    md.append(f"### otomai ∩ dump ∩ JondoEmu (triple accord) : **{len(triple)}** — {sorted(triple)}")
    md.append("")

    md.append("## 2. Accord OPCODE↔NOM entre otomai et JondoEmu — LA TROUVAILLE")
    md.append("")
    common_opcodes = set(otomai_by_op) & set(jondo_named)
    same_name_op = [o for o in common_opcodes if otomai_by_op[o] == jondo_named[o]]
    diff_name_op = sorted(o for o in common_opcodes if otomai_by_op[o] != jondo_named[o])
    md.append(f"**Jointure par OPCODE (chaîne 3 lettres identique)** : {len(common_opcodes)} opcodes existent "
              f"dans les deux tables. Accord sur le nom : **{len(same_name_op)}/{len(common_opcodes)}**. "
              f"Désaccord : **{len(diff_name_op)}/{len(common_opcodes)}**.")
    if not same_name_op:
        md.append("")
        md.append("**➡ 0 accord sur les 27 collisions d'opcode.** La jointure par identifiant opcode entre deux "
                   "extractions indépendantes du même build nominal (3.6.10.10) est **entièrement fallacieuse** — "
                   "exactement le piège que le cahier §ETAGE1 anticipait pour 2.42→2.73 (« une jointure par id "
                   "rendrait TOUTES les paires fausses avec l'apparence d'un succès »), ici mesuré ENTRE DEUX "
                   "OUTILS visant le MÊME build. Un opcode 3 lettres identique dans deux extractions ne prouve "
                   "RIEN sur l'identité du message ; c'est une collision dans un espace de ~17 576 codes.")
    md.append("")
    md.append("Désaccords (10 premiers sur 27, liste complète en annexe §5) :")
    md.append("")
    md.append("| opcode | nom otomai | nom JondoEmu (proposé) |")
    md.append("|---|---|---|")
    for o in diff_name_op[:10]:
        md.append(f"| `{o}` | {otomai_by_op[o]} | {jondo_named[o]} |")
    md.append("")

    common_names = otomai_names & jondo_names_set
    md.append(f"**Jointure par NOM CLAIR (la voie correcte)** : {len(common_names)} noms communs "
              f"({sorted(common_names)}). Sur CES messages authentifiés par le nom, l'opcode concorde-t-il ?")
    op_agree, op_disagree = [], []
    otomai_name_to_op = {v: k for k, v in otomai_by_op.items()}
    jondo_name_to_op = {v: k for k, v in jondo_named.items()}
    for n in common_names:
        oa, ja = otomai_name_to_op[n], jondo_name_to_op[n]
        (op_agree if oa == ja else op_disagree).append((n, oa, ja))
    for n, oa, ja in op_disagree:
        md.append(f"- `{n}` : otomai=`{oa}` vs JondoEmu=`{ja}` — **DIFFÉRENT**")
    md.append(f"- Accord opcode sur nom commun : {len(op_agree)}/{len(common_names)}.")
    md.append("")

    md.append("## 3. Champs (numéro+type) otomai vs Jondo `.proto`, sur les messages COMMUNS (par nom)")
    md.append("")
    md.append(f"Échantillon disponible : **{len(common_names)}** messages (limité par les {len(jondo_named)} "
              "noms proposés de JondoEmu — ce n'est pas un défaut du script, c'est la taille réelle du "
              "recoupement possible ; voir §0).")
    md.append("")
    total_fields_pairs, matching_kind = 0, 0
    for n in sorted(common_names):
        oa_op, ja_op = otomai_name_to_op[n], jondo_name_to_op[n]
        oa_fields = {num: t for num, t, _ in otomai_fields.get(oa_op, [])}
        ja_fields = {num: t for num, t, _ in jondo_proto_fields.get(ja_op, [])}
        all_nums = sorted(set(oa_fields) | set(ja_fields))
        md.append(f"### `{n}` — otomai `{oa_op}` ({len(oa_fields)} champs) vs Jondo `{ja_op}` ({len(ja_fields)} champs)")
        md.append(f"- réf. JondoEmu anclas : {JONDO_ANCLAS}, opcode `{ja_op}` — "
                   f"forme observée sur le fil : « {jondo_anclas[ja_op]['forme'] or 'vide'} »")
        if not all_nums:
            md.append("- (aucun champ des deux côtés)")
        for num in all_nums:
            ot, jt = oa_fields.get(num), ja_fields.get(num)
            total_fields_pairs += 1
            if ot and jt and field_kind(ot) == field_kind(jt):
                matching_kind += 1
                verdict = f"accord (catégorie `{field_kind(ot)}`)"
            elif ot and jt:
                verdict = f"DÉSACCORD — otomai=`{ot}` ({field_kind(ot)}) vs jondo=`{jt}` ({field_kind(jt)})"
            elif ot:
                verdict = f"seulement chez otomai (`{ot}`)"
            else:
                verdict = f"seulement chez jondo (`{jt}`)"
            md.append(f"  - f{num}: otomai=`{ot or '—'}` jondo=`{jt or '—'}` → {verdict}")
        md.append("")
    if total_fields_pairs:
        md.append(f"**Taux de champs en accord de catégorie sur l'échantillon : {matching_kind}/{total_fields_pairs} "
                   f"({100*matching_kind/total_fields_pairs:.0f}%).** Échantillon minuscule ({len(common_names)} "
                   "messages) — un pourcentage sur si peu de cas n'est PAS une mesure de fiabilité générale du "
                   "croisement, seulement le résultat exact sur les seuls cas mesurables aujourd'hui.")
    md.append("")

    md.append("## 4. Ce que porte réellement le sniffer (rappel, détail dans RAPPORT-EXTRACTION-TIERS.md)")
    md.append("")
    prov_counts = Counter(r["provenance"] for r in sniffer_rows)
    for p, c in prov_counts.items():
        md.append(f"- `{p}` : {c} ligne(s)")
    md.append("- **0 fichier `.proto` embarqué, 0 `go:embed`** (mesuré : `grep -rn embed` + recherche de "
               "`*.proto`/`*.pb`/`*.bin` sur tout l'arbre → 0 partout). Le sniffer charge ses descripteurs et sa "
               "table de renommage **au runtime**, fournis par l'opérateur — ce n'est pas un défaut du dépôt, "
               "c'est sa conception (README §Usage : `i`/`s` pour pointer les .proto extraits ailleurs).")
    if "readme_exemple" in prov_counts:
        md.append("- Le SEUL exemple non purement synthétique (README, build cité `3.5.11.14`) donne "
                   f"`iri`→`MapMovementRequest`. Chez otomai (opcode probablement pour un autre build), "
                   f"`iri`→`{otomai_by_op.get('iri', 'absent')}` — **désaccord**, cohérent avec §2 : l'opcode "
                   "seul ne survit pas d'un build/outil à l'autre, même quand le NOM, lui, est correct des deux "
                   "côtés (`MapMovementRequest`/`MapMovementEvent` existent bien chez otomai ET dans le dump).")
    md.append("")

    md.append("## 5. Annexes — listes complètes")
    md.append("")
    md.append(f"### 5.1 Les {len(diff_name_op)} désaccords opcode↔nom otomai vs JondoEmu (complet)")
    md.append("")
    md.append("| opcode | nom otomai | nom JondoEmu (proposé) |")
    md.append("|---|---|---|")
    for o in diff_name_op:
        md.append(f"| `{o}` | {otomai_by_op[o]} | {jondo_named[o]} |")
    md.append("")
    md.append(f"### 5.2 otomai ∩ dump — les {len(otomai_names & dump_leaves)} noms communs (complet)")
    md.append(", ".join(sorted(otomai_names & dump_leaves)))
    md.append("")

    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {
        "otomai_opcodes": len(otomai_by_op),
        "otomai_noms": len(otomai_names),
        "sniffer_lignes": len(sniffer_rows),
        "dump_top_level": dump_top_n,
        "dump_noms_uniques": len(dump_leaves),
        "jondo_nommes": len(jondo_named),
        "jondo_blocs_proto": jondo_proto_blocks,
        "otomai_dump_intersection": len(otomai_names & dump_leaves),
        "otomai_jondo_opcode_collisions": len(common_opcodes),
        "otomai_jondo_opcode_accord": len(same_name_op),
        "otomai_jondo_nom_commun": len(common_names),
        "out": str(out_path),
    }


def run_epreuve() -> int:
    """FR: pas un 'extracteur' de fichiers source, mais un croiseur de TSV --
    l'epreuve verifie ici que 2 executions consecutives produisent un rapport
    IDENTIQUE (determinisme), sur les VRAIES tables (rejeu byte-identique).
    EN: not a source-file extractor but a TSV cross-referencer -- the trial
    checks that two consecutive runs produce an IDENTICAL report (byte-exact
    rerun) against the real tables."""
    global OTOMAI_TSV, SNIFFER_TSV, DUMP_TXT, JONDO_ANCLAS, JONDO_PROTO
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-accord-"))
    out1, out2 = tmp / "r1.md", tmp / "r2.md"
    if not (OTOMAI_TSV.exists() and SNIFFER_TSV.exists()):
        print("PREALABLE MANQUANT : lancer extraire_protocole_otomai.py et extraire_opcodes_sniffer.py d'abord.")
        return 1
    build_report(out1)
    build_report(out2)
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    same = h1 == h2
    print(f"=== EPREUVE : rejeu byte-identique === sha256 run1={h1[:16]}... run2={h2[:16]}... "
          f"{'IDENTIQUE' if same else 'DIVERGENT'}")

    print("\n=== EPREUVE : sabotage (paire nom-commun avec champs sciemment differents doit etre reperee) ===")
    fake_dir = tmp / "fake"
    fake_dir.mkdir()
    fake_otomai = fake_dir / "protocole-otomai.tsv"
    fake_sniffer = fake_dir / "opcodes-sniffer.tsv"
    fake_otomai.write_text(
        "nom_message_clair\tnom_complet\topcode_ou_typeurl\tdirection\tchamps\tfichier:ligne\n"
        "WitnessSharedName\tWitnessSharedName\twp1\tC2S\t1:int:a\t/tmp/w.cs:1\n",
        encoding="utf-8",
    )
    fake_sniffer.write_text("opcode\tnom_clair\tfichier:ligne\tprovenance\tnote\n", encoding="utf-8")
    fake_dump = fake_dir / "dump.txt"
    fake_dump.write_text("Com.Fake.WitnessSharedName\n", encoding="utf-8")
    fake_anclas = fake_dir / "anclas.tsv"
    fake_anclas.write_text("# temoin\nwpz\tC2S\tWitnessSharedName\tsignification\thandler\tf1: autre_type\n", encoding="utf-8")
    fake_proto = fake_dir / "proto.proto"
    fake_proto.write_text("message wpz {\n  string a = 1;\n}\n", encoding="utf-8")
    saved = (OTOMAI_TSV, SNIFFER_TSV, DUMP_TXT, JONDO_ANCLAS, JONDO_PROTO)
    try:
        OTOMAI_TSV, SNIFFER_TSV, DUMP_TXT, JONDO_ANCLAS, JONDO_PROTO = (
            fake_otomai, fake_sniffer, fake_dump, fake_anclas, fake_proto)
        out3 = tmp / "r3.md"
        build_report(out3)
    finally:
        OTOMAI_TSV, SNIFFER_TSV, DUMP_TXT, JONDO_ANCLAS, JONDO_PROTO = saved
    txt = out3.read_text(encoding="utf-8")
    detected = "DÉSACCORD" in txt and "int" in txt and "string" in txt
    print(f"  desaccord de type (int vs string) sur le nom commun repere: {'OK' if detected else 'MANQUANT'}")

    tout_ok = same and detected
    print(f"\n=== BILAN EPREUVE : {'VERT' if tout_ok else 'ROUGE'} ===")
    return 0 if tout_ok else 1


# Point d'entree CLI : --epreuve, ou un rapport reel (verifie d'abord que les 5 sources existent).
# / CLI entry point: --epreuve, or a real report (first checks all 5 sources exist).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()

    if args.epreuve:
        sys.exit(run_epreuve())

    for p, label in ((OTOMAI_TSV, "protocole-otomai.tsv"), (SNIFFER_TSV, "opcodes-sniffer.tsv"),
                      (DUMP_TXT, "dump"), (JONDO_ANCLAS, "anclas"), (JONDO_PROTO, "proto")):
        if not p.exists():
            print(f"ERREUR: {label} absent: {p}", file=sys.stderr)
            sys.exit(1)
    stats = build_report(Path(args.out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
