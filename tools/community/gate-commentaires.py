#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Gate déterministe (0 jeton) qui mesure la couverture de commentaires du
    code du chantier Namaste 3 — en-tête de fichier, % de fonctions/classes/
    méthodes commentées, nombres magiques non sourcés.
POURQUOI (04/09/2026, décision du projet — verbatim : « tu me commentes tout le code,
    super important pour un projet commu ») : partagé à la communauté,
    une consigne relue et oubliée ne protège rien
    (règle du projet) — cette gate la rend mesurable, rejouable, refus nommés.
COMMENT LANCER :
    python3 gate-commentaires.py <dossier> [<dossier2> ...] [--exclude NOM ...]
    python3 gate-commentaires.py <dossier> --markdown > ETAT.md
    python3 gate-commentaires.py --epreuve
GATE : VERT par fichier si (a) en-tête QUOI/POURQUOI/COMMENT LANCER/GATE
    présent (mots-clés FR ou EN, tolérant sur la forme) ET (b) ≥ 90 % des
    fonctions/classes/méthodes ont un commentaire/docstring dans les 2 lignes
    au-dessus ou en 1re ligne du corps. Sinon ROUGE + liste NOMMÉE des manques
    (fichier:ligne:nom). Nombres magiques (littéraux ≥ 3 chiffres hors 1000)
    sans commentaire sur leur ligne/au-dessus : comptés, ne bloquent PAS le
    verdict (mesure, pas gate — le brief ne les met pas dans VERT/ROUGE).
"""

import argparse
import re
import sys
import tempfile
import shutil
from pathlib import Path

CODE_EXTS = {".py", ".cs", ".sh", ".ps1"}
DEFAULT_EXCLUDES = {"bin", "obj", "__pycache__", "deplie", "staging", ".venv", ".git"}
MIN_PCT_VERT = 90.0
MAGIC_EXCLUDED_VALUES = {1000}  # hors 0/1/1000 (0 et 1 n'ont qu'1 chiffre, exclus par le regex lui-même)

# Mots-clés d'en-tête : FR ou EN, un seul suffit par catégorie (tolérant sur la forme).
HEADER_PATTERNS = {
    "QUOI": re.compile(r"\b(QUOI|WHAT)\b", re.IGNORECASE),
    "POURQUOI": re.compile(r"\b(POURQUOI|WHY)\b", re.IGNORECASE),
    "COMMENT": re.compile(r"\b(COMMENT\s+LANCER|HOW\s+TO\s+RUN|USAGE)\b", re.IGNORECASE),
    "GATE": re.compile(r"\bGATE\b", re.IGNORECASE),
}
HEADER_SCAN_LINES = 80  # l'en-tête se cherche dans le début du fichier, pas tout le fichier

MAGIC_NUM_RE = re.compile(r"(?<![\w.])\d{3,}(?![\w])")

def is_comment_line(line: str, ext: str) -> bool:
    """Dit si une ligne EST un commentaire (pas juste en contient un) / Says whether a line IS (not just contains) a comment, per language."""
    s = line.strip()
    if not s:
        return False
    if ext == ".py":
        return s.startswith("#")
    if ext == ".cs":
        return s.startswith("//") or s.startswith("/*") or s.startswith("*")
    if ext == ".sh":
        return s.startswith("#")
    if ext == ".ps1":
        return s.startswith("#") or s.startswith("<#") or s.startswith("#>")
    return False

def is_docstring_start(line: str, ext: str) -> bool:
    """1re ligne de corps = docstring/commentaire → compte "commenté" même sans ligne au-dessus. / 1st body line = docstring/comment → counts as "commented" with no line above."""
    s = line.strip()
    if not s:
        return False
    if ext == ".py":
        return s.startswith('"""') or s.startswith("'''") or s.startswith("#")
    return is_comment_line(line, ext)

# Une "unité" = fonction, classe, méthode. Chaque extracteur rend une liste de
# (ligne 1-indexée, nom, ligne_du_corps_ou_None).
# Each extractor returns a list of (1-indexed line, name, body_line_or_None).

def extract_units_py(lines):
    units = []
    pat = re.compile(r"^\s*(def|class)\s+([A-Za-z_][\w]*)")
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            body_line = i + 1 if i + 1 < len(lines) else None
            units.append((i + 1, m.group(2), body_line, i))
    return units

# Repère classes/struct/interface/record ET méthodes publiques|privées|internal
# à la ligne (regex, pas un vrai parseur C# — suffisant pour une gate de forme).
# / Finds class/struct/interface/record AND public|private|internal methods by
# line (regex, not a real C# parser — enough for a form-level gate).
def extract_units_cs(lines):
    units = []
    class_pat = re.compile(
        r"^\s*(?:\[[^\]]*\]\s*)*(?:public|private|internal|protected)?\s*"
        r"(?:static\s+|sealed\s+|abstract\s+|partial\s+)*"
        r"(?:class|struct|interface|record)\s+([A-Za-z_]\w*)"
    )
    method_pat = re.compile(
        r"^\s*(?:\[[^\]]*\]\s*)*(public|private|internal|protected)\b"
        r"[^;{}=]*?\s([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:where\b.*)?\{?\s*$"
    )
    for i, line in enumerate(lines):
        cm = class_pat.match(line)
        if cm:
            body_line = i + 1 if i + 1 < len(lines) else None
            units.append((i + 1, cm.group(1), body_line, i))
            continue
        mm = method_pat.match(line)
        if mm and "class " not in line and "namespace " not in line:
            body_line = i + 1 if i + 1 < len(lines) else None
            units.append((i + 1, mm.group(2), body_line, i))
    return units

# Deux formes bash reconnues : `function nom` et `nom() {`.
# / Two recognized bash forms: `function name` and `name() {`.
def extract_units_sh(lines):
    units = []
    pat1 = re.compile(r"^\s*function\s+([\w-]+)")
    pat2 = re.compile(r"^\s*([\w-]+)\s*\(\)\s*\{?")
    for i, line in enumerate(lines):
        m = pat1.match(line) or pat2.match(line)
        if m:
            body_line = i + 1 if i + 1 < len(lines) else None
            units.append((i + 1, m.group(1), body_line, i))
    return units

# Une seule forme PowerShell : `function Nom`.
# / One PowerShell form only: `function Name`.
def extract_units_ps1(lines):
    units = []
    pat = re.compile(r"^\s*function\s+([\w-]+)", re.IGNORECASE)
    for i, line in enumerate(lines):
        m = pat.match(line)
        if m:
            body_line = i + 1 if i + 1 < len(lines) else None
            units.append((i + 1, m.group(1), body_line, i))
    return units

EXTRACTORS = {".py": extract_units_py, ".cs": extract_units_cs, ".sh": extract_units_sh, ".ps1": extract_units_ps1}
DECORATOR_SKIP = {".py": re.compile(r"^\s*@\w"), ".cs": re.compile(r"^\s*\[")}

def unit_is_commented(lines, idx0, ext):
    """idx0 = index 0-based de la déclaration : regarde 2 lignes au-dessus (décorateurs sautés), puis la 1re ligne du corps. / Looks 2 lines above (decorators skipped), then the 1st body line."""
    skip_re = DECORATOR_SKIP.get(ext)
    j = idx0 - 1
    checked = 0
    while j >= 0 and checked < 2:
        above = lines[j]
        if skip_re and skip_re.match(above):
            j -= 1
            continue
        if not above.strip():
            j -= 1
            checked += 1
            continue
        if is_comment_line(above, ext):
            return True
        j -= 1
        checked += 1
    # 1re ligne non vide du corps
    k = idx0 + 1
    while k < len(lines) and not lines[k].strip():
        k += 1
    if k < len(lines) and is_docstring_start(lines[k], ext):
        return True
    return False

# VRAI seulement si les 4 mots-clés QUOI/POURQUOI/COMMENT/GATE sont tous
# trouvés dans le début du fichier — un seul manquant refuse l'en-tête entier.
# / TRUE only if all 4 keywords QUOI/POURQUOI/COMMENT/GATE are found near the
# top of the file — a single one missing refuses the whole header.
def header_ok(lines):
    text = "\n".join(lines[:HEADER_SCAN_LINES])
    return all(p.search(text) for p in HEADER_PATTERNS.values())

def magic_numbers(lines, ext):
    """Littéraux ≥3 chiffres (hors 1000) sans commentaire ligne/au-dessus → liste (ligne, valeur). / ≥3-digit literals (excl. 1000), uncommented → (line, value) list."""
    found = []
    for i, line in enumerate(lines):
        for m in MAGIC_NUM_RE.finditer(line):
            val = int(m.group(0))
            if val in MAGIC_EXCLUDED_VALUES:
                continue
            same_line_comment = ("#" in line) or ("//" in line)
            above_comment = i > 0 and is_comment_line(lines[i - 1], ext)
            if not same_line_comment and not above_comment:
                found.append((i + 1, val))
    return found

def shebang_ext(path: Path):
    """Un script SANS extension (ex. bin/run-nightly) se classe par son shebang, sinon la gate l'ignore. / An extensionless script is classed by its shebang, else silently skipped."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return None
    if first.startswith("#!") and ("bash" in first or "/sh" in first or first.rstrip().endswith("sh")):
        return ".sh"
    if first.startswith("#!") and "pwsh" in first:
        return ".ps1"
    if first.startswith("#!") and "python" in first:
        return ".py"
    return None

def analyze_file(path: Path, ext=None):
    # ext explicite (fichier sans extension, ex. bin/run-nightly) sinon celle du nom.
    # / explicit ext (extensionless file, e.g. bin/run-nightly) else the filename's.
    ext = ext or path.suffix
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"path": str(path), "error": str(e)}
    lines = text.split("\n")
    h_ok = header_ok(lines)
    units = EXTRACTORS[ext](lines)
    missing = []
    commented_count = 0
    for lineno, name, _body, idx0 in units:
        if unit_is_commented(lines, idx0, ext):
            commented_count += 1
        else:
            missing.append((lineno, name))
    total = len(units)
    pct = 100.0 if total == 0 else round(100.0 * commented_count / total, 1)
    verdict = "VERT" if (h_ok and pct >= MIN_PCT_VERT) else "ROUGE"
    reasons = []
    if not h_ok:
        missing_kw = [k for k, p in HEADER_PATTERNS.items() if not p.search("\n".join(lines[:HEADER_SCAN_LINES]))]
        reasons.append(f"en-tête manquant: {','.join(missing_kw)}")
    if pct < MIN_PCT_VERT:
        reasons.append(f"{pct}% fonctions commentées (< {MIN_PCT_VERT}%)")
    magics = magic_numbers(lines, ext)
    return {
        "path": str(path),
        "ext": ext,
        "header_ok": h_ok,
        "total_units": total,
        "commented_units": commented_count,
        "pct": pct,
        "verdict": verdict,
        "missing": missing,  # [(lineno, name), ...]
        "reasons": reasons,
        "magic_count": len(magics),
        "magic_sample": magics[:10],
    }

def iter_code_files(roots, excludes):
    # Rend (chemin, ext) : ext vient du nom, ou du shebang pour un fichier sans
    # extension passé EXPLICITEMENT (jamais deviné pendant un rglob de dossier).
    # / Yields (path, ext): ext comes from the name, or the shebang for an
    # extensionless file passed EXPLICITLY (never guessed during a dir rglob).
    seen = set()
    for root in roots:
        rp = Path(root)
        if rp.is_file():
            ext = rp.suffix if rp.suffix in CODE_EXTS else shebang_ext(rp)
            if ext and rp not in seen:
                seen.add(rp)
                yield rp, ext
            continue
        for p in sorted(rp.rglob("*")):
            if not p.is_file() or p.suffix not in CODE_EXTS:
                continue
            if any(part in excludes for part in p.parts):
                continue
            if p in seen:
                continue
            seen.add(p)
            yield p, p.suffix

def run(roots, excludes, markdown=False):
    # Point d'entrée unique de la mesure : liste triée + analyse par fichier.
    # / Single entry point for measurement: sorted list + per-file analysis.
    results = [analyze_file(p, ext) for p, ext in iter_code_files(roots, excludes)]
    results.sort(key=lambda r: r["path"])
    return results

# Rapport lisible en console : verdict ligne par ligne + refus nommés
# (fichier:ligne:nom) + compteurs globaux par motif (loi F du chantier).
# / Console-readable report: per-file verdict + named refusals
# (file:line:name) + global counters by pattern (chantier's "loi F").
def print_text_report(results):
    n_vert = sum(1 for r in results if r.get("verdict") == "VERT")
    n_rouge = sum(1 for r in results if r.get("verdict") == "ROUGE")
    motifs = {}
    for r in results:
        for reason in r.get("reasons", []):
            key = reason.split(":")[0].split("(")[0].strip()
            motifs[key] = motifs.get(key, 0) + 1
    for r in results:
        if "error" in r:
            print(f"ERREUR {r['path']}: {r['error']}")
            continue
        print(f"{r['verdict']} {r['path']} ({r['pct']}%, {r['commented_units']}/{r['total_units']} unités, "
              f"en-tête={'oui' if r['header_ok'] else 'non'}, {r['magic_count']} nombres magiques)")
        if r["verdict"] == "ROUGE":
            for reason in r["reasons"]:
                print(f"    - {reason}")
            for lineno, name in r["missing"]:
                print(f"    - {r['path']}:{lineno}:{name} — non commenté")
    print(f"\nTOTAL: {n_vert} VERT / {n_rouge} ROUGE / {len(results)} fichiers")
    print("Compteurs globaux par motif (loi F):")
    for k, v in sorted(motifs.items()):
        print(f"  - {k}: {v}")

# Même mesure que print_text_report, en tableau markdown (pour un
# ETAT-COMMENTAIRES.md collé directement sans reformatage manuel).
# / Same measurement as print_text_report, as a markdown table (for an
# ETAT-COMMENTAIRES.md pasted directly, no manual reformatting).
def print_markdown_report(results):
    print("| Fichier | Verdict | % | Unités | En-tête | Nombres magiques | Manques |")
    print("|---|---|---|---|---|---|---|")
    for r in results:
        if "error" in r:
            print(f"| {r['path']} | ERREUR | - | - | - | - | {r['error']} |")
            continue
        manques = "; ".join(f"{r['path']}:{ln}:{name}" for ln, name in r["missing"][:8])
        if len(r["missing"]) > 8:
            manques += f" … (+{len(r['missing']) - 8})"
        print(f"| {r['path']} | {r['verdict']} | {r['pct']}% | {r['commented_units']}/{r['total_units']} | "
              f"{'oui' if r['header_ok'] else 'NON'} | {r['magic_count']} | {manques} |")
    n_vert = sum(1 for r in results if r.get("verdict") == "VERT")
    n_rouge = sum(1 for r in results if r.get("verdict") == "ROUGE")
    total = len(results)
    avg = round(sum(r["pct"] for r in results if "pct" in r) / total, 1) if total else 0.0
    print(f"\n**TOTAL** : {n_vert}/{total} VERT, {n_rouge}/{total} ROUGE, moyenne {avg}%.")

# --epreuve : témoins fabriqués, verdicts attendus, + rejeu byte-identique. Refuse nommément si un témoin ne rend pas le verdict attendu.

WITNESS_CONFORME = '''# QUOI : témoin conforme pour gate-commentaires --epreuve.
# POURQUOI : prouver que la gate rend VERT sur un fichier qui respecte la règle (04/09).
# COMMENT LANCER : n'est jamais lancé, seulement mesuré.
# GATE : doit rendre VERT.

# Additionne deux nombres.
def add(a, b):
    return a + b

# Soustrait b de a.
def sub(a, b):
    return a - b

# Multiplie deux nombres.
def mul(a, b):
    return a * b

# Divise a par b.
def div(a, b):
    return a / b

# Représente un point 2D.
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
'''

WITNESS_SANS_ENTETE = '''def add(a, b):
    # Additionne deux nombres.
    return a + b
'''

WITNESS_40_POURCENT = '''# QUOI : témoin 2/5 commenté pour gate-commentaires --epreuve.
# POURQUOI : prouver que la gate rend ROUGE sous 90% (04/09).
# COMMENT LANCER : jamais lancé.
# GATE : doit rendre ROUGE, 40.0%.

# Additionne deux nombres.
def add(a, b):
    return a + b

def sub(a, b):
    return a - b

def mul(a, b):
    return a * b

def div(a, b):
    return a / b

# Modulo de a par b.
def mod(a, b):
    return a % b
'''

WITNESS_DOCSTRING = '''# QUOI : témoin docstring-seule pour gate-commentaires --epreuve.
# POURQUOI : prouver que la docstring seule compte comme commentaire (04/09).
# COMMENT LANCER : jamais lancé.
# GATE : doit rendre VERT.

def add(a, b):
    """Additionne deux nombres."""
    return a + b

def sub(a, b):
    """Soustrait b de a."""
    return a - b
'''

# Fait tourner les 4 témoins + le rejeu déterministe, refuse NOMMÉMENT si un
# verdict ne colle pas à l'attendu. C'est l'épreuve dans les deux sens (méthode
# du projet : erreur→fiche→garde→épreuve) qui rend cette gate elle-même crédible.
# / Runs the 4 witnesses + the deterministic replay, refuses BY NAME if a
# verdict doesn't match expectations. This is the two-way proof that makes
# this gate itself trustworthy.
def run_epreuve():
    tmpdir = Path(tempfile.mkdtemp(prefix="gate-commentaires-epreuve-"))
    witnesses = {
        "conforme.py": (WITNESS_CONFORME, "VERT"),
        "sans_entete.py": (WITNESS_SANS_ENTETE, "ROUGE"),
        "quarante_pourcent.py": (WITNESS_40_POURCENT, "ROUGE"),
        "docstring_seule.py": (WITNESS_DOCSTRING, "VERT"),
    }
    for name, (content, _expected) in witnesses.items():
        (tmpdir / name).write_text(content, encoding="utf-8")

    ok = True
    print(f"--epreuve : témoins écrits dans {tmpdir}")
    results = run([str(tmpdir)], DEFAULT_EXCLUDES)
    by_name = {Path(r["path"]).name: r for r in results}

    for name, (_content, expected) in witnesses.items():
        r = by_name.get(name)
        if r is None:
            print(f"REFUS: {name} — introuvable dans les résultats")
            ok = False
            continue
        got = r["verdict"]
        if got != expected:
            print(f"REFUS: {name} — attendu {expected}, obtenu {got} ({r.get('reasons')})")
            ok = False
        else:
            detail = f"{r['pct']}%" if name == "quarante_pourcent.py" else ""
            print(f"OK: {name} — {got} {detail}".strip())

    # cas spécifique attendu : quarante_pourcent.py doit être à 40.0% pile
    r40 = by_name.get("quarante_pourcent.py")
    if r40 and r40["pct"] != 40.0:
        print(f"REFUS: quarante_pourcent.py — attendu 40.0%, obtenu {r40['pct']}%")
        ok = False

    # rejeu byte-identique : deux mesures successives du même dossier témoin
    import io
    import contextlib

    # Capture la sortie texte d'une mesure complète pour la comparer bit à bit.
    # / Captures a full measurement's text output to diff it byte for byte.
    def render():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            print_text_report(run([str(tmpdir)], DEFAULT_EXCLUDES))
        return buf.getvalue()

    out1 = render()
    out2 = render()
    if out1 == out2:
        print("OK: rejeu byte-identique (2 mesures successives, sortie identique)")
    else:
        print("REFUS: rejeu NON byte-identique — la gate n'est pas déterministe")
        ok = False

    shutil.rmtree(tmpdir, ignore_errors=True)
    print(f"\n--epreuve : {'VERT' if ok else 'ROUGE'}")
    return ok

# CLI : dossier(s)/fichier(s) à mesurer, ou --epreuve seul. Code de sortie 1
# si au moins un fichier est ROUGE (utilisable comme gate CI).
# / CLI: folder(s)/file(s) to measure, or --epreuve alone. Exit code 1 if at
# least one file is ROUGE (usable as a CI gate).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roots", nargs="*", help="dossier(s) ou fichier(s) à mesurer")
    ap.add_argument("--exclude", nargs="*", default=[], help="noms de dossiers additionnels à exclure")
    ap.add_argument("--markdown", action="store_true", help="sortie tableau markdown")
    ap.add_argument("--epreuve", action="store_true", help="fait tourner les témoins, --epreuve dans les deux sens")
    args = ap.parse_args()

    if args.epreuve:
        ok = run_epreuve()
        sys.exit(0 if ok else 1)

    if not args.roots:
        ap.error("au moins un dossier requis (ou --epreuve)")

    excludes = set(DEFAULT_EXCLUDES) | set(args.exclude)
    results = run(args.roots, excludes)
    if args.markdown:
        print_markdown_report(results)
    else:
        print_text_report(results)
    n_rouge = sum(1 for r in results if r.get("verdict") == "ROUGE")
    sys.exit(1 if n_rouge > 0 else 0)

if __name__ == "__main__":
    main()
