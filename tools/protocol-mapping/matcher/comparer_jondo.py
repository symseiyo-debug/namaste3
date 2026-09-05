#!/usr/bin/env python3
"""
comparer_jondo.py — Étage 1 (Namaste 3), matcher v1.

QUOI : mesure l'accord entre NOTRE table (`correspondance-noms-classes.tsv`, produite
    SANS lire Jondo) et la table INDÉPENDANTE de JondoEmu (`datos/anclas_3.6.10.10.tsv`,
    opcode → nom proposé, mesurée par Jondo sur 242 captures réelles du MÊME build
    3.6.10.10). Écrit `ACCORD-JONDO.md`.
POURQUOI (04/09/2026, brief) : une table produite sans vérité terrain a
    besoin d'un second instrument indépendant pour savoir si elle mesure quelque chose —
    ce script est ce second instrument, plus le plancher de hasard qui dit si l'accord
    mesuré dépasse le pur hasard (correction issue d'une révision indépendante, cf. `mesurer`/`plancher_de_hasard`).
COMMENT LANCER : `python3 comparer_jondo.py` (lit `signatures-obfusquees.jsonl`,
    `attendus-depuis-noms.jsonl`, `correspondance-noms-classes.tsv`, écrit `ACCORD-JONDO.md`).
GATE : le plancher de hasard (20 tirages, moyenne+max) doit être rapporté — un accord
    brut sans lui est une fausse mesure (piège vécu et corrigé le 04/09).

FR : mesuré AVANT tout : 291/293 (99,3%) des opcodes de Jondo existent comme nom de
     classe (message ou nœud imbriqué) QUELQUE PART dans notre propre dump — ça VALIDE
     l'hypothèse que les deux dumps du même build partagent le même espace de noms
     obfusqués (sinon la comparaison n'aurait aucun sens). Mais mesuré ensuite : nos 4
     propositions réelles (kfp/knk/kfn/kni) ont un recoupement de 0 avec les 99 opcodes
     NOMMÉS par Jondo — parce que ce que notre matcher a réussi à apparier (GuildMission,
     TreasureHuntEvent…) sont des messages référencés en profondeur (champs d'un autre
     message), jamais envoyés seuls sur le fil, donc jamais des « opcodes » au sens où
     Jondo les définit (`type.ankama.com/<opcode>`, toujours de tête). Un taux d'accord
     sur N=0 ne se invente pas — donc CE script mesure aussi une comparaison plus large
     et plus utile : pour chaque opcode nommé par Jondo, un rapprochement TEXTUEL (mots
     du nom, indépendant de notre matcher structurel) vers un nom clair de la liste des
     513, puis un test de COMPATIBILITÉ STRUCTURELLE (même bucket assembly, même forme
     imbriquée) entre l'opcode (via NOTRE dump, lu indépendamment de Jondo) et ce nom
     clair. Un désaccord structurel dit que Jondo, notre rapprochement textuel, ou notre
     calcul de forme a une erreur — pas lequel, juste qu'il y en a une quelque part.
EN : measured first: 291/293 (99.3%) of Jondo's opcodes exist as a class name somewhere
     in our OWN dump — validates the same-build/same-obfuscation assumption. But our 4
     actual proposals overlap 0 with Jondo's 99 named opcodes (different message
     population: field-referenced submessages vs wire-top opcodes). So this script also
     runs a broader, more informative comparison: textual name-matching (independent of
     our structural matcher) + structural compatibility check, to get a measurable N.
Stdlib seule. 0 LLM.
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JONDO_ANCLAS = "refs/JondoEmu/datos/anclas_3.6.10.10.tsv"
SIG_PATH = os.path.join(HERE, "signatures-obfusquees.jsonl")
ATTENDUS_PATH = os.path.join(HERE, "attendus-depuis-noms.jsonl")
CORRESPONDANCE_TSV = os.path.join(HERE, "correspondance-noms-classes.tsv")
OUT_MD = os.path.join(HERE, "ACCORD-JONDO.md")

STOPWORDS = {"message", "event", "request", "response", "data", "info", "informations"}
WORD_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z0-9]+|[A-Z]+")


# Écrit sur stderr. / Writes to stderr.
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Découpe un nom camelCase en mots minuscules, mots creux (message/event…) écartés.
# / Splits a camelCase name into lowercase words, stopwords removed.
def words_of(name):
    ws = {w.lower() for w in WORD_RE.findall(name)}
    return ws - STOPWORDS


# Indice de Jaccard (recoupement / union) entre deux ensembles de mots.
# / Jaccard index (overlap / union) between two word sets.
def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# Charge les opcodes Jondo à nom proposé non vide (99/293, cf. anclas_3.6.10.10.tsv).
# / Loads Jondo opcodes with a non-empty proposed name (99/293).
def load_jondo():
    rows = []
    with open(JONDO_ANCLAS, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 3 or not cols[0]:
                continue
            opcode, direction, nom = cols[0], cols[1] if len(cols) > 1 else "", cols[2]
            signif = cols[3] if len(cols) > 3 else ""
            if nom.strip():
                rows.append({"opcode": opcode, "dir": direction, "nom": nom.strip(), "signif": signif})
    return rows


# Reconvertit les listes JSON en tuples (round-trip inverse de attendus_depuis_noms.py).
# / Converts JSON lists back to tuples (inverse round-trip of attendus_depuis_noms.py).
def to_tuple(x):
    return tuple(to_tuple(i) for i in x) if isinstance(x, list) else x


# Enfants sémantiques réels = enfants du conteneur Types (jamais le conteneur lui-même).
# / Real semantic children = the Types wrapper's own children (never the wrapper itself).
def collapse_wrapper_children(tree_node):
    real = []
    for wrapper in tree_node.get("children", []):
        real.extend(wrapper.get("children", []))
    return real


# Signature de forme récursive (tuple trié), même définition que matcher.py.
# / Recursive shape signature (sorted tuple), same definition as matcher.py.
def shape_of_obf(tree_node):
    real = collapse_wrapper_children(tree_node)
    return tuple(sorted(shape_of_obf(r) for r in real))


# Charge nos 3 sources : signatures obfusquées, attendus clairs, propositions v1 déjà écrites.
# / Loads our 3 sources: obfuscated signatures, clear expectations, v1 proposals already written.
def load_our_data():
    sig_by_name = {}
    with open(SIG_PATH, encoding="utf-8") as f:
        for l in f:
            r = json.loads(l)
            r["_shape"] = shape_of_obf(r["nested_tree"])
            sig_by_name.setdefault(r["obf_name"], []).append(r)

    clear = []
    with open(ATTENDUS_PATH, encoding="utf-8") as f:
        for l in f:
            r = json.loads(l)
            r["shape_signature"] = to_tuple(r["shape_signature"])
            clear.append(r)

    proposed_by_clear = {}
    if os.path.exists(CORRESPONDANCE_TSV):
        with open(CORRESPONDANCE_TSV, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if row["statut"] == "DÉDUIT":
                    proposed_by_clear[row["nom_clair"]] = row

    return sig_by_name, clear, proposed_by_clear


# Meilleur nom clair par recoupement de mots (Jaccard), seuil 0,34 mesuré à la main
# (§ historique du chantier — au-dessous, trop de faux rapprochements).
# / Best clear name by word overlap (Jaccard), 0.34 threshold hand-tuned.
def best_textual_match(jondo_name, clear_records, seuil=0.34):
    jw = words_of(jondo_name)
    best, best_score = None, 0.0
    for c in clear_records:
        cw = words_of(c["short_name"])
        s = jaccard(jw, cw)
        if s > best_score:
            best, best_score = c, s
    if best_score >= seuil:
        return best, best_score
    return None, best_score


def mesurer(sig_by_name, clear_records, jondo_rows, proposed_by_clear=None):
    """FR: cœur réutilisable — matcher.py --epreuve l'appelle avec des `clear_records`
    mélangés pour prouver que le taux s'effondre, sans dupliquer cette boucle.
    EN: reusable core — matcher.py --epreuve calls it with shuffled clear_records to
    prove the rate collapses, without duplicating this loop."""
    proposed_by_clear = proposed_by_clear or {}
    comparisons = []
    for row in jondo_rows:
        opcode = row["opcode"]
        our_recs = sig_by_name.get(opcode)
        match, score = best_textual_match(row["nom"], clear_records)
        entry = {"opcode": opcode, "jondo_nom": row["nom"], "jondo_signif": row["signif"],
                 "opcode_connu_chez_nous": our_recs is not None,
                 "match_textuel": match["full_name"] if match else None,
                 "score_textuel": round(score, 2)}
        if our_recs and match:
            our_rec = our_recs[0]
            same_assembly = our_rec["assembly"] == match["assembly_guess"]
            same_shape = our_rec["_shape"] == to_tuple(match["shape_signature"])
            entry["compatible_structurellement"] = bool(same_assembly and same_shape)
            entry["same_assembly"] = same_assembly
            entry["same_shape"] = same_shape
            entry["notre_forme"] = our_rec["_shape"]
            entry["forme_attendue"] = to_tuple(match["shape_signature"])
        else:
            entry["compatible_structurellement"] = None
        proposed = proposed_by_clear.get(match["full_name"]) if match else None
        entry["notre_matcher_a_propose"] = proposed["classe_obf"] if proposed else None
        entry["accord_matcher"] = (proposed is not None and proposed["classe_obf"] == opcode)
        comparisons.append(entry)

    with_match = [c for c in comparisons if c["match_textuel"]]
    compatible = [c for c in with_match if c["compatible_structurellement"] is True]
    incompatible = [c for c in with_match if c["compatible_structurellement"] is False]
    no_data = [c for c in with_match if c["compatible_structurellement"] is None]
    no_textual = [c for c in comparisons if not c["match_textuel"]]
    taux = len(compatible) / len(with_match) if with_match else 0.0
    return {"comparisons": comparisons, "with_match": with_match, "compatible": compatible,
            "incompatible": incompatible, "no_data": no_data, "no_textual": no_textual, "taux": taux}


def plancher_de_hasard(sig_by_name, clear_records, jondo_rows, n_tirages=20):
    """FR: CORRECTION issue d'une révision indépendante (sur l'épreuve initiale) — « l'accord doit
    s'effondrer » n'est pas une mesure (71%→62% ne tranche rien). Le témoin réel : 20
    tirages mélangés (seeds fixes 1..20), moyenne et max mesurés, verdict CHIFFRÉ contre
    le réel — jamais un seuil arbitraire. Dupliqué depuis matcher.py sciemment (import
    croisé matcher↔comparer_jondo déjà en place dans l'autre sens ; éviter un cycle).
    EN: independent-review correction — a numeric random floor (20 fixed-seed shuffles), not a
    collapse threshold. Duplicated from matcher.py on purpose (avoids an import cycle,
    matcher.py already imports comparer_jondo)."""
    import random
    m_reel = mesurer(sig_by_name, clear_records, jondo_rows)
    tirages = []
    for seed in range(1, n_tirages + 1):
        rng = random.Random(seed)
        clear_shuffle = json.loads(json.dumps(clear_records))
        shapes = [r["shape_signature"] for r in clear_shuffle]
        rng.shuffle(shapes)
        for r, s in zip(clear_shuffle, shapes):
            r["shape_signature"] = s
        tirages.append(mesurer(sig_by_name, clear_shuffle, jondo_rows)["taux"])
    maximum = max(tirages)
    return {"taux_reel": m_reel["taux"], "n_reel": len(m_reel["with_match"]), "tirages": tirages,
            "moyenne_hasard": sum(tirages) / len(tirages), "max_hasard": maximum,
            "min_hasard": min(tirages), "mesure_quelque_chose": m_reel["taux"] > maximum}


# Point d'entrée : charge Jondo+nos données, mesure la validation de terrain, le taux
# de compatibilité et le plancher de hasard, écrit ACCORD-JONDO.md.
# / Entry point: loads everything, measures ground validation, compatibility rate and
# random floor, writes ACCORD-JONDO.md.
def main():
    for p in (JONDO_ANCLAS, SIG_PATH, ATTENDUS_PATH):
        if not os.path.exists(p):
            log(f"ABSENT : {p} — comparaison impossible, je n'invente pas.")
            sys.exit(2)

    jondo_rows = load_jondo()
    log(f"[comparer] {len(jondo_rows)} opcodes Jondo nommés (sur 293 opcodes au total)")
    sig_by_name, clear_records, proposed_by_clear = load_our_data()

    all_our_names = set(sig_by_name.keys())
    tree_names = set()
    for recs in sig_by_name.values():
        for r in recs:
            # Aplatit récursivement tous les noms de l'arbre imbriqué. / Recursively flattens all nested tree names.
            def collect(t):
                tree_names.add(t["name"])
                for c in t.get("children", []):
                    collect(c)
            collect(r["nested_tree"])
    total_opcodes_all = []
    with open(JONDO_ANCLAS, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            cols = line.split("\t")
            if cols and cols[0]:
                total_opcodes_all.append(cols[0])
    present = sum(1 for o in total_opcodes_all if o in all_our_names or o in tree_names)
    log(f"[comparer] validation build : {present}/{len(total_opcodes_all)} opcodes Jondo "
        "existent comme nom de classe/nœud dans NOTRE dump (même build, même obfuscation)")

    direct_overlap = [r for r in jondo_rows if r["opcode"] in {row["classe_obf"] for row in proposed_by_clear.values()}]
    log(f"[comparer] recoupement direct (nos propositions ∩ opcodes nommés par Jondo) : {len(direct_overlap)}")

    m = mesurer(sig_by_name, clear_records, jondo_rows, proposed_by_clear)
    with_match, compatible, incompatible, no_data, no_textual, taux = (
        m["with_match"], m["compatible"], m["incompatible"], m["no_data"], m["no_textual"], m["taux"])

    log(f"[comparer] rapprochement textuel réussi (seuil 0.34) : {len(with_match)}/{len(jondo_rows)}")
    log(f"[comparer] compatibilité structurelle sur ces {len(with_match)} : "
        f"{len(compatible)} compatibles, {len(incompatible)} INCOMPATIBLES, {len(no_data)} sans donnée")
    log(f"[comparer] taux de compatibilité BRUT = {taux:.1%} — voir plancher de hasard ci-dessous "
        "avant d'y lire un accord")

    log("[comparer] plancher de hasard (20 tirages, seeds 1..20)…")
    floor = plancher_de_hasard(sig_by_name, clear_records, jondo_rows, 20)
    log(f"[comparer] 20 tirages : {[round(v, 4) for v in floor['tirages']]}")
    log(f"[comparer] moyenne_hasard={floor['moyenne_hasard']:.1%}  max_hasard={floor['max_hasard']:.1%}  "
        f"réel={floor['taux_reel']:.1%}  mesure_quelque_chose={floor['mesure_quelque_chose']}")

    write_report(jondo_rows, present, len(total_opcodes_all), direct_overlap, m["comparisons"],
                 with_match, compatible, incompatible, no_data, no_textual, taux, floor)
    log(f"[comparer] rapport → {OUT_MD}")


# Écrit ACCORD-JONDO.md — toutes les mesures de main()/mesurer()/plancher_de_hasard() en un rapport lisible.
# / Writes ACCORD-JONDO.md — all measurements from main()/mesurer()/plancher_de_hasard() as one readable report.
def write_report(jondo_rows, present, total_opcodes, direct_overlap, comparisons,
                  with_match, compatible, incompatible, no_data, no_textual, taux, floor):
    L = []
    P = L.append
    P("# Accord avec JondoEmu — mesuré, pas simulé\n")
    P(f"Source Jondo : `{JONDO_ANCLAS}` — {len(jondo_rows)}/293 opcodes portent un nom proposé.\n")

    P("## 1. Validation du terrain : même build, même obfuscation")
    P(f"- **{present}/{total_opcodes} ({present/total_opcodes:.1%})** des opcodes Jondo existent "
      "comme nom de classe/nœud QUELQUE PART dans notre propre dump (extrait indépendamment, "
      "sans lire Jondo). Ça valide l'hypothèse de départ (même build 3.6.10.10 → même espace de "
      "noms obfusqués des DEUX côtés) — condition nécessaire pour que le reste de cette page ait un sens.\n")

    P("## 2. Recoupement DIRECT avec nos propositions réelles")
    P(f"- Nos 4 lignes `DÉDUIT` (matcher.py) ∩ les {len(jondo_rows)} opcodes nommés par Jondo : "
      f"**{len(direct_overlap)}**.")
    P("- Mesuré, pas un bug : nos 2 correspondances de tête (`kfp`→GuildMission, "
      "`knk`→TreasureHuntEvent) sont des messages référencés en PROFONDEUR par un autre message "
      "(champs), jamais envoyés seuls sur le fil — donc jamais des « opcodes » au sens de Jondo "
      "(`type.ankama.com/<opcode>`, toujours de tête). Un taux d'accord sur cette population "
      "précise vaut 0/0 (non défini) ; la section 3 mesure une comparaison plus large.\n")

    P("## 3. Comparaison élargie : rapprochement textuel + compatibilité structurelle")
    P("Pour chacun des opcodes nommés par Jondo, on cherche le nom clair (parmi nos 513 noms de "
      "tête) dont les MOTS se recoupent le plus (Jaccard sur tokens camelCase, seuil 0,34, "
      "indépendant de notre matcher structurel) — puis on teste si CET opcode, tel que NOUS "
      "l'avons mesuré dans notre dump, a bien la même forme imbriquée et le même bucket "
      "d'assembly que ce nom clair l'exigerait.\n")
    P(f"- rapprochement textuel trouvé : **{len(with_match)}/{len(comparisons)}**")
    P(f"- sans rapprochement textuel plausible (score < 0,34) : **{len(no_textual)}**")
    P(f"- compatibles structurellement : **{len(compatible)}**")
    P(f"- **INCOMPATIBLES : {len(incompatible)}**")
    P(f"- sans donnée (opcode absent de notre dump) : **{len(no_data)}**")
    P(f"- taux de compatibilité BRUT = **{taux:.1%}**\n")

    P("### Plancher de hasard — CORRECTION mesurée (revue indépendante, 04/09)")
    P("« L'accord doit s'effondrer sous mélange » n'est pas une mesure : 71%→62% ne "
      "permet de trancher ni dans un sens ni dans l'autre. Le vrai témoin : mélanger les "
      "noms clairs 20 fois (seeds fixes 1..20), mesurer ce même taux de compatibilité à "
      "chaque tirage, comparer le RÉEL à la moyenne et au MAXIMUM des 20.\n")
    P(f"- les 20 tirages : `{[round(v, 4) for v in floor['tirages']]}`")
    P(f"- moyenne du hasard : **{floor['moyenne_hasard']:.1%}**")
    P(f"- maximum du hasard : **{floor['max_hasard']:.1%}**")
    P(f"- réel : **{floor['taux_reel']:.1%}**\n")
    if floor["mesure_quelque_chose"]:
        ratio = floor["taux_reel"] / floor["max_hasard"] if floor["max_hasard"] else float("inf")
        P(f"**Verdict : le matcher mesure quelque chose** — réel ({floor['taux_reel']:.1%}) > "
          f"max_hasard ({floor['max_hasard']:.1%}), ratio réel/max_hasard = **{ratio:.2f}**.\n")
    else:
        P(f"**Verdict : cette comparaison élargie NE MESURE RIEN.** Le réel "
          f"({floor['taux_reel']:.1%}) tombe DANS la plage des 20 tirages mélangés "
          f"[{floor['min_hasard']:.1%}, {floor['max_hasard']:.1%}] — il n'est même pas le "
          "maximum des 20. Ce n'est pas un échec de la mesure : c'est le résultat. La "
          "cause la plus probable, déjà mesurée ailleurs (`RAPPORT-MATCHER.md` §4) : 87% "
          "des noms de tête ont une forme d'imbrication TRIVIALE (aucun enfant), donc "
          "« compatible en forme » coïncide presque aussi souvent par hasard que par "
          "vraie correspondance — le taux brut de 60,5% ne doit PAS être lu comme un "
          "accord avec Jondo, quel que soit son chiffre. Ce que ce même mécanisme arrive "
          "à faire sur le sous-ensemble à forme NON triviale (le matcher réel, "
          "`correspondance-noms-classes.tsv`) reste, lui, mesuré séparément et différent : "
          "voir `RAPPORT-MATCHER.md` §4 (3,1% de résolution UNIQUE sur les 65 noms à forme "
          "non triviale, 0% sur les 448 triviaux) — un mécanisme plus strict "
          "(candidat UNIQUE, pas juste « compatible ») que celui mesuré ici.\n")

    P("### Tous les désaccords (incompatibilité structurelle)")
    if incompatible:
        P("| opcode | nom Jondo | nom clair rapproché | notre forme | forme attendue | assembly OK |")
        P("|---|---|---|---|---|---|")
        for c in incompatible:
            P(f"| `{c['opcode']}` | {c['jondo_nom']} | {c['match_textuel']} | "
              f"`{c['notre_forme']}` | `{c['forme_attendue']}` | {'oui' if c['same_assembly'] else 'NON'} |")
    else:
        P("(aucun)")
    P("")

    P("### 5 désaccords analysés — la question n'est pas qui a tort")
    P("Correction de la revue independante : le bon angle n'est pas « qui a raison » mais « les "
      "deux instruments regardent-ils la MÊME CHOSE ». Un désaccord localisé sur ce même "
      "build est soit une erreur (rapprochement textuel qui a pris le mauvais candidat — "
      "le cas le plus probable ici, l'heuristique est un simple Jaccard de mots sans "
      "connaissance du protocole), soit une AMBIGUÏTÉ STRUCTURELLE RÉELLE — et ce second "
      "cas est une trouvaille à rapporter comme telle, pas un bug à corriger.\n")
    for c in incompatible[:5]:
        P(f"\n**`{c['opcode']}` (Jondo: {c['jondo_nom']}) ↔ {c['match_textuel']}**")
        P(f"- Jondo dit (mesuré sur 242 captures) : {c['jondo_signif'] or '(pas de description)'}")
        P(f"- notre forme mesurée : `{c['notre_forme']}` — forme attendue par le nom clair : `{c['forme_attendue']}`")
        if not c["same_assembly"]:
            P("- **bucket d'assembly différent** — les deux instruments ne regardent probablement "
              "PAS la même chose : le rapprochement textuel (Jaccard de mots, aucune connaissance "
              "du protocole) a plus probablement choisi le mauvais nom clair (Connection vs Game) "
              "que Jondo ou notre extraction ne se trompent sur l'assembly, qui est lu directement "
              "du TypeDefIndex — un fait dur, pas une hypothèse.")
        elif c["notre_forme"] == () and c["forme_attendue"] != ():
            P("- notre forme est TRIVIALE alors que le nom clair en attend une : deux lectures "
              "possibles, ni tranchée ni à trancher ici — (a) les deux instruments regardent des "
              "objets DIFFÉRENTS (rapprochement textuel fautif, cas fréquent vu que 87% des noms "
              "de tête ont une forme triviale et ne discriminent rien) ; (b) les deux regardent le "
              "MÊME message mais son schéma a changé entre la mesure du littéral et cette build "
              "— dans ce cas précis (b) serait la trouvaille, pas l'erreur.")
        elif c["forme_attendue"] == () and c["notre_forme"] != ():
            P("- l'inverse : notre classe a des enfants, le nom clair n'en attend aucun — même "
              "double lecture que ci-dessus, pas tranchée.")
        else:
            P("- les deux ont une forme non triviale mais DIFFÉRENTE — c'est le cas le plus "
              "informatif des deux lectures : soit un rapprochement textuel qui a pris un nom "
              "clair voisin mais faux, soit les deux instruments regardent authentiquement le "
              "même message à deux moments structurels différents (trouvaille, pas erreur).")
    if not incompatible:
        P("(aucun désaccord structurel mesuré — voir §2 pour la limite de N sur nos propositions réelles)")
    P("")

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
