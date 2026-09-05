#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : DUMP → `protocole-<build>.proto`. Reconstruit un fichier proto3 VALIDE
    depuis `cs/il2cpp.cs` : un `message` par classe protobuf du client, champs
    avec leur NUMÉRO et leur TYPE résolus, imbrication et `oneof` préservés,
    `optional` (présence explicite) préservé, énumérations avec leurs valeurs.
    Le nom de chaque message reste le TOKEN OBFUSQUÉ ; le nom sémantique proposé
    par un instrument tiers n'apparaît qu'en COMMENTAIRE, avec sa provenance.
    / Rebuilds a valid proto3 file from the IL2CPP dump; obfuscated tokens stay
    the identifiers, proposed clear names are comments only.

POURQUOI (05/09/2026, maillon A6 de `tools/community/chaine/CHAINE.md`, déclaré
    MANQUANT ; cahier étage 4, lois L6/L7) : les devs de la communauté désignent
    l'analyse statique comme LA cible pour pouvoir monter de version sans casse
    (« proto client ⇒ ému message ⇒ handler »). L6 : l'opcode 3 lettres EST le
    nom de classe obfusqué, re-brassé à chaque build — donc ce fichier se
    RÉGÉNÈRE, il ne se maintient pas. Un nom clair écrit comme identifiant
    ferait croire à une stabilité qui n'existe pas : il reste en commentaire.

COMMENT LANCER :
    python3 generer_proto.py --dump <…/cs/il2cpp.cs> --build 3.6.10.10 --out ./out
    python3 generer_proto.py --dump … --build … --out … --verifier   # + protoc

GATE (jouée par `--verifier`, rejouée par `gate-proto-sync.py`) :
    (1) `protoc --proto_path=… --descriptor_set_out=/dev/null` compile SANS erreur ;
    (2) le nombre de `message` émis == le nombre de classes `IMessage<self>` des
        assemblies protocolaires, recompté par un SECOND CHEMIN (grep sur le dump,
        indépendant du parseur à pile) ;
    (3) le nombre de champs émis == le nombre de `const int` du dump, recompté
        lui aussi par grep. Un compte produit deux fois par le même chemin ne
        prouve rien.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib_dump import (ASSEMBLIES_PROTOCOLE, BIEN_CONNUS, Dump, Type,   # noqa: E402
                       charger_dump, chemin_stable, sha256_fichier)
from _lib_noms import charger_noms                                       # noqa: E402

# Mots réservés de proto3 qui ne peuvent pas servir d'identifiant nu. Mesuré le
# 05/09 : aucun token obfusqué de nos 2206 classes n'y figure — mais une build
# suivante peut en produire un (les tokens sont re-brassés), donc la garde reste.
MOTS_RESERVES_PROTO = {
    "syntax", "import", "weak", "public", "package", "option", "message", "enum",
    "service", "rpc", "stream", "returns", "extend", "extensions", "reserved",
    "to", "max", "oneof", "map", "repeated", "optional", "required", "group",
    "true", "false", "default", "int32", "int64", "uint32", "uint64", "sint32",
    "sint64", "fixed32", "fixed64", "sfixed32", "sfixed64", "float", "double",
    "bool", "string", "bytes",
}

INDENT = "  "


def main(argv=None) -> int:
    """Point d'entrée : lit le dump, écrit le `.proto` et ses mesures, joue la gate si demandé.
    / Entry point: reads the dump, writes the .proto and its measurements, runs the gate on demand."""
    ap = argparse.ArgumentParser(description="dump IL2CPP -> protocole-<build>.proto (proto3)")
    ap.add_argument("--dump", required=True, help="chemin de cs/il2cpp.cs")
    ap.add_argument("--build", required=True, help="version de la build, ex. 3.6.10.10")
    ap.add_argument("--out", required=True, help="dossier de sortie")
    ap.add_argument("--verifier", action="store_true", help="joue la gate (protoc + seconds chemins)")
    ap.add_argument("--sans-noms", action="store_true",
                    help="n'annote aucun nom sémantique (utile pour un diff de forme pure)")
    ap.add_argument("--horodatage", default=None,
                    help="fige l'horodatage de l'en-tête (ISO UTC) — sans lui, deux rejeux "
                         "ne peuvent pas être byte-identiques et la gate (d) est intestable")
    a = ap.parse_args(argv)

    if not os.path.exists(a.dump):
        print("REFUS : dump introuvable — %s" % a.dump, file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)

    d = charger_dump(a.dump)
    noms = None if a.sans_noms else charger_noms()
    racines = _racines_protocolaires(d)

    chemin_proto = os.path.join(a.out, "protocole-%s.proto" % a.build)
    mesures = _ecrire_proto(chemin_proto, d, racines, noms, a.build,
                            chemin_stable(a.dump), a.horodatage)
    chemin_mesures = os.path.join(a.out, "protocole-%s.mesures.json" % a.build)
    with open(chemin_mesures, "w", encoding="utf-8") as fh:
        json.dump(mesures, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")

    print("écrit : %s (%d messages, %d champs, %d enums)"
          % (chemin_proto, mesures["messages_emis"], mesures["champs_emis"], mesures["enums_emis"]))
    print("écrit : %s" % chemin_mesures)
    if not a.verifier:
        return 0
    return 0 if verifier(chemin_proto, a.dump, mesures, bavard=True) else 1


def _racines_protocolaires(d: Dump):
    """Les types de TÊTE des deux assemblies du protocole : ceux qui deviennent des `message`
    ou `enum` de premier niveau du fichier. / Top-level protocol types of the two assemblies."""
    return [t for t in d.racines
            if t.genre in ("message", "enum") and t.assembly in ASSEMBLIES_PROTOCOLE]


def _ident(nom: str) -> str:
    """Rend un identifiant proto sûr. Un token qui heurterait un mot réservé serait accepté
    par la plupart des parseurs et refusé par certains : on le suffixe, et on le DIT.
    / Returns a safe proto identifier, suffixing a reserved word rather than hoping."""
    return nom + "_" if nom in MOTS_RESERVES_PROTO else nom


def _ecrire_proto(chemin, d: Dump, racines, noms, build, chemin_dump, horodatage=None) -> dict:
    """Écrit le fichier proto3 complet et rend les mesures de ce qui a été émis.
    / Writes the full proto3 file and returns what was actually emitted."""
    m = {"build": build, "messages_emis": 0, "champs_emis": 0, "enums_emis": 0,
         "valeurs_enum_emises": 0, "oneof_emis": 0, "optional_emis": 0,
         "repeated_emis": 0, "map_emis": 0, "noms_annotes": 0,
         "identifiants_echappes": [], "types_non_resolus": []}
    lignes = _entete(d, build, chemin_dump, racines, horodatage)
    corps = []
    for t in sorted(racines, key=lambda x: x.nom):
        _emettre(t, d, noms, 0, corps, m)
    lignes += corps
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lignes) + "\n")
    m["sha256_proto"] = sha256_fichier(chemin)
    m["sha256_dump"] = d.sha256
    m["controles_lecture"] = d.controles
    if noms is not None:
        m["sources_noms"] = noms.sources_lues
        m["collisions_noms"] = noms.collisions
    return m


def _entete(d: Dump, build, chemin_dump, racines, horodatage=None) -> list:
    """En-tête du `.proto` : la build y est écrite deux fois (commentaire ET `package`), parce
    qu'un artefact sans sa build devient faux EN SILENCE au patch suivant (L6).
    / Header: the build appears twice, in the comment and in the package name (law L6)."""
    horo = horodatage or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [
        "// protocole-%s.proto — GÉNÉRÉ, NE PAS ÉDITER À LA MAIN." % build,
        "// / GENERATED FILE — do not edit by hand.",
        "//",
        "// build            : %s" % build,
        "// source           : %s" % chemin_dump,
        "// sha256(source)   : %s" % d.sha256,
        "// généré le        : %s (UTC) par protocol/extract/proto-sync/generer_proto.py" % horo,
        "// régénérer        : voir protocol/extract/proto-sync/PROTO-SYNC.md",
        "//",
        "// CE QUI EST VÉRIFIÉ (lu dans le dump, avec fichier:ligne sur chaque message) :",
        "//   la FORME — quels messages existent, quels numéros de champ, quels types C#,",
        "//   l'imbrication, les oneof, la présence explicite (`optional`), les enums.",
        "// CE QUI EST DÉDUIT :",
        "//   (a) les noms de messages en commentaire `nom proposé:` — aucun n'est lisible",
        "//       dans le binaire (0/2206 mesuré, RAPPORT-MATCHER-V3.md §2) ;",
        "//   (b) int32/int64/uint32 : le C# généré compile int32, sint32 et sfixed32 vers",
        "//       le même `int`. Le type de FIL exact n'est pas récupérable du dump seul ;",
        "//       il ne se prouve que par une capture (chaîne L7).",
        "// Les identifiants sont les TOKENS OBFUSQUÉS : ils changent à chaque build (L6).",
        "//",
        "// %d types de tête, %d messages, %d champs (recomptés par un second chemin par la gate)."
        % (len(racines), d.controles.get("messages", 0), d.controles.get("consts", 0)),
        "",
        'syntax = "proto3";',
        "",
        # Le package porte la build : deux builds ne peuvent alors pas se joindre par accident,
        # même piège que la clé de nœud du graphe (règle du projet §2).
        "package namaste3.b%s;" % build.replace(".", "_"),
        "",
        'import "google/protobuf/any.proto";',
        "",
    ]


def _emettre(t: Type, d: Dump, noms, niveau: int, out: list, m: dict) -> None:
    """Émet récursivement un message ou un enum, avec ses types imbriqués.
    / Recursively emits a message or enum with its nested types."""
    pad = INDENT * niveau
    if t.genre == "enum":
        _emettre_enum(t, pad, out, m)
        return
    if t.genre != "message":
        return
    m["messages_emis"] += 1
    for c in _commentaire_message(t, noms, m):
        out.append(pad + c)
    out.append("%smessage %s {" % (pad, _garder(_ident(t.nom), t.nom, m)))
    _emettre_champs(t, pad + INDENT, out, m)
    # Un type imbriqué du PROTOCOLE passe toujours par le conteneur `Types` de protoc
    # (mesuré : 577 messages imbriqués, 383 enums, tous via un conteneur ; 0 sans).
    # Un enum accroché DIRECTEMENT au message est, lui, le `XxxOneofCase` fabriqué par le
    # générateur C# : il n'existe pas dans le `.proto` d'origine et ne doit pas y revenir.
    # Preuve d'exactitude de la règle, mesurée le 05/09 : l'ensemble des 118 messages
    # porteurs d'un oneof est EXACTEMENT l'ensemble des parents de ces 118 enums.
    # / Nested protocol types always go through protoc's `Types` container; an enum attached
    #   straight to the message is the C#-only OneofCase artifact and is dropped.
    m["enums_oneofcase_ecartes"] = m.get("enums_oneofcase_ecartes", 0) + sum(
        1 for e in t.enfants if e.genre == "enum")
    enfants = [pe for e in t.enfants if e.genre == "conteneur"
               for pe in e.enfants if pe.genre in ("message", "enum")]
    if t.champs and enfants:
        out.append("")
    for e in sorted(enfants, key=lambda x: x.nom):
        _emettre(e, d, noms, niveau + 1, out, m)
    out.append(pad + "}")
    if niveau == 0:
        out.append("")


def _commentaire_message(t: Type, noms, m: dict) -> list:
    """Le commentaire porte la SOURCE (fichier:ligne) et, s'il existe, le nom proposé avec sa
    provenance et son statut. Un nom sans provenance ne s'écrit pas.
    / The comment carries the source line and, if any, the proposed name with provenance."""
    c = ["// %s | %s:%d | TypeDefIndex %s"
         % (t.chemin_proto, os.path.basename("il2cpp.cs"), t.ligne, t.tdi)]
    if noms is None or t.parent is not None:
        return c
    e = noms.pour(t.nom)
    if e.nom_semantique:
        m["noms_annotes"] += 1
        c.append("// nom proposé: %s (%s, %s)" % (e.nom_semantique, e.provenance.split(":")[0], e.statut))
        if e.direction != "INCONNUE":
            c.append("// direction: %s (%s)" % (e.direction, e.direction_provenance.split(":")[0]))
    for cf in e.conflits:
        if "nom_ecarte" in cf:
            c.append("// nom ÉCARTÉ: %s — %s" % (cf["nom_ecarte"], cf["raison"]))
    return c


def _emettre_champs(t: Type, pad: str, out: list, m: dict) -> None:
    """Émet les champs dans l'ordre des numéros, en ouvrant un bloc `oneof` là où il faut.
    / Emits fields in number order, opening a `oneof` block where one exists."""
    dans_oneof = None
    for c in t.champs:
        if c.oneof and dans_oneof is None:
            dans_oneof = c.oneof
            m["oneof_emis"] += 1
            out.append("%soneof %s {" % (pad, _garder(_ident(c.oneof), c.oneof, m)))
        elif dans_oneof is not None and not c.oneof:
            out.append(pad + "}")
            dans_oneof = None
        p = pad + (INDENT if dans_oneof else "")
        out.append(p + _ligne_champ(c, m))
        m["champs_emis"] += 1
    if dans_oneof is not None:
        out.append(pad + "}")


def _ligne_champ(c, m: dict) -> str:
    """Une ligne de champ proto3, avec son type résolu et sa source en commentaire.
    / One proto3 field line, with resolved type and its dump line as a comment."""
    if c.type_proto.startswith("<INCONNU:"):
        m["types_non_resolus"].append({"champ": c.nom, "type_cs": c.type_cs, "ligne": c.ligne})
    prefixe = ""
    if c.label == "repeated":
        prefixe, m["repeated_emis"] = "repeated ", m["repeated_emis"] + 1
    elif c.label == "map":
        m["map_emis"] += 1
    elif c.presence and not c.oneof:
        # `optional` de proto3 : présence explicite. Sans lui, une valeur par défaut posée
        # exprès n'est pas sérialisée et le client ne la voit jamais.
        prefixe, m["optional_emis"] = "optional ", m["optional_emis"] + 1
    typ = ("map<%s, %s>" % (c.cle_map, c.type_proto)) if c.label == "map" else c.type_proto
    return "%s%s %s = %d;  // il2cpp.cs:%d" % (prefixe, typ, _ident(c.nom), c.numero, c.ligne)


def _emettre_enum(t: Type, pad: str, out: list, m: dict) -> None:
    """Émet une énumération. proto3 exige que la PREMIÈRE valeur vaille 0 : mesuré le 05/09,
    les 569 enums du protocole la respectent toutes (0 exception).
    / Emits an enum; proto3 requires first value 0, satisfied by all 569 measured enums."""
    m["enums_emis"] += 1
    out.append("%s// %s | il2cpp.cs:%d" % (pad, t.chemin_proto, t.ligne))
    out.append("%senum %s {" % (pad, _garder(_ident(t.nom), t.nom, m)))
    vus = set()
    for nom, val in t.valeurs:
        if val in vus:
            continue                    # alias : jamais rencontré ici, la garde reste
        vus.add(val)
        m["valeurs_enum_emises"] += 1
        out.append("%s%s%s = %d;" % (pad, INDENT, _ident(nom), val))
    out.append(pad + "}")


def _garder(sortie: str, entree: str, m: dict) -> str:
    """Note tout identifiant qu'on a dû échapper : un renommage silencieux casserait le lien
    entre le `.proto` et le dump. / Records any escaped identifier; a silent rename would break traceability."""
    if sortie != entree:
        m["identifiants_echappes"].append({"dump": entree, "proto": sortie})
    return sortie


# ── Gate ──────────────────────────────────────────────────────────────────────

def compter_par_grep(chemin_dump: str) -> dict:
    """SECOND CHEMIN de comptage : lecture ligne à ligne par expressions régulières, sans le
    parseur à pile. Deux chemins qui tombent d'accord valent mieux qu'un chemin répété — un
    compte produit deux fois par le même instrument ne mesure que l'instrument.
    / Independent regex-based count, deliberately not reusing the stack parser."""
    plages = []
    re_img = re.compile(r"^// Image \d+: ([\w\.]+) - Assembly: .* - Types (\d+)-(\d+)")
    # `IBufferMessage` est exigé : c'est le critère de la gate G0 (`internal/GATE-G0-RAPPORT.md`),
    # donc le second chemin compte EXACTEMENT la même population qu'elle. Mesuré le 05/09 :
    # 2206 `IMessage<self>` protocolaires, 2206 portent aussi `IBufferMessage` — les deux
    # critères coïncident ici, mais on prend le plus strict pour ne pas dériver.
    re_cls = re.compile(r"class (\w+) : IMessage<(\w+)>, IBufferMessage")
    re_tdi = re.compile(r"TypeDefIndex:\s*(\d+)")
    re_cst = re.compile(r"^\s*public const int @?\w+ = -?\d+;")
    msgs, champs, dedans = 0, 0, False
    with open(chemin_dump, encoding="utf-8-sig", errors="replace") as fh:
        for l in fh:
            mi = re_img.match(l)
            if mi:
                plages.append((mi.group(1), int(mi.group(2)), int(mi.group(3))))
                continue
            mc = re_cls.search(l)
            if mc:
                dedans = False
                if mc.group(1) == mc.group(2):
                    mt = re_tdi.search(l)
                    if mt:
                        tdi = int(mt.group(1))
                        for nom, a, b in plages:
                            if a <= tdi <= b and nom in ASSEMBLIES_PROTOCOLE:
                                msgs += 1
                                dedans = True
                                break
                continue
            if l.startswith("}"):
                dedans = False
            elif dedans and re_cst.match(l):
                champs += 1
    return {"messages": msgs, "champs": champs}


def verifier(chemin_proto: str, chemin_dump: str, mesures: dict, bavard=False) -> bool:
    """Joue les trois barrières de la gate et refuse NOMMÉMENT. / Runs the three barriers, refusing by name."""
    refus = []
    second = compter_par_grep(chemin_dump)
    if mesures["messages_emis"] != second["messages"]:
        refus.append("compte de messages : %d émis, %d au second chemin (grep)"
                     % (mesures["messages_emis"], second["messages"]))
    if mesures["champs_emis"] != second["champs"]:
        refus.append("compte de champs : %d émis, %d au second chemin (grep)"
                     % (mesures["champs_emis"], second["champs"]))
    ok_protoc, detail = compiler_protoc(chemin_proto)
    if not ok_protoc:
        refus.append("protoc : " + detail)
    if bavard:
        print("second chemin (grep) : %d messages, %d champs" % (second["messages"], second["champs"]))
        print("protoc : " + ("OK — " + detail if ok_protoc else "REFUS"))
        for r in refus:
            print("REFUS : " + r, file=sys.stderr)
        print("GATE generer_proto : " + ("🟢 VERTE" if not refus else "🔴 ROUGE (%d refus)" % len(refus)))
    return not refus


def compiler_protoc(chemin_proto: str):
    """Compile le `.proto` par protoc. C'est le seul juge qui ne soit pas nous.
    / Compiles with protoc: the only judge that is not ourselves."""
    exe = _trouver_protoc()
    if exe is None:
        return False, "protoc absent (apt-get install -y protobuf-compiler)"
    dossier = os.path.dirname(os.path.abspath(chemin_proto)) or "."
    cmd = [exe, "--proto_path=" + dossier, "--proto_path=/usr/include",
           "--descriptor_set_out=" + os.devnull, os.path.basename(chemin_proto)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return False, (p.stderr.strip().split("\n")[:5] and "\n".join(p.stderr.strip().split("\n")[:5]))
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    return True, "compile sans erreur (%s)" % ver


def _trouver_protoc():
    """Trouve protoc dans le PATH. / Locates protoc on PATH."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        c = os.path.join(d, "protoc")
        if os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


if __name__ == "__main__":
    sys.exit(main())
