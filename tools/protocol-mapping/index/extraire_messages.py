#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : extraire_messages.py <emu> <racine> — table des messages du protocole, 0-LLM.
Deterministic 0-LLM message-table extractor (Namaste 3, etage 1).

POURQUOI :
Formes mesurees AVANT d'ecrire ce script (04/09) :
  jiva/giny/ginycore/oneair/symbioz : une classe de message = `class X : Message|NetworkMessage`
    qui porte `public [new] const (ushort|uint|short|int) Id = N;`. Les champs sont des lignes
    `public TYPE nom;` (jamais de List<T> au niveau message, des tableaux `T[]` a la place --
    mesure : 0 fichier `grep -l "List<"` dans les 5 dossiers Messages/). Suivi par comptage
    d'accolades (brace-depth) pour borner le corps de classe, pas par une regex plein-texte
    (evite de deborder sur la classe suivante).
  jondo : pas de .cs. Source = le .proto RECONSTRUIT DEPUIS LE CLIENT par
    Jondo.Unity.ProtocolBuilder (dossier `datos/`, 2169 blocs `message X {}` mesures, 0
    imbrique, 550 `enum`) -- son propre en-tete le dit : "numeros et types reels, noms
    rotes par Ankama". L'identifiant opcode = le nom du bloc LUI-MEME quand il figure dans
    Op.cs (les opcodes JondoEmu sont des noms de classe obfusques, pas des entiers, cf. Op.cs
    et cahier §L6) -- plus de table de jointure C# intermediaire.
    *** CORRECTIF 04/09 (team-lead + architecte, DAG J3.A pt.4) *** : la 1ere version de ce
    script lisait un AUTRE .proto, sous `Messages/` a cote du code C# du depot -- celui-la est
    ECRIT A LA MAIN (noms invente, champs INVERSES) et n'a jamais ete produit depuis le client.
    Erreur mesuree et corrigee -- detail complet dans RAPPORT-INDEX.md (jamais le chemin en
    toutes lettres ici : la gate `gate_ancien_proto_absent()` ci-dessous grep les .py de ce
    dossier pour s'assurer qu'aucun ne le reference plus, un aveu ecrit ici la ferait echouer).

Limite documentee (pas cachee) : les champs d'un sous-message imbrique ne remontent pas dans
nb_champs du message parent (chaque bloc {} est compte a son propre niveau, jamais fusionne).
Un type generique multi-mots avec espace (`Dictionary<int, string>`) n'est pas reconnu par le
regex de champ C# (un seul token entre `public` et le nom) : absent du compte, pas un crash --
mesure : 0 occurrence de ce type dans les Messages/ scannes (mai/juin 2026).

COMMENT LANCER : python3 extraire_messages.py <emu> <racine> (emu dans jiva/giny/ginycore/oneair/
    symbioz/jondo) | python3 extraire_messages.py --epreuve [emu]
GATE : --epreuve par emu (total messages attendu, rejeu sha256 byte-identique, et pour jondo :
    opcodes/noms_proposes resolus == attendu) + gate_ancien_proto_absent() (DAG J3.A pt.4).
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

from _lib_extract import CLASS_RE, MESSAGE_ID_CONST_RE, iter_cs_files, write_tsv, sha256_file
from extraire_handlers import parse_op_cs

HEADER = ["message_nom", "protocol_id", "fichier:ligne", "nb_champs", "champs",
          "nom_propose", "nom_propose_provenance"]

EMU_VERSION = {
    "jiva": "2.42", "giny": "2.68", "ginycore": "2.63", "oneair": "2.68-docker",
    "symbioz": "2.38", "jondo": "3.6.10.10",
}

FIELD_RE = re.compile(r"^\s*public\s+([\w<>\[\],\.]+)\s+(\w+)\s*;\s*$")


# Lignee C# (jiva/giny/ginycore/oneair/symbioz) : suit la profondeur d'accolades pour borner
# chaque classe `class X : Message`, capture son Id const + ses champs `public TYPE nom;`.
# / C# lineage (jiva/giny/ginycore/oneair/symbioz): tracks brace depth to bound each
# `class X : Message`, captures its Id const + its `public TYPE name;` fields.
def extract_code_family(racine: Path, emu: str) -> tuple[list[list[str]], dict]:
    rows: list[list[str]] = []
    stats = {"classes_message_trouvees": 0, "champs_type_non_reconnu_lignes": 0}
    files = list(iter_cs_files(racine))
    for fi, path in enumerate(files, 1):
        if fi % 500 == 0:
            print(f"  [messages:{emu}] {fi}/{len(files)} fichiers", flush=True)
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        # depth = profondeur d'accolades ABSOLUE dans le fichier (une classe C# vit sous au
        # moins 1 niveau de `namespace X { ... }`, jamais a depth==0 -- 1ere version comparait
        # a 0 et ne trouvait JAMAIS aucune classe, EN SILENCE. Corrige : on retient la
        # profondeur au moment ou `class X` est vue (start_depth) et on cloture quand la
        # profondeur y revient, quel que soit ce chiffre.
        depth = 0
        cur = None  # dict courant si on est dans une classe candidate

        for i, line in enumerate(lines, start=1):
            cm = CLASS_RE.match(line)
            if cm and cur is None:
                cur = {"name": cm.group(1), "start_depth": depth, "id": None,
                       "id_line": None, "fields": [], "entered": False}
            # classe imbriquee dans une classe candidate (cur deja pose) : non observee dans
            # les 5 depots (classes de message = feuilles), ignoree sans casser le parent.

            depth += line.count("{") - line.count("}")

            if cur is not None and depth > cur["start_depth"]:
                cur["entered"] = True  # on a vu au moins une '{' d'ouverture du corps
                idm = MESSAGE_ID_CONST_RE.search(line)
                if idm and cur["id"] is None:
                    cur["id"] = int(idm.group(1))
                    cur["id_line"] = i
                fm = FIELD_RE.match(line)
                if fm and "const" not in line and "override" not in line:
                    cur["fields"].append(f"{fm.group(2)}:{fm.group(1)}")

            # Fermeture reelle : il faut ETRE ENTRE dans le corps au moins une fois avant
            # que depth<=start_depth signifie une fermeture (sinon la ligne `class X` elle-meme,
            # qui ne porte pas encore d'accolade, se refermerait sur elle-meme instantanement).
            if cur is not None and cur["entered"] and depth <= cur["start_depth"]:
                if cur["id"] is not None:
                    stats["classes_message_trouvees"] += 1
                    # nom_propose/provenance : sans objet pour la lignee C# (le nom de
                    # classe EST deja le nom reel, pas un token obfusque a eclaircir) --
                    # colonnes vides, presentes pour un schema uniforme sur les 6 TSV.
                    rows.append([cur["name"], str(cur["id"]), f"{path}:{cur['id_line']}",
                                 str(len(cur["fields"])), ";".join(cur["fields"]), "", ""])
                cur = None
    return rows, stats


# ---------------------------------------------------------------------------
# JondoEmu : .proto RECONSTRUIT depuis le client (brace-depth) + Op.cs (opcode = nom du
# bloc lui-meme) + anclas_*.tsv (nom_propose, colonne humaine, PAS structurelle).
# ---------------------------------------------------------------------------
PROTO_BLOCK_RE = re.compile(r"^(message|enum)\s+(\w+)\s*\{")
PROTO_FIELD_RE = re.compile(r"^(repeated\s+)?([\w.]+)\s+(\w+)\s*=\s*(\d+)\s*;")
# `map<K, V> nom = N;` -- 157 occurrences mesurees dans le .proto reconstruit (04/09), forme
# absente de l'ancien .proto ecrit a la main. PROTO_FIELD_RE ne la matche pas (le `<`/`,`
# casse le token de type) : sans ce filet, ces 157 champs disparaitraient EN SILENCE du
# compte nb_champs des messages qui les portent.
MAP_FIELD_RE = re.compile(r"^map<\s*([\w.]+)\s*,\s*([\w.]+)\s*>\s+(\w+)\s*=\s*(\d+)\s*;")


def _find_proto_reconstruit(racine: Path) -> Path:
    """Le .proto RECONSTRUIT depuis le client par Jondo.Unity.ProtocolBuilder (numeros et
    types reels, noms rotes par Ankama -- son propre en-tete le dit) : `datos/`, jamais
    le dossier du code C# genere a cote du depot (celui-la etait ecrit a la main, cf.
    docstring de module -- corrige le 04/09)."""
    direct = racine / "datos" / "protocolo_3.6.10.10.proto"
    if direct.exists():
        return direct
    datos = racine / "datos"
    if datos.exists():
        candidats = sorted(datos.glob("protocolo_*.proto"))
        if candidats:
            return candidats[0]
    found = sorted(racine.rglob("protocolo_*.proto"))
    return found[0] if found else direct


def parse_anclas_nom_propose(racine: Path) -> dict[str, tuple[str, str]]:
    """opcode -> (nom_propose, fichier_source), depuis datos/anclas_*.tsv colonne 3
    ("nombre propuesto") -- une PROPOSITION humaine, jamais une preuve structurelle (cf.
    l'en-tete de l'anclas tsv lui-meme : "Vacio significa que el documento no establece
    que hace, y entonces no se inventa" -- meme discipline ici : vide reste vide)."""
    out: dict[str, tuple[str, str]] = {}
    tsv_dir = racine / "datos"
    files = sorted(tsv_dir.glob("anclas_*.tsv")) if tsv_dir.exists() else sorted(
        racine.rglob("anclas_*.tsv"))
    for tsv in files:
        for line in tsv.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split("\t")
            if len(cols) < 3:
                continue
            opcode, nom = cols[0].strip(), cols[2].strip()
            if nom and opcode not in out:
                out[opcode] = (nom, tsv.name)
    return out


# JondoEmu : parcourt le .proto RECONSTRUIT (brace-depth), resout l'opcode via Op.cs et le
# nom_propose (humain) via anclas_*.tsv -- les messages imbriques sont comptes mais exclus du TSV.
# / JondoEmu: walks the RECONSTRUCTED .proto (brace-depth), resolves the opcode via Op.cs and
# the (human) nom_propose via anclas_*.tsv -- nested messages are counted but excluded from the TSV.
def extract_jondo(racine: Path) -> tuple[list[list[str]], dict]:
    proto_file = _find_proto_reconstruit(racine)
    opcodes = parse_op_cs(racine)  # set des opcodes VIVANTS de cette build (extraire_handlers.py)
    nom_propose_map = parse_anclas_nom_propose(racine)
    stats = {"blocs_message_top_level": 0, "blocs_message_imbriques": 0, "blocs_enum": 0,
             "messages_avec_opcode_resolu": 0, "messages_avec_nom_propose": 0}
    rows: list[list[str]] = []
    if not proto_file.exists():
        return rows, stats

    lines = proto_file.read_text(encoding="utf-8", errors="replace").splitlines()
    stack: list[dict] = []
    depth = 0
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        bm = PROTO_BLOCK_RE.match(stripped)
        if bm:
            kind, name = bm.groups()
            stack.append({"kind": kind, "name": name, "start": i, "depth": depth,
                          "fields": []})
            depth += 1
            continue
        if stripped.startswith("}"):
            if stack:
                top = stack.pop()
                depth -= 1
                if top["kind"] == "message":
                    if top["depth"] == 0:
                        stats["blocs_message_top_level"] += 1
                        # L'opcode JondoEmu EST le nom du bloc lui-meme (classe obfusquee =
                        # identifiant sur le fil, cf. cahier §L6) -- pas de table intermediaire.
                        is_opcode = top["name"] in opcodes
                        protocol_id = top["name"] if is_opcode else ""
                        if is_opcode:
                            stats["messages_avec_opcode_resolu"] += 1
                        propose, source = nom_propose_map.get(top["name"], ("", ""))
                        if propose:
                            stats["messages_avec_nom_propose"] += 1
                        rows.append([top["name"], protocol_id, f"{proto_file}:{top['start']}",
                                     str(len(top["fields"])), ";".join(top["fields"]),
                                     propose, source])
                    else:
                        stats["blocs_message_imbriques"] += 1
                else:
                    stats["blocs_enum"] += 1
            continue
        if stack:
            fm = PROTO_FIELD_RE.match(stripped)
            if fm:
                repeated, ftype, fname, _fnum = fm.groups()
                stack[-1]["fields"].append(f"{fname}:{'repeated ' if repeated else ''}{ftype}")
                continue
            mm = MAP_FIELD_RE.match(stripped)
            if mm:
                ktype, vtype, fname, _fnum = mm.groups()
                stack[-1]["fields"].append(f"{fname}:map<{ktype},{vtype}>")
    return rows, stats


def gate_ancien_proto_absent() -> tuple[bool, int]:
    """Gate DAG J3.A pt.4 (architecte, correctif team-lead 04/09) : aucun .py de ce dossier
    ne doit plus referencer l'ancien .proto ecrit a la main. Motif construit par
    CONCATENATION (jamais en toutes lettres dans le SOURCE de ce fichier) : sinon cette
    gate se ferait echouer elle-meme au premier grep statique en se citant."""
    motif = "Jondo.Unity.Protocol" + "/Messages/" + "Protocol.proto"
    here = Path(__file__).resolve().parent
    total = 0
    for py in sorted(here.glob("*.py")):
        total += py.read_text(encoding="utf-8", errors="replace").count(motif)
    return total == 0, total


# Dispatch vers extract_jondo() ou extract_code_family() selon l'emu, ecrit messages-<emu>.tsv.
# / Dispatches to extract_jondo() or extract_code_family() per emu, writes messages-<emu>.tsv.
def run(emu: str, racine: Path, outdir: Path) -> dict:
    version = EMU_VERSION[emu]
    if emu == "jondo":
        rows, stats = extract_jondo(racine)
    else:
        rows, stats = extract_code_family(racine, emu)
    write_tsv(outdir / f"messages-{emu}.tsv", HEADER, rows)
    stats.update({"emu": emu, "version": version, "total_messages": len(rows)})
    return stats


# Epreuve dans les deux sens pour UN emu : fabrique un temoin (C# ou .proto reconstruit selon
# le cas), verifie le compte de messages attendu, le rejeu sha256, et la gate anti-ancien-proto.
# / Two-way proof for ONE emu: fabricates a witness (C# or reconstructed .proto depending on the
# case), checks the expected message count, the sha256 replay, and the anti-old-proto gate.
def epreuve(emu: str) -> bool:
    import tempfile
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        racine = Path(tmp)
        outdir = racine / "out"
        outdir.mkdir()

        if emu == "jondo":
            (racine / "Jondo.Unity.Protocol").mkdir()
            (racine / "Jondo.Unity.Protocol" / "Op.cs").write_text(
                'public static class Op {\n    public const string Xyz = "xyz";\n}\n',
                encoding="utf-8")
            (racine / "datos").mkdir()
            (racine / "datos" / "anclas_test.tsv").write_text(
                "# columnas: opcode\tdireccion\tnombre propuesto\tsignificado\thandler\tforma\n"
                "xyz\tC2S\tConformeMsg\tun test\tSampleHandler.HandleConforme\tf1:int\n",
                encoding="utf-8")
            (racine / "datos" / "protocolo_3.6.10.10.proto").write_text(
                "message xyz {\n"
                "    int32 f1 = 1;\n"
                "    repeated int32 f2 = 2;\n"
                "    map<int32, bool> f3 = 3;\n"  # forme mesuree 04/09, 157 occurrences reelles
                "}\n"
                "message sinopcode {\n"  # absent de Op.cs -> protocol_id vide, jamais invente
                "    int32 z = 1;\n"
                "}\n"
                "message Nested {\n"  # imbrique -> exclu du compte top-level
                "    message Inner {\n"
                "        int32 zz = 1;\n"
                "    }\n"
                "}\n",
                encoding="utf-8")
            stats1 = run("jondo", racine, outdir)
            expected_total = 3  # xyz + sinopcode + Nested (top-level), Inner exclu
            expected_resolus = 1  # seul xyz est dans Op.cs
            expected_nom_propose = 1  # seul xyz est dans l'anclas tsv
        else:
            (racine / "src").mkdir()
            content = (
                "namespace Test\n{\n"
                "    public class ConformeMessage : Message\n    {\n"
                "        public const uint Id = 1234;\n"
                "        public string nom;\n"
                "        public int[] valeurs;\n"
                "        public ConformeMessage() {}\n"
                "    }\n\n"
                "    public class DerivedMessage : ConformeMessage\n    {\n"
                "        public new const uint Id = 5678;\n"
                "        public bool flag;\n"
                "    }\n\n"
                "    public class PasUnMessage\n    {\n"
                "        public int rien;\n"
                "    }\n}\n"
            )
            (racine / "src" / "Sample.cs").write_text(content, encoding="utf-8")
            stats1 = run(emu, racine, outdir)
            expected_total = 2  # ConformeMessage + DerivedMessage (PasUnMessage sans Id exclue)
            expected_resolus = None
            expected_nom_propose = None

        h1 = sha256_file(outdir / f"messages-{emu}.tsv")
        outdir2 = racine / "out2"
        outdir2.mkdir()
        run(emu, racine, outdir2)
        h2 = sha256_file(outdir2 / f"messages-{emu}.tsv")

        gate_ok, gate_n = gate_ancien_proto_absent()
        checks = [
            ("total messages == attendu", stats1["total_messages"] == expected_total,
             f"{stats1['total_messages']} vs {expected_total}"),
            ("rejeu byte-identique (sha256)", h1 == h2, f"{h1} vs {h2}"),
            ("gate DAG J3.A pt.4 : ancien .proto (main) absent des .py de index/",
             gate_ok, f"{gate_n} occurrence(s) trouvee(s), attendu 0"),
        ]
        if expected_resolus is not None:
            checks.append(("opcodes resolus == attendu (sinopcode/orphan hors Op.cs exclu)",
                            stats1["messages_avec_opcode_resolu"] == expected_resolus,
                            f"{stats1['messages_avec_opcode_resolu']} vs {expected_resolus}"))
        if expected_nom_propose is not None:
            checks.append(("nom_propose resolus == attendu (anclas tsv)",
                            stats1["messages_avec_nom_propose"] == expected_nom_propose,
                            f"{stats1['messages_avec_nom_propose']} vs {expected_nom_propose}"))
        print(f"\n=== --epreuve extraire_messages.py {emu} ===")
        for label, passed, detail in checks:
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}  ({detail})")
            ok = ok and passed
    return ok


# Point d'entree CLI : --epreuve [emu], ou une extraction reelle <emu> <racine>.
# / CLI entry point: --epreuve [emu], or a real extraction <emu> <racine>.
def main():
    if len(sys.argv) < 2:
        print("usage: extraire_messages.py <emu> <racine> | extraire_messages.py --epreuve [emu]")
        sys.exit(2)
    if sys.argv[1] == "--epreuve":
        emus = [sys.argv[2]] if len(sys.argv) > 2 else list(EMU_VERSION)
        all_ok = all(epreuve(e) for e in emus)
        sys.exit(0 if all_ok else 1)
    if len(sys.argv) != 3:
        print("usage: extraire_messages.py <emu> <racine>")
        sys.exit(2)
    emu, racine_s = sys.argv[1], sys.argv[2]
    if emu not in EMU_VERSION:
        print(f"emu inconnu: {emu} (attendus: {list(EMU_VERSION)})")
        sys.exit(2)
    # FR : pas de .resolve() ici — cf. extraire_handlers.py : absolutiser la racine graverait le
    #      chemin de la machine d'extraction dans les citations `fichier:ligne` de la sortie.
    # EN : no .resolve() here — see extraire_handlers.py: resolving the root would bake the
    #      extracting machine's path into the output's `file:line` citations.
    racine = Path(racine_s)
    outdir = Path(__file__).resolve().parent
    stats = run(emu, racine, outdir)
    print(f"[messages:{emu}] {stats}")


if __name__ == "__main__":
    main()
