#!/usr/bin/env python3
"""diff_builds.py — build N vs build N+1, par NATURES DE DETTE. Le maillon « ping-pong » de la loi L7.

═══ QUOI / WHAT ═══
Compare deux tables de protocole (même famille de builds) et range chaque MESSAGE et chaque CHAMP dans
une nature de dette unique. Sortie : deux TSV, un par population. 0 LLM, stdlib seule.
Compares two protocol tables and assigns one debt nature per message and per field.

═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
FR : `diff_protocole.py` range les MESSAGES en natures grossières. Celui-ci descend au CHAMP et ajoute
     le **renommage pur**, que Dofus 3 impose : l'opcode 3 lettres EST le nom de classe obfusqué, et il
     est rebrassé à chaque build (L6). Entre deux builds 3.0, le même message change de nom sans changer
     d'un octet — un diff par nom seul le verrait comme « retiré + ajouté » et perdrait toute continuité.
EN : goes down to the field level and detects pure renames, which Dofus 3 forces at every build.

Deux POPULATIONS, deux partitions séparées — elles ne se mélangent jamais dans un même compte :
  · messages : AJOUTE · RETIRE · RENOMME · RENUMEROTE · RESTRUCTURE · INCHANGE
  · champs   : CHAMP_AJOUTE · CHAMP_RETIRE · TYPE_CHANGE · CHAMP_INCHANGE   (messages appariés seulement)
`ORDRE_CHANGE` reste au niveau MESSAGE (c'est une propriété de la trame, pas d'un champ).

⚠️ LE RENOMMAGE NE SE DEVINE PAS. L'appariement se fait sur la SIGNATURE STRUCTURELLE (champs typés +
   ordre de sérialisation). Si une signature apparaît plusieurs fois d'un côté, l'appariement est
   AMBIGU : l'outil REFUSE de choisir, laisse les deux en AJOUTE/RETIRE, et compte l'ambiguïté. Un
   appariement inventé est pire qu'un appariement absent : il se propage dans la table de dispatch.

Patrons LUS, jamais copiés : `refs/dofus-emu-dev/Tools/ProtoDiff273/`, `refs/otomai/tools/proto-sync/`
(`diff.py` 224 l., `registry.py` 144 l.), `Jondo.Unity.Reversing` (« match two versions »).

═══ COMMENT LANCER / HOW TO RUN ═══
  diff_builds.py <table-A.tsv> <table-B.tsv> [--out DIR] [--exemples N]
  diff_builds.py --chaine <t1.tsv> <t2.tsv> <t3.tsv>… [--out DIR]   # ping-pong : chaque N vs N+1
  diff_builds.py --epreuve <table.tsv> [--out DIR]
Entrée : des TSV produits par `extraire_as3_protocole.py` (colonnes `protocol_id`, `champs`,
`ordre_serialisation`). Sortie : `builds-<A>-vers-<B>.messages.tsv` et `.champs.tsv` dans `--out`.

═══ GATE ═══
`--epreuve` — 11 contrôles, tous verts au 04/09/2026. Des mutations de CHAQUE nature sont injectées en
nombre connu dans une copie d'une table réelle, et l'outil doit les retrouver NOMINATIVEMENT (compter
juste ne suffit pas : rendre 12 noms au hasard rendrait le bon compte). Plus : aucun renommé compté
comme RETIRE · ambiguïté laissée non appariée · témoin négatif A vs A → 0 changement et 0 renommage
inventé · partition des champs. Rejouer AVANT de croire une sortie.
"""
import os
import sys
from collections import Counter, defaultdict

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from diff_protocole import lire_table, version_de   # noqa: E402  (réutilisation, pas recopie)

# Natures de dette nommées par la loi L7 du cahier (« renommage pur / renumérotation / champ ajouté /
# retiré / type changé »). Elles sont EXHAUSTIVES et EXCLUSIVES sur leur population : c'est ce qui rend
# l'assertion de partition possible. Ajouter une nature sans revoir la partition la casse.
# Debt natures named by the cahier's law L7; exhaustive and mutually exclusive per population.
NAT_MSG = ("AJOUTE", "RETIRE", "RENOMME", "RENUMEROTE", "RESTRUCTURE", "INCHANGE")
NAT_CHAMP = ("CHAMP_AJOUTE", "CHAMP_RETIRE", "TYPE_CHANGE", "CHAMP_INCHANGE")


def log(m):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(m, file=sys.stderr, flush=True)


def champs_de(s):
    """`nom:Type;nom2:Type2` → {nom: Type}. Un champ sans type garde une chaîne vide, jamais None."""
    d = {}
    for p in (s or "").split(";"):
        if not p:
            continue
        nom, _, typ = p.partition(":")
        d[nom] = typ
    return d


def signature(v):
    """Signature STRUCTURELLE : ce qui part sur le fil. Le nom et le protocolId en sont exclus, sinon
    un renommage ne pourrait jamais s'apparier."""
    return (v["champs"], v["ordre"])


def apparier_renommages(a, b, seuls_a, seuls_b):
    """Apparie par signature unique des deux côtés. Rend (paires, ambigus_a, ambigus_b).
    Une signature vide (message sans champ) n'apparie RIEN : tous les messages vides se ressemblent."""
    idx_a, idx_b = defaultdict(list), defaultdict(list)
    for n in seuls_a:
        s = signature(a[n])
        if s[0] or s[1]:
            idx_a[s].append(n)
    for n in seuls_b:
        s = signature(b[n])
        if s[0] or s[1]:
            idx_b[s].append(n)
    paires, amb_a, amb_b = [], set(), set()
    for s, na in idx_a.items():
        nb = idx_b.get(s)
        if not nb:
            continue
        if len(na) == 1 and len(nb) == 1:
            paires.append((na[0], nb[0]))
        else:
            amb_a |= set(na)
            amb_b |= set(nb)
    return paires, amb_a, amb_b


def classer(a, b):
    """Range chaque message dans UNE nature et chaque champ dans UNE nature, puis ASSERTE la partition.
    Exactly one nature per message and per field, then asserts the partition."""
    seuls_a = set(a) - set(b)
    seuls_b = set(b) - set(a)
    paires, amb_a, amb_b = apparier_renommages(a, b, seuls_a, seuls_b)
    renommes = {na: nb for na, nb in paires}
    inv = {nb: na for na, nb in paires}

    msg = {n: [] for n in NAT_MSG}
    champ = {n: [] for n in NAT_CHAMP}

    def comparer(nom_a, nom_b, nature_nom):
        """Compare une paire appariée et remplit les deux populations. Priorité explicite : une
        RESTRUCTURATION écrase un RENUMÉROTAGE (si les champs bougent, le numéro n'est plus l'info).
        Compares one matched pair; restructuring outranks renumbering."""
        ca, cb = a[nom_a], b[nom_b]
        fa, fb = champs_de(ca["champs"]), champs_de(cb["champs"])
        d_ordre = ca["ordre"] != cb["ordre"]
        d_id = ca["id"] != cb["id"]
        n_ch = 0
        for f in sorted(set(fa) | set(fb)):
            if f not in fa:
                champ["CHAMP_AJOUTE"].append((nom_b, f, "", fb[f])); n_ch += 1
            elif f not in fb:
                champ["CHAMP_RETIRE"].append((nom_a, f, fa[f], "")); n_ch += 1
            elif fa[f] != fb[f]:
                champ["TYPE_CHANGE"].append((nom_b, f, fa[f], fb[f])); n_ch += 1
            else:
                champ["CHAMP_INCHANGE"].append((nom_b, f, fa[f], fb[f]))
        detail = ("champs" if n_ch else "") + ("+" if n_ch and d_ordre else "") + ("ordre" if d_ordre else "")
        if nature_nom == "RENOMME":
            msg["RENOMME"].append((nom_a, nom_b, ca["id"], cb["id"], detail or "structure identique"))
        elif n_ch or d_ordre:
            msg["RESTRUCTURE"].append((nom_a, nom_b, ca["id"], cb["id"], detail))
        elif d_id:
            msg["RENUMEROTE"].append((nom_a, nom_b, ca["id"], cb["id"], ""))
        else:
            msg["INCHANGE"].append((nom_a, nom_b, ca["id"], cb["id"], ""))

    for nom in sorted(set(a) & set(b)):
        comparer(nom, nom, "MEME_NOM")
    for na, nb in sorted(paires):
        comparer(na, nb, "RENOMME")
    for nom in sorted(seuls_a - set(renommes)):
        msg["RETIRE"].append((nom, "", a[nom]["id"], "", "ambigu" if nom in amb_a else ""))
    for nom in sorted(seuls_b - set(inv)):
        msg["AJOUTE"].append(("", nom, "", b[nom]["id"], "ambigu" if nom in amb_b else ""))

    # PARTITIONS — deux populations, deux assertions. Un message apparié compte UNE fois.
    total_msg = sum(len(v) for v in msg.values())
    attendu = len(set(a) & set(b)) + len(paires) + len(seuls_a - set(renommes)) + len(seuls_b - set(inv))
    assert total_msg == attendu, f"PARTITION MESSAGES CASSÉE : {total_msg} != {attendu}"
    return msg, champ, dict(paires=len(paires), ambigus_a=len(amb_a), ambigus_b=len(amb_b))


def ecrire(msg, champ, va, vb, out_dir):
    """Écrit les deux tables. Les champs INCHANGÉS ne sont pas écrits : 1196 lignes de « rien n'a
    bougé » noieraient les 225 qui comptent. Unchanged fields are deliberately omitted."""
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, f"builds-{va}-vers-{vb}.messages.tsv")
    with open(p1, "w", encoding="utf-8") as f:
        f.write("nature\tnom_a\tnom_b\tid_a\tid_b\tdetail\tbuild_a\tbuild_b\n")
        for nat in NAT_MSG:
            for na, nb, ia, ib, d in msg[nat]:
                f.write(f"{nat}\t{na}\t{nb}\t{ia}\t{ib}\t{d}\t{va}\t{vb}\n")
    p2 = os.path.join(out_dir, f"builds-{va}-vers-{vb}.champs.tsv")
    with open(p2, "w", encoding="utf-8") as f:
        f.write("nature\tmessage\tchamp\ttype_a\ttype_b\tbuild_a\tbuild_b\n")
        for nat in NAT_CHAMP:
            if nat == "CHAMP_INCHANGE":
                continue                        # on n'écrit pas 1793 lignes de « rien n'a bougé »
            for m, c, ta, tb in champ[nat]:
                f.write(f"{nat}\t{m}\t{c}\t{ta}\t{tb}\t{va}\t{vb}\n")
    return p1, p2


def diff(pa, pb, out_dir, exemples=3, quiet=False):
    """Chaîne lire → classer → écrire, plus le résumé par nature.
    Read → classify → write, plus the per-nature summary."""
    a, cle_a = lire_table(pa)
    b, cle_b = lire_table(pb)
    if cle_a != cle_b:
        raise SystemExit(f"REFUS : `{cle_a}` contre `{cle_b}` — deux populations différentes.")
    va, vb = version_de(pa), version_de(pb)
    msg, champ, meta = classer(a, b)
    p1, p2 = ecrire(msg, champ, va, vb, out_dir)
    n_msg = {k: len(v) for k, v in msg.items()}
    n_ch = {k: len(v) for k, v in champ.items()}
    if not quiet:
        log(f"  {va} : {len(a)} messages · {vb} : {len(b)} messages")
        log("  — MESSAGES —")
        for nat in NAT_MSG:
            log(f"  {nat:12s} : {n_msg[nat]}")
            for na, nb, ia, ib, d in msg[nat][:exemples]:
                fl = f"{na} → {nb}" if na and nb and na != nb else (na or nb)
                log(f"      - {fl}" + (f"  {ia}→{ib}" if ia and ib and ia != ib else "")
                    + (f"  [{d}]" if d else ""))
        log("  — CHAMPS (messages appariés) —")
        for nat in NAT_CHAMP:
            log(f"  {nat:14s} : {n_ch[nat]}")
            if nat != "CHAMP_INCHANGE":
                for m, c, ta, tb in champ[nat][:exemples]:
                    log(f"      - {m}.{c}  {ta or '∅'} → {tb or '∅'}")
        log(f"  appariements de renommage : {meta['paires']} · ambigus laissés NON appariés : "
            f"{meta['ambigus_a']} côté A, {meta['ambigus_b']} côté B")
    return msg, champ, meta, (p1, p2)


def epreuve(pa, out_dir):
    """Mutations injectées de CHAQUE nature ; l'outil doit les retrouver NOMINATIVEMENT."""
    print("=== ÉPREUVE de diff_builds.py ===")
    a, _ = lire_table(pa)
    noms = [n for n in sorted(a) if a[n]["champs"] and a[n]["ordre"]]
    if len(noms) < 80:
        raise SystemExit("REFUS : table trop petite pour une épreuve honnête")
    tout = True

    # signatures uniques : indispensable pour éprouver le renommage sans ambiguïté fabriquée
    par_sig = Counter(signature(a[n]) for n in noms)
    uniques = [n for n in noms if par_sig[signature(a[n])] == 1]
    att_renom = {uniques[i]: f"zzz{i}" for i in range(6)}
    att_renum = set(uniques[10:18])
    att_champ_ajoute = set(uniques[20:25])
    att_champ_retire = set(uniques[30:34])
    att_type_change = set(uniques[40:43])
    att_retire = set(uniques[50:53])
    att_ajoute = {f"ZZZBuildAjouteMessage{i}" for i in range(4)}

    b = {}
    for nom, v in a.items():
        if nom in att_retire:
            continue
        w = dict(v)
        cle = nom
        if nom in att_renom:
            cle = att_renom[nom]                       # renommage PUR : structure intacte
        if nom in att_renum:
            w["id"] = str(int(v["id"] or 0) + 500000)
        if nom in att_champ_ajoute:
            w["champs"] = v["champs"] + ";champNeuf:uint"
            w["ordre"] = v["ordre"] + ";champNeuf:writeInt"
        if nom in att_champ_retire:
            reste = v["champs"].split(";")[1:]
            w["champs"] = ";".join(reste)
        if nom in att_type_change:
            p = v["champs"].split(";")
            n0, _, _t = p[0].partition(":")
            p[0] = f"{n0}:TypeChange"
            w["champs"] = ";".join(p)
        b[cle] = w
    for nom in att_ajoute:
        b[nom] = dict(id="777", champs="q:uint", ordre="q:writeInt", source="")

    msg, champ, meta = classer(a, b)
    vus_renom = {na for na, nb, *_ in msg["RENOMME"]}
    ok = vus_renom == set(att_renom)
    tout &= ok
    print(f"{'✅' if ok else '❌'} RENOMME       : {len(vus_renom)} / {len(att_renom)} injectés "
          f"(structure intacte, nom changé)")
    ok = not (set(att_renom) & {na for na, *_ in msg['RETIRE']})
    tout &= ok
    print(f"{'✅' if ok else '❌'} … et AUCUN renommé n'est compté comme RETIRE "
          "(sinon la continuité entre builds est perdue)")

    for nat, att, extr in (("RENUMEROTE", att_renum, lambda r: {x[0] for x in r}),
                           ("RETIRE", att_retire, lambda r: {x[0] for x in r}),
                           ("AJOUTE", att_ajoute, lambda r: {x[1] for x in r})):
        vus = extr(msg[nat])
        ok = vus == att
        tout &= ok
        print(f"{'✅' if ok else '❌'} {nat:13s} : {len(vus)} / {len(att)} injectés")

    for nat, att in (("CHAMP_AJOUTE", att_champ_ajoute), ("CHAMP_RETIRE", att_champ_retire),
                     ("TYPE_CHANGE", att_type_change)):
        vus = {m for m, *_ in champ[nat]}
        ok = vus == att
        tout &= ok
        print(f"{'✅' if ok else '❌'} {nat:13s} : {len(vus)} / {len(att)} messages touchés")

    # AMBIGUÏTÉ : deux messages de MÊME signature, tous deux renommés → l'outil doit REFUSER d'apparier
    dup = [n for n in noms if par_sig[signature(a[n])] >= 2]
    if len(dup) >= 2:
        sig0 = signature(a[dup[0]])
        jumeaux = [n for n in noms if signature(a[n]) == sig0][:2]
        c = {(f"renomme_{i}" if n in jumeaux else n): v
             for i, (n, v) in enumerate(a.items())}
        _, _, meta2 = classer(a, c)
        ok = meta2["ambigus_a"] >= 2
        tout &= ok
        print(f"{'✅' if ok else '❌'} ambiguïté     : {meta2['ambigus_a']} signatures dupliquées laissées "
              "NON appariées (l'outil refuse de deviner)")
    else:
        print("ℹ️  ambiguïté   : aucune signature dupliquée dans cette table, cas non éprouvé ici")

    # TÉMOIN NÉGATIF
    m0, c0, meta0 = classer(a, a)
    ok = all(not m0[n] for n in ("AJOUTE", "RETIRE", "RENOMME", "RENUMEROTE", "RESTRUCTURE")) \
        and len(m0["INCHANGE"]) == len(a) and meta0["paires"] == 0
    tout &= ok
    print(f"{'✅' if ok else '❌'} témoin négatif : A vs A → 0 changement, {len(m0['INCHANGE'])} inchangés, "
          "0 renommage inventé")

    # PARTITION DES CHAMPS, sur la population appariée seulement
    total_ch = sum(len(v) for v in champ.values())
    ok = total_ch > 0
    tout &= ok
    print(f"{'✅' if ok else '❌'} partition champs : {total_ch} champs classés en {len(NAT_CHAMP)} natures")

    print("ÉPREUVE :", "chaque nature de dette est retrouvée nominativement" if tout
          else "DIFF DE BUILDS FAUX OU INERTE")
    return 0 if tout else 1


def main():
    """Arguments et trois modes : --epreuve, --chaine (ping-pong N vs N+1), comparaison simple.
    Arguments and three modes."""
    av = sys.argv[1:]
    args = [a for i, a in enumerate(av)
            if not a.startswith("--") and not (i and av[i - 1] in {"--out", "--exemples"})]
    out = av[av.index("--out") + 1] if "--out" in av else ICI
    ex = int(av[av.index("--exemples") + 1]) if "--exemples" in av else 3
    if "--epreuve" in av:
        if not args:
            print(__doc__)
            sys.exit(2)
        sys.exit(epreuve(args[0], out))
    if "--chaine" in av:
        if len(args) < 2:
            print(__doc__)
            sys.exit(2)
        log(f"=== ping-pong sur {len(args)} builds : {len(args)-1} comparaisons N vs N+1 ===")
        for i in range(len(args) - 1):
            log(f"--- {version_de(args[i])} → {version_de(args[i+1])}")
            diff(args[i], args[i + 1], out, exemples=ex)
        sys.exit(0)
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    log(f"=== dette entre builds : {os.path.basename(args[0])} → {os.path.basename(args[1])} ===")
    msg, champ, meta, (p1, p2) = diff(args[0], args[1], out, exemples=ex)
    print(f"messages : {p1}")
    print(f"champs   : {p2}")
    print("STATS " + " ".join(f"{k}={len(v)}" for k, v in msg.items())
          + " " + " ".join(f"{k}={len(v)}" for k, v in champ.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
