#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_opcodes_sniffer.py [racine] [--out PATH] [--epreuve]
Table opcode <-> nom_clair depuis dofus3-sniffer-tui (Go, gopacket+BubbleTea) —
le second instrument tiers independant du chantier Namaste 3, etage 1. 0-LLM.

POURQUOI :
TROUVAILLE MESUREE AVANT d'ecrire ce script (04/09, cf. RAPPORT-EXTRACTION-TIERS.md
pour le detail) : ce depot NE PORTE AUCUNE table opcode<->nom. `internal/protoreg/
mappings.go` est du code GENERIQUE qui CHARGE un fichier JSON de renommage fourni
par l'operateur au runtime (`--mapping-paths`) ; `internal/protoreg/registry.go` +
`compiler.go` COMPILENT des fichiers .proto egalement fournis au runtime (extraits
par l'operateur depuis les DLL du client avec un AUTRE outil, hors de ce depot).
Aucun `.proto`, aucun JSON de mapping, aucun `go:embed` n'est trouve dans l'arbre
(mesure : grep -rn 'embed' + find *.proto/*.pb/*.bin -> 0 partout). Les SEULES
chaines "opcode -> nom" litterales du depot sont des EXEMPLES (README, docstring)
ou des FIXTURES DE TEST (mappings_test.go) — donc PAS des donnees Dofus reelles.
Ce script les extrait quand meme, un par un, avec leur provenance exacte, pour
qu'aucun consommateur en aval ne les prenne pour une table reelle par erreur de lecture.

FR/EN : commentaires bilingues courts. Aucun code Go recopie (seuls des noms/
litteraux structurels sont transcrits, jamais un corps de fonction).

COMMENT LANCER : python3 extraire_opcodes_sniffer.py [racine] [--out PATH.tsv] [--epreuve]
GATE : --epreuve (message plat + message etendu + champ renomme sortent, une ligne cassee
    n'invente RIEN, rejeu sha256 byte-identique).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib_extract import write_tsv

RACINE_DEFAUT = Path("refs/dofus3-sniffer-tui")
ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "opcodes-sniffer.tsv"

HEADER = ["opcode", "nom_clair", "fichier:ligne", "provenance", "note"]

# Les 3 SEULS fichiers du depot ou une chaine "opcode -> nom" litterale existe
# (mesure par grep -rl 'type.ankama.com\|type\.x/\|type\.test/' sur tout l'arbre
# le 04/09 : exactement ces 3, rien ailleurs). On ne scanne QUE ceux-la --
# elargir a tout le depot inventerait des faux positifs sur du texte non lie.
FICHIERS_CIBLES = {
    "README.md": "readme_exemple",
    "internal/protoreg/mappings.go": "docstring_exemple_fictif",
    "internal/protoreg/mappings_test.go": "fixture_test_synthetique",
}

# Forme plate : "cle": "Valeur"  (ex. "type.ankama.com/iri": "MapMovementRequest")
RE_FLAT = re.compile(r'"([\w./:-]+)"\s*:\s*"(\w+)"')
# Forme etendue : "cle": { "name": "Valeur"  (le "name" peut etre sur la ligne
# suivante ou la meme). Piege mesure (04/09) : le docstring Go de mappings.go
# porte un commentaire `// extended: ...` juste apres le '{' -- une 1ere
# version ancree sur `\{\s*"name"` (espaces seuls) ratait ce cas, ET le repli
# `RE_FLAT` capturait alors la cle reservee "name" comme si c'etait un opcode
# ("name" -> "Goodbye"). `[^\n]*\n` avale le reste de la ligne (commentaire
# inclus) avant de chercher "name" sur la suivante.
# EN: the Go docstring carries a trailing `//` comment right after '{'; a
# version anchored on whitespace only missed it, and RE_FLAT then mis-fired
# on the reserved "name" key as if it were an opcode. `[^\n]*\n` eats the
# rest of that line (comment included) before looking for "name" below.
RE_EXT = re.compile(r'"([\w./:-]+)"\s*:\s*\{[^\n]*\n\s*(?://)?\s*"name"\s*:\s*"(\w+)"')
# Renommage de champ a l'interieur d'un bloc "fields": { "abc": "userId", ... }
RE_FIELD = re.compile(r'"(\w+)"\s*:\s*"([a-zA-Z_]\w*)"')


def strip_prefix(key: str) -> str:
    """FR: normalise 'type.ankama.com/iri' -> 'iri' (meme convention que
    normalizeMsgKey dans mappings.go : tout apres le dernier '/').
    EN: same normalization as mappings.go's normalizeMsgKey."""
    return key.rsplit("/", 1)[-1]


# Numero de ligne 1-indexe d'une position (comptage direct des '\n', fichiers courts ici).
# / 1-indexed line number for a position (direct '\n' counting, files are small here).
def line_at(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def in_fields_block(text: str, pos: int, block_radius: int = 300) -> bool:
    """FR: heuristique -- la cle/valeur est-elle a l'interieur d'un bloc
    '\"fields\": {' proche en amont (donc un renommage de CHAMP, pas de message) ?
    EN: heuristic -- is this key/value inside a nearby preceding '"fields": {'
    block (a FIELD rename, not a message rename)?"""
    window = text[max(0, pos - block_radius):pos]
    return bool(re.search(r'"fields"\s*:\s*\{[^}]*$', window, re.DOTALL))


# Extrait les paires opcode<->nom_clair (formes plate et etendue) puis les renommages de champ
# du texte d'UN fichier cible -- coeur de l'extraction, appele par run() sur chaque fichier.
# / Extracts opcode<->clear-name pairs (flat and extended forms) then field renames from ONE
# target file's text -- the extraction core, called by run() on each file.
def extract_from_text(text: str, file_rel: str, provenance: str, rows: list, discarded: list):
    seen_spans = set()
    for rx, is_ext in ((RE_EXT, True), (RE_FLAT, False)):
        for m in rx.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in seen_spans):
                continue  # deja couvert par l'autre regex (forme etendue prioritaire)
            raw_key, value = m.group(1), m.group(2)
            if raw_key in ("name", "fields"):
                continue  # cle RESERVEE du schema de mapping (jamais un opcode reel)
            if in_fields_block(text, m.start()):
                continue  # un renommage de CHAMP, traite a part plus bas
            if "/" not in raw_key and not re.match(r"^[a-z]{2,6}$", raw_key) and raw_key not in ("Inner",):
                # cle qui ne ressemble ni a un typeUrl ni a un opcode court ni a
                # l'alias de test connu -- hors perimetre, ne pas inventer un sens.
                if is_ext:
                    pass  # forme etendue = toujours un vrai message-rename candidat
                else:
                    continue
            opcode = strip_prefix(raw_key)
            line = line_at(text, m.start())
            rows.append([opcode, value, f"{file_rel}:{line}", provenance, ""])
            if is_ext:
                seen_spans.add((m.start(), m.end()))

    # Renommages de champ (bloc "fields": {...}) -- annexes a la note du dernier
    # message-rename etendu rencontre juste avant, sinon reportes seuls.
    for fm in re.finditer(r'"fields"\s*:\s*\{([^}]*)\}', text, re.DOTALL):
        line = line_at(text, fm.start())
        # FR: attache au message-parent le PLUS PROCHE (distance de ligne
        # minimale), jamais au 1er trouve dans un ordre arbitraire -- piege
        # mesure : "ij" (Hello, ligne 24) est PLUS LOIN du bloc "fields" que
        # "kl" (Goodbye, ligne 25) mais un parcours non trie l'attrapait
        # quand meme en premier. EN: attach to the CLOSEST parent row (min
        # line distance), never the first found in an arbitrary order --
        # measured trap: an unsorted scan attached the fields block to the
        # farther candidate instead of the nearer one.
        candidates = [row for row in rows if row[2].startswith(file_rel + ":")
                      and abs(int(row[2].rsplit(":", 1)[1]) - line) < 6]
        for field_m in RE_FIELD.finditer(fm.group(1)):
            fkey, fval = field_m.group(1), field_m.group(2)
            note = f"renommage de champ: {fkey} -> {fval}"
            if candidates:
                nearest = min(candidates, key=lambda r: abs(int(r[2].rsplit(":", 1)[1]) - line))
                nearest[4] = (nearest[4] + "; " if nearest[4] else "") + note
            else:
                discarded.append((f"{fkey}->{fval}", "renommage de champ sans message-parent proche", f"{file_rel}:{line}"))


def extract_envelope_facts(readme_text: str) -> list[str]:
    """FR: faits hors-table utiles a la comparaison (noms d'enveloppe, version,
    port par defaut) -- pas des opcodes, donc pas dans le TSV, juste le rapport.
    EN: non-table facts useful for cross-checking -- not opcodes, report only."""
    facts = []
    m = re.search(r"For `([\d.]+)` ?: ?connection envelope = `(\w+)`, game envelope = `(\w+)`", readme_text)
    if m:
        facts.append(f"enveloppe mesuree pour build {m.group(1)} (README) : connexion='{m.group(2)}' jeu='{m.group(3)}'")
    return facts


# Scanne les 3 SEULS fichiers cibles (voir FICHIERS_CIBLES), deduplique, ecrit le TSV.
# / Scans the 3 ONLY target files (see FICHIERS_CIBLES), deduplicates, writes the TSV.
def run(racine: Path, out: Path) -> dict:
    rows: list = []
    discarded: list = []
    files_scanned = []
    for rel, provenance in FICHIERS_CIBLES.items():
        p = racine / rel
        if not p.exists():
            discarded.append((rel, "fichier cible absent du depot", f"{rel}:0"))
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        extract_from_text(text, str(p), provenance, rows, discarded)
        files_scanned.append(str(p))

    # Deduplique (meme opcode+valeur+ligne) au cas ou les 2 regex se recoupent.
    uniq = {}
    for r in rows:
        uniq[(r[0], r[1], r[2])] = r
    rows = list(uniq.values())
    rows.sort(key=lambda r: (r[3], r[2]))
    write_tsv(out, HEADER, rows)

    readme = racine / "README.md"
    envelope_facts = extract_envelope_facts(readme.read_text(encoding="utf-8")) if readme.exists() else []

    return {
        "fichiers_scannes": files_scanned,
        "lignes_extraites": len(rows),
        "par_provenance": {p: sum(1 for r in rows if r[3] == p) for p in set(FICHIERS_CIBLES.values())},
        "renommages_champ_orphelins": len(discarded),
        "faits_enveloppe_hors_table": envelope_facts,
        "descripteurs_proto_embarques": 0,  # mesure : 0 .proto, 0 go:embed dans tout le depot
        "out": str(out),
    }


# --- epreuve : rejeu byte-identique + sabotage ---
def run_epreuve() -> int:
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-sniffer-"))
    (tmp / "internal" / "protoreg").mkdir(parents=True)
    readme = tmp / "README.md"
    readme.write_text(
        'témoin\n```json\n{\n"type.ankama.com/wp1": "WitnessOkMessage",\n'
        '"type.ankama.com/wp2": {\n"name": "WitnessOkEvent",\n"fields": {\n"wfld": "witness_field"\n}\n}\n}\n```\n'
        "For `9.9.9.9` : connection envelope = `xco`, game envelope = `xga`\n",
        encoding="utf-8",
    )
    (tmp / "internal/protoreg/mappings.go").write_text(
        "// pas de mapping ici, temoin negatif dedie (aucune ligne ne doit sortir de ce fichier)\n",
        encoding="utf-8",
    )
    (tmp / "internal/protoreg/mappings_test.go").write_text(
        '// cle cassee : valeur non fermee -- doit etre IGNOREE (pas de faux positif), pas plantee\n'
        '`{"type.x/wpX": "Unterminat\n',
        encoding="utf-8",
    )
    out1, out2 = tmp / "out1.tsv", tmp / "out2.tsv"

    print("=== EPREUVE 1/2 : sabotage (message + champ renomme sortent, ligne cassee n'invente rien) ===")
    stats = run(tmp, out1)
    txt = out1.read_text(encoding="utf-8")
    p1 = "WitnessOkMessage" in txt and "wp1" in txt
    p2 = "WitnessOkEvent" in txt and "witness_field -> " not in txt and "wfld -> witness_field" in txt
    p3 = "wpX" not in txt and "Unterminat" not in txt  # la ligne cassee n'a RIEN invente
    print(f"  message plat wp1 sorti: {'OK' if p1 else 'MANQUANT'}")
    print(f"  message etendu wp2 + son champ renomme sortis: {'OK' if p2 else 'MANQUANT'}")
    print(f"  ligne cassee n'a rien invente: {'OK' if p3 else 'ECHEC (faux positif fabrique)'}")

    print("\n=== EPREUVE 2/2 : rejeu byte-identique (sha256) ===")
    run(tmp, out2)
    h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
    h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
    same = h1 == h2
    print(f"  sha256 run1={h1[:16]}... run2={h2[:16]}... {'IDENTIQUE' if same else 'DIVERGENT'}")

    tout_ok = p1 and p2 and p3 and same
    print(f"\n=== BILAN EPREUVE : {'VERT' if tout_ok else 'ROUGE'} ===")
    return 0 if tout_ok else 1


# Point d'entree CLI : --epreuve, ou une extraction reelle (racine -> --out).
# / CLI entry point: --epreuve, or a real extraction (racine -> --out).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("racine", nargs="?", default=str(RACINE_DEFAUT))
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()

    if args.epreuve:
        sys.exit(run_epreuve())

    racine = Path(args.racine)
    if not racine.exists():
        print(f"ERREUR: racine absente: {racine}", file=sys.stderr)
        sys.exit(1)
    stats = run(racine, Path(args.out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
