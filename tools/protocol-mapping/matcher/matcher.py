#!/usr/bin/env python3
"""
matcher.py — Étage 1 (Namaste 3), matcher v1.

QUOI : apparie les 513 noms clairs de tête à des classes obfusquées IBufferMessage, par
    FORME D'IMBRICATION seule (aucun champ côté clair, cf. POURQUOI), à partir de
    `signatures-obfusquees.jsonl` et `attendus-depuis-noms.jsonl`. Écrit
    `correspondance-noms-classes.tsv`.
POURQUOI (04/09/2026, brief) : 1re tentative de matching — sert de ligne de
    base mesurée pour v2/v3 (voir ci-dessous pourquoi ce n'est pas l'algorithme complet
    de Jondo).
COMMENT LANCER : `python3 matcher.py` (lit les 2 fichiers ci-dessus, écrit le TSV) ;
    `python3 matcher.py --epreuve` pour les 3 témoins.
GATE : `--epreuve` doit rendre "MORD DANS LES DEUX SENS" — identité des paires détruite
    par mélange (témoin 2) et stabilité inter-processus à seeds de hachage différents
    (témoin 3).

FR : POURQUOI ce n'est PAS l'algorithme de Jondo (Matcher.cs, a.1 de la spec), et le dire
     est plus utile que le simuler. Le WL-matching de Jondo apparie DEUX GRAPHES DE MÊME
     NATURE (obfusqué-ancien ↔ obfusqué-nouveau), chacun avec ses numéros de champ, ses
     types résolus, son graphe complet de références. Notre problème est ASYMÉTRIQUE :
     un côté (classes obfusquées) a un graphe complet ; l'autre (1003 littéraux orphelins,
     mesuré par Jondo lui-même : « NADIE las referencia ») n'a NI numéro de champ NI type —
     seulement un NOM et une POSITION dans un arbre d'imbrication (`Foo+Types+Bar`). Le
     round-0/rondes de Jondo (signature = numéros+types de champ) n'a donc pas de PENDANT
     côté noms clairs : impossible à reproduire tel quel, pas juste « pas encore fait ».
     Le seul axe commun mesuré aux DEUX côtés est la FORME D'IMBRICATION (nombre d'enfants,
     récursif) — confirmée alternante `Types`/libellé à 100% (1003/1003) côté clair, et
     repliable symétriquement côté obfusqué (le conteneur `Types` existe, mais renommé :
     0 occurrence du littéral "class Types" dans nos 2 assemblies cibles, mesuré). C'est
     l'ADAPTATION réimplémentée ici : un WL round-0 restreint à cette seule dimension.
     Score mesuré (voir RAPPORT-MATCHER.md) : très en dessous du 11,3% de Jondo — attendu,
     puisque son signal (champs) est bien plus riche que le nôtre (imbrication seule).
EN : why this is NOT Jondo's algorithm, measured not asserted — see FR above. Our two
     sides are asymmetric (one has a full field graph, the other only orphaned names with
     a nesting position), so only nesting SHAPE is comparable; field-based WL rounds have
     no counterpart on the clear-name side.

Statut : DÉDUIT PARTOUT (règle du projet) — la ressemblance de forme est une hypothèse, jamais
une preuve ; VÉRIFIÉ exigerait un ancrage déterministe nommable, et aucun n'existe ici
(mesuré : aucun descripteur protobuf en clair, littéraux orphelins — cf. hypothèse déjà
réfutée citée par l'ordre de mission). Une classe/nom sans correspondance UNIQUE va en
« À CLASSER », jamais assignée au hasard parmi des candidats à égalité.
Stdlib seule. 0 LLM.
"""
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIG_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
ATTENDUS_PATH = os.path.join(HERE, "attendus-depuis-noms.jsonl")
OUT_TSV = os.path.join(HERE, "correspondance-noms-classes.tsv")

HEADER = ["classe_obf", "typedef_index", "nom_clair", "score", "methode", "statut", "note"]


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Reconvertit les listes JSON en tuples (les shape_signature écrites par attendus_depuis_noms.py).
# / Converts JSON lists back to tuples (shape_signature written by attendus_depuis_noms.py).
def to_tuple(x):
    return tuple(to_tuple(i) for i in x) if isinstance(x, list) else x


# Charge un fichier JSONL en liste de dicts, lignes vides ignorées.
# / Loads a JSONL file into a list of dicts, blank lines skipped.
def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def collapse_wrapper_children(tree_node):
    """FR: les vrais enfants sémantiques d'un nœud obfusqué = les enfants de son unique
    conteneur `Types` (à profondeur+1), jamais ses enfants directs (qui SONT le/les
    conteneur(s)). EN: real semantic children = grandchildren via the single `Types`
    wrapper, never the direct children (which ARE the wrapper(s))."""
    real = []
    for wrapper in tree_node.get("children", []):
        real.extend(wrapper.get("children", []))
    return real


# Signature de forme récursive (tuple trié) côté obfusqué, après repli du conteneur Types.
# / Recursive shape signature (sorted tuple) on the obfuscated side, Types wrapper collapsed.
def shape_of_obf(tree_node):
    real = collapse_wrapper_children(tree_node)
    return tuple(sorted(shape_of_obf(r) for r in real))


def build_obf_index(sig_records):
    """Ajoute `_shape` et indexe les messages de tête (depth 0) par assembly."""
    by_assembly = {}
    for r in sig_records:
        r["_shape"] = shape_of_obf(r["nested_tree"])
        if r["depth"] == 0:
            by_assembly.setdefault(r["assembly"], []).append(r)
    return by_assembly


def match_top_level(clear_records, by_assembly, stats):
    """FR: pour chaque nom clair de tête, candidats = même assembly ET même forme
    exacte. Un seul candidat → proposé (DÉDUIT). Zéro ou plusieurs → À CLASSER, avec
    le compte des candidats visible (jamais tu). EN: bucket by assembly + exact shape;
    unique candidate only → proposed; 0 or >1 → unresolved, count always visible."""
    rows = []
    resolved_pairs = []  # (clear_record, obf_record) pour le parent-drag
    for c in clear_records:
        sig = to_tuple(c["shape_signature"])
        cands = [o for o in by_assembly.get(c["assembly_guess"], []) if o["_shape"] == sig]
        if len(cands) == 1:
            o = cands[0]
            rows.append([o["obf_name"], o["typedef_index"], c["full_name"], "1.0",
                         "forme_imbriquee", "DÉDUIT",
                         f"forme exacte unique dans {c['assembly_guess']} (0 autre candidat)"])
            resolved_pairs.append((c, o))
            stats["top_unique"] += 1
        elif len(cands) == 0:
            rows.append(["", "", c["full_name"], "", "", "À_CLASSER",
                         f"0 candidat de même forme dans {c['assembly_guess']} (forme={sig})"])
            stats["top_zero"] += 1
        else:
            rows.append(["", "", c["full_name"], "", "", "À_CLASSER",
                         f"{len(cands)} candidats à égalité de forme dans {c['assembly_guess']} — "
                         "aucun élu sans preuve supplémentaire"])
            stats["top_tied"] += 1
            tied_sizes = stats.setdefault("tied_sizes", {})
            tied_sizes[len(cands)] = tied_sizes.get(len(cands), 0) + 1
    return rows, resolved_pairs


CAUSE_RE_ZERO = "0 candidat de même forme"
CAUSE_RE_TIED = "candidats à égalité de forme"


def tabuler_rejets_par_cause(rows, stats):
    """FR: REJETS PAR CAUSE (garde demandée en revue) — distingue « aucun
    candidat de même forme » (le bucket+forme n'a rien trouvé) de « plusieurs candidats
    à égalité » (trouvé, mais pas unique), et donne la distribution des tailles
    d'égalité. Notre matcher n'a ni graine (seed) ni seuil de score (pas de mécanisme à
    la Jondo 0.55/0.08) — seulement ces deux causes ; une 3e catégorie « autre » reste
    prévue pour ne jamais avaler silencieusement un cas non couvert.
    EN: rejection tally by cause — our matcher has no seed/threshold concept (unlike
    Jondo's scored 0.55/0.08), just these two causes; an "other" bucket stays visible
    so nothing gets silently swallowed."""
    zero = sum(1 for r in rows if r[5] == "À_CLASSER" and CAUSE_RE_ZERO in r[6])
    tied = sum(1 for r in rows if r[5] == "À_CLASSER" and CAUSE_RE_TIED in r[6])
    total_a_classer = sum(1 for r in rows if r[5] == "À_CLASSER")
    autre = total_a_classer - zero - tied
    tied_sizes = stats.get("tied_sizes", {})
    return {"zero_candidat": zero, "candidats_a_egalite": tied, "autre_cause": autre,
            "total_a_classer": total_a_classer, "distribution_tailles_egalite": tied_sizes}


def match_children_by_drag(clear_top_records, resolved_pairs, clear_by_outer, stats):
    """FR: « arrastre par les parents » adapté (spec a.1.5) — UNE seule profondeur, et
    UNIQUEMENT quand la forme distingue les enfants un-à-un des deux côtés (même
    multi-ensemble de formes, chaque forme en exemplaire unique) : sinon les libellés
    clairs (ex. Success/Error) sont interchangeables du point de vue de la forme, et
    forcer un appariement serait une fausse précision — compté à part, jamais deviné.
    EN: one-level parent-drag — pairs children only when shapes distinguish them 1:1 on
    both sides; ties among same-shape siblings are counted, never guessed."""
    rows = []
    for c_top, o_top in resolved_pairs:
        clear_children = load_children_tree(c_top["full_name"], clear_by_outer)
        obf_children = collapse_wrapper_children(o_top["nested_tree"])
        if not clear_children and not obf_children:
            continue
        if len(clear_children) != len(obf_children):
            stats["drag_count_mismatch"] += 1
            continue
        # regroupe par forme des deux côtés — pour un enfant obfusqué déjà "réel" (pas
        # un conteneur Types), sa propre forme = shape_of_obf(node) tel quel (ses
        # propres enfants seront eux-mêmes des conteneurs Types s'il y a un niveau de plus).
        from collections import defaultdict
        by_shape_clear = defaultdict(list)
        for lab, node in clear_children.items():
            by_shape_clear[shape_of_clear(node)].append(lab)
        by_shape_obf = defaultdict(list)
        for node in obf_children:
            by_shape_obf[shape_of_obf(node)].append(node)
        for shape, labels in by_shape_clear.items():
            cands = by_shape_obf.get(shape, [])
            if len(labels) == 1 and len(cands) == 1:
                o = cands[0]
                rows.append([o["name"], o.get("tdi", ""), f"{c_top['full_name']}+Types+{labels[0]}",
                             "0.6", "parent_drag", "DÉDUIT",
                             f"seul enfant de forme {shape} des deux côtés (parent {o_top['obf_name']} déjà proposé)"])
                stats["drag_unique"] += 1
            else:
                stats["drag_tied"] += len(labels)
    return rows


# Signature de forme récursive côté clair (déjà sans conteneur Types, construit par rebuild_clear_trees).
# / Recursive shape signature on the clear side (already Types-free, built by rebuild_clear_trees).
def shape_of_clear(node):
    return tuple(sorted(shape_of_clear(c) for c in node["children"].values()))


# Enfants {libellé: nœud} d'un nom de tête, pour l'arrastre parent-enfant.
# / {label: node} children of a top-level name, for parent-child drag.
def load_children_tree(outer_full_name, clear_by_outer):
    node = clear_by_outer.get(outer_full_name)
    return node["children"] if node else {}


def rebuild_clear_trees():
    """FR: attendus-depuis-noms.jsonl ne garde QUE la signature de forme du nom de tête,
    pas l'arbre {label: nœud} complet nécessaire au parent-drag — on le reconstruit ici
    depuis le fichier source, à l'identique de attendus_depuis_noms.py (même fonction,
    dupliquée sciemment : matcher.py doit rester lisible seul, cf. règle du projet : fichiers
    <500 lignes — un import croisé entre les 2 scripts aurait été plus fragile qu'utile
    pour ~15 lignes). EN: rebuilds the label→node tree matcher.py needs for parent-drag;
    duplicated on purpose, small enough that a cross-import would cost more than it saves."""
    noms_path = os.path.join(os.path.dirname(os.path.dirname(HERE)), "etage0-dump",
                              "noms-protocole-en-clair.v2.txt")
    trees = {}
    with open(noms_path, encoding="utf-8") as f:
        for line in f:
            full = line.strip()
            if not full:
                continue
            parts = full.split("+")
            outer = parts[0]
            labels = parts[1:][1::2]
            node = trees.setdefault(outer, {"children": {}})
            cur = node
            for lab in labels:
                cur = cur["children"].setdefault(lab, {"children": {}})
    return trees


# Écrit les lignes en TSV avec l'en-tête HEADER. / Writes rows as TSV with the HEADER row.
def write_tsv(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")


def run(sig_path=SIG_PATH, attendus_path=ATTENDUS_PATH, out_path=OUT_TSV, shuffle_seed=None):
    """FR: cœur rejouable, appelé tel quel par --epreuve (seed=None = réel,
    seed=int = témoin positif mélangé). EN: replayable core, used as-is by --epreuve."""
    sig_records = load_jsonl(sig_path)
    clear_records = load_jsonl(attendus_path)

    if shuffle_seed is not None:
        # FR: témoin positif — on mélange les FORMES entre noms clairs (seed fixe), en
        # gardant assembly_guess intact (sinon on casserait aussi le bucket, qui n'est
        # pas ce qu'on veut éprouver ici : on veut voir la forme seule perdre son mordant).
        # EN: positive witness — shuffle SHAPES across clear names (fixed seed), keep
        # assembly_guess so only the shape signal itself is tested.
        rng = random.Random(shuffle_seed)
        shapes = [r["shape_signature"] for r in clear_records]
        rng.shuffle(shapes)
        for r, s in zip(clear_records, shapes):
            r["shape_signature"] = s

    by_assembly = build_obf_index(sig_records)
    stats = {"top_unique": 0, "top_zero": 0, "top_tied": 0,
             "drag_unique": 0, "drag_tied": 0, "drag_count_mismatch": 0}
    rows, resolved_pairs = match_top_level(clear_records, by_assembly, stats)

    clear_by_outer = rebuild_clear_trees()
    drag_rows = match_children_by_drag(clear_records, resolved_pairs, clear_by_outer, stats)
    rows.extend(drag_rows)

    write_tsv(rows, out_path)
    return rows, stats


# Point d'entrée : lance run() ou --epreuve, logue les rejets par cause.
# / Entry point: runs run() or --epreuve, logs rejections by cause.
def main():
    args = sys.argv[1:]
    if "--epreuve" in args:
        sys.exit(run_epreuve())
    if not os.path.exists(SIG_PATH) or not os.path.exists(ATTENDUS_PATH):
        log("ABSENT : lance d'abord extraire_signatures.py et attendus_depuis_noms.py.")
        sys.exit(2)
    rows, stats = run()
    a_classer = sum(1 for r in rows if r[5] == "À_CLASSER")
    proposes = len(rows) - a_classer
    log(f"[matcher] {len(rows)} lignes écrites → {OUT_TSV}")
    log(f"[matcher] proposées={proposes} (DÉDUIT) / à_classer={a_classer}")
    log(f"[matcher] détail top-niveau : {stats}")
    rejets = tabuler_rejets_par_cause(rows, stats)
    dominant = max(rejets["distribution_tailles_egalite"].items(), key=lambda kv: kv[1], default=(None, 0))
    log(f"[matcher] rejets par cause : 0 candidat={rejets['zero_candidat']}, "
        f"candidats à égalité={rejets['candidats_a_egalite']}, autre={rejets['autre_cause']} "
        f"(sur {rejets['total_a_classer']} À_CLASSER)")
    log(f"[matcher] distribution des tailles d'égalité (taille→nb noms) : "
        f"{dict(sorted(rejets['distribution_tailles_egalite'].items()))}")
    if dominant[0] is not None:
        part = dominant[1] / max(rejets["candidats_a_egalite"], 1)
        log(f"[matcher] cause dominante des égalités : taille {dominant[0]} "
            f"({dominant[1]} noms, {part:.0%} des cas à égalité) — "
            + ("le critère forme+bucket est trop large pour cette taille, pas le terrain qui est dur"
               if part > 0.5 else "pas de taille qui domine seule"))


# Empreinte sha256 d'un fichier (témoin de déterminisme). / File sha256 hash (determinism witness).
def sha256_of(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# Ensemble des paires (nom_clair, classe_obf) proposées par graine de tête (méthode forme_imbriquee).
# / Set of (clear_name, obf_class) pairs proposed by top-level seeding (forme_imbriquee method).
def top_pairs(rows):
    return {(r[2], r[0]) for r in rows if r[5] == "DÉDUIT" and r[4] == "forme_imbriquee"}


def plancher_de_hasard(n_tirages=20):
    """FR: CORRECTION issue d'une revue independante — « l'accord doit s'effondrer » n'est pas
    une mesure : à 71%→62% on ne peut rien trancher. Le vrai témoin est un PLANCHER DE
    HASARD chiffré : mélanger les noms clairs `n_tirages` fois (seeds fixes 1..n),
    mesurer l'accord Jondo (comparer_jondo.mesurer) à chaque tirage, garder moyenne et
    max. Verdict : réel >> max(tirages) → le matcher mesure quelque chose (ratio donné) ;
    réel dans la plage des tirages → il ne mesure RIEN, même si le chiffre brut paraît
    élevé (les classes peuvent juste se ressembler toutes structurellement — mesuré :
    87% des noms de tête ont une forme triviale, cf. RAPPORT-MATCHER.md §4).
    EN: independent-review correction — "agreement must collapse" isn't a measurement (71%→62% can't be
    judged). The real witness is a numeric random FLOOR: shuffle clear names n times
    (fixed seeds), measure Jondo agreement each time, keep mean/max. real >> max(draws)
    → the matcher measures something; real within the draws' range → it measures
    NOTHING, even at a seemingly high raw percentage."""
    import comparer_jondo
    if not os.path.exists(comparer_jondo.JONDO_ANCLAS):
        return None
    jondo_rows = comparer_jondo.load_jondo()
    sig_by_name, clear_reel, _ = comparer_jondo.load_our_data()
    m_reel = comparer_jondo.mesurer(sig_by_name, clear_reel, jondo_rows)
    taux_reel, n_reel = m_reel["taux"], len(m_reel["with_match"])

    tirages = []
    for seed in range(1, n_tirages + 1):
        rng = random.Random(seed)
        clear_shuffle = json.loads(json.dumps(clear_reel))  # copie profonde, seed fixe
        shapes = [r["shape_signature"] for r in clear_shuffle]
        rng.shuffle(shapes)
        for r, s in zip(clear_shuffle, shapes):
            r["shape_signature"] = s
        m = comparer_jondo.mesurer(sig_by_name, clear_shuffle, jondo_rows)
        tirages.append(m["taux"])

    moyenne = sum(tirages) / len(tirages)
    maximum = max(tirages)
    mesure_qqch = taux_reel > maximum
    return {"taux_reel": taux_reel, "n_reel": n_reel, "tirages": tirages,
            "moyenne_hasard": moyenne, "max_hasard": maximum, "min_hasard": min(tirages),
            "mesure_quelque_chose": mesure_qqch,
            "ratio_reel_sur_max_hasard": (taux_reel / maximum) if maximum else float("inf")}


def run_epreuve():
    """--epreuve : 3 témoins.
    (1) PLANCHER DE HASARD (le témoin canonique, corrigé en revue indépendante) —
    voir `plancher_de_hasard()`. Verdict chiffré, pas un seuil arbitraire.
    (2) IDENTITÉ DES PAIRES (additionnel, sur le mécanisme du matcher lui-même, pas sur
    l'accord Jondo) — les paires PRÉCISES que le mélange produit doivent différer des
    vraies, pas seulement leur nombre (mesuré une fois : 2 paires avant, 2 après, par
    coïncidence, mais 0 recoupement — un comptage seul aurait donné un faux vert).
    (3) STABILITÉ — rejouer en SOUS-PROCESSUS SÉPARÉS avec des PYTHONHASHSEED différents
    (0 et 42), pas juste deux appels dans le même interpréteur (qui partagent le même
    seed de hachage et ne peuvent PAS révéler un non-déterminisme caché dans un ordre
    d'itération sur un `set`) → sha256 du TSV produit, doit être identique. Audit fait :
    les seuls `set()` du code (`comparer_jondo.py`) ne servent qu'à des tests
    d'appartenance (`in`, `&`, `|`) jamais à produire un ordre de sortie — mais on le
    PROUVE ici plutôt que de l'affirmer.
    EN: (1) numeric random floor (canonical witness, per the independent review's correction). (2) pair
    identity (checks the matcher's own mechanism, not Jondo agreement). (3) stability —
    replayed as SEPARATE SUBPROCESSES with different PYTHONHASHSEED (same-process reuse
    can't catch set-iteration-order bugs since hash seed is fixed per process)."""
    if not os.path.exists(SIG_PATH) or not os.path.exists(ATTENDUS_PATH):
        log("ABSENT : lance d'abord extraire_signatures.py et attendus_depuis_noms.py.")
        return 2
    ok = True

    log(f"=== témoin 1 : plancher de hasard sur {20} tirages (seeds 1..20) ===")
    floor = plancher_de_hasard(20)
    if floor is None:
        log("ABSENT : table Jondo introuvable — témoin 1 impossible.")
        ok = False
    else:
        log(f"réel : {floor['taux_reel']:.1%} (N={floor['n_reel']})")
        log(f"20 tirages : {[round(v, 4) for v in floor['tirages']]}")
        log(f"moyenne_hasard={floor['moyenne_hasard']:.1%}  max_hasard={floor['max_hasard']:.1%}  "
            f"min_hasard={floor['min_hasard']:.1%}")
        if floor["mesure_quelque_chose"]:
            print(f"✅ témoin 1 : réel ({floor['taux_reel']:.1%}) > max_hasard "
                  f"({floor['max_hasard']:.1%}) — le matcher mesure quelque chose, "
                  f"ratio réel/max_hasard = {floor['ratio_reel_sur_max_hasard']:.2f}")
        else:
            print(f"⚠️  témoin 1 : réel ({floor['taux_reel']:.1%}) DANS la plage du hasard "
                  f"[{floor['min_hasard']:.1%}, {floor['max_hasard']:.1%}] — la comparaison "
                  "élargie de comparer_jondo.py NE MESURE RIEN au-delà de la ressemblance "
                  "structurelle de base (87% des noms de tête ont une forme triviale) — "
                  "résultat honnête, pas un échec de l'épreuve elle-même.")
        # FR: ce témoin ne fait pas échouer l'épreuve — c'est une MESURE, pas un pass/fail ;
        # le verdict qu'il rend (mesure/ne mesure rien) EST le résultat à rapporter tel quel.

    log("=== témoin 2 : identité des paires — le mélange (seed=1234) doit produire des "
        "paires DIFFÉRENTES des vraies (pas seulement un nombre différent) ===")
    rows_reel, _ = run(out_path=os.path.join(HERE, "_epreuve_reel.tsv"))
    rows_shuffle, _ = run(out_path=os.path.join(HERE, "_epreuve_shuffle.tsv"), shuffle_seed=1234)
    p_reel, p_shuffle = top_pairs(rows_reel), top_pairs(rows_shuffle)
    overlap = p_reel & p_shuffle
    log(f"réel : {sorted(p_reel)}")
    log(f"mélangé : {sorted(p_shuffle)}")
    identite_ok = len(p_reel) > 0 and len(overlap) == 0
    print(f"{'✅' if identite_ok else '❌'} témoin 2 (identité des paires détruite par le mélange) : "
          f"{len(p_reel)} paire(s) réelle(s), {len(overlap)} qui survivent au mélange")
    ok &= identite_ok

    log("=== témoin 3 : STABILITÉ — 2 sous-processus, PYTHONHASHSEED différents (0 et 42) ===")
    import subprocess
    import shutil
    same = False
    try:
        for seed, dest in ((0, "_epreuve_hash0.tsv"), (42, "_epreuve_hash42.tsv")):
            env = dict(os.environ, PYTHONHASHSEED=str(seed))
            r = subprocess.run([sys.executable, os.path.join(HERE, "matcher.py")],
                                cwd=HERE, env=env, capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                log(f"[témoin 3] sous-processus PYTHONHASHSEED={seed} a échoué : {r.stderr[-500:]}")
                raise RuntimeError("sous-processus en échec")
            shutil.copyfile(OUT_TSV, os.path.join(HERE, dest))
        h1 = sha256_of(os.path.join(HERE, "_epreuve_hash0.tsv"))
        h2 = sha256_of(os.path.join(HERE, "_epreuve_hash42.tsv"))
        same = h1 == h2
        print(f"{'✅' if same else '❌'} témoin 3 (stabilité inter-processus, hash seeds différents) : "
              f"{h1[:12]}… vs {h2[:12]}… — {'identiques' if same else 'DIFFÉRENTS (bug de tri à trouver)'}")
    except Exception as e:
        log(f"[témoin 3] erreur : {e}")
        print("❌ témoin 3 (stabilité) : n'a pas pu s'exécuter")
    ok &= same

    for f in ("_epreuve_reel.tsv", "_epreuve_shuffle.tsv", "_epreuve_hash0.tsv", "_epreuve_hash42.tsv"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            os.remove(p)

    print(f"\n=== BILAN ÉPREUVE : {'MORD DANS LES DEUX SENS ✅' if ok else 'ÉCHEC ❌'} "
          "(le témoin 1 est une MESURE rapportée telle quelle, pas un critère pass/fail) ===")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
