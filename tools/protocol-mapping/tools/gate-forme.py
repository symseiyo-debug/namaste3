#!/usr/bin/env python3
"""
gate-forme.py — Garde de forme §4 pour les fragments de carte étage 1 (Namaste 3).
FR/EN : vérifie mécaniquement (0 LLM, stdlib) la forme d'un fragment (§4 + L2).
Grammaire PARTAGÉE avec l'ingesteur du graphe-protocole — chaque règle vient d'un
piège mesuré, jamais deviné. / Shared grammar with the protocol graph — every rule traces to a
measured real trap, never a guess.
Usage: gate-forme.py <fragment.md> [...] | gate-forme.py --epreuve
"""
import os
import tempfile
import re
import sys

# FR/EN: grammaire partagée avec le graphe-protocole — chaque extension mesurée dans son dépôt
# (`find <dépôt> | grep -oE '\.[a-z0-9]+$'`) avant ajout ; une extension manquante
# ROUGIT une citation exacte ET peut la lire comme un dossier sans slash.
KNOWN_EXTS = ("cs|md|proto|tsv|sql|dll|bin|py|json|log|ps1|js|yml|yaml|tt|csproj|thrift|d2o|xml|txt|asar"
              "|go|rs|toml|hpp|cpp|h|cc|cxx|ini|ts|tsx|mjs|sh|as|bat")
# FR: cité EN ENTIER (comme LICENSE) — bin/dll/txt/json gardent AUSSI leur forme
# `:NNN`/`:offset` (KNOWN_EXTS) : un binaire ou un dump/table (32 936 littéraux
# dans `il2cpp.json`) se cite par offset OU entier, jamais les deux à la fois.
# EN: cited AS A WHOLE (like LICENSE) — bin/dll/txt/json ALSO keep their `:NNN`
# form: a binary or data dump is cited by offset OR whole, either is fine.
WHOLE_FILE_EXTS = "vcxproj|sln|swf|dat|bin|dll|txt|json"
BARE_FILES = r"(?:LICENSE|README|Makefile|Dockerfile|\.gitignore|go\.mod|go\.sum|Cargo\.lock)"
SOURCE_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./\-]*\.(?:" + KNOWN_EXTS + r"):\d[\d,\-]*"           # chemin:NNN[,-...]
    r"|(?:[A-Za-z0-9_.\-]+/)*" + BARE_FILES + r"\b"                                 # LICENSE/README… (± dossier)
    r"|[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:" + WHOLE_FILE_EXTS + r")\b"                # .vcxproj/.sln (entier, pas de ligne)
    r"|[A-Za-z0-9_]{2,}[A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)*/(?![A-Za-z0-9_.\-])"  # dossier/ — PAS un préfixe
    r"|§\s?\(?[A-Za-z0-9.\-]+\)?"                                                    # §X.Y
    r"|`:\d[\d,\-]*`"                                                                 # `:19` — suite d'un fichier déjà cité
)
# FR/EN: piège connu (Giny) — `Fighter.cs:1` = 2721 lignes est un COMPTE, pas une référence.
MESURE_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./\-]*\.(?:" + KNOWN_EXTS + r")(?::\d[\d,\-]*)?`?\s*=\s*\d+"
)
BACKTICK_SPAN_RE = re.compile(r"`([^`\n]+)`")
# FR: "fichier" au sens large pour R3 — un nom de classe seul (`SomeClass`) ne suffit PAS.
FILE_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_./\-]*/[A-Za-z0-9_./\-]*"
    r"|[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:" + KNOWN_EXTS + r")"
    r"|" + BARE_FILES
)
PATH_TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)+/?")
# FR/EN: R4 mesure une FORME, pas l'ACTE de recopie tierce — par défaut, R4 ne
# s'applique qu'en zone de LECTURE (internal/ + protocol-mapping/) ; ailleurs un
# marqueur la désactive (ELLE SEULE, jamais R2/R3), imprimé. Ignoré DANS la zone.
CONTRAT_INTERNE_MARKER = "<!-- gate-forme: contrat-interne -->"

def in_reading_zone(path):
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    return any(p == "internal" for p in parts) or any(p == "protocol-mapping" for p in parts)

HEADER_TAG_RE = re.compile(r"^#{2,4}\s.*?\|\s*tag\s*:\s*(.*)$")
HEADER_DIR_RE = re.compile(r"^#{2,4}\s.*\|\s*dir\s*:")
BOLD_TAG_RE = re.compile(r"^-?\s*\*{1,2}tag\*{1,2}\s*:\s*(.*)$", re.IGNORECASE)
SI_DEDUIT_RE = re.compile(r"si\s*\*{0,2}D[ÉE]DUIT\*{0,2}\s*:\s*(.*)$", re.IGNORECASE)
LEADING_TAG_RE = re.compile(r"^-?\s*\*{0,2}(VÉRIFIÉ|DÉDUIT)\b")
# FR: filet large — « comment vérifier » prend mille formes ; un filet étroit refuse la prose réelle.
# EN: wide net — a narrow one wrongly red-flags real prose.
VERIF_KEYWORDS_RE = re.compile(
    r"(?i)(v[ée]rifi|valide?r|confirm|recoup|compar|capturer|mesurer|"
    r"à lire si|non (?:lu|relu|creus[ée]|isol[ée])|hors budget|manque de budget|"
    r"pas fait ici|non recroisé)"
)
NEGATION_PRODDB_RE = re.compile(
    r"(?i)(jamais|aucun|aucune|pas de|⛔|interdit|exclu|ne\s+\w+\s+(?:lire|lu|citer|cit[ée]))"
)
CODE_METHOD_LINE_RE = re.compile(r"^\s*(public|private|internal|protected)\b[^\n]*\(")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")

RULES = {
    "R1-tag-manquant": "un en-tête d'entrée (`| dir: ... |`) sans champ `tag: VÉRIFIÉ|DÉDUIT`",
    "R2-source-manquante": "un `VÉRIFIÉ` sans source (chemin:NNN / dossier/ / §X.Y) repérable",
    "R2-dossier-sans-slash": "un dossier cité SANS son '/' final — remède : l'ajouter",
    "R2-mesure-nest-pas-une-source": "un `fichier = NNN` (un COMPTE) pris pour une référence de ligne",
    "R3-comment-verifier-manquant": "un `DÉDUIT` réel sans façon de le vérifier",
    "R3-deduit-sans-fichier": "un `DÉDUIT` dont le « comment vérifier » ne nomme aucun FICHIER (chemin/extension)",
    "R4-code-csharp-recopie": "un bloc de code C# recopié (méthodes en série)",
    "R5-proddb-comme-source": "`PROD-DB` cité comme SOURCE (hors clause d'exclusion)",
    "R6-entete-incomplete": "en-tête de document incomplet (titre / étage / source)",
}

def excerpt(s, n=140):
    s = " ".join(s.split())
    return (s[:n] + "…") if len(s) > n else s

def paragraphs(lines):
    """FR: blocs séparés par ligne vide ou '---'. EN: blank/'---'-separated blocks."""
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

def expand_units(lines):
    """FR: une table à colonne 'tag' est éclatée ligne par ligne (une entrée/ligne).
    EN: a table with a 'tag' column is exploded row by row (one entry per row)."""
    units = []
    for start, para in paragraphs(lines):
        if len(para) >= 2 and all(TABLE_ROW_RE.match(l) for l in para[:2]):
            cells = [c.strip().lower() for c in para[0].strip().strip("|").split("|")]
            if "tag" in cells:
                for j, row in enumerate(para[1:], start=1):
                    if not TABLE_SEP_RE.match(row):
                        units.append((start + j, "row", [row], row))
                continue
        units.append((start, "para", para, "\n".join(para)))
    return units

# Rend VÉRIFIÉ/DÉDUIT si la 1re ligne non vide/non-titre du paragraphe OUVRE dessus (patron Jiva).
# / Returns VÉRIFIÉ/DÉDUIT if the paragraph's first non-blank/non-heading line OPENS on it (Jiva pattern).
def leading_tag(para_lines):
    for l in para_lines:
        s = l.strip()
        if not s or s.startswith("#"):
            continue
        m = LEADING_TAG_RE.match(s)
        return m.group(1) if m else None
    return None

def classify_unit(kind, lines, text):
    """FR: (forme, tag) — pipe-header, bullet gras, prose (Jiva), ligne de table.
    Reste taggé mais non reconnu → 'unclassified' (compté, jamais jugé).
    EN: (shape, tag) — surfaced-but-unrecognized forms are counted, never judged."""
    for l in lines:
        m = HEADER_TAG_RE.match(l.strip()) or BOLD_TAG_RE.match(l.strip())
        if m:
            return "header", m.group(1)
    if kind == "row":
        return ("row", text) if ("VÉRIFIÉ" in text or "DÉDUIT" in text) else (None, None)
    lt = leading_tag(lines)
    if lt is not None:
        return "prose", lt
    if "VÉRIFIÉ" in text or "DÉDUIT" in text:
        return "unclassified", text
    return None, None

def find_si_deduit(lines):
    """FR/EN: 'si DÉDUIT' déborde souvent sur plusieurs lignes sans nouveau bullet
    (ex. `krt`, 15 lignes) — ne prendre que la 1ère perd des fichiers cités plus
    bas. On rassemble jusqu'au '- ' suivant. / gather until the next '- ' bullet."""
    for idx, l in enumerate(lines):
        m = SI_DEDUIT_RE.search(l)
        if m:
            buf = [m.group(1)]
            for l2 in lines[idx + 1:]:
                if re.match(r"^\s*-\s", l2) or l2.strip().startswith("#"):
                    break
                buf.append(l2)
            return " ".join(buf).strip()
    return None

def dossier_sans_slash(text):
    """FR/EN: chemin multi-segments dans un CODE SPAN (repère de ce corpus, jamais
    « client/serveur » en prose), shaped DOSSIER sans '/' final. Exige 1 segment à
    un seul point (`Giny.CraftableDrop`) ou ≥3 segments — laisse une route HAAPI
    (0 point) ou un typeUrl (`type.ankama.com/jru`, 2 points=domaine) tranquilles."""
    for span in BACKTICK_SPAN_RE.findall(text):
        for m in PATH_TOKEN_RE.finditer(span):
            tok = m.group(0)
            if tok.endswith("/"):
                continue
            segs = tok.split("/")
            last_seg = segs[-1]
            if re.search(r"\.(?:" + KNOWN_EXTS + r"|" + WHOLE_FILE_EXTS + r")$", last_seg) or re.fullmatch(BARE_FILES, last_seg):
                continue
            namespace_like = any(s.count(".") == 1 for s in segs)
            if len(segs) < 3 and not namespace_like:
                continue
            return tok
    return None

def check_unit(shape, tagfield, text, lineno, lines, violations, stats):
    if shape == "unclassified":
        stats["a_classer"] += 1
        return
    genuine_verifie = "VÉRIFIÉ" in tagfield
    genuine_deduit = "DÉDUIT" in tagfield
    stats["entries"] += 1
    stats["verifie"] += genuine_verifie
    stats["deduit"] += genuine_deduit

    # FR: annonce de section finissant par ':' = pas un fait feuille isolé.
    if shape == "prose" and text.rstrip().endswith(":") and len(text.split()) < 25:
        return

    if genuine_verifie:
        # FR/EN: ces 2 pièges mordent TOUJOURS, même avec une source valide
        # ailleurs — l'ingestion se fait par CHAMP, un piège local reste local.
        m = MESURE_RE.search(text)
        if m:
            violations.setdefault("R2-mesure-nest-pas-une-source", []).append(
                (lineno, f"« {m.group(0)} » est un COMPTE, pas une ligne — {excerpt(text)}"))
        d = dossier_sans_slash(text)
        if d:
            violations.setdefault("R2-dossier-sans-slash", []).append(
                (lineno, f"« {d} » sans '/' final (remède: « {d}/ ») — {excerpt(text)}"))
        if not SOURCE_TOKEN_RE.search(text):
            violations.setdefault("R2-source-manquante", []).append((lineno, excerpt(text)))

    if genuine_deduit:
        si_val = find_si_deduit(lines if shape != "row" else [text])
        ok, isolated = False, False
        if si_val is not None and re.sub(r"[.\s]+$", "", si_val).strip().lower() not in ("n/a", "na", "-", "", "none"):
            ok, isolated = True, True
        ok = ok or bool(VERIF_KEYWORDS_RE.search(text))
        if not ok:
            violations.setdefault("R3-comment-verifier-manquant", []).append((lineno, excerpt(text)))
        elif isolated and not FILE_TOKEN_RE.search(si_val):
            violations.setdefault("R3-deduit-sans-fichier", []).append((lineno, excerpt(si_val)))

# R1: un opcode sans tag est invisible à L2. / an untagged opcode is invisible to L2.
def check_r1(lines, violations):
    for i, l in enumerate(lines):
        s = l.strip()
        if HEADER_DIR_RE.match(s) and not re.search(r"tag\s*:\s*(VÉRIFIÉ|DÉDUIT)", s):
            violations.setdefault("R1-tag-manquant", []).append((i + 1, excerpt(s)))

# R4: ≥2 méthodes en série dans un bloc -- rationale complet plus haut (CONTRAT_INTERNE_MARKER).
def check_r4(lines, violations, path, notes):
    zone = in_reading_zone(path)
    marker = any(CONTRAT_INTERNE_MARKER in l for l in lines[:15])
    if marker and not zone:
        notes.append("R4 désactivé par marqueur (`contrat-interne`, hors zone de lecture internal/protocol-mapping/)")
        return
    in_fence, fence_start, fence_lines = False, None, []
    for i, l in enumerate(lines):
        if l.strip().startswith("```"):
            if not in_fence:
                in_fence, fence_start, fence_lines = True, i + 1, []
            else:
                hits = [fl for fl in fence_lines if CODE_METHOD_LINE_RE.match(fl)]
                if len(hits) >= 2:
                    violations.setdefault("R4-code-csharp-recopie", []).append(
                        (fence_start, excerpt(" / ".join(hits[:3]))))
                in_fence = False
            continue
        if in_fence:
            fence_lines.append(l)

# R5: `PROD-DB` cité comme SOURCE (ligne rouge du cahier, hors négation). / red-line prod data.
def check_r5(lines, violations):
    for i, l in enumerate(lines):
        if "prod-db" in l.lower() and re.search(r"(?i)source\s*[:：]", l) and not NEGATION_PRODDB_RE.search(l):
            violations.setdefault("R5-proddb-comme-source", []).append((i + 1, excerpt(l)))

# R6: titre/étage/source manquants dans les 15 1res lignes. / missing in the first 15 lines.
def check_r6(lines, violations):
    head = lines[:15]
    joined = "\n".join(head)
    missing = []
    if not any(re.match(r"^#\s+\S", l) for l in head):
        missing.append("titre (# ...)")
    if not re.search(r"(?i)étage", joined):
        missing.append("mention d'étage")
    if not re.search(r"(?i)source", joined):
        missing.append("mention de source(s) lue(s)")
    if missing:
        violations.setdefault("R6-entete-incomplete", []).append((1, ", ".join(missing)))

def check_fragment(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().replace("\r\n", "\n").split("\n")
    violations = {}
    notes = []
    stats = {"entries": 0, "verifie": 0, "deduit": 0, "a_classer": 0}
    check_r1(lines, violations)
    check_r4(lines, violations, path, notes)
    check_r5(lines, violations)
    check_r6(lines, violations)
    for start, kind, ulines, utext in expand_units(lines):
        shape, tagfield = classify_unit(kind, ulines, utext)
        if shape is not None:
            check_unit(shape, tagfield, utext, start + 1, ulines, violations, stats)
    return len(violations) == 0, violations, stats, notes

def print_report(path, ok, violations, stats, notes):
    print(f"\n--- {path} ---")
    print(f"entrées={stats['entries']}  VÉRIFIÉ={stats['verifie']}  "
          f"DÉDUIT réels={stats['deduit']}  à_classer={stats['a_classer']}")
    for n in notes:
        print(f"  [note] {n}")
    print("VERT" if ok else "ROUGE")
    for rule, hits in violations.items():
        print(f"  [{rule}] {RULES.get(rule, '')} — {len(hits)} occurrence(s)")
        for lineno, exc in hits[:8]:
            print(f"    ligne {lineno}: {exc}")

WITNESS_HEAD = "# Fragment témoin — {rule}\n\n> Étage 1, domaine témoin (fabriqué pour l'épreuve).\n\n"
WITNESSES = {
    "R2-source-manquante": """### Opcode `wp1` | dir: C2S | nom proposé: `FakeMessage` | tag: VÉRIFIÉ
- source: n/a
- si DÉDUIT: n/a
""",
    "R3-comment-verifier-manquant": """### Opcode `wp2` | dir: S2C | nom proposé: `FakeGuessMessage` | tag: DÉDUIT
- source: FakeFile.cs:12
- si DÉDUIT: n/a
""",
    "R4-code-csharp-recopie": """### Opcode `wp3` | dir: S2C | nom proposé: `CopiedCodeMessage` | tag: VÉRIFIÉ
- source: FakeHandler.cs:10
- si DÉDUIT: n/a

```csharp
public class FakeHandler
{
    public static void HandleFoo(WorldClient client, FooMessage msg) { client.Send(new BarMessage()); }
    private static void HandleBar(WorldClient client, BarMessage msg) { client.Send(new BazMessage()); }
}
```
""",
    "R5-proddb-comme-source": """### Opcode `wp4` | dir: C2S | nom proposé: `Wp4Message` | tag: VÉRIFIÉ
- source: world_PROD-DB/players.sql:42
- si DÉDUIT: n/a
""",
    "R3-deduit-sans-fichier": """### Opcode `wp5` | dir: S2C | nom proposé: `FakeInternalMessage` | tag: DÉDUIT
- source: FakeFile.cs:20
- si DÉDUIT: le comportement dépend de `SomeInternalClass`, à vérifier en relisant le code correspondant.
""",
    "R2-dossier-sans-slash": """### Opcode `wp6` | dir: C2S | nom proposé: `FakeModuleMessage` | tag: VÉRIFIÉ
- source: `Modules/Fake.CraftableDrop`, un module chargé au démarrage
- si DÉDUIT: n/a
""",
    "R2-mesure-nest-pas-une-source": """### Opcode `wp7` | dir: S2C | nom proposé: `FakeCountMessage` | tag: VÉRIFIÉ
- source: `FakeHandler.cs:1` = 2721 lignes
- si DÉDUIT: n/a
""",
}
# FR: témoin négatif — un fichier CONVENTIONNEL sans extension reste une source
# valide. EN: negative witness — a conventional extensionless file stays valid.
WITNESS_LICENSE_OK = """### Opcode `wp8` | dir: C2S | nom proposé: `FakeLicenseCheckMessage` | tag: VÉRIFIÉ
- source: vendor/FakeRepo/LICENSE
- si DÉDUIT: n/a
"""
# FR: témoin R4 en ZONE de lecture — le marqueur doit être IGNORÉ, R4 doit mordre.
# EN: R4 witness INSIDE the reading zone — marker ignored, R4 must still bite.
WITNESS_R4_MARKER_IN_ZONE = """# Fragment témoin — marqueur en zone de lecture

<!-- gate-forme: contrat-interne -->

> Étage 1, domaine témoin (fabriqué pour l'épreuve) — source : dépôt tiers fictif.

### Opcode `wp9` | dir: S2C | nom proposé: `FakeZoneMessage` | tag: VÉRIFIÉ
- source: FakeHandlerZone.cs:10
- si DÉDUIT: n/a

```csharp
public class FakeHandlerZone { public static void HandleFoo(WorldClient c, FooMessage m) { c.Send(new BarMessage()); }
private static void HandleBar(WorldClient c, BarMessage m) { c.Send(new BazMessage()); } }
```
"""
INTERFACES_MD = "server/INTERFACES.md"
# FR/EN: (ext, dépôt mesuré, forme VALIDE, forme VOISINE INVALIDE) — chaque
# extension mord dans les deux sens avant d'être crue. swf/dat/bin/dll: formes ENTIÈRES.
EXTENSION_WITNESSES = [
    ("ts", "dofus3-gatherer", "src/index.ts:42", "src/index.ts"),
    ("tsx", "dofus3-gatherer", "components/App.tsx:10", "components/App.tsx"),
    ("mjs", "dofus3-gatherer", "scripts/build.mjs:5", "scripts/build.mjs"),
    ("sh", "dofus-unity-protocol-builder", "tools/run.sh:12", "tools/run.sh"),
    ("as", "client242-as3", "scripts/Dofus.as:88", "scripts/Dofus.as"),
    ("bat", "dofus-emu-dev", "worldServer.bat:3", "worldServer.bat"),
    ("swf", "dofus-server-client-2.68", "DofusInvoker.swf", "DofusInvoker.exe"),
    ("dat", "analyse3.0", "global-metadata.dat", "global-metadata.exe"),
    ("bin", "JondoEmu", "world_etapa1.bin", "world_etapa1.exe"),
    ("dll", "GameAssembly", "GameAssembly.dll", "GameAssembly.exe"),
]

REAL_FRAGMENTS_GREEN = [
    "internal/ARCHI-REFERENCE-JIVA.md",
    "internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md",
    "internal/LAUNCHER-BETA-CROISEMENT-ZAAP.md",
    "internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md",
    # FR: Giny corrigé EN PARALLÈLE ailleurs dans le projet (mtime+grep vérifiés) —
    # remesuré propre, déplacé ici depuis le rouge attendu.
    # EN: Giny fixed IN PARALLEL elsewhere in the project (mtime+grep verified) —
    # remeasured clean, moved here from red-expected.
    "internal/ARCHI-REFERENCE-GINY.md",
]
REAL_FRAGMENTS_RED_EXPECTED = {}

# FR: rejoue TOUS les témoins + les fragments réels attendus verts — l'épreuve à deux sens.
# EN: replays ALL witnesses + the real fragments expected green — the two-way proof.
def run_epreuve():
    tmpdir = tempfile.mkdtemp(prefix="gate-forme-epreuve-")
    all_ok = True
    print("=== ÉPREUVE — témoins positifs (doivent ROUGIR sur la BONNE règle) ===\n")
    for rule, body in WITNESSES.items():
        p = os.path.join(tmpdir, f"witness-{rule}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(WITNESS_HEAD.format(rule=rule) + body)
        ok, violations, _, _ = check_fragment(p)
        hit = (not ok) and (rule in violations)
        all_ok = all_ok and hit
        got = "VERT (BUG : aucune règle n'a mordu)" if ok else ", ".join(violations.keys())
        print(f"{'✅' if hit else '❌'} {os.path.basename(p)} — attendu {rule} — obtenu: {got}")

    print("\n=== ÉPREUVE — témoin négatif dédié (fichier conventionnel, doit rester VERT) ===\n")
    p = os.path.join(tmpdir, "witness-OK-fichier-conventionnel.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(WITNESS_HEAD.format(rule="OK-fichier-conventionnel") + WITNESS_LICENSE_OK)
    ok, violations, _, _ = check_fragment(p)
    all_ok = all_ok and ok
    print(f"{'✅' if ok else '❌'} {p} — {'VERT comme attendu' if ok else 'ROUGE (BUG): ' + ', '.join(violations.keys())}")

    print("\n=== ÉPREUVE — R4 : marqueur DANS la zone de lecture, doit rester ROUGE ===\n")
    zdir = os.path.join(tmpdir, "internal")
    os.makedirs(zdir, exist_ok=True)
    p = os.path.join(zdir, "witness-r4-marker-in-zone.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write(WITNESS_R4_MARKER_IN_ZONE)
    ok, violations, _, notes = check_fragment(p)
    hit = (not ok) and ("R4-code-csharp-recopie" in violations)
    all_ok = all_ok and hit
    print(f"{'✅' if hit else '❌'} {p} — attendu ROUGE (marqueur ignoré en zone) — "
          f"obtenu: {'VERT (BUG)' if ok else ', '.join(violations.keys())} ; notes={notes}")

    print("\n=== ÉPREUVE — R4 : INTERFACES.md (étage 3, marqueur réel) doit être VERT ===\n")
    if os.path.exists(INTERFACES_MD):
        ok, violations, stats, notes = check_fragment(INTERFACES_MD)
        hit = ok and any("marqueur" in n or "désactivé" in n for n in notes)
        all_ok = all_ok and hit
        print(f"{'✅' if hit else '❌'} {INTERFACES_MD} — attendu VERT + note — "
              f"obtenu: {'VERT' if ok else 'ROUGE: ' + ', '.join(violations.keys())} ; notes={notes}")
    else:
        print(f"⚠️  {INTERFACES_MD} absent — épreuve incomplète")
        all_ok = False

    print("\n=== ÉPREUVE — extensions ajoutées (valide passe, voisine invalide rougit) ===\n")
    for ext, repo, valid, invalid in EXTENSION_WITNESSES:
        for label, source, want_ok in ((f"{ext}-valide", valid, True), (f"{ext}-invalide", invalid, False)):
            p = os.path.join(tmpdir, f"witness-ext-{label}.md")
            with open(p, "w", encoding="utf-8") as f:
                f.write(WITNESS_HEAD.format(rule=label) +
                         f"### Opcode `wpx` | dir: C2S | nom proposé: `Msg` | tag: VÉRIFIÉ\n"
                         f"- source: `{source}`\n- si DÉDUIT: n/a\n")
            ok, violations, _, _ = check_fragment(p)
            hit = ok == want_ok
            all_ok = all_ok and hit
            print(f"{'✅' if hit else '❌'} .{ext} ({repo}) `{source}` — attendu "
                  f"{'VERT' if want_ok else 'ROUGE'} — obtenu {'VERT' if ok else 'ROUGE: ' + ', '.join(violations.keys())}")

    print("\n=== ÉPREUVE — témoins négatifs stricts (doivent rester VERTS) ===\n")
    for path in REAL_FRAGMENTS_GREEN:
        if not os.path.exists(path):
            print(f"⚠️  {path} absent — épreuve incomplète")
            all_ok = False
            continue
        ok, violations, stats, notes = check_fragment(path)
        all_ok = all_ok and ok
        status = "VERT" if ok else "ROUGE: " + ", ".join(violations.keys())
        print(f"{'✅' if ok else '❌'} {os.path.basename(path)} — {status} "
              f"(entrées={stats['entries']}, VÉRIFIÉ={stats['verifie']}, "
              f"DÉDUIT={stats['deduit']}, à_classer={stats['a_classer']})")
        if not ok:
            print_report(path, ok, violations, stats, notes)

    print("\n=== ÉPREUVE — fragments à ROUGE ATTENDU (pièges réels non corrigés, ne pas toucher) ===\n")
    for path, expected_motifs in REAL_FRAGMENTS_RED_EXPECTED.items():
        if not os.path.exists(path):
            print(f"⚠️  {path} absent — épreuve incomplète")
            all_ok = False
            continue
        ok, violations, stats, notes = check_fragment(path)
        hit = (not ok) and expected_motifs.issubset(violations.keys())
        all_ok = all_ok and hit
        print(f"{'✅' if hit else '❌'} {os.path.basename(path)} — attendu ROUGE sur {sorted(expected_motifs)} "
              f"— obtenu: {'VERT (BUG)' if ok else ', '.join(violations.keys())}")
        print_report(path, ok, violations, stats, notes)

    print(f"\n=== BILAN ÉPREUVE : {'MORD DANS LES DEUX SENS ✅' if all_ok else 'ÉCHEC ❌'} ===")
    return 0 if all_ok else 1

def main():
    args = sys.argv[1:]
    if "--epreuve" in args:
        sys.exit(run_epreuve())
    if not args:
        print("usage: gate-forme.py <fragment.md> [...] | --epreuve")
        sys.exit(1)
    all_ok = True
    for p in args:
        ok, violations, stats, notes = check_fragment(p)
        print_report(p, ok, violations, stats, notes)
        all_ok = all_ok and ok
    sys.exit(0 if all_ok else 1)

if __name__ == "__main__":
    main()
