#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Charge les NOMS SÉMANTIQUES et les DIRECTIONS proposés pour les opcodes
    obfusqués, depuis les instruments tiers déjà indexés par le chantier, et les
    fusionne SANS jamais trancher un conflit en silence.
    / Loads semantic names and directions from the third-party instruments and
    merges them, never resolving a conflict silently.

POURQUOI (05/09/2026) : loi L6 — l'opcode 3 lettres est re-brassé à chaque build,
    donc il ne peut PAS être la clé contre laquelle un handler est écrit. La clé
    stable est le NOM SÉMANTIQUE. Mais aucun nom n'est lisible dans notre binaire :
    le matcher v3 a mesuré 0/2206 classes obfusquées avec un porteur en clair
    (`tools/protocol-mapping/matcher/RAPPORT-MATCHER-V3.md` §2). Les noms viennent donc
    tous d'un TIERS, et la seule chose honnête est de dire lequel, avec quel degré
    de preuve.
    HIÉRARCHIE À 3 NIVEAUX — c'est exactement celle que l'auteur du matcher a
    demandée sans avoir le temps de la construire (RAPPORT-MATCHER-V3.md §3 et §5 :
    « une hiérarchie de priorité à 3 niveaux (capture vérifiée > structure v2 >
    proposition Jondo seule) reste à construire ») :
       1. `jondo-anclas` — nom attesté par les 242 captures de Jondo (en-tête du
          fichier : « el SIGNIFICADO está medido »). Le plus fort.
       2. `matcher-v3`  — nom proposé par appariement STRUCTUREL sur notre dump.
       3. `messages-jondo` — proposition sans attestation propre.
    Le cas nommé par le matcher (`jtg`→GiftsListMessage écrasé à tort par
    `kmz`) se résout tout seul sous cette hiérarchie : `jtg` vient des anclas et
    passe devant. Le perdant n'est pas effacé, il est rendu dans `conflits`.

COMMENT LANCER : module, pas exécutable.
    from _lib_noms import charger_noms
    n = charger_noms()          # chemins par défaut du chantier
    n.pour("jru")               # -> Nom(nom_semantique=…, statut=…, provenance=…)

GATE : éprouvé par `gate-proto-sync.py --epreuve`, témoins (c) provenance/statut
    sur chaque entrée et (f) opcode inventé absent.
"""

import os
import re
from dataclasses import dataclass, field as _dc_field
from typing import Dict, List, Optional

# Racine du chantier, déduite de l'emplacement de ce fichier (protocol/extract/proto-sync/).
RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Sources, dans l'ordre de PRIORITÉ décroissante. Chacune dit ce qu'elle prouve.
#   (cle, chemin, statut_attribue, detail)
SOURCES_DEFAUT = [
    ("jondo-anclas", "refs/JondoEmu/datos/anclas_3.6.10.10.tsv", "VERIFIE",
     "nom attesté par les 242 captures de JondoEmu sur la build 3.6.10.10 "
     "(en-tête du fichier) ; l'existence du token comme classe est, elle, "
     "re-mesurée dans NOTRE dump"),
    ("matcher-v3", os.path.join(RACINE, "tools/protocol-mapping/matcher/correspondance-v3.tsv"), "DEDUIT",
     "appariement STRUCTUREL sur notre dump (forme + champs + voisinage), "
     "jamais une preuve — cf. RAPPORT-MATCHER-V3.md"),
    ("messages-jondo", os.path.join(RACINE, "tools/protocol-mapping/index/messages-jondo.tsv"), "DEDUIT",
     "proposition portée par l'index, sans attestation propre"),
]
# Directions : même fichier d'anclas, plus l'index des handlers qui en dérive.
SOURCE_HANDLERS = os.path.join(RACINE, "tools/protocol-mapping/index/handlers-jondo.tsv")

_RE_OPCODE = re.compile(r"^[a-z]{3}$")   # forme mesurée de l'opcode 3.x : 3 minuscules


@dataclass
class Nom:
    """Ce qu'on sait du nom d'un opcode, et d'où on le sait. / What is known about an opcode's name, and from where."""
    opcode: str
    nom_semantique: str = ""
    statut: str = "SANS_NOM"            # VERIFIE | DEDUIT | SANS_NOM
    provenance: str = ""                # <source>:<fichier>:<ligne>
    detail: str = ""                    # ce que la source prouve exactement
    direction: str = "INCONNUE"         # C2S | S2C | INCONNUE
    direction_provenance: str = ""
    conflits: List[dict] = _dc_field(default_factory=list)


class Noms:
    """Table opcode -> Nom, plus les collisions de nom sémantique entre opcodes.
    / opcode -> Nom table, plus semantic-name collisions between opcodes."""

    def __init__(self):
        # Trois vues sur la même fusion : la table, ce qu'on a lu pour la bâtir, et ce
        # qu'on a REFUSÉ de trancher. / Table, what was read to build it, what was refused.
        self.par_opcode: Dict[str, Nom] = {}
        self.sources_lues: List[dict] = []
        self.collisions: List[dict] = []

    def pour(self, opcode: str) -> Nom:
        """Rend ce qu'on sait de cet opcode, ou une entrée SANS_NOM — jamais None, jamais une invention.
        / Returns what is known, or a SANS_NOM entry; never None, never invented."""
        return self.par_opcode.get(opcode) or Nom(opcode=opcode)


def _lire_tsv(chemin: str):
    """Lit un TSV à en-tête, en sautant les lignes de commentaire `#`. / Reads a headered TSV, skipping `#` lines."""
    if not os.path.exists(chemin):
        return None, []
    lignes = []
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        for no, l in enumerate(fh, 1):
            if l.startswith("#") or not l.strip():
                continue
            lignes.append((no, l.rstrip("\n").split("\t")))
    if not lignes:
        return None, []
    return lignes[0][1], lignes[1:]


def _lire_anclas(chemin: str):
    """anclas_*.tsv de Jondo : SANS en-tête, colonnes fixes (opcode, direction, nom, …).
    / Jondo's anclas table has no header row: fixed columns."""
    if not os.path.exists(chemin):
        return []
    out = []
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        for no, l in enumerate(fh, 1):
            if l.startswith("#") or not l.strip():
                continue
            col = l.rstrip("\n").split("\t")
            if len(col) < 3 or not _RE_OPCODE.match(col[0]):
                continue
            out.append((no, col[0], col[1].strip(), col[2].strip()))
    return out


def charger_noms(sources=None, source_handlers=SOURCE_HANDLERS) -> Noms:
    """Fusionne les instruments par priorité décroissante ; tout écart devient un conflit RENDU.
    / Merges instruments by decreasing priority; every disagreement is reported, not resolved away."""
    n = Noms()
    for cle, chemin, statut, detail in (sources or SOURCES_DEFAUT):
        present = os.path.exists(chemin)
        lues = 0
        if present:
            lues = _fusionner(n, cle, chemin, statut, detail)
        n.sources_lues.append({"source": cle, "chemin": chemin, "present": present,
                               "entrees_retenues": lues, "statut_attribue": statut})
    _charger_directions(n, source_handlers)
    _reperer_collisions(n)
    return n


def _fusionner(n: Noms, cle: str, chemin: str, statut: str, detail: str) -> int:
    """Verse une source ; la première qui nomme un opcode gagne, les suivantes deviennent conflits.
    / Pours one source in; first to name an opcode wins, later ones become recorded conflicts."""
    paires = []
    if cle == "jondo-anclas":
        for no, op, direction, nom in _lire_anclas(chemin):
            if nom:
                paires.append((op, nom, no, {"direction": direction}))
    else:
        entete, lignes = _lire_tsv(chemin)
        if entete is None:
            return 0
        idx = {c: i for i, c in enumerate(entete)}
        col_op = next((idx[c] for c in ("classe_obf", "message_nom") if c in idx), None)
        col_nom = next((idx[c] for c in ("nom_clair", "nom_propose") if c in idx), None)
        col_st = idx.get("statut")
        if col_op is None or col_nom is None:
            return 0
        for no, col in lignes:
            if len(col) <= max(col_op, col_nom):
                continue
            op, nom = col[col_op].strip(), col[col_nom].strip()
            if not op or not nom or not _RE_OPCODE.match(op):
                continue
            if col_st is not None and len(col) > col_st and col[col_st].strip() == "À_CLASSER":
                continue          # le matcher dit lui-même qu'il n'a pas tranché : on ne tranche pas pour lui
            paires.append((op, nom, no, {}))
    retenues = 0
    for op, nom, no, extra in paires:
        prov = "%s:%s:%d" % (cle, chemin, no)
        courant = n.par_opcode.get(op)
        if courant is None:
            e = Nom(opcode=op, nom_semantique=nom, statut=statut, provenance=prov, detail=detail)
            if extra.get("direction") in ("C2S", "S2C"):
                e.direction, e.direction_provenance = extra["direction"], prov
            n.par_opcode[op] = e
            retenues += 1
        elif courant.nom_semantique != nom:
            courant.conflits.append({"nom_ecarte": nom, "source": cle, "provenance": prov,
                                     "raison": "source de priorité inférieure, nom différent"})
    return retenues


def _charger_directions(n: Noms, chemin: str) -> None:
    """Complète la direction C2S/S2C depuis l'index des handlers. La direction est portée
    par l'ARÊTE, jamais déduite du nom : un handler qui confond envoi et réception marche
    une fois sur deux (cahier §2, design du graphe).
    / Fills direction from the handler index; never inferred from the name."""
    entete, lignes = _lire_tsv(chemin)
    if entete is None:
        return
    idx = {c: i for i, c in enumerate(entete)}
    if "protocol_id" not in idx or "direction" not in idx:
        return
    for no, col in lignes:
        if len(col) <= max(idx["protocol_id"], idx["direction"]):
            continue
        op, dirn = col[idx["protocol_id"]].strip(), col[idx["direction"]].strip()
        if not _RE_OPCODE.match(op) or dirn not in ("C2S", "S2C"):
            continue
        e = n.par_opcode.setdefault(op, Nom(opcode=op))
        if e.direction == "INCONNUE":
            e.direction = dirn
            e.direction_provenance = "jondo-handlers:%s:%d" % (chemin, no)
        elif e.direction != dirn:
            e.conflits.append({"direction_ecartee": dirn, "source": "jondo-handlers",
                               "provenance": "%s:%d" % (chemin, no),
                               "raison": "direction contradictoire entre instruments"})


def _reperer_collisions(n: Noms) -> None:
    """Deux opcodes qui revendiquent le MÊME nom sémantique cassent la clé stable des handlers :
    `table[nom]` cesserait d'être une fonction. On tranche par la hiérarchie quand elle
    départage, et on REFUSE de trancher quand elle ne départage pas — un nom retiré aux
    deux vaut mieux qu'un nom donné au hasard à l'un des deux.
    / Two opcodes claiming one semantic name break the handler key. Resolved by the
    hierarchy when it separates them; refused for everyone when it does not."""
    rang = {"VERIFIE": 0, "DEDUIT": 1, "SANS_NOM": 2}
    par_nom: Dict[str, List[str]] = {}
    for op, e in n.par_opcode.items():
        if e.nom_semantique:
            par_nom.setdefault(e.nom_semantique, []).append(op)
    for nom, ops in sorted(par_nom.items()):
        if len(ops) < 2:
            continue
        ops = sorted(ops)
        meilleur = min(rang[n.par_opcode[o].statut] for o in ops)
        tete = [o for o in ops if rang[n.par_opcode[o].statut] == meilleur]
        garde = tete[0] if len(tete) == 1 else None
        for o in ops:
            if o == garde:
                continue
            e = n.par_opcode[o]
            raison = ("nom retiré : conflit tranché par la hiérarchie au profit de « %s » (%s)" % (
                garde, n.par_opcode[garde].statut)) if garde else (
                "nom retiré aux %d revendicateurs : même rang (%s), la hiérarchie ne départage pas"
                % (len(tete), n.par_opcode[o].statut))
            e.conflits.append({"nom_ecarte": nom, "source": e.provenance.split(":")[0],
                               "provenance": e.provenance, "raison": raison})
            e.nom_semantique, e.statut, e.detail = "", "SANS_NOM", raison
        n.collisions.append({"nom_semantique": nom, "opcodes": ops,
                             "retenu": garde or "", "tranche": bool(garde)})
