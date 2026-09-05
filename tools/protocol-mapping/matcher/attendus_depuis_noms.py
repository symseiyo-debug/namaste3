#!/usr/bin/env python3
"""
attendus_depuis_noms.py — Étage 1 (Namaste 3), matcher.

QUOI : dérive, pour chacun des 1003 littéraux clairs (`noms-protocole-en-clair.v2.txt`,
    gate G0 VERT), la FORME D'IMBRICATION sémantique attendue (le conteneur `Types`
    replié) — en ATTENDANT de savoir à quelle classe obfusquée le nom correspond.
POURQUOI (04/09/2026, brief « matcher noms clairs ↔ classes obfusquées ») :
    sans cette forme, matcher.py n'a aucun signal comparable côté obfusqué — 1re brique
    de la chaîne v1.
COMMENT LANCER : `python3 attendus_depuis_noms.py` (lit `noms-protocole-en-clair.v2.txt`,
    écrit `attendus-depuis-noms.jsonl`).
GATE : logue l'alternance Types/libellé mesurée (doit être 1003/1003) et le compte de
    `decoy` (doit être 0) — un chiffre différent signale que la référence a changé.

FR : mesuré ici, avant tout matching (§ vérifié, pas supposé) — sur les 1003 noms :
     - l'imbrication ALTERNE STRICTEMENT `Types` puis un vrai libellé (`Foo+Types+Bar`,
       jamais `Foo+Bar` direct) : 1003/1003, 0 exception. C'est la convention connue du
       codegen Google.Protobuf C# (un conteneur statique `Types` par message parent),
       confirmée ICI par du code NON obfusqué ailleurs dans le même dump (TypeDefIndex
       6664-6667, hors de nos deux assemblies cibles) où le conteneur s'appelle
       littéralement `Types`.
     - DANS nos deux assemblies cibles, ce conteneur `Types` est lui aussi obfusqué (0
       occurrence du littéral `class Types` dans ces plages, mesuré) : invisible par le
       nom, seulement par la FORME (aucun champ propre, seulement des enfants).
     - conséquence : on peut donc COMPARER la forme des deux côtés en ignorant les sauts
       `Types` de chaque côté — c'est ce que ce script prépare côté noms clairs, et que
       matcher.py prépare côté classes obfusquées (fonction équivalente, indépendante).
     - AUCUN marqueur `decoy` n'existe dans le fichier v2 actuel (0/1003, mesuré) —
       contredit la mention historique « 184 decoy » du cahier des charges, qui provient
       de l'ANCIENNE mesure à 1223 (retirée par gate-g0.py lui-même, cf. son code) ; ce
       script utilise le fichier v2 courant, seule référence certifiée VERT par G0.
EN : measured here, before any matching: nesting strictly ALTERNATES `Types` then a
     real label (1003/1003, 0 exceptions) — confirmed against unobfuscated reference
     code elsewhere in the same dump. No `decoy` marker exists in the current v2 file
     (0/1003) — the historical "184 decoy" figure comes from the RETIRED 1223-count,
     not from this gate-G0-certified reference.
Stdlib seule. 0 LLM.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NOMS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "etage0-dump", "noms-protocole-en-clair.v2.txt"
)
OUT_PATH = os.path.join(HERE, "attendus-depuis-noms.jsonl")


# Écrit sur stderr (stdout reste dispo pour une sortie propre, jamais utilisé ici).
# / Writes to stderr (keeps stdout free for a clean output, unused here).
def log(msg):
    print(msg, file=sys.stderr, flush=True)


# Lit les 1003 noms clairs, une ligne = un nom, lignes vides ignorées.
# / Reads the 1003 clear names, one per line, blank lines skipped.
def load_names(path):
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def check_alternance(names):
    """Loi de vérité : on RE-mesure ici plutôt que de faire confiance au commentaire du
    module — si jamais le fichier change, ce script doit le voir et le dire."""
    bad = []
    for n in names:
        nested = n.split("+")[1:]
        for i, seg in enumerate(nested):
            if (seg == "Types") != (i % 2 == 0):
                bad.append(n)
                break
    return bad


# Bucket assembly (Connection vs Game) déduit du namespace du nom clair.
# / Assembly bucket (Connection vs Game) guessed from the clear name's namespace.
def guess_assembly(full_name):
    if ".Connection.Protocol." in full_name:
        return "Ankama.Dofus.Protocol.Connection.dll"
    if ".Game.Protocol." in full_name:
        return "Ankama.Dofus.Protocol.Game.dll"
    return "?"


def build_semantic_trees(names):
    """FR: un arbre par nom de tête (sans '+'), en gardant SEULEMENT les libellés
    sémantiques (on saute chaque 'Types' — position paire de la liste imbriquée, déjà
    vérifiée alternante ci-dessus). EN: one tree per top-level name, keeping only real
    labels (Types hops skipped, alternance already checked above)."""
    trees = {}
    for full in names:
        parts = full.split("+")
        outer = parts[0]
        nested = parts[1:]
        labels = nested[1::2]  # positions impaires (0-indexées) après le 1er 'Types'
        node = trees.setdefault(outer, {"label": outer, "children": {}, "literal_count": 0})
        node["literal_count"] += 1
        cur = node
        for lab in labels:
            cur = cur["children"].setdefault(lab, {"label": lab, "children": {}, "literal_count": 0})
            cur["literal_count"] += 1
    return trees


def shape_signature(node):
    """Tuple canonique (récursif, trié) — comparable directement à celui calculé côté
    obfusqué par matcher.py sur nested_tree (même définition, cf. son docstring)."""
    return tuple(sorted(shape_signature(c) for c in node["children"].values()))


# Nombre total de descendants sémantiques (récursif, tous niveaux).
# / Total semantic descendant count (recursive, all levels).
def subtree_size(node):
    return len(node["children"]) + sum(subtree_size(c) for c in node["children"].values())


# Profondeur sémantique maximale sous ce nœud (0 si aucun enfant).
# / Max semantic depth under this node (0 if no children).
def max_depth(node):
    if not node["children"]:
        return 0
    return 1 + max(max_depth(c) for c in node["children"].values())


SPECIAL_LABELS = ("Success", "Error", "Failed")


# Aplati récursivement tous les libellés descendants dans `acc` (mutation en place).
# / Recursively flattens every descendant label into `acc` (in-place mutation).
def collect_labels(node, acc):
    for lab, c in node["children"].items():
        acc.append(lab)
        collect_labels(c, acc)


# Point d'entrée : lit les noms, vérifie l'alternance, construit les arbres, écrit le JSONL.
# / Entry point: reads names, checks alternation, builds trees, writes the JSONL.
def main():
    if not os.path.exists(NOMS_PATH):
        log(f"ABSENT : {NOMS_PATH} — rien à dériver, je n'invente pas.")
        sys.exit(2)

    names = load_names(NOMS_PATH)
    log(f"[attendus] {len(names)} noms clairs lus depuis {NOMS_PATH}")

    bad = check_alternance(names)
    log(f"[attendus] alternance Types/libellé : {len(names)-len(bad)}/{len(names)} OK"
        + (f" — {len(bad)} EXCEPTIONS (voir stderr) : {bad[:10]}" if bad else " — 0 exception"))
    decoy_count = sum(1 for n in names if "decoy" in n.lower())
    log(f"[attendus] occurrences 'decoy' dans le fichier v2 : {decoy_count} "
        "(0 attendu — la mention '184 decoy' du cahier des charges vient de l'ancienne mesure retirée 1223)")

    trees = build_semantic_trees(names)
    log(f"[attendus] {len(trees)} arbres de tête construits (attendu 513)")

    records = []
    for outer, node in trees.items():
        labels = []
        collect_labels(node, labels)
        sig = shape_signature(node)
        records.append({
            "full_name": outer,
            "short_name": outer.rsplit(".", 1)[-1],
            "assembly_guess": guess_assembly(outer),
            "num_direct_children": len(node["children"]),
            "subtree_semantic_size": subtree_size(node),
            "max_semantic_depth": max_depth(node),
            "shape_signature": sig,
            "descendant_labels": sorted(labels),
            "has_success": "Success" in labels,
            "has_error": "Error" in labels,
            "has_failed": "Failed" in labels,
            "literal_count_total": node["literal_count"],
        })

    records.sort(key=lambda r: r["full_name"])
    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for r in records:
            # json ne sérialise pas les tuples imbriqués tels quels de façon stable pour
            # relecture -> on les convertit récursivement en listes (round-trip par matcher.py
            # via une fonction inverse : list -> tuple).
            def tup2list(t):
                return [tup2list(x) for x in t] if isinstance(t, tuple) else t
            rec = dict(r)
            rec["shape_signature"] = tup2list(r["shape_signature"])
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    trivial = sum(1 for r in records if r["num_direct_children"] == 0)
    by_assembly = {}
    for r in records:
        by_assembly[r["assembly_guess"]] = by_assembly.get(r["assembly_guess"], 0) + 1
    log(f"[attendus] {trivial}/{len(records)} noms de tête SANS aucun enfant (forme triviale, "
        "0 pouvoir discriminant par la forme)")
    log(f"[attendus] répartition par assembly devinée : {by_assembly}")
    log(f"[attendus] {len(records)} fiches écrites → {OUT_PATH}")


if __name__ == "__main__":
    main()
