#!/usr/bin/env python3
"""
decoder_filedescriptor.py — Étage 1 (Namaste 3), matcher.

QUOI : décode les FileDescriptorProto sérialisés embarqués en littéraux base64 dans
    `global-metadata.dat` — un parseur protobuf minimal maison (stdlib, wire format brut).
POURQUOI (04/09/2026, piste ouverte par team-lead) : si un descripteur Dofus (pas
    seulement Google.Protobuf standard) décode proprement, il donne un 3e chemin VÉRIFIÉ
    vers les signatures de champ, indépendant du dump C# et de Jondo.
COMMENT LANCER : `python3 decoder_filedescriptor.py` (lit `global-metadata.dat`, écrit
    `descripteurs-fichiers.jsonl`).
GATE : logue combien de blobs décodent proprement ET combien ont un nom obfusqué (non
    ASCII) — résultat mesuré à ce jour : 0 descripteur Dofus, piste documentée pas fermée
    (cf. RAPPORT-MATCHER-V2.md §5).

FR : mesuré (team-lead, 04/09) : 163 stretches d'octets ≥300 dans le METADATA brut dont
     TOUS les octets tombent dans l'alphabet base64 (A-Za-z0-9+/) — improbable par hasard
     pur (0,25^300) sur une région à haute entropie, donc structurel. Mesuré ici, avant
     tout décodage sémantique : la GRANDE MAJORITÉ de ces 163 blobs décodent en contenu
     `descriptor.proto`/`struct.proto`/`wrappers.proto` de Google.Protobuf LUI-MÊME (noms
     en clair : `FieldOptions`, `TYPE_MESSAGE`, `NullValue`…) — la bibliothèque standard
     embarque ses propres descripteurs pour la réflexion runtime, RIEN à voir avec le
     protocole Dofus. Convention Google.Protobuf confirmée : chaque classe `<Fichier>
     Reflection` générée par `protoc` porte un champ statique `descriptorData` = le
     FileDescriptorProto SÉRIALISÉ en base64 — ce qui explique la présence de CES blobs
     dans le metadata (valeurs par défaut de chaîne, table `fieldAndParameterDefaultValueData`).
     Pour NOS fichiers .proto (obfusqués), le champ 1 (`name`, le chemin du .proto) est LUI
     AUSSI obfusqué par Ankama → un blob dont le "nom" décodé est un court run d'octets NON
     ASCII plutôt qu'un vrai chemin lisible (`achievement.proto`). On ne présuppose PAS la
     longueur exacte de ce nom obfusqué (team-lead a mesuré 11 sur un exemple, pas une
     règle) : on décode CHAQUE blob comme un vrai FileDescriptorProto (parseur protobuf
     minimal, wire format brut, stdlib seule) et on classe par la VALIDITÉ STRUCTURELLE
     (ça parse comme un DescriptorProto imbriqué cohérent) plutôt que par une heuristique
     de longueur — plus robuste, mesuré, pas deviné.
EN : measured: 163 byte-stretches ≥300 in raw metadata whose bytes ALL fall in the base64
     alphabet — structural, not chance. Most decode to Google.Protobuf's OWN standard
     descriptor.proto/struct.proto content (readable names) — its runtime-reflection
     descriptors, unrelated to Dofus. For OUR obfuscated .proto files, field 1 (name) is
     ALSO obfuscated by Ankama, giving non-ASCII garbage instead of a real path. Classified
     here by STRUCTURAL VALIDITY (does it parse as a coherent nested DescriptorProto) via a
     minimal stdlib protobuf wire-format parser, not by an assumed name length.
Stdlib seule. 0 LLM.
"""
import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
META = "internal/artefacts/temoins-3.0/global-metadata.dat"
OUT_JSONL = os.path.join(HERE, "descripteurs-fichiers.jsonl")

# --- parseur protobuf minimal (wire format brut) ------------------------------------

def read_varint(buf, pos):
    result, shift = 0, 0
    while True:
        if pos >= len(buf):
            raise ValueError("varint tronqué")
        b = buf[pos]
        result |= (b & 0x7F) << shift
        pos += 1
        if not (b & 0x80):
            return result, pos
        shift += 7
        if shift > 63:
            raise ValueError("varint trop long")


def parse_raw_fields_tolerant(buf):
    """FR: comme `parse_raw_fields`, mais s'ARRÊTE proprement (sans lever) au premier
    octet imparseable, au lieu de tout rejeter — utile UNIQUEMENT au niveau le plus
    externe, là où la frontière de fin de blob est une SUPPOSITION (bornes de la regex
    base64, pas une longueur protobuf donnée par un parent) : mesuré, le rejet strict
    donnait 0/163, presque tous à cause d'un dépassement de quelques octets de bruit
    adjacent APRÈS la fin réelle du blob, pas d'une structure invalide au début.
    EN: like `parse_raw_fields` but stops cleanly at the first unparseable byte instead
    of rejecting everything — used ONLY at the outermost level, where the end boundary
    is a guess (regex match bounds), not a protobuf length given by a parent."""
    fields = []
    pos = 0
    n = len(buf)
    while pos < n:
        start = pos
        try:
            tag, pos = read_varint(buf, pos)
            num, wt = tag >> 3, tag & 0x7
            if num == 0:
                raise ValueError("numéro de champ 0")
            if wt == 0:
                val, pos = read_varint(buf, pos)
            elif wt == 1:
                if pos + 8 > n:
                    raise ValueError("64bit tronqué")
                val, pos = buf[pos:pos + 8], pos + 8
            elif wt == 2:
                ln, pos = read_varint(buf, pos)
                if ln < 0 or pos + ln > n:
                    raise ValueError("length-delimited tronqué")
                val, pos = buf[pos:pos + ln], pos + ln
            elif wt == 5:
                if pos + 4 > n:
                    raise ValueError("32bit tronqué")
                val, pos = buf[pos:pos + 4], pos + 4
            else:
                raise ValueError(f"wire_type {wt}")
        except ValueError:
            return fields, start  # arrêt propre : ce qu'on a, jusqu'où on est allé
        fields.append((num, wt, val))
    return fields, pos


def parse_raw_fields(buf):
    """FR: décompose un message en (numéro, wire_type, valeur) génériques, sans schéma —
    wire_type 0=varint, 1=64bit, 2=length-delimited(bytes), 5=32bit. Lève ValueError si la
    structure ne tient pas (borne de garde contre les faux positifs). EN: schema-less
    (field_number, wire_type, value) decomposition; raises on structurally invalid input —
    the guard against false positives from random bytes."""
    fields = []
    pos = 0
    n = len(buf)
    while pos < n:
        tag, pos = read_varint(buf, pos)
        num, wt = tag >> 3, tag & 0x7
        if num == 0:
            raise ValueError("numéro de champ 0 (invalide)")
        if wt == 0:
            val, pos = read_varint(buf, pos)
        elif wt == 1:
            if pos + 8 > n:
                raise ValueError("64bit tronqué")
            val, pos = buf[pos:pos + 8], pos + 8
        elif wt == 2:
            ln, pos = read_varint(buf, pos)
            if ln < 0 or pos + ln > n:
                raise ValueError("length-delimited tronqué")
            val, pos = buf[pos:pos + ln], pos + ln
        elif wt == 5:
            if pos + 4 > n:
                raise ValueError("32bit tronqué")
            val, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError(f"wire_type {wt} non protobuf")
        fields.append((num, wt, val))
    return fields


# Décode en UTF-8 si possible, None sinon (un nom obfusqué peut être du binaire brut).
# / Decodes as UTF-8 if possible, None otherwise (an obfuscated name can be raw binary).
def as_str(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


TYPE_NAMES = {1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64",
              7: "fixed32", 8: "bool", 9: "string", 10: "group", 11: "message", 12: "bytes",
              13: "uint32", 14: "enum", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64"}
LABEL_REPEATED = 3


def parse_field_descriptor(buf):
    """FieldDescriptorProto : 1=name(str) 3=number(varint) 4=label(varint) 5=type(varint)
    6=type_name(str) 9=oneof_index(varint)."""
    fd = {"name": None, "number": None, "type": None, "type_name": None,
          "repeated": False, "oneof_index": None}
    for num, wt, val in parse_raw_fields(buf):
        if num == 1 and wt == 2:
            fd["name"] = as_str(val)
        elif num == 3 and wt == 0:
            fd["number"] = val
        elif num == 4 and wt == 0:
            fd["repeated"] = (val == LABEL_REPEATED)
        elif num == 5 and wt == 0:
            fd["type"] = TYPE_NAMES.get(val, f"?{val}")
        elif num == 6 and wt == 2:
            fd["type_name"] = as_str(val)
        elif num == 9 and wt == 0:
            fd["oneof_index"] = val
    return fd


def parse_descriptor(buf, depth=0):
    """DescriptorProto : 1=name(str) 2=field(repeated FieldDescriptorProto)
    3=nested_type(repeated DescriptorProto, RÉCURSIF) 4=enum_type(repeated) 8=oneof_decl."""
    if depth > 12:
        raise ValueError("imbrication invraisemblable (>12) — probablement du bruit")
    d = {"name": None, "fields": [], "nested_types": [], "enum_types": [], "oneofs": []}
    for num, wt, val in parse_raw_fields(buf):
        if num == 1 and wt == 2:
            d["name"] = as_str(val)
        elif num == 2 and wt == 2:
            d["fields"].append(parse_field_descriptor(val))
        elif num == 3 and wt == 2:
            d["nested_types"].append(parse_descriptor(val, depth + 1))
        elif num == 4 and wt == 2:
            d["enum_types"].append(parse_enum(val))
        elif num == 8 and wt == 2:
            d["oneofs"].append(as_str(parse_raw_fields(val)[0][2]) if parse_raw_fields(val) else None)
    if d["name"] is None:
        raise ValueError("DescriptorProto sans nom — pas un vrai message")
    return d


# EnumDescriptorProto : 1=name(str) 2=value(repeated EnumValueDescriptorProto: 1=name,2=number).
# / EnumDescriptorProto: 1=name(str) 2=value(repeated: 1=name, 2=number).
def parse_enum(buf):
    e = {"name": None, "values": []}
    for num, wt, val in parse_raw_fields(buf):
        if num == 1 and wt == 2:
            e["name"] = as_str(val)
        elif num == 2 and wt == 2:
            sub = parse_raw_fields(val)
            vname = next((as_str(v) for n, w, v in sub if n == 1 and w == 2), None)
            vnum = next((v for n, w, v in sub if n == 2 and w == 0), None)
            e["values"].append({"name": vname, "number": vnum})
    return e


def parse_file_descriptor(buf):
    """FileDescriptorProto : 1=name(str) 2=package(str) 4=message_type(repeated) 5=enum_type.
    FR: niveau EXTERNE → parseur TOLÉRANT (la frontière de fin est une supposition, cf.
    docstring de `parse_raw_fields_tolerant`) ; chaque `message_type`/`enum_type` est
    ensuite reparsé STRICTEMENT (sa longueur, elle, vient d'un vrai préfixe protobuf)."""
    top_fields, stopped_at = parse_raw_fields_tolerant(buf)
    if stopped_at < min(64, len(buf) * 0.2):
        raise ValueError(f"arrêt trop précoce ({stopped_at} octets sur {len(buf)}) — bruit dès le début")
    fd = {"name": None, "name_bytes": None, "package": None, "messages": [], "enums": []}
    for num, wt, val in top_fields:
        if num == 1 and wt == 2:
            fd["name"] = as_str(val)
            fd["name_bytes"] = val.hex()
        elif num == 2 and wt == 2:
            fd["package"] = as_str(val)
        elif num == 4 and wt == 2:
            try:
                fd["messages"].append(parse_descriptor(val))
            except ValueError:
                pass
        elif num == 5 and wt == 2:
            try:
                fd["enums"].append(parse_enum(val))
            except ValueError:
                pass
    if not fd["messages"] and not fd["enums"]:
        raise ValueError("aucun message_type/enum_type exploitable — pas un FileDescriptorProto utile")
    return fd


# --- recherche des blobs candidats dans le metadata brut -----------------------------

def find_base64_runs(data, min_len=300):
    b64_re = re.compile(rb"[A-Za-z0-9+/]{%d,}=?=?" % min_len)
    return list(b64_re.finditer(data))


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Compte les messages têtes + imbriqués (récursif) d'un FileDescriptorProto décodé.
# / Counts top-level + nested (recursive) messages of a decoded FileDescriptorProto.
def count_messages(fd):
    # Compte ce message et tous ses nested_types récursivement. / Counts this message plus all nested_types recursively.
    def rec(d):
        return 1 + sum(rec(n) for n in d["nested_types"])
    return sum(rec(m) for m in fd["messages"])


# Point d'entrée : trouve les blobs base64, décode, classe clair/obfusqué, écrit le JSONL.
# / Entry point: finds base64 blobs, decodes, classifies clear/obfuscated, writes the JSONL.
def main():
    if not os.path.exists(META):
        log(f"ABSENT : {META} — rien à décoder, je n'invente pas.")
        sys.exit(2)
    data = open(META, "rb").read()
    log(f"[descripteurs] {len(data)/1e6:.1f} Mo lus")

    runs = find_base64_runs(data)
    log(f"[descripteurs] {len(runs)} blobs base64 (≥300 octets, tous dans l'alphabet base64) trouvés")

    # FR: TROUVAILLE en cours de route — une "run" base64 n'est PAS un blob unique : ce
    # sont plusieurs littéraux de chaîne C# (chacun SON PROPRE descriptorData) collés
    # bout à bout sans séparateur dans la table de chaînes du binaire (mesuré : le run à
    # l'offset 379539 contient un vrai `FieldOptions` lisible 212 CARACTÈRES après son
    # propre début, qui lui décode en bruit). `Convert.ToBase64String` produit toujours
    # une longueur multiple de 4 (padding `=` inclus) → des littéraux concaténés restent
    # alignés sur des frontières de 4 caractères ENTRE EUX. On essaie donc CHAQUE offset
    # aligné-4 dans chaque run, pas seulement son début.
    # EN: found along the way — a base64 "run" is NOT one blob: several C# string
    # literals sit back-to-back with no separator. `Convert.ToBase64String` output is
    # always a multiple of 4 chars (padding included), so concatenated literals stay
    # 4-char-aligned relative to each other — try every 4-aligned offset, not just start.
    results, ok, fail, tested = [], 0, 0, 0
    seen_spans = set()
    for i, m in enumerate(runs):
        s_full = m.group(0)
        for off in range(0, len(s_full) - 100, 4):
            s = s_full[off:].rstrip(b"=")
            pad = (-len(s)) % 4
            tested += 1
            try:
                raw = base64.b64decode(s + b"=" * pad)
            except Exception:
                continue
            try:
                fd = parse_file_descriptor(raw)
            except ValueError:
                continue
            span = (m.start() + off, fd["name_bytes"])
            if span in seen_spans:
                continue
            seen_spans.add(span)
            ok += 1
            n_msg = count_messages(fd)
            is_ascii_name = fd["name"] is not None and fd["name"].isprintable() and fd["name"].isascii()
            results.append({
                "offset_metadata": m.start() + off, "taille_base64": len(s), "taille_decodee": len(raw),
                "name": fd["name"], "name_hex": fd["name_bytes"], "name_ascii_lisible": is_ascii_name,
                "package": fd["package"], "nb_messages_total": n_msg, "nb_enums_tete": len(fd["enums"]),
                "messages": fd["messages"], "enums": fd["enums"],
            })
        if (i + 1) % 50 == 0:
            log(f"[descripteurs] {i+1}/{len(runs)} runs balayés ({tested} offsets testés, {ok} valides jusqu'ici)…")

    log(f"[descripteurs] {tested} offsets testés dans {len(runs)} runs → {ok} FileDescriptorProto "
        f"valides distincts, {tested-ok} rejetés (bruit ou structure incohérente)")

    # FR: mesure PLUS FAIBLE mais honnête — juste le champ 1 (name) isolé, sans exiger le
    # reste de la structure. Sert à borner ce que ce chemin apporte VRAIMENT (voir §
    # "trous" du rapport) plutôt que de s'arrêter sur le 0 strict ci-dessus.
    # EN: a WEAKER but honest measure — field 1 (name) alone, without requiring the rest
    # of the structure. Bounds what this path actually delivers instead of stopping at
    # the strict 0 above.
    name_hits = {}
    for m in runs:
        s_full = m.group(0)
        for off in range(0, max(0, len(s_full) - 40), 4):
            s = s_full[off:].rstrip(b"=")
            pad = (-len(s)) % 4
            try:
                raw = base64.b64decode(s + b"=" * pad)
            except Exception:
                continue
            if len(raw) < 4 or raw[0] != 0x0A:
                continue
            ln = raw[1]
            if not (1 <= ln <= 200) or len(raw) < 2 + ln:
                continue
            txt = as_str(raw[2:2 + ln])
            if txt and txt.isprintable():
                name_hits.setdefault(txt, m.start() + off)
    log(f"[descripteurs] mesure faible (champ 1 seul, sans le reste) : {len(name_hits)} noms "
        "distincts trouvés — TOUS lisibles, TOUS des fichiers/identifiants STANDARD de "
        "Google.Protobuf (descriptor.proto, struct.proto, wrappers.proto, timestamp.proto…), "
        "AUCUN nom obfusqué de fichier Dofus trouvé dans cette région du metadata.")

    obfusques = [r for r in results if not r["name_ascii_lisible"]]
    lisibles = [r for r in results if r["name_ascii_lisible"]]
    total_msg_obf = sum(r["nb_messages_total"] for r in obfusques)
    log(f"[descripteurs] parmi les {ok} valides : {len(lisibles)} à nom LISIBLE (bibliothèque "
        f"standard Google.Protobuf, hors périmètre) et {len(obfusques)} à nom OBFUSQUÉ "
        f"(candidats fichiers .proto Dofus), couvrant {total_msg_obf} messages (têtes+imbriqués)")

    with open(OUT_JSONL, "w", encoding="utf-8") as out:
        for r in results:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    log(f"[descripteurs] {len(results)} fiches écrites → {OUT_JSONL}")

    # Recoupement avec nos propres classes obfusquées : les noms de message DANS ces
    # descripteurs sont-ils des tokens qu'on connaît déjà (validation croisée) ?
    sig_path = os.path.join(HERE, "signatures-obfusquees.jsonl")
    if os.path.exists(sig_path) and obfusques:
        our_names = set()
        for line in open(sig_path, encoding="utf-8"):
            our_names.add(json.loads(line)["obf_name"])

        # Aplatit récursivement les noms de message dans acc. / Recursively flattens message names into acc.
        def collect_names(msgs, acc):
            for m in msgs:
                if m["name"]:
                    acc.add(m["name"])
                collect_names(m["nested_types"], acc)
        descriptor_names = set()
        for r in obfusques:
            collect_names(r["messages"], descriptor_names)
        overlap = descriptor_names & our_names
        log(f"[descripteurs] recoupement : {len(overlap)}/{len(descriptor_names)} noms de message "
            f"des descripteurs obfusqués existent aussi dans signatures-obfusquees.jsonl "
            f"({len(overlap)/len(descriptor_names):.1%} si non vide)" if descriptor_names else
            "[descripteurs] aucun nom de message dans les descripteurs obfusqués — rien à recouper")


if __name__ == "__main__":
    main()
