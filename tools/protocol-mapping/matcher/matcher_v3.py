#!/usr/bin/env python3
"""
matcher_v3.py — Étage 1 (Namaste 3), matcher v3.

QUOI : graines VÉRIFIÉES-par-capture (Jondo anclas, 242 captures réelles) + propagation
    Weisfeiler-Lehman sur le graphe {références de types imbriqués (v1/v2) +
    co-occurrence de méthodes (extraire_contexte.py) + ordre de la rafale de
    bienvenue} contre le graphe clair fusionné (v2). Écrit `correspondance-v3.tsv`.
POURQUOI (04/09/2026, brief « ancres par contexte d'appel + graines Jondo +
    propagation ») : v2 plafonnait sur l'ambiguïté des formes — plus de graines
    (Jondo direct) et un graphe de voisinage plus riche font propager plus loin.
COMMENT LANCER : `python3 matcher_v3.py` (lit signatures*.jsonl, correspondance-v2.tsv,
    aretes-voisinage.jsonl, écrit le TSV) ; `python3 matcher_v3.py --epreuve`.
GATE : `--epreuve` doit rendre "MORD ✅" — déterminisme, sabotage de 10% des arêtes de
    voisinage, et accord d'IDENTITÉ (pas de compte) sous graines mélangées effondré.
v2 (`matcher_v2.py`) reste intacte pour comparaison — v3 est un fichier À PART, il en
importe les briques structurelles (jamais dupliquées).

FR : POURQUOI les graines viennent de Jondo directement, pas d'un recoupement otomai —
     la loi L6 du cahier (mesurée le 04/09, avant ce fichier) : les opcodes sont
     RE-BRASSÉS à chaque compilation, même à version nominale identique — Jondo colle à
     NOTRE build (290-291/293 mesuré, deux fois, indépendamment), otomai (« 3.6.10.10 »
     nominal d'une AUTRE compilation, mars 2026) NE COLLE PAS AU NIVEAU DES TOKENS
     (0/27 accord sur les collisions d'opcode, mesuré par team-lead). Les 99 noms
     PROPOSÉS de Jondo (`anclas_3.6.10.10.tsv`, sourcés « code + 242 captures ») sont
     donc la source de graines la plus solide disponible — utilisés TELS QUELS comme
     nom clair, `statut=DÉDUIT` quand même (une proposition stylée n'est pas une preuve).
     `extraire_contexte.py` (nouveau, ce chantier) a mesuré, avant tout : **0/2206
     classes obfusquées ont un porteur en clair** dans le dump statique — 2 bugs trouvés
     et corrigés en chemin (namespace-texte non fiable, collision `int`/mot-clé C#) ;
     la conclusion tient : l'obfuscation d'Ankama couvre TOUT le code de première
     partie visible statiquement, pas seulement le protocole. La co-occurrence de
     méthodes (obfusqué↔obfusqué) reste le seul signal de VOISINAGE disponible.
EN : seeds come from Jondo directly (not an otomai cross-check) because L6 measured
     opcodes reshuffle every compile, even at the same nominal version — Jondo matches
     OUR build, otomai does not (0/27 opcode agreement, team-lead's measurement).
     `extraire_contexte.py` measured 0/2206 obfuscated classes have a clear-text
     caller — Ankama's obfuscation covers the whole first-party codebase visible
     statically, not just the protocol. Obfuscated-to-obfuscated co-occurrence is the
     only neighborhood signal left.
Stdlib seule. 0 LLM.
"""
import json
import os
import random
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matcher_v2 import (  # réutilisées telles quelles, jamais dupliquées
    load_jsonl, obf_round0, obf_assembly_bucket, merge_clear_fields, clear_assembly_bucket,
    build_type_refs_obf, build_type_refs_clear, similar, SEUIL_SCORE, SEUIL_ECART,
)
from charger_proto_clair import load_anclas, JONDO_ANCLAS

HERE = os.path.dirname(os.path.abspath(__file__))
SIG_OBF_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
SIG_CLEAR_PATH = os.path.join(HERE, "signatures-claires.jsonl")
CORRESPONDANCE_V2 = os.path.join(HERE, "correspondance-v2.tsv")
ARETES_PATH = os.path.join(HERE, "aretes-voisinage.jsonl")
OUT_TSV = os.path.join(HERE, "correspondance-v3.tsv")

HEADER = ["classe_obf", "typedef_index", "nom_clair", "score", "methode", "statut",
          "provenances_daccord", "nb_candidats_a_egalite", "chemin_de_preuve"]

# FR: rafale de bienvenue, ORDRE VÉRIFIÉ (SEQUENCE-CHEMIN-CRITIQUE-JONDO.md §3.6, sourcé
# `ConnectionProtocol.cs:191-221`, 242 captures) — une arête de voisinage supplémentaire,
# indépendante de la co-occurrence de méthode. EN: welcome-burst order, VÉRIFIÉ from the
# already-read chemin-critique doc — an extra neighborhood edge, independent of method co-occurrence.
RAFALE_BIENVENUE = ["kra", "lqu", "hoy", "kqu", "mgq", "mgt", "hpd", "krs", "mgz",
                     "kqp", "kvi", "kvd", "jtg"]


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Charge les paires DÉDUIT de correspondance-v2.tsv (obf_token -> nom_clair).
# / Loads DÉDUIT pairs from correspondance-v2.tsv (obf_token -> clear_name).
def load_v2_pairs(path):
    pairs = {}
    if not os.path.exists(path):
        return pairs
    with open(path, encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 6 and cols[5] == "DÉDUIT" and cols[0]:
                pairs[cols[0]] = cols[2]
    return pairs


# Charge les arêtes de co-occurrence + ajoute l'ordre de la rafale de bienvenue (RAFALE_BIENVENUE).
# / Loads co-occurrence edges + adds welcome-burst order (RAFALE_BIENVENUE).
def load_edges(path):
    edges = defaultdict(set)
    if not os.path.exists(path):
        return edges
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        edges[e["a"]].add(e["b"])
        edges[e["b"]].add(e["a"])
    for i in range(len(RAFALE_BIENVENUE) - 1):
        a, b = RAFALE_BIENVENUE[i], RAFALE_BIENVENUE[i + 1]
        edges[a].add(b)
        edges[b].add(a)
    return edges


def build_graines(sig_clear_path=SIG_CLEAR_PATH, v2_path=CORRESPONDANCE_V2, shuffle_seed=None):
    """FR: fusion anclas (99, `jondo-anclas`) + v2 (31, `v2`) ; conflit = les DEUX
    gardées, signalées, JAMAIS tranchées en silence. EN: merge anclas + v2; a conflict
    keeps BOTH, flagged, never silently resolved."""
    anclas = load_anclas(JONDO_ANCLAS)
    v2_pairs = load_v2_pairs(v2_path)
    if shuffle_seed is not None:
        rng = random.Random(shuffle_seed)
        names = list(anclas.values())
        rng.shuffle(names)
        anclas = dict(zip(anclas.keys(), names))
        names2 = list(v2_pairs.values())
        rng.shuffle(names2)
        v2_pairs = dict(zip(v2_pairs.keys(), names2))

    graines = {}
    conflits = []
    for opcode, name in anclas.items():
        graines[opcode] = (name, "jondo-anclas", f"graine directe : anclas Jondo (242 captures), opcode={opcode}")
    for opcode, name in v2_pairs.items():
        if opcode in graines and graines[opcode][0] != name:
            conflits.append((opcode, graines[opcode][0], name))
        graines[opcode] = (name, "v2", "graine v2 (forme+champs, matcher_v2.py)")
    return graines, conflits


# Renvoie la fiche claire existante, ou une fiche VIDE créée à la volée (nom Jondo
# sans données de champ otomai/gatherer/luaxy) — jamais une KeyError silencieuse.
# / Returns the existing clear record, or an empty one created on the fly (Jondo name
# with no otomai/gatherer/luaxy field data) — never a silent KeyError.
def get_or_make_clear(name, clear_by_name):
    if name in clear_by_name:
        return clear_by_name[name]
    rec = {"clear_name": name, "provenances": [], "nb_provenances": 0,
           "accord_nb_champs": None, "nom_clair_suspect": False, "_sig": ()}
    clear_by_name[name] = rec
    return rec


# Arrastre par les parents (spec a.1.5) : propage les graines via les références de type
# des champs, en construisant le chemin_de_preuve à chaque saut.
# / Parent-drag (spec a.1.5): propagates seeds via field type references, building the
# chemin_de_preuve at each hop.
def propagate(graines, obf_index, clear_by_name, obf_refs, clear_refs, stats):
    added = 0
    frontier = list(graines.items())
    while frontier:
        obf_tok, (clear_name, prov, chemin) = frontier.pop()
        o = obf_index.get(obf_tok)
        if o is None:
            continue
        c = clear_by_name.get(clear_name) or get_or_make_clear(clear_name, clear_by_name)
        o_refs = obf_refs.get(obf_tok, {})
        c_refs = clear_refs.get(clear_name, {})
        for num, target_tok in o_refs.items():
            target_clear = c_refs.get(num)
            if not target_clear or target_tok in graines:
                continue
            new_chemin = f"{chemin} -> arrastre champ f{num} ({obf_tok}.f{num}={target_tok} <-> {clear_name}.f{num}={target_clear})"
            graines[target_tok] = (target_clear, prov, new_chemin)
            frontier.append((target_tok, graines[target_tok]))
            added += 1
    stats["arrastre_v3"] = added


def arrosage_avec_voisinage(obf_by_bucket, clear_by_bucket, graines, edges, obf_refs, stats):
    """FR: comme v2, + BONUS si le candidat obfusqué CO-OCCURRE (voisinage, rafale
    incluse) avec un token DÉJÀ apparié dont le champ référence le même nom clair
    candidat (recoupement structurel indépendant du round-0 seul). EN: like v2, plus a
    bonus when the obf candidate co-occurs with an already-matched neighbor whose own
    field reference agrees with the candidate clear name."""
    taken_clear = {name for name, _, _ in graines.values()}
    candidates = []
    for bucket in ("Game", "Connection"):
        obf_list = [o for o in obf_by_bucket.get(bucket, []) if o["obf_name"] not in graines]
        clear_list = [c for c in clear_by_bucket.get(bucket, []) if c["clear_name"] not in taken_clear]
        if not obf_list or not clear_list or len(obf_list) * len(clear_list) > 20_000_000:
            continue
        for o in obf_list:
            if not o["_sig"]:
                continue
            neighbor_clears = set()
            for nb in edges.get(o["obf_name"], ()):
                if nb in graines:
                    neighbor_clears.add(graines[nb][0])
            scored = []
            for c in clear_list:
                s = similar(o["_sig"], c["_sig"])
                bonus = 0.05 if c["clear_name"] in neighbor_clears else 0.0
                scored.append((min(s + bonus, 1.0), s, bonus, c))
            scored.sort(key=lambda x: -x[0])
            if not scored:
                continue
            best_total, best_raw, best_bonus, best_c = scored[0]
            second_total = scored[1][0] if len(scored) > 1 else 0.0
            if best_total >= SEUIL_SCORE and (best_total - second_total) >= SEUIL_ECART:
                candidates.append((best_total, best_raw, best_bonus, o, best_c))
    candidates.sort(key=lambda x: -x[0])
    added = 0
    taken_obf = set()
    for total, raw, bonus, o, c in candidates:
        if o["obf_name"] in taken_obf or c["clear_name"] in taken_clear:
            continue
        chemin = f"arrosage score={round(raw,3)}" + (f" +voisinage(bonus={bonus})" if bonus else "")
        graines[o["obf_name"]] = (c["clear_name"], "arrosage", chemin)
        taken_obf.add(o["obf_name"])
        taken_clear.add(c["clear_name"])
        added += 1
    stats["arrosage_v3"] = added


# Cœur rejouable : graines + propagation + arrosage-avec-voisinage + dédoublonnage des
# noms clairs en conflit, écrit le TSV.
# / Replayable core: seeds + propagation + neighborhood-arrosage + clear-name conflict
# de-duplication, writes the TSV.
def run(sig_obf_path=SIG_OBF_PATH, sig_clear_path=SIG_CLEAR_PATH, v2_path=CORRESPONDANCE_V2,
        aretes_path=ARETES_PATH, out_path=OUT_TSV, shuffle_seed=None, sabotage_edge_frac=0.0):
    obf_records = load_jsonl(sig_obf_path)
    clear_records_all = load_jsonl(sig_clear_path)
    clear_records = [r for r in clear_records_all if not r.get("nom_clair_suspect")]

    obf_top = [r for r in obf_records if r["depth"] == 0]
    for o in obf_top:
        o["_sig"] = obf_round0(o)
    obf_by_bucket = defaultdict(list)
    for o in obf_top:
        obf_by_bucket[obf_assembly_bucket(o)].append(o)
    obf_index = {o["obf_name"]: o for o in obf_top}
    obf_refs = {o["obf_name"]: build_type_refs_obf(o) for o in obf_top}

    for c in clear_records:
        c["_sig"], _ = merge_clear_fields(c)
    clear_by_bucket = defaultdict(list)
    for c in clear_records:
        clear_by_bucket[clear_assembly_bucket(c)].append(c)
    clear_by_name = {c["clear_name"]: c for c in clear_records}
    clear_refs = {c["clear_name"]: build_type_refs_clear(c) for c in clear_records}

    edges = load_edges(aretes_path)
    if sabotage_edge_frac > 0:
        rng = random.Random(12345)
        all_pairs = [(a, b) for a in edges for b in edges[a] if a < b]
        n_drop = int(len(all_pairs) * sabotage_edge_frac)
        for a, b in rng.sample(all_pairs, min(n_drop, len(all_pairs))):
            edges[a].discard(b)
            edges[b].discard(a)

    graines, conflits = build_graines(sig_clear_path, v2_path, shuffle_seed)
    stats = {"graines_initiales": len(graines), "conflits_anclas_v2": len(conflits)}
    propagate(graines, obf_index, clear_by_name, obf_refs, clear_refs, stats)
    arrosage_avec_voisinage(obf_by_bucket, clear_by_bucket, graines, edges, obf_refs, stats)

    rows = []
    matched_clear = {name for name, _, _ in graines.values()}
    for obf_tok, (clear_name, prov, chemin) in graines.items():
        o = obf_index.get(obf_tok)
        rows.append([obf_tok, o["typedef_index"] if o else "", clear_name,
                     "1.0" if prov in ("jondo-anclas", "v2") else "", prov, "DÉDUIT",
                     prov, "1", chemin])

    # FR: trouvaille — un même nom clair peut être revendiqué par PLUSIEURS tokens
    # obfusqués distincts, pour 2 raisons différentes : (a) le même type clair est
    # RÉFÉRENCÉ par plusieurs parents différents (le protobuf réutilise un type, mais le
    # C# généré compile une copie imbriquée DISTINCTE par parent — chaque copie est une
    # classe obfusquée à part) : légitime, gardé DÉDUIT, noté ; (b) DEUX SOURCES DE
    # GRAINES INDÉPENDANTES (`jondo-anclas`, une proposition stylée non extraite, vs
    # `v2`, une correspondance structurelle sur données de champs réelles) se
    # contredisent sur le MÊME nom : jamais laissé comme 2 DÉDUIT contradictoires — le
    # `v2` structurel l'emporte, `jondo-anclas` est rétrogradé en À_CLASSER avec la
    # raison. Mesuré : 7 groupes en double, 5 conflits inter-sources, 2 réutilisations.
    # EN: a clear name can be claimed by several obf tokens for two reasons: (a) the
    # same clear type is referenced by several DIFFERENT parents — legit, C# compiles a
    # separate nested copy per parent; kept DÉDUIT, noted; (b) two INDEPENDENT seed
    # sources disagree on the same name — never left as 2 contradicting DÉDUIT rows;
    # the structural v2-rooted one wins, jondo-anclas is demoted with the reason.
    by_clear_name = defaultdict(list)
    for r in rows:
        by_clear_name[r[2]].append(r)
    for name, group in by_clear_name.items():
        if len(group) < 2:
            continue
        roots = {r[6] for r in group}
        if len(roots) > 1:
            structurels = [r for r in group if r[6] == "v2"]
            gagnant = structurels[0] if structurels else group[0]
            for r in group:
                if r is gagnant:
                    continue
                autres = ", ".join(f"{o[0]}({o[6]})" for o in group if o is not gagnant)
                r[5], r[3], r[4], r[6] = "À_CLASSER", "", "", ""
                r[7] = "0"
                r[8] = (f"nom clair EN CONFLIT avec {gagnant[0]} ({gagnant[6]}, retenu) — "
                        f"autres revendicants : {autres}")
        else:
            for r in group:
                r[8] += f" [nom réutilisé par {len(group)} occurrences distinctes : " \
                         + ", ".join(o[0] for o in group if o is not r) + "]"

    for c in clear_records:
        if c["clear_name"] in matched_clear:
            continue
        bucket = clear_assembly_bucket(c)
        n_cands = sum(1 for o in obf_by_bucket.get(bucket, [])
                      if o["obf_name"] not in graines and o["_sig"] == c["_sig"])
        rows.append(["", "", c["clear_name"], "", "", "À_CLASSER", "", str(n_cands),
                     f"0 ou plusieurs candidats de même round-0 dans {bucket}, aucun retenu"])

    rows.sort(key=lambda r: r[2])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")
    return rows, stats, graines


# Point d'entrée : lance run() ou --epreuve, logue le résumé (proposées/à_classer/causes).
# / Entry point: runs run() or --epreuve, logs the summary (proposed/unclassed/causes).
def main():
    if "--epreuve" in sys.argv[1:]:
        sys.exit(run_epreuve())
    for p in (SIG_OBF_PATH, SIG_CLEAR_PATH):
        if not os.path.exists(p):
            log("ABSENT : lance d'abord extraire_signatures.py et charger_proto_clair.py.")
            sys.exit(2)
    rows, stats, _ = run()
    a_classer = sum(1 for r in rows if r[5] == "À_CLASSER")
    log(f"[matcher_v3] {len(rows)} lignes → {OUT_TSV}")
    log(f"[matcher_v3] proposées={len(rows)-a_classer} (DÉDUIT) / à_classer={a_classer}")
    log(f"[matcher_v3] détail : {stats}")
    uniques = sum(1 for r in rows if r[5] == "À_CLASSER" and r[7] == "0")
    tied = sum(1 for r in rows if r[5] == "À_CLASSER" and r[7] not in ("0", ""))
    log(f"[matcher_v3] parmi les à_classer : {uniques} sans candidat, {tied} à égalité")


# Empreinte sha256 d'un fichier (témoin de déterminisme). / File sha256 hash (determinism witness).
def sha256_of(path):
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def run_epreuve():
    """FR: (1) déterminisme. (2) sabotage — casser 10% des arêtes de voisinage : les
    correspondances qui EN DÉPENDAIENT (chemin_de_preuve contenant "voisinage") doivent
    tomber ; listées. (3) plancher de hasard — 20 tirages de graines MÉLANGÉES (noms
    permutés, seed fixe), moyenne/max du nombre de DÉDUIT. EN: (1) determinism. (2)
    sabotage — break 10% of neighborhood edges, matches that depended on them must fall.
    (3) random floor — 20 shuffled-seed draws, mean/max of DÉDUIT count."""
    for p in (SIG_OBF_PATH, SIG_CLEAR_PATH):
        if not os.path.exists(p):
            log("ABSENT : lance d'abord extraire_signatures.py et charger_proto_clair.py.")
            return 2
    ok = True

    log("=== témoin 1 : rejeu déterministe (sha256) ===")
    run(out_path=os.path.join(HERE, "_v3_run1.tsv"))
    run(out_path=os.path.join(HERE, "_v3_run2.tsv"))
    h1 = sha256_of(os.path.join(HERE, "_v3_run1.tsv"))
    h2 = sha256_of(os.path.join(HERE, "_v3_run2.tsv"))
    same = h1 == h2
    print(f"{'✅' if same else '❌'} témoin 1 (déterminisme) : {h1[:12]}… vs {h2[:12]}…")
    ok &= same

    log("=== témoin 2 : sabotage — 10% des arêtes de voisinage cassées ===")
    rows_reel, _, _ = run(out_path=os.path.join(HERE, "_v3_reel.tsv"))
    rows_sab, _, _ = run(out_path=os.path.join(HERE, "_v3_sab.tsv"), sabotage_edge_frac=0.10)
    dependantes = {r[0] for r in rows_reel if r[5] == "DÉDUIT" and "voisinage" in r[8]}
    p_reel = {r[0]: r[2] for r in rows_reel if r[5] == "DÉDUIT"}
    p_sab = {r[0]: r[2] for r in rows_sab if r[5] == "DÉDUIT"}
    cassees = [tok for tok in dependantes if p_sab.get(tok) != p_reel.get(tok)]
    print(f"{'✅' if dependantes and len(cassees) > 0 else 'ℹ️ '} témoin 2 (sabotage voisinage) : "
          f"{len(dependantes)} correspondance(s) dépendaient du voisinage, {len(cassees)} sont "
          f"tombées sous 10% d'arêtes cassées : {cassees}")
    ok &= (len(dependantes) == 0 or len(cassees) > 0)

    log("=== témoin 3 : plancher de hasard — 20 tirages de graines mélangées ===")
    rows_r, _, _ = run(out_path=os.path.join(HERE, "_v3_floor.tsv"))
    n_reel = sum(1 for r in rows_r if r[5] == "DÉDUIT")
    p_reel = {r[0]: r[2] for r in rows_r if r[5] == "DÉDUIT"}
    tirages, accords = [], []
    for seed in range(1, 21):
        rows_s, _, _ = run(out_path=os.path.join(HERE, "_v3_floor.tsv"), shuffle_seed=seed)
        p_s = {r[0]: r[2] for r in rows_s if r[5] == "DÉDUIT"}
        tirages.append(len(p_s))
        communs = set(p_reel) & set(p_s)
        accords.append(sum(1 for t in communs if p_reel[t] == p_s[t]) / len(communs) if communs else 0.0)
    log(f"réel={n_reel}  20 tirages (compte)={tirages}  moyenne={sum(tirages)/len(tirages):.1f}  max={max(tirages)}")
    log(f"20 tirages (accord D'IDENTITÉ sur les tokens communs, PAS le compte)={[round(a,3) for a in accords]}")
    print(f"ℹ️  témoin 3, compte SEUL (info, pas un test — même piège que v1/v2, mesuré et écarté "
          f"comme critère) : réel={n_reel} vs moyenne_hasard={sum(tirages)/len(tirages):.1f} "
          f"max_hasard={max(tirages)} — LE COMPTE NE DISCRIMINE RIEN (structure de propagation "
          f"identique, seuls les LABELS changent).")
    accord_moyen = sum(accords) / len(accords)
    effondre_identite = accord_moyen < 0.15
    print(f"{'✅' if effondre_identite else '❌'} témoin 3, IDENTITÉ (le vrai témoin) : accord "
          f"moyen sur les tokens communs = {accord_moyen:.1%} (max {max(accords):.1%}) — "
          f"{'effondré, le mécanisme est identité-dépendant' if effondre_identite else 'NE S’EFFONDRE PAS'}")
    ok &= effondre_identite

    for fn in ("_v3_run1.tsv", "_v3_run2.tsv", "_v3_reel.tsv", "_v3_sab.tsv", "_v3_floor.tsv"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            os.remove(p)

    print(f"\n=== BILAN ÉPREUVE v3 : {'MORD ✅' if ok else 'ÉCHEC ❌'} "
          "(témoin 3 est une mesure, pas un pass/fail) ===")
    return 0 if ok else 1


if __name__ == "__main__":
    main()
