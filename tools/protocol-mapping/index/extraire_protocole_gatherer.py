#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_protocole_gatherer.py [racine] [--out PATH] [--epreuve]
Table nom_clair <-> typeUrl <-> champs depuis dofus3-gatherer (TypeScript,
Electron) — 79 fichiers .proto CLAIRS (noms, numéros, types déjà lisibles,
aucune obfuscation). 0-LLM, stdlib (via `_lib_proto3.py`).

POURQUOI :
TROUVAILLE MESURÉE AVANT d'écrire ce script (04/09) : `diff -rq` entre
`resources/proto/` (gatherer) et `proto/` (dofus-unity-protocol-builder,
LuaxY) sur les 79 fichiers → **0 différence, exit 0**. gatherer VENDORISE
littéralement la sortie de LuaxY (le `go_package` interne dit encore
`go-xp-dofus-unity-proto-builder`) — ce n'est PAS un second instrument
indépendant, c'est la MÊME donnée. Voir RAPPORT-EXTRACTION-TIERS.md §gatherer.

TROUVAILLE ARCHITECTURE (mesurée dans `dofus-unity-protocol-builder/src/
protocol/protocol.go:100` et `resolver.go`, lu en amont) : ce tiers construit
et résout le `type.ankama.com/…` avec le NOM CLAIR COMPLET en suffixe
(`Descriptor().FullName()`), **jamais un opcode 3 lettres**. Donc
`opcode_ou_typeurl` ici est TOUJOURS `type.ankama.com/<package>.<Nom>` —
comparable à otomai/Jondo par NOM, pas par forme d'opcode.

COMMENT LANCER : python3 extraire_protocole_gatherer.py [racine] [--out PATH.tsv] [--epreuve]
GATE : --epreuve (2 volets : forme du TSV sur un témoin fabriqué avec message imbriqué + oneof,
    et rejeu sha256 byte-identique). Réutilisée telle quelle par extraire_protocole_luaxy.py.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib_extract import write_tsv
from _lib_proto3 import iter_proto_files, process_proto_file

RACINE_DEFAUT = Path("refs/dofus3-gatherer/resources/proto")
ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "protocole-gatherer.tsv"

HEADER = ["nom_message_clair", "nom_complet", "opcode_ou_typeurl", "direction", "champs", "fichier:ligne"]
DIRECTION_SUFFIX = (("Request", "C2S"), ("Response", "S2C"), ("Event", "S2C"))


# DEDUIT depuis le suffixe conventionnel du nom (Request=C2S, Response/Event=S2C) -- pas mesure.
# / DEDUCED from the name's conventional suffix (Request=C2S, Response/Event=S2C) -- not measured.
def deduce_direction(name: str) -> str:
    for suf, d in DIRECTION_SUFFIX:
        if name.endswith(suf):
            return d
    return ""


def to_full_dotted(complet: str) -> str:
    """`+`-imbrique (notre convention interne) -> `.`-imbrique (convention
    protobuf FullName, celle réellement utilisée par `type.ankama.com/…`)."""
    return complet.replace("+", ".")


# Parcourt tous les .proto de racine, ecrit le TSV (typeUrl = type.ankama.com/<package>.<Nom>).
# / Walks all .proto files under racine, writes the TSV (typeUrl = type.ankama.com/<package>.<Name>).
def run(racine: Path, out: Path) -> dict:
    raw_rows: list = []
    counters = {"message": 0, "enum": 0, "champs": 0}
    discarded: list = []
    files = list(iter_proto_files(racine))
    for p in files:
        process_proto_file(p, raw_rows, counters, discarded)
    tsv_rows = []
    for r in raw_rows:
        opcode = "type.ankama.com/" + to_full_dotted(r["complet"])
        tsv_rows.append([r["nom"], r["complet"], opcode, deduce_direction(r["nom"]), r["champs"], r["fichier_ligne"]])
    write_tsv(out, HEADER, tsv_rows)
    return {
        "fichiers": len(files),
        "messages": len(raw_rows),
        "enums_ecartes": counters["enum"],
        "champs_total": counters["champs"],
        "erreurs_lecture": len(discarded),
        "out": str(out),
    }


# Epreuve dans les deux sens : forme du TSV sur un .proto fabrique (message top-level + direction
# deduite, message imbrique, champs DANS un oneof) + rejeu sha256 byte-identique.
# / Two-way proof: TSV form on a fabricated .proto (top-level message + deduced direction, nested
# message, fields INSIDE a oneof) + byte-identical sha256 replay.
def run_epreuve() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-gatherer-"))
    (tmp / "witness.proto").write_text(
        'syntax = "proto3";\npackage com.witness;\n\n'
        "message WitnessOkRequest {\n\tint32 foo_bar = 1;\n"
        "\tmessage Nested {\n\t\tint32 inner = 1;\n\t}\n}\n\n"
        "message WitnessWithOneofEvent {\n\toneof content {\n\t\tint32 a = 1;\n\t\tstring b = 2;\n\t}\n}\n",
        encoding="utf-8",
    )
    out1, out2 = tmp / "out1.tsv", tmp / "out2.tsv"
    print("=== EPREUVE 1/2 : sabotage (message + imbriqué + champs de oneof sortent) ===")
    run(tmp, out1)
    txt = out1.read_text(encoding="utf-8")
    p1 = "WitnessOkRequest" in txt and "C2S" in txt
    p2 = "Nested" in txt and "1:int32:inner" in txt
    p3 = "WitnessWithOneofEvent" in txt and "1:int32:a" in txt and "2:string:b" in txt
    print(f"  message top-level + direction deduite: {'OK' if p1 else 'MANQUANT'}")
    print(f"  message imbrique + son champ: {'OK' if p2 else 'MANQUANT'}")
    print(f"  champs DANS un oneof rattaches au message parent: {'OK' if p3 else 'MANQUANT'}")

    print("\n=== EPREUVE 2/2 : rejeu byte-identique (sha256) ===")
    run(tmp, out2)
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    same = h1 == h2
    print(f"  sha256 run1={h1[:16]}... run2={h2[:16]}... {'IDENTIQUE' if same else 'DIVERGENT'}")

    tout_ok = p1 and p2 and p3 and same
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
