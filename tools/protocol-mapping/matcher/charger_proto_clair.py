#!/usr/bin/env python3
"""
charger_proto_clair.py — Étage 1 (Namaste 3), matcher v2.

QUOI : construit le graphe CLAIR complet (numéros de champ + types + imbrication +
    oneof/repeated/map) depuis PLUSIEURS provenances indépendantes (Jondo anclas+.proto,
    otomai, gatherer, luaxy). Écrit `signatures-claires.jsonl`.
POURQUOI (04/09/2026, correction team-lead) : v1 comparait des noms clairs SANS aucun
    champ (asymétrie) — ce script donne enfin un second graphe complet, symétrique à
    `signatures-obfusquees.jsonl`, pour que `matcher_v2.py` fasse du vrai matching
    structurel (numéro+type), pas seulement de la forme d'imbrication.
COMMENT LANCER : `python3 charger_proto_clair.py` (lit les .proto/.tsv listés ci-dessous,
    écrit `signatures-claires.jsonl`).
GATE : logue le nombre de noms clairs par provenance et le taux d'accord du nombre de
    champs entre provenances qui se recoupent — un chiffre qui chute signale une
    provenance cassée ou absente.

FR : correction de team-lead (04/09) sur la consigne « Jondo jamais en entrée » — elle
     valait pour la VALIDATION d'un matcher à une seule source (v1) ; avec un second
     graphe COMPLET, l'algorithme de Jondo (a.1 de la spec) s'applique enfin des DEUX
     côtés. Mesuré AVANT d'écrire ce script (pas supposé) :
     - `datos/protocolo_3.6.10.10.proto` (Jondo) : 2169 messages, mais ses NOMS DE
       MESSAGE sont des tokens OBFUSQUÉS (`message hex {...}`), PAS des noms clairs —
       contredit la lecture littérale de la consigne ; seuls 99 tokens ont un nom clair
       PROPOSÉ (pas extrait) via `anclas_3.6.10.10.tsv`. Champs VÉRIFIÉS fiables :
       100% d'accord de NUMÉROS de champ et 97,3% d'accord de CATÉGORIE (scalaire/
       référence) avec notre propre dump indépendant (mesuré sur les 2169 tokens
       partagés) — l'écart s'explique presque entièrement par les `oneof` (Jondo résout
       le type de CHAQUE variante via les Properties, notre dump ne voit que le champ
       `object` partagé) : validation forte, pas une hypothèse.
     - `index/protocole-otomai.tsv` (BubbleBot/otomai, réimplémentation communautaire) :
       **1285 noms CLAIRS** avec numéros+types+imbrication COMPLETS — la vraie source de
       noms clairs riches, bien plus que Jondo (99). Provenance marquée `otomai` — c'est
       une RÉIMPLÉMENTATION, pas une extraction du binaire : sa fiabilité n'est PAS
       supposée égale à Jondo/notre dump, mesurée à part (accord inter-provenances, §
       matcher_v2.py).
     - `index/protocole-{gatherer,deobfs,luaxy}.tsv` : ABSENTS au moment du run (mesuré,
       pas deviné) — chargés SI présents, silence explicite sinon.
EN : team-lead's correction — "never Jondo as input" applied to single-source validation
     (v1); with a second COMPLETE graph, real WL matching finally applies both sides.
     Measured before writing this script: Jondo's .proto message NAMES are obfuscated
     tokens, not clear names (only 99 have a Jondo-proposed clear name via anclas.tsv);
     otomai's TSV is the real rich clear-name source (1285 names, full field data).
Stdlib seule. 0 LLM.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(os.path.dirname(HERE), "index")
JONDO_PROTO = "refs/JondoEmu/datos/protocolo_3.6.10.10.proto"
JONDO_CONEXION_PROTO = "refs/JondoEmu/datos/protocolo_conexion_3.6.10.10.proto"
JONDO_ANCLAS = "refs/JondoEmu/datos/anclas_3.6.10.10.tsv"
OTOMAI_TSV = os.path.join(INDEX_DIR, "protocole-otomai.tsv")
THIRD_PARTY_TSVS = ["protocole-gatherer.tsv", "protocole-deobfs.tsv", "protocole-luaxy.tsv"]
OUT_JSONL = os.path.join(HERE, "signatures-claires.jsonl")

MSG_RE = re.compile(r"^message (\w+) \{$")
FIELD_RE = re.compile(r"^\s*(repeated\s+)?(map<[^>]+>|\S+)\s+(\w+)\s*=\s*(\d+);")
CLOSE_RE = re.compile(r"^\}$")


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


def parse_jondo_proto(path):
    """FR: `message TOKEN { [repeated] TYPE nom = N; ... }` — un bloc par classe
    obfusquée. EN: one block per obfuscated class."""
    if not os.path.exists(path):
        return {}
    messages = {}
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = MSG_RE.match(line)
            if m:
                cur = {"name": m.group(1), "fields": []}
                continue
            if cur is not None:
                fm = FIELD_RE.match(line)
                if fm:
                    repeated, typ, name, num = fm.groups()
                    is_map = typ.startswith("map<")
                    cur["fields"].append({"number": int(num), "raw_type": typ,
                                           "repeated": bool(repeated) or is_map,
                                           "is_map": is_map, "field_name": name})
                    continue
                if CLOSE_RE.match(line):
                    messages[cur["name"]] = cur["fields"]
                    cur = None
    return messages


def load_anclas(path):
    """opcode → nom proposé (99/293 non vides)."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 3 and cols[0] and cols[2].strip():
                rows[cols[0]] = cols[2].strip()
    return rows


LIST_RE = re.compile(r"^List<(.+)>$")
# FR: bug trouvé et corrigé — gatherer/luaxy écrivent leurs champs en convention
# protobuf (`int32`,`bool`,`uint64`…) alors qu'otomai écrit en convention C# (`int`,
# `long`) ; un ensemble ne couvrant QUE l'une des deux classait `int32`/`int64` comme
# "référence" par défaut → `matcher_v3.py` produisait des noms clairs `int32`/`int64`
# (15+7 occurrences mesurées) au lieu d'un vrai nom de message. EN: bug found — gatherer/
# luaxy use protobuf-style scalar names, otomai uses C#-style; a set covering only one
# wrongly classified protobuf scalars as "reference", producing fake clear names.
OTOMAI_SCALARS = {"string", "int", "long", "bool", "float", "double", "byte", "short",
                   "uint", "ulong", "sbyte", "ushort", "DateTime", "Guid",
                   "int32", "int64", "uint32", "uint64", "sint32", "sint64",
                   "fixed32", "fixed64", "sfixed32", "sfixed64", "bytes"}

# FR: trouvaille en cours de route — le nom court PEUT être un vrai mot anglais par pure
# coïncidence (`Ride`) alors que SES CHAMPS restent des tokens obfusqués (`ebko`,`ebkp`) :
# otomai (réimplémentation communautaire) n'a pas fini de renommer TOUS ses types
# imbriqués — certains gardent le nom obfusqué (parfois capitalisé, ex. `Hio`, `Jio`) et
# des champs `eXXX` non résolus. Le nom seul ment ; les CHAMPS ne mentent pas : un champ
# obfusqué ressemble à ceci (mesuré) : tout minuscule, 3-6 lettres, ni underscore ni
# majuscule interne, alors qu'un champ réel est `snake_case` ou `camelCase` lisible.
# EN: found along the way — the short name can be a real English word by pure
# coincidence (`Ride`) while its OWN fields stay obfuscated tokens — otomai hasn't
# finished renaming every nested type. The name alone lies; the FIELD NAMES don't.
OBF_FIELD_RE = re.compile(r"^[a-z]{3,6}$")


def champs_semblent_obfusques(fields, seuil=0.6):
    """FR: proportion de noms de champ à la FORME d'un token obfusqué ; True si ≥ seuil
    ET au moins 1 champ (jamais vrai sur une fiche vide, silencieusement). EN: fraction
    of field names shaped like an obfuscated token; True only if ≥ threshold AND ≥1 field."""
    named = [f["field_name"] for f in fields if f.get("field_name")]
    if not named:
        return False
    opaque = sum(1 for n in named if OBF_FIELD_RE.match(n))
    return (opaque / len(named)) >= seuil


# Parse un segment "numéro:type:nom" du format otomai/gatherer/luaxy ; None si malformé.
# / Parses one "number:type:name" segment of the otomai/gatherer/luaxy format; None if malformed.
def parse_otomai_champ(spec):
    parts = spec.split(":", 2)
    if len(parts) != 3:
        return None
    num_s, typ, name = parts
    try:
        num = int(num_s)
    except ValueError:
        return None
    repeated = False
    lm = LIST_RE.match(typ)
    if lm:
        repeated, typ = True, lm.group(1)
    # FR: bug trouvé et corrigé (v4) — gatherer/luaxy écrivent AUSSI le répété en
    # convention protobuf directe (`repeated int32`), pas seulement `List<int>` (otomai).
    # Sans ce dépouillement, "repeated int32" restait le type LITTÉRAL, tombait hors de
    # OTOMAI_SCALARS → classé "reference" à tort → une fausse "clear_name" `repeated
    # int32` a fini dans correspondance-v4.tsv (mesuré, 1 occurrence, `len`/f14). EN: bug
    # found — gatherer/luaxy also write "repeated int32" directly (not just List<int>);
    # without stripping it, the literal string leaked through as a fake clear name.
    if typ.startswith("repeated "):
        repeated, typ = True, typ[len("repeated "):].strip()
    kind = "scalar" if typ in OTOMAI_SCALARS else "reference"
    return {"number": num, "raw_type": typ, "repeated": repeated,
            "field_name": name, "resolved_kind": kind}


def load_otomai(path):
    """FR: `nom_message_clair, nom_complet, opcode_ou_typeurl, direction, champs,
    fichier:ligne` — nom_complet porte l'imbrication (`Outer+Types+Inner` façon .NET,
    ou `Outer+Inner` chez otomai, mesuré : PAS de segment `Types` intermédiaire ici,
    convention différente de notre dump — noté, pas uniformisé de force)."""
    entries = {}
    if not os.path.exists(path):
        return entries
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader, None)
        for row in reader:
            if len(row) < 6:
                continue
            short_name, full_name, opcode, direction, champs, loc = row[:6]
            fields = []
            if champs.strip():
                for spec in champs.split(";"):
                    spec = spec.strip()
                    if not spec:
                        continue
                    f = parse_otomai_champ(spec)
                    if f:
                        fields.append(f)
            entries[short_name] = {
                "full_name": full_name, "opcode": opcode or None,
                "direction": direction or None, "fields": fields, "source_loc": loc,
            }
    return entries


def build_signatures(jondo_msgs, jondo_conexion_msgs, anclas, otomai, extra_provenances):
    """FR: une fiche PAR NOM CLAIR connu (union otomai ∪ noms proposés Jondo ∪ tiers),
    chacune portant la liste des provenances qui la nomment, chacune avec SA propre
    signature de champs. Le token obfusqué Jondo (`kfp`, `jru`…) est joint QUAND
    disponible (via anclas) — jamais fabriqué. EN: one record per known clear name
    (union across all provenances), each carrying every provenance's own field
    signature; the Jondo obfuscated token is attached only when anclas actually names it."""
    all_jondo = dict(jondo_msgs)
    all_jondo.update(jondo_conexion_msgs)

    records = {}

    for short_name, entry in otomai.items():
        rec = records.setdefault(short_name, {"clear_name": short_name, "provenances": []})
        rec["provenances"].append({
            "provenance": "otomai", "full_name": entry["full_name"],
            "opcode_or_typeurl": entry["opcode"], "direction": entry["direction"],
            "field_count": len(entry["fields"]), "fields": entry["fields"],
            "source": entry["source_loc"],
            "champs_semblent_obfusques": champs_semblent_obfusques(entry["fields"]),
        })

    for opcode, clear_name in anclas.items():
        jondo_fields = all_jondo.get(opcode)
        rec = records.setdefault(clear_name, {"clear_name": clear_name, "provenances": []})
        rec["provenances"].append({
            "provenance": "jondo-proto", "obf_token": opcode,
            "field_count": len(jondo_fields) if jondo_fields is not None else None,
            "fields": jondo_fields if jondo_fields is not None else [],
            "source": f"{JONDO_ANCLAS} + {JONDO_PROTO}",
            "note": None if jondo_fields is not None else
                    "opcode nommé par anclas.tsv mais absent du .proto (top-niveau connexion, hors "
                    "protocolo_3.6.10.10.proto — cf. protocolo_conexion)",
        })

    for name, provs in extra_provenances.items():
        rec = records.setdefault(name, {"clear_name": name, "provenances": []})
        rec["provenances"].extend(provs)

    for rec in records.values():
        provs = rec["provenances"]
        rec["nb_provenances"] = len(provs)
        if len(provs) >= 2:
            counts = sorted({p["field_count"] for p in provs if p["field_count"] is not None})
            rec["accord_nb_champs"] = (len(counts) == 1) if counts else None
        else:
            rec["accord_nb_champs"] = None
        # FR: le nom est suspect si TOUTES les provenances qui se prononcent (celles qui
        # portent des champs nommés) le disent obfusqué — jamais sur une seule voix
        # minoritaire. EN: suspect only if EVERY provenance with an opinion agrees.
        opinions = [p.get("champs_semblent_obfusques") for p in provs
                    if p.get("champs_semblent_obfusques") is not None]
        rec["nom_clair_suspect"] = bool(opinions) and all(opinions)
    return records


# Point d'entrée : charge toutes les provenances, fusionne, écrit signatures-claires.jsonl.
# / Entry point: loads every provenance, merges, writes signatures-claires.jsonl.
def main():
    for name, path in (("jondo .proto", JONDO_PROTO), ("otomai tsv", OTOMAI_TSV),
                        ("anclas tsv", JONDO_ANCLAS)):
        if not os.path.exists(path):
            log(f"ABSENT : {name} → {path} — je n'invente pas, je continue avec ce qui existe.")

    jondo_msgs = parse_jondo_proto(JONDO_PROTO)
    jondo_conexion_msgs = parse_jondo_proto(JONDO_CONEXION_PROTO)
    log(f"[proto-clair] jondo .proto (jeu) : {len(jondo_msgs)} messages, "
        f"(connexion) : {len(jondo_conexion_msgs)} messages")

    anclas = load_anclas(JONDO_ANCLAS)
    log(f"[proto-clair] anclas : {len(anclas)}/293 opcodes nommés")

    otomai = load_otomai(OTOMAI_TSV)
    log(f"[proto-clair] otomai : {len(otomai)} noms clairs chargés depuis {OTOMAI_TSV}")

    extra_provenances = {}
    for fname in THIRD_PARTY_TSVS:
        path = os.path.join(INDEX_DIR, fname)
        if os.path.exists(path):
            loaded = load_otomai(path)  # même format tabulaire attendu, réutilise le parseur
            for name, entry in loaded.items():
                extra_provenances.setdefault(name, []).append({
                    "provenance": fname.replace("protocole-", "").replace(".tsv", ""),
                    "full_name": entry["full_name"], "opcode_or_typeurl": entry["opcode"],
                    "direction": entry["direction"], "field_count": len(entry["fields"]),
                    "fields": entry["fields"], "source": entry["source_loc"],
                    "champs_semblent_obfusques": champs_semblent_obfusques(entry["fields"]),
                })
            log(f"[proto-clair] {fname} : {len(loaded)} noms clairs chargés (provenance supplémentaire)")
        else:
            log(f"[proto-clair] {fname} : ABSENT (pas encore écrit ailleurs dans le projet) — ignoré, pas inventé")

    records = build_signatures(jondo_msgs, jondo_conexion_msgs, anclas, otomai, extra_provenances)
    log(f"[proto-clair] {len(records)} noms clairs distincts au total (union de toutes les provenances)")
    suspects = sum(1 for r in records.values() if r["nom_clair_suspect"])
    log(f"[proto-clair] {suspects}/{len(records)} noms marqués SUSPECTS (champs internes "
        "encore obfusqués malgré un nom court parfois lisible par coïncidence, ex. `Ride` "
        "-> champs `ebko`,`ebkp`… — otomai n'a pas fini de renommer tous ses types imbriqués)")

    multi = [r for r in records.values() if r["nb_provenances"] >= 2]
    log(f"[proto-clair] {len(multi)} noms clairs portés par ≥2 provenances "
        f"(recoupement possible) sur {len(records)}")
    if multi:
        accord = sum(1 for r in multi if r["accord_nb_champs"])
        log(f"[proto-clair] accord du NOMBRE de champs entre provenances, sur ces {len(multi)} : "
            f"{accord}/{len(multi)} ({accord/len(multi):.1%})")

    with open(OUT_JSONL, "w", encoding="utf-8") as out:
        for name in sorted(records):
            out.write(json.dumps(records[name], ensure_ascii=False) + "\n")
    log(f"[proto-clair] {len(records)} fiches écrites → {OUT_JSONL}")


if __name__ == "__main__":
    main()
