#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Extracteur de la GÉOMÉTRIE DES CARTES Dofus 3.0. Lit les 577 bundles Unity de
    `Content/Map/Data/`, décode chaque MonoBehaviour `map_<mapId>` (l'enveloppe
    `MapMetadata : ScriptableObject`, il2cpp.cs:395458, qui porte un `ClientMapData`,
    il2cpp.cs:123604-123645) et écrit UN JSON par carte : les 17 champs de
    `ClientCellData` (il2cpp.cs:123424-123440) pour les 560 cellules, les 4 voisins,
    les 4 listes de flèches de bord, les éléments interactifs et les métadonnées.
    WHAT: extracts Dofus 3.0 map geometry from the Unity map bundles -- one JSON per
    map with the 17 ClientCellData fields for all 560 cells, plus map metadata.

POURQUOI (04/09/2026) : c'est le TROU N°1 pour entrer sur une carte. Le client attend
    17 champs par cellule ; nous n'en avions que 2, tous deux DÉRIVÉS de JondoEmu
    (`mov` via map_walkable_cells.json, `fight` via map_fight_cells.json) — cf.
    `server/DONNEES-3.0-CARTE.md:148` : « 13 des 17 champs sont un trou ».
    Ni lot31, ni `datos/`, ni même la base de Jondo ne portent de géométrie de carte
    (DONNEES-3.0-CARTE.md:99) : le trou était structurel. Les bundles, eux, la portent.
    WHY: the client expects 17 fields per cell; we had 2, both derived. No existing
    source carried map geometry -- the bundles do.

COMMENT LANCER / HOW TO RUN :
    V=internal/artefacts/\\
      lot30-data-3.0-extract/.venv/bin/python
    nice -n 10 $V extraire_cartes.py --localiser 191105026  # index, dit quel bundle (~91 s)
    nice -n 10 $V extraire_cartes.py --bundle <nom.bundle>  # un seul bundle
    nice -n 10 $V extraire_cartes.py --carte 191105026      # une seule carte
    nice -n 10 $V extraire_cartes.py --tout                 # 17 353 cartes, ~12 min, 2,9 Go

GATE : `gate-cartes.py --epreuve` (5 épreuves, dont un sabotage qui DOIT rougir) et
    `gate-cartes.py --corpus` (confrontations sur les 17 353 cartes). Rien de ce que
    cet outil écrit ne doit être cité sans que la gate ait été rejouée. En propre :
    tout rejet est compté PAR CAUSE et listé dans `a-classer.tsv`, jamais étouffé ;
    le JSON ne porte ni horodatage ni chemin absolu, pour que le rejeu soit byte-identique.

Ne réécrit PAS le lecteur de bundle : réutilise `read_object` et `write_json` de lot30
(`lot30-data-3.0-extract/extract_bundle.py`, UnityPy 1.25.3, outil déjà prouvé).
Does NOT rewrite the bundle reader: reuses lot30's proven `read_object`/`write_json`.
"""
import argparse
import json
import re
import sys
import time
import warnings
from pathlib import Path

# --- Reutilisation de l'outil deja prouve (lot30) / reuse of the proven lot30 tool ---
LOT30 = Path("internal/artefacts/"
             "lot30-data-3.0-extract")
sys.path.insert(0, str(LOT30))
import UnityPy  # noqa: E402
from extract_bundle import read_object, DEFAULT_UNITY_VERSION, write_json  # noqa: E402

ENTREE = Path("internal/artefacts/"
              "lot37-mapdata-3.0/Content/Map/Data")
SORTIE = Path(__file__).resolve().parent / "sortie"

# FR: build NON mesuree -- aucun marqueur de version trouve dans les bundles ni dans les
#     deux catalogues (recherche de motifs de version = 0 resultat, mesure le 2026-09-04) ;
#     la version rendue par UnityPy est le REPLI qu'on lui donne, pas une lecture du fichier
#     (temoin: repli 6000.2.0f1 -> il annonce 6000.2f1). Seule ancre: la date de la copie.
# EN: build NOT measured -- no version marker in the bundles or in either catalog; the
#     version UnityPy reports is the fallback we hand it, not a read from the file.
BUILD = "DEDUITE 2026-08-15 (aucun marqueur de version dans bundles/catalogues)"

# FR: les 17 champs de `ClientCellData`, DANS L'ORDRE DU DUMP et sous leurs noms du dump
#     (aucun renommage : un consommateur doit pouvoir relire le dump ligne à ligne).
#     Toutes les lignes ci-dessous : internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs
# EN: the 17 ClientCellData fields, in dump order, under their dump names (no renaming).
CELL_FIELDS = [
    "cellNumber",                       # uint -- :123424  numéro de la cellule, 0..559
    "speed",                            # int  -- :123425  modificateur de vitesse
    "mapChangeData",                    # int  -- :123426  masque de changement de carte
    "moveZone",                         # int  -- :123427  zone de déplacement
    "linkedZone",                       # int  -- :123428  zone liée (cf. GetLinkedRpZone)
    "mov",                              # bool -- :123429  MARCHABLE
    "los",                              # bool -- :123430  laisse passer la LIGNE DE VUE
    "nonWalkableDuringFight",           # bool -- :123431  bloquée en combat
    "nonWalkableDuringRP",              # bool -- :123432  bloquée hors combat
    "farmCell",                         # bool -- :123433  cellule de culture
    "visible",                          # bool -- :123434  cellule affichée
    "havenbagCell",                     # bool -- :123435  cellule de havre-sac
    "roleplayMonstersMovementBlocked",  # bool -- :123436  monstres bloqués hors combat
    "floor",                            # int  -- :123437  hauteur / étage
    "red",                              # bool -- :123438  placement combat, équipe rouge
    "blue",                             # bool -- :123439  placement combat, équipe bleue
    "arrow",                            # int  -- :123440  flèche de bord de carte
]
# FR: les 10 champs déclarés `bool` dans le dump (lignes ci-dessus). Le typetree les rend
#     en 0/1 ; on les écrit en true/false. Une valeur hors 0/1 n'est PAS convertie (elle
#     serait perdue en silence) : elle est gardée brute et signalée en rejet.
# EN: the 10 dump-declared bools; 0/1 -> true/false, anything else kept raw and flagged.
CELL_BOOLS = {"mov", "los", "nonWalkableDuringFight", "nonWalkableDuringRP", "farmCell",
              "visible", "havenbagCell", "roleplayMonstersMovementBlocked", "red", "blue"}

# FR: 560 cellules par carte. Source dump : `private const int CellsCount = 560`
#     -- il2cpp.cs:245096, et une 2e déclaration indépendante à il2cpp.cs:332686.
#     La grille « 14x40 » est DÉDUITE : `private const int Column = 14` (il2cpp.cs:245098)
#     et 560/14 = 40 ; le dump n'écrit nulle part « 14x40 » tel quel.
#     MESURÉ : les 17 353 cartes extraites portent toutes exactement 560 cellules.
# EN: 560 cells/map, from the dump's CellsCount; the 14x40 grid is DERIVED from Column=14.
CELL_ATTENDU = 560
COLONNES = 14

# FR: champs de ClientMapData recopies tels quels. EN: ClientMapData fields copied verbatim.
# Source: il2cpp.cs:123604-123645
MAP_SCALARS = ["topNeighbourId", "bottomNeighbourId", "leftNeighbourId", "rightNeighbourId"]
MAP_ARROWS = ["topArrowCellList", "leftArrowCellList", "bottomArrowCellList", "rightArrowCellList"]
MAP_KEPT = ["backgroundColor", "playlistSet", "interactiveElements", "boundingBoxes",
            "localizedSounds", "stagingSequences", "mapWindConfiguration",
            "mapPostProcessConfiguration", "mapWaveConfiguration",
            "mapNoiseModifierConfiguration"]
# FR: listes de RENDU pur -- on garde le compte, pas les milliers de transforms (poids).
# EN: pure RENDERING lists -- we keep the count, not the thousands of transforms (size).
MAP_COUNTED = ["backgroundElements", "sortableElements", "foregroundElements",
               "animatedElements", "refractionElements", "particlesParameters"]
# FR: atlas de rendu (dict, pas liste) -- on note leur presence, pas leur contenu.
# EN: rendering atlases (dict, not list) -- presence noted, content dropped.
MAP_ATLASES = ["foregroundMaterialData", "backgroundMaterialData", "sortableMaterialData"]

# FR: nom d'un asset de carte dans le bundle -- MESURÉ : 17 353 assets sur 17 354 suivent
#     ce motif ; le seul hors-motif est `elements` (bibliothèque d'éléments partagés).
# EN: map asset naming inside the bundles; the single exception is the shared `elements`.
NOM_CARTE = re.compile(r"^map_(\d+)$")


class Rejets:
    """FR: compte et liste les rejets PAR CAUSE. Une extraction qui tait ses échecs
       fabrique un vert : ici tout rejet finit nommé dans `a-classer.tsv`.
       EN: counts and lists rejects BY CAUSE -- a silent failure would fake success."""

    def __init__(self):
        """FR: deux vues du même flux -- le détail ligne à ligne, et le compte par cause.
           EN: two views of the same stream -- line detail, and per-cause counts."""
        self.lignes = []
        self.par_cause = {}

    def add(self, cause, bundle, cible, detail=""):
        """FR: enregistre un rejet. Le détail est tronqué et ses tabulations retirées
           pour ne pas casser le TSV -- la cause, elle, n'est jamais tronquée.
           EN: records one reject; detail is TSV-safe and truncated, cause never is."""
        self.par_cause[cause] = self.par_cause.get(cause, 0) + 1
        # 300 : plafond ARBITRAIRE de lisibilité du TSV (aucune source, aucun enjeu) ;
        # la CAUSE, elle, n'est jamais tronquée -- c'est elle qui porte le sens.
        self.lignes.append((cause, bundle, str(cible), detail.replace("\t", " ")[:300]))

    def ecrire(self, path):
        """FR: écrit le TSV des rejets, en-tête comprise, même s'il est vide (un fichier
           vide dit « mesuré, zéro » ; un fichier absent ne dit rien).
           EN: writes the reject TSV even when empty -- empty means measured-zero."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write("cause\tbundle\tcible\tdetail\n")
            for l in self.lignes:
                f.write("\t".join(l) + "\n")


def resoudre_refs(tree):
    """FR: index rid -> entree du registre SerializeReference (references.RefIds)."""
    refs = (tree.get("references") or {}).get("RefIds") or []
    return {r["rid"]: r for r in refs if isinstance(r, dict) and "rid" in r}


def deref(val, rid_map):
    """FR: remplace {'rid': N} par la donnee referencee ; rid<0 = null Unity."""
    if isinstance(val, dict) and set(val.keys()) == {"rid"}:
        r = rid_map.get(val["rid"])
        if r is None:
            return None
        cls = (r.get("type") or {}).get("class")
        data = r.get("data")
        # FR: sentinelle "null" d'Unity (rid negatif, classe vide, pas de donnee) -> null JSON.
        # EN: Unity's null sentinel (negative rid, empty class, no data) -> JSON null.
        if not cls and not data:
            return None
        d = {"_class": cls}
        if isinstance(data, dict):
            d.update({k: deref(v, rid_map) for k, v in data.items()})
        elif data is not None:
            d["_data"] = data
        return d
    if isinstance(val, list):
        return [deref(v, rid_map) for v in val]
    return val


def construire_carte(tree, map_id, bundle_nom, path_id, rej):
    """FR: ClientMapData (typetree) -> enregistrement carte deterministe.
       EN: ClientMapData typetree -> deterministic map record."""
    md = tree.get("mapData")
    if not isinstance(md, dict):
        rej.add("mapdata_absent", bundle_nom, map_id, "objet sans champ mapData")
        return None
    rid_map = resoudre_refs(tree)

    brut = md.get("cellsData")
    if not isinstance(brut, list):
        rej.add("cellsdata_absent", bundle_nom, map_id, "mapData sans cellsData")
        return None

    cellules = []
    champs_absents = set()
    for i, c in enumerate(brut):
        manquants = [f for f in CELL_FIELDS if f not in c]
        if manquants:
            # FR: schema de cellule PLUS ANCIEN dans ce bundle. On garde la carte et on
            #     ecrit `null` -- un null dit « absent a la source », un `false` MENTIRAIT.
            # EN: OLDER cell schema in this bundle. Keep the map, write `null` -- a null
            #     says "absent at the source", a `false` would fabricate a value.
            if not champs_absents:
                rej.add("champ_cellule_manquant", bundle_nom, map_id,
                        f"{','.join(manquants)} absent(s) des {len(brut)} cellules "
                        f"-> ecrit null, carte CONSERVEE")
            champs_absents.update(manquants)
        out = {}
        for f in CELL_FIELDS:
            if f not in c:
                out[f] = None
                continue
            v = c[f]
            if f in CELL_BOOLS:
                if v in (0, 1, True, False):
                    v = bool(v)
                else:
                    # FR: un "bool" hors 0/1 = anomalie -> on garde le brut ET on la signale.
                    rej.add("valeur_bool_inattendue", bundle_nom, map_id, f"{f}={v!r} cell#{i}")
            out[f] = v
        inconnus = [k for k in c if k not in CELL_FIELDS]
        if inconnus:
            rej.add("champ_cellule_en_trop", bundle_nom, map_id, f"cellule#{i}: {inconnus}")
        cellules.append(out)

    if len(cellules) != CELL_ATTENDU:
        rej.add("nb_cellules_inattendu", bundle_nom, map_id, f"{len(cellules)} != {CELL_ATTENDU}")

    mov = [c["cellNumber"] for c in cellules if c["mov"]]
    rec = {
        "mapId": map_id,
        "build": BUILD,
        "source_bundle": bundle_nom,
        "asset_name": f"map_{map_id}",
        "path_id": path_id,
        "cellCount": len(cellules),
        # FR: present UNIQUEMENT si le bundle porte un schema de cellule plus ancien.
        "champsCelluleAbsents": sorted(champs_absents) if champs_absents else None,
        "cellsData": cellules,
        "resume": {
            "mov": len(mov),
            "los": sum(1 for c in cellules if c["los"]),
            "losBloquees": sum(1 for c in cellules if not c["los"]),
            "nonWalkableDuringFight": sum(1 for c in cellules if c["nonWalkableDuringFight"]),
            "nonWalkableDuringRP": sum(1 for c in cellules if c["nonWalkableDuringRP"]),
            "farmCell": sum(1 for c in cellules if c["farmCell"]),
            "havenbagCell": sum(1 for c in cellules if c["havenbagCell"]),
            "visible": sum(1 for c in cellules if c["visible"]),
            "movEtCombattables": sum(1 for c in cellules
                                     if c["mov"] and not c["nonWalkableDuringFight"]),
            "avecMapChangeData": sum(1 for c in cellules if c["mapChangeData"]),
            "avecArrow": sum(1 for c in cellules if c["arrow"]),
        },
    }
    for f in MAP_SCALARS + MAP_ARROWS:
        if f not in md:
            rej.add("champ_carte_manquant", bundle_nom, map_id, f)
        rec[f] = md.get(f)
    for f in MAP_KEPT:
        if f in md:
            rec[f] = deref(md[f], rid_map)
    rec["renderCounts"] = {f: len(md[f]) for f in MAP_COUNTED if isinstance(md.get(f), list)}
    rec["renderCounts"].update({f: bool(md.get(f)) for f in MAP_ATLASES if f in md})
    for f in ("mapTextures", "allowMapEffects"):
        if f in tree:
            rec[f] = tree[f]
    inconnus = [k for k in md if k not in
                set(MAP_SCALARS + MAP_ARROWS + MAP_KEPT + MAP_COUNTED + MAP_ATLASES)
                | {"cellsData"}]
    if inconnus:
        rej.add("champ_carte_en_trop", bundle_nom, map_id, ",".join(sorted(inconnus)))
    return rec


def lire_container(env):
    """FR: liste des assets du bundle via AssetBundle.m_Container (lecture peu couteuse)."""
    for o in env.objects:
        if o.type.name == "AssetBundle":
            tr = o.read_typetree()
            return [k for k, _ in tr.get("m_Container", [])]
    return []


def bundles_du_dossier(racine):
    """FR: les bundles du dossier, triés (l'ordre fixe rend les parcours comparables).
       MESURÉ : 577 `.bundle` -- les 2 autres fichiers sont catalog_1.0.bin et .hash.
       EN: the folder's bundles, sorted so two runs walk them in the same order."""
    return sorted(p for p in racine.glob("*.bundle") if p.is_file())


def indexer(racine, rej):
    """FR: mapId -> bundle, par m_Container seulement. EN: cheap mapId -> bundle index."""
    idx = {}
    bundles = bundles_du_dossier(racine)
    t0 = time.time()
    for i, b in enumerate(bundles, 1):
        try:
            env = UnityPy.load(str(b))
            noms = lire_container(env)
        except Exception as e:
            rej.add("bundle_illisible", b.name, "-", f"{type(e).__name__}: {e}")
            continue
        for n in noms:
            m = NOM_CARTE.match(n[:-6] if n.endswith(".asset") else n)
            if m:
                idx[int(m.group(1))] = b.name
            else:
                rej.add("asset_non_carte", b.name, n, "nom hors motif map_<id>.asset")
        # 100 : cadence d'affichage ARBITRAIRE (~15 s de travail), pour que la passe
        # d'index de 91 s montre qu'elle avance sans noyer le terminal.
        if i % 100 == 0:
            print(f"  index {i}/{len(bundles)} ({time.time()-t0:.0f}s)", flush=True)
    return idx, bundles


def extraire_bundle(path, rej, cibles=None):
    """FR: rend {mapId: enregistrement} pour un bundle. `cibles` = filtre d'ids."""
    out = {}
    try:
        env = UnityPy.load(str(path))
        objets = list(env.objects)
    except Exception as e:
        rej.add("bundle_illisible", path.name, "-", f"{type(e).__name__}: {e}")
        return out
    for o in objets:
        if o.type.name == "AssetBundle":
            continue
        if o.type.name != "MonoBehaviour":
            rej.add("type_objet_inattendu", path.name, o.path_id, o.type.name)
            continue
        try:
            nom = o.peek_name()
        except Exception as e:
            rej.add("nom_illisible", path.name, o.path_id, f"{type(e).__name__}: {e}")
            continue
        m = NOM_CARTE.match(nom or "")
        if not m:
            rej.add("objet_non_carte", path.name, o.path_id, f"nom={nom!r}")
            continue
        map_id = int(m.group(1))
        if cibles is not None and map_id not in cibles:
            continue
        res = read_object(o)            # <- outil lot30, non reecrit
        if not res.get("decoded"):
            rej.add("objet_non_decode", path.name, map_id, res.get("error", ""))
            continue
        rec = construire_carte(res["typetree"], map_id, path.name, o.path_id, rej)
        if rec is not None:
            out[map_id] = rec
    return out


def ecrire_carte(rec, dossier):
    """FR: JSON deterministe (aucun horodatage, aucun chemin absolu) -> rejeu byte-identique."""
    p = dossier / f"{rec['mapId']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return p


# FR: en-tête de `index-cartes.tsv` -- une ligne par carte, lisible sans ouvrir 17 353 JSON.
# EN: header of index-cartes.tsv -- one line per map, readable without opening 17353 JSONs.
LIGNE_TSV = ("mapId\tbundle\tcellCount\tmov\tlosBloquees\tmovEtCombattables\t"
             "top\tbottom\tleft\tright\tinteractifs\tbuild\n")


def ligne_tsv(rec):
    """FR: une carte -> une ligne d'index. Porte la BUILD sur chaque ligne (loi L6 du
       cahier des charges : tout artefact porte sa build, sinon un rebrassage d'Ankama
       rend le fichier faux en silence).
       EN: one map -> one index line, carrying its build on every row (rule L6)."""
    r = rec["resume"]
    return "\t".join(str(x) for x in [
        rec["mapId"], rec["source_bundle"], rec["cellCount"], r["mov"], r["losBloquees"],
        r["movEtCombattables"], rec.get("topNeighbourId"), rec.get("bottomNeighbourId"),
        rec.get("leftNeighbourId"), rec.get("rightNeighbourId"),
        len(rec.get("interactiveElements") or []), rec["build"]]) + "\n"


def main():
    """FR: aiguille vers UN des 4 modes (localiser / carte / bundle / tout), écrit les
       sorties et rend 0, sauf 2 si zéro carte n'est sortie -- un pipeline ne doit
       jamais confondre « rien à faire » et « échec total ».
       EN: dispatches one of four modes; exit 2 on a zero-map run, never a silent 0."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--entree", default=str(ENTREE))
    ap.add_argument("--out", default=str(SORTIE))
    ap.add_argument("--unity-version", default=DEFAULT_UNITY_VERSION)
    ap.add_argument("--localiser", type=int, help="dit dans quel bundle vit un mapId, puis sort")
    ap.add_argument("--carte", type=int, help="extrait UNE carte")
    ap.add_argument("--bundle", help="extrait UN bundle (nom de fichier)")
    ap.add_argument("--tout", action="store_true", help="extrait tous les bundles")
    ap.add_argument("--limite", type=int, default=0, help="n'ouvrir que N bundles (essai)")
    args = ap.parse_args()

    UnityPy.config.FALLBACK_UNITY_VERSION = args.unity_version
    warnings.filterwarnings("ignore", category=UserWarning)
    racine, out = Path(args.entree), Path(args.out)
    dossier_cartes = out / "cartes"
    rej = Rejets()
    t0 = time.time()

    if args.localiser is not None:
        idx, bundles = indexer(racine, rej)
        b = idx.get(args.localiser)
        print(f"{args.localiser} -> {b or 'ABSENT'}")
        print(f"bundles ouverts : {len(bundles)} | cartes indexees : {len(idx)}")
        write_json({"build": BUILD, "index": {str(k): v for k, v in sorted(idx.items())}},
                   out / "index-bundles.json")
        # FR: fichier de rejets DISTINCT -- ne pas ecraser celui d'une extraction complete.
        # EN: SEPARATE reject file -- never clobber a full extraction's a-classer.tsv.
        rej.ecrire(out / "a-classer-index.tsv")
        return 0 if b else 1

    if args.carte is not None:
        idx, _ = indexer(racine, rej)
        b = idx.get(args.carte)
        if not b:
            print(f"REFUS: carte {args.carte} absente des bundles", file=sys.stderr)
            rej.ecrire(out / "a-classer.tsv")
            return 1
        cartes = extraire_bundle(racine / b, rej, cibles={args.carte})
        travail = [(racine / b).name]
    elif args.bundle:
        cartes = extraire_bundle(racine / args.bundle, rej)
        travail = [args.bundle]
    elif args.tout:
        cartes = None
        travail = [p.name for p in bundles_du_dossier(racine)]
        if args.limite:
            travail = travail[:args.limite]
    else:
        print("Rien a faire : --localiser | --carte | --bundle | --tout", file=sys.stderr)
        return 2

    dossier_cartes.mkdir(parents=True, exist_ok=True)
    tsv = out / "index-cartes.tsv"
    n_cartes = 0
    with tsv.open("w", encoding="utf-8") as ftsv:
        ftsv.write(LIGNE_TSV)
        if cartes is not None:
            for mid in sorted(cartes):
                ecrire_carte(cartes[mid], dossier_cartes)
                ftsv.write(ligne_tsv(cartes[mid]))
                n_cartes += 1
        else:
            for i, nom in enumerate(travail, 1):
                lot = extraire_bundle(racine / nom, rej)
                for mid in sorted(lot):
                    ecrire_carte(lot[mid], dossier_cartes)
                    ftsv.write(ligne_tsv(lot[mid]))
                    n_cartes += 1
                if i % 25 == 0 or i == len(travail):
                    print(f"  {i}/{len(travail)} bundles | {n_cartes} cartes | "
                          f"{time.time()-t0:.0f}s", flush=True)
    rej.ecrire(out / "a-classer.tsv")

    print("---")
    print(f"Bundles parcourus : {len(travail)}")
    print(f"Cartes ecrites    : {n_cartes}  -> {dossier_cartes}")
    print(f"Index             : {tsv}")
    print(f"Rejets            : {sum(rej.par_cause.values())} "
          f"{rej.par_cause if rej.par_cause else '(aucun)'}")
    print(f"Duree             : {time.time()-t0:.0f}s")
    if n_cartes == 0:
        print("ALERTE: 0 carte extraite -- ne PAS presenter comme une extraction reussie.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
