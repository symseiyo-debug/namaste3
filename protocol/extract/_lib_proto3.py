#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : _lib_proto3.py — parseur .proto3 textuel générique partagé par les
extracteurs gatherer/luaxy/deobfs (Namaste 3, étage 1). 0-LLM, stdlib.

POURQUOI :
Récursif à accolades (même patron que `extraire_protocole_otomai.py`, mais
sur du .proto natif : pas de bruit C#). Gère `message`/`enum` imbriqués à
profondeur arbitraire, les champs `[repeated|optional] type nom = N;`, et
les blocs `oneof x { ... }` dont les champs sont TRAITÉS COMME CEUX DU
PARENT (un oneof n'est pas un type, juste un groupe — cf. gatherer
`connection/message.proto`, ex. `Message.content`). `map<K,V>` n'est PAS
géré (0 occurrence mesurée dans les 4 dépôts cibles au 04/09) : une ligne
`map<...>` non reconnue tombe simplement hors du compte de champs plutôt
que de planter — mesurer avant d'écrire le cas, pas l'inverse.

COMMENT LANCER : jamais seul -- importé par extraire_protocole_{gatherer,luaxy,deobfs}.py.
GATE : aucune propre -- couverte par l'--epreuve de chaque extracteur qui l'utilise.
"""
from __future__ import annotations

import bisect
import re
from pathlib import Path

RE_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
RE_MSG_HDR = re.compile(r"\bmessage\s+(\w+)\s*\{")
RE_ENUM_HDR = re.compile(r"\benum\s+(\w+)\s*\{")
RE_FIELD = re.compile(
    r"^\s*(repeated\s+|optional\s+)?([\w.]+)\s+(\w+)\s*=\s*(\d+)\s*(?:\[[^\]]*\])?\s*;",
    re.MULTILINE,
)


# Index juste APRES le '}' qui ferme le '{' a open_pos (compte de profondeur, pas de regex).
# / Index just AFTER the '}' that closes the '{' at open_pos (depth counting, not regex).
def find_matching_brace(text: str, open_pos: int) -> int:
    depth, i, n = 0, open_pos, len(text)
    while i < n:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


# Numero de ligne 1-indexe d'une position par recherche binaire sur les offsets de '\n'.
# / 1-indexed line number for a position via binary search on '\n' offsets.
def line_no_at(newline_offsets: list, pos: int) -> int:
    return bisect.bisect_right(newline_offsets, pos) + 1


def collect_children(text: str, start: int, end: int):
    """Enfants `message`/`enum` à profondeur 0 dans text[start:end].
    Retourne (hdr_start, full_end, kind, name_pos, name, body_start, body_end)
    -- body_start/body_end = intérieur des accolades (exclut le noeud
    lui-même de la récursion, même piège que otomai déjà corrigé)."""
    children = []
    i = start
    while i < end:
        mm = RE_MSG_HDR.search(text, i, end)
        em = RE_ENUM_HDR.search(text, i, end)
        if not mm and not em:
            break
        if mm and (not em or mm.start() < em.start()):
            kind, hm = "message", mm
        else:
            kind, hm = "enum", em
        brace_pos = hm.end() - 1  # RE_*_HDR inclut le '{' final
        close_pos = find_matching_brace(text, brace_pos)
        children.append((hm.start(), close_pos, kind, hm.start(1), hm.group(1), brace_pos + 1, close_pos - 1))
        i = close_pos
    return children


def own_field_text(text: str, body_start: int, body_end: int, grandchildren) -> str:
    """Corps sans les messages/enums imbriqués (blanchis, \\n préservés) --
    les blocs `oneof { }` restent (ne sont jamais reconnus comme enfants),
    donc leurs champs sont naturellement vus par le scan de champs."""
    cursor, parts = body_start, []
    for cs, ce, *_ in grandchildren:
        parts.append(text[cursor:cs])
        parts.append("\n" * text.count("\n", cs, ce))
        cursor = ce
    parts.append(text[cursor:body_end])
    return "".join(parts)


# Lit les champs `[repeated|optional] type nom = N;` d'un corps DEJA blanchi de ses enfants.
# / Reads a `[repeated|optional] type name = N;` field list from a body ALREADY blanked of its children.
def parse_fields(own_text: str) -> list[tuple[int, str, str]]:
    out = []
    for fm in RE_FIELD.finditer(own_text):
        modifier, ftype, fname, fnum = fm.groups()
        t = ftype
        if modifier and modifier.strip() == "repeated":
            t = f"repeated {ftype}"
        out.append((int(fnum), t, fname))
    return out


# Recursion sur l'arbre message/enum : traite chaque enfant (champs, ligne) puis descend dans
# son corps pour ses propres enfants imbriques.
# / Recurses the message/enum tree: processes each child (fields, line) then descends into its
# body for its own nested children.
def walk(text, start, end, path, package, file_rel, newline_offsets, rows, counters, discarded):
    for cs, ce, kind, name_pos, name, body_start, body_end in collect_children(text, start, end):
        line = line_no_at(newline_offsets, name_pos)
        if kind == "enum":
            counters["enum"] += 1
            continue
        counters["message"] += 1
        grandchildren = collect_children(text, body_start, body_end)
        own_text = own_field_text(text, body_start, body_end, grandchildren)
        fields = parse_fields(own_text)
        counters["champs"] += len(fields)
        champs = ";".join(f"{n}:{t}:{fn}" for n, t, fn in fields)
        full_path = path + [name]
        complet = (package + "." if package else "") + "+".join(full_path)
        rows.append({"nom": name, "complet": complet, "champs": champs,
                      "fichier_ligne": f"{file_rel}:{line}", "n_champs": len(fields)})
        walk(text, body_start, body_end, full_path, package, file_rel, newline_offsets, rows, counters, discarded)


# Lit UN fichier .proto, resout son package, lance walk() dessus (jamais planter sur 1 fichier illisible).
# / Reads ONE .proto file, resolves its package, runs walk() on it (never crashes on 1 unreadable file).
def process_proto_file(path: Path, rows: list, counters: dict, discarded: list):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        discarded.append((str(path), f"lecture impossible: {e}", f"{path}:0"))
        return
    newline_offsets = [i for i, c in enumerate(text) if c == "\n"]
    pkg_m = RE_PACKAGE.search(text)
    package = pkg_m.group(1) if pkg_m else ""
    walk(text, 0, len(text), [], package, str(path), newline_offsets, rows, counters, discarded)


# Tous les .proto sous racine, ordre trie (determinisme du rejeu).
# / All .proto files under racine, sorted order (deterministic replay).
def iter_proto_files(racine: Path):
    yield from sorted(racine.rglob("*.proto"))
