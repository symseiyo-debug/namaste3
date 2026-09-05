#!/usr/bin/env python3
"""
matcher_v4.py — Étage 1 (Namaste 3), matcher v4.

QUOI : hiérarchie de provenance à 3 niveaux (`capture_verifiee` > `structure_v2` >
    `proposition_jondo_seule`) pour trancher les conflits de graines que v3 laissait à
    un choix par défaut arbitraire. Réutilise `propagate`/`arrosage_avec_voisinage`/
    `load_edges` de `matcher_v3.py` SANS les dupliquer. Écrit `correspondance-v4.tsv`.
POURQUOI (04/09/2026, brief) : v3 a trouvé 5 conflits entre graines
    `jondo-anclas` et `v2`, tranchés par défaut en faveur de `v2` — et un cas mesuré
    (`jtg`→`GiftsListMessage`) montrait que ce défaut est FAUX : `jtg` est VÉRIFIÉ par
    242 captures réelles (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6,
    `ConnectionProtocol.cs:191-221`), alors que la proposition Jondo générique
    (`anclas_3.6.10.10.tsv`) n'est qu'une étiquette stylée non extraite (son propre
    en-tête le dit). v4 corrige : une graine attestée par une capture RÉELLE (chaîne
    fléchée sourcée `fichier:ligne` dans `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6/§5 ou
    `COMPLEMENT-CHEMIN-CRITIQUE-G1.md`) bat toujours une correspondance structurelle
    (v2), qui bat toujours une simple proposition Jondo non recoupée.
COMMENT LANCER : `python3 matcher_v4.py` (lit signatures*.jsonl, correspondance-v2.tsv,
    aretes-voisinage.jsonl, anclas Jondo, écrit `correspondance-v4.tsv` +
    `A-NOMMER-PAR-CAPTURE.tsv`).
GATE : logue le niveau de CHAQUE graine et vérifie explicitement que `jtg` gagne
    `GiftsListMessage` sur `kmz` (assertion nommée, pas un espoir) — voir §3 de
    RAPPORT-MATCHER-V4.md pour le résultat mesuré.

FR : les 24 opcodes `capture_verifiee` ci-dessous sont TOUS transcrits depuis les 2
     documents cités par team-lead, avec leur citation fichier:ligne propre (jamais une
     recopie du tag "VÉRIFIÉ" sans vérifier qu'un NOM CLAIR l'accompagne — 8 opcodes du
     chemin critique sont VÉRIFIÉS en FORME mais SANS nom proposé — `mgq`,`mgt`,`hpd`,
     `krs`,`kqp`,`ksl`,`krt`,`hjk` — ils restent DES NŒUDS DE VOISINAGE utiles à la
     propagation mais ne peuvent PAS semer une graine sans nom à donner).
EN : the 24 `capture_verifiee` opcodes below are ALL transcribed from the 2 docs
     team-lead cited, each with its own fichier:ligne citation — 8 critical-path
     opcodes are VÉRIFIÉ in FORM but carry no proposed name, so they can't seed a
     named graine (still useful as neighborhood nodes for propagation).
Stdlib seule. 0 LLM.
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matcher_v2 import (
    load_jsonl, obf_round0, obf_assembly_bucket, merge_clear_fields, clear_assembly_bucket,
    build_type_refs_obf, build_type_refs_clear,
)
from matcher_v3 import (
    load_edges, get_or_make_clear, propagate, arrosage_avec_voisinage, load_v2_pairs,
    RAFALE_BIENVENUE,
)
from charger_proto_clair import load_anclas, JONDO_ANCLAS

HERE = os.path.dirname(os.path.abspath(__file__))
SIG_OBF_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
SIG_CLEAR_PATH = os.path.join(HERE, "signatures-claires.jsonl")
CORRESPONDANCE_V2 = os.path.join(HERE, "correspondance-v2.tsv")
ARETES_PATH = os.path.join(HERE, "aretes-voisinage.jsonl")
CHEMIN_CRITIQUE_PATH = os.path.join(os.path.dirname(HERE), "chemin-critique.txt")
OUT_TSV = os.path.join(HERE, "correspondance-v4.tsv")
OUT_A_NOMMER = os.path.join(HERE, "A-NOMMER-PAR-CAPTURE.tsv")

HEADER = ["classe_obf", "typedef_index", "nom_clair", "score", "methode", "niveau",
          "statut", "provenances_daccord", "nb_candidats_a_egalite", "chemin_de_preuve"]

# Priorité NUMÉRIQUE explicite (plus petit = plus fiable) — jamais une comparaison de
# chaîne implicite, un futur 4e niveau s'insère ici sans deviner un ordre alphabétique.
# / Explicit numeric priority (smaller = more trusted) — a future 4th level slots in
# here without guessing an alphabetical order.
NIVEAU_PRIORITE = {"capture_verifiee": 0, "structure_v2": 1, "proposition_jondo_seule": 2,
                   "arrastre": 3, "arrosage": 4}

# FR: transcrit depuis `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6 (rafale, ordre fléché
# exact) et §5 (carte/déplacement), complété par `COMPLEMENT-CHEMIN-CRITIQUE-G1.md`
# (kvw/kvl/jsn confirmés par double source) — CHAQUE valeur ici a un tag VÉRIFIÉ **et**
# un nom clair proposé dans l'un des 2 documents (8 opcodes du chemin critique sont
# VÉRIFIÉS en forme mais SANS nom : `mgq`,`mgt`,`hpd`,`krs`,`kqp`,`ksl`,`krt`,`hjk` —
# volontairement ABSENTS d'ici, cf. docstring). Source précise en commentaire de chaque
# ligne. EN: transcribed from the 2 docs team-lead cited; every value here has BOTH a
# VÉRIFIÉ tag AND a proposed clear name in one of them.
CAPTURE_VERIFIEE = {
    "kqz": "AuthenticationTicketMessage",   # SEQUENCE §3.5, anclas ligne kqz
    "kra": "AuthenticationTicketAcceptedMessage",  # SEQUENCE §3.6, ConnectionProtocol.cs:195
    "lqu": "BasicTimeMessage",              # SEQUENCE §3.6 + COMPLEMENT: ConnectionProtocol.cs:196-199,234
    "hoy": "HelloGameMessage",              # COMPLEMENT: ConnectionProtocol.cs:258-269 (BuildHoy)
    "kqu": "ServerOptionalFeaturesMessage",  # SEQUENCE §3.6, ConnectionProtocol.cs:201
    "mgz": "ContentCatalogVersionMessage",  # COMPLEMENT: ConnectionProtocol.cs:206,240 (CatalogMark)
    "kvi": "CharactersListMessage",         # SEQUENCE §4.1, ConnectionProtocol.cs:284-336
    "kvd": "CharactersListEndMessage",      # SEQUENCE §4.1, ConnectionProtocol.cs:216
    "jtg": "GiftsListMessage",              # SEQUENCE §3.6, ConnectionProtocol.cs:218 — LE cas du conflit
    "kvw": "CharacterSelectionMessage",     # COMPLEMENT: CharacterSelectionHandler.cs:210-238 + .proto:13498-13500
    "kvl": "CharacterFirstSelectionMessage",  # COMPLEMENT: .proto:13459-13462 (divergence f1/f2 notée)
    "kva": "CharacterSelectedSuccessMessage",  # SEQUENCE §4.2, ConnectionProtocol.cs:338-356
    "jsn": "GameContextRefreshEntityLookMessage",  # COMPLEMENT: GameNodeProxy.cs:296-301
    "lqc": "GameContextCreateRequestMessage",  # SEQUENCE §5.1, GameNodeProxy.cs:384
    "jru": "CurrentMapMessage",             # SEQUENCE §5.3, WorldEntry.cs:698-709
    "jrh": "WorldEntryRequests",            # SEQUENCE §5.2, GameNodeProxy.cs:312-329
    "jss": "MapComplementaryInformationsDataMessage",  # SEQUENCE §5.2, docs/world.md §5.5
    "lva": "MapLoadedMessage",              # SEQUENCE §5.2, ConnectionProtocol.cs:636
    "jrw": "GameMapMovementRequestMessage",  # SEQUENCE §5.3, WorldMoveHandler.cs:69
    "jsj": "GameMapMovementMessage",        # SEQUENCE §5.3, docs/world.md §1.2
    "jqi": "MapMovementConfirmRequest",     # SEQUENCE §5.3, docs/protocol.md §3
    "jsq": "MapMovementConfirmResponse",    # SEQUENCE §5.3, ConnectionProtocol.cs:2171-2179
    "jqk": "ChangeMapMessage",              # SEQUENCE §5.3, WorldMoveHandler.cs:39-45,167,361
    "jsd": "GameContextRemoveElementMessage",  # SEQUENCE §5.3, docs/sessions.md §5
}


def log(msg):
    """Écrit sur stderr. / Writes to stderr."""
    print(msg, file=sys.stderr, flush=True)


def charge_chemin_critique(path):
    """Charge les 32 opcodes du chemin critique (1/ligne, commentaires # ignorés).
    / Loads the 32 critical-path opcodes (1/line, # comments skipped)."""
    if not os.path.exists(path):
        return []
    ops = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s and not s.startswith("#"):
                ops.append(s)
    return ops


def build_graines_hierarchie(v2_path=CORRESPONDANCE_V2, stats=None):
    """FR: fusionne les 3 niveaux dans l'ordre de priorité — chaque graine déjà posée
    par un niveau plus fiable n'est JAMAIS écrasée par un niveau moins fiable (on trie
    NIVEAU_PRIORITE croissant et on n'écrit que si le nom clair n'est pas déjà pris par
    un niveau meilleur). Un conflit est un fait, jamais un hasard d'ordre d'itération
    dict — trié explicitement. EN: merges the 3 levels by priority order — a seed
    already placed by a more trusted level is NEVER overwritten by a less trusted one;
    a conflict is a fact, never a dict-iteration-order accident (explicit sort)."""
    stats = stats if stats is not None else {}
    anclas = load_anclas(JONDO_ANCLAS)
    v2_pairs = load_v2_pairs(v2_path)

    sources = []  # (niveau, opcode, nom_clair, chemin)
    for opcode, name in sorted(CAPTURE_VERIFIEE.items()):
        sources.append(("capture_verifiee", opcode, name,
                         f"graine capture_verifiee : {opcode}={name} (SEQUENCE-CHEMIN-CRITIQUE-JONDO.md "
                         "ou COMPLEMENT-CHEMIN-CRITIQUE-G1.md, 242 captures réelles)"))
    for opcode, name in sorted(v2_pairs.items()):
        sources.append(("structure_v2", opcode, name, "graine structure_v2 (forme+champs, matcher_v2.py)"))
    for opcode, name in sorted(anclas.items()):
        sources.append(("proposition_jondo_seule", opcode, name,
                         f"graine proposition_jondo_seule : anclas Jondo, opcode={opcode} "
                         "(propositions stylée, PAS extraite — en-tête anclas.tsv)"))

    graines, conflits_tranches = {}, []
    nom_pris_par = {}  # nom_clair -> (niveau, opcode) déjà retenu
    for niveau, opcode, name, chemin in sources:
        if opcode in graines:
            continue  # un opcode DÉJÀ semé par un niveau plus fiable ne se réécrit jamais
        if name in nom_pris_par:
            niveau_gagnant, opcode_gagnant = nom_pris_par[name]
            if niveau_gagnant != niveau:
                conflits_tranches.append((name, niveau_gagnant, opcode_gagnant, niveau, opcode))
            continue  # nom déjà pris (par ce niveau ou un meilleur) — jamais un doublon
        graines[opcode] = (name, niveau, chemin)
        nom_pris_par[name] = (niveau, opcode)

    stats["par_niveau"] = {lvl: sum(1 for _, l, _ in graines.values() if l == lvl)
                            for lvl in ("capture_verifiee", "structure_v2", "proposition_jondo_seule")}
    stats["conflits_tranches_par_hierarchie"] = len(conflits_tranches)
    return graines, conflits_tranches


# Cœur : construit les graines hiérarchisées, propage (v3), arrose (v3), écrit le TSV.
# / Core: builds the tiered seeds, propagates (v3), arroses (v3), writes the TSV.
def run(sig_obf_path=SIG_OBF_PATH, sig_clear_path=SIG_CLEAR_PATH, v2_path=CORRESPONDANCE_V2,
        aretes_path=ARETES_PATH, out_path=OUT_TSV):
    """Cœur : construit les graines hiérarchisées, propage (v3), arrose (v3), écrit le TSV.
    / Core: builds the tiered seeds, propagates (v3), arroses (v3), writes the TSV."""
    obf_records = load_jsonl(sig_obf_path)
    clear_records_all = load_jsonl(sig_clear_path)
    clear_records = [r for r in clear_records_all if not r.get("nom_clair_suspect")]

    obf_top = [r for r in obf_records if r["depth"] == 0]
    for o in obf_top:
        o["_sig"] = obf_round0(o)
    obf_by_bucket = defaultdict(list)
    for o in obf_top:
        obf_by_bucket[obf_assembly_bucket(o)].append(o)
    obf_index = {o["obf_name"]: o for o in obf_top}
    obf_refs = {o["obf_name"]: build_type_refs_obf(o) for o in obf_top}

    for c in clear_records:
        c["_sig"], _ = merge_clear_fields(c)
    clear_by_bucket = defaultdict(list)
    for c in clear_records:
        clear_by_bucket[clear_assembly_bucket(c)].append(c)
    clear_by_name = {c["clear_name"]: c for c in clear_records}
    clear_refs = {c["clear_name"]: build_type_refs_clear(c) for c in clear_records}

    edges = load_edges(aretes_path)

    stats = {}
    graines, conflits = build_graines_hierarchie(v2_path, stats)
    propagate(graines, obf_index, clear_by_name, obf_refs, clear_refs, stats)
    # FR: les graines nées de l'arrastre héritent du niveau "arrastre" (pas du niveau du
    # parent) — un fait propagé structurellement n'est pas une capture réelle. EN: seeds
    # born from parent-drag get the "arrastre" level (not the parent's) — a
    # structurally-propagated fact is not an actual capture.
    graines_avant_arrastre = set(build_graines_hierarchie(v2_path, {})[0].keys())
    for tok in list(graines.keys()):
        if tok not in graines_avant_arrastre:
            name, _niveau_herite, chemin = graines[tok]
            graines[tok] = (name, "arrastre", chemin)
    arrosage_avec_voisinage(obf_by_bucket, clear_by_bucket, graines, edges, obf_refs, stats)

    rows = []
    matched_clear = {name for name, _, _ in graines.values()}
    for obf_tok, (clear_name, niveau, chemin) in graines.items():
        o = obf_index.get(obf_tok)
        methode = niveau if niveau in ("capture_verifiee", "structure_v2", "proposition_jondo_seule") else niveau
        rows.append([obf_tok, o["typedef_index"] if o else "", clear_name,
                     "1.0" if niveau in ("capture_verifiee", "structure_v2") else "",
                     methode, niveau, "DÉDUIT", niveau, "1", chemin])
    for c in clear_records:
        if c["clear_name"] in matched_clear:
            continue
        bucket = clear_assembly_bucket(c)
        n_cands = sum(1 for o in obf_by_bucket.get(bucket, [])
                      if o["obf_name"] not in graines and o["_sig"] == c["_sig"])
        rows.append(["", "", c["clear_name"], "", "", "", "À_CLASSER", "", str(n_cands),
                     f"0 ou plusieurs candidats de même round-0 dans {bucket}, aucun retenu"])

    rows.sort(key=lambda r: r[2])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    return rows, stats, graines, conflits


def cite_les_plus_cites(edges, deja_nommes, obf_index, top_n=15):
    """FR: les tokens obfusqués NON nommés après v4 les plus cités par co-occurrence
    (voisinage riche = probablement une famille importante). EN: unnamed obfuscated
    tokens with the most co-occurrence edges after v4 (rich neighborhood = likely an
    important family)."""
    scored = [(tok, len(nbs)) for tok, nbs in edges.items()
              if tok not in deja_nommes and tok in obf_index]
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]


def ecrire_a_nommer(graines, obf_index, edges, chemin_critique_ops):
    """FR: écrit A-NOMMER-PAR-CAPTURE.tsv — le cahier des charges de la capture
    dynamique (L7) : chemin critique non résolu + familles les plus citées, avec un
    indice CONCRET de ce qu'une capture doit montrer. EN: writes the dynamic-capture
    (L7) spec: unresolved critical path + most-cited families, with a concrete hint of
    what a capture should show."""
    nommes = set(graines.keys())
    rows = []
    for op in chemin_critique_ops:
        if op in nommes:
            continue
        o = obf_index.get(op)
        voisins = sorted(edges.get(op, ()))[:5]
        rows.append([op, o["typedef_index"] if o else "", "chemin_critique",
                     "écran de connexion/perso/carte selon la position dans la séquence "
                     f"(cf. chemin-critique.txt) — voisins de voisinage : {','.join(voisins) or '(aucun)'}"])
    cites = cite_les_plus_cites(edges, nommes, obf_index, top_n=15)
    for tok, nb_edges in cites:
        o = obf_index.get(tok)
        voisins = sorted(edges.get(tok, ()))[:5]
        rows.append([tok, o["typedef_index"] if o else "", f"famille_citee({nb_edges}_arêtes)",
                     f"capturer une action qui touche un de ses voisins : {','.join(voisins) or '(aucun)'}"])
    with open(OUT_A_NOMMER, "w", encoding="utf-8") as f:
        f.write("classe_obf\ttypedef_index\traison\tindice_pour_la_capture\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    return rows


def main():
    """Point d'entrée : construit v4, écrit le TSV + A-NOMMER-PAR-CAPTURE.tsv, vérifie jtg.
    / Entry point: builds v4, writes the TSV + A-NOMMER-PAR-CAPTURE.tsv, checks jtg."""
    for p in (SIG_OBF_PATH, SIG_CLEAR_PATH):
        if not os.path.exists(p):
            log("ABSENT : lance d'abord extraire_signatures.py et charger_proto_clair.py.")
            sys.exit(2)
    rows, stats, graines, conflits = run()
    a_classer = sum(1 for r in rows if r[6] == "À_CLASSER")
    log(f"[matcher_v4] {len(rows)} lignes → {OUT_TSV}")
    log(f"[matcher_v4] proposées={len(rows)-a_classer} (DÉDUIT) / à_classer={a_classer}")
    log(f"[matcher_v4] par niveau : {stats['par_niveau']}")
    log(f"[matcher_v4] conflits tranchés par la hiérarchie : {stats['conflits_tranches_par_hierarchie']}")

    # Assertion NOMMÉE, pas un espoir — jtg doit gagner GiftsListMessage sur kmz (v3 §3).
    jtg = graines.get("jtg")
    if jtg and jtg[0] == "GiftsListMessage" and jtg[1] == "capture_verifiee":
        log("[matcher_v4] ✅ jtg→GiftsListMessage gagne bien (capture_verifiee), kmz rétrogradé.")
    else:
        log(f"[matcher_v4] ❌ ATTENDU jtg→GiftsListMessage(capture_verifiee), OBTENU {jtg}")

    obf_records = load_jsonl(SIG_OBF_PATH)
    obf_index = {o["obf_name"]: o for o in obf_records if o["depth"] == 0}
    edges = load_edges(ARETES_PATH)
    chemin_ops = charge_chemin_critique(CHEMIN_CRITIQUE_PATH)
    a_nommer = ecrire_a_nommer(graines, obf_index, edges, chemin_ops)
    non_nommes_chemin = sum(1 for r in a_nommer if r[2] == "chemin_critique")
    log(f"[matcher_v4] {non_nommes_chemin}/{len(chemin_ops)} opcodes du chemin critique restent "
        f"À NOMMER PAR CAPTURE ; {len(a_nommer)} lignes → {OUT_A_NOMMER}")


if __name__ == "__main__":
    main()
