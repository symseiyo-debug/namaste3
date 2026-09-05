#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI / WHAT
    Importe les tables de correspondance de JondoEmu, les trie par FIABILITÉ RÉELLE, et les
    confronte à nos 208 correspondances `DÉDUIT` de `correspondance-v4.tsv`.
    Imports JondoEmu's mapping tables, sorts them by ACTUAL reliability, and confronts them with
    our own 208 deduced correspondences.

POURQUOI / WHY  (écrit le 2026-09-05 / written 2026-09-05)
    Deux pièges, et les deux se referment si on lit vite :

    1. LA BONNE TABLE N'EST PAS CELLE QU'ON CROIT. `mapeo_3.6.10.10_a_DofusClient.tsv` n'est PAS
       « jeton → nom clair » : ses deux premières colonnes sont deux jetons obfusqués. La table qui
       nous concerne est `mapeo_3.6.10.10_a_3.6.10.11.tsv` — la nôtre, 3.6.10.11 — et on y a mesuré
       que les 2 169 lignes sont l'IDENTITÉ : `hdw→hdw`, `hdx→hdx`, zéro rotation entre ces deux
       correctifs. Donc TOUT le travail 3.6.10.10 de Jondo s'applique verbatim à notre client.
       The right table is the 3.6.10.11 one, and its 2,169 rows are the IDENTITY: no rotation
       between those two patches, so all of Jondo's 3.6.10.10 work applies to our client verbatim.

    2. « NOM » ET « SIGNIFICATION » N'ONT PAS LA MÊME FIABILITÉ, et c'est Jondo qui le dit dans
       l'en-tête de `anclas` : « El NOMBRE es una propuesta, no un dato » — le nom est écrit « au
       style de Dofus » d'après ce que le message fait. La SIGNIFICATION, elle, est mesurée en
       croisant le code de l'émulateur avec 242 captures du jeu réel. Importer les deux sous la
       même étiquette « Jondo » ferait passer une proposition pour une mesure.
       Jondo states it himself: the NAME is a proposal, the MEANING is measured against 242 live
       captures. Importing both under one label would launder a guess into a measurement.

COMMENT / HOW
    `origen` de Jondo → notre fiabilité :
      estructura = l'apparieur structurel a tranché, il ne se trompe pas  → FIABLE (le JETON)
      modelo     = plusieurs candidats de même forme, un LLM a choisi     → DÉDUIT
      duda       = des candidats, personne n'a tranché                    → JAMAIS
      retirado   = aucun candidat : nouveau, ou disparu                   → ABSENT
    et, transversalement : `significado` = MESURÉ (242 captures) · `nombre` = PROPOSÉ.

GATE
    `--epreuve` : témoin d'identité (les 2 169 lignes 3.6.10.10→3.6.10.11 sont bien l'identité),
    témoin négatif (aucune ligne `duda`/`retirado` ne franchit le tri), rejeu byte-identique.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
DATOS = Path("refs/JondoEmu/datos")
V4 = ICI.parent / "matcher/correspondance-v4.tsv"

# Nos versions : ce qui compte est la table qui aboutit à 3.6.10.11, notre client.
TABLE_NOTRE_VERSION = DATOS / "mapeo_3.6.10.10_a_3.6.10.11.tsv"
TABLE_DOFUSCLIENT = DATOS / "mapeo_3.6.10.10_a_DofusClient.tsv"
TABLE_GAME = DATOS / "mapeo_Ankama.Dofus.Protocol.Game_a_3.6.10.10.tsv"
ANCLAS = DATOS / "anclas_3.6.10.10.tsv"

FIABILITE = {"estructura": "FIABLE", "modelo": "DÉDUIT", "duda": "JAMAIS", "retirado": "ABSENT"}


def lire_mapeo(chemin: Path) -> list[dict]:
    """
    Colonnes déclarées par Jondo : viejo, nuevo, origen, nombre, qué hace, lo usa el emulador.
    Columns as declared by Jondo in the file header.
    """
    out = []
    if not chemin.exists():
        return out
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        if not ligne.strip() or ligne.startswith("#"):
            continue
        c = (ligne.split("\t") + [""] * 6)[:6]
        out.append({"vieux": c[0].strip(), "nouveau": c[1].strip(), "origen": c[2].strip(),
                    "nom": c[3].strip(), "que_fait": c[4].strip(), "emulateur": c[5].strip()})
    return out


def lire_anclas() -> list[dict]:
    """Colonnes : opcode, direction, nom proposé, signification, handler, forme."""
    out = []
    if not ANCLAS.exists():
        return out
    for ligne in ANCLAS.read_text(encoding="utf-8").splitlines():
        if not ligne.strip() or ligne.startswith("#"):
            continue
        c = (ligne.split("\t") + [""] * 6)[:6]
        out.append({"opcode": c[0].strip(), "direction": c[1].strip(), "nom": c[2].strip(),
                    "signification": c[3].strip(), "handler": c[4].strip(), "forme": c[5].strip()})
    return out


def lire_v4() -> dict[str, tuple[str, str]]:
    """
    Nos correspondances retenues : jeton → (nom clair, provenance).
    La PROVENANCE est indispensable : 72 de nos 208 sont recopiées de `anclas` de Jondo
    (`proposition_jondo_seule`). Les compter comme un accord AVEC Jondo, c'est se faire
    confirmer par sa propre copie. Mesuré le 2026-09-05.
    The PROVENANCE matters: 72 of our 208 are copied from Jondo's own anchors, so counting them
    as agreement WITH Jondo is being confirmed by one's own copy.
    """
    out = {}
    if not V4.exists():
        return out
    for i, ligne in enumerate(V4.read_text(encoding="utf-8").splitlines()):
        if i == 0 or not ligne.strip():
            continue
        c = ligne.split("\t")
        if len(c) > 7 and c[0].strip() and c[2].strip() and c[6].strip() == "DÉDUIT":
            out[c[0].strip()] = (c[2].strip(), c[7].strip())
    return out


def circulaire(provenance: str) -> bool:
    """La provenance vient-elle de Jondo ? / Does this provenance come from Jondo itself?"""
    return "jondo" in provenance.lower()


def construire(sortie: Path) -> dict:
    """Assemble la table des noms Jondo utilisables sur NOTRE client, et la confronte à la nôtre."""
    notre = lire_mapeo(TABLE_NOTRE_VERSION)
    identiques = sum(1 for r in notre if r["vieux"] and r["vieux"] == r["nouveau"])
    anclas = lire_anclas()
    par_opcode = {a["opcode"]: a for a in anclas}

    lignes = ["jeton_3.6.10.11\tnom_propose\tfiabilite_du_nom\tsignification_mesuree\t"
              "fiabilite_du_jeton\tdirection\thandler\tforme_capturee\torigen_jondo\tsource"]
    retenus: dict[str, str] = {}
    compte = defaultdict(int)

    for r in notre:
        fiab_jeton = FIABILITE.get(r["origen"], "?")
        compte[f"jeton:{fiab_jeton}"] += 1
        if fiab_jeton not in ("FIABLE", "DÉDUIT"):
            continue                       # `duda` et `retirado` ne franchissent jamais le tri
        jeton = r["nouveau"] or r["vieux"]
        a = par_opcode.get(r["vieux"], {})
        nom = r["nom"] or a.get("nom", "")
        sens = r["que_fait"] or a.get("signification", "")
        if not nom and not sens:
            continue
        # Jondo le dit lui-même : le NOM est une proposition, la SIGNIFICATION est mesurée.
        fiab_nom = "PROPOSÉ" if nom else ""
        if nom:
            compte["noms_proposes"] += 1
            retenus[jeton] = nom
        if sens:
            compte["significations_mesurees"] += 1
        lignes.append("\t".join([
            jeton, nom, fiab_nom, sens.replace("\t", " "), fiab_jeton,
            a.get("direction", ""), a.get("handler", ""), a.get("forme", ""),
            r["origen"], TABLE_NOTRE_VERSION.name]))

    (sortie / "noms-jondo-fiables.tsv").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    # ── Confrontation avec nos 208 / Confrontation with our own 208 ───────────────────────────
    nous = lire_v4()
    accord, circ, desaccord, neuf_jondo, neuf_nous = [], [], [], [], []
    conf = ["jeton\tverdict\tnom_jondo\tnom_nous\tprovenance_v4"]
    for jeton, nom_j in sorted(retenus.items()):
        if jeton not in nous:
            neuf_jondo.append((jeton, nom_j))
            conf.append(f"{jeton}\tNOUVEAU_JONDO\t{nom_j}\t\t")
            continue
        nom_n, prov = nous[jeton]
        meme = nom_n.split(".")[-1].lower() == nom_j.split(".")[-1].lower()
        if circulaire(prov):
            # Recopié de Jondo : ne compte NI comme accord NI comme désaccord.
            circ.append((jeton, nom_j, nom_n, prov))
            conf.append(f"{jeton}\tCIRCULAIRE\t{nom_j}\t{nom_n}\t{prov}")
        elif meme:
            accord.append((jeton, nom_j, nom_n, prov))
            conf.append(f"{jeton}\tACCORD_INDÉPENDANT\t{nom_j}\t{nom_n}\t{prov}")
        else:
            desaccord.append((jeton, nom_j, nom_n, prov))
            conf.append(f"{jeton}\tDÉSACCORD\t{nom_j}\t{nom_n}\t{prov}")
    for jeton, (nom_n, prov) in sorted(nous.items()):
        if jeton not in retenus:
            neuf_nous.append((jeton, nom_n, prov))
            conf.append(f"{jeton}\tNOUVEAU_NOUS\t\t{nom_n}\t{prov}")
    (sortie / "confrontation-jondo-v4.tsv").write_text("\n".join(conf) + "\n", encoding="utf-8")

    return {
        "table_de_notre_version": TABLE_NOTRE_VERSION.name,
        "lignes": len(notre),
        "jetons_identiques_3_6_10_10_vers_3_6_10_11": identiques,
        "rotation_entre_ces_deux_correctifs": len(notre) - identiques,
        "repartition_fiabilite": dict(compte),
        "noms_utilisables_sur_notre_client": len(retenus),
        "anclas_opcodes": len(anclas),
        "anclas_avec_nom_propose": sum(1 for a in anclas if a["nom"]),
        "anclas_avec_signification_mesuree": sum(1 for a in anclas if a["signification"]),
        "nos_correspondances_v4": len(nous),
        "nos_correspondances_v4_recopiees_de_jondo": sum(1 for _n, p in nous.values()
                                                         if circulaire(p)),
        "accord_independant": len(accord),
        "accord_circulaire_exclu": len(circ),
        "desaccord": len(desaccord),
        "nouveau_apporte_par_jondo": len(neuf_jondo), "seulement_chez_nous": len(neuf_nous),
        "accords_independants": [{"jeton": j, "nom": a, "provenance_v4": p}
                                 for j, a, _b, p in accord],
        "desaccords": [{"jeton": j, "jondo": a, "nous": b, "provenance_v4": p}
                       for j, a, b, p in desaccord],
        "autres_tables": {
            TABLE_DOFUSCLIENT.name: {
                "lignes": len(lire_mapeo(TABLE_DOFUSCLIENT)),
                "note": "deux colonnes de JETONS, pas un mapping vers des noms clairs"},
            TABLE_GAME.name: {
                "lignes": len(lire_mapeo(TABLE_GAME)),
                "note": "deux colonnes de JETONS, aucune colonne nom renseignée"}},
    }


def epreuve(sortie: Path) -> int:
    """GATE : identité mesurée, tri des non fiables, rejeu. / Gate: identity, filter, replay."""
    verts = []
    b = construire(sortie)

    ok1 = (b["jetons_identiques_3_6_10_10_vers_3_6_10_11"] == b["lignes"] == 2169)
    verts.append(ok1)
    print(f"[1] TÉMOIN D'IDENTITÉ 3.6.10.10 → 3.6.10.11 : {'VERT' if ok1 else 'ROUGE'} — "
          f"{b['jetons_identiques_3_6_10_10_vers_3_6_10_11']}/{b['lignes']} identiques, "
          f"{b['rotation_entre_ces_deux_correctifs']} rotations")

    # Témoin négatif : rien de `duda`/`retirado` ne doit avoir franchi le tri.
    lus = (sortie / "noms-jondo-fiables.tsv").read_text(encoding="utf-8").splitlines()[1:]
    interdits = [l for l in lus if l.split("\t")[8] in ("duda", "retirado")]
    ok2 = not interdits
    verts.append(ok2)
    print(f"[2] TÉMOIN NÉGATIF (aucun `duda`/`retirado` retenu) : "
          f"{'VERT' if ok2 else 'ROUGE'} — {len(interdits)} intrus sur {len(lus)} lignes")

    t1 = (sortie / "noms-jondo-fiables.tsv").read_bytes()
    c1 = (sortie / "confrontation-jondo-v4.tsv").read_bytes()
    construire(sortie)
    ok3 = (t1 == (sortie / "noms-jondo-fiables.tsv").read_bytes()
           and c1 == (sortie / "confrontation-jondo-v4.tsv").read_bytes())
    verts.append(ok3)
    print(f"[3] REJEU byte-identique : {'VERT' if ok3 else 'ROUGE'} — {len(t1)} + {len(c1)} octets")
    print(f"\nGATE : {sum(verts)}/3 verts\n{json.dumps(b, ensure_ascii=False, indent=2)}")
    return 0 if all(verts) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epreuve", action="store_true")
    ap.add_argument("--sortie", default=str(ICI))
    args = ap.parse_args()
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    if args.epreuve:
        return epreuve(sortie)
    b = construire(sortie)
    (sortie / "mesure-mapeos.json").write_text(
        json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(b, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
