#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI / WHAT
    Parseur protobuf STRICT en stdlib pure, typé par le schéma de `descriptor.proto`.
    A strict pure-stdlib protobuf parser, typed by the `descriptor.proto` schema.

POURQUOI / WHY  (écrit le 2026-09-05 / written 2026-09-05)
    Un lecteur protobuf ordinaire est TRÈS permissif : presque n'importe quel tas d'octets se
    laisse parser sans se plaindre, en rangeant ce qu'il ne comprend pas dans des « champs
    inconnus ». Donc « ça a parsé » ne prouve RIEN. Ce qui prouve, c'est l'aller-retour :
    re-sérialiser doit rendre les MÊMES octets. Cela n'arrive que si chaque octet de l'entrée est
    tombé dans un champ que le schéma connaît — et c'est aussi ce qui décide OÙ le bloc se termine,
    la seule donnée qui n'est écrite nulle part.
    (Méthode réimplémentée d'après Jondo.Unity.Reversing/DescriptorExtractor.cs — la MÉTHODE,
    aucune ligne de son C#.)
    A permissive reader proves nothing; the byte-identical round-trip does.

COMMENT / HOW
    - Décodage guidé par le SCHÉMA : numéro de champ inconnu ou type de fil incohérent = rejet.
    - Numéros de champ NON DÉCROISSANTS exigés : un sérialiseur protobuf réel écrit toujours
      dans l'ordre croissant ; un tas d'octets au hasard, non.
    - Varints MINIMAUX exigés : on ré-encode depuis la valeur Python, un varint rembourré tombe.
    - Chaînes : UTF-8 strict, ré-encodées depuis le `str`.
    - Les messages non modélisés (options, source_code_info) passent par un décodeur générique
      soumis aux MÊMES règles, pas par un « tampon opaque » qui rendrait l'aller-retour trivial.

GATE
    `strict_parse` rend None au moindre doute. Un témoin synthétique valide DOIT être accepté
    (sinon l'instrument est mort et son zéro ne veut rien dire) ; un octet corrompu DOIT le faire
    tomber. Éprouvé par `extraire_descripteurs.py --epreuve`.
"""

from __future__ import annotations

# ── Types de fil protobuf / protobuf wire types ────────────────────────────────────────────────
WIRE_VARINT = 0
WIRE_64 = 1
WIRE_LEN = 2
WIRE_32 = 5

# Genres de champ du schéma / schema field kinds
K_STR = "string"      # length-delimited, UTF-8 strict
K_BYTES = "bytes"     # length-delimited, opaque
K_INT = "int"         # varint
K_BOOL = "bool"       # varint 0/1
K_MSG = "msg"         # length-delimited, sous-message typé / typed submessage
K_ANY = "any"         # length-delimited, sous-message générique / generic submessage


class StrictError(Exception):
    """Rejet de décodage strict. / Strict decoding rejection."""


# ── Schéma de descriptor.proto ────────────────────────────────────────────────────────────────
# Numéros de champ recopiés de la spécification officielle de descriptor.proto (proto2),
# PAS de mémoire. / Field numbers transcribed from the official descriptor.proto spec.
# name, (genre, répété, cible)
SCHEMA: dict[str, dict[int, tuple[str, str, bool, str | None]]] = {
    "FileDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("package", K_STR, False, None),
        3: ("dependency", K_STR, True, None),
        4: ("message_type", K_MSG, True, "DescriptorProto"),
        5: ("enum_type", K_MSG, True, "EnumDescriptorProto"),
        6: ("service", K_MSG, True, "ServiceDescriptorProto"),
        7: ("extension", K_MSG, True, "FieldDescriptorProto"),
        8: ("options", K_ANY, False, None),
        9: ("source_code_info", K_ANY, False, None),
        10: ("public_dependency", K_INT, True, None),
        11: ("weak_dependency", K_INT, True, None),
        12: ("syntax", K_STR, False, None),
        13: ("edition", K_STR, False, None),
    },
    "DescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("field", K_MSG, True, "FieldDescriptorProto"),
        3: ("nested_type", K_MSG, True, "DescriptorProto"),
        4: ("enum_type", K_MSG, True, "EnumDescriptorProto"),
        5: ("extension_range", K_ANY, True, None),
        6: ("extension", K_MSG, True, "FieldDescriptorProto"),
        7: ("options", K_ANY, False, None),
        8: ("oneof_decl", K_MSG, True, "OneofDescriptorProto"),
        9: ("reserved_range", K_ANY, True, None),
        10: ("reserved_name", K_STR, True, None),
    },
    "FieldDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("extendee", K_STR, False, None),
        3: ("number", K_INT, False, None),
        4: ("label", K_INT, False, None),
        5: ("type", K_INT, False, None),
        6: ("type_name", K_STR, False, None),
        7: ("default_value", K_STR, False, None),
        8: ("options", K_ANY, False, None),
        9: ("oneof_index", K_INT, False, None),
        10: ("json_name", K_STR, False, None),
        17: ("proto3_optional", K_BOOL, False, None),
    },
    "EnumDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("value", K_MSG, True, "EnumValueDescriptorProto"),
        3: ("options", K_ANY, False, None),
        4: ("reserved_range", K_ANY, True, None),
        5: ("reserved_name", K_STR, True, None),
    },
    "EnumValueDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("number", K_INT, False, None),
        3: ("options", K_ANY, False, None),
    },
    "OneofDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("options", K_ANY, False, None),
    },
    "ServiceDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("method", K_MSG, True, "MethodDescriptorProto"),
        3: ("options", K_ANY, False, None),
    },
    "MethodDescriptorProto": {
        1: ("name", K_STR, False, None),
        2: ("input_type", K_STR, False, None),
        3: ("output_type", K_STR, False, None),
        4: ("options", K_ANY, False, None),
        5: ("client_streaming", K_BOOL, False, None),
        6: ("server_streaming", K_BOOL, False, None),
    },
}

# FieldDescriptorProto.Type — spec officielle / official spec.
PROTO_TYPE = {
    1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32", 6: "fixed64",
    7: "fixed32", 8: "bool", 9: "string", 10: "group", 11: "message", 12: "bytes",
    13: "uint32", 14: "enum", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64",
}
PROTO_LABEL = {1: "optional", 2: "required", 3: "repeated"}

_WIRE_OF_KIND = {
    K_STR: WIRE_LEN, K_BYTES: WIRE_LEN, K_MSG: WIRE_LEN, K_ANY: WIRE_LEN,
    K_INT: WIRE_VARINT, K_BOOL: WIRE_VARINT,
}


def read_varint(buf: bytes, at: int) -> tuple[int, int]:
    """Lit un varint MINIMAL. / Reads a MINIMAL varint. Rejects padded encodings."""
    value = 0
    shift = 0
    start = at
    while at < len(buf):
        if shift > 63:
            raise StrictError("varint trop long / varint too long")
        b = buf[at]
        at += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            # Un octet de continuation nul en fin = rembourrage : non minimal.
            # A trailing zero continuation byte means padding: not minimal.
            if at - start > 1 and b == 0:
                raise StrictError("varint non minimal / non-minimal varint")
            return value, at
        shift += 7
    raise StrictError("varint tronqué / truncated varint")


def write_varint(value: int) -> bytes:
    """Ré-encode un entier en varint minimal. / Minimal varint re-encoding."""
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _decode_generic(buf: bytes) -> list[tuple[int, int, object]]:
    """
    Décode un sous-message NON modélisé sous les mêmes règles strictes.
    Decodes an unmodelled submessage under the same strict rules (used for `options` etc.).
    """
    out: list[tuple[int, int, object]] = []
    at = 0
    last_field = 0
    while at < len(buf):
        key, at = read_varint(buf, at)
        field, wire = key >> 3, key & 7
        if field == 0:
            raise StrictError("numéro de champ 0 / field number 0")
        if field < last_field:
            raise StrictError("champs décroissants / decreasing field order")
        last_field = field
        if wire == WIRE_VARINT:
            val, at = read_varint(buf, at)
            out.append((field, wire, val))
        elif wire == WIRE_LEN:
            ln, at = read_varint(buf, at)
            if at + ln > len(buf):
                raise StrictError("longueur hors bloc / length past end")
            out.append((field, wire, buf[at:at + ln]))
            at += ln
        elif wire == WIRE_64:
            if at + 8 > len(buf):
                raise StrictError("fixed64 tronqué / truncated fixed64")
            out.append((field, wire, buf[at:at + 8]))
            at += 8
        elif wire == WIRE_32:
            if at + 4 > len(buf):
                raise StrictError("fixed32 tronqué / truncated fixed32")
            out.append((field, wire, buf[at:at + 4]))
            at += 4
        else:
            raise StrictError(f"type de fil interdit / forbidden wire type {wire}")
    return out


def _encode_generic(items: list[tuple[int, int, object]]) -> bytes:
    """Ré-émet un générique dans l'ordre lu. / Re-emits a generic message in read order."""
    out = bytearray()
    for field, wire, val in items:
        out += write_varint((field << 3) | wire)
        if wire == WIRE_VARINT:
            out += write_varint(val)                      # type: ignore[arg-type]
        elif wire == WIRE_LEN:
            out += write_varint(len(val)) + val           # type: ignore[arg-type]
        else:
            out += val                                    # type: ignore[operator]
    return bytes(out)


def decode(buf: bytes, kind: str) -> list[tuple[int, str, object]]:
    """
    Décode un message typé par le schéma, en gardant l'ordre du flux.
    Decodes a schema-typed message, preserving stream order (needed for the round-trip).
    """
    schema = SCHEMA[kind]
    out: list[tuple[int, str, object]] = []
    at = 0
    last_field = 0
    while at < len(buf):
        key, at = read_varint(buf, at)
        field, wire = key >> 3, key & 7
        if field not in schema:
            raise StrictError(f"champ inconnu / unknown field {field} in {kind}")
        if field < last_field:
            raise StrictError("champs décroissants / decreasing field order")
        last_field = field
        name, gk, _rep, target = schema[field]
        if wire != _WIRE_OF_KIND[gk]:
            raise StrictError(f"type de fil incohérent / wire mismatch on {kind}.{name}")
        if gk in (K_INT, K_BOOL):
            val, at = read_varint(buf, at)
            if gk == K_BOOL and val > 1:
                raise StrictError(f"bool hors 0/1 / bool out of range on {kind}.{name}")
            out.append((field, name, val))
        else:
            ln, at = read_varint(buf, at)
            if at + ln > len(buf):
                raise StrictError("longueur hors bloc / length past end")
            raw = buf[at:at + ln]
            at += ln
            if gk == K_STR:
                try:
                    out.append((field, name, raw.decode("utf-8")))
                except UnicodeDecodeError as exc:
                    raise StrictError(f"UTF-8 invalide / invalid UTF-8 on {kind}.{name}") from exc
            elif gk == K_BYTES:
                out.append((field, name, raw))
            elif gk == K_MSG:
                out.append((field, name, decode(raw, target)))   # type: ignore[arg-type]
            else:  # K_ANY
                out.append((field, name, _decode_generic(raw)))
    return out


def encode(items: list[tuple[int, str, object]], kind: str) -> bytes:
    """
    Ré-sérialise DEPUIS LA VALEUR décodée — c'est ce qui rend l'aller-retour probant.
    Re-serialises FROM the decoded value: that is what makes the round-trip meaningful.
    """
    schema = SCHEMA[kind]
    out = bytearray()
    for field, _name, val in items:
        _n, gk, _rep, target = schema[field]
        out += write_varint((field << 3) | _WIRE_OF_KIND[gk])
        if gk in (K_INT, K_BOOL):
            out += write_varint(val)                                  # type: ignore[arg-type]
        elif gk == K_STR:
            b = val.encode("utf-8")                                   # type: ignore[union-attr]
            out += write_varint(len(b)) + b
        elif gk == K_BYTES:
            out += write_varint(len(val)) + val                       # type: ignore[arg-type]
        elif gk == K_MSG:
            b = encode(val, target)                                   # type: ignore[arg-type]
            out += write_varint(len(b)) + b
        else:
            b = _encode_generic(val)                                  # type: ignore[arg-type]
            out += write_varint(len(b)) + b
    return bytes(out)


def as_dict(items: list[tuple[int, str, object]], kind: str) -> dict:
    """Vue lisible : répétés en listes, singuliers en scalaires. / Readable view."""
    schema = SCHEMA[kind]
    res: dict = {}
    for field, name, val in items:
        _n, gk, rep, target = schema[field]
        if gk == K_MSG:
            val = as_dict(val, target)          # type: ignore[arg-type]
        elif gk == K_ANY:
            val = f"<{len(val)} champs opaques>"  # type: ignore[arg-type]
        if rep:
            res.setdefault(name, []).append(val)
        else:
            res[name] = val
    return res


def strict_parse(raw: bytes, kind: str = "FileDescriptorProto") -> dict | None:
    """
    Décode ET vérifie l'aller-retour. Rend None au moindre doute.
    Decodes AND checks the byte-identical round-trip. Returns None on any doubt.
    """
    try:
        items = decode(raw, kind)
    except StrictError:
        return None
    except (IndexError, RecursionError):
        return None
    if encode(items, kind) != raw:
        return None
    return as_dict(items, kind)
