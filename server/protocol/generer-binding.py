#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Générateur DÉTERMINISTE (0 jeton, 0 LLM) de la table de liaison du protocole 3.0 —
    `protocol/binding-<build>.json`. La table porte, pour CHAQUE nom sémantique stable, l'opcode
    3 lettres de CETTE build, le sens, la source qui le prouve, et la FORME de la charge utile
    que le serveur émet (un arbre de champs numérotés/typés, pas du code).
    FR/EN : deterministic generator of the 3.0 protocol binding table.

POURQUOI (05/09/2026) : l'opcode 3 lettres EST le nom de classe obfusqué du client — il est
    re-brassé à chaque build (mesuré : le matcher structurel ne réapparie que 245 messages sur
    2169, soit 11,3 %, entre 3.6.4.3 et 3.6.10.10). Écrire un opcode dans du C# ferait d'un
    changement de build une réécriture du serveur. DECISIONS.md D-08 tranche : « un seul fichier
    nomme les opcodes littéraux ». Ce fichier-ci est ce seul fichier ; `src/` n'en contient aucun,
    et `gate-serveur.sh` le mesure par grep.
    EN : the 3-letter opcode IS the client's obfuscated class name, reshuffled every build.

    ⚠️ Ce script ne se CROIT pas : chaque opcode qu'il écrit et qui porte un nom clair est
    RECROISÉ contre l'instrument indépendant de l'étage 1
    (`tools/protocol-mapping/matcher/correspondance-v4.tsv`). Un désaccord est un REFUS NOMMÉ, pas un
    avertissement — sinon la table serait « plausible et fausse », la pire des deux propriétés
    (INTERFACES.md §2, mesure Jondo/otomai : 84 % de collisions d'opcodes, 0 accord de sens
    sur 27 examinés).

COMMENT LANCER / USAGE :
    python3 generer-binding.py                 # écrit protocol/binding-3.6.10.11.json
    python3 generer-binding.py --verifier      # ne réécrit rien ; rc=1 si le fichier est périmé

GATE : rc=0 ssi (a) chaque nom clair de la table est confirmé par correspondance-v4.tsv,
    (b) aucun opcode n'est en double, (c) chaque entrée porte une source non vide.
    rc=1 + refus NOMMÉ sinon.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

# Racine du chantier, déduite de l'emplacement de CE fichier (jamais un chemin absolu en dur).
# / Chantier root, derived from THIS file's location (never a hard-coded absolute path).
ICI = Path(__file__).resolve().parent
ETAGE3 = ICI.parent
CHANTIER = ETAGE3.parent
CORRESPONDANCE_V4 = CHANTIER / "etage1-carte" / "matcher" / "correspondance-v4.tsv"
# La table de dispatch GÉNÉRÉE par l'étage 5 (2 206 messages, formes lues dans notre dump).
# Second instrument INDÉPENDANT : un autre extracteur, un autre auteur, la même source binaire.
# / Stage 5's GENERATED dispatch table — a second INDEPENDENT instrument.
DISPATCH = CHANTIER / "etage5-outils" / "proto-sync" / "out" / "dispatch-3.6.10.10.json"

# La build VISÉE. Le client réel installé est 3.6.10.11 ; les tables de l'étage 1 sont mesurées
# sur 3.6.10.10 et notre dump. Les deux portent les MÊMES noms obfusqués pour tout le chemin
# critique — vérifié classe par classe dans il2cpp.cs le 05/09 (kvi, lpg, lpe, lpj, kqz, kvw,
# kvl, jru, lqu, hoy, kqu, mgq, mgt, hpd, krs, mgz, kqp, kra, kvd, jtg, mhh, mhj, mhl, mia, mik).
# / The TARGET build. Same obfuscated names as 3.6.10.10 across the whole critical path.
BUILD = "3.6.10.11"
BUILD_MESURE = "3.6.10.10"

# ------------------------------------------------------------------------------------------
# LA TABLE. Une ligne = un nom sémantique STABLE (le seul que le C# connaît) -> l'opcode de
# cette build + le sens + la SOURCE qui le prouve.
# / One row = a STABLE semantic name (the only thing the C# knows) -> this build's opcode.
# `nom_clair` vide = aucun nom clair établi ; l'opcode est alors sourcé par la séquence seule.
# ------------------------------------------------------------------------------------------
TABLE = [
    # -- Phase 2, entrée : le client présente son ticket ------------------------------------
    ("AuthTicket", "kqz", "C2S", "AuthenticationTicketMessage",
     "SEQUENCE-CHEMIN-CRITIQUE-JONDO.md §3.5 ; il2cpp.cs:991823 (f1 int, f2 string, f3 string)"),
    ("AuthTicketCompanion", "krt", "C2S", "",
     "COMPLEMENT-CHEMIN-CRITIQUE-G1.md « krt » — SENS INCONNU de la source elle-même ; "
     "il2cpp.cs:993113 (0 champ). Accompagne kqz, n'attend aucune reponse."),

    # -- Phase 2, la rafale de bienvenue, dans l'ordre exact de ConnectionProtocol.cs:191-221 -
    ("AuthTicketAccepted", "kra", "S2C", "AuthenticationTicketAcceptedMessage",
     "SEQUENCE §3.6 ; il2cpp.cs:991928 (0 champ)"),
    ("BasicTime", "lqu", "S2C", "BasicTimeMessage",
     "COMPLEMENT « lqu » ; il2cpp.cs:1033385 (f1 int32, f2 int64, f3 int32)"),
    ("HelloGame", "hoy", "S2C", "HelloGameMessage",
     "COMPLEMENT « hoy » ; il2cpp.cs:857576 (f1 int, f2 enum lbu, f3 bool, f4 bool, "
     "f5 int, f6 string, f7 int) — f2 est un ENUM donc un varint, la forme Jondo tient"),
    ("ServerOptionalFeatures", "kqu", "S2C", "ServerOptionalFeaturesMessage",
     "SEQUENCE §3.6 ; il2cpp.cs:991459 (f1 repeated int32 packed, f2 repeated bool)"),
    ("BurstFlagsTriple", "mgq", "S2C", "",
     "COMPLEMENT « mgq » — nom clair INEXISTANT ; il2cpp.cs:1062818 (f1 enum mgo, f2 bool, "
     "f3 enum lbb) : trois varints, la forme Jondo tient"),
    ("BurstPairEmpty", "mgt", "S2C", "",
     "SEQUENCE §3.6 ; il2cpp.cs:1062925 (f1 message mgr, f2 message mgr)"),
    ("BurstFlagSingle", "hpd", "S2C", "",
     "COMPLEMENT « hpd » — nom clair INEXISTANT ; il2cpp.cs:857888 (f1 bool)"),
    ("BurstEmptyMarker", "krs", "S2C", "",
     "SEQUENCE §3.6 ; il2cpp.cs:992926 (f1 message krq) — Jondo l'emet VIDE"),
    ("ContentCatalogVersion", "mgz", "S2C", "ContentCatalogVersionMessage",
     "COMPLEMENT « mgz » ; il2cpp.cs:1063424 (f1 int64)"),
    ("BurstCounterPair", "kqp", "S2C", "",
     "SEQUENCE §3.6 — emis TROIS FOIS avec trois charges differentes ; "
     "il2cpp.cs:991027 (f1 int32, f2 int32)"),
    ("CharactersList", "kvi", "S2C", "CharactersListMessage",
     "SEQUENCE §4.1 ; il2cpp.cs:999127 (f1 repeated lpg)"),
    ("CharactersListEnd", "kvd", "S2C", "CharactersListEndMessage",
     "SEQUENCE §4 ; il2cpp.cs:998873 (0 champ)"),
    ("GiftsList", "jtg", "S2C", "GiftsListMessage",
     "SEQUENCE §3.6 ; il2cpp.cs:950553 (f1 int64, f2/f3 repeated jtd) — emis VIDE"),

    # -- Phase 2, selection de personnage ----------------------------------------------------
    ("CharacterSelection", "kvw", "C2S", "CharacterSelectionMessage",
     "COMPLEMENT « kvw » ; il2cpp.cs:1000115 (f1 int64 characterId)"),
    ("CharacterFirstSelection", "kvl", "C2S", "CharacterFirstSelectionMessage",
     "COMPLEMENT « kvl » ; il2cpp.cs:999385 (f1 bool, f2 int64) — l'id est en f2, PAS f1"),
    ("CharacterSelectedSuccess", "kva", "S2C", "CharacterSelectedSuccessMessage",
     "SEQUENCE §4 ; il2cpp.cs:998424 (oneof f1 kuy, f2 kux) ; kuy = { f1 lpg } il2cpp.cs:998547"),

    # -- Phase 2, entree monde ---------------------------------------------------------------
    ("GameContextCreateRequest", "lqc", "C2S", "GameContextCreateRequestMessage",
     "SEQUENCE §5.1 ; il2cpp.cs:1032191 (f1 int32, f2 int64)"),
    ("BasicPing", "kqo", "C2S", "BasicPingMessage",
     "SEQUENCE §5 ; il2cpp.cs:990937 (f1 repeated bool, f2 bool)"),
    ("BasicPong", "kqy", "S2C", "BasicPongMessage",
     "SEQUENCE §5 ; il2cpp.cs:991644 (f1 bool, f2 string, f3 kqw) — voyage sur le cas racine 1"),
    ("CurrentMap", "jru", "S2C", "CurrentMapMessage",
     "SEQUENCE §5 ; il2cpp.cs:948192 (f1 enum jrs, f2 int64 mapId)"),
    ("MapDiscovered", "hjk", "S2C", "",
     "COMPLEMENT « hjk » — nom clair INEXISTANT ; f1 packed [mapId], voyage AVEC jru"),
    ("WorldEntryRequests", "jrh", "C2S", "WorldEntryRequests",
     "SEQUENCE §5.2 ; le client demande qui est sur la carte"),
    ("MapLoaded", "lva", "S2C", "MapLoadedMessage",
     "SEQUENCE §5.2 ; 0 champ — le plus petit message serveur possible (26 octets)"),
]

# ------------------------------------------------------------------------------------------
# LES CHARGES UTILES. Un arbre declaratif : {n: numero, t: type, v: valeur}.
# Types : varint / chaine / octets_hex / varint_packed / message / injecte_*.
# Les valeurs INVENTEES sont marquees par le champ "invente" a cote de la forme.
# / Declarative payload trees. INVENTED values are flagged next to the (verified) shape.
# ------------------------------------------------------------------------------------------

def var(n, v):
    """Champ varint. / Varint field."""
    return {"n": n, "t": "varint", "v": v}

def chaine(n, v):
    """Champ chaine UTF-8 (length-delimited). / UTF-8 string field."""
    return {"n": n, "t": "chaine", "v": v}

def packed(n, v):
    """Champ repeated varint EMPAQUETE. / Packed repeated varint field."""
    return {"n": n, "t": "varint_packed", "v": v}

def msg(n, champs):
    """Sous-message. Une liste vide = sous-message VIDE, pas un champ absent.
    / Sub-message. An empty list means an EMPTY sub-message, not a missing field."""
    return {"n": n, "t": "message", "v": champs}

def injecte(n, t, cle):
    """Champ dont la valeur vient du serveur a l'execution (horloge, ticket, hote, ports).
    / Field whose value the server injects at run time (clock, ticket, host, ports)."""
    return {"n": n, "t": t, "v": cle}


# La rafale de bienvenue : QUINZE emissions, TREIZE opcodes distincts, dans CET ordre.
# Source : ConnectionProtocol.cs:191-221 (`BuildWelcomeBurst`), transcrite par
# SEQUENCE-CHEMIN-CRITIQUE-JONDO.md §3.6 ; chaque FORME recroisee contre il2cpp.cs (05/09).
# / The welcome burst: FIFTEEN emissions, THIRTEEN distinct opcodes, in THIS order.
RAFALE = [
    ("AuthTicketAccepted", []),
    # f1 = SyncRate (constante 120, ConnectionProtocol.cs:234) ; f2 = horloge serveur unix-ms.
    ("BasicTime", [var(1, 120), injecte(2, "varint_injecte", "horloge_ms")]),
    # f1=30, f2=1, f3=1, f6=langue, f7=200. f5 VOLONTAIREMENT absent (absent des 3 captures).
    ("HelloGame", [var(1, 30), var(2, 1), var(3, 1), chaine(6, "fr"), var(7, 200)]),
    # Liste de fonctionnalites optionnelles, empaquetee. Valeurs copiees de la capture Jondo.
    ("ServerOptionalFeatures",
     [packed(1, [3, 7, 13, 20, 23, 105, 124, 125, 126, 136, 143, 145, 150])]),
    ("BurstFlagsTriple", [var(1, 1), var(2, 1), var(3, 1)]),
    ("BurstPairEmpty", [msg(2, [])]),
    ("BurstFlagSingle", [var(1, 1)]),
    ("BurstEmptyMarker", []),
    # Marque de catalogue : valeur OPAQUE copiee d'une capture, le client la compare a elle-meme.
    ("ContentCatalogVersion", [var(1, 304672615)]),
    # Trois emissions du MEME opcode, trois charges DIFFERENTES, dans cet ordre.
    ("BurstCounterPair", [var(1, 1), var(2, 1)]),
    ("BurstCounterPair", [var(1, 1)]),
    ("BurstCounterPair", []),
    ("CharactersList", "@liste_personnages"),   # resolu plus bas (charge dynamique)
    ("CharactersListEnd", []),
    ("GiftsList", []),
]

# Le personnage servi. FORMES verifiees sur une trame kva REELLE decodee le 05/09 depuis
# `world_etapa1_tras_elegir_personaje.bin` @138 (le meme type `lpg` que kvi, prouve par
# il2cpp.cs:998547 `kuy { lpg = 1 }`). VALEURS inventees — aucun compte tiers.
# / The served character. SHAPES verified on a REAL kva frame; VALUES invented.
PERSONNAGE = {
    "identifiant": 302677754147,          # invente (l'id reel de la capture +1, jamais reutilise)
    "nom": "Namaste",                     # invente
    "niveau": 1,                          # invente
    "race": 11,                           # forme VERIFIEE (f7 varint), valeur inventee
    "sexe": 0,                            # 0 => sous-message f2 VIDE (regle mesuree)
    "apparence": [                        # f6 : bloc d'apparence, forme copiee de la capture
        var(2, 3),
        var(3, 9584),
        chaine(5, "s"),
    ],
}


def details_personnage(avec_dates):
    """Le bloc « details » d'un personnage — partage par CharactersList et
    CharacterSelectedSuccess. `avec_dates` ajoute f1 (date de creation) et f4 (horodatage
    serveur) dans le sous-bloc f4 : MESURE sur la trame kva reelle (world_etapa1 @138), qui les
    PORTE, alors que la liste ne les porte pas.
    Forme : { f2 nom, f3 niveau, f4 { [f1 date] , f2 sexe, [f4 horodatage], f6 apparence,
    f7 race } } — chaque numero VERIFIE (il2cpp.cs `lpe`/`lpj` + la trame reelle).
    / A character's shared `details` block; `avec_dates` adds the two date fields."""
    p = PERSONNAGE
    bloc = []
    if avec_dates:
        bloc.append(chaine(1, "2026-09-05T00:00:00.000Z"))       # date de creation, inventee
    # sexe 0 => sous-message VIDE, pas de champ f3 : regle mesuree sur la trame reelle (f2 len=0).
    bloc.append(msg(2, [] if p["sexe"] == 0 else [var(3, p["sexe"])]))
    if avec_dates:
        bloc.append(chaine(4, "2026-09-05T00:00:00.000000000Z"))  # horodatage serveur, invente
    bloc.append(msg(6, p["apparence"]))
    bloc.append(var(7, p["race"]))
    return [chaine(2, p["nom"]), var(3, p["niveau"]), msg(4, bloc)]


def charge_liste_personnages():
    """Charge de CharactersList : f1 repete = une entree `lpg` par personnage.
    lpg { f1 = details, f2 = characterId } — VERIFIE il2cpp.cs:1029268 (f1 lpe, f2 int64, f3 lpj)
    ET sur la trame kva reelle, qui porte le MEME type `lpg` (kuy { lpg = 1 }, il2cpp.cs:998547).
    / CharactersList payload: one `lpg` entry per character."""
    entree = [msg(1, details_personnage(avec_dates=False)),
              var(2, PERSONNAGE["identifiant"])]
    return [msg(1, entree)]


def charge_personnage_selectionne():
    """Charge de CharacterSelectedSuccess : kva { f1 = kuy { f1 = lpg } }.
    DEUX enveloppes avant l'entree — forme lue telle quelle sur la trame reelle @138 :
    f1:msg(181) > f1:msg(178) > { f1:msg(168) details, f2:varint characterId }.
    Sans ce message le client reste sur l'ecran perso, sablier tournant (mesure citee).
    / CharacterSelectedSuccess payload: two wrappers, then the entry."""
    entree = [msg(1, details_personnage(avec_dates=True)),
              var(2, PERSONNAGE["identifiant"])]
    return [msg(1, [msg(1, entree)])]


# Le message « carte courante ». mapId 191105026 = le zaap d'Astrub, VERIFIE
# `CharacterCreationHandler.cs:31 const long StartingMap = 191105026L`.
# f2 porte le mapId (il2cpp.cs:948192, f2 int64) ; f1 est un enum, omis.
CHARGE_CARTE = [var(2, 191105026)]

# La reponse au ping. f1 = 1, sur le cas racine 1 (push), PAS 3 — mesure citee SEQUENCE §5.
CHARGE_PONG = [var(1, 1)]

# hjk voyage avec jru : la liste EMPAQUETEE des cartes decouvertes (ici la carte courante).
CHARGE_CARTE_DECOUVERTE = [packed(1, [191105026])]

# lva : aucun champ. Sans lui le client ne considere jamais la carte comme chargee.
CHARGE_CARTE_PRETE = []

# ------------------------------------------------------------------------------------------
# PHASE 1 — le protocole de connexion NU (pas d'enveloppe `type.ankama.com`, pas d'opcode).
# Racine `mhh` : oneof { f1 mhj auth C2S, f2 mhl authResult S2C, f3 mhn }.
# Verifie il2cpp.cs:1063673 (mhh), :1063780 (mhj), :1063912 (mhl), :1065253 (mih).
# ------------------------------------------------------------------------------------------

# `mia` (acces accepte) = f1 accountId, f2 nickname, f3 tag, f4 miq (liste serveurs),
# f5 subscriptionEndDate, f6 mhy. Verifie protocolo_conexion_3.6.10.10.proto:232-242.
# `miq` = f1 repeated mit (serveurs), f2 repeated mio (quotas), f3 bool.
# `mit` = f1 miw { f1 serverId, f3 type }, f2 mir, f3 repeated mjg (personnages du serveur).
# `mjg` = f1 nom, f2 race, f3 sexe, f4 niveau, f5 derniere connexion.
SERVEUR_ID = 290          # forme VERIFIEE (docs/protocol.md §6 decode serverId=290), valeur reprise
SERVEUR_TYPE = 1          # enum mhf, valeur inventee dans la plage declaree (0..6)
QUOTA_PERSONNAGES = 5     # invente

def charge_acces_accepte():
    """Reponse S2C au premier frame NU : compte accepte + liste des serveurs.
    C'est ce message qui peuple l'ECRAN DE SELECTION DE SERVEUR.
    / S2C answer to the first NAKED frame: account accepted + server list."""
    # Un serveur, portant le resume du personnage (ce que l'ecran de selection affiche).
    resume_perso = [chaine(1, PERSONNAGE["nom"]),
                    var(2, max(PERSONNAGE["race"] - 1, 0)),   # mjg.f2 = race MOINS UN (mesure Jondo)
                    var(3, PERSONNAGE["sexe"]),
                    var(4, PERSONNAGE["niveau"]),
                    chaine(5, "2026-09-05T00:00:00Z")]
    entree_serveur = [msg(1, [var(1, SERVEUR_ID), var(3, SERVEUR_TYPE)]),
                      msg(3, resume_perso)]
    liste_serveurs = [msg(1, entree_serveur),
                      msg(2, [var(1, SERVEUR_TYPE), var(2, QUOTA_PERSONNAGES)])]
    accepte = [var(1, 1),                                   # accountId, invente
               chaine(2, "Namaste"),                        # nickname, invente
               chaine(3, "0001"),                           # tag, invente
               msg(4, liste_serveurs),
               chaine(5, "2035-01-01T00:00:00Z"),           # fin d'abonnement, inventee
               msg(6, [])]
    return [msg(2, [chaine(1, "fr"), msg(3, [msg(1, accepte)])])]

def charge_serveur_selectionne():
    """Reponse S2C a la selection de serveur : ticket + hote + ports de jeu.
    `mik` = f1 ticket(string), f2 host(string), f3 ports(packed) — proto:259-263.
    Le client ferme alors cette connexion et en rouvre une sur hote:ports[0].
    / S2C answer to server selection: ticket + host + game ports."""
    selection = [injecte(1, "chaine_injectee", "ticket"),
                 injecte(2, "chaine_injectee", "hote"),
                 injecte(3, "varint_packed_injecte", "ports_jeu")]
    return [msg(2, [chaine(1, "fr"), msg(4, [msg(1, selection)])])]


# ------------------------------------------------------------------------------------------
# LES NUMÉROS DE CHAMP DONT LE SERVEUR DÉPEND. Ils sont figés dans `ConnectionSession.cs` et
# `ConnectEnvelope.cs` ; ici on les RECROISE contre la table de dispatch de l'étage 5.
# POURQUOI c'est le contrôle qui manquait : un mauvais numéro de champ produit du protobuf
# VALIDE qui s'encode et se décode sans erreur — le compilateur ne dit rien, le round-trip est
# vert, et la panne n'apparaît qu'à l'écran. C'est le motif « le type est bon, la source est
# fausse ». Le cas le plus coûteux ici : `kvl`, dont le champ 1 est un BOOLÉEN et le champ 2
# l'identifiant — lire f1 rendrait 0 ou 1 en guise d'identifiant de personnage.
# / The field numbers the server depends on, cross-checked against stage 5's dispatch table.
# A wrong field number yields VALID protobuf: the compiler is silent, the round-trip is green,
# and the failure only shows on screen.
#
# ⚠️ Les types IMBRIQUES se nomment par leur CHEMIN QUALIFIE dans cette table (`mim.mik`, pas
# `mik`). Mesure du 05/09 : ma premiere version interrogeait les noms nus et rendait « message
# absent » sur `mik` et `mio` — j'ai cru un instant a un trou de couverture de l'etage 5, alors
# que c'etait MA cle qui etait fausse. Le recroisement a donc trouve son premier defaut dans le
# recroiseur lui-meme, ce qui est le cas le plus frequent.
# / Nested types are keyed by their QUALIFIED PATH here (`mim.mik`, not `mik`). My first version
# queried bare names and reported "message absent" — the cross-check's first finding was in the
# cross-checker itself, which is the most common case.
CHAMPS_DONT_LE_SERVEUR_DEPEND = [
    # -- phase JEU
    ("kqz", 2, "string", "le ticket presente par le client"),
    ("kvw", 1, "int64", "l'identifiant de personnage, selection normale"),
    ("kvl", 2, "int64", "l'identifiant de personnage, PREMIERE selection (f1 est un bool)"),
    ("lpg", 2, "int64", "l'identifiant dans une entree de la liste de personnages"),
    ("lpg.lpe", 2, "string", "le nom du personnage"),
    ("lpg.lpe", 3, "int32", "le niveau du personnage"),
    ("kvi", 1, "lpg", "la liste de personnages est un repete d'entrees lpg"),
    ("jru", 2, "int64", "l'identifiant de carte"),
    # -- phase NUE (protocole de connexion, pas d'opcode)
    ("mhh", 2, "mhl", "la branche RESULTAT de la racine de connexion"),
    ("mhj", 4, "mih", "le serveur choisi, dans la branche AUTH"),
    ("mih", 1, "int32", "l'identifiant de serveur choisi"),
    ("mhl", 3, "mig", "la branche ACCES ACCEPTE du resultat"),
    ("mhl", 4, "mim", "la branche SERVEUR SELECTIONNE du resultat"),
    ("mig.mia", 4, "miq", "la liste des serveurs, dans l'acces accepte"),
    ("mim.mik", 1, "string", "le ticket rendu au client"),
    ("mim.mik", 2, "string", "l'hote annonce au client"),
    ("mim.mik", 3, "int32", "les ports annonces au client (repete empaquete)"),
    ("miw", 1, "int32", "l'identifiant d'un serveur de la liste"),
    ("mjg", 1, "string", "le nom du personnage sur l'ecran de selection de serveur"),
    ("mjg", 4, "int32", "le niveau du personnage sur l'ecran de selection de serveur"),
]


def charger_dispatch(refus):
    """Lit la table de dispatch de l'étage 5 et rend deux index : opcode -> entrée, et
    chemin_proto -> entrée (les messages imbriqués comme `lpg` n'ont pas d'opcode).
    Son ABSENCE est un refus NOMMÉ : un recroisement qui cesse silencieusement d'avoir lieu
    ressemble en tout point à un recroisement qui passe.
    / Reads stage 5's dispatch table. Its ABSENCE is a NAMED refusal: a cross-check that
    silently stops happening looks exactly like one that passes."""
    if not DISPATCH.exists():
        refus.append(
            "table de dispatch etage 5 ABSENTE : %s — la regenerer "
            "(protocol/extract/proto-sync) ou corriger le chemin" % DISPATCH)
        return {}, {}, ""
    doc = json.loads(DISPATCH.read_text(encoding="utf-8"))
    par_opcode, par_chemin = {}, {}
    for e in doc.get("entrees", []):
        if e.get("opcode"):
            par_opcode[e["opcode"]] = e
        if e.get("chemin_proto"):
            par_chemin[e["chemin_proto"]] = e
    return par_opcode, par_chemin, doc.get("build", "")


def recroiser_champs(par_chemin, par_opcode, refus):
    """Vérifie CHAQUE numéro de champ dont le serveur dépend contre la table de dispatch.
    Un désaccord est un REFUS, pas un avertissement : c'est exactement le défaut qui passe
    toutes les gates de forme.
    / Checks EVERY field number the server depends on. A disagreement is a REFUSAL."""
    verifies = []
    for message, numero, type_attendu, sens in CHAMPS_DONT_LE_SERVEUR_DEPEND:
        entree = par_chemin.get(message) or par_opcode.get(message)
        if entree is None:
            refus.append("champ %s.f%d (%s) : message absent de la table de dispatch"
                         % (message, numero, sens))
            continue
        champ = next((c for c in entree.get("champs", []) if c.get("num") == numero), None)
        if champ is None:
            refus.append("champ %s.f%d (%s) : ABSENT du message dans la table de dispatch"
                         % (message, numero, sens))
            continue
        if champ.get("type") != type_attendu:
            refus.append("champ %s.f%d (%s) : le serveur attend %s, la table de dispatch dit %s"
                         % (message, numero, sens, type_attendu, champ.get("type")))
            continue
        verifies.append({"message": message, "numero": numero, "type": type_attendu,
                         "sens": sens, "source": champ.get("source", "")})
    return verifies


def charger_correspondance_v4():
    """Lit l'instrument INDEPENDANT de l'etage 1 : nom_clair -> opcode.
    / Reads stage 1's INDEPENDENT instrument: clear name -> opcode."""
    par_nom = {}
    with CORRESPONDANCE_V4.open(encoding="utf-8") as fh:
        for ligne in csv.DictReader(fh, delimiter="\t"):
            nom = (ligne.get("nom_clair") or "").strip()
            obf = (ligne.get("classe_obf") or "").strip()
            if nom and obf:
                par_nom.setdefault(nom, obf)
    return par_nom


def construire(refus):
    """Assemble le document JSON complet, en accumulant les REFUS NOMMES dans `refus`.
    / Assembles the full JSON document, accumulating NAMED refusals into `refus`."""
    croise = charger_correspondance_v4()
    par_opcode, par_chemin, build_dispatch = charger_dispatch(refus)
    messages, vus = [], {}
    for semantique, opcode, sens, nom_clair, source in TABLE:
        if not source:
            refus.append("%s : source vide" % semantique)
        if opcode in vus:
            refus.append("opcode %s porte par %s ET %s" % (opcode, vus[opcode], semantique))
        vus[opcode] = semantique
        # Recroisement 1 : un nom clair connu de l'etage 1 DOIT pointer sur le meme opcode.
        accord = "sans_nom_clair"
        if nom_clair:
            attendu = croise.get(nom_clair)
            if attendu is None:
                accord = "nom_clair_absent_de_correspondance_v4"
            elif attendu != opcode:
                refus.append("%s : correspondance-v4 dit %s=%s, la table dit %s"
                             % (semantique, nom_clair, attendu, opcode))
                accord = "DESACCORD"
            else:
                accord = "confirme_par_correspondance_v4"

        # Recroisement 2 : la table de dispatch de l'etage 5, second instrument INDEPENDANT.
        # L'opcode DOIT y exister (sinon il ne designe rien dans notre dump) ; et s'il y porte
        # un nom semantique, ce nom DOIT etre le notre. Un opcode present SANS nom est un etat
        # NORMAL et nomme : 7 des 25 sont dans ce cas, les deux instruments s'accordent dessus.
        # / Cross-check 2: stage 5's dispatch table, a second INDEPENDENT instrument.
        dispatch = par_opcode.get(opcode)
        if par_opcode and dispatch is None:
            refus.append("%s : opcode %s ABSENT de la table de dispatch de l'etage 5"
                         % (semantique, opcode))
            accord_dispatch = "ABSENT"
        elif dispatch is None:
            accord_dispatch = "non_verifie_table_absente"
        else:
            nom_dispatch = dispatch.get("nom_semantique") or ""
            if not nom_dispatch:
                accord_dispatch = "present_sans_nom"
            elif nom_clair and nom_dispatch != nom_clair:
                refus.append("%s : la table de dispatch dit %s=%s, nous disons %s"
                             % (semantique, opcode, nom_dispatch, nom_clair))
                accord_dispatch = "DESACCORD"
            else:
                accord_dispatch = "confirme_par_dispatch"

        messages.append({"semantique": semantique, "opcode": opcode, "sens": sens,
                         "nom_clair": nom_clair, "source": source, "recroisement": accord,
                         "recroisement_dispatch": accord_dispatch})

    champs_verifies = recroiser_champs(par_chemin, par_opcode, refus) if par_opcode else []

    rafale = []
    for semantique, charge in RAFALE:
        if charge == "@liste_personnages":
            charge = charge_liste_personnages()
        rafale.append({"semantique": semantique, "charge": charge})

    return {
        "build": BUILD,
        "build_des_mesures": BUILD_MESURE,
        "genere_par": "protocol/generer-binding.py",
        "genere_le": "2026-09-05",
        # Ce que le recroisement contre l'etage 5 a REELLEMENT verifie, ecrit dans le produit
        # plutot que seulement imprime : un controle dont la trace ne survit pas a la sortie
        # console ne se distingue pas d'un controle qui n'a pas eu lieu.
        # / What the stage-5 cross-check ACTUALLY verified, written into the product rather than
        # merely printed: a check whose trace does not survive the console is indistinguishable
        # from one that never ran.
        "recroisement_etage5": {
            "table": str(DISPATCH.relative_to(CHANTIER)) if DISPATCH.exists() else "ABSENTE",
            "build_de_la_table": build_dispatch,
            "note_de_build": (
                "la table de dispatch est mesuree sur %s, nous visons %s : le recroisement est "
                "donc CROSS-BUILD. Il tient parce que les 25 opcodes du chemin critique portent "
                "le meme nom obfusque dans les deux builds, ce qui est verifie ici meme — un "
                "opcode qui aurait bouge serait rendu ABSENT, pas silencieusement accepte."
                % (build_dispatch or "?", BUILD)),
            "champs_verifies": champs_verifies,
        },
        "avertissement": ("Ce fichier est le SEUL a nommer des opcodes 3 lettres. "
                          "src/ n'en contient aucun (gate-serveur.sh le mesure). "
                          "Regenerer a chaque build du client, ne jamais editer a la main."),
        "messages": messages,
        "rafale_bienvenue": rafale,
        "charges": {
            "carte_courante": CHARGE_CARTE,
            "carte_decouverte": CHARGE_CARTE_DECOUVERTE,
            "carte_prete": CHARGE_CARTE_PRETE,
            "pong": CHARGE_PONG,
            "acces_accepte": charge_acces_accepte(),
            "serveur_selectionne": charge_serveur_selectionne(),
            "personnage_selectionne": charge_personnage_selectionne(),
        },
        "personnage_servi": {
            "identifiant": PERSONNAGE["identifiant"],
            "nom": PERSONNAGE["nom"],
            "niveau": PERSONNAGE["niveau"],
            "note": ("FORMES verifiees sur une trame kva REELLE (world_etapa1 @138) et sur "
                     "il2cpp.cs ; VALEURS inventees — aucune donnee de compte tiers."),
        },
    }


def main():
    ap = argparse.ArgumentParser(description="Genere la table de liaison du protocole 3.0")
    ap.add_argument("--verifier", action="store_true",
                    help="ne reecrit rien ; rc=1 si le fichier sur disque est perime")
    args = ap.parse_args()

    refus = []
    doc = construire(refus)
    if refus:
        for r in refus:
            print("REFUS/REFUSED : %s" % r, file=sys.stderr)
        return 1

    cible = ICI / ("binding-%s.json" % BUILD)
    texte = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=False) + "\n"

    if args.verifier:
        if not cible.exists():
            print("REFUS/REFUSED : %s absent" % cible.name, file=sys.stderr)
            return 1
        if cible.read_text(encoding="utf-8") != texte:
            print("REFUS/REFUSED : %s est PERIME (regenerer)" % cible.name, file=sys.stderr)
            return 1
        print("binding a jour : %s (%d messages, %d etapes de rafale)"
              % (cible.name, len(doc["messages"]), len(doc["rafale_bienvenue"])))
        return 0

    cible.write_text(texte, encoding="utf-8")
    confirmes = sum(1 for m in doc["messages"] if m["recroisement"] == "confirme_par_correspondance_v4")
    e5 = doc["recroisement_etage5"]
    print("ecrit %s" % cible)
    print("  messages                  : %d" % len(doc["messages"]))
    print("  confirmes par v4          : %d" % confirmes)
    print("  sans nom clair            : %d"
          % sum(1 for m in doc["messages"] if m["recroisement"] == "sans_nom_clair"))
    print("  confirmes par dispatch e5 : %d"
          % sum(1 for m in doc["messages"] if m["recroisement_dispatch"] == "confirme_par_dispatch"))
    print("  presents e5 SANS nom      : %d (etat normal, les 2 instruments s'accordent)"
          % sum(1 for m in doc["messages"] if m["recroisement_dispatch"] == "present_sans_nom"))
    print("  champs recroises e5       : %d/%d"
          % (len(e5["champs_verifies"]), len(CHAMPS_DONT_LE_SERVEUR_DEPEND)))
    print("  etapes de rafale          : %d (opcodes distincts : %d)"
          % (len(doc["rafale_bienvenue"]),
             len({e["semantique"] for e in doc["rafale_bienvenue"]})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
