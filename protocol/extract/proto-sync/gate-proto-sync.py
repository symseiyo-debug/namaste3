#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : Gate déterministe (0 jeton) du maillon proto-sync. Six témoins, refus
    NOMMÉS, rejouables : (a) aucun opcode 3 lettres écrit en dur hors de la table,
    (b) tout opcode du chemin critique présent dans la table, (c) chaque entrée
    porte sa provenance et son statut, (d) rejeu byte-identique (sha256),
    (e) SABOTAGE — renommer un token dans le dump d'entrée doit changer la table
    ET être dit, (f) TÉMOIN NÉGATIF — un opcode inventé est absent.
    / Deterministic gate for the proto-sync link: six witnesses, named refusals.

POURQUOI (05/09/2026) : (d), (e) et (f) sont là parce que les trois pièges qui
    ont coûté le plus cher au chantier sont des VERTS SANS CAUSE.
      · Sans (e), une gate qui lit la table SANS jamais toucher l'entrée serait
        verte même si le générateur ignorait le dump : elle certifierait un
        fichier, pas une chaîne.
      · Sans (f), une table qui contiendrait TOUT serait verte : une barrière
        qui ne sait rien refuser ne distingue rien.
      · Sans (d), une régénération qui dérive d'un rejeu à l'autre passerait
        inaperçue — et c'est tout l'intérêt du ping-pong entre builds.
    (a) est le témoin qui garde la loi L6 : un opcode en dur dans un handler
    compile, passe les tests, et devient faux au patch suivant SANS bruit.

COMMENT LANCER :
    python3 gate-proto-sync.py --out ./out --build 3.6.10.10          # (a)-(d)
    python3 gate-proto-sync.py --out ./out --build 3.6.10.10 --epreuve  # les 6
    python3 gate-proto-sync.py --epreuve --rapide     # les 6, sans rejeu du gros dump

GATE : rc 0 si les témoins joués sont tous verts ; rc 1 sinon, avec un refus
    NOMMÉ par témoin (quoi, où, mesuré combien contre combien attendu).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from _lib_dump import sha256_fichier   # noqa: E402

RACINE = os.path.abspath(os.path.join(ICI, "..", ".."))
DUMP_DEFAUT = os.path.join(RACINE, "internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs")
CHEMIN_CRITIQUE = os.path.join(RACINE, "internal/chemin-critique.txt")
# Zones où un opcode en dur serait un défaut : le socle et le serveur. La zone
# proto-sync elle-même est EXCLUE — c'est elle qui a le droit de nommer les opcodes.
ZONES_SANS_OPCODE = [os.path.join(RACINE, "etage2-socle"), os.path.join(RACINE, "server")]
EXTS_CODE = {".cs", ".go", ".py", ".sh", ".ps1", ".ts", ".js"}
DOSSIERS_IGNORES = {"bin", "obj", "__pycache__", "deplie", "staging", ".venv", ".git",
                    "node_modules", "out", "packages"}
# Opcodes inventés : ils ne doivent exister NULLE PART. Formés hors de l'espace réel
# (aucun token du dump ne commence par 'z' — vérifié à l'exécution par le témoin lui-même).
OPCODES_INVENTES = ["zzq", "zzw", "zzx"]
# FR : marqueur d'exemption L6 pour un littéral de TEST délibérément gardé (ex. seconde
#     transcription indépendante d'une capture réelle, cf. NegativeTests.cs). Une ligne qui PORTE
#     ce marqueur exempte ELLE-MÊME et LA LIGNE QUI SUIT IMMÉDIATEMENT — jamais plus loin (témoin
#     négatif : un 2e littéral posé deux lignes plus bas doit rester couvert par la règle). Le
#     marqueur exige les deux-points pour ne pas se déclencher sur une simple MENTION en prose
#     (« voir le marqueur TEST_ONLY » ne porte pas de « : » et ne déclenche rien).
# EN : L6 exemption marker for a deliberately kept TEST literal (e.g. an independent second
#     transcription of a real capture, see NegativeTests.cs). A line CARRYING this marker exempts
#     ITSELF and THE LINE IMMEDIATELY FOLLOWING — never further (negative witness: a 2nd literal
#     two lines below must stay covered by the rule). The marker requires the colon so a bare prose
#     MENTION ("see the TEST_ONLY marker") carries no ":" and triggers nothing.
MARQUEUR_TEST_ONLY = "TEST_ONLY:"
HORODATAGE_FIGE = "1970-01-01T00:00:00Z"   # fige l'en-tête pour que (d) soit testable


def main(argv=None) -> int:
    """Joue les témoins demandés et rend un verdict global avec refus nommés.
    / Runs the requested witnesses and returns a global verdict with named refusals."""
    ap = argparse.ArgumentParser(description="gate du maillon proto-sync")
    ap.add_argument("--out", default=os.path.join(ICI, "out"), help="dossier des artefacts")
    ap.add_argument("--build", default="3.6.10.10")
    ap.add_argument("--dump", default=DUMP_DEFAUT)
    ap.add_argument("--epreuve", action="store_true", help="joue AUSSI (e) sabotage et (f) témoin négatif")
    ap.add_argument("--rapide", action="store_true", help="saute (d), qui régénère depuis le gros dump")
    a = ap.parse_args(argv)

    table = _charger_table(a.out, a.build)
    resultats = []
    resultats.append(temoin_a_pas_dopcode_en_dur(table))
    resultats.append(temoin_b_chemin_critique(table))
    resultats.append(temoin_c_provenance_et_statut(table))
    if a.rapide:
        resultats.append(("d", "rejeu byte-identique", None, "SAUTÉ (--rapide)"))
    else:
        resultats.append(temoin_d_rejeu(a.out, a.build, a.dump))
    if a.epreuve:
        resultats.append(temoin_e_sabotage())
        resultats.append(temoin_f_temoin_negatif(table))

    print("")
    joues = [r for r in resultats if r[2] is not None]
    for cle, titre, ok, detail in resultats:
        marque = "🟢" if ok else ("⏭️ " if ok is None else "🔴")
        print("%s (%s) %s — %s" % (marque, cle, titre, detail))
    rouges = [r for r in joues if not r[2]]
    print("\nGATE proto-sync : %s (%d témoins joués, %d refus)"
          % ("🟢 VERTE" if not rouges else "🔴 ROUGE", len(joues), len(rouges)))
    return 1 if rouges else 0


def _charger_table(dossier: str, build: str) -> dict:
    """Charge la table de dispatch générée ; son absence est elle-même un refus, pas un plantage.
    / Loads the generated dispatch table; its absence is a refusal, not a crash."""
    chemin = os.path.join(dossier, "dispatch-%s.json" % build)
    if not os.path.exists(chemin):
        print("REFUS : table absente — %s (lancer generer_dispatch.py)" % chemin, file=sys.stderr)
        sys.exit(2)
    with open(chemin, encoding="utf-8") as fh:
        return json.load(fh)


# ── (a) ───────────────────────────────────────────────────────────────────────

# Ce qui fait qu'un littéral de 3 lettres EST un opcode écrit en dur, c'est-à-dire l'ACTE
# que la loi L6 interdit — et non le fait qu'il ressemble à un opcode :
#   · il est posé dans une CONSTANTE (`const string X = "jru"`, `X: str = "jru"`, `X := "jru"`) ;
#   · ou il est collé au préfixe de `typeUrl` ;
#   · ou il est affecté/comparé à quelque chose qui se nomme opcode / typeUrl / messageId.
# Chacun décrit un GESTE, pas un mot. Mesuré le 05/09 : la règle purement lexicale
# (« tout littéral de 3 minuscules qui figure dans la table ») rendait 8 occurrences dont
# 4 sans aucun rapport avec le protocole — `"meh"` (un nom d'action du bot-testeur) et
# `"len"` (une étiquette d'erreur du codec) heurtent par hasard de vrais tokens. Il y a
# 1629 opcodes pour 17 576 triplets possibles : ~9 % des mots de 3 lettres collisionnent.
MOTIFS_ACTE = [
    (re.compile(r'\b(?:const|static\s+readonly|readonly)\s+string\s+\w+\s*=\s*"([a-z]{3})"'),
     "constante C# d'opcode"),
    (re.compile(r'^\s*[A-Z_][A-Z0-9_]*\s*(?::\s*str)?\s*=\s*"([a-z]{3})"\s*$'),
     "constante Python d'opcode"),
    (re.compile(r'\bconst\s+\w+\s*=\s*"([a-z]{3})"'), "constante Go d'opcode"),
    (re.compile(r'type\.ankama\.com/([a-z]{3})'), "typeUrl écrit en dur"),
    (re.compile(r'(?i)\b\w*(?:opcode|typeurl|messageid)\w*\s*(?:==|=|!=)\s*"([a-z]{3})"'),
     "opcode affecté ou comparé en dur"),
]


def temoin_a_pas_dopcode_en_dur(table: dict):
    """Barrière de la loi L6 : l'opcode ne doit vivre que dans la table générée.

    La barrière PROUVE d'abord qu'elle sait mordre : elle se joue sur deux fichiers-témoins,
    un POSITIF (une vraie constante d'opcode en dur) et un NÉGATIF (une constante de 3 lettres
    qui n'est pas un opcode). Sans ces deux-là, un vert ne distinguerait pas « la zone est
    propre » de « le détecteur ne détecte rien ».
    Elle rend deux populations séparées, jamais mélangées :
      · BLOQUANT — l'ACTE est là (constante, typeUrl, affectation à un opcode) ;
      · SIGNALÉ — un littéral de 3 lettres qui collisionne, sans le geste. Signal faible,
        rendu tel quel, non bloquant.
    Une TROISIÈME population, disjointe des deux — EXEMPTÉE — recueille ce que le marqueur
    `TEST_ONLY:` a sorti des deux premières ; elle est TOUJOURS imprimée avec son fichier:ligne,
    jamais en silence (voir MARQUEUR_TEST_ONLY).
    / Self-proving barrier: positive and negative witnesses first, then two separate
      populations — the act (blocking) and mere collisions (reported). A THIRD population —
      EXEMPTED — is always printed with file:line, never silently."""
    ctrl = _controles_du_detecteur()
    if ctrl:
        return ("a", "aucun opcode en dur hors de la table", False, "détecteur non fiable — " + ctrl)
    opcodes = {e["opcode"] for e in table["entrees"] if e["opcode"]}
    bloquants, signales, exemptions, fichiers = [], [], [], 0
    for zone in ZONES_SANS_OPCODE:
        for chemin in _fichiers_de_code(zone):
            fichiers += 1
            rel = os.path.relpath(chemin, RACINE)
            b, s, ex = _scruter(chemin, opcodes)
            bloquants += ["%s:%s" % (rel, x) for x in b]
            signales += ["%s:%s" % (rel, x) for x in s]
            exemptions += ["%s:%s" % (rel, x) for x in ex]
    note = "%d collisions sans geste, signalées non bloquantes : %s" % (
        len(signales), ", ".join(signales[:8])) if signales else "0 collision de littéral"
    exempt_note = "%d lignes exemptées (TEST_ONLY) : %s" % (
        len(exemptions), ", ".join(exemptions)) if exemptions else "0 ligne exemptée (TEST_ONLY)"
    if bloquants:
        return ("a", "aucun opcode en dur hors de la table", False,
                "%d opcodes ÉCRITS EN DUR : %s | POUR SORTIR : lire l'opcode dans "
                "dispatch-<build>.json (champ `type_url`) au lieu du littéral — un opcode figé "
                "reste VERT avec une valeur périmée, c'est exactement le défaut visé par L6 | %s | %s"
                % (len(bloquants), ", ".join(bloquants[:8]), note, exempt_note))
    return ("a", "aucun opcode en dur hors de la table", True,
            "0 opcode écrit en dur sur %d fichiers de code (etage2-socle/, server/) ; "
            "détecteur éprouvé positif ET négatif | %s | %s" % (fichiers, note, exempt_note))


def _lignes_exemptees(chemin: str) -> set:
    """Rend l'ensemble des numéros de ligne exemptés par le marqueur `TEST_ONLY:` — la ligne qui
    le porte, ET la ligne qui la suit immédiatement, jamais plus loin.
    / Returns the line numbers exempted by the `TEST_ONLY:` marker — the line carrying it, AND
    the line immediately following it, never further."""
    exemptees = set()
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        for no, l in enumerate(fh, 1):
            if MARQUEUR_TEST_ONLY in l:
                exemptees.add(no)
                exemptees.add(no + 1)
    return exemptees


def _scruter(chemin: str, opcodes: set):
    """Rend (occurrences de l'ACTE, simples collisions de littéral, lignes EXEMPTÉES par
    `TEST_ONLY:`) pour un fichier. Une ligne exemptée sort de la population bloquante ET de la
    population signalée — elle est reportée à part, JAMAIS en silence (voir temoin_a, qui imprime
    chaque exemption avec son fichier:ligne).
    / Returns (acts, mere collisions, `TEST_ONLY:`-exempted hits) for one file. An exempted line
    leaves both the blocking and the signalled population — reported separately, NEVER silently
    (see temoin_a, which prints every exemption with its file:line)."""
    exemptees = _lignes_exemptees(chemin)
    re_lit = re.compile(r'"([a-z]{3})"|\'([a-z]{3})\'')
    actes, collisions, exemptions = [], [], []
    with open(chemin, encoding="utf-8", errors="replace") as fh:
        for no, l in enumerate(fh, 1):
            nu = l.split("//")[0].split("#")[0]
            vu = False
            for motif, quoi in MOTIFS_ACTE:
                for m in motif.finditer(nu):
                    if m.group(1) in opcodes:
                        cible = exemptions if no in exemptees else actes
                        cible.append("%d:%s (%s)" % (no, m.group(1), quoi))
                        vu = True
            if vu:
                continue
            for m in re_lit.finditer(nu):
                tok = m.group(1) or m.group(2)
                if tok in opcodes:
                    cible = exemptions if no in exemptees else collisions
                    cible.append("%d:%s" % (no, tok))
    return actes, collisions, exemptions


# Témoins du détecteur lui-même. Le positif DOIT être vu, le négatif NE DOIT PAS l'être.
TEMOIN_POSITIF_A = 'public const string OpcodeCarte = "jru";\n'
TEMOIN_NEGATIF_A = 'public const string Etiquette = "zzq";\nvar meh = "meh";\n'


def _controles_du_detecteur() -> str:
    """Joue le contrôle positif et le contrôle négatif du détecteur ; rend "" si les deux passent.
    / Runs the detector's positive and negative controls; returns "" when both pass."""
    tmp = tempfile.mkdtemp(prefix="proto-sync-temoin-a-")
    try:
        faux = {"jru", "meh"}                    # "meh" est un opcode réel : le négatif doit l'ignorer
        pos = os.path.join(tmp, "Positif.cs")
        neg = os.path.join(tmp, "Negatif.cs")
        open(pos, "w", encoding="utf-8").write(TEMOIN_POSITIF_A)
        open(neg, "w", encoding="utf-8").write(TEMOIN_NEGATIF_A)
        ap, _, _ = _scruter(pos, faux)
        an, cn, _ = _scruter(neg, faux)
        if not ap:
            return "le contrôle POSITIF n'a pas été vu (une constante d'opcode en dur passe)"
        if an:
            return "le contrôle NÉGATIF a été pris pour un acte : %s" % an
        if not cn:
            return "le contrôle NÉGATIF n'a même pas été signalé comme collision"
        return ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fichiers_de_code(racine: str):
    """Parcourt les fichiers de code d'une zone, en sautant les dossiers générés/copiés.
    / Walks a zone's code files, skipping generated and copied directories."""
    if not os.path.isdir(racine):
        return
    for base, dirs, fichiers in os.walk(racine):
        dirs[:] = [d for d in dirs if d not in DOSSIERS_IGNORES]
        for f in fichiers:
            if os.path.splitext(f)[1] in EXTS_CODE:
                yield os.path.join(base, f)


# ── (b) ───────────────────────────────────────────────────────────────────────

def temoin_b_chemin_critique(table: dict):
    """Les 32 opcodes du chemin critique (login → perso → carte → déplacement) doivent tous être
    dans la table, sinon le serveur ne peut pas être écrit sans opcode en dur.
    / All 32 critical-path opcodes must be present, else the server cannot be written opcode-free."""
    attendus = _lire_chemin_critique()
    if not attendus:
        return ("b", "chemin critique couvert", False, "liste introuvable — %s" % CHEMIN_CRITIQUE)
    presents = {e["opcode"] for e in table["entrees"] if e["opcode"]}
    manquants = [o for o in attendus if o not in presents]
    avec_nom = sum(1 for e in table["entrees"] if e["opcode"] in attendus and e["nom_semantique"])
    avec_dir = sum(1 for e in table["entrees"] if e["opcode"] in attendus and e["direction"] != "INCONNUE")
    if manquants:
        return ("b", "chemin critique couvert", False,
                "%d/%d présents ; manquants : %s" % (len(attendus) - len(manquants), len(attendus),
                                                     ", ".join(manquants)))
    return ("b", "chemin critique couvert", True,
            "%d/%d présents ; %d avec nom sémantique, %d avec direction"
            % (len(attendus), len(attendus), avec_nom, avec_dir))


def _lire_chemin_critique():
    """Lit la liste des opcodes du chemin critique, commentaires exclus. / Reads the critical-path list."""
    if not os.path.exists(CHEMIN_CRITIQUE):
        return []
    return [l.strip() for l in open(CHEMIN_CRITIQUE, encoding="utf-8")
            if l.strip() and not l.startswith("#")]


# ── (c) ───────────────────────────────────────────────────────────────────────

def temoin_c_provenance_et_statut(table: dict):
    """Une entrée sans provenance ni statut est une affirmation sans source : elle n'a pas le
    droit d'exister. On vérifie aussi que le statut appartient au vocabulaire déclaré.
    / An entry without provenance and status is a claim without a source and may not exist."""
    permis = {"VERIFIE", "DEDUIT", "SANS_NOM"}
    fautifs = []
    for e in table["entrees"]:
        if not e.get("provenance"):
            fautifs.append("%s sans provenance" % e["token_obfusque"])
        elif e.get("statut") not in permis:
            fautifs.append("%s statut « %s » hors vocabulaire" % (e["token_obfusque"], e.get("statut")))
        elif not e.get("structure", {}).get("source"):
            fautifs.append("%s sans source de structure" % e["token_obfusque"])
    if fautifs:
        return ("c", "provenance et statut sur chaque entrée", False,
                "%d fautives : %s" % (len(fautifs), ", ".join(fautifs[:6])))
    m = table["mesures"]
    return ("c", "provenance et statut sur chaque entrée", True,
            "%d/%d entrées conformes (%d VERIFIE, %d DEDUIT, %d SANS_NOM sur %d opcodes)"
            % (m["entrees"], m["entrees"], m["nom_verifie"], m["nom_deduit"], m["sans_nom"], m["opcodes"]))


# ── (d) ───────────────────────────────────────────────────────────────────────

def temoin_d_rejeu(dossier: str, build: str, dump: str):
    """Régénère dans un dossier neuf avec le MÊME horodatage figé et compare les sha256.
    Sans horodatage figé, deux rejeux diffèrent toujours et ce témoin ne mesurerait rien.
    / Regenerates into a fresh directory with the same pinned timestamp and compares sha256."""
    if not os.path.exists(dump):
        return ("d", "rejeu byte-identique", False, "dump absent — %s" % dump)
    tmp = tempfile.mkdtemp(prefix="proto-sync-rejeu-")
    try:
        for outil in ("generer_proto.py", "generer_dispatch.py"):
            p = subprocess.run([sys.executable, os.path.join(ICI, outil), "--dump", dump,
                                "--build", build, "--out", tmp, "--horodatage", HORODATAGE_FIGE],
                               capture_output=True, text=True)
            if p.returncode != 0:
                return ("d", "rejeu byte-identique", False,
                        "%s a échoué : %s" % (outil, p.stderr.strip()[:200]))
        ecarts = []
        for nom in ("protocole-%s.proto" % build, "dispatch-%s.json" % build, "dispatch-%s.cs" % build):
            a, b = os.path.join(dossier, nom), os.path.join(tmp, nom)
            if not os.path.exists(a):
                ecarts.append("%s absent de la référence" % nom)
            elif sha256_fichier(a) != sha256_fichier(b):
                ecarts.append("%s : sha différent" % nom)
        if ecarts:
            return ("d", "rejeu byte-identique", False,
                    "%s — (attendu si la référence a été écrite sans --horodatage %s)"
                    % ("; ".join(ecarts), HORODATAGE_FIGE))
        return ("d", "rejeu byte-identique", True,
                "3 artefacts identiques au sha256 sur deux exécutions séparées")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── (e) et (f) : sur un dump-témoin, contrôlé de bout en bout ─────────────────

# Dump-témoin écrit à la grammaire EXACTE d'Il2CppInspector-Redux (relevée sur
# `il2cpp.cs:839045`). Il sert de CONTRÔLE POSITIF au sabotage : on prouve d'abord
# qu'il produit la table attendue, sinon un sabotage « vu » ne prouverait rien —
# un rouge sans contrôle positif ne distingue pas un défaut d'un instrument cassé.
DUMP_TEMOIN = """\
// Image 1: Ankama.Dofus.Protocol.Game.dll - Assembly: Ankama.Dofus.Protocol.Game, \
Version=0.0.0.0, Culture=neutral, PublicKeyToken=null - Types 9439-15069

[DebuggerDisplay("{ToString(),nq}")]
public sealed class %TOKEN% : IMessage<%TOKEN%>, IBufferMessage // TypeDefIndex: 9444
{
\t// Fields
\tprivate static readonly MessageParser<%TOKEN%> aaaa; // 0x00
\tprivate UnknownFieldSet aaab; // 0x10
\tpublic const int aaac = 1; // Metadata: 0x01499283
\tprivate int aaad; // 0x18
\tpublic const int aaae = 2; // Metadata: 0x01499284
\tprivate string aaaf; // 0x20

\t// Properties
\t[DebuggerNonUserCode]
\t[GeneratedCode("protoc", null)]
\tpublic static MessageParser<%TOKEN%> bbba { get; } // 0x00-0x01
\t[DebuggerNonUserCode]
\t[GeneratedCode("protoc", null)]
\tpublic static MessageDescriptor bbbb { get; } // 0x00-0x01
\t[DebuggerNonUserCode]
\t[GeneratedCode("protoc", null)]
\tprivate MessageDescriptor bbbc { get; } // 0x00-0x01
\t[DebuggerNonUserCode]
\t[GeneratedCode("protoc", null)]
\tpublic int bbbd { get; set; } // 0x00-0x01 0x02-0x03
\t[DebuggerNonUserCode]
\t[GeneratedCode("protoc", null)]
\tpublic string bbbe { get; set; } // 0x00-0x01 0x02-0x03

\t// Methods
\tpublic void WriteTo(CodedOutputStream output); // 0x00-0x01
}
"""


def _table_temoin(token: str, dossier: str):
    """Fabrique un dump-témoin portant `token`, en tire une table, et rend ses opcodes.
    / Builds a witness dump carrying `token`, derives a table from it, returns its opcodes."""
    chemin = os.path.join(dossier, "il2cpp.cs")
    with open(chemin, "w", encoding="utf-8") as fh:
        fh.write(DUMP_TEMOIN.replace("%TOKEN%", token))
    p = subprocess.run([sys.executable, os.path.join(ICI, "generer_dispatch.py"),
                        "--dump", chemin, "--build", "temoin", "--out", dossier,
                        "--horodatage", HORODATAGE_FIGE], capture_output=True, text=True)
    if p.returncode != 0:
        return None, p.stderr.strip()[:200]
    with open(os.path.join(dossier, "dispatch-temoin.json"), encoding="utf-8") as fh:
        t = json.load(fh)
    return t, ""


def temoin_e_sabotage():
    """SABOTAGE : renommer le token du dump d'entrée doit changer la table, et la gate doit le dire.
    Contrôle positif d'abord (le témoin non saboté produit bien `jru`), sinon un changement
    observé ne prouverait rien sur la chaîne.
    / Renaming the input token must change the table; positive control runs first."""
    tmp = tempfile.mkdtemp(prefix="proto-sync-sabotage-")
    try:
        avant, err = _table_temoin("jru", tmp)
        if avant is None:
            return ("e", "sabotage du dump vu par la table", False, "contrôle positif KO : " + err)
        ops_avant = {e["opcode"] for e in avant["entrees"] if e["opcode"]}
        if ops_avant != {"jru"}:
            return ("e", "sabotage du dump vu par la table", False,
                    "contrôle positif KO : le témoin non saboté rend %s au lieu de {'jru'}" % ops_avant)
        apres, err = _table_temoin("zzq", tmp)
        if apres is None:
            return ("e", "sabotage du dump vu par la table", False, "sabotage KO : " + err)
        ops_apres = {e["opcode"] for e in apres["entrees"] if e["opcode"]}
        if ops_apres != {"zzq"}:
            return ("e", "sabotage du dump vu par la table", False,
                    "la table ne suit pas le dump : après renommage jru→zzq elle porte %s" % ops_apres)
        if avant["entrees"][0]["champs"] != apres["entrees"][0]["champs"]:
            return ("e", "sabotage du dump vu par la table", False,
                    "les champs ont bougé alors que seul le NOM a été saboté")
        return ("e", "sabotage du dump vu par la table", True,
                "contrôle positif {jru} ; après renommage jru→zzq la table porte {zzq}, "
                "champs inchangés — la table suit bien son entrée")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def temoin_f_temoin_negatif(table: dict):
    """TÉMOIN NÉGATIF : un opcode inventé ne doit apparaître ni dans la table, ni dans le `.proto`.
    Une barrière incapable de refuser ne distingue rien.
    / An invented opcode must be absent everywhere; a barrier that cannot refuse distinguishes nothing."""
    tous = {e["opcode"] for e in table["entrees"] if e["opcode"]}
    tous |= {e["token_obfusque"] for e in table["entrees"]}
    intrus = [o for o in OPCODES_INVENTES if o in tous]
    if intrus:
        return ("f", "opcode inventé absent", False,
                "%d opcodes inventés PRÉSENTS dans la table : %s" % (len(intrus), intrus))
    return ("f", "opcode inventé absent", True,
            "%s absents de la table (%d tokens) — la table ne contient pas tout"
            % (", ".join(OPCODES_INVENTES), len(tous)))


if __name__ == "__main__":
    sys.exit(main())
