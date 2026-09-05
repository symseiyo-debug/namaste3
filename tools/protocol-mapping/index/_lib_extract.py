#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : _lib_extract.py — bibliotheque partagee des extracteurs opcodes/handlers (Namaste 3, etage 1).
Shared library for the deterministic 0-LLM opcode/handler extractors.
POURQUOI : Aucune dependance externe (stdlib seule, regle du projet : deterministe avant le travail parallele).
    Ne pas dupliquer iter_cs_files/write_tsv dans chaque extracteur -- une seule exclusion
    d'artefacts de build, une seule discipline de rejeu byte-identique.
FR/EN : commentaires bilingues courts sur le code de doctrine/frontiere (règle du projet).
COMMENT LANCER : jamais seul -- importe par les extraire_*.py de ce dossier.
GATE : aucune propre -- couverte par l'--epreuve de chaque extracteur qui l'utilise.
"""
from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Iterator

# Une classe C# ouvre un contexte "classe courante" qu'on suit ligne a ligne.
# A C# class opens a "current class" context we track line by line.
CLASS_RE = re.compile(
    r"^\s*(?:public|internal|private|protected)?\s*(?:static\s+|sealed\s+|abstract\s+|partial\s+)*class\s+(\w+)"
)

# Constante d'identifiant de message : `public const ushort Id = N;` (ou uint/short), avec
# ou sans `new` (mesure sur Giny : 23/1124 classes derivent d'une base qui declare deja `Id`
# et le masquent via `public new const ushort Id = N;` -- 1ere version du regex les ratait
# EN SILENCE, protocol_id restait vide pour PartyLeaveRequestMessage etc.)
# Message id constant, width flavours + optional `new` shadow modifier, measured on Giny.
MESSAGE_ID_CONST_RE = re.compile(
    r"public\s+(?:new\s+)?const\s+(?:ushort|uint|short|int)\s+Id\s*=\s*(\d+)\s*;"
)


# Repertoires a exclure : artefacts de build .NET (obj/bin, copies generees/intermediaires du
# MEME code source -> doublons purs) et instantane fige "oracle" du diffeur inter-versions
# (Tools/ProtoDiff273/out/oracle-2.42/, cf. ARCHI-REFERENCE-JIVA.md §F.1 -- "bundle fige", pas
# le code vivant). Mesure le 04/09 : Symbioz porte 1025 .cs sous obj/bin (30% du depot !),
# Jiva 19 sous obj/ + tout DofusProtocol duplique sous l'oracle -- sans exclusion, chaque
# classe de message y apparaissait 2x, EN SILENCE, gonflant messages-jiva.tsv de 1113 lignes
# fantomes. Excludes .NET build artifacts (obj/bin, pure duplicates of live source) and the
# frozen ProtoDiff273 oracle snapshot from the scan.
EXCLUDED_DIR_PARTS = {"obj", "bin"}
EXCLUDED_PATH_MARKER = "ProtoDiff273/out"


def iter_cs_files(racine: Path) -> Iterator[Path]:
    """Parcourt tous les .cs sous racine, ordre trie (determinisme du rejeu), hors
    artefacts de build et instantane fige (cf. EXCLUDED_DIR_PARTS/EXCLUDED_PATH_MARKER).
    Walk every .cs under racine, sorted order (rejeu byte-identique), skipping build
    artifacts and the frozen oracle snapshot."""
    for path in sorted(racine.rglob("*.cs")):
        parts = set(path.parts)
        if parts & EXCLUDED_DIR_PARTS:
            continue
        if EXCLUDED_PATH_MARKER in str(path):
            continue
        yield path


# Hash sha256 d'UN fichier -- utilise par les epreuves --epreuve pour comparer des rejeux.
# / sha256 hash of ONE file -- used by --epreuve runs to compare replays.
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build_message_id_lookup(racine: Path) -> dict[str, tuple[int, str]]:
    """Indexe TOUT le depot : nom_de_classe -> (id_numerique, fichier:ligne).
    Une seule passe, reutilisee par extraire_handlers (resoudre l'Id symbolique
    d'un attribut `[WorldHandler(XMessage.Id)]`) et par extraire_messages.
    Index the whole repo once: class name -> (numeric id, file:line). Reused by
    the handler extractor to resolve a symbolic `X.Id` attribute reference.
    """
    lookup: dict[str, tuple[int, str]] = {}
    for path in iter_cs_files(racine):
        current_class = None
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for i, line in enumerate(lines, start=1):
            m = CLASS_RE.match(line)
            if m:
                current_class = m.group(1)
            m2 = MESSAGE_ID_CONST_RE.search(line)
            if m2 and current_class:
                # Un doublon (meme nom de classe dans 2 fichiers) : on garde le 1er
                # rencontre (ordre trie = deterministe) et ne l'ecrase pas en silence.
                # Duplicate class name across files: keep first (sorted = deterministic).
                lookup.setdefault(current_class, (int(m2.group(1)), f"{path}:{i}"))
    return lookup


def write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """Ecrit un TSV avec fin de ligne \\n stable (rejeu byte-identique).
    Writes a TSV with a stable \\n line ending (byte-identical rerun)."""
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(header) + "\n")
        for row in rows:
            f.write("\t".join(str(c).replace("\t", " ").replace("\n", " ") for c in row) + "\n")


# Imprime "[label] done/total" tous les `every` pas (et au dernier) -- feedback sur un scan long.
# / Prints "[label] done/total" every `every` steps (and on the last) -- feedback on a long scan.
def print_progress(label: str, done: int, total: int, every: int = 200) -> None:
    if total and (done % every == 0 or done == total):
        print(f"  [{label}] {done}/{total}", flush=True)
