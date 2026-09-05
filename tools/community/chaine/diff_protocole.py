#!/usr/bin/env python3
"""diff_protocole.py — deux versions du protocole → le delta, par NATURES DE DETTE. 0 LLM, stdlib.

═══ QUOI / WHAT ═══
Survol : range chaque MESSAGE de deux tables dans une nature unique (sans descendre au champ, sans
détecter les renommages — pour ça, voir `diff_builds.py`). Sortie : un TSV.
Coarse view: one nature per message, no field-level detail, no rename detection.

═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
FR : compare deux tables produites par `extraire_as3_protocole.py` (ou toute table au même format) et
     range chaque message dans UNE nature : AJOUTÉ · RETIRÉ · RENUMÉROTÉ · RESTRUCTURÉ · INCHANGÉ.
     Ce n'est pas un `diff` de texte : un `diff` ligne à ligne d'une table triée par nom rendrait
     « tout a changé » dès que les `protocolId` bougent — or ils bougent presque tous (mesuré :
     874 sur 876 entre 2.42 et 2.73, soit 99,8 %).
EN : classifies each message into exactly one nature instead of diffing text.

⚠️ L'ANCRE EST LE NOM, JAMAIS LE `protocolId` (règle du projet §2). `msg:2.42:5` et `msg:2.73:5`
   sont deux choses sans rapport : une jointure par identifiant rendrait des centaines de paires
   TOUTES fausses, avec l'apparence d'un succès.

═══ COMMENT LANCER / HOW TO RUN ═══
  diff_protocole.py <table-A.tsv> <table-B.tsv> [--out DIR] [--exemples N]
  diff_protocole.py --epreuve <table-A.tsv> [--out DIR]
Sortie : `evolution-<A>-vers-<B>.tsv` dans `--out`.

═══ GATE ═══
`--epreuve` — 8 contrôles, tous verts au 04/09/2026 : mutations injectées en nombre connu et retrouvées
NOMINATIVEMENT · partition (classés == union des deux tables) · témoin négatif A vs A → 0 changement ·
sabotage de l'ancre (tous les id décalés → 100 % RENUMEROTE et 0 AJOUTE, là où une jointure par
`protocolId` aurait rendu tout en AJOUTE + RETIRE). Rejouer AVANT de croire une sortie.
"""
import os
import re
import sys
from collections import Counter

ICI = os.path.dirname(os.path.abspath(__file__))
# Natures de SURVOL : exhaustives et exclusives, mais SANS le renommage pur (qui demande un appariement
# structurel — voir `diff_builds.py`). Sur du 3.x, où l'opcode change de nom à chaque build, ce jeu-ci
# ne suffit pas. / Coarse natures, without pure-rename detection: not enough for 3.x builds.
NATURES = ("AJOUTE", "RETIRE", "RENUMEROTE", "RESTRUCTURE", "INCHANGE")


def log(m):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(m, file=sys.stderr, flush=True)


def lire_table(chemin):
    """Rend {nom: {id, champs, ordre, source}}. Tolère les colonnes en plus (on lit par en-tête)."""
    lignes = open(chemin, encoding="utf-8").read().split("\n")
    entete = lignes[0].split("\t")
    idx = {n: i for i, n in enumerate(entete)}
    for exige in ("protocol_id", "champs"):
        if exige not in idx:
            raise SystemExit(f"REFUS : colonne `{exige}` absente de {chemin} — table d'un autre format ?")
    cle = entete[0]                     # message_nom / type_nom / enum_nom
    ordre_col = idx.get("ordre_serialisation")
    t = {}
    for l in lignes[1:]:
        if not l.strip():
            continue
        c = l.split("\t")
        if len(c) <= idx["champs"]:
            continue
        t[c[0]] = dict(id=c[idx["protocol_id"]], champs=c[idx["champs"]],
                       ordre=(c[ordre_col] if ordre_col is not None and len(c) > ordre_col else ""),
                       source=c[idx.get("fichier:ligne", 2)] if len(c) > 2 else "")
    return t, cle


def classer(a, b):
    """Une nature et une seule par nom. La priorité est explicite : une restructuration ÉCRASE un
    renumérotage (si les champs bougent, le numéro n'est plus l'information intéressante)."""
    res = {n: [] for n in NATURES}
    for nom in sorted(set(a) | set(b)):
        if nom not in a:
            res["AJOUTE"].append((nom, "", b[nom]["id"], "", ""))
        elif nom not in b:
            res["RETIRE"].append((nom, a[nom]["id"], "", "", ""))
        else:
            ca, cb = a[nom], b[nom]
            d_champs = "champs" if ca["champs"] != cb["champs"] else ""
            d_ordre = "ordre" if ca["ordre"] != cb["ordre"] else ""
            if d_champs or d_ordre:
                res["RESTRUCTURE"].append((nom, ca["id"], cb["id"], d_champs, d_ordre))
            elif ca["id"] != cb["id"]:
                res["RENUMEROTE"].append((nom, ca["id"], cb["id"], "", ""))
            else:
                res["INCHANGE"].append((nom, ca["id"], cb["id"], "", ""))
    # ASSERTION DE PARTITION, définie par rapport à ce qu'on GARDE : l'union des deux tables.
    total = sum(len(v) for v in res.values())
    union = len(set(a) | set(b))
    assert total == union, f"PARTITION CASSÉE : {total} classés != {union} noms de l'union"
    return res


def ecrire(res, va, vb, out_dir):
    """Écrit la table d'évolution, natures groupées dans un ordre STABLE — sans quoi le rejeu ne
    serait pas byte-identique. Stable ordering keeps replays byte-identical."""
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"evolution-{va}-vers-{vb}.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("nature\tnom\tid_a\tid_b\tdelta_champs\tdelta_ordre\tversion_a\tversion_b\n")
        for nat in NATURES:
            for nom, ia, ib, dc, do in res[nat]:
                f.write(f"{nat}\t{nom}\t{ia}\t{ib}\t{dc}\t{do}\t{va}\t{vb}\n")
    return p


def version_de(chemin):
    """Étiquette de version déduite du NOM du fichier (`messages-2.42.tsv` → `2.42`). C'est une
    convention, pas une mesure : elle vaut ce que vaut le nom donné en amont.
    Version label inferred from the file name; a convention, not a measurement."""
    m = re.search(r"-([\w.]+)\.tsv$", os.path.basename(chemin))
    return m.group(1) if m else os.path.basename(chemin)


def diff(pa, pb, out_dir, exemples=4, quiet=False):
    """Chaîne lire → classer → écrire, plus le résumé.
    Read → classify → write, plus the summary."""
    a, cle_a = lire_table(pa)
    b, cle_b = lire_table(pb)
    if cle_a != cle_b:
        raise SystemExit(f"REFUS : on compare `{cle_a}` avec `{cle_b}` — deux populations différentes.")
    va, vb = version_de(pa), version_de(pb)
    res = classer(a, b)
    p = ecrire(res, va, vb, out_dir)
    n = {k: len(v) for k, v in res.items()}
    commun = len(set(a) & set(b))
    if not quiet:
        log(f"  {va} : {len(a)} · {vb} : {len(b)} · communs : {commun}")
        for nat in NATURES:
            pct = f" ({n[nat]/commun:.1%} des communs)" if nat in ("RENUMEROTE", "RESTRUCTURE", "INCHANGE") and commun else ""
            log(f"  {nat:12s} : {n[nat]}{pct}")
            for nom, ia, ib, dc, do in res[nat][:exemples]:
                detail = f" {ia}→{ib}" if ia and ib and ia != ib else ""
                detail += f" [{dc}{'+' if dc and do else ''}{do}]" if (dc or do) else ""
                log(f"      - {nom}{detail}")
    return res, n, p


def epreuve(pa, out_dir):
    """Mutations INJECTÉES en nombre connu : l'outil doit retrouver EXACTEMENT ces noms-là.
    Compter juste ne suffit pas — un outil qui rendrait 12 noms au hasard rendrait le bon compte."""
    print("=== ÉPREUVE de diff_protocole.py ===")
    a, _ = lire_table(pa)
    noms = sorted(a)
    if len(noms) < 60:
        raise SystemExit("REFUS : table trop petite pour une épreuve honnête (< 60 lignes)")
    tout = True

    attendu_retire = set(noms[0:5])
    attendu_renum = set(noms[10:22])
    attendu_restr_champs = set(noms[30:37])
    attendu_restr_ordre = set(noms[40:44])
    attendu_ajoute = {f"ZZZTemoinAjouteMessage{i}" for i in range(3)}

    b = {}
    for nom, v in a.items():
        if nom in attendu_retire:
            continue
        w = dict(v)
        if nom in attendu_renum:
            w["id"] = str(int(v["id"] or 0) + 100000)
        if nom in attendu_restr_champs:
            w["champs"] = v["champs"] + ";champInjecte:uint"
        if nom in attendu_restr_ordre:
            w["ordre"] = v["ordre"] + ";champInjecte:writeInt"
        b[nom] = w
    for nom in attendu_ajoute:
        b[nom] = dict(id="424242", champs="x:uint", ordre="x:writeInt", source="")

    res = classer(a, b)
    vus = {nat: {x[0] for x in res[nat]} for nat in NATURES}
    attendu_restr = attendu_restr_champs | attendu_restr_ordre

    for nat, att in (("AJOUTE", attendu_ajoute), ("RETIRE", attendu_retire),
                     ("RENUMEROTE", attendu_renum), ("RESTRUCTURE", attendu_restr)):
        ok = vus[nat] == att
        tout &= ok
        manque, trop = att - vus[nat], vus[nat] - att
        print(f"{'✅' if ok else '❌'} {nat:12s} : {len(vus[nat])} trouvés / {len(att)} injectés"
              + ("" if ok else f" — {len(manque)} manqués, {len(trop)} en trop"))

    reste = len(a) - len(attendu_retire) - len(attendu_renum) - len(attendu_restr)
    ok = len(vus["INCHANGE"]) == reste
    tout &= ok
    print(f"{'✅' if ok else '❌'} INCHANGE    : {len(vus['INCHANGE'])} == {reste} attendus "
          "(le reste, par soustraction)")

    somme = sum(len(v) for v in res.values())
    union = len(set(a) | set(b))
    ok = somme == union
    tout &= ok
    print(f"{'✅' if ok else '❌'} partition   : {somme} classés == {union} noms de l'union")

    # TÉMOIN NÉGATIF : une table comparée à ELLE-MÊME ne doit produire AUCUN changement.
    res0 = classer(a, a)
    ok = all(not res0[n] for n in ("AJOUTE", "RETIRE", "RENUMEROTE", "RESTRUCTURE")) \
        and len(res0["INCHANGE"]) == len(a)
    tout &= ok
    print(f"{'✅' if ok else '❌'} témoin négatif : A vs A → 0 changement, {len(res0['INCHANGE'])} inchangés")

    # SABOTAGE DE L'ANCRE : si l'outil joignait par `protocolId`, renuméroter TOUT le rendrait aveugle.
    c = {nom: dict(v, id=str(int(v["id"] or 0) + 7)) for nom, v in a.items()}
    res1 = classer(a, c)
    ok = len(res1["RENUMEROTE"]) == len(a) and not res1["RESTRUCTURE"] and not res1["AJOUTE"]
    tout &= ok
    print(f"{'✅' if ok else '❌'} ancre : tous les id décalés → {len(res1['RENUMEROTE'])} RENUMEROTE "
          f"et {len(res1['AJOUTE'])} AJOUTE (une jointure par id aurait rendu {len(a)} AJOUTE + {len(a)} RETIRE)")

    print("ÉPREUVE :", "le diff retrouve exactement ce qu'on y a mis" if tout else "DIFF FAUX OU INERTE")
    return 0 if tout else 1


def main():
    """Arguments et deux modes : --epreuve ou comparaison.
    Arguments and two modes."""
    av = sys.argv[1:]
    args = [a for i, a in enumerate(av)
            if not a.startswith("--") and not (i and av[i - 1] in {"--out", "--exemples"})]
    out = av[av.index("--out") + 1] if "--out" in av else ICI
    ex = int(av[av.index("--exemples") + 1]) if "--exemples" in av else 4
    if "--epreuve" in av:
        if not args:
            print(__doc__)
            sys.exit(2)
        sys.exit(epreuve(args[0], out))
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    log(f"=== évolution du protocole : {os.path.basename(args[0])} → {os.path.basename(args[1])} ===")
    res, n, p = diff(args[0], args[1], out, exemples=ex)
    print(f"table : {p}")
    print("STATS " + " ".join(f"{k}={v}" for k, v in n.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
