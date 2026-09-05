#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI / WHAT
    Cherche des `FileDescriptorProto` protobuf BRUTS dans les artefacts du client Dofus 3.6.10.11
    (`global-metadata.dat`, `GameAssembly.dll`) et, s'il y en a, les rend en `.jsonl` + `.proto`.
    Hunts RAW protobuf `FileDescriptorProto` blobs inside the Dofus 3.6.10.11 client artefacts.

POURQUOI / WHY  (écrit le 2026-09-05 / written 2026-09-05)
    Le `.proto` que nous avons est DÉDUIT : reconstruit depuis la structure des classes IL2CPP
    (constantes de numéro de champ). Un descripteur trouvé dans le client serait VÉRIFIÉ : la
    source d'autorité, avec les noms de fichiers, les paquets et les `oneof` déclarés.
    Le dépôt Jondo porte DEUX affirmations opposées là-dessus, et c'est pour cela qu'on mesure :
      · `Jondo.Unity.Reversing/DescriptorExtractor.cs` (en-tête) : « está EN CRUDO » dans
        global-metadata.dat, on le reconnaît au champ 1 = nom de fichier.
      · `docs/desofuscacion.md` §3.1, seconde passe du 19/08/2026, MESURÉE : « El descriptor
        serializado no está en el cliente » — pas de base64, pas de brut (les `.proto` trouvés sont
        des chemins `PackageCache\\com.ankama.dofus.protocol.` — « protocol » contient « .proto »),
        rien dans GameAssembly.dll. Et sa table des fichiers (ligne 629) classe
        `DescriptorExtractor.cs` comme « el camino muerto del descriptor serializado (§3.1) ».
    L'en-tête du C# est l'HYPOTHÈSE ; le §3.1 est la RÉFUTATION mesurée. Mais la mesure de Jondo
    porte sur SON client 3.6.10.10 : elle ne vaut pas mesure sur notre 3.6.10.11. On remesure.
    Jondo's own repo contradicts itself; his §3.1 refutes his class docstring. Either way his
    measurement was on his 3.6.10.10 artefact, not on ours — so we measure ours.

COMMENT / HOW
    Méthode réimplémentée (jamais copiée) d'après `DescriptorExtractor.cs`, en Python stdlib :
      1. On cherche l'aiguille « .proto » et on RECULE jusqu'à un en-tête `0x0A <longueur>` qui
         tombe pile sur le début du nom : c'est le champ 1 d'un FileDescriptorProto.
      2. La longueur du bloc n'est écrite NULLE PART : on avance champ à champ tant que c'est
         plausible et, à chaque pas, on tente un décodage STRICT avec aller-retour byte-identique
         (`protobuf_strict.strict_parse`). Le plus long qui survit est la fin du bloc.
      3. Trois chemins de mesure INDÉPENDANTS, pour ne pas confirmer son propre angle mort :
         A) brut dans global-metadata.dat   B) base64 dans global-metadata.dat (la forme que
         laisse le générateur C# de bureau)   C) brut dans GameAssembly.dll.

GATE
    `--epreuve` doit rendre 3 verts, sinon aucun chiffre de ce script n'est recevable :
      · TÉMOIN POSITIF : un FileDescriptorProto synthétique, écrit ici, INJECTÉ dans un vrai bloc
        de métadonnées, doit être RETROUVÉ par le scan et décodé à l'identique. Sans lui, un « 0 »
        et un instrument aveugle s'écrivent pareil.
      · SABOTAGE : un octet corrompu dans ce témoin doit le faire tomber en décodage strict, PAS
        produire un message faux.
      · REJEU : deux passes sur la même entrée rendent des octets identiques.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protobuf_strict import (  # noqa: E402
    PROTO_LABEL, PROTO_TYPE, StrictError, encode, decode, read_varint, strict_parse, write_varint,
)

ICI = Path(__file__).resolve().parent
METADATA = Path("internal/artefacts/"
                "temoins-3.0/global-metadata.dat")
GAMEASM = Path("internal/artefacts/"
               "temoins-3.0/GameAssembly.dll")
VERSION = "3.6.10.11"
LONGUEUR_MIN = 24          # comme Jondo : en deçà, ce n'est pas un descripteur / min blob size


# ── Chemin A : le brut / Path A: raw scan ─────────────────────────────────────────────────────
def debuts_bruts(data: bytes, max_nom: int = 120):
    """
    Où un descripteur peut COMMENCER : un `0x0A <longueur>` suivi d'un nom finissant en « .proto ».
    On cherche par la FIN (« .proto ») et on recule — bien plus rapide que tester chaque octet.
    Where a descriptor may START: `0x0A <len>` then a name ending in ".proto". Searched backwards
    from the needle, which is far cheaper than probing every byte of a 40 MB file.
    """
    aiguille = b".proto"
    for m in re.finditer(re.escape(aiguille), data):
        fin = m.start() + len(aiguille)
        for lg_nom in range(len(aiguille), max_nom + 1):
            entete = fin - lg_nom - 2          # 0x0A + un octet de longueur / tag + one length byte
            if entete < 0:
                break
            if data[entete] == 0x0A and data[entete + 1] == lg_nom:
                yield entete


def _champ_plausible(data: bytes, at: int) -> int | None:
    """
    Avance d'UN champ de niveau supérieur si c'est plausible pour un FileDescriptorProto.
    Advances by ONE top-level field if plausible; returns the new cursor or None.
    """
    try:
        cle, at = read_varint(data, at)
    except StrictError:
        return None
    champ, fil = cle >> 3, cle & 7
    # Un FileDescriptorProto va jusqu'au champ 13 (`edition`). Au-delà, on est sorti du bloc.
    if not (1 <= champ <= 13):
        return None
    if fil == 0:
        try:
            _v, at = read_varint(data, at)
        except StrictError:
            return None
        return at
    if fil == 2:
        try:
            lg, at = read_varint(data, at)
        except StrictError:
            return None
        if lg > len(data) or at + lg > len(data):
            return None
        return at + lg
    return None       # un descripteur n'utilise ni 32 ni 64 bits fixes / no fixed-width fields


def lire_a(data: bytes, debut: int) -> tuple[int, dict] | None:
    """
    Lit un descripteur complet depuis `debut`, s'il y en a un.
    La longueur n'est pas donnée : on avance champ à champ et, chaque fois que le morceau lu
    survit à l'aller-retour STRICT, on le note comme meilleure fin connue. On rend le plus long.
    Reads a full descriptor: the block length is written nowhere, so the longest prefix that
    survives the strict round-trip defines where it ends.
    """
    meilleur: dict | None = None
    meilleure_lg = 0
    at = debut
    while at < len(data):
        suivant = _champ_plausible(data, at)
        if suivant is None:
            break
        at = suivant
        lg = at - debut
        if lg < LONGUEUR_MIN:
            continue
        obj = strict_parse(data[debut:at])
        if obj is None:
            continue
        if not obj.get("name"):
            continue
        if not obj.get("message_type") and not obj.get("enum_type"):
            continue
        meilleur, meilleure_lg = obj, lg
    return None if meilleur is None else (meilleure_lg, meilleur)


def scan_brut(data: bytes, etiquette: str) -> tuple[list[dict], dict]:
    """Balaye un conteneur pour des descripteurs BRUTS. / Scans a container for RAW descriptors."""
    trouves: list[dict] = []
    fin_precedente = 0
    candidats = 0
    for debut in debuts_bruts(data):
        candidats += 1
        if debut < fin_precedente:
            continue                        # déjà dans le précédent / already inside the last one
        lu = lire_a(data, debut)
        if lu is None:
            continue
        lg, obj = lu
        obj["_offset"] = debut
        obj["_longueur"] = lg
        obj["_conteneur"] = etiquette
        trouves.append(obj)
        fin_precedente = debut + lg
    # Le CONTRASTE est la mesure : combien de « .proto » existent, combien portent un en-tête
    # protobuf valide. Beaucoup d'occurrences + zéro en-tête = des CHAÎNES, pas des descripteurs.
    # The CONTRAST is the measurement: many ".proto" strings with zero valid protobuf headers
    # means they are plain string literals, not descriptors.
    return trouves, {"conteneur": etiquette, "octets": len(data),
                     "occurrences_texte_point_proto": data.count(b".proto"),
                     "candidats_0x0A_nom_proto": candidats, "descripteurs_valides": len(trouves)}


# ── Chemin B : le base64 / Path B: base64 scan ────────────────────────────────────────────────
RE_B64 = re.compile(rb"[A-Za-z0-9+/]{40,}={0,2}")


def scan_base64(data: bytes, etiquette: str) -> tuple[list[dict], dict]:
    """
    La forme que laisse le générateur C# de BUREAU : le descripteur en base64 dans une constante.
    The DESKTOP C# generator form: the descriptor as a base64 string constant.
    """
    trouves: list[dict] = []
    candidats = 0
    decodables = 0
    for m in RE_B64.finditer(data):
        candidats += 1
        brut = m.group(0)
        try:
            crus = base64.b64decode(brut + b"=" * (-len(brut) % 4), validate=True)
        except Exception:
            continue
        decodables += 1
        if len(crus) < LONGUEUR_MIN:
            continue
        obj = strict_parse(crus)
        if obj is None or not obj.get("name"):
            continue
        if not obj.get("message_type") and not obj.get("enum_type"):
            continue
        obj["_offset"] = m.start()
        obj["_longueur"] = len(crus)
        obj["_conteneur"] = etiquette + " (base64)"
        trouves.append(obj)
    return trouves, {"conteneur": etiquette + " (base64)", "octets": len(data),
                     "candidats_base64_40plus": candidats, "base64_decodables": decodables,
                     "descripteurs_valides": len(trouves)}


# ── Rendu / Rendering ─────────────────────────────────────────────────────────────────────────
def _type_de_champ(f: dict) -> str:
    """Nom de type proto3 d'un champ. / proto3 type name of one field."""
    tn = f.get("type_name")
    if tn:
        return tn.lstrip(".")
    return PROTO_TYPE.get(f.get("type", 0), f"UNKNOWN_{f.get('type')}")


def _rendre_message(m: dict, indent: int) -> list[str]:
    """Un message en proto3, `oneof` regroupés. / One message as proto3, oneofs grouped."""
    pad = "  " * indent
    out = [f"{pad}message {m.get('name', '?')} {{"]
    oneofs = m.get("oneof_decl", []) or []
    libres = [f for f in m.get("field", []) or [] if "oneof_index" not in f]
    for f in libres:
        lab = "repeated " if PROTO_LABEL.get(f.get("label", 1)) == "repeated" else ""
        out.append(f"{pad}  {lab}{_type_de_champ(f)} {f.get('name','?')} = {f.get('number','?')};")
    for i, o in enumerate(oneofs):
        out.append(f"{pad}  oneof {o.get('name', f'oneof_{i}')} {{")
        for f in m.get("field", []) or []:
            if f.get("oneof_index") == i:
                out.append(f"{pad}    {_type_de_champ(f)} {f.get('name','?')} "
                           f"= {f.get('number','?')};")
        out.append(f"{pad}  }}")
    for e in m.get("enum_type", []) or []:
        out += _rendre_enum(e, indent + 1)
    for n in m.get("nested_type", []) or []:
        out += _rendre_message(n, indent + 1)
    out.append(f"{pad}}}")
    return out


def _rendre_enum(e: dict, indent: int) -> list[str]:
    pad = "  " * indent
    out = [f"{pad}enum {e.get('name','?')} {{"]
    for v in e.get("value", []) or []:
        out.append(f"{pad}  {v.get('name','?')} = {v.get('number', 0)};")
    out.append(f"{pad}}}")
    return out


def rendre_proto(fichiers: list[dict]) -> str:
    """Régénère un `.proto` proto3 compilable. / Regenerates a compilable proto3 file."""
    out = ["// Régénéré depuis les descripteurs BRUTS du client " + VERSION,
           "// Regenerated from the RAW descriptors found inside the client.",
           'syntax = "proto3";', ""]
    for f in fichiers:
        out.append(f"// ── {f.get('name','?')} @0x{f.get('_offset',0):x} "
                   f"({f.get('_longueur',0)} o) ──")
        if f.get("package"):
            out.append(f"package {f['package']};")
        for d in f.get("dependency", []) or []:
            out.append(f'import "{d}";')
        for e in f.get("enum_type", []) or []:
            out += _rendre_enum(e, 0)
        for m in f.get("message_type", []) or []:
            out += _rendre_message(m, 0)
        out.append("")
    return "\n".join(out) + "\n"


def compter(fichiers: list[dict]) -> dict:
    """Compte messages/champs/enums, imbriqués compris. / Counts messages, fields, enums."""
    msg = champs = enums = 0

    def visiter(m: dict):
        nonlocal msg, champs, enums
        msg += 1
        champs += len(m.get("field", []) or [])
        enums += len(m.get("enum_type", []) or [])
        for n in m.get("nested_type", []) or []:
            visiter(n)

    for f in fichiers:
        enums += len(f.get("enum_type", []) or [])
        for m in f.get("message_type", []) or []:
            visiter(m)
    return {"fichiers_proto": len(fichiers), "messages": msg, "champs": champs, "enums": enums}


# ── Épreuve / Proof ───────────────────────────────────────────────────────────────────────────
def _temoin_synthetique() -> bytes:
    """
    Un FileDescriptorProto VALIDE, écrit ici à la main, pour prouver que l'instrument voit.
    A hand-built VALID FileDescriptorProto, so that a "0 found" is a fact about the terrain
    and not about a blind instrument.
    """
    def champ(nom: str, num: int, typ: int) -> bytes:
        b = write_varint(0x0A) + write_varint(len(nom)) + nom.encode()
        b += write_varint(0x18) + write_varint(num)
        b += write_varint(0x20) + write_varint(1)       # label = optional
        b += write_varint(0x28) + write_varint(typ)
        return b

    msg = write_varint(0x0A) + write_varint(len("TemoinMessage")) + b"TemoinMessage"
    for nom, num, typ in (("id", 1, 5), ("libelle", 2, 9), ("actif", 3, 8)):
        c = champ(nom, num, typ)
        msg += write_varint(0x12) + write_varint(len(c)) + c

    nom_fichier = b"temoin/nos_temoin.proto"
    out = write_varint(0x0A) + write_varint(len(nom_fichier)) + nom_fichier
    out += write_varint(0x12) + write_varint(len(b"nos.temoin")) + b"nos.temoin"
    out += write_varint(0x22) + write_varint(len(msg)) + msg
    out += write_varint(0x62) + write_varint(len(b"proto3")) + b"proto3"
    return out


def epreuve() -> int:
    """Les trois épreuves de la GATE. / The three gate proofs. Returns a shell exit code."""
    verts = []
    temoin = _temoin_synthetique()

    # 1. TÉMOIN POSITIF, injecté dans la zone du fichier réel qui contient DÉJÀ des « .proto ».
    #    L'injecter dans une zone calme ne prouverait que le parseur ; ici le scan doit distinguer
    #    le vrai descripteur des chaînes voisines qui portent le même texte.
    #    Injected into the noisy region that already holds ".proto" strings, so the scan has to
    #    tell a real descriptor apart from look-alike string literals.
    if METADATA.exists():
        tout = METADATA.read_bytes()
        pivot = tout.find(b"google/protobuf/any.proto")
        base = max(0, pivot - 1_000_000) if pivot >= 0 else 0
        bruit = tout[base:base + 2_000_000]
        del tout
    else:
        bruit = bytes(2_000_000)
    porteur = bruit[:1_000_000] + temoin + bruit[1_000_000:]
    trouves, stats = scan_brut(porteur, "temoin-injecte")
    attendu = [t for t in trouves if t.get("name") == "temoin/nos_temoin.proto"]
    ok1 = len(attendu) == 1 and attendu[0]["_offset"] == 1_000_000 \
        and attendu[0]["_longueur"] == len(temoin) \
        and compter(attendu) == {"fichiers_proto": 1, "messages": 1, "champs": 3, "enums": 0}
    verts.append(ok1)
    print(f"[1] TÉMOIN POSITIF injecté à 0x{1_000_000:x} : "
          f"{'VERT' if ok1 else 'ROUGE'} — retrouvé={len(attendu)}, "
          f"candidats balayés={stats['candidats_0x0A_nom_proto']}, "
          f"compte={compter(attendu)}")

    # 2. SABOTAGE : un octet corrompu doit TOMBER, pas mentir.
    faux = 0
    tombes = 0
    for pos in range(len(temoin)):
        casse = bytearray(temoin)
        casse[pos] ^= 0xFF
        obj = strict_parse(bytes(casse))
        if obj is None:
            tombes += 1
        elif obj.get("name") == "temoin/nos_temoin.proto" and \
                compter([obj]) != {"fichiers_proto": 1, "messages": 1, "champs": 3, "enums": 0}:
            faux += 1                       # décodé ET faux : le pire cas / decoded AND wrong
    ok2 = faux == 0
    verts.append(ok2)
    print(f"[2] SABOTAGE 1 octet ×{len(temoin)} positions : {'VERT' if ok2 else 'ROUGE'} — "
          f"{tombes}/{len(temoin)} rejetés en décodage strict, "
          f"{len(temoin) - tombes} acceptés (variantes VALIDES du témoin), "
          f"{faux} messages FAUX produits")

    # 3. REJEU byte-identique.
    a = rendre_proto([t for t in trouves if t.get("name") == "temoin/nos_temoin.proto"])
    trouves2, _ = scan_brut(porteur, "temoin-injecte")
    b = rendre_proto([t for t in trouves2 if t.get("name") == "temoin/nos_temoin.proto"])
    ok3 = a == b and a.strip() != ""
    verts.append(ok3)
    print(f"[3] REJEU byte-identique : {'VERT' if ok3 else 'ROUGE'} — {len(a)} octets rendus")

    print(f"\nGATE : {sum(verts)}/3 verts")
    return 0 if all(verts) else 1


# ── Entrée / Entry point ──────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epreuve", action="store_true", help="joue la GATE et sort / run the gate")
    ap.add_argument("--sortie", default=str(ICI), help="répertoire de sortie / output directory")
    args = ap.parse_args()

    if args.epreuve:
        return epreuve()

    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    tous: list[dict] = []
    mesures: list[dict] = []

    for chemin, etiquette in ((METADATA, "global-metadata.dat"), (GAMEASM, "GameAssembly.dll")):
        if not chemin.exists():
            mesures.append({"conteneur": etiquette, "erreur": "absent"})
            continue
        data = chemin.read_bytes()
        t, s = scan_brut(data, etiquette)
        tous += t
        mesures.append(s)
        if etiquette == "global-metadata.dat":       # base64 : seulement là où c'est plausible
            t2, s2 = scan_base64(data, etiquette)
            tous += t2
            mesures.append(s2)
        del data

    jsonl = sortie / f"descripteurs-{VERSION}.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for f in tous:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    (sortie / "protocole-descripteur.proto").write_text(rendre_proto(tous), encoding="utf-8")

    bilan = {"version": VERSION, "chemins_de_mesure": mesures, "totaux": compter(tous)}
    (sortie / "mesure-descripteur.json").write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
