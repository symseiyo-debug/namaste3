#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_handlers.py <emu> <racine> — table message <-> protocol_id <-> handler, 0-LLM.
Deterministic 0-LLM handler extractor (Namaste 3, etage 1, loi L1 du cahier).

POURQUOI :
Formes mesurees AVANT d'ecrire ce script (grep -c sur les 6 depots, 04/09) :
  jiva      : attribut [WorldHandler(X.Id)] / [AuthHandler(X.Id)], empile (multi-opcode -> 1 methode).
  giny/ginycore/oneair/symbioz : attribut [MessageHandler] SANS argument (l'Id vient du TYPE du
              1er parametre de la methode, cf. ARCHI-REFERENCE-GINY.md §C.2). Symbioz porte aussi
              [SpellEffectHandler(...)]/[CustomSpellHandler...] (effets de sort, PAS des handlers
              reseau) : notre regex ne matche que "[MessageHandler]" exact, ils sont donc deja
              exclus sans action supplementaire.
  jondo     : PAS d'attribut. Dispatch par if/else sur Op.Uri(Op.X). La table datos/anclas_*.tsv
              (curee, sourcee "code + 242 captures", cf. son propre en-tete) est LA source ici :
              cf. cahier §1 "JondoEmu = MANUEL : on lit le .proto/tables comme spec". Colonne
              handler mesuree PROSE, pas machine-generee (50/176 = Classe.Methode strict, le
              reste = nom nu, liste separee par virgule, ou note entre parentheses) — le
              parseur reconnait ces 3 formes explicitement, jamais en devine une 4e.

Direction : un handler serveur ne route QUE des messages ENTRANTS (c'est la nature meme du
dispatch), donc direction=C2S pour CHAQUE ligne de handlers-<emu>.tsv, deduite de la POSITION
structurelle (le message est recu par le handler), pas d'une convention de nommage — plus fort
que l'heuristique "*Request/*Message" suggeree, jamais fausse par construction.

COMMENT LANCER : python3 extraire_handlers.py <emu> <racine> (emu dans jiva/giny/ginycore/oneair/
    symbioz/jondo) | python3 extraire_handlers.py --epreuve [emu]
GATE : --epreuve par emu (candidats/extraits/a-classer == attendus, partition len(extraits)+
    len(a_classer)==candidats, rejeu sha256 byte-identique sur les 2 TSV).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

from _lib_extract import (
    CLASS_RE, build_message_id_lookup, iter_cs_files, write_tsv, sha256_file
)

HEADER = ["message_nom", "protocol_id", "direction", "handler_classe", "handler_methode",
          "fichier:ligne", "emu", "version"]
ACLASSER_HEADER = ["raw", "motif", "fichier:ligne", "classe_courante", "emu", "version"]

EMU_CONFIG = {
    # emu: (family, version_label)
    "jiva":    ("attr_jiva", "2.42"),
    "giny":    ("attr_giny", "2.68"),
    "ginycore": ("attr_giny", "2.63"),
    "oneair":  ("attr_giny", "2.68-docker"),
    "symbioz": ("attr_giny", "2.38"),
    "jondo":   ("jondo_tsv", "3.6.10.10"),
}

JIVA_ATTR_RE = re.compile(r"^\s*\[(World|Auth)Handler\(\s*(\w+)\.Id\s*(?:,.*)?\)\]\s*$")
# Forme mesuree apres coup (04/09) : 26/232 attributs Jiva portent des arguments nommes
# supplementaires -- [WorldHandler(X.Id, ShouldBeLogged = false, IsGamePacket = false)] (cf.
# ARCHI-REFERENCE-JIVA.md §D.2). 1ere version du regex les ratait EN SILENCE (208 candidats
# au lieu de 232) : corrige pour capturer le nom de classe quel que soit ce qui suit la virgule.
GINY_ATTR_RE = re.compile(r"^\s*\[MessageHandler\]\s*$")
# Forme "vivante mais non reconnue" (code reel, pas un commentaire) : sert a ne JAMAIS faire
# disparaitre en silence un attribut multi-ligne (2/232 chez Jiva, ex. ApproachHandler.cs:200,
# ses arguments nommes debordent sur la ligne suivante) -- il tombe en a-classer au lieu d'etre
# invisible. L'ancrage ^\s*\[ exclut deja les formes commentees (`// [WorldHandler(...)]`,
# `/*[WorldHandler(...)]`) : mesure faite (9/234 chez Jiva sont du code MORT commente, un grep
# brut sans ancrage de debut de ligne les compte a tort comme candidats).
LOOSE_LIVE_ATTR_RE = {
    "attr_jiva": re.compile(r"^\s*\[(World|Auth)Handler\("),
    "attr_giny": re.compile(r"^\s*\[MessageHandler\b"),
}
METHOD_SIG_RE = re.compile(
    r"^\s*(?:public|internal)\s+static\s+(?:async\s+)?[\w<>\[\],\.]+\s+(\w+)\s*"
    r"\(\s*([\w\.]+)\s+\w+\s*,\s*([\w\.]+)\s+\w+\b"
)
COMMENT_OR_BLANK_RE = re.compile(r"^\s*(//.*)?\s*$")


# Extrait les handlers pour les familles a base d'attribut (jiva/giny) : suit classe courante +
# attribut(s) en attente jusqu'a la signature de methode qui les resout.
# / Extracts handlers for the attribute-based families (jiva/giny): tracks the current class +
# pending attribute(s) until the method signature that resolves them.
def extract_attr_family(racine: Path, emu: str, version: str, family: str,
                         lookup: dict[str, tuple[int, str]]):
    """Extrait les handlers pour les familles a base d'attribut (jiva/giny). Retourne
    (rows, aclasser_rows, n_candidats)."""
    attr_re = JIVA_ATTR_RE if family == "attr_jiva" else GINY_ATTR_RE
    loose_re = LOOSE_LIVE_ATTR_RE[family]
    rows: list[list[str]] = []
    aclasser: list[list[str]] = []
    n_candidats = 0

    files = list(iter_cs_files(racine))
    for fi, path in enumerate(files, 1):
        if fi % 500 == 0:
            print(f"  [handlers:{emu}] {fi}/{len(files)} fichiers", flush=True)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        current_class = None
        pending: list[tuple[int, str | None]] = []  # (lineno, message_class_or_None)

        # Verse les attributs en attente vers a-classer (jamais perdus en silence) avec le motif donne.
        # / Flushes pending attributes to a-classer (never silently lost) with the given reason.
        def flush_unmatched(reason: str):
            for lineno, _msgcls in pending:
                aclasser.append([lines[lineno - 1].strip(), reason, f"{path}:{lineno}",
                                  current_class or "", emu, version])
            pending.clear()

        for i, line in enumerate(lines, start=1):
            cm = CLASS_RE.match(line)
            if cm:
                # Une nouvelle classe s'ouvre sans que les attributs en attente aient
                # trouve leur methode : ils sont perdus, on les classe.
                if pending:
                    flush_unmatched("classe suivante avant methode")
                current_class = cm.group(1)
                continue

            am = attr_re.match(line)
            if am:
                n_candidats += 1
                msgcls = am.group(2) if family == "attr_jiva" else None
                pending.append((i, msgcls))
                continue

            if loose_re.match(line):
                # Vivant (pas un commentaire), reconnu comme attribut par la forme large,
                # mais pas par la forme stricte : multi-ligne ou variante atypique. Compte
                # comme candidat, jamais perdu.
                n_candidats += 1
                aclasser.append([line.strip(), "attribut multi-ligne ou forme non reconnue",
                                  f"{path}:{i}", current_class or "", emu, version])
                continue

            if pending:
                if COMMENT_OR_BLANK_RE.match(line):
                    continue  # ligne vide/commentaire entre attribut(s) et methode : on saute
                sm = METHOD_SIG_RE.match(line)
                if sm:
                    method_name = sm.group(1)
                    # Nom court : le 1er parametre peut etre qualifie par son namespace
                    # (mesure sur Giny : "Protocol.IPC.Messages.IPCServerStatusUpdateMessage")
                    # -- on ne garde que le dernier segment pour joindre avec les autres emus,
                    # qui eux ne qualifient jamais (attribut `[WorldHandler(X.Id)]` chez Jiva).
                    param1_type = sm.group(2).rsplit(".", 1)[-1]
                    for lineno, msgcls in pending:
                        message_nom = msgcls if family == "attr_jiva" else param1_type
                        pid, _def = lookup.get(message_nom, ("", ""))
                        rows.append([message_nom, str(pid), "C2S", current_class or "",
                                     method_name, f"{path}:{lineno}", emu, version])
                    pending.clear()
                else:
                    flush_unmatched("attribut sans signature de methode reconnue")
        if pending:
            flush_unmatched("fin de fichier sans methode")

    return rows, aclasser, n_candidats


# ---------------------------------------------------------------------------
# JondoEmu : table anclas_*.tsv comme source (cf. docstring module).
# ---------------------------------------------------------------------------
OP_CONST_RE = re.compile(r'public\s+const\s+string\s+\w+\s*=\s*"([a-z0-9]+)"\s*;')
IDENT_RE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$")
TRAILING_PAREN_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")
VALID_DIRECTIONS = {"C2S", "S2C", "S2C_f3"}


# Lit Op.cs, rend l'ensemble des opcodes VIVANTS de cette build (const string reconnues).
# / Reads Op.cs, returns the set of LIVE opcodes for this build (recognized const strings).
def parse_op_cs(racine: Path) -> set[str]:
    op_file = racine / "Jondo.Unity.Protocol" / "Op.cs"
    if not op_file.exists():
        found = list(racine.rglob("Op.cs"))
        op_file = found[0] if found else op_file
    opcodes: set[str] = set()
    if op_file.exists():
        for line in op_file.read_text(encoding="utf-8", errors="replace").splitlines():
            m = OP_CONST_RE.search(line)
            if m:
                opcodes.add(m.group(1))
    return opcodes


# JondoEmu : lit anclas_*.tsv (source MANUELLE, cf. POURQUOI), decompose la colonne handler
# (3 formes reconnues : Classe.Methode / nom nu / liste separee par virgule) sans en deviner une 4e.
# / JondoEmu: reads anclas_*.tsv (MANUAL source, see POURQUOI), decomposes the handler column
# (3 recognized forms: Class.Method / bare name / comma-separated list) without guessing a 4th.
def extract_jondo(racine: Path, version: str):
    rows: list[list[str]] = []
    aclasser: list[list[str]] = []
    n_candidats = 0
    n_sans_handler = 0

    opcodes = parse_op_cs(racine)
    tsv_files = sorted((racine / "datos").glob("anclas_*.tsv")) if (racine / "datos").exists() \
        else sorted(racine.rglob("anclas_*.tsv"))

    for tsv in tsv_files:
        lines = tsv.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 6:
                aclasser.append([line, f"ligne TSV a {len(cols)} colonnes (6 attendues)",
                                  f"{tsv}:{lineno}", "", "jondo", version])
                continue
            opcode, direction, nom_propose, _signif, handler_cell, _forme = cols[:6]
            opcode = opcode.strip()
            direction = direction.strip()

            opcode_ok = opcode in opcodes
            direction_ok = (direction == "" or direction in VALID_DIRECTIONS)

            raw_handler = handler_cell.strip()
            if raw_handler in ("", "-"):
                n_sans_handler += 1
                continue

            # Parenthese finale = note, pas structurelle (ex: "GameNodeProxy (empty branch)").
            pm = TRAILING_PAREN_RE.match(raw_handler)
            core = pm.group(1).strip() if pm else raw_handler

            tokens = [t.strip() for t in core.split(",")] if core else []
            if not tokens:
                tokens = [core]

            for tok in tokens:
                n_candidats += 1
                reasons = []
                if not opcode_ok:
                    reasons.append("opcode absent de Op.cs")
                if not direction_ok:
                    reasons.append("direction non reconnue")
                if not IDENT_RE.match(tok):
                    reasons.append("forme prose non decomposable")

                if reasons:
                    aclasser.append([line, "; ".join(reasons), f"{tsv}:{lineno}", "", "jondo",
                                      version])
                    continue

                if "." in tok:
                    classe, methode = tok.split(".", 1)
                else:
                    classe, methode = "", tok
                rows.append([nom_propose.strip(), opcode, direction if direction else "",
                             classe, methode, f"{tsv}:{lineno}", "jondo", version])

    return rows, aclasser, n_candidats, n_sans_handler


# Dispatch vers extract_jondo() ou extract_attr_family() selon l'emu, ecrit les 2 TSV
# (handlers + a-classer), rend les stats de partition.
# / Dispatches to extract_jondo() or extract_attr_family() per emu, writes both TSVs
# (handlers + a-classer), returns partition stats.
def run(emu: str, racine: Path, outdir: Path) -> dict:
    family, version = EMU_CONFIG[emu]
    stats: dict = {"emu": emu, "version": version}

    if family == "jondo_tsv":
        rows, aclasser, n_candidats, n_sans = extract_jondo(racine, version)
        stats["opcodes_sans_handler_documente"] = n_sans
    else:
        print(f"[handlers:{emu}] indexation des Id de message (1 passe)...", flush=True)
        lookup = build_message_id_lookup(racine)
        stats["messages_indexes_pour_resolution_id"] = len(lookup)
        rows, aclasser, n_candidats = extract_attr_family(racine, emu, version, family, lookup)
        stats["handlers_sans_id_resolu"] = sum(1 for r in rows if r[1] == "")

    write_tsv(outdir / f"handlers-{emu}.tsv", HEADER, rows)
    write_tsv(outdir / f"a-classer-{emu}.tsv", ACLASSER_HEADER, aclasser)

    stats["candidats"] = n_candidats
    stats["extraits"] = len(rows)
    stats["a_classer"] = len(aclasser)
    stats["partition_ok"] = (len(rows) + len(aclasser) == n_candidats)
    return stats


def epreuve(emu: str) -> bool:
    """Rejeu byte-identique + sabotage (conforme/casse/doublon), cf. cahier §"--epreuve"."""
    import tempfile
    family, version = EMU_CONFIG[emu]
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        outdir = racine / "out"
        outdir.mkdir()

        if family == "jondo_tsv":
            (racine / "Jondo.Unity.Protocol").mkdir()
            (racine / "Jondo.Unity.Protocol" / "Op.cs").write_text(
                'public static class Op {\n'
                '    public const string Xyz = "xyz";\n'
                '}\n', encoding="utf-8")
            (racine / "datos").mkdir()
            tsv = (
                "# header\n"
                "# columnas: opcode\tdireccion\tnombre\tsignificado\thandler\tforma\n"
                "xyz\tC2S\tConformeMessage\tun test\tSampleHandler.HandleConforme\tf1:int\n"
                "xyz\tC2S\tConformeMessage\tdoublon volontaire\tSampleHandler.HandleConforme\tf1:int\n"
                "xyz\tC2S\tConformeMessage\tprose non decomposable\tGameNodeProxy -> chest or zaap\tf1:int\n"
                "abc\tC2S\tInconnu\topcode absent de Op.cs\tSampleHandler.HandleAbsent\t-\n"
                "xyz\tC2S\tSansHandler\taucun handler documente\t-\t-\n"
            )
            (racine / "datos" / "anclas_test.tsv").write_text(tsv, encoding="utf-8")
            stats1 = run("jondo", racine, outdir)
            expected_candidats = 4  # 5 tokens - 1 ligne sans-handler (skip avant comptage)
            expected_extraits = 2   # conforme + doublon
            expected_aclasser = 2   # prose + opcode absent
        else:
            (racine / "src").mkdir()
            if family == "attr_jiva":
                content = (
                    "namespace Test\n{\n    public static class SampleHandler\n    {\n"
                    "        [WorldHandler(ConformeMessage.Id)]\n"
                    "        public static void HandleConforme(WorldClient client, ConformeMessage message)\n"
                    "        {\n        }\n\n"
                    "        [WorldHandler(ConformeMessage.Id)]\n"
                    "        public static void HandleConforme(WorldClient client, ConformeMessage message)\n"
                    "        {\n        }\n\n"
                    "        [WorldHandler(CasseMessage.Id)]\n"
                    "        public static int HandleCasseBadSignature\n"
                    "        {\n            get { return 0; }\n        }\n"
                    "    }\n\n"
                    "    public class ConformeMessage : Message\n    {\n"
                    "        public const uint Id = 9999;\n"
                    "    }\n}\n"
                )
            else:
                content = (
                    "namespace Test\n{\n    public static class SampleHandler\n    {\n"
                    "        [MessageHandler]\n"
                    "        public static void HandleConforme(ConformeMessage message, WorldClient client)\n"
                    "        {\n        }\n\n"
                    "        [MessageHandler]\n"
                    "        public static void HandleConforme(ConformeMessage message, WorldClient client)\n"
                    "        {\n        }\n\n"
                    "        [MessageHandler]\n"
                    "        public static int HandleCasseBadSignature\n"
                    "        {\n            get { return 0; }\n        }\n"
                    "    }\n\n"
                    "    public class ConformeMessage : NetworkMessage\n    {\n"
                    "        public const ushort Id = 9999;\n"
                    "    }\n}\n"
                )
            (racine / "src" / "Sample.cs").write_text(content, encoding="utf-8")
            stats1 = run(emu, racine, outdir)
            expected_candidats = 3
            expected_extraits = 2
            expected_aclasser = 1

        h1 = sha256_file(outdir / f"handlers-{emu}.tsv")
        a1 = sha256_file(outdir / f"a-classer-{emu}.tsv")
        # 2e passe : rejeu byte-identique.
        outdir2 = racine / "out2"
        outdir2.mkdir()
        run("jondo" if family == "jondo_tsv" else emu, racine, outdir2)
        h2 = sha256_file(outdir2 / f"handlers-{emu}.tsv")
        a2 = sha256_file(outdir2 / f"a-classer-{emu}.tsv")

        checks = [
            ("candidats mesures == attendus",
             stats1["candidats"] == expected_candidats,
             f"{stats1['candidats']} vs {expected_candidats}"),
            ("extraits == attendus (conforme+doublon comptes)",
             stats1["extraits"] == expected_extraits,
             f"{stats1['extraits']} vs {expected_extraits}"),
            ("a-classer == attendus (casse tombe, jamais disparait)",
             stats1["a_classer"] == expected_aclasser,
             f"{stats1['a_classer']} vs {expected_aclasser}"),
            ("partition len(extraits)+len(a_classer) == candidats",
             stats1["partition_ok"], str(stats1)),
            ("rejeu byte-identique (sha256 handlers)", h1 == h2, f"{h1} vs {h2}"),
            ("rejeu byte-identique (sha256 a-classer)", a1 == a2, f"{a1} vs {a2}"),
        ]
        print(f"\n=== --epreuve extraire_handlers.py {emu} ===")
        for label, passed, detail in checks:
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}  ({detail})")
            ok = ok and passed
    return ok


# Point d'entree CLI : --epreuve [emu], ou une extraction reelle <emu> <racine>.
# / CLI entry point: --epreuve [emu], or a real extraction <emu> <racine>.
def main():
    if len(sys.argv) < 2:
        print("usage: extraire_handlers.py <emu> <racine> | extraire_handlers.py --epreuve [emu]")
        sys.exit(2)
    if sys.argv[1] == "--epreuve":
        emus = [sys.argv[2]] if len(sys.argv) > 2 else list(EMU_CONFIG)
        all_ok = all(epreuve(e) for e in emus)
        sys.exit(0 if all_ok else 1)

    if len(sys.argv) != 3:
        print("usage: extraire_handlers.py <emu> <racine>")
        sys.exit(2)
    emu, racine_s = sys.argv[1], sys.argv[2]
    if emu not in EMU_CONFIG:
        print(f"emu inconnu: {emu} (attendus: {list(EMU_CONFIG)})")
        sys.exit(2)
    # FR : pas de .resolve() ici — un chemin RELATIF donné en argument (ex. `refs/JondoEmu`,
    #      `sources/client268-as3`) reste relatif dans les citations `fichier:ligne` écrites plus
    #      bas. Absolutiser ici graverait le chemin absolu de la machine qui a lancé l'extraction
    #      dans une sortie censée être portable (mesuré : c'est ce bug qui avait produit des
    #      chemins absolus machine-spécifiques dans les tables versées).
    # EN : no .resolve() here — a RELATIVE root path given on the CLI stays relative in the
    #      `file:line` citations written below. Resolving it would bake the invoking machine's
    #      absolute layout into an output meant to be portable (measured: this is exactly the bug
    #      that had leaked machine-specific absolute paths into the checked-in tables).
    racine = Path(racine_s)
    outdir = Path(__file__).resolve().parent
    stats = run(emu, racine, outdir)
    print(f"[handlers:{emu}] {stats}")


if __name__ == "__main__":
    main()
