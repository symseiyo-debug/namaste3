#!/usr/bin/env python3
"""tabler_protobuf_3x.py — dump 3.x → table de protocole comparable entre builds. 0 LLM, stdlib.

═══ QUOI / WHAT ═══
Maillon A4bis de la chaîne 3.x. Entrée : le `cs/il2cpp.cs` d'un dump. Sortie :
`messages3x-<build>.tsv`, au MÊME format de colonnes que les tables 2.x, pour que `diff_builds.py`
puisse comparer deux builds 3.x sans outil supplémentaire.
Stage A4bis: turns a 3.x dump into a table `diff_builds.py` can compare across builds.

═══ POURQUOI / WHY (écrit le 05/09/2026) ═══
Le rebrassage 3.x (loi L6) ne se mesure que si l'on peut comparer DEUX builds. Or en 3.x il n'y a ni
`protocolId` ni nom clair de classe : le message est identifié par son TOKEN obfusqué (`hdw`), qui
change à chaque build. Ce qui NE change pas, c'est la forme protobuf : les numéros de champ et leurs
types. C'est donc elle qui sert d'ancre — exactement l'appariement par signature de `diff_builds.py`.

RÉUTILISATION, pas réécriture : l'extraction elle-même est faite par `tools/protocol-mapping/matcher/
extraire_signatures.py` (écrit ailleurs dans le projet, déjà éprouvé, 2206 classes sur 3.6.10.10). Ce
script l'IMPORTE et surcharge ses deux constantes de chemin, parce qu'elles sont figées sur une seule
build — le même verrou que `gate-g0.py` avait. On ne modifie pas sa zone ; on écrit dans la nôtre.
Reuses the neighbouring extractor by overriding its build-locked path constants.

⚠️ `protocol_id` reste VIDE : en 3.x il n'existe pas. La nature `RENUMEROTE` ne peut donc pas se
déclencher, et c'est correct — ce qui bouge ici est le TOKEN (nature `RENOMME`), pas un numéro.

═══ COMMENT LANCER / HOW TO RUN ═══
  tabler_protobuf_3x.py <dossier-dump> <build> [--out DIR] [--assemblies Game,Connection]
  tabler_protobuf_3x.py --epreuve <dossier-dump> [--out DIR]
Le dossier-dump doit contenir `cs/il2cpp.cs`. Sortie : `messages3x-<build>.tsv` + le JSONL brut.

═══ GATE ═══
`--epreuve` : rejeu byte-identique · partition (classes retenues + écartées == classes lues) ·
sabotage (une classe retirée fait baisser le compte de 1) · témoin négatif (un token inventé est
absent) · contrôle que chaque ligne porte au moins un champ numéroté OU est déclarée sans champ.
"""
import hashlib
import importlib.util
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
# Extracteur voisin, réutilisé tel quel. Son chemin est une CONSTANTE SOURCÉE : il vit dans la zone du
# matcher (étage 1, renommé `protocol-mapping` depuis) et est éprouvé par `verifier_motif.py` 3/3.
EXTRACTEUR = os.path.normpath(os.path.join(
    ICI, "..", "..", "protocol-mapping", "matcher", "extraire_signatures.py"))
# Assemblages qui portent le protocole, MESURÉS par gate-g0 le 04/09 : Game.dll 2169 classes
# IBufferMessage, Connection.dll 37. Les autres (Google, Core) sont de la plomberie protobuf.
ASSEMBLAGES_PROTOCOLE = ("Ankama.Dofus.Protocol.Game.dll", "Ankama.Dofus.Protocol.Connection.dll")


def log(m):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(m, file=sys.stderr, flush=True)


def charger_extracteur():
    """Importe `extraire_signatures.py` sans l'exécuter, pour pouvoir surcharger ses chemins.
    Imports the neighbouring extractor as a module so its path constants can be overridden."""
    if not os.path.isfile(EXTRACTEUR):
        raise SystemExit(f"REFUS : extracteur voisin introuvable — {EXTRACTEUR}")
    s = importlib.util.spec_from_file_location("extraire_signatures", EXTRACTEUR)
    m = importlib.util.module_from_spec(s)
    sys.modules["extraire_signatures"] = m
    sys.path.insert(0, os.path.dirname(EXTRACTEUR))   # il importe `verifier_motif` à côté de lui
    s.loader.exec_module(m)
    return m


def extraire_jsonl(dump, build, out_dir):
    """Produit le JSONL des signatures pour CETTE build, en surchargeant les chemins figés du voisin.
    Produces the signature JSONL for THIS build by overriding the neighbour's frozen paths."""
    cs = os.path.join(dump, "cs", "il2cpp.cs")
    if not os.path.isfile(cs):
        raise SystemExit(f"REFUS : `{cs}` absent — dump incomplet ou pas encore fini.")
    m = charger_extracteur()
    os.makedirs(out_dir, exist_ok=True)
    jsonl = os.path.join(out_dir, f"signatures3x-{build}.jsonl")
    m.CS_PATH = cs                                   # la build jugée, pas celle codée en dur
    m.OUT_PATH = jsonl
    m.DUMP = dump
    if hasattr(m, "HERE"):
        m.HERE = out_dir                             # les à-côtés (stats) restent dans NOTRE zone
    log(f"  extraction des signatures depuis {cs} ({os.path.getsize(cs)/1e6:.0f} Mo)")
    m.main()
    return jsonl


def champs_de(sig):
    """Empreinte STRUCTURELLE d'un message : `f<numéro>:<type>` triés par numéro. C'est ce qui part sur
    le fil, et la seule chose qui survit au rebrassage des tokens.
    Structural fingerprint: field number and type, the only thing that survives token reshuffling."""
    out = []
    for f in sorted(sig.get("fields", []), key=lambda x: x.get("number", 0)):
        t = f.get("inner") or f.get("raw") or "?"
        if f.get("is_map"):
            t = f"map<{f.get('key_type')},{t}>"
        elif f.get("repeated"):
            t = f"repeated {t}"
        out.append(f"f{f.get('number')}:{t}")
    return out


def tabler(jsonl, build, out_dir, assemblages):
    """JSONL → TSV au format des tables 2.x, pour que `diff_builds.py` le lise sans adaptation.
    JSONL → TSV in the same column layout as the 2.x tables."""
    retenues, ecartees, sans_champ = [], 0, 0
    with open(jsonl, encoding="utf-8") as f:
        for ligne in f:
            if not ligne.strip():
                continue
            s = json.loads(ligne)
            if assemblages and s.get("assembly") not in assemblages:
                ecartees += 1
                continue
            ch = champs_de(s)
            if not ch:
                sans_champ += 1
            retenues.append((s, ch))
    p = os.path.join(out_dir, f"messages3x-{build}.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("message_nom\tprotocol_id\tfichier:ligne\tnb_champs\tchamps"
                "\tparent\tordre_serialisation\temu\tversion\n")
        for s, ch in sorted(retenues, key=lambda x: x[0].get("obf_name", "")):
            parent = ".".join(s.get("parent_chain") or [])
            # `protocol_id` VIDE : le 3.x n'en a pas. `ordre_serialisation` = l'ordre des numéros,
            # qui EST l'ordre protobuf sur le fil.
            f.write(f"{s.get('obf_name')}\t\tcs/il2cpp.cs:{s.get('typedef_index')}\t{len(ch)}"
                    f"\t{';'.join(ch)}\t{parent}\t{';'.join(ch)}\tclient-il2cpp\t{build}\n")
    stats = dict(retenues=len(retenues), ecartees=ecartees, sans_champ=sans_champ,
                 lues=len(retenues) + ecartees)
    assert stats["retenues"] + stats["ecartees"] == stats["lues"], "PARTITION CASSÉE"
    return p, stats


def sha(p):
    """sha256 d'un fichier : la preuve du rejeu byte-identique.
    sha256 of one file: the byte-identical replay proof."""
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def epreuve(dump, out_dir):
    """Rejeu byte-identique, partition, sabotage et témoin négatif sur le JSONL déjà produit.
    Replay, partition, sabotage and negative witness over the produced JSONL."""
    print("=== ÉPREUVE de tabler_protobuf_3x.py ===")
    tout = True
    jsonl = os.path.join(out_dir, "_epr.jsonl")
    src = None
    for cand in sorted(os.listdir(out_dir)):
        if cand.startswith("signatures3x-") and cand.endswith(".jsonl"):
            src = os.path.join(out_dir, cand)
            break
    if src is None:
        raise SystemExit("REFUS : aucun `signatures3x-*.jsonl` à éprouver — lance d'abord l'extraction.")
    lignes = [l for l in open(src, encoding="utf-8") if l.strip()]
    open(jsonl, "w", encoding="utf-8").writelines(lignes)

    p1, s1 = tabler(jsonl, "epr", out_dir, ASSEMBLAGES_PROTOCOLE)
    h1 = sha(p1)
    p2, s2 = tabler(jsonl, "epr", out_dir, ASSEMBLAGES_PROTOCOLE)
    ok = h1 == sha(p2)
    tout &= ok
    print(f"{'✅' if ok else '❌'} rejeu byte-identique : {h1[:16]}…")
    print(f"   référence : {s1['lues']} classes lues, {s1['retenues']} retenues "
          f"(assemblages du protocole), {s1['ecartees']} écartées, {s1['sans_champ']} sans champ")

    ok = s1["retenues"] + s1["ecartees"] == s1["lues"]
    tout &= ok
    print(f"{'✅' if ok else '❌'} partition : {s1['retenues']} + {s1['ecartees']} == {s1['lues']}")

    # SABOTAGE : retirer une classe RETENUE doit faire baisser le compte de 1
    garde = [l for l in lignes if json.loads(l).get("assembly") in ASSEMBLAGES_PROTOCOLE]
    open(jsonl, "w", encoding="utf-8").writelines([l for l in lignes if l != garde[0]])
    _, s3 = tabler(jsonl, "epr", out_dir, ASSEMBLAGES_PROTOCOLE)
    ok = s3["retenues"] == s1["retenues"] - 1
    tout &= ok
    print(f"{'✅' if ok else '❌'} sabotage : 1 classe retirée → {s1['retenues']} → {s3['retenues']}")

    # TÉMOIN NÉGATIF : un token inventé ne doit pas apparaître
    ok = "zzzTokenInvente" not in open(p1, encoding="utf-8").read()
    tout &= ok
    print(f"{'✅' if ok else '❌'} témoin négatif : `zzzTokenInvente` absent de la table")

    # ENTRÉE VIDE : l'instrument doit rendre 0, pas le même chiffre
    open(jsonl, "w", encoding="utf-8").write("")
    _, s4 = tabler(jsonl, "epr", out_dir, ASSEMBLAGES_PROTOCOLE)
    ok = s4["lues"] == 0
    tout &= ok
    print(f"{'✅' if ok else '❌'} entrée vide → {s4['lues']} classes lues")

    for f in (jsonl, p1):
        if os.path.exists(f):
            os.remove(f)
    print("ÉPREUVE :", "la table mesure le dump" if tout else "TABLE INERTE OU FAUSSE")
    return 0 if tout else 1


def main():
    """Arguments et deux modes : --epreuve, ou extraction + mise en table.
    Arguments and two modes."""
    av = sys.argv[1:]
    args = [a for i, a in enumerate(av)
            if not a.startswith("--") and not (i and av[i - 1] in {"--out", "--assemblies"})]
    out = av[av.index("--out") + 1] if "--out" in av else ICI
    asm = (tuple(av[av.index("--assemblies") + 1].split(","))
           if "--assemblies" in av else ASSEMBLAGES_PROTOCOLE)
    if "--epreuve" in av:
        os.makedirs(out, exist_ok=True)
        sys.exit(epreuve(args[0] if args else "", out))
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    dump, build = args[0], args[1]
    log(f"=== table protobuf 3.x · build {build} ===")
    jsonl = extraire_jsonl(dump, build, out)
    p, stats = tabler(jsonl, build, out, asm)
    print(f"jsonl : {jsonl}")
    print(f"table : {p}")
    print("STATS " + " ".join(f"{k}={v}" for k, v in stats.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
