#!/usr/bin/env python3
"""extraire_as3_protocole.py — arbre AS3 décompilé (2.x) → tables du protocole. 0 LLM, stdlib seule.

═══ QUOI / WHAT ═══
Maillon C4 de la chaîne 2.x. Entrée : un arbre `.as` sorti de ffdec. Sortie : `messages-<v>.tsv`,
`types-<v>.tsv`, `enums-<v>.tsv`. N'appartient QU'À la chaîne 2.x (loi L4) : rien ici ne sert au 3.x.
Stage C4 of the 2.x chain; belongs to that chain only.

═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
FR : l'ORDRE DE SÉRIALISATION se lit dans le corps de `serializeAs_<Classe>`, jamais dans la liste des
     `public var` : l'ordre DÉCLARÉ n'est PAS l'ordre du fil. Mesuré sur 2.42, les booléens groupés en
     tête d'un octet de drapeaux (BooleanByteWrapper) cassent la coïncidence — un serveur qui sérialise
     dans l'ordre de déclaration produit des trames que le client refuse.
EN : wire order is read from the `serializeAs_<Class>` body, never from the field declarations.

Ce qu'il AFFIRME : nom, protocolId, parent, champs, ordre d'écriture — tout est LU dans un fichier, avec
`fichier:ligne`. Il n'INTERPRÈTE aucune sémantique. Loi F : tout ce qu'il écarte est COMPTÉ et DIT, par
motif — un rejet muet est un défaut qui n'existe pas, jusqu'au jour où le résultat est inexplicable.
What it claims is read from a file with a line reference; it interprets no semantics; every reject is
counted and reported by motive.

═══ COMMENT LANCER / HOW TO RUN ═══
  extraire_as3_protocole.py <racine-arbre-as3> <version> [--out DIR]
  extraire_as3_protocole.py --epreuve <racine-arbre-as3> [--out DIR]
La racine peut être l'arbre entier ou son dossier `scripts/` : le script retrouve `.../dofus/network`
tout seul, et REFUSE s'il ne le trouve pas (plutôt que de rendre une table vide).

═══ GATE ═══
`--epreuve` — 6 contrôles, tous verts au 04/09/2026 : rejeu byte-identique (sha256 des 3 tables) ·
partition assertée (messages+types+enums+autres+sans-classe == fichiers) · sabotage `protocolId` (la
sortie change ET l'id saboté est vu) · sabotage d'une ligne d'écriture (la table change) · 1 fichier
retiré → le compte baisse de 1 · témoin inventé absent.
À LIRE À CHAQUE RUN : la ligne `REJETS`. Chaque `ligne de serializeAs_ non reconnue` est un OCTET DU FIL
qui manque à la table. Référence : 0 rejet sur 2.42 (1420 fichiers) et 2.73 (1679).
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter

ICI = os.path.dirname(os.path.abspath(__file__))

# --- Grammaire AS3 mesurée sur client242-as3 (1420 .as) / AS3 grammar measured on 2.42 ---
RE_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)")
RE_DECL = re.compile(
    r"^\s*public\s+(?:final\s+)?(class|interface)\s+(\w+)"
    r"(?:\s+extends\s+([\w.]+))?(?:\s+implements\s+([\w.,\s]+?))?\s*$")
RE_PROTOID = re.compile(r"public\s+static\s+const\s+protocolId\s*:\s*\w+\s*=\s*(\d+)")
RE_CONST = re.compile(r"public\s+static\s+const\s+(\w+)\s*:\s*([\w.<>]+)\s*=\s*(.+?);")
RE_FIELD = re.compile(r"^\s*public\s+var\s+(\w+)\s*:\s*([\w.]+(?:\.<[\w.]+>)?)\s*(?:=\s*(.+?))?;")
RE_SERIAL_FN = re.compile(r"public\s+function\s+serializeAs_(\w+)\s*\(")
RE_DESERIAL_FN = re.compile(r"public\s+function\s+deserializeAs_(\w+)\s*\(")

# Opérations d'écriture reconnues, dans l'ordre de spécificité (la 1re qui matche gagne).
# Recognised write ops, most specific first.
OPS = [
    # super.serializeAs_Parent(param1)
    (re.compile(r"super\.serializeAs_(\w+)\s*\("), lambda m: f"super:{m.group(1)}"),
    # BooleanByteWrapper.setFlag(_locN_, K, this.champ)
    (re.compile(r"BooleanByteWrapper\.setFlag\(\s*\w+\s*,\s*(\d+)\s*,\s*this\.(\w+)"),
     lambda m: f"{m.group(2)}:bit{m.group(1)}"),
    # param1.writeX((this.champ[_locN_] as Type).getTypeId())  ← polymorphisme : le type est SUR LE FIL
    (re.compile(r"\w+\.(write\w+)\(\s*\(\s*this\.(\w+)\[[^\]]*\]\s+as\s+\w+\s*\)\.getTypeId\(\)"),
     lambda m: f"{m.group(2)}[]#typeId:{m.group(1)}"),
    # (this.champ[_locN_] as Type).serializeAs_T2(param1)
    (re.compile(r"\(\s*this\.(\w+)\[[^\]]*\]\s+as\s+\w+\s*\)\.serializeAs_(\w+)\s*\("),
     lambda m: f"{m.group(1)}[]:as{m.group(2)}"),
    # (this.champ as Type).serializeAs_T2(param1)
    (re.compile(r"\(\s*this\.(\w+)\s+as\s+\w+\s*\)\.serializeAs_(\w+)\s*\("),
     lambda m: f"{m.group(1)}:as{m.group(2)}"),
    # (this.champ[_locN_] as Type).serialize(param1)
    (re.compile(r"\(\s*this\.(\w+)\[[^\]]*\]\s+as\s+\w+\s*\)\.serialize\s*\(\s*\w+\s*\)"),
     lambda m: f"{m.group(1)}[]:serialize"),
    # (this.champ as Type).serialize(param1)
    (re.compile(r"\(\s*this\.(\w+)\s+as\s+\w+\s*\)\.serialize\s*\(\s*\w+\s*\)"),
     lambda m: f"{m.group(1)}:serialize"),
    # this.champ[_locN_].serializeAs_Type(param1)
    (re.compile(r"this\.(\w+)\[[^\]]*\]\.serializeAs_(\w+)\s*\("), lambda m: f"{m.group(1)}[]:as{m.group(2)}"),
    # this.champ.serializeAs_Type(param1)
    (re.compile(r"this\.(\w+)\.serializeAs_(\w+)\s*\("), lambda m: f"{m.group(1)}:as{m.group(2)}"),
    # this.champ[_locN_].serialize(param1) — répartition polymorphe, type porté par typeId
    (re.compile(r"this\.(\w+)\[[^\]]*\]\.serialize\s*\(\s*\w+\s*\)"), lambda m: f"{m.group(1)}[]:serialize"),
    # this.champ.serialize(param1)
    (re.compile(r"this\.(\w+)\.serialize\s*\(\s*\w+\s*\)"), lambda m: f"{m.group(1)}:serialize"),
    # param1.writeX(this.champ.length)
    (re.compile(r"\w+\.(write\w+)\(\s*this\.(\w+)\.length\s*\)"), lambda m: f"{m.group(2)}#len:{m.group(1)}"),
    # param1.writeX(this.champ[_locN_])
    (re.compile(r"\w+\.(write\w+)\(\s*this\.(\w+)\[[^\]]*\]\s*\)"), lambda m: f"{m.group(2)}[]:{m.group(1)}"),
    # param1.writeX(this.champ.sousChamp)
    (re.compile(r"\w+\.(write\w+)\(\s*this\.(\w+)\.(\w+)\s*\)"), lambda m: f"{m.group(2)}.{m.group(3)}:{m.group(1)}"),
    # param1.writeX(this.champ)
    (re.compile(r"\w+\.(write\w+)\(\s*this\.(\w+)\s*\)"), lambda m: f"{m.group(2)}:{m.group(1)}"),
    # param1.writeX(0) → une constante littérale sur le fil (padding, drapeau toujours nul)
    (re.compile(r"\w+\.(write\w+)\(\s*(-?\d+)\s*\)"), lambda m: f"#const{m.group(2)}:{m.group(1)}"),
    # param1.writeX(<local>) → l'octet de drapeaux, ou la longueur d'un vecteur local.
    # 2.42 nomme ses locales `_locN_`, 2.68 les nomme `_box0`/`data` : on n'ancre PAS sur le nom.
    # 2.42 names locals `_locN_`, 2.68 names them `_box0`/`data`: never anchor on the name.
    (re.compile(r"\w+\.(write\w+)\(\s*[A-Za-z_]\w*\s*\)"), lambda m: f"#local:{m.group(1)}"),
    # param1.writeX(this.champ.getTypeId()) — dernier recours, forme sans cast
    (re.compile(r"\w+\.(write\w+)\(.*?getTypeId\(\)"), lambda m: f"#typeId:{m.group(1)}"),
]
# Lignes structurelles ignorées SANS être des rejets (elles ne portent pas d'octet).
# Structural lines skipped without counting as rejects (they carry no byte).
RE_INOFFENSIF = re.compile(
    r"^\s*(\}|\{|//|/\*|\*|var\s|while\s*\(|for\s*\(|if\s*\(|else|throw\s|return|break|continue|"
    r"(?!this\.)[A-Za-z_]\w*\s*(\+\+|--|=[^=])|"       # affectation à une LOCALE (jamais `this.x`)
    r"public\s+function|override\s+public|super\(\))")
# Un fichier que ffdec n'a pas su décompiler : il EXISTE, il a l'air normal, il ne contient rien.
# A file ffdec failed to decompile: it exists, it looks normal, it holds nothing.
RE_ECHEC_FFDEC = re.compile(r"Decompilation error|Not decompiled due to")


def log(msg):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(msg, file=sys.stderr, flush=True)


def lire_corps(lignes, i_debut):
    """Corps d'une fonction à partir de la ligne de sa signature, par comptage d'accolades.
    Function body from its signature line, by brace counting. Rend (lignes, index_fin)."""
    prof, demarre, corps = 0, False, []
    for j in range(i_debut, len(lignes)):
        ligne = lignes[j]
        # on compte les accolades hors chaînes littérales / count braces outside string literals
        nu = re.sub(r'"(\\.|[^"\\])*"', '""', ligne)
        if not demarre:
            if "{" in nu:
                demarre = True
                prof = nu.count("{") - nu.count("}")
                corps.append((j, ligne))
                if prof <= 0:
                    return corps, j
            continue
        prof += nu.count("{") - nu.count("}")
        corps.append((j, ligne))
        if prof <= 0:
            return corps, j
    return corps, len(lignes) - 1


class Rejets:
    """Compteur de rejets par MOTIF. Un rejet muet est un défaut invisible (règle du projet §3d)."""

    def __init__(self):
        """Compteur vide. Un rejet non compté est un défaut qui n'existe pas — jusqu'au jour où le
        résultat est inexplicable. An uncounted reject is an invisible defect."""
        self.par_motif = Counter()
        self.exemples = {}

    def add(self, motif, ou, texte=""):
        """Enregistre un rejet SOUS SON MOTIF et garde le premier exemple, pour que le lecteur voie
        la forme et pas seulement le nombre. Records a reject under its motive, with an example."""
        self.par_motif[motif] += 1
        self.exemples.setdefault(motif, f"{ou} :: {texte.strip()[:110]}")

    def total(self):
        """Somme de tous les motifs. Sum over all motives."""
        return sum(self.par_motif.values())

    def rapport(self):
        """Motifs du plus fréquent au moins fréquent : un motif qui DOMINE désigne une consigne à
        reformuler, pas un terrain difficile. Most frequent first: it points at the instruction."""
        out = []
        for motif, n in self.par_motif.most_common():
            out.append(f"    {n:6d}  {motif}   ex. {self.exemples[motif]}")
        return "\n".join(out)


def analyser_fichier(chemin, rejets):
    """Rend un dict décrivant la classe du fichier, ou None si le fichier n'en déclare pas."""
    try:
        texte = open(chemin, encoding="utf-8", errors="replace").read()
    except OSError as e:
        rejets.add("fichier illisible", chemin, str(e))
        return None
    lignes = texte.split("\n")

    paquet = cls = None
    parent = ""
    ligne_decl = 0
    for i, ligne in enumerate(lignes):
        if paquet is None:
            m = RE_PACKAGE.match(ligne)
            if m:
                paquet = m.group(1)
                continue
        m = RE_DECL.match(ligne)
        if m and cls is None:
            cls = m.group(2)
            parent = m.group(3) or ""
            ligne_decl = i + 1
            kind = m.group(1)
    if cls is None:
        if RE_ECHEC_FFDEC.search(texte):
            # Ce n'est PAS un fichier vide : c'est un ÉCHEC de ffdec (souvent OutOfMemoryError).
            # Remède mesuré : relancer avec un tas plus grand (voir RUNBOOK-COMMUNAUTE.md).
            rejets.add("ÉCHEC DE DÉCOMPILATION ffdec (fichier présent, corps absent)", chemin,
                       texte.strip().split("\n")[-1])
        else:
            rejets.add("aucune classe publique déclarée", chemin)
        return None

    proto_id = ""
    m = RE_PROTOID.search(texte)
    if m:
        proto_id = m.group(1)

    champs = []          # (nom, type)
    for i, ligne in enumerate(lignes):
        m = RE_FIELD.match(ligne)
        if m:
            champs.append((m.group(1), m.group(2)))

    constantes = []      # pour les enums / for enums
    for m in RE_CONST.finditer(texte):
        if m.group(1) != "protocolId":
            constantes.append((m.group(1), m.group(2), m.group(3).strip()))

    # ordre de sérialisation / wire order
    ordre, ordre_ok, n_rejets_local = [], False, 0
    for i, ligne in enumerate(lignes):
        m = RE_SERIAL_FN.search(ligne)
        if not m:
            continue
        corps, _ = lire_corps(lignes, i)
        ordre_ok = True
        for j, l in corps[1:-1] if len(corps) > 2 else []:
            brut = l.strip()
            if not brut:
                continue
            touche = False
            for rx, fmt in OPS:
                mm = rx.search(l)
                if mm:
                    ordre.append(fmt(mm))
                    touche = True
                    break
            if not touche and not RE_INOFFENSIF.match(l):
                n_rejets_local += 1
                rejets.add("ligne de serializeAs_ non reconnue", f"{chemin}:{j+1}", brut)
        break

    if not ordre_ok and proto_id:
        rejets.add("classe avec protocolId mais sans serializeAs_", f"{chemin}:{ligne_decl}")

    return dict(paquet=paquet, classe=cls, parent=parent, kind=kind, proto_id=proto_id,
                champs=champs, constantes=constantes, ordre=ordre,
                source=f"{chemin}:{ligne_decl}", n_rejets=n_rejets_local)


def racine_network(racine):
    """Trouve `.../dofus/network` sous une racine quelconque (arbre complet ou `scripts/`)."""
    for base, dirs, _ in os.walk(racine):
        if os.path.basename(base) == "network" and "dofus" in base.replace("\\", "/").split("/"):
            return base
    return None


def extraire(racine, version, out_dir, quiet=False):
    """Parcourt le sous-arbre réseau, range chaque fichier dans son seau, ASSERTE la partition,
    écrit les trois tables. Walks the network tree, buckets, asserts partition, writes tables."""
    t0 = time.time()
    net = racine_network(racine)
    if net is None:
        raise SystemExit(f"REFUS : aucun dossier `.../dofus/network` sous {racine} — arbre AS3 incomplet ?")
    rejets = Rejets()
    fichiers = []
    for base, _, noms in os.walk(net):
        for n in sorted(noms):
            if n.endswith(".as"):
                fichiers.append(os.path.join(base, n))
    fichiers.sort()
    if not quiet:
        log(f"  arbre : {net}  ·  {len(fichiers)} fichiers .as sous network/")

    seaux = {"messages": [], "types": [], "enums": [], "autres": []}
    for k, chemin in enumerate(fichiers, 1):
        if not quiet and k % 250 == 0:
            log(f"  lecture : {k}/{len(fichiers)} ({time.time()-t0:.1f}s)")
        rel = os.path.relpath(chemin, net).replace("\\", "/")
        seau = rel.split("/")[0]
        if seau not in seaux:
            seau = "autres"
        info = analyser_fichier(chemin, rejets)
        if info is None:
            continue
        info["seau"] = seau
        seaux[seau].append(info)

    # ASSERTION DE PARTITION — définie par rapport à ce qu'on GARDE (règle du projet §3c).
    lus = sum(len(v) for v in seaux.values())
    sans_classe = (rejets.par_motif.get("aucune classe publique déclarée", 0)
                   + rejets.par_motif.get("fichier illisible", 0)
                   + rejets.par_motif.get(
                       "ÉCHEC DE DÉCOMPILATION ffdec (fichier présent, corps absent)", 0))
    assert lus + sans_classe == len(fichiers), \
        f"PARTITION CASSÉE : {lus} classés + {sans_classe} sans classe != {len(fichiers)} fichiers"

    os.makedirs(out_dir, exist_ok=True)
    sorties = {}

    def champs_str(info):
        """Champs déclarés en `nom:type;…` — la forme que lit `croiser.py` de l'étage 1.
        Declared fields as `name:type;…`, the shape etage-1 tooling reads."""
        return ";".join(f"{n}:{t}" for n, t in info["champs"])

    # messages-<v>.tsv — 5 premières colonnes identiques à tools/protocol-mapping/index/messages-*.tsv
    # (compatibilité avec `croiser.py` de l'indexeur ; colonnes ajoutées à la FIN).
    p = os.path.join(out_dir, f"messages-{version}.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("message_nom\tprotocol_id\tfichier:ligne\tnb_champs\tchamps\tparent\tordre_serialisation\temu\tversion\n")
        for i in sorted(seaux["messages"], key=lambda x: x["classe"]):
            f.write(f"{i['classe']}\t{i['proto_id']}\t{i['source']}\t{len(i['champs'])}\t{champs_str(i)}"
                    f"\t{i['parent']}\t{';'.join(i['ordre'])}\tclient-as3\t{version}\n")
    sorties["messages"] = (p, len(seaux["messages"]))

    p = os.path.join(out_dir, f"types-{version}.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("type_nom\tprotocol_id\tfichier:ligne\tnb_champs\tchamps\tparent\tordre_serialisation\temu\tversion\n")
        for i in sorted(seaux["types"], key=lambda x: x["classe"]):
            f.write(f"{i['classe']}\t{i['proto_id']}\t{i['source']}\t{len(i['champs'])}\t{champs_str(i)}"
                    f"\t{i['parent']}\t{';'.join(i['ordre'])}\tclient-as3\t{version}\n")
    sorties["types"] = (p, len(seaux["types"]))

    p = os.path.join(out_dir, f"enums-{version}.tsv")
    n_const = 0
    with open(p, "w", encoding="utf-8") as f:
        f.write("enum_nom\tfichier:ligne\tnb_valeurs\tvaleurs\tversion\n")
        for i in sorted(seaux["enums"], key=lambda x: x["classe"]):
            vals = ";".join(f"{n}={v}" for n, _, v in i["constantes"])
            n_const += len(i["constantes"])
            f.write(f"{i['classe']}\t{i['source']}\t{len(i['constantes'])}\t{vals}\t{version}\n")
    sorties["enums"] = (p, len(seaux["enums"]))

    stats = dict(
        fichiers=len(fichiers), messages=len(seaux["messages"]), types=len(seaux["types"]),
        enums=len(seaux["enums"]), autres=len(seaux["autres"]), constantes=n_const,
        avec_id=sum(1 for i in seaux["messages"] if i["proto_id"]),
        avec_ordre=sum(1 for i in seaux["messages"] if i["ordre"]),
        rejets=rejets.total(), secondes=round(time.time() - t0, 1),
    )
    if not quiet:
        log(f"  → {stats['messages']} messages ({stats['avec_id']} avec protocolId, "
            f"{stats['avec_ordre']} avec ordre de sérialisation), {stats['types']} types, "
            f"{stats['enums']} enums ({n_const} valeurs), {stats['autres']} autres")
        log(f"  → REJETS : {rejets.total()}")
        if rejets.total():
            log(rejets.rapport())
        log(f"  → {stats['secondes']}s")
    return stats, sorties, rejets


def sha_dossier(out_dir, version):
    """sha256 des trois tables concaténées : la preuve du rejeu byte-identique.
    sha256 over the three tables: the byte-identical replay proof."""
    h = hashlib.sha256()
    for nom in (f"messages-{version}.tsv", f"types-{version}.tsv", f"enums-{version}.tsv"):
        h.update(open(os.path.join(out_dir, nom), "rb").read())
    return h.hexdigest()


def epreuve(racine, out_base):
    """Rejeu byte-identique + sabotages + partition. La sortie doit CHANGER quand l'entrée est faussée
    (règle du projet : une mesure qui ne devient pas fausse quand on fausse son entrée ne mesure rien)."""
    print("=== ÉPREUVE de extraire_as3_protocole.py ===")
    tmp = tempfile.mkdtemp(prefix="epreuve-as3-")
    ok_total = True
    try:
        # copie de travail (on ne touche JAMAIS l'arbre d'origine) / working copy, source untouched
        copie = os.path.join(tmp, "arbre")
        shutil.copytree(racine, copie)
        o1, o2 = os.path.join(tmp, "o1"), os.path.join(tmp, "o2")

        s1, _, r1 = extraire(copie, "epr", o1, quiet=True)
        s2, _, _ = extraire(copie, "epr", o2, quiet=True)
        h1, h2 = sha_dossier(o1, "epr"), sha_dossier(o2, "epr")
        ok = (h1 == h2)
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} rejeu byte-identique : sha256 {h1[:16]}… "
              f"{'==' if ok else '!='} {h2[:16]}…")
        print(f"   référence : {s1['fichiers']} .as → {s1['messages']} messages / {s1['types']} types "
              f"/ {s1['enums']} enums · {s1['rejets']} rejets")

        # partition (déjà assertée dans extraire(), on l'affiche)
        somme = s1["messages"] + s1["types"] + s1["enums"] + s1["autres"]
        ok = (somme + r1.par_motif.get("aucune classe publique déclarée", 0) == s1["fichiers"])
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} partition : {s1['messages']}+{s1['types']}+{s1['enums']}"
              f"+{s1['autres']} = {somme} classés, +{r1.par_motif.get('aucune classe publique déclarée', 0)} "
              f"sans classe = {s1['fichiers']} fichiers")

        net = racine_network(copie)

        # SABOTAGE 1 — un protocolId falsifié doit se voir dans la sortie
        cible = None
        for base, _, noms in os.walk(os.path.join(net, "messages")):
            for n in sorted(noms):
                if n.endswith(".as"):
                    cible = os.path.join(base, n)
                    break
            if cible:
                break
        t = open(cible, encoding="utf-8").read()
        t2 = re.sub(r"(public static const protocolId:uint = )\d+", r"\g<1>999999", t, count=1)
        open(cible, "w", encoding="utf-8").write(t2)
        s3, _, _ = extraire(copie, "epr", os.path.join(tmp, "o3"), quiet=True)
        h3 = sha_dossier(os.path.join(tmp, "o3"), "epr")
        vu = "999999" in open(os.path.join(tmp, "o3", "messages-epr.tsv"), encoding="utf-8").read()
        ok = (h3 != h1) and vu
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} sabotage protocolId ({os.path.basename(cible)} → 999999) : "
              f"sortie {'CHANGE' if h3 != h1 else 'INCHANGÉE'}, id saboté {'vu' if vu else 'ABSENT'}")
        open(cible, "w", encoding="utf-8").write(t)

        # SABOTAGE 2 — supprimer une ligne d'écriture doit raccourcir l'ordre de sérialisation
        avant = open(os.path.join(o1, "messages-epr.tsv"), encoding="utf-8").read()
        cible2, ligne_sup = None, None
        for base, _, noms in os.walk(os.path.join(net, "messages")):
            for n in sorted(noms):
                if not n.endswith(".as"):
                    continue
                p = os.path.join(base, n)
                src = open(p, encoding="utf-8").read()
                m = RE_SERIAL_FN.search(src)
                if not m:
                    continue
                ls = src.split("\n")
                idx = src[:m.start()].count("\n")
                corps, _ = lire_corps(ls, idx)
                cands = [j for j, l in corps if re.search(r"\w+\.write\w+\(\s*this\.\w+\s*\)", l)]
                if cands:
                    cible2, ligne_sup = p, cands[0]
                    break
            if cible2:
                break
        t = open(cible2, encoding="utf-8").read()
        ls = t.split("\n")
        supprimee = ls[ligne_sup].strip()
        del ls[ligne_sup]
        open(cible2, "w", encoding="utf-8").write("\n".join(ls))
        _, _, _ = extraire(copie, "epr", os.path.join(tmp, "o4"), quiet=True)
        apres = open(os.path.join(tmp, "o4", "messages-epr.tsv"), encoding="utf-8").read()
        ok = (apres != avant)
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} sabotage ordre (retrait de `{supprimee[:52]}` dans "
              f"{os.path.basename(cible2)}) : table {'CHANGE' if ok else 'INCHANGÉE'}")
        open(cible2, "w", encoding="utf-8").write(t)

        # SABOTAGE 3 — retirer un fichier doit faire baisser le compte de 1 (l'instrument REGARDE)
        os.remove(cible)
        s5, _, _ = extraire(copie, "epr", os.path.join(tmp, "o5"), quiet=True)
        ok = (s5["messages"] == s1["messages"] - 1)
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} sabotage complétude (1 fichier retiré) : "
              f"{s1['messages']} → {s5['messages']} messages")

        # TÉMOIN NÉGATIF — une classe inventée ne doit PAS apparaître
        faux = "ZZZTemoinInventeMessage"
        ok = faux not in open(os.path.join(o1, "messages-epr.tsv"), encoding="utf-8").read()
        ok_total &= ok
        print(f"{'✅' if ok else '❌'} témoin négatif : `{faux}` absent de la table")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ÉPREUVE :", "l'extracteur mesure le terrain" if ok_total
          else "L'EXTRACTEUR EST INERTE OU FAUX")
    return 0 if ok_total else 1


def main():
    """Arguments et deux modes : --epreuve ou extraction.
    Arguments and two modes."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = ICI
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    if "--epreuve" in sys.argv:
        if not args:
            print(__doc__)
            sys.exit(2)
        sys.exit(epreuve(args[0], out))
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    racine, version = args[0], args[1]
    log(f"=== extraction AS3 → protocole · version {version} ===")
    stats, sorties, _ = extraire(racine, version, out)
    for k, (p, n) in sorties.items():
        print(f"{k}: {p} ({n} lignes)")
    print("STATS " + " ".join(f"{k}={v}" for k, v in stats.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
