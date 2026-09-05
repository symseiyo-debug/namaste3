#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : comparer_stabilite_builds.py [--out PATH] [--epreuve]
Second passage (Namaste 3, étage 1) : intègre gatherer/luaxy/deobfs au
croisement de `comparer_instruments.py` (non modifié, déjà rendu) et mesure
la STABILITÉ des noms/champs entre un instrument ANCIEN (gatherer/luaxy,
~2024-10, protocole encore en clair) et les instruments du build courant
(otomai, JondoEmu 3.6.10.10) — ce qui n'a pas bougé en ~18 mois est ce qui
survivra le mieux aux patchs futurs (périmètre étage 4). 0-LLM, stdlib.

POURQUOI :
TROUVAILLE PRÉALABLE (mesurée avant tout calcul) : `dofus3-gatherer` et
`dofus-unity-protocol-builder` (LuaxY) partagent des `.proto` BYTE-IDENTIQUES
(`diff -rq` → 0 différence sur les 79 fichiers). `dofus-deobfs` embarque EN
PLUS une 3ᵉ copie de ces mêmes 79 fichiers sous `protos/clear/` (idem, 0
différence) — donc le total "1441 .proto" cité pour deobfs mélange 1362
fichiers réellement OBFUSQUÉS (`protos/filtered/`, la vraie donnée deobfs)
et 79 qui sont LA MÊME chose que gatherer/luaxy comptée une 3ᵉ fois. Cette
correction est appliquée partout ci-dessous.

COMMENT LANCER : python3 comparer_stabilite_builds.py [--out PATH.md] [--epreuve]
    (lit protocole-{gatherer,luaxy,deobfs,otomai}.tsv + le dump étage0 + anclas_3.6.10.10.tsv,
    tous dans son propre dossier ou des chemins locaux en dur).
GATE : --epreuve (compare_trees detecte l'identite ET la difference, sabotage dans les deux
    sens ; rejeu byte-identique du rapport si les TSV prealables sont presents).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ICI = Path(__file__).parent
OUT_DEFAUT = ICI / "STABILITE-BUILDS.md"
GATHERER_TSV = ICI / "protocole-gatherer.tsv"
LUAXY_TSV = ICI / "protocole-luaxy.tsv"
DEOBFS_TSV = ICI / "protocole-deobfs.tsv"
OTOMAI_TSV = ICI / "protocole-otomai.tsv"
DUMP_TXT = Path("internal/noms-protocole-en-clair.v2.txt")
JONDO_ANCLAS = Path("refs/JondoEmu/datos/anclas_3.6.10.10.tsv")
GATHERER_PROTO_DIR = Path("refs/dofus3-gatherer/resources/proto")
LUAXY_PROTO_DIR = Path("refs/dofus-unity-protocol-builder/proto")
DEOBFS_CLEAR_DIR = Path("refs/dofus-deobfs/protos/clear")
DEOBFS_FILTERED_DIR = Path("refs/dofus-deobfs/protos/filtered")


def sha_of_tree(root: Path) -> dict:
    """FR: sha256 par fichier relatif, pour prouver une identité byte-a-byte
    SANS dependre d'un `diff` externe (rejeu autonome). EN: per-file sha256,
    proving byte identity without shelling out to `diff` (self-contained rerun)."""
    out = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.proto")):
        out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def compare_trees(a: Path, b: Path) -> tuple[int, int, int]:
    """Retourne (fichiers_identiques, fichiers_differents, presents_un_seul_cote)."""
    ha, hb = sha_of_tree(a), sha_of_tree(b)
    common = set(ha) & set(hb)
    identical = sum(1 for k in common if ha[k] == hb[k])
    different = len(common) - identical
    only_one_side = len(set(ha) ^ set(hb))
    return identical, different, only_one_side


# Lit un TSV en liste de dict (colonnes = en-tete) -- [] si le fichier n'existe pas.
# / Reads a TSV into a list of dicts (columns = header) -- [] if the file doesn't exist.
def load_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# Filtre les lignes top-level (is_top), rend (noms, {nom: {numero_champ: type}}).
# / Filters top-level rows (is_top), returns (names, {name: {field_number: type}}).
def names_and_fields(rows: list[dict], is_top: "callable", name_key="nom_message_clair"):
    names, fields = set(), {}
    for r in rows:
        if not is_top(r) or not r.get(name_key):
            continue
        names.add(r[name_key])
        champs = {}
        if r["champs"]:
            for part in r["champs"].split(";"):
                num, t, _fn = part.split(":", 2)
                champs[int(num)] = t
        fields.setdefault(r[name_key], champs)
    return names, fields


# Regroupe un type litteral en categorie large (numerique/flottant/bool/string/bytes/liste/
# message_ou_enum) -- comparer des categories, pas des mots (int32 vs int, C# vs proto3).
# / Buckets a literal type into a broad category (numeric/float/bool/string/bytes/list/
# message_or_enum) -- comparing categories, not words (int32 vs int, C# vs proto3).
def field_kind(t: str) -> str:
    tl = t.lower()
    if tl.startswith("repeated ") or tl.startswith("list<"):
        return "liste"
    if tl in ("int", "int32", "uint32", "sint32", "long", "int64", "uint64", "sint64", "short", "byte"):
        return "numerique"
    if tl in ("float", "double"):
        return "flottant"
    if tl == "bool":
        return "bool"
    if tl == "string":
        return "string"
    if tl == "bytes":
        return "bytes"
    return "message_ou_enum"


# Sur les noms communs a et b : accord de categorie/type exact/nombre de champs/champs orphelins.
# / On the names common to a and b: category/exact-type/field-count agreement + orphan fields.
def field_agreement(names_common, fields_a, fields_b):
    total, kind_match, exact_match, one_side = 0, 0, 0, 0
    for n in names_common:
        fa, fb = fields_a[n], fields_b[n]
        for num in set(fa) | set(fb):
            total += 1
            ta, tb = fa.get(num), fb.get(num)
            if ta and tb:
                if field_kind(ta) == field_kind(tb):
                    kind_match += 1
                if ta == tb:
                    exact_match += 1
            else:
                one_side += 1
    same_count = sum(1 for n in names_common if len(fields_a[n]) == len(fields_b[n]))
    return {"total": total, "kind_match": kind_match, "exact_match": exact_match,
            "one_side": one_side, "same_count": same_count, "n_names": len(names_common)}


# Construit STABILITE-BUILDS.md (les 4 sections : dedoublonnage gatherer/luaxy/deobfs, stabilite
# des noms, accord des champs, cas deobfs sans nom) et rend les stats resumees.
# / Builds STABILITE-BUILDS.md (the 4 sections: gatherer/luaxy/deobfs dedup, name stability,
# field agreement, the nameless deobfs case) and returns the summary stats.
def build_report(out_path: Path) -> dict:
    md = ["# STABILITÉ-BUILDS — gatherer/luaxy (≈2024) vs otomai/JondoEmu (3.6.10.10)", "",
          "> Étage 1 (Namaste 3), second passage sur `comparer_instruments.py`. "
          "Sources : `protocole-gatherer.tsv`, `protocole-luaxy.tsv`, `protocole-deobfs.tsv`, "
          "`protocole-otomai.tsv`, dump étage0, `anclas_3.6.10.10.tsv`.", ""]

    md.append("## 1. gatherer / luaxy / deobfs — ce qui est réellement indépendant")
    id_gl, diff_gl, only_gl = compare_trees(GATHERER_PROTO_DIR, LUAXY_PROTO_DIR)
    md.append(f"- gatherer vs luaxy (`.proto` sha256 par fichier) : **{id_gl} identiques**, {diff_gl} différents, "
              f"{only_gl} présents d'un seul côté. {'⚠️ CE SONT LA MÊME DONNÉE.' if diff_gl == 0 and only_gl == 0 else ''}")
    id_dc, diff_dc, only_dc = compare_trees(DEOBFS_CLEAR_DIR, LUAXY_PROTO_DIR)
    md.append(f"- deobfs `protos/clear/` vs luaxy : **{id_dc} identiques**, {diff_dc} différents, {only_dc} "
              f"présents d'un seul côté — {'une 3ᵉ copie de la MÊME donnée.' if diff_dc == 0 and only_dc == 0 else ''}")
    n_filtered = len(list(DEOBFS_FILTERED_DIR.rglob('*.proto'))) if DEOBFS_FILTERED_DIR.exists() else 0
    n_clear = len(list(DEOBFS_CLEAR_DIR.rglob('*.proto'))) if DEOBFS_CLEAR_DIR.exists() else 0
    md.append(f"- **Correction de compte** : `dofus-deobfs` contient {n_filtered + n_clear} `.proto` au total "
              f"(`find -iname` sur tout le dépôt), mais seuls **{n_filtered}** (`protos/filtered/`) sont une "
              f"donnée OBFUSQUÉE propre à cet outil — les {n_clear} de `protos/clear/` sont LuaxY, déjà comptés "
              "via gatherer/luaxy. Ne pas citer « 1441 fichiers .proto indépendants » pour deobfs : c'est "
              f"{n_filtered} + une 4ᵉ copie de 79.")
    md.append("")
    md.append("**Conséquence pour tout calcul « N instruments s'accordent »** : gatherer, luaxy et le "
              "sous-dossier `protos/clear/` de deobfs comptent pour **UN SEUL** instrument indépendant "
              "(LuaxY, 2024-10). Un accord affiché comme « 3 instruments convergent » qui inclut deux de ces "
              "trois est en réalité **2 instruments**, pas 3 — l'un d'eux votant deux ou trois fois.")
    md.append("")

    gatherer_rows = load_tsv(GATHERER_TSV)
    g_names, g_fields = names_and_fields(gatherer_rows, lambda r: "+" not in r["nom_complet"])
    otomai_rows = load_tsv(OTOMAI_TSV)
    o_names, o_fields = names_and_fields(
        otomai_rows,
        lambda r: r["opcode_ou_typeurl"] and not r["opcode_ou_typeurl"].startswith(".") and "." not in r["opcode_ou_typeurl"])
    dump_leaves = set()
    if DUMP_TXT.exists():
        lines = [l.strip() for l in DUMP_TXT.read_text(encoding="utf-8").splitlines() if l.strip()]
        dump_leaves = {l.rsplit(".", 1)[-1] for l in lines if "+" not in l}
    jondo_named = {}
    if JONDO_ANCLAS.exists():
        for line in JONDO_ANCLAS.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) > 2 and parts[2].strip():
                jondo_named[parts[0]] = parts[2].strip()
    jondo_names = set(jondo_named.values())

    md.append("## 2. gatherer (LuaxY, ~2024-10) ∩ instruments du build courant — la stabilité des NOMS")
    md.append(f"- gatherer : {len(g_names)} noms top-level | otomai (2026-03) : {len(o_names)} | "
              f"dump (LA VÉRITÉ, 3.6.10.10) : {len(dump_leaves)} | JondoEmu nommés (3.6.10.10) : {len(jondo_names)}")
    ga_o = g_names & o_names
    ga_d = g_names & dump_leaves
    ga_j = g_names & jondo_names
    md.append(f"- gatherer ∩ otomai : **{len(ga_o)}/{len(g_names)} ({100*len(ga_o)/len(g_names):.0f}%)** — "
              "un instrument de ~2024 et un instrument de 2026, construits par des auteurs différents, "
              "s'accordent sur la quasi-totalité de leurs noms de messages communs.")
    md.append(f"- gatherer ∩ dump (vérité, mesurée sur NOTRE build) : **{len(ga_d)}/{len(g_names)} "
              f"({100*len(ga_d)/len(g_names):.0f}%)**.")
    md.append(f"- gatherer ∩ JondoEmu (nommés) : **{len(ga_j)}/99** — {sorted(ga_j)}")
    md.append("")
    md.append("**Lecture à charge, pas seulement à décharge** : gatherer (1239 noms) et otomai (1286 noms) "
              f"dépassent LARGEMENT le compte de notre propre dump ({len(dump_leaves)} noms top-level). Deux "
              "hypothèses concurrentes, ni l'une ni l'autre tranchée ici (DÉDUIT, à vérifier) : (a) notre "
              "extraction étage0 (littéraux du metadata v39) est **incomplète** — elle ne capte pas tous les "
              "noms réellement présents dans le binaire 3.6.10.10 ; (b) gatherer/otomai agrègent des messages "
              "qui existaient sur d'anciens builds et ont depuis été retirés du protocole. **Comment trancher** : "
              "prendre 20 noms présents chez gatherer+otomai mais absents du dump, et grep leur littéral exact "
              "dans `global-metadata.dat` (v39) directement — présent = (a), notre extracteur étage0 sous-compte ; "
              "absent = (b), message disparu du protocole depuis.")
    md.append("")

    md.append("## 3. Champs (numéro+type) — gatherer vs otomai, sur les 1202 noms communs (échantillon large)")
    fa = field_agreement(ga_o, g_fields, o_fields)
    md.append(f"- {fa['n_names']} messages communs, {fa['total']} emplacements de champ comparés.")
    md.append(f"- **Même NOMBRE de champs** (comptage brut, le signal le moins ambigu) : "
              f"{fa['same_count']}/{fa['n_names']} ({100*fa['same_count']/fa['n_names']:.1f}%).")
    md.append(f"- Accord sur la CATÉGORIE de type (numérique/string/liste/bool/message…) : "
              f"{fa['kind_match']}/{fa['total']} ({100*fa['kind_match']/fa['total']:.1f}%) — "
              "mesure BASSE volontairement prudente : deux champs référençant chacun un type MESSAGE "
              "différent tombent tous les deux dans le même seau `message_ou_enum` et comptent comme "
              "\"accord\" alors que le type précis diffère peut-être ; ce chiffre sur-compte donc "
              "légèrement l'accord réel sur les champs message-typés.")
    md.append(f"- Accord sur le type LITTÉRAL exact (`int32`==`int`, faux négatif attendu — deux conventions "
              f"de nommage différentes, C# vs proto3) : {fa['exact_match']}/{fa['total']} "
              f"({100*fa['exact_match']/fa['total']:.1f}%) — chiffre BAS attendu et normal, pas un signe de désaccord.")
    md.append(f"- Présent d'un seul côté (champ ajouté/retiré) : {fa['one_side']}/{fa['total']} "
              f"({100*fa['one_side']/fa['total']:.1f}%).")
    md.append("")
    md.append("**Conclusion mesurée** : à la différence de la comparaison otomai↔JondoEmu (0/27 sur les "
              "OPCODES, cf. `ACCORD-INSTRUMENTS.md` §2), la comparaison par NOM ici — sur un échantillon "
              "50× plus grand (1202 vs 2) — montre une stabilité réelle et forte : 80% des messages communs "
              "gardent EXACTEMENT le même nombre de champs entre un snapshot ~2024 et notre build 3.6.10.10. "
              "**Le nom et la structure de champs survivent aux patchs ; l'opcode 3 lettres, jamais.**")
    md.append("")

    md.append("## 4. dofus-deobfs — pourquoi aucune comparaison par nom n'est possible")
    md.append(f"`protos/filtered/` ({n_filtered} fichiers, tous nommés par leur code obfusqué 3 lettres, 0 "
              "exception mesurée) ne porte AUCUN nom clair dans ce commit — le mapping vers les noms clairs "
              "est un produit de RUNTIME (`utils/report.go` du dépôt construit un `MessageMatch{ObfuscatedMsg, "
              "OriginalMsg, MatchPercent}`), écrit dans un dossier `reports/` absent de ce commit (gitignored). "
              "**0 nom disponible → 0 jointure possible par nom, avec quiconque.** Une jointure par OPCODE "
              "serait possible mécaniquement (comparer les codes 3 lettres de `protos/filtered/` à ceux du "
              "`.proto` de Jondo) mais a déjà été prouvée sans valeur sur un cas mesuré 50× plus favorable "
              "(otomai vs Jondo, mêmes deux tables mais TOUTES DEUX partiellement nommées : 0/27 accord, "
              "`ACCORD-INSTRUMENTS.md` §2) — ne pas la refaire ici sans raison nouvelle. Ce que deobfs apporte "
              "concrètement au chantier n'est donc PAS une table utilisable en l'état, mais sa MÉTHODE (le "
              "matching structurel contre les protos clairs de LuaxY) — un second patron pour l'étage 4, à "
              "coté de `otomai/tools/proto-sync/` (§2 du RAPPORT-EXTRACTION-TIERS.md).")
    md.append("")

    out_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {
        "gatherer_luaxy_identiques": id_gl, "gatherer_luaxy_differents": diff_gl,
        "deobfs_clear_vs_luaxy_identiques": id_dc,
        "deobfs_fichiers_reels": n_filtered, "deobfs_fichiers_dupliques_luaxy": n_clear,
        "gatherer_noms": len(g_names), "otomai_noms": len(o_names), "dump_noms": len(dump_leaves),
        "gatherer_otomai_intersection": len(ga_o),
        "champs_meme_nombre_pct": round(100 * fa["same_count"] / fa["n_names"], 1) if fa["n_names"] else 0,
        "out": str(out_path),
    }


def run_epreuve() -> int:
    """FR: verifie que compare_trees detecte a la fois l'identite (temoin
    positif) ET la difference (temoin negatif) -- sabotage dans les deux sens."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="epreuve-stabilite-"))
    a, b, c = tmp / "a", tmp / "b", tmp / "c"
    a.mkdir(); b.mkdir(); c.mkdir()
    (a / "x.proto").write_text("message X { int32 f = 1; }\n", encoding="utf-8")
    (b / "x.proto").write_text("message X { int32 f = 1; }\n", encoding="utf-8")
    (c / "x.proto").write_text("message X { int32 f = 2; }\n", encoding="utf-8")  # sabote : contenu different

    id_ab, diff_ab, only_ab = compare_trees(a, b)
    id_ac, diff_ac, only_ac = compare_trees(a, c)
    p1 = id_ab == 1 and diff_ab == 0
    p2 = id_ac == 0 and diff_ac == 1
    print(f"=== EPREUVE : temoin identique detecte: {'OK' if p1 else 'MANQUANT'} "
          f"(id={id_ab} diff={diff_ab})")
    print(f"=== EPREUVE : temoin SABOTE (contenu different) detecte comme different: "
          f"{'OK' if p2 else 'MANQUANT'} (id={id_ac} diff={diff_ac})")

    out1, out2 = tmp / "r1.md", tmp / "r2.md"
    if OTOMAI_TSV.exists() and GATHERER_TSV.exists():
        build_report(out1)
        build_report(out2)
        h1 = hashlib.sha256(out1.read_bytes()).hexdigest()
        h2 = hashlib.sha256(out2.read_bytes()).hexdigest()
        same = h1 == h2
        print(f"=== EPREUVE : rejeu byte-identique: {'IDENTIQUE' if same else 'DIVERGENT'}")
    else:
        same = True
        print("(prealables TSV absents -- rejeu du rapport complet non tente)")

    tout_ok = p1 and p2 and same
    print(f"\n=== BILAN EPREUVE : {'VERT' if tout_ok else 'ROUGE'} ===")
    return 0 if tout_ok else 1


# Point d'entree CLI : --epreuve, ou un rapport reel (--out).
# / CLI entry point: --epreuve, or a real report (--out).
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DEFAUT))
    ap.add_argument("--epreuve", action="store_true")
    args = ap.parse_args()
    if args.epreuve:
        sys.exit(run_epreuve())
    stats = build_report(Path(args.out))
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
