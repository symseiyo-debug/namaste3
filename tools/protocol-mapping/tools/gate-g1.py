#!/usr/bin/env python3
"""
gate-g1.py — Gate G1 du cahier Namaste 3 (§ÉTAGE 1) : « la carte couvre le CHEMIN
CRITIQUE (login → perso → carte → déplacement) sans aucun DÉDUIT non vérifié, et
chaque opcode du chemin a ses champs (numéro, type) sourcés. »

Écrite AVANT le travail qu'elle juge (règle du projet : une gate écrite après mesure ce
qu'on a fait, pas ce qu'il fallait faire). EN: written BEFORE the swarm work it will
judge — it measures what SHOULD be true, not what already was done.

Entrées : une liste d'opcodes (chemin-critique.txt, un code par ligne, '#'=commentaire)
+ les fragments *.md de internal/ (format §4, cf. gate-forme.py — non réimporté ici
pour rester un script autonome, cf. angle mort #5 dans le rapport).

VERT ssi 100% des opcodes du chemin sont présents, tagués VÉRIFIÉ (aucun DÉDUIT), avec
une source repérable, et des champs numérotés+typés (ou explicitement vides).
Usage: gate-g1.py [--chemin FICHIER] [fragment.md ...] | gate-g1.py --epreuve
"""
import glob
import os
import tempfile
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ETAGE1 = os.path.dirname(HERE)
DEFAULT_CHEMIN = os.path.join(ETAGE1, "chemin-critique.txt")

HEADER_TAG_RE = re.compile(r"^#{2,4}\s.*?\|\s*tag\s*:\s*(.*)$")
CHAMPS_LINE_RE = re.compile(r"^-?\s*\*{0,2}champs\*{0,2}\s*:\s*(.*)$", re.IGNORECASE)
SOURCE_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,}\.(?:cs|md|proto|tsv|sql|dll|bin|py|json|log|ps1)(?::\d[\d,\-]*)?"
    r"|[A-Za-z0-9_]{2,}[A-Za-z0-9_.\-]*/[A-Za-z0-9_./\-]+"
    r"|§\s?\(?[A-Za-z0-9.\-]+\)?"
)
TYPE_HINT_RE = re.compile(r"(?i)(int32|int64|varint|string|bytes|bool|float|double|packed|\brep\b|guid|hex|\{)")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
CODE_RE = re.compile(r"`([a-z]{3})`")

MOTIFS = {
    "ABSENT": "opcode absent de tout fragment",
    "DEDUIT": "tag contient DÉDUIT — pas encore VÉRIFIÉ (G1 : zéro DÉDUIT toléré sur le chemin)",
    "SOURCE": "VÉRIFIÉ sans source (chemin/fichier:ligne/§) repérable",
    "CHAMPS": "champs sans numéro et/ou sans type repérables",
}


# Lit chemin-critique.txt : un opcode 3 lettres par ligne, '#'=commentaire, lignes vides ignorées.
# / Reads chemin-critique.txt: one 3-letter opcode per line, '#'=comment, blank lines skipped.
def load_chemin(path):
    with open(path, encoding="utf-8") as f:
        return [s for s in (l.strip() for l in f) if s and not s.startswith("#")]


# Découpe un fragment en blocs séparés par une ligne vide ou '---' (même patron que gate-forme.py).
# / Splits a fragment into blocks separated by a blank line or '---' (same pattern as gate-forme.py).
def paragraphs(lines):
    paras, cur, start = [], [], 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "" or s == "---":
            if cur:
                paras.append((start, cur)); cur = []
        else:
            if not cur:
                start = i
            cur.append(ln)
    if cur:
        paras.append((start, cur))
    return paras


def champs_status(text):
    """FR: (ok, motif) — vide/aucun EN TÊTE = 0 champ, accepté d'office.
    EN: (ok, why) — a leading 'vide'/'aucun' means zero fields, trivially fine."""
    low = text.strip().lower()
    lead = low[:30]
    if lead in ("", "-", "n/a") or "vide" in lead or "aucun" in lead:
        return True, None
    if not re.search(r"f\d+", text):
        return False, "aucun champ numéroté (fN) repéré"
    if not TYPE_HINT_RE.search(text):
        return False, "numéroté mais aucun type repéré (int32/varint/string/{...})"
    return True, None


def scan_fragment(path, targets, entries):
    """FR: remplit entries[code] += (fichier, ligne, tagfield, texte, champs_texte).
    EN: fills entries[code] with (file, line, tagfield, full_text, champs_text)."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    for start, para in paragraphs(lines):
        if len(para) >= 2 and all(TABLE_ROW_RE.match(l) for l in para[:2]):
            head_cells = [c.strip().lower() for c in para[0].strip().strip("|").split("|")]
            if "tag" in head_cells:
                champs_idx = head_cells.index("champs") if "champs" in head_cells else None
                for j, row in enumerate(para[1:], start=1):
                    if TABLE_SEP_RE.match(row):
                        continue
                    cells = row.strip().strip("|").split("|")
                    matched = [c for c in CODE_RE.findall(cells[0]) if c in targets] if cells else []
                    if matched:
                        tag = "VÉRIFIÉ" if "VÉRIFIÉ" in row else ("DÉDUIT" if "DÉDUIT" in row else "")
                        ctext = cells[champs_idx] if champs_idx is not None and champs_idx < len(cells) else row
                        for c in matched:
                            entries.setdefault(c, []).append((path, start + j, tag, row, ctext))
                continue
        header_line = next((l.strip() for l in para if HEADER_TAG_RE.match(l.strip())), None)
        if header_line is None:
            continue
        codes = [c for c in CODE_RE.findall(header_line.split("|", 1)[0]) if c in targets]
        if not codes:
            continue
        tagfield = HEADER_TAG_RE.match(header_line).group(1)
        text = "\n".join(para)
        # champs = tout le bloc, de son bullet jusqu'au bullet suivant (souvent multi-lignes réelles)
        plines = para
        champs_text = None
        for idx, l in enumerate(plines):
            m2 = CHAMPS_LINE_RE.match(l.strip())
            if m2:
                buf = [m2.group(1)]
                for l2 in plines[idx + 1:]:
                    if re.match(r"^\s*-\s", l2):
                        break
                    buf.append(l2)
                champs_text = " ".join(buf)
                break
        for c in codes:
            entries.setdefault(c, []).append((path, start + 1, tagfield, text, champs_text))


# Motifs de refus pour UNE occurrence d'un opcode (DEDUIT/SOURCE/CHAMPS) -- {} = cette occurrence est propre.
# / Refusal motifs for ONE opcode occurrence (DEDUIT/SOURCE/CHAMPS) -- {} = this occurrence is clean.
def gaps_for_one(occ):
    _, _, tagfield, text, champs_text = occ
    gaps = {}
    if "DÉDUIT" in tagfield:
        gaps["DEDUIT"] = f"tag: {tagfield.strip()}"
    if "VÉRIFIÉ" in tagfield and not SOURCE_TOKEN_RE.search(text):
        gaps["SOURCE"] = "aucun chemin/fichier:ligne/§ repérable dans l'entrée"
    if champs_text is None:
        gaps["CHAMPS"] = "aucun bullet `champs:` repéré"
    else:
        ok, why = champs_status(champs_text)
        if not ok:
            gaps["CHAMPS"] = why
    return gaps


def evaluate(occs):
    """FR: motifs de refus pour un opcode ({} = VERT). Un opcode documenté DEUX
    fois (ex. la rafale de bienvenue renvoie « voir §4.1 » vers une entrée
    complète) est jugé sur la MEILLEURE occurrence trouvée, jamais la première
    au hasard — sinon un renvoi de section se lit comme un manque.
    EN: failing motifs (empty = green). An opcode documented twice is judged on
    its BEST occurrence, not an arbitrary first one — else a cross-reference to
    a fuller entry elsewhere reads as a gap."""
    if not occs:
        return {"ABSENT": "aucun fragment ne documente cet opcode"}
    per_occ = [gaps_for_one(o) for o in occs]
    if any(not g for g in per_occ):
        return {}
    common = set(per_occ[0])
    for g in per_occ[1:]:
        common &= set(g)
    result = {}
    for motif in common:
        for g in per_occ:
            if motif in g:
                result[motif] = g[motif]
                break
    return result


# Liste tous les fragments *.md de internal/ (tri déterministe) -- source par défaut si aucun n'est passé en CLI.
# / Lists all *.md fragments in internal/ (deterministic sort) -- default source when none is passed on the CLI.
def default_fragments():
    return sorted(p for p in glob.glob(os.path.join(ETAGE1, "*.md")))


# Scanne tous les fragments, évalue chaque opcode du chemin critique, rend le verdict global + stats.
# / Scans all fragments, evaluates each critical-path opcode, returns the overall verdict + stats.
def run_gate(chemin_path, fragment_paths):
    codes = load_chemin(chemin_path)
    targets = set(codes)
    entries = {}
    for p in fragment_paths:
        scan_fragment(p, targets, entries)
    results = {c: evaluate(entries.get(c, [])) for c in codes}
    stats = {
        "total": len(codes),
        "couverts": sum(1 for c in codes if entries.get(c)),
        "verts": sum(1 for c in codes if not results[c]),
    }
    return stats["verts"] == stats["total"], results, stats, entries


# Affiche le verdict G1 : couverture, conformité, et le détail des manques groupés par motif.
# / Prints the G1 verdict: coverage, conformance, and the gap detail grouped by motif.
def print_report(chemin_path, fragment_paths):
    ok, results, stats, _ = run_gate(chemin_path, fragment_paths)
    print(f"chemin critique : {stats['total']} opcodes — couverts (≥1 fragment) : {stats['couverts']} "
          f"— conformes G1 (VÉRIFIÉ + source + champs) : {stats['verts']}")
    print("VERT — G1 satisfaite" if ok else "ROUGE — G1 non satisfaite")
    if not ok:
        by_motif = {}
        for c, gaps in results.items():
            for motif, detail in gaps.items():
                by_motif.setdefault(motif, []).append((c, detail))
        for motif in MOTIFS:
            if motif in by_motif:
                items = by_motif[motif]
                print(f"  [{motif}] {MOTIFS[motif]} — {len(items)} opcode(s)")
                for c, detail in items:
                    print(f"    {c}: {detail}")
    return ok, stats


# ---------------------------------------------------------------------------
# Épreuve — FR : témoin négatif = l'état ACTUEL (doit être ROUGE aujourd'hui, il
# rend le reste-à-faire du chantier) ; 2 sabotages doivent faire bouger la gate.
# EN : negative witness = TODAY's state (must be red — becomes the swarm's punch
# list) ; 2 sabotages must move the gate's verdict.
# ---------------------------------------------------------------------------
def run_epreuve():
    tmpdir = tempfile.mkdtemp(prefix="gate-g1-epreuve-")
    all_ok = True

    print("=== ÉPREUVE — témoin négatif : état ACTUEL (doit être ROUGE, la carte n'est pas finie) ===\n")
    ok0, stats0 = print_report(DEFAULT_CHEMIN, default_fragments())
    hit0 = not ok0
    all_ok = all_ok and hit0
    print(f"\n{'✅' if hit0 else '❌'} " +
          ("ROUGE comme attendu — ceci est le reste-à-faire du chantier" if hit0
           else "VERT (BUG : la carte devrait être incomplète aujourd'hui)"))

    print("\n=== ÉPREUVE — sabotage 1 : retirer un opcode de chemin-critique.txt ===\n")
    codes = load_chemin(DEFAULT_CHEMIN)
    sab1 = os.path.join(tmpdir, "chemin-critique-sabotage1.txt")
    with open(sab1, "w", encoding="utf-8") as f:
        f.write("\n".join(codes[:-1]))
    _, stats1 = print_report(sab1, default_fragments())
    hit1 = stats1["total"] == stats0["total"] - 1
    all_ok = all_ok and hit1
    print(f"{'✅' if hit1 else '❌'} total {stats0['total']} → {stats1['total']} (attendu : -1)")

    print("\n=== ÉPREUVE — sabotage 2 : `jru` VÉRIFIÉ → DÉDUIT dans une copie temporaire ===\n")
    frags = default_fragments()
    seq_candidates = [p for p in frags if "SEQUENCE-CHEMIN-CRITIQUE" in os.path.basename(p)]
    if not seq_candidates:
        print("⚠️  SEQUENCE-CHEMIN-CRITIQUE-JONDO.md introuvable — sabotage 2 impossible")
        all_ok = False
    else:
        seq_path = seq_candidates[0]
        original = open(seq_path, encoding="utf-8").read()
        needle = "### Opcode `jru` | dir: S2C | nom proposé: `CurrentMapMessage` | tag: VÉRIFIÉ"
        sabotaged = original.replace(needle, needle.replace("tag: VÉRIFIÉ", "tag: DÉDUIT"), 1)
        changed = sabotaged != original
        sab2 = os.path.join(tmpdir, "SEQUENCE-sabotage2.md")
        with open(sab2, "w", encoding="utf-8") as f:
            f.write(sabotaged)
        other = [p for p in frags if p != seq_path]
        _, results2, _, _ = run_gate(DEFAULT_CHEMIN, other + [sab2])
        hit2 = changed and ("DEDUIT" in results2.get("jru", {}))
        all_ok = all_ok and hit2
        print(f"{'✅' if hit2 else '❌'} substitution appliquée={changed} ; `jru` après sabotage : "
              f"{results2.get('jru', {})}")

    print(f"\n=== BILAN ÉPREUVE : {'MORD DANS LES DEUX SENS ✅' if all_ok else 'ÉCHEC ❌'} ===")
    return 0 if all_ok else 1


# Point d'entrée CLI : --epreuve, ou --chemin FICHIER + fragments explicites (sinon les défauts).
# / CLI entry point: --epreuve, or --chemin FILE + explicit fragments (else the defaults).
def main():
    args = sys.argv[1:]
    if "--epreuve" in args:
        sys.exit(run_epreuve())
    chemin, frags, i = DEFAULT_CHEMIN, [], 0
    while i < len(args):
        if args[i] == "--chemin" and i + 1 < len(args):
            chemin, i = args[i + 1], i + 2
        else:
            frags.append(args[i]); i += 1
    ok, _ = print_report(chemin, frags or default_fragments())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
