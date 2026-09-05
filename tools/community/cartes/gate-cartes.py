#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Gate déterministe (0 jeton) de l'extraction de géométrie des cartes 3.0.
    Refuse une extraction fausse en la confrontant à des SECONDS INSTRUMENTS
    produits hors de notre chaîne (`refs/JondoEmu/datos/`, `world.db`), et à
    des invariants tirés du dump du client (`il2cpp.cs`).
    WHAT: deterministic gate for the 3.0 map-geometry extraction; refuses a false
    extraction by confronting it with second instruments built outside our chain.

POURQUOI (04/09/2026) : le client attend 17 champs par cellule et nous n'en
    avions que 2 (`mov` dérivé, `fight` dérivé) — cf. `server/
    DONNEES-3.0-CARTE.md:148`, « 13 des 17 champs sont un trou ». Une extraction
    de 9,7 millions de cellules ne se relit pas à l'œil : sans gate, une erreur
    de décodage passerait pour de la donnée. Et un compte juste ne prouve rien —
    seule une ÉGALITÉ D'ENSEMBLE contre une source indépendante prouve.
    WHY: 9.7M cells cannot be eyeballed; only set equality against an independent
    source proves the decode.

COMMENT LANCER / HOW TO RUN :
    V=internal/artefacts/\\
      lot30-data-3.0-extract/.venv/bin/python
    $V gate-cartes.py --epreuve   # les 5 épreuves (quelques minutes)
    $V gate-cartes.py --corpus    # les 3 confrontations sur les 17 353 cartes

GATE : VERTE si les 5 épreuves passent.
    E1 carte témoin 191105026 — 560 cellules, ids 0..559, et TROIS confrontations
       à des sources indépendantes (fight `f`, fight `b`, voisins MapScrolls).
    E2 partition — marchables + non-marchables = cellCount, sur chaque carte.
    E3 sabotage — un flag `mov` inversé dans une COPIE doit faire ROUGIR E1.
       Sans E3, cinq verts ne prouveraient pas que la gate regarde quelque chose.
    E4 témoin négatif — un mapId inventé rend « absent », jamais une exception.
    E5 rejeu — re-extraction du même bundle, sha256 des JSON identiques.
    Tout refus est NOMMÉ (quelle épreuve, quel écart, quels chiffres). Aucun
    avertissement silencieux, aucune exception avalée en vert.
"""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
SORTIE = ICI / "sortie"
EXTRACTEUR = ICI / "extraire_cartes.py"
# FR: le venv de lot30 porte UnityPy 1.25.3 (outil déjà prouvé, non réécrit).
VENV = Path("internal/artefacts/"
            "lot30-data-3.0-extract/.venv/bin/python")
JONDO = Path("refs/JondoEmu/datos")

# --- Constantes, chacune avec sa SOURCE / each constant with its SOURCE ---------
# 560 cellules par carte : constante du client, `private const int CellsCount = 560`
#   -- il2cpp.cs:245096 (et une 2e déclaration indépendante à il2cpp.cs:332686).
CELL_ATTENDU = 560
# 14 colonnes : `private const int Column = 14` -- il2cpp.cs:245098.
#   560 / 14 = 40 rangées : la grille « 14x40 » est DÉDUITE de ces deux constantes,
#   elle n'est écrite nulle part telle quelle dans le dump.
COLONNES = 14
RANGEES = CELL_ATTENDU // COLONNES  # 40

# Carte témoin : Astrub, la carte d'entrée du chemin critique J3.3.
TEMOIN = 191105026
# Bundle qui la porte : MESURÉ par l'index des 577 bundles (extraire_cartes.py --localiser).
TEMOIN_BUNDLE = "mapdata_assets_world_729.bundle"
# MESURÉ dans le bundle, pas déduit : 360 cellules `mov=true` sur la carte témoin.
#   ⚠️ Le brief annonçait « exactement 230 marchables ». C'est FAUX comme critère de
#   marchabilité : les 230 viennent de map_walkable_cells.json, qui rogne les bords
#   EXPRÈS pour que les monstres n'apparaissent pas au bord -- JondoEmu/docs/world.md:48
#   et JondoEmu/docs/data.md:34. Jondo lui-même refuse ce fichier pour la marchabilité
#   (MapManager.cs:51, WorldMoveHandler.cs:442). On garde 230 comme BORNE INFÉRIEURE.
TEMOIN_MOV = 360
TEMOIN_JONDO_WALK = 230
# MESURÉ : |mov ET NON nonWalkableDuringFight| == |map_fight_cells['f']| == 357.
#   Légende de `f` et `b` : JondoEmu/docs/data.md:33.
TEMOIN_FIGHT = 357
# MESURÉ : |NON los| == |map_fight_cells['b']| == 85.
TEMOIN_LOS_BLOQUEES = 85
# MESURÉ dans world.db (MapScrolls) ET dans le bundle : droite/bas/gauche/haut.
TEMOIN_VOISINS = {"rightNeighbourId": 191106050, "bottomNeighbourId": 191105028,
                  "leftNeighbourId": 191104002, "topNeighbourId": 191105024}

# Les 17 champs de ClientCellData, ordre du dump -- il2cpp.cs:123424-123440.
CHAMPS = ("cellNumber", "speed", "mapChangeData", "moveZone", "linkedZone", "mov", "los",
          "nonWalkableDuringFight", "nonWalkableDuringRP", "farmCell", "visible",
          "havenbagCell", "roleplayMonstersMovementBlocked", "floor", "red", "blue", "arrow")


class Refus(Exception):
    """FR: un refus de gate, avec son motif nommé. EN: a named gate refusal."""


def charge(dossier, map_id):
    """FR: lit un JSON de carte, ou None s'il n'existe pas (jamais d'exception).
       EN: reads one map JSON, or None if absent -- never raises on absence."""
    p = Path(dossier) / "cartes" / f"{map_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def sha(p):
    """FR: sha256 d'un fichier, pour prouver un rejeu byte-identique.
       EN: file sha256, to prove a byte-identical replay."""
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _mapscrolls():
    """FR: ouvre world.db (dans world.zip) et rend {mapId: (droite,bas,gauche,haut)}.
       C'est le TROISIÈME instrument : la table MapScrolls de Jondo, 17 353 lignes.
       EN: opens Jondo's world.db and returns the MapScrolls neighbour table."""
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(JONDO / "world.zip") as z:
            z.extract("world.db", td)
        c = sqlite3.connect(str(Path(td) / "world.db"))
        return {r[0]: (r[1], r[2], r[3], r[4]) for r in
                c.execute("SELECT MapId,RightMapId,BottomMapId,LeftMapId,TopMapId "
                          "FROM MapScrolls")}


# ------------------------------------------------------------------ E1
def e1_temoin(dossier, sans_voisins=False):
    """FR: la carte témoin, confrontée à TROIS sources indépendantes.
       Refuse en nommant l'écart chiffré. `sans_voisins` sert au sabotage (E3),
       qui travaille sur une copie sans rouvrir world.db.
       EN: the witness map against THREE independent sources; named refusals."""
    rec = charge(dossier, TEMOIN)
    if rec is None:
        raise Refus(f"E1 carte-temoin {TEMOIN} ABSENTE de {dossier}/cartes/")
    cd = rec["cellsData"]

    # (a) invariant du dump : 560 cellules, ids 0..559 sans trou ni doublon.
    if len(cd) != CELL_ATTENDU:
        raise Refus(f"E1 {TEMOIN} : {len(cd)} cellules, attendu {CELL_ATTENDU} "
                    f"(il2cpp.cs:245096)")
    ids = {c["cellNumber"] for c in cd}
    if ids != set(range(CELL_ATTENDU)):
        raise Refus(f"E1 {TEMOIN} : ids de cellules != 0..{CELL_ATTENDU-1} "
                    f"({len(ids)} uniques, manquants {sorted(set(range(CELL_ATTENDU))-ids)[:5]})")
    manquants = [f for f in CHAMPS if any(f not in c for c in cd)]
    if manquants:
        raise Refus(f"E1 champs manquants dans cellsData : {manquants}")

    # (b) le compte `mov` MESURÉ, et la borne inférieure demandée par le brief.
    mov = {c["cellNumber"] for c in cd if c["mov"]}
    if not (TEMOIN_JONDO_WALK <= len(mov) <= CELL_ATTENDU):
        raise Refus(f"E1 {TEMOIN} : {len(mov)} mov hors bornes "
                    f"[{TEMOIN_JONDO_WALK}, {CELL_ATTENDU}]")
    if len(mov) != TEMOIN_MOV:
        raise Refus(f"E1 {TEMOIN} : {len(mov)} cellules mov, attendu {TEMOIN_MOV} (mesure)")

    # (c) 1er second instrument : map_fight_cells.json, légende docs/data.md:33.
    fj = json.loads((JONDO / "map_fight_cells.json").read_text())[str(TEMOIN)]
    mien_f = {c["cellNumber"] for c in cd if c["mov"] and not c["nonWalkableDuringFight"]}
    if set(fj["f"]) != mien_f:
        raise Refus(f"E1 fight `f` (mov ET NON nonWalkableDuringFight) : "
                    f"{len(set(fj['f']))} contre {len(mien_f)}, "
                    f"{len(set(fj['f']) ^ mien_f)} cellules d'ecart")
    if len(mien_f) != TEMOIN_FIGHT:
        raise Refus(f"E1 fight : {len(mien_f)} != {TEMOIN_FIGHT}")
    mien_b = {c["cellNumber"] for c in cd if not c["los"]}
    if set(fj["b"]) != mien_b:
        raise Refus(f"E1 fight `b` (NON los) : {len(set(fj['b']))} contre {len(mien_b)}")
    if len(mien_b) != TEMOIN_LOS_BLOQUEES:
        raise Refus(f"E1 los bloquees : {len(mien_b)} != {TEMOIN_LOS_BLOQUEES}")

    # (d) 2e second instrument : map_walkable_cells.json, en CONTAINMENT seulement.
    #     Ses 230 doivent tous etre `mov` chez nous ; l'inverse est FAUX par construction
    #     (bords rognes expres), donc on ne teste jamais l'egalite.
    wj = set(json.loads((JONDO / "map_walkable_cells.json").read_text())[str(TEMOIN)])
    if len(wj) != TEMOIN_JONDO_WALK:
        raise Refus(f"E1 Jondo walkable : {len(wj)} != {TEMOIN_JONDO_WALK}")
    if not wj <= mov:
        raise Refus(f"E1 containment ROMPUE : {len(wj - mov)} cellules Jondo non `mov`")

    # (e) 3e second instrument : les 4 voisins contre world.db/MapScrolls.
    for k in TEMOIN_VOISINS:
        if not isinstance(rec.get(k), int):
            raise Refus(f"E1 voisin {k} absent ou non entier : {rec.get(k)!r}")
    if not sans_voisins:
        ms = _mapscrolls().get(TEMOIN)
        attendu = tuple(TEMOIN_VOISINS[k] for k in
                        ("rightNeighbourId", "bottomNeighbourId",
                         "leftNeighbourId", "topNeighbourId"))
        if ms != attendu:
            raise Refus(f"E1 MapScrolls a bouge : {ms} != {attendu}")
        nous = (rec["rightNeighbourId"], rec["bottomNeighbourId"],
                rec["leftNeighbourId"], rec["topNeighbourId"])
        if nous != ms:
            raise Refus(f"E1 voisins != MapScrolls : nous {nous}, jondo {ms}")
    return (f"E1 OK : {TEMOIN} = {CELL_ATTENDU} cellules ids 0..{CELL_ATTENDU-1}, "
            f"{len(mov)} mov (>= {TEMOIN_JONDO_WALK}), fight `f` {len(mien_f)} EXACT, "
            f"`b` {len(mien_b)} EXACT, {len(wj)} walkable ⊆ mov, "
            f"4 voisins == MapScrolls")


# ------------------------------------------------------------------ E2
def e2_partition(dossier, limite=0):
    """FR: sur CHAQUE carte, marchables + non-marchables == cellCount, ids 0..559
       uniques. Un decodage qui perdrait des cellules se verrait ici.
       EN: per map, walkable + non-walkable == cellCount, ids unique and complete."""
    fichiers = sorted((Path(dossier) / "cartes").glob("*.json"))
    if not fichiers:
        raise Refus("E2 aucune carte a verifier")
    if limite:
        fichiers = fichiers[:limite]
    for p in fichiers:
        rec = json.loads(p.read_text(encoding="utf-8"))
        cd = rec["cellsData"]
        m = sum(1 for c in cd if c["mov"])
        nm = sum(1 for c in cd if not c["mov"])
        if m + nm != rec["cellCount"] or rec["cellCount"] != len(cd):
            raise Refus(f"E2 partition rompue sur {p.name} : {m}+{nm} != {rec['cellCount']}")
        if {c["cellNumber"] for c in cd} != set(range(len(cd))):
            raise Refus(f"E2 ids de cellules != 0..{len(cd)-1} sur {p.name}")
    return (f"E2 OK : partition mov/non-mov == cellCount et ids 0..{CELL_ATTENDU-1} "
            f"sur {len(fichiers)} carte(s)")


# ------------------------------------------------------------------ E3
def e3_sabotage(dossier):
    """FR: inverse UN flag `mov` dans une COPIE (jamais l'original) et exige que E1
       rougisse. C'est l'epreuve qui prouve que la gate mesure le terrain.
       EN: flips one `mov` in a COPY and requires E1 to go red -- proves the gate bites."""
    src = Path(dossier) / "cartes" / f"{TEMOIN}.json"
    if not src.exists():
        raise Refus(f"E3 impossible : {src} absent")
    with tempfile.TemporaryDirectory() as td:
        faux = Path(td) / "cartes"
        faux.mkdir(parents=True)
        rec = json.loads(src.read_text(encoding="utf-8"))
        for c in rec["cellsData"]:
            if c["mov"]:
                c["mov"] = False
                break
        else:
            raise Refus("E3 aucune cellule mov a saboter")
        (faux / f"{TEMOIN}.json").write_text(json.dumps(rec), encoding="utf-8")
        try:
            e1_temoin(td, sans_voisins=True)
        except Refus as r:
            return f"E3 OK : sabotage detecte -> {r}"
        return None  # None = la gate n'a rien vu ; l'appelant le traite en ROUGE


# ------------------------------------------------------------------ E4
def e4_temoin_negatif(dossier):
    """FR: un mapId inventé doit rendre « absent », pas une exception ni une carte.
       Sans ce témoin, on ne distingue pas « rien trouvé » de « tout trouvé ».
       EN: a made-up mapId must read as absent -- no exception, no fabricated map."""
    # 999999999 : mapId INVENTÉ, choisi hors de toute plage réelle (les vrais vont de
    # 0 à ~250 000 000, MESURÉ sur les 17 353 cartes). Aucune source : c'est le principe.
    invente = 999999999
    if charge(dossier, invente) is not None:
        raise Refus(f"E4 mapId invente {invente} TROUVE -- la sortie fabrique des cartes")
    return f"E4 OK : mapId invente {invente} -> absent, sans exception"


# ------------------------------------------------------------------ E5
def e5_rejeu(dossier):
    """FR: re-extrait le bundle du temoin dans un dossier neuf et compare les sha256.
       Un JSON qui porterait un horodatage ou un chemin absolu casserait ici.
       EN: re-extracts the witness bundle and compares sha256 -- catches nondeterminism."""
    ref = Path(dossier) / "cartes" / f"{TEMOIN}.json"
    if not ref.exists():
        raise Refus(f"E5 impossible : {ref} absent")
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([str(VENV), str(EXTRACTEUR), "--bundle", TEMOIN_BUNDLE,
                            "--out", td], capture_output=True, text=True)
        if r.returncode != 0:
            # 400 : longueur ARBITRAIRE de queue de stderr, assez pour porter la
            # trace Python utile sans inonder le refus. Aucune source.
            raise Refus(f"E5 re-extraction rc={r.returncode} : {r.stderr[-400:]}")
        neuf = Path(td) / "cartes" / f"{TEMOIN}.json"
        if not neuf.exists():
            raise Refus("E5 la re-extraction n'a pas produit la carte temoin")
        a, b = sha(ref), sha(neuf)
        if a != b:
            raise Refus(f"E5 rejeu NON byte-identique : {a[:16]} != {b[:16]}")
        n = len(list((Path(td) / "cartes").glob("*.json")))
    return f"E5 OK : rejeu byte-identique (sha256 {a[:16]}…, {n} cartes re-extraites)"


# ------------------------------------------------------------------ corpus
def _reciprocite(src):
    """FR: test INTERNE, sans source externe : si A.droite==B alors B.gauche==A ?
       Aucune des deux sources ne peut le truquer -- c'est ce qui le rend utile.
       EN: internal test no source can game: A.right==B implies B.left==A?"""
    ok = ko = 0
    for mid, v in src.items():
        for i, j in ((0, 2), (1, 3), (2, 0), (3, 1)):  # droite<->gauche, bas<->haut
            n = v[i]
            if n in src and n != mid:
                ok, ko = (ok + 1, ko) if src[n][j] == mid else (ok, ko + 1)
    return ok, ko


def corpus(dossier):
    """FR: rejoue les confrontations sur TOUTES les cartes extraites et rend des
       chiffres, pas un verdict binaire seul : fight `f`, fight `b`, voisins
       MapScrolls, et la réciprocité interne des deux tables de voisins.
       EN: replays every confrontation across the whole corpus and reports counts."""
    fj = json.loads((JONDO / "map_fight_cells.json").read_text())
    wj = json.loads((JONDO / "map_walkable_cells.json").read_text())
    ms = _mapscrolls()
    okf = badf = okb = badb = hors = 0
    sousens = egal = pasinclus = 0
    vok = vbad = vhors = 0
    nous_inconnu = jondo_inconnu = 0
    ecarts = []
    nos_voisins = {}
    fichiers = sorted((Path(dossier) / "cartes").glob("*.json"))
    for p in fichiers:
        rec = json.loads(p.read_text(encoding="utf-8"))
        cd = rec["cellsData"]
        mid = rec["mapId"]
        mov = {c["cellNumber"] for c in cd if c["mov"]}
        if str(mid) in fj:
            f = {c["cellNumber"] for c in cd if c["mov"] and not c["nonWalkableDuringFight"]}
            b = {c["cellNumber"] for c in cd if not c["los"]}
            if set(fj[str(mid)]["f"]) == f: okf += 1
            else:
                badf += 1
                if len(ecarts) < 6: ecarts.append(("f", mid, len(set(fj[str(mid)]["f"])), len(f)))
            if set(fj[str(mid)]["b"]) == b: okb += 1
            else: badb += 1
        else:
            hors += 1
        if str(mid) in wj:
            w = set(wj[str(mid)])
            if w == mov: egal += 1
            elif w < mov: sousens += 1
            else: pasinclus += 1
        nous = (rec["rightNeighbourId"], rec["bottomNeighbourId"],
                rec["leftNeighbourId"], rec["topNeighbourId"])
        nos_voisins[mid] = nous
        if mid not in ms:
            vhors += 1
        elif nous == ms[mid]:
            vok += 1
        else:
            vbad += 1
    tous = set(nos_voisins)
    for mid, nous in nos_voisins.items():
        if mid in ms and nous != ms[mid]:
            for i in range(4):
                if nous[i] != ms[mid][i]:
                    nous_inconnu += nous[i] not in tous
                    jondo_inconnu += ms[mid][i] not in tous
    n = len(fichiers)
    print(f"cartes lues                       : {n}")
    print(f"fight `f` == mov ET NON nwFight   : EXACT {okf} | ECART {badf} "
          f"| hors fichier Jondo {hors}")
    print(f"fight `b` == NON los              : EXACT {okb} | ECART {badb}")
    print(f"walkable Jondo vs mov (containment): egal {egal} | sous-ensemble strict "
          f"{sousens} | NON inclus {pasinclus}")
    print(f"voisins == MapScrolls (world.db)  : IDENTIQUES {vok} | ECART {vbad} "
          f"| hors MapScrolls {vhors}")
    print(f"  dans les ecarts : NOTRE id absent des {n} cartes {nous_inconnu} fois, "
          f"celui de Jondo {jondo_inconnu} fois")
    a, b = _reciprocite(nos_voisins)
    c, d = _reciprocite(ms)
    print(f"  reciprocite interne (A.cote==B => B.oppose==A) : nous {100*a/(a+b):.2f}% "
          f"({a}/{a+b}) | jondo {100*c/(c+d):.2f}% ({c}/{c+d})")
    if ecarts:
        print("premiers ecarts fight (type, mapId, jondo, nous):", ecarts)
    return 0 if (badf == 0 and badb == 0 and pasinclus == 0 and vbad == 0) else 1


def main():
    """FR: joue les epreuves demandees et rend 0 (VERTE) ou 1 (ROUGE).
       EN: runs the requested checks; exit 0 green, 1 red."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(SORTIE))
    ap.add_argument("--epreuve", action="store_true", help="joue les 5 epreuves")
    ap.add_argument("--corpus", action="store_true",
                    help="rejoue les confrontations sur TOUTES les cartes (long)")
    ap.add_argument("--limite-partition", type=int, default=0)
    args = ap.parse_args()

    if args.corpus:
        return corpus(args.out)

    epreuves = [
        ("E1 carte-temoin + 3 sources independantes", lambda: e1_temoin(args.out)),
        ("E2 partition + ids 0..559", lambda: e2_partition(args.out, args.limite_partition)),
        ("E3 sabotage (doit rougir)", lambda: e3_sabotage(args.out)),
        ("E4 temoin negatif (mapId invente)", lambda: e4_temoin_negatif(args.out)),
        ("E5 rejeu byte-identique", lambda: e5_rejeu(args.out)),
    ]
    if not args.epreuve:
        epreuves = epreuves[:2]

    rc = 0
    for titre, f in epreuves:
        try:
            msg = f()
        except Refus as r:
            print(f"[ROUGE] {titre}\n         {r}")
            rc = 1
            continue
        except Exception as e:  # FR: une exception n'est JAMAIS un vert.
            print(f"[ROUGE] {titre}\n         exception {type(e).__name__}: {e}")
            rc = 1
            continue
        if msg is None:
            print(f"[ROUGE] {titre}\n         le sabotage n'a PAS ete detecte -- "
                  f"la gate ne mesure rien")
            rc = 1
        else:
            print(f"[VERT ] {msg}")
    print("---")
    print("GATE CARTES : " + ("VERTE" if rc == 0 else "ROUGE"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
