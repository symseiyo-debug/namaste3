#!/usr/bin/env python3
"""extraire_litteraux.py — dump Il2CppInspector-Redux (3.0) → table EXACTE des littéraux + surfaces.

═══ QUOI / WHAT ═══
Maillon A4 de la chaîne 3.x. Entrée : `il2cpp.json` (+ les binaires pour les noms de messages).
Sortie : la table exacte des littéraux, plus un fichier par surface (routes HAAPI, URL, noms de
protocole, chemins sources, Zaap, candidats de configuration). N'appartient QU'À la chaîne 3.x (L4).
Stage A4 of the 3.x chain; belongs to that chain only.

═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
FR : lit `il2cpp.json` → `addressMap.stringLiterals` (chaque littéral avec son adresse virtuelle et ses
     FRONTIÈRES EXACTES). Remplace les extractions inline en une passe de `strings`, qui concaténaient
     des littéraux voisins : c'est ce qui avait fait croire à « 9 routes HAAPI » là où il y en a 372.
     Un extracteur qui concatène produit un compte plausible qui n'est le compte de rien.
EN : reads the exact string-literal table (address + exact boundaries) instead of a `strings` sweep,
     which glued neighbouring literals together and produced a plausible count of nothing.

Ce que le script AFFIRME / what it claims:
  - VÉRIFIÉ : « ce littéral existe dans le client, à cette adresse ». Rien de plus.
  - Ce que le client FAIT du littéral (l'appelle-t-il ?) est DÉDUIT jusqu'à une capture. Exister ≠ être
    appelé : la colonne `categorie` est un classement de FORME, pas une preuve d'usage.

Sorties (dans --out) :
  litteraux-<v>.tsv            table exacte : adresse, catégorie, littéral échappé
  urls-<v>.txt                 http(s)://…
  routes-haapi-<v>.txt         /Segment/Segment… (convention openapi-generator)
  noms-protocole-<v>.txt       Com.Ankama.Dofus.Server.*
  zaap-<v>.txt                 littéraux du canal launcher
  chemins-source-<v>.txt       fichiers .cs/.cpp/.h en clair (attributs CallerFilePath)
  config-candidats-<v>.txt     chemins .json (candidats LoadExternalConfiguration) — DÉDUIT

⚠️ MESURÉ le 04/09 : `il2cpp.json` ne contient **AUCUN** `Com.Ankama.Dofus.Server.*` (0 sur 216 Mo).
Les noms de messages vivent dans `global-metadata.dat` et dans les DLL fantômes — d'où `--binaire`,
répétable. Chercher les noms dans le JSON aurait rendu « 0 » sur un dump PARFAIT.

═══ COMMENT LANCER / HOW TO RUN ═══
  extraire_litteraux.py <il2cpp.json> <version> [--out DIR]
        [--binaire <global-metadata.dat|dossier de DLL>]…  [--corroborer <noms-protocole.txt>]
  extraire_litteraux.py --epreuve <il2cpp.json> [--out DIR]
Les `--binaire` NE SONT PAS OPTIONNELS pour obtenir les noms de protocole (voir l'avertissement ci-dessus).

═══ GATE ═══
`--epreuve` — 7 contrôles, tous verts au 04/09/2026 : rejeu byte-identique · SECOND CHEMIN de comptage
(décodage JSON == regex brut sur le même texte) · partition (classés == littéraux) · URL fantôme injectée
→ vue, compte +1 · route retirée → compte −1 · témoin négatif (route inventée absente du client) ·
entrée vide → 0 classés (un instrument qui rend le même chiffre sur une entrée vide n'a rien lu).
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter

ICI = os.path.dirname(os.path.abspath(__file__))
# Clé de la section du dump qui porte la table exacte des littéraux, LUE dans `il2cpp.json` produit par
# Il2CppInspector-Redux le 04/09 (chaque entrée : `virtualAddress`, `name`, `string`). Si une version
# future de l'outil renomme cette section, le script REFUSE au lieu de rendre une table vide.
# Section key read from the Inspector-Redux dump; a rename makes the script refuse, not return empty.
MARQUEUR = '"stringLiterals": ['

# Classement par FORME, ordonné : la 1re catégorie qui matche gagne → partition par construction.
# Form-based classification, ordered: first match wins → partition holds by construction.
CATEGORIES = [
    ("url", re.compile(r"^https?://")),
    ("nom_protocole", re.compile(r"^Com\.Ankama\.Dofus\.Server\.[A-Za-z0-9_.+|]+$")),
    ("route_haapi", re.compile(r"^/[A-Z][A-Za-z0-9]*(?:/[A-Za-z0-9{}_.-]+)+$")),
    ("config_candidat", re.compile(r"^/?[\w./-]*\.json$")),
    # chemins Windows échappés dans le binaire : `.\Library\PackageCache\com.ankama.x@sha\…\F.cs`
    ("chemin_source", re.compile(r"^[\w.:/\\@ -]+\.(cs|cpp|h|hpp)$")),
    ("zaap", re.compile(r"[Zz]aap")),
    ("type_ankama", re.compile(r"^Com\.Ankama\.[A-Za-z0-9_.+]+$")),
]


RE_NOM_PROTO = re.compile(rb"Com\.Ankama\.Dofus\.Server\.[A-Za-z0-9_.+]+")


def log(m):
    """Trace de progression sur stderr : stdout ne porte que le RÉSULTAT.
    Progress goes to stderr; stdout carries the result only."""
    print(m, file=sys.stderr, flush=True)


def noms_protocole_binaires(chemins, quiet=False):
    """Les noms de messages `Com.Ankama.Dofus.Server.*` ne sont PAS dans `il2cpp.json` — MESURÉ le
    04/09 : 0 occurrence sur les 216 Mo. Ils vivent dans `global-metadata.dat` et dans les DLL fantômes.
    Un extracteur qui les cherchait dans le JSON aurait rendu « 0 nom de protocole » sur un dump PARFAIT :
    un zéro fabriqué par l'instrument, indiscernable d'un client sans protocole.
    Measured: those names live in the raw metadata and the ghost DLLs, never in the JSON."""
    par_fichier, union = {}, set()
    for c in chemins:
        if os.path.isdir(c):
            fichiers = [os.path.join(c, n) for n in sorted(os.listdir(c))]
        else:
            fichiers = [c]
        for f in fichiers:
            try:
                noms = {m.group(0).decode() for m in RE_NOM_PROTO.finditer(open(f, "rb").read())}
            except OSError as e:
                log(f"  ⚠️ illisible : {f} ({e})")
                continue
            if noms:
                par_fichier[f] = noms
                union |= noms
    if not quiet:
        for f, n in sorted(par_fichier.items(), key=lambda x: -len(x[1])):
            log(f"  noms de protocole · {os.path.basename(f)} : {len(n)}")
        log(f"  noms de protocole · union : {len(union)}")
    return union, par_fichier


def echapper(s):
    """Neutralise tabulations et retours ligne : un littéral qui en contient casserait le TSV EN
    SILENCE (colonnes décalées, aucune erreur). Escapes tabs/newlines that would break the TSV."""
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def charger_litteraux(chemin, quiet=False):
    """Rend (liste de dicts, compte du SECOND CHEMIN). Décodage JSON exact, pas de découpe à l'accolade :
    un littéral peut CONTENIR `{`, `[`, `}` — le comptage d'accolades sur ce fichier est faux (mesuré le
    04/09 : il déborde de 164 681 lignes et casse json.loads)."""
    t = time.time()
    taille = os.path.getsize(chemin)
    with open(chemin, "rb") as f:
        # 1) retrouver l'offset du marqueur sans charger les 216 Mo
        cible, dep, prec = MARQUEUR.encode(), None, b""
        pos = 0
        while True:
            bloc = f.read(8 << 20)
            if not bloc:
                break
            j = (prec + bloc).find(cible)
            if j >= 0:
                dep = pos - len(prec) + j
                break
            pos += len(bloc)
            prec = bloc[-len(cible):]
            if not quiet and pos % (64 << 20) == 0:
                log(f"  recherche du marqueur : {pos/1e6:.0f}/{taille/1e6:.0f} Mo")
        if dep is None:
            raise SystemExit(f"REFUS : `{MARQUEUR}` introuvable dans {chemin} — dump d'un autre format ?")
        # 2) décoder le TABLEAU à partir de son crochet ouvrant, par agrandissements successifs
        f.seek(dep + MARQUEUR.index("["))
        dec, tampon, data = json.JSONDecoder(), "", None
        while True:
            bloc = f.read(32 << 20)
            if not bloc:
                raise SystemExit("REFUS : fin de fichier avant la fin du tableau stringLiterals")
            tampon += bloc.decode("utf-8", "replace")
            try:
                data, _ = dec.raw_decode(tampon)
                break
            except json.JSONDecodeError:
                if not quiet:
                    log(f"  lecture du tableau : {len(tampon)/1e6:.0f} Mo…")
    # SECOND CHEMIN : compter les entrées par regex sur le texte brut, sans passer par le décodeur JSON.
    second = len(re.findall(r'^\s*"string":', tampon[:tampon.index("\n]") if "\n]" in tampon else len(tampon)], re.M))
    if not quiet:
        log(f"  {len(data)} littéraux décodés (JSON) · {second} comptés (regex, 2e chemin) "
            f"({time.time()-t:.1f}s)")
    return data, second


def classer(litteraux):
    """Range chaque littéral dans la PREMIÈRE catégorie qui matche → partition par construction.
    First matching category wins, so the partition holds by construction."""
    cat, compte = {}, Counter()
    for e in litteraux:
        s = e.get("string")
        if s is None:
            compte["sans_champ_string"] += 1
            continue
        for nom, rx in CATEGORIES:
            if rx.search(s):
                cat.setdefault(nom, []).append(e)
                compte[nom] += 1
                break
        else:
            cat.setdefault("autre", []).append(e)
            compte["autre"] += 1
    return cat, compte


def ecrire(cat, compte, litteraux, version, out_dir, noms_binaires=None):
    """Écrit la table exacte plus un fichier par surface. Les noms de protocole viennent des
    BINAIRES, jamais du JSON (0 sur 217 Mo, mesuré). Protocol names come from the binaries."""
    os.makedirs(out_dir, exist_ok=True)
    ecrits = {}
    p = os.path.join(out_dir, f"litteraux-{version}.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("adresse_virtuelle\tcategorie\tlitteral_echappe\n")
        for e in litteraux:
            s = e.get("string")
            if s is None:
                continue
            c = next((n for n, rx in CATEGORIES if rx.search(s)), "autre")
            f.write(f"{e.get('virtualAddress','')}\t{c}\t{echapper(s)}\n")
    ecrits["litteraux"] = (p, sum(1 for e in litteraux if e.get("string") is not None))

    for nom_cat, fichier in [("url", "urls"), ("route_haapi", "routes-haapi"),
                             ("zaap", "zaap"), ("chemin_source", "chemins-source"),
                             ("config_candidat", "config-candidats")]:
        vals = sorted({e["string"] for e in cat.get(nom_cat, [])})
        p = os.path.join(out_dir, f"{fichier}-{version}.txt")
        open(p, "w", encoding="utf-8").write("\n".join(vals) + ("\n" if vals else ""))
        ecrits[fichier] = (p, len(vals))

    # noms de protocole : jamais depuis le JSON (0 mesuré) — depuis les binaires passés en `--binaire`.
    if noms_binaires is not None:
        vals = sorted(noms_binaires)
        p = os.path.join(out_dir, f"noms-protocole-{version}.txt")
        open(p, "w", encoding="utf-8").write("\n".join(vals) + ("\n" if vals else ""))
        ecrits["noms-protocole"] = (p, len(vals))
    return ecrits


def extraire(chemin, version, out_dir, corroborer=None, binaires=(), quiet=False):
    """Chaîne complète, avec l'assertion de partition et le second chemin de comptage.
    Full chain, with the partition assertion and the second counting path."""
    litteraux, second = charger_litteraux(chemin, quiet=quiet)
    cat, compte = classer(litteraux)
    noms_bin, par_fichier = (noms_protocole_binaires(binaires, quiet=quiet)
                             if binaires else (None, {}))

    # ASSERTION DE PARTITION — tout littéral tombe dans exactement une catégorie.
    somme = sum(compte.values())
    assert somme == len(litteraux), f"PARTITION CASSÉE : {somme} classés != {len(litteraux)} littéraux"
    # SECOND CHEMIN — un compte issu d'une extraction se remesure avant d'être cité (convention §4).
    ecart = abs(second - len(litteraux))
    if ecart:
        log(f"  ⚠️ écart entre les deux chemins de comptage : JSON {len(litteraux)} vs regex {second}")

    ecrits = ecrire(cat, compte, litteraux, version, out_dir, noms_binaires=noms_bin)

    corrob = None
    if corroborer and os.path.exists(corroborer) and noms_bin is not None:
        ref = {l.strip() for l in open(corroborer, encoding="utf-8") if l.strip()}
        corrob = dict(ref=len(ref), ici=len(noms_bin), commun=len(ref & noms_bin),
                      seulement_ref=len(ref - noms_bin), seulement_ici=len(noms_bin - ref))
        if not quiet:
            log(f"  corroboration `{os.path.basename(corroborer)}` : {corrob['commun']} communs, "
                f"{corrob['seulement_ref']} seulement dans la référence, "
                f"{corrob['seulement_ici']} seulement ici")

    stats = dict(litteraux=len(litteraux), second_chemin=second, ecart=ecart,
                 noms_protocole=(len(noms_bin) if noms_bin is not None else "non mesuré"),
                 **{k: v for k, v in compte.items()})
    if not quiet:
        log("  répartition : " + ", ".join(f"{k}={v}" for k, v in compte.most_common()))
    return stats, ecrits, corrob


def sha_sorties(ecrits):
    """sha256 de toutes les sorties : preuve du rejeu byte-identique.
    sha256 over every output: the byte-identical replay proof."""
    h = hashlib.sha256()
    for _, (p, _) in sorted(ecrits.items()):
        h.update(open(p, "rb").read())
    return h.hexdigest()


def epreuve(chemin, out_dir):
    """Rejeu byte-identique + sabotages sur la table décodée + partition. Les sabotages s'appliquent à
    une base SAINE (l'état réel sert de témoin négatif, jamais de base : un témoin qui porte déjà un
    défaut ne mesure que celui-là)."""
    print("=== ÉPREUVE de extraire_litteraux.py ===")
    tout = True
    o1 = os.path.join(out_dir, "_epreuve1")
    o2 = os.path.join(out_dir, "_epreuve2")
    litteraux, second = charger_litteraux(chemin)
    cat, compte = classer(litteraux)

    s1, e1, _ = extraire(chemin, "epr", o1, quiet=True)
    s2, e2, _ = extraire(chemin, "epr", o2, quiet=True)
    h1, h2 = sha_sorties(e1), sha_sorties(e2)
    ok = h1 == h2
    tout &= ok
    print(f"{'✅' if ok else '❌'} rejeu byte-identique : {h1[:16]}… {'==' if ok else '!='} {h2[:16]}…")

    ok = (s1["litteraux"] == second)
    tout &= ok
    print(f"{'✅' if ok else '❌'} second chemin de comptage : JSON {s1['litteraux']} "
          f"{'==' if ok else '!='} regex {second}")

    somme = sum(v for k, v in compte.items())
    ok = (somme == len(litteraux))
    tout &= ok
    print(f"{'✅' if ok else '❌'} partition : {somme} classés == {len(litteraux)} littéraux "
          f"({len(CATEGORIES)+1} catégories)")

    # SABOTAGE 1 — un littéral injecté doit APPARAÎTRE dans sa catégorie
    faux = {"virtualAddress": "0xDEADBEEF",
            "string": "https://sabotage-temoin.invalid/route"}
    c2, cp2 = classer(litteraux + [faux])
    vu = any(e["string"] == faux["string"] for e in c2.get("url", []))
    ok = vu and cp2["url"] == compte["url"] + 1
    tout &= ok
    print(f"{'✅' if ok else '❌'} sabotage injection : URL fantôme {'vue' if vu else 'ABSENTE'}, "
          f"url {compte['url']} → {cp2['url']}")

    # SABOTAGE 2 — retirer une route doit faire BAISSER le compte de 1
    routes = cat.get("route_haapi", [])
    sans = [e for e in litteraux if e is not routes[0]]
    _, cp3 = classer(sans)
    ok = cp3["route_haapi"] == compte["route_haapi"] - 1
    tout &= ok
    print(f"{'✅' if ok else '❌'} sabotage retrait (`{routes[0]['string']}`) : "
          f"routes {compte['route_haapi']} → {cp3['route_haapi']}")

    # TÉMOIN NÉGATIF — une route inventée ne doit PAS être dans le terrain
    faux_route = "/Fantome/RouteQuiNexistePas"
    ok = faux_route not in {e["string"] for e in routes}
    tout &= ok
    print(f"{'✅' if ok else '❌'} témoin négatif : `{faux_route}` absente du client")

    # SABOTAGE 3 — vider l'entrée doit rendre TOUS les comptes nuls (l'instrument REGARDE)
    _, cp4 = classer([])
    ok = sum(cp4.values()) == 0
    tout &= ok
    print(f"{'✅' if ok else '❌'} entrée vide → {sum(cp4.values())} classés "
          "(un instrument qui rend le même chiffre sur une entrée vide n'a rien lu)")

    for d in (o1, o2):
        for n in os.listdir(d):
            os.remove(os.path.join(d, n))
        os.rmdir(d)
    print("ÉPREUVE :", "l'extracteur mesure le terrain" if tout else "L'EXTRACTEUR EST INERTE OU FAUX")
    return 0 if tout else 1


def main():
    """Arguments (dont `--binaire`, répétable) et deux modes.
    Arguments (including repeatable `--binaire`) and two modes."""
    av = sys.argv[1:]
    drapeaux = {"--out", "--corroborer", "--binaire"}
    args = [a for i, a in enumerate(av)
            if not a.startswith("--") and not (i and av[i - 1] in drapeaux)]
    out = av[av.index("--out") + 1] if "--out" in av else ICI
    corr = av[av.index("--corroborer") + 1] if "--corroborer" in av else None
    binaires = [av[i + 1] for i, a in enumerate(av) if a == "--binaire" and i + 1 < len(av)]
    if "--epreuve" in sys.argv:
        if not args:
            print(__doc__)
            sys.exit(2)
        os.makedirs(out, exist_ok=True)
        sys.exit(epreuve(args[0], out))
    if len(args) < 2:
        print(__doc__)
        sys.exit(2)
    log(f"=== extraction des littéraux · {args[0]} ===")
    stats, ecrits, corrob = extraire(args[0], args[1], out, corroborer=corr, binaires=binaires)
    for k, (p, n) in sorted(ecrits.items()):
        print(f"{k}: {p} ({n} lignes)")
    if corrob:
        print("CORROBORATION " + " ".join(f"{k}={v}" for k, v in corrob.items()))
    print("STATS " + " ".join(f"{k}={v}" for k, v in stats.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
