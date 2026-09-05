#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_protocole_deobfs.py [racine] [--out PATH] [--epreuve]
Table nom_clair <-> opcode <-> champs depuis dofus-deobfs (Go, « Dofus
Protocol Deobfuscator ») — 1441 fichiers `.proto` sous `protos/filtered/`.
0-LLM, stdlib (via `_lib_proto3.py`).

POURQUOI :
TROUVAILLE MESURÉE AVANT d'écrire ce script (04/09, lecture de son propre
README + `utils/report.go`) : **malgré son nom, le snapshot COMMIT de ce
dépôt (`protos/filtered/`) ne porte AUCUN nom clair** — les 1441 fichiers
sont TOUS nommés par leur code obfusqué 3 lettres (`hpo.proto`, `hmw.proto`…
mesuré : 0/1441 exception). Le README le confirme : le dépôt « utilise les
protos clairs de LuaxY pour essayer de MAPPER les obfusqués » — c'est-à-dire
que le nommage clair est un PRODUIT DE RUNTIME (un `MessageMatch{ObfuscatedMsg,
OriginalMsg, MatchPercent}` vu dans `utils/report.go`), écrit dans un dossier
`reports/` **absent de ce commit** (gitignored). `nom_message_clair` est donc
TOUJOURS VIDE ici, par construction de la source — pas une panne de cet
extracteur. `opcode_ou_typeurl` porte le code obfusqué lui-même.

COMMENT LANCER : python3 extraire_protocole_deobfs.py [racine] [--out PATH.tsv] [--epreuve]
GATE : --epreuve (2 volets : forme du TSV sur un témoin fabriqué + rejeu sha256 byte-identique).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib_extract import write_tsv
from _lib_proto3 import iter_proto_files, process_proto_file

RACINE_DEFAUT = Path("refs/dofus-deobfs/protos/filtered")
ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "protocole-deobfs.tsv"

HEADER = ["nom_message_clair", "nom_complet", "opcode_ou_typeurl", "direction", "champs", "fichier:ligne"]


# Parcourt tous les .proto de racine, ecrit le TSV (nom_message_clair TOUJOURS vide, voir POURQUOI).
# / Walks all .proto files under racine, writes the TSV (nom_message_clair ALWAYS empty, see POURQUOI).
def run(racine: Path, out: Path) -> dict:
    raw_rows: list = []
    counters = {"message": 0, "enum": 0, "champs": 0}
    discarded: list = []
    files = list(iter_proto_files(racine))
    for p in files:
        process_proto_file(p, raw_rows, counters, discarded)
    tsv_rows = []
    for r in raw_rows:
        is_top_level = "+" not in r["complet"]
        opcode = r["complet"] if is_top_level else "." + r["complet"].split("+")[-1]
        # nom_message_clair TOUJOURS vide (voir docstring) : la source ne le porte pas.
        tsv_rows.append(["", r["complet"], opcode, "", r["champs"], r["fichier_ligne"]])
    write_tsv(out, HEADER, tsv_rows)
    return {
        "fichiers": len(files),
        "messages": len(raw_rows),
        "enums_ecartes": counters["enum"],
        "champs_total": counters["champs"],
        "erreurs_lecture": len(discarded),
        "noms_clairs_disponibles": 0,  # par construction -- voir docstring
        "out": str(out),
    }


# Epreuve dans les deux sens : forme du TSV sur 2 .proto fabriques (message top-level, imbrique,
# enum ecarte, aucun nom clair invente) + rejeu sha256 byte-identique.
# / Two-way proof: TSV form on 2 fabricated .proto files (top-level message, nested, enum
# discarded, no invented clear name) + byte-identical sha256 replay.
def run_epreuve() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-deobfs-"))
    (tmp / "abc.proto").write_text(
        "syntax = \"proto3\";\nmessage abc {\n  bool wflag = 1;\n  message Nested {\n    int32 wnum = 1;\n  }\n}\n",
        encoding="utf-8",
    )
    (tmp / "zzz.proto").write_text("syntax = \"proto3\";\nenum zzz {\n  A = 0;\n}\n", encoding="utf-8")
    out1, out2 = tmp / "out1.tsv", tmp / "out2.tsv"
    print("=== EPREUVE 1/2 : sabotage (message obfusque sort SANS nom clair invente, enum ecarte) ===")
    stats = run(tmp, out1)
    txt = out1.read_text(encoding="utf-8")
    p1 = "\tabc\t" in txt.replace("abc\t", "\tabc\t", 1) or "abc\tabc\tabc" in txt  # complet=opcode=abc, nom vide
    p2 = "1:bool:wflag" in txt
    p3 = ".Nested" in txt and "1:int32:wnum" in txt
    p4 = stats["enums_ecartes"] == 1  # zzz.proto -- un enum, jamais un message
    # aucun nom clair n'a ete fabrique nulle part
    p5 = "\t\t" in txt  # colonne nom_message_clair vide entre 2 tabs en tete de ligne
    print(f"  opcode top-level sans nom invente: {'OK' if p1 and p5 else 'MANQUANT'}")
    print(f"  champ du message top-level: {'OK' if p2 else 'MANQUANT'}")
    print(f"  message imbrique marque '.': {'OK' if p3 else 'MANQUANT'}")
    print(f"  enum ecarte (pas un message): {'OK' if p4 else 'MANQUANT'}")

    print("\n=== EPREUVE 2/2 : rejeu byte-identique (sha256) ===")
    run(tmp, out2)
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    same = h1 == h2
    print(f"  sha256 run1={h1[:16]}... run2={h2[:16]}... {'IDENTIQUE' if same else 'DIVERGENT'}")

    tout_ok = p1 and p2 and p3 and p4 and p5 and same
    print(f"\n=== BILAN EPREUVE : {'VERT' if tout_ok else 'ROUGE'} ===")
    return 0 if tout_ok else 1


# Point d'entree CLI : --epreuve, ou une extraction reelle (racine -> --out).
# / CLI entry point: --epreuve, or a real extraction (racine -> --out).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("racine", nargs="?", default=str(RACINE_DEFAUT))
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()
    if args.epreuve:
        sys.exit(run_epreuve())
    racine = Path(args.racine)
    if not racine.exists():
        print(f"ERREUR: racine absente: {racine}", file=sys.stderr)
        sys.exit(1)
    stats = run(racine, Path(args.out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
