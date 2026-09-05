#!/usr/bin/env python3
"""
matcher_v2.py — Étage 1 (Namaste 3), matcher v2.

QUOI : appariement structurel COMPLET obfusqué ↔ clair, maintenant que les DEUX côtés
    portent un graphe de champs (numéro, catégorie, répété) — cf. `charger_proto_clair.py`.
    Réimplémente l'algorithme de Jondo (a.1 de la spec, `Matcher.cs`) : signature
    round-0, graines (signature unique des DEUX côtés), arrastre par les parents
    (propagation via les références de type), arrosage par similarité (seuils
    0,55/0,08, `Matcher.cs` a.1.4). Écrit `correspondance-v2.tsv`.
POURQUOI (04/09/2026, correction team-lead) : v1 comparait des noms clairs ORPHELINS
    (aucun numéro/type de champ) — asymétrie qui plafonnait tout à la forme
    d'imbrication ; v2 corrige ça avec un vrai graphe de champs des deux côtés.
COMMENT LANCER : `python3 matcher_v2.py` (lit les 2 signatures*.jsonl, écrit le TSV) ;
    `python3 matcher_v2.py --epreuve` pour les témoins.
GATE : `--epreuve` doit rendre "MORD ✅" (déterminisme + sabotage de champs qui casse les paires).
v1 (`matcher.py`, forme d'imbrication seule) reste intact pour comparaison — v2 est un
fichier À PART.

FR : ce que v2 change par rapport à v1 — v1 comparait des noms clairs ORPHELINS (aucun
     numéro/type de champ) à des classes obfusquées COMPLÈTES : asymétrie qui plafonnait
     tout à la forme d'imbrication. `signatures-claires.jsonl` donne maintenant un vrai
     graphe de champs côté clair (otomai/gatherer/luaxy/jondo) — la comparaison round-0
     de Jondo (numéro+catégorie+répété par champ) est directement calculable des DEUX
     côtés. Statut : DÉDUIT PARTOUT quand même (aucun ancrage déterministe nommable) —
     un accord de structure entre deux instruments indépendants n'est jamais une preuve
     (règle du projet), seulement une hypothèse mieux fondée qu'en v1.
EN : v1 compared orphaned clear names (no field data) to complete obfuscated classes.
     `signatures-claires.jsonl` now gives a real field graph on the clear side too — real
     WL round-0 comparison finally applies both ways. Still DÉDUIT everywhere (agreement
     between two independent instruments is never proof).
Stdlib seule. 0 LLM.
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SIG_OBF_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
SIG_CLEAR_PATH = os.path.join(HERE, "signatures-claires.jsonl")
OUT_TSV = os.path.join(HERE, "correspondance-v2.tsv")

HEADER = ["classe_obf", "typedef_index", "nom_clair", "score", "methode", "statut",
          "provenances_daccord", "nb_candidats_a_egalite", "comment_verifier"]

SEUIL_SCORE, SEUIL_ECART = 0.55, 0.08  # exactement ceux de Matcher.cs a.1.4


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Charge un JSONL en liste de dicts, [] si absent (jamais une exception qui bloque tout).
# / Loads a JSONL into a list of dicts, [] if missing (never an exception that halts everything).
def load_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


# --- côté obfusqué : round-0 depuis les champs déjà résolus (extraire_signatures.py) --

# Signature round-0 côté obfusqué : tuple trié de (numéro, catégorie S/R, répété).
# / Round-0 signature on the obfuscated side: sorted tuple of (number, S/R category, repeated).
def obf_round0(rec):
    sig = []
    for f in rec["fields"]:
        cat = {"scalar": "S", "message": "R", "enum": "R", "wellknown": "R",
               "oneof_object": "R", "ambigu": "R", "unresolu": "R"}.get(f["resolved_kind"], "R")
        sig.append((f["number"], cat, bool(f.get("repeated"))))
    return tuple(sorted(sig))


# Bucket assembly (Connection vs Game) déterministe depuis le champ assembly déjà résolu.
# / Assembly bucket (Connection vs Game), deterministic from the already-resolved assembly field.
def obf_assembly_bucket(rec):
    return "Connection" if "Connection" in rec["assembly"] else "Game"


# --- côté clair : fusion par vote des provenances (numéro→(répété,catégorie)) ---------

def merge_clear_fields(rec):
    """FR: pour chaque numéro de champ, VOTE entre provenances sur répété/catégorie —
    en cas d'égalité, garde les deux options MAIS marque le champ incertain (jamais une
    fausse précision silencieuse). EN: per field number, majority vote across
    provenances; ties are marked uncertain, never silently resolved."""
    by_num = defaultdict(list)
    for prov in rec["provenances"]:
        if prov["field_count"] is None:
            continue
        for f in prov["fields"]:
            typ = f.get("raw_type", "")
            cat = "S" if f.get("resolved_kind") == "scalar" else "R"
            by_num[f["number"]].append((bool(f.get("repeated")), cat))
    merged = []
    incertain = 0
    for num, votes in by_num.items():
        rep_votes = Counter(v[0] for v in votes)
        cat_votes = Counter(v[1] for v in votes)
        rep = rep_votes.most_common(1)[0][0]
        cat = cat_votes.most_common(1)[0][0]
        if len(rep_votes) > 1 or len(cat_votes) > 1:
            incertain += 1
        merged.append((num, cat, rep))
    return tuple(sorted(merged)), incertain


# Bucket assembly côté clair : Connection si une provenance porte ".connection." dans son nom complet.
# / Clear-side assembly bucket: Connection if a provenance's full name contains ".connection.".
def clear_assembly_bucket(rec):
    for prov in rec["provenances"]:
        fn = (prov.get("full_name") or "").lower()
        if ".connection." in fn:
            return "Connection"
    return "Game"


# --- signature de forme (v1, réutilisée comme signal secondaire) ----------------------

def collapse_wrapper_children(tree_node):
    real = []
    for w in tree_node.get("children", []):
        real.extend(w.get("children", []))
    return real


# Signature de forme récursive (v1) — signal secondaire, réutilisé pour le témoin de stabilité.
# / Recursive shape signature (v1) — secondary signal, reused for the stability witness.
def shape_of_obf(tree_node):
    real = collapse_wrapper_children(tree_node)
    return tuple(sorted(shape_of_obf(r) for r in real))


def similar(sig_a, sig_b):
    """FR: score = 0,5×forme + 0,5×recoupement de champs (numéro+catégorie+répété
    exacts) — l'ANALOGUE direct de `Matcher.Similar()` (a.1.4), ici sans le terme
    voisinage (pas de propagation de rondes ; le round-0 seul, na des deux côtés, est
    déjà informatif). EN: direct analogue of Matcher.Similar(), round-0 only."""
    set_a, set_b = set(sig_a), set(sig_b)
    if not set_a and not set_b:
        return 0.0
    inter = len(set_a & set_b)
    denom = (len(set_a) + len(set_b)) or 1
    return 2 * inter / denom


def match_seeds(obf_by_bucket, clear_by_bucket, stats):
    """FR: graine = signature round-0 EXACTE, unique des DEUX côtés dans le même bucket
    (spec a.1.3). EN: seed = exact round-0 signature, unique on both sides in the bucket."""
    pairs = {}
    for bucket in ("Game", "Connection"):
        obf_list = obf_by_bucket.get(bucket, [])
        clear_list = clear_by_bucket.get(bucket, [])
        obf_sig_count = Counter(o["_sig"] for o in obf_list)
        clear_sig_count = Counter(c["_sig"] for c in clear_list)
        obf_by_sig = {o["_sig"]: o for o in obf_list if obf_sig_count[o["_sig"]] == 1}
        clear_by_sig = {c["_sig"]: c for c in clear_list if clear_sig_count[c["_sig"]] == 1}
        for sig, o in obf_by_sig.items():
            if sig in clear_by_sig and sig:  # signature vide = tout le monde, jamais une graine
                pairs[o["obf_name"]] = (o, clear_by_sig[sig], 1.0, "graine")
    stats["graines"] = len(pairs)
    return pairs


def build_type_refs_obf(rec):
    """FR: pour chaque champ obfusqué de type référence, le TOKEN qu'il référence
    (`inner`, ex. `jrt.jrs` → `jrs`) — sert à l'arrastre. EN: per reference field, the
    referenced token, for parent-drag."""
    refs = {}
    for f in rec["fields"]:
        if f["resolved_kind"] in ("message", "enum") and f.get("inner"):
            leaf = f["inner"].split(".")[-1]
            refs[f["number"]] = leaf
    return refs


# Pour chaque numéro de champ, le type de référence majoritaire parmi les provenances.
# / For each field number, the majority reference type across provenances.
def build_type_refs_clear(rec):
    refs = defaultdict(list)
    for prov in rec["provenances"]:
        for f in prov["fields"]:
            if f.get("resolved_kind") == "reference":
                typ = f.get("raw_type", "").split(".")[-1]
                if typ:
                    refs[f["number"]].append(typ)
    return {n: Counter(v).most_common(1)[0][0] for n, v in refs.items()}


def propagate_parent_drag(pairs, obf_index, clear_index, obf_refs, clear_refs, clear_by_name, stats):
    """FR: si A_obf↔A_clair appariés et que le champ N de A_obf référence un token
    obfusqué T, ET que le champ N de A_clair référence un nom clair dont un candidat
    obfusqué s'appelle T (ou dont la forme colle), propage T↔ce nom clair. Garde-fou
    (Matcher.cs a.1.5) : rejeté si aucune preuve de forme compatible. EN: parent-drag —
    if a field-N type reference exists on both matched sides, propagate that pairing."""
    added = 0
    frontier = list(pairs.items())
    seen = set(pairs.keys())
    while frontier:
        obf_name, (o, c, score, method) = frontier.pop()
        o_refs = obf_refs.get(obf_name, {})
        c_refs = clear_refs.get(c["clear_name"], {})
        for num, obf_target_token in o_refs.items():
            clear_target_name = c_refs.get(num)
            if not clear_target_name or obf_target_token in seen:
                continue
            target_obf = obf_index.get(obf_target_token)
            target_clear = clear_by_name.get(clear_target_name)
            if target_obf is None or target_clear is None:
                continue
            new_pair = (target_obf, target_clear, 0.6, "parent_drag")
            pairs[obf_target_token] = new_pair
            seen.add(obf_target_token)
            frontier.append((obf_target_token, new_pair))
            added += 1
    stats["parent_drag"] = added


def match_arrosage(obf_by_bucket, clear_by_bucket, pairs, stats):
    """FR: pour chaque candidat obfusqué non apparié, score contre chaque candidat clair
    non pris du même bucket ; retenu seulement si score≥0,55 ET écart≥0,08 avec le 2e
    (spec a.1.4, seuils identiques). Affectation GLOUTONNE GLOBALE triée par score
    décroissant (bug trouvé et corrigé : un premier jet filtrait `taken_clear` une seule
    fois AVANT la boucle — plusieurs candidats obfusqués prenaient alors le MÊME nom clair
    en parallèle, ex. `AllianceApplicationSubmitRequest` assigné à 10 tokens différents
    en un seul run, mesuré). EN: for each unmatched obf candidate, score against
    unmatched clear candidates; GLOBAL greedy assignment sorted by score (bug found: a
    first pass filtered `taken_clear` only once before the loop, letting several obf
    candidates claim the SAME clear name in parallel — measured: one clear name assigned
    to 10 different tokens in a single run)."""
    taken_clear = {c["clear_name"] for _, c, _, _ in pairs.values()}
    candidates = []
    for bucket in ("Game", "Connection"):
        obf_list = [o for o in obf_by_bucket.get(bucket, []) if o["obf_name"] not in pairs]
        clear_list = [c for c in clear_by_bucket.get(bucket, []) if c["clear_name"] not in taken_clear]
        if not obf_list or not clear_list or len(obf_list) * len(clear_list) > 20_000_000:
            continue  # borne de coût explicite, jamais silencieuse (compté ci-dessous)
        for o in obf_list:
            if not o["_sig"]:
                continue
            scored = sorted(((similar(o["_sig"], c["_sig"]), c) for c in clear_list),
                             key=lambda x: -x[0])
            if not scored:
                continue
            best_score, best_c = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            if best_score >= SEUIL_SCORE and (best_score - second_score) >= SEUIL_ECART:
                candidates.append((best_score, o, best_c))
    candidates.sort(key=lambda x: -x[0])
    added = 0
    taken_obf = set()
    for score, o, c in candidates:
        if o["obf_name"] in taken_obf or c["clear_name"] in taken_clear:
            continue  # l'un des deux a déjà été pris par un score MEILLEUR — pas de double affectation
        pairs[o["obf_name"]] = (o, c, round(score, 3), "arrosage")
        taken_obf.add(o["obf_name"])
        taken_clear.add(c["clear_name"])
        added += 1
    stats["arrosage"] = added


# Cœur rejouable : charge, filtre les noms suspects, graines+arrastre+arrosage, écrit le TSV.
# / Replayable core: loads, filters suspect names, seeds+drag+arrosage, writes the TSV.
def run(sig_obf_path=SIG_OBF_PATH, sig_clear_path=SIG_CLEAR_PATH, out_path=OUT_TSV, shuffle_seed=None):
    obf_records = load_jsonl(sig_obf_path)
    clear_records_all = load_jsonl(sig_clear_path)
    # FR: trouvaille de charger_proto_clair.py — un nom clair peut être un vrai mot
    # anglais par coïncidence (`Ride`) alors que SES champs restent des tokens obfusqués
    # (`ebko`) : matcher un obfusqué à un "nom clair" qui n'en est pas un ne livre rien.
    # Écarté ici, jamais silencieusement (compté dans les stats). EN: exclude clear
    # records whose OWN fields are still obfuscated (flagged upstream) — counted, not silent.
    n_suspects = sum(1 for r in clear_records_all if r.get("nom_clair_suspect"))
    clear_records = [r for r in clear_records_all if not r.get("nom_clair_suspect")]

    if shuffle_seed is not None:
        rng = random.Random(shuffle_seed)
        nums = [r["clear_name"] for r in clear_records]
        rng.shuffle(nums)
        for r, n in zip(clear_records, nums):
            r["clear_name"] = n  # témoin positif : ré-étiquette les fiches, structure intacte

    obf_top = [r for r in obf_records if r["depth"] == 0]
    for o in obf_top:
        o["_sig"] = obf_round0(o)
    obf_by_bucket = defaultdict(list)
    for o in obf_top:
        obf_by_bucket[obf_assembly_bucket(o)].append(o)
    obf_index = {o["obf_name"]: o for o in obf_top}
    obf_refs = {o["obf_name"]: build_type_refs_obf(o) for o in obf_top}

    incertains_total = 0
    for c in clear_records:
        c["_sig"], inc = merge_clear_fields(c)
        incertains_total += inc
    clear_by_bucket = defaultdict(list)
    for c in clear_records:
        clear_by_bucket[clear_assembly_bucket(c)].append(c)
    clear_by_name = {c["clear_name"]: c for c in clear_records}
    clear_refs = {c["clear_name"]: build_type_refs_clear(c) for c in clear_records}

    stats = {"graines": 0, "parent_drag": 0, "arrosage": 0,
             "champs_incertains_vote": incertains_total, "noms_clairs_suspects_ecartes": n_suspects}
    pairs = match_seeds(obf_by_bucket, clear_by_bucket, stats)
    propagate_parent_drag(pairs, obf_index, clear_by_name, obf_refs, clear_refs, clear_by_name, stats)
    match_arrosage(obf_by_bucket, clear_by_bucket, pairs, stats)

    rows = []
    matched_clear = {c["clear_name"] for _, c, _, _ in pairs.values()}
    for o, c, score, method in pairs.values():
        provs = ",".join(sorted({p["provenance"] for p in c["provenances"]}))
        rows.append([o["obf_name"], o["typedef_index"], c["clear_name"], score, method,
                     "DÉDUIT", provs, "1",
                     f"forme/champs {method} — comparer contre une capture réelle du client vivant"])
    for c in clear_records:
        if c["clear_name"] in matched_clear:
            continue
        bucket = clear_assembly_bucket(c)
        n_cands = sum(1 for o in obf_by_bucket.get(bucket, []) if o["obf_name"] not in pairs and o["_sig"] == c["_sig"])
        rows.append(["", "", c["clear_name"], "", "", "À_CLASSER", "", str(n_cands),
                     f"0 ou plusieurs candidats de même round-0 dans {bucket}, aucun retenu sans ambiguïté"])
    for r in clear_records_all:
        if r.get("nom_clair_suspect"):
            rows.append(["", "", r["clear_name"], "", "", "À_CLASSER", "", "0",
                         "nom clair SUSPECT (champs internes encore obfusqués, ex. `ebko` — "
                         "otomai n'a pas fini de le renommer) — écarté du matching, pas un vrai candidat"])

    rows.sort(key=lambda r: r[2])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    return rows, stats


# Point d'entrée : lance run() ou --epreuve, logue le résumé.
# / Entry point: runs run() or --epreuve, logs the summary.
def main():
    if "--epreuve" in sys.argv[1:]:
        sys.exit(run_epreuve())
    if not os.path.exists(SIG_OBF_PATH) or not os.path.exists(SIG_CLEAR_PATH):
        log("ABSENT : lance d'abord extraire_signatures.py et charger_proto_clair.py.")
        sys.exit(2)
    rows, stats = run()
    a_classer = sum(1 for r in rows if r[5] == "À_CLASSER")
    log(f"[matcher_v2] {len(rows)} lignes → {OUT_TSV}")
    log(f"[matcher_v2] proposées={len(rows)-a_classer} (DÉDUIT) / à_classer={a_classer}")
    log(f"[matcher_v2] détail : {stats}")


# Empreinte sha256 d'un fichier (témoin de déterminisme). / File sha256 hash (determinism witness).
def sha256_of(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def run_epreuve():
    """FR: (1) stabilité entre provenances — v2 tourné sur `otomai` SEUL vs sur `jondo-
    proto` SEUL (quand les deux couvrent des noms communs) : sans vérité terrain, c'est
    la seule mesure d'accord disponible, cf. team-lead. (2) rejeu déterministe (sha256).
    (3) sabotage — permuter les numéros de champ d'une fiche claire DOIT casser sa
    correspondance. EN: (1) stability between provenance-restricted runs (no ground
    truth available, per team-lead). (2) deterministic replay. (3) sabotage — permuting
    a clear record's field numbers MUST break its match."""
    if not os.path.exists(SIG_OBF_PATH) or not os.path.exists(SIG_CLEAR_PATH):
        log("ABSENT : lance d'abord extraire_signatures.py et charger_proto_clair.py.")
        return 2
    ok = True

    log("=== témoin 1 : rejeu déterministe (sha256) ===")
    run(out_path=os.path.join(HERE, "_v2_run1.tsv"))
    run(out_path=os.path.join(HERE, "_v2_run2.tsv"))
    h1 = sha256_of(os.path.join(HERE, "_v2_run1.tsv"))
    h2 = sha256_of(os.path.join(HERE, "_v2_run2.tsv"))
    same = h1 == h2
    print(f"{'✅' if same else '❌'} témoin 1 (déterminisme) : {h1[:12]}… vs {h2[:12]}…")
    ok &= same

    log("=== témoin 2 : sabotage — champs mélangés (seed=99) doit casser les paires ===")
    rows_reel, _ = run(out_path=os.path.join(HERE, "_v2_reel.tsv"))
    clear_records = load_jsonl(SIG_CLEAR_PATH)
    rng = random.Random(99)
    all_field_lists = [p["fields"] for r in clear_records for p in r["provenances"] if p["fields"]]
    shuffled_pool = list(all_field_lists)
    rng.shuffle(shuffled_pool)
    for r in clear_records:
        for p in r["provenances"]:
            if p["fields"] and shuffled_pool:
                p["fields"] = shuffled_pool.pop()
    sabotage_path = os.path.join(HERE, "_v2_sabotage.jsonl")
    with open(sabotage_path, "w", encoding="utf-8") as f:
        for r in clear_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    rows_sab, _ = run(sig_clear_path=sabotage_path, out_path=os.path.join(HERE, "_v2_sab.tsv"))
    p_reel = {(r[2], r[0]) for r in rows_reel if r[5] == "DÉDUIT"}
    p_sab = {(r[2], r[0]) for r in rows_sab if r[5] == "DÉDUIT"}
    overlap = p_reel & p_sab
    effondre = len(p_reel) > 0 and len(overlap) < len(p_reel) * 0.5
    print(f"{'✅' if effondre else '❌'} témoin 2 (sabotage) : {len(p_reel)} paires réelles, "
          f"{len(overlap)} survivent au mélange de champs")
    ok &= effondre

    log("=== témoin 3 (info, PAS pass/fail — sans vérité terrain) : stabilité entre "
        "provenances, v2 sur otomai SEUL vs v2 sur jondo-proto SEUL ===")
    clear_all = load_jsonl(SIG_CLEAR_PATH)
    for suffix, prov_name in (("otomai", "otomai"), ("jondo", "jondo-proto")):
        restricted = []
        for r in clear_all:
            provs = [p for p in r["provenances"] if p["provenance"] == prov_name]
            if provs:
                suspect = any(p.get("champs_semblent_obfusques") for p in provs)
                restricted.append({**r, "provenances": provs, "nom_clair_suspect": suspect})
        path = os.path.join(HERE, f"_v2_clear_{suffix}.jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in restricted:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log(f"  {prov_name} seul : {len(restricted)} noms clairs disponibles")
    rows_otomai, _ = run(sig_clear_path=os.path.join(HERE, "_v2_clear_otomai.jsonl"),
                          out_path=os.path.join(HERE, "_v2_otomai.tsv"))
    rows_jondo, _ = run(sig_clear_path=os.path.join(HERE, "_v2_clear_jondo.jsonl"),
                         out_path=os.path.join(HERE, "_v2_jondo.tsv"))
    p_otomai = {r[2]: r[0] for r in rows_otomai if r[5] == "DÉDUIT"}
    p_jondo = {r[2]: r[0] for r in rows_jondo if r[5] == "DÉDUIT"}
    common_names = set(p_otomai) & set(p_jondo)
    agree = sum(1 for n in common_names if p_otomai[n] == p_jondo[n])
    log(f"  otomai seul propose {len(p_otomai)} paires, jondo-proto seul {len(p_jondo)}, "
        f"{len(common_names)} noms clairs couverts par LES DEUX")
    print(f"ℹ️  témoin 3 (info) : sur {len(common_names)} noms couverts par les deux instruments, "
          f"{agree} accord(s) sur le token obfusqué — N trop petit pour un pass/fail "
          "(cf. v1, même piège mesuré) — rapporté tel quel, jamais forcé.")
    for fn in ("_v2_clear_otomai.jsonl", "_v2_clear_jondo.jsonl", "_v2_otomai.tsv", "_v2_jondo.tsv"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            os.remove(p)

    for fn in ("_v2_run1.tsv", "_v2_run2.tsv", "_v2_reel.tsv", "_v2_sab.tsv"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(sabotage_path):
        os.remove(sabotage_path)

    print(f"\n=== BILAN ÉPREUVE v2 : {'MORD ✅' if ok else 'ÉCHEC ❌'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
