#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_protocole_luaxy.py [racine] [--out PATH] [--epreuve]
Table nom_clair <-> typeUrl <-> champs depuis dofus-unity-protocol-builder
(Go, LuaxY, 2024-10, dépôt marqué « outdated » par son auteur) — 79 fichiers
.proto CLAIRS. 0-LLM, stdlib (via `_lib_proto3.py`).

POURQUOI :
RAPPEL DE LA TROUVAILLE (mesurée dans `extraire_protocole_gatherer.py`,
répétée ici pour qui lance CE script isolément) : les 79 `.proto` de ce
dépôt et ceux de `refs/dofus3-gatherer/resources/proto/` sont
**BYTE-IDENTIQUES** (`diff -rq` → 0 différence). `protocole-gatherer.tsv`
et `protocole-luaxy.tsv` portent donc LA MÊME donnée sous deux noms — ne
JAMAIS les compter comme deux instruments indépendants dans un croisement
à 3+ sources (cf. RAPPORT-EXTRACTION-TIERS.md §gatherer/luaxy).

Ce script existe pour honorer la demande explicite (fichier nommé), et pour
que la provenance `fichier:ligne` de chaque champ pointe, au choix, vers LE
dépôt qu'on préfère citer (LuaxY = l'origine ; gatherer = le vendeur).

COMMENT LANCER : python3 extraire_protocole_luaxy.py [racine] [--out PATH.tsv] [--epreuve]
GATE : réutilise l'épreuve d'extraire_protocole_gatherer.py (même code, même données) via --epreuve.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from extraire_protocole_gatherer import run, run_epreuve as _run_epreuve_shared  # reutilise l'existant, ne reinvente pas

RACINE_DEFAUT = Path("refs/dofus-unity-protocol-builder/proto")
ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "protocole-luaxy.tsv"


# Point d'entree CLI : delegue tout (extraction + --epreuve) a extraire_protocole_gatherer.py,
# seul le chemin racine/sortie par defaut change (dofus-unity-protocol-builder, pas gatherer).
# / CLI entry point: delegates everything (extraction + --epreuve) to
# extraire_protocole_gatherer.py, only the default root/output path differs.
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("racine", nargs="?", default=str(RACINE_DEFAUT))
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()
    if args.epreuve:
        sys.exit(_run_epreuve_shared())
    racine = Path(args.racine)
    if not racine.exists():
        print(f"ERREUR: racine absente: {racine}", file=sys.stderr)
        sys.exit(1)
    stats = run(racine, Path(args.out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
