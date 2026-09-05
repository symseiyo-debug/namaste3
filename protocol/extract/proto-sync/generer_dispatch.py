#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : DUMP → `dispatch-<build>.json` + `dispatch-<build>.cs`. La TABLE que le
    serveur charge au démarrage : pour chaque message, son opcode, son token
    obfusqué, son nom sémantique STABLE, sa direction, ses champs typés, sa
    provenance et son statut. Le `.cs` est une classe de DONNÉES pures —
    déclarations et littéraux, aucune logique, aucun index construit par du code.
    / The dispatch table the server loads at boot; the .cs side is data only.

POURQUOI (05/09/2026, cahier lois L6/L7, étage 4) : L6 — l'opcode 3 lettres EST
    le nom de classe obfusqué, re-brassé à CHAQUE build. Un opcode écrit en dur
    dans un handler est donc une bombe à retardement : il compile, il passe les
    tests, et il devient faux au patch suivant SANS que rien ne s'allume.
    D'où l'inversion : **l'opcode n'existe qu'ici**. Les handlers sont écrits
    contre le NOM SÉMANTIQUE, seule clé qui traverse les builds ; c'est la table
    qui traduit nom → opcode, et elle se régénère.
    Verbatim des devs de la communauté (cahier, étage 4) : « avec les proto-sync
    dispo : proto client ⇒ ému message ⇒ handler, et voilà comment on upgrade ».
    Deux honnêtetés portées par la table, parce qu'elles coûtent cher si on les tait :
      · aucun nom n'est lisible dans notre binaire (0/2206, RAPPORT-MATCHER-V3.md
        §2) — tout nom vient d'un TIERS et porte donc sa provenance et son statut ;
      · un nom revendiqué par deux opcodes n'est pas une clé : la table le retire
        aux deux quand la hiérarchie ne départage pas, plutôt que d'en élire un.

COMMENT LANCER :
    python3 generer_dispatch.py --dump <…/cs/il2cpp.cs> --build 3.6.10.10 --out ./out
    python3 generer_dispatch.py --dump … --build … --out … --verifier

GATE (jouée par `--verifier`, rejouée par `gate-proto-sync.py`) :
    (1) une entrée par message des assemblies protocolaires, recompté par un
        SECOND CHEMIN indépendant du parseur ;
    (2) chaque entrée porte `provenance` ET `statut` non vides ;
    (3) un opcode ne désigne qu'une entrée, un nom sémantique n'en désigne qu'une ;
    (4) le `.cs` est sans logique : aucun `if`, `for`, `while`, `return`, `=>`.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _lib_dump import (ASSEMBLIES_PROTOCOLE, Dump, Type, charger_dump,   # noqa: E402
                       chemin_stable)
from _lib_noms import charger_noms                                     # noqa: E402
from generer_proto import compter_par_grep                             # noqa: E402

# Le préfixe du `typeUrl` de l'enveloppe `google.protobuf.Any`, mesuré par le codec
# de l'étage 2 (`codec/CODEC.md`, 355 trames réelles décodées).
PREFIXE_TYPEURL = "type.ankama.com/"

# Mots qui trahiraient de la LOGIQUE dans le fichier C# généré. La table doit rester
# une donnée : du code généré qui décide est du code que personne ne relit.
MOTS_LOGIQUE = (r"\bif\b", r"\bfor\b", r"\bwhile\b", r"\bswitch\b", r"\breturn\b",
                r"\bforeach\b", r"=>")


def main(argv=None) -> int:
    """Point d'entrée : lit le dump, écrit la table JSON et C#, joue la gate si demandé.
    / Entry point: reads the dump, writes the JSON and C# tables, runs the gate on demand."""
    ap = argparse.ArgumentParser(description="dump IL2CPP -> table de dispatch générée")
    ap.add_argument("--dump", required=True, help="chemin de cs/il2cpp.cs")
    ap.add_argument("--build", required=True, help="version de la build, ex. 3.6.10.10")
    ap.add_argument("--out", required=True, help="dossier de sortie")
    ap.add_argument("--verifier", action="store_true", help="joue la gate")
    ap.add_argument("--horodatage", default=None,
                    help="fige l'horodatage (ISO UTC) — sans lui, deux rejeux ne peuvent pas "
                         "être byte-identiques et la gate (d) est intestable")
    a = ap.parse_args(argv)

    if not os.path.exists(a.dump):
        print("REFUS : dump introuvable — %s" % a.dump, file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)

    d = charger_dump(a.dump)
    noms = charger_noms()
    entrees = batir_entrees(d, noms)

    table = {
        "build": a.build,
        "genere_le": a.horodatage or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "genere_par": "protocol/extract/proto-sync/generer_dispatch.py",
        "source": {"chemin": chemin_stable(a.dump), "sha256": d.sha256},
        "prefixe_typeurl": PREFIXE_TYPEURL,
        "controles_lecture": d.controles,
        "sources_noms": noms.sources_lues,
        "collisions_noms": noms.collisions,
        "mesures": mesurer(entrees),
        "entrees": entrees,
    }
    chemin_json = os.path.join(a.out, "dispatch-%s.json" % a.build)
    with open(chemin_json, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(table, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    chemin_cs = os.path.join(a.out, "dispatch-%s.cs" % a.build)
    _ecrire_cs(chemin_cs, table)

    m = table["mesures"]
    print("écrit : %s (%d entrées, %d opcodes, %d avec nom sémantique)"
          % (chemin_json, m["entrees"], m["opcodes"], m["avec_nom"]))
    print("écrit : %s" % chemin_cs)
    if not a.verifier:
        return 0
    return 0 if verifier(table, chemin_cs, a.dump, bavard=True) else 1


def batir_entrees(d: Dump, noms) -> list:
    """Une entrée par message protocolaire. L'opcode n'est porté que par les messages de TÊTE :
    seuls eux voyagent dans une enveloppe `Any` et ont donc un `typeUrl`.
    / One entry per protocol message; only top-level ones carry an opcode (they alone get a typeUrl)."""
    out = []
    for t in sorted((x for x in d.messages if x.assembly in ASSEMBLIES_PROTOCOLE),
                    key=lambda x: (x.parent is not None, x.chemin_proto)):
        tete = t.parent is None
        e = noms.pour(t.nom) if tete else None
        source = "il2cpp.cs:%d" % t.ligne
        out.append({
            "opcode": t.nom if tete else "",
            "type_url": (PREFIXE_TYPEURL + t.nom) if tete else "",
            "token_obfusque": t.nom,
            "chemin_proto": t.chemin_proto,
            "niveau": "tete" if tete else "imbrique",
            "nom_semantique": e.nom_semantique if e else "",
            "direction": e.direction if e else "INCONNUE",
            "direction_provenance": e.direction_provenance if e else "",
            "statut": (e.statut if e else "SANS_NOM"),
            "statut_detail": _detail_statut(e, source),
            "provenance": (e.provenance if (e and e.provenance) else ("dump:" + source)),
            "conflits": (e.conflits if e else []),
            "structure": {"source": source, "typedef_index": t.tdi, "assembly": t.assembly,
                          "statut": "VERIFIE",
                          "detail": "forme lue directement dans NOTRE dump de la build"},
            "champs": [{"num": c.numero, "type": c.type_proto, "nom": c.nom,
                        "label": c.label, "presence_explicite": c.presence,
                        "cle_map": c.cle_map, "source": "il2cpp.cs:%d" % c.ligne}
                       for c in t.champs],
        })
    return out


def _detail_statut(e, source: str) -> str:
    """Dit EXACTEMENT ce que le statut couvre. « VÉRIFIÉ » nu s'élargit tout seul avec le temps :
    il doit nommer qui atteste quoi, et ce qui reste à prouver.
    / Spells out what the status covers; a bare 'VERIFIED' widens on its own over time."""
    if e is None or not e.nom_semantique:
        return ("structure VÉRIFIÉE dans notre dump (%s) ; AUCUN nom sémantique — "
                "à obtenir par capture (chaîne L7)" % source)
    if e.statut == "VERIFIE":
        return ("structure VÉRIFIÉE dans notre dump (%s) ; nom ATTESTÉ PAR CAPTURE d'un tiers "
                "(JondoEmu, 242 captures sur la même build) — pas encore par une capture À NOUS"
                % source)
    return ("structure VÉRIFIÉE dans notre dump (%s) ; nom DÉDUIT par appariement structurel — "
            "à promouvoir par capture (chaîne L7)" % source)


def mesurer(entrees: list) -> dict:
    """Compte ce que la table contient réellement — jamais ce qu'on croit y avoir mis.
    / Counts what the table actually holds, never what one believes was put in it."""
    tete = [e for e in entrees if e["niveau"] == "tete"]
    m = {"entrees": len(entrees), "opcodes": len(tete),
         "imbriques": len(entrees) - len(tete),
         "champs": sum(len(e["champs"]) for e in entrees),
         "avec_nom": sum(1 for e in tete if e["nom_semantique"]),
         "nom_verifie": sum(1 for e in tete if e["statut"] == "VERIFIE"),
         "nom_deduit": sum(1 for e in tete if e["statut"] == "DEDUIT"),
         "sans_nom": sum(1 for e in tete if e["statut"] == "SANS_NOM"),
         "direction_c2s": sum(1 for e in tete if e["direction"] == "C2S"),
         "direction_s2c": sum(1 for e in tete if e["direction"] == "S2C"),
         "direction_inconnue": sum(1 for e in tete if e["direction"] == "INCONNUE")}
    m["pct_avec_nom"] = round(100.0 * m["avec_nom"] / max(m["opcodes"], 1), 2)
    return m


# ── Sortie C# : DONNÉES, pas de logique ───────────────────────────────────────

def _ecrire_cs(chemin: str, table: dict) -> None:
    """Écrit la classe C# de données. Une ligne par entrée : le fichier reste diffable
    entre deux builds, ce qui est tout l'intérêt du ping-pong (`diff_builds.py`).
    / Writes the C# data class, one line per entry so two builds stay diffable."""
    b = table["build"]
    suffixe = re.sub(r"[^0-9A-Za-z]", "_", b)
    m = table["mesures"]
    L = [
        "// dispatch-%s.cs — GÉNÉRÉ par protocol/extract/proto-sync/generer_dispatch.py." % b,
        "// QUOI : la table de dispatch de la build %s, en DONNÉES pures (aucune logique)." % b,
        "// POURQUOI (05/09/2026, loi L6 du cahier) : l'opcode 3 lettres est re-brassé à chaque",
        "//   build. Il n'existe donc QUE dans ce fichier généré ; les handlers sont écrits",
        "//   contre NomSemantique, la seule clé qui traverse les builds. Un opcode écrit en",
        "//   dur dans un handler compile, passe les tests, et devient faux au patch suivant.",
        "// COMMENT LANCER : ce fichier ne se lance pas, il se CHARGE au démarrage du serveur.",
        "//   L'indexation (par opcode, par nom) est le travail du chargeur, pas de la table :",
        "//   une donnée qui s'indexe elle-même est du code que personne ne relit.",
        "// GATE : protocol/extract/proto-sync/gate-proto-sync.py --epreuve",
        "//",
        "// build          : %s" % b,
        "// source         : %s" % table["source"]["chemin"],
        "// sha256(source) : %s" % table["source"]["sha256"],
        "// généré le      : %s (UTC)" % table["genere_le"],
        "// entrées %d · opcodes %d · champs %d · avec nom sémantique %d (%.2f %% des opcodes)"
        % (m["entrees"], m["opcodes"], m["champs"], m["avec_nom"], m["pct_avec_nom"]),
        "// NE PAS ÉDITER À LA MAIN — régénérer (cf. PROTO-SYNC.md).",
        "",
        "namespace Namaste3.Protocole.B%s;" % suffixe,
        "",
        "// Un champ protobuf : numéro et type sont LUS dans le dump ; Nom est le token obfusqué.",
        "// / One protobuf field; Num and Type are read from the dump, Nom is the obfuscated token.",
        "public sealed record Champ(int Num, string Type, string Nom, string Label, bool PresenceExplicite, string CleMap, string Source);",
        "",
        "// Une entrée de dispatch. Statut et Provenance portent ce qui est prouvé et par qui ;",
        "// une entrée sans eux n'a pas le droit d'exister (gate (c)).",
        "// / One dispatch entry; Statut and Provenance carry what is proven and by whom.",
        "public sealed record Entree(string Opcode, string TypeUrl, string Token, string CheminProto,",
        "    string Niveau, string NomSemantique, string Direction, string Statut, string Provenance,",
        "    string Source, int TypeDefIndex, string Assembly, Champ[] Champs);",
        "",
        "// La table elle-même : des littéraux et rien d'autre.",
        "// / The table itself: literals and nothing else.",
        "public static class Dispatch%s" % suffixe,
        "{",
        '    public const string Build = "%s";' % b,
        '    public const string Sha256Dump = "%s";' % table["source"]["sha256"],
        '    public const string PrefixeTypeUrl = "%s";' % table["prefixe_typeurl"],
        "    public static readonly Entree[] Entrees =",
        "    {",
    ]
    for e in table["entrees"]:
        champs = ", ".join(
            "new(%d, %s, %s, %s, %s, %s, %s)" % (
                c["num"], _s(c["type"]), _s(c["nom"]), _s(c["label"]),
                "true" if c["presence_explicite"] else "false", _s(c["cle_map"]), _s(c["source"]))
            for c in e["champs"])
        L.append("        new(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %d, %s, new Champ[] { %s })," % (
            _s(e["opcode"]), _s(e["type_url"]), _s(e["token_obfusque"]), _s(e["chemin_proto"]),
            _s(e["niveau"]), _s(e["nom_semantique"]), _s(e["direction"]), _s(e["statut"]),
            _s(e["provenance"]), _s(e["structure"]["source"]),
            e["structure"]["typedef_index"] or 0, _s(e["structure"]["assembly"]), champs))
    L += ["    };", "}", ""]
    with open(chemin, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))


def _s(v) -> str:
    """Littéral chaîne C# échappé. / Escaped C# string literal."""
    return '"' + str(v or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


# ── Gate ──────────────────────────────────────────────────────────────────────

def verifier(table: dict, chemin_cs: str, chemin_dump: str, bavard=False) -> bool:
    """Joue les quatre barrières et refuse NOMMÉMENT. / Runs the four barriers, refusing by name."""
    refus = []
    second = compter_par_grep(chemin_dump)
    if table["mesures"]["entrees"] != second["messages"]:
        refus.append("compte d'entrées : %d dans la table, %d au second chemin (grep)"
                     % (table["mesures"]["entrees"], second["messages"]))
    if table["mesures"]["champs"] != second["champs"]:
        refus.append("compte de champs : %d dans la table, %d au second chemin (grep)"
                     % (table["mesures"]["champs"], second["champs"]))
    sans = [e["token_obfusque"] for e in table["entrees"]
            if not e.get("provenance") or not e.get("statut")]
    if sans:
        refus.append("%d entrées sans provenance ou sans statut : %s" % (len(sans), sans[:5]))
    refus += _unicite(table)
    logique = _logique_dans_cs(chemin_cs)
    if logique:
        refus.append("le .cs généré contient de la logique : %s" % ", ".join(sorted(logique)))
    if bavard:
        print("second chemin (grep) : %d messages, %d champs" % (second["messages"], second["champs"]))
        for r in refus:
            print("REFUS : " + r, file=sys.stderr)
        print("GATE generer_dispatch : " + ("🟢 VERTE" if not refus else "🔴 ROUGE (%d refus)" % len(refus)))
    return not refus


def _unicite(table: dict) -> list:
    """Un opcode ou un nom sémantique qui désigne deux entrées cesse d'être une clé.
    / An opcode or semantic name pointing at two entries stops being a key."""
    refus, vus_op, vus_nom = [], {}, {}
    for e in table["entrees"]:
        if e["opcode"]:
            vus_op.setdefault(e["opcode"], []).append(e["token_obfusque"])
        if e["nom_semantique"]:
            vus_nom.setdefault(e["nom_semantique"], []).append(e["opcode"])
    for k, v in sorted(vus_op.items()):
        if len(v) > 1:
            refus.append("opcode %s porté par %d entrées" % (k, len(v)))
    for k, v in sorted(vus_nom.items()):
        if len(v) > 1:
            refus.append("nom sémantique %s porté par %d opcodes : %s" % (k, len(v), v))
    return refus


def _logique_dans_cs(chemin: str) -> set:
    """Cherche des mots-clés de contrôle dans le C# généré : la table doit rester une donnée.
    / Looks for control keywords in the generated C#: the table must stay data."""
    if not os.path.exists(chemin):
        return {"fichier absent"}
    trouves = set()
    with open(chemin, encoding="utf-8") as fh:
        for l in fh:
            nu = l.split("//")[0]
            for mot in MOTS_LOGIQUE:
                if re.search(mot, nu):
                    trouves.add(mot.strip("\\b"))
    return trouves


if __name__ == "__main__":
    sys.exit(main())
