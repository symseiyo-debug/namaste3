#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI : croiser.py — joint les tables handlers-*.tsv / messages-*.tsv par NOM.
Sortie : CROISEMENT-OPCODES.md (lisible) + croisement.tsv (brut).
0-LLM, stdlib seule (difflib pour le score de similarite Jondo, deterministe).
POURQUOI : les protocolId sont renumerotes entre versions -- 868/872 classes renumerotees
2.42->2.73, mesure par Tools/ProtoDiff273, cf. ARCHI-REFERENCE-JIVA.md §F.1 -- seul le nom relie
deux versions, et c'est une arete DEDUITE, jamais VERIFIEE par construction.
COMMENT LANCER : python3 croiser.py (lit messages-*.tsv/handlers-*.tsv dans son propre dossier,
    aucun argument).
GATE : aucune propre -- lecture visuelle du rapport CROISEMENT-OPCODES.md produit.
"""
from __future__ import annotations
import csv
import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIGNEE_2X = ["jiva", "giny", "ginycore", "oneair", "symbioz"]  # meme famille de protocole 2.x
JONDO = "jondo"


# Lit un TSV en liste de dict (colonnes = en-tete) -- [] si le fichier n'existe pas (emu absent).
# / Reads a TSV into a list of dicts (columns = header) -- [] if the file doesn't exist (missing emu).
def read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def load_messages() -> dict[str, dict[str, list[dict]]]:
    """emu -> {message_nom: [rows]} (une classe peut avoir >1 definition rare -> liste)."""
    out: dict[str, dict[str, list[dict]]] = {}
    for emu in LIGNEE_2X + [JONDO]:
        rows = read_tsv(HERE / f"messages-{emu}.tsv")
        by_name: dict[str, list[dict]] = {}
        for r in rows:
            by_name.setdefault(r["message_nom"], []).append(r)
        out[emu] = by_name
    return out


# Meme forme que load_messages() mais pour handlers-*.tsv (emu -> {message_nom: [rows]}).
# / Same shape as load_messages() but for handlers-*.tsv (emu -> {message_nom: [rows]}).
def load_handlers() -> dict[str, dict[str, list[dict]]]:
    out: dict[str, dict[str, list[dict]]] = {}
    for emu in LIGNEE_2X + [JONDO]:
        rows = read_tsv(HERE / f"handlers-{emu}.tsv")
        by_name: dict[str, list[dict]] = {}
        for r in rows:
            by_name.setdefault(r["message_nom"], []).append(r)
        out[emu] = by_name
    return out


def croiser_2x(messages: dict, handlers: dict) -> tuple[list[dict], dict]:
    """Joint la lignee 2.x par nom exact (meme convention de nommage cote AS3/generateur
    pour jiva/giny/ginycore/oneair/symbioz -- mesure : Giny et Symbioz partagent le meme
    chemin d'entree client `com/ankamagames/dofus/network/messages/` depuis 8 ans, cf.
    ARCHI-REFERENCE-GINY.md §A.4 -- le nom de classe genere est stable entre ces 5 outils)."""
    present_emus = [e for e in LIGNEE_2X if messages.get(e)]
    all_names: set[str] = set()
    for e in present_emus:
        all_names |= set(messages[e].keys())

    rows = []
    n_total = len(present_emus)
    counts = {"INVARIANT": 0, "PARTIEL": 0, "DIVERGENT": 0}
    for name in sorted(all_names):
        presence = [e for e in present_emus if name in messages[e]]
        with_handler = [e for e in present_emus if name in handlers.get(e, {})]
        n = len(presence)
        if n == n_total:
            tag = "INVARIANT"
        elif n == 1:
            tag = "DIVERGENT"
        else:
            tag = "PARTIEL"
        counts[tag] += 1
        rows.append({
            "message_nom": name,
            "presence_2x": ";".join(presence),
            "nb_emus_2x": str(n),
            "sur_n_total": str(n_total),
            "handler_2x": ";".join(with_handler),
            "tag": tag,
        })
    return rows, {"present_emus": present_emus, "n_total": n_total, "counts": counts,
                  "total_noms_2x": len(all_names)}


def lier_jondo(messages: dict, handlers: dict, noms_2x: set[str], seuil: float = 0.55):
    """Lien Jondo -> lignee 2.x par similarite de NOM SEMANTIQUE (nom propose, cf. anclas
    tsv), DEDUIT -- jamais VERIFIE. difflib.SequenceMatcher : deterministe, stdlib, 0-LLM."""

    # Retire un suffixe conventionnel (Message/Request/Answer/Event...) pour comparer le radical semantique.
    # / Strips a conventional suffix (Message/Request/Answer/Event...) to compare the semantic root.
    def norm(s: str) -> str:
        s = s.lower()
        for suf in ("requestmessage", "message", "request", "answer", "event"):
            if s.endswith(suf) and len(s) > len(suf) + 2:
                s = s[: -len(suf)]
        return s

    # Le nom propose vit dans handlers-jondo.tsv sous 'message_nom' (colonne nom_propose de
    # l'anclas tsv, cf. extraire_handlers.py), l'opcode sous 'protocol_id'.
    candidats: dict[str, str] = {}  # nom_propose (jondo) -> opcode
    for name, hrows in handlers.get(JONDO, {}).items():
        if name:
            for hr in hrows:
                candidats[name] = hr.get("protocol_id", "")

    liens = []
    norm_2x = {n: norm(n) for n in noms_2x}
    for jname, opcode in sorted(candidats.items()):
        jn = norm(jname)
        best_name, best_score = "", 0.0
        for n2x, n2x_norm in norm_2x.items():
            score = difflib.SequenceMatcher(None, jn, n2x_norm).ratio()
            if score > best_score:
                best_score, best_name = score, n2x
        if best_score >= seuil:
            liens.append({"jondo_opcode": opcode, "jondo_nom_propose": jname,
                          "lien_2x_nom": best_name, "score": f"{best_score:.2f}"})
    return liens


# Ecrit CROISEMENT-OPCODES.md : stats 2.x, top INVARIANTS/DIVERGENTS, liens Jondo DEDUITS.
# / Writes CROISEMENT-OPCODES.md: 2.x stats, top INVARIANTS/DIVERGENTS, DEDUCED Jondo links.
def write_report(rows_2x: list[dict], stats_2x: dict, liens_jondo: list[dict],
                  hstats: dict) -> None:
    md = []
    md.append("# CROISEMENT-OPCODES.md — jointure par nom, deterministe 0-LLM\n")
    md.append(
        "> Jointure par NOM (les protocolId sont renumerotes entre versions -- 868/872 "
        "classes renumerotees 2.42->2.73 mesure par ProtoDiff273, cf. ARCHI-REFERENCE-JIVA.md "
        "§F.1). Le nom est une arete DEDUITE (deux classes de meme nom dans deux depots "
        "distincts sont supposees designer le meme message protocolaire -- pas verifie champ "
        "par champ ici, c'est le travail de lecture qui reste, cf. RAPPORT-INDEX.md).\n"
    )
    p = stats_2x["present_emus"]
    md.append(f"## Lignee 2.x — {len(p)} emus croises : {', '.join(p)}\n")
    md.append(f"- Noms de message distincts (union) : **{stats_2x['total_noms_2x']}**")
    for tag, n in stats_2x["counts"].items():
        md.append(f"- {tag} : **{n}**")
    md.append("")

    inv = [r for r in rows_2x if r["tag"] == "INVARIANT"]
    div = [r for r in rows_2x if r["tag"] == "DIVERGENT"]
    # Tri par nb d'emus AVEC handler (desc) puis nom : sinon les 20 premiers alphabetiques
    # sont tous des classes de base Abstract* jamais directement dispatchees (mesure : 0
    # handler sur les 20 premiers en ordre alphabetique pur) -- moins utile a lire en premier
    # qu'un message reellement au coeur du chemin critique.
    inv_sorted = sorted(inv, key=lambda r: (-len([e for e in r["handler_2x"].split(";") if e]),
                                             r["message_nom"]))
    div_sorted = sorted(div, key=lambda r: (0 if r["handler_2x"] else 1, r["message_nom"]))
    md.append(f"### Top {min(20, len(inv))} INVARIANTS (presents dans les {stats_2x['n_total']} emus 2.x, tries par couverture handler)\n")
    for r in inv_sorted[:20]:
        md.append(f"- `{r['message_nom']}` — handler cote : {r['handler_2x'] or '(aucun)'}")
    md.append("")
    md.append(f"### Top {min(20, len(div))} DIVERGENTS (presents dans 1 seul emu, avec handler en premier)\n")
    for r in div_sorted[:20]:
        marque = " (avec handler)" if r["handler_2x"] else ""
        md.append(f"- `{r['message_nom']}` — seul {r['presence_2x']}{marque}")
    md.append("")

    md.append("## JondoEmu 3.0 — lien DEDUIT par similarite de nom semantique\n")
    md.append(
        f"- Candidats Jondo avec nom propose : **{len(liens_jondo)}** liens trouves "
        f"(seuil difflib >= 0.55, stdlib, deterministe).\n"
    )
    for l in sorted(liens_jondo, key=lambda x: -float(x["score"]))[:20]:
        md.append(f"- `{l['jondo_opcode']}` ({l['jondo_nom_propose']}) ~ `{l['lien_2x_nom']}` "
                   f"— score {l['score']} — **DEDUIT**")
    md.append("")

    md.append("## Handlers presents/absents par emu (sur les messages INVARIANTS)\n")
    for e in stats_2x["present_emus"]:
        n_msg_invariant_avec_handler = sum(1 for r in inv if e in r["handler_2x"].split(";"))
        md.append(f"- {e} : {n_msg_invariant_avec_handler}/{len(inv)} messages invariants "
                   f"ont un handler cote {e}")

    (HERE / "CROISEMENT-OPCODES.md").write_text("\n".join(md) + "\n", encoding="utf-8")


# Point d'entree : charge messages/handlers, croise la lignee 2.x, lie Jondo, ecrit les 2 sorties.
# / Entry point: loads messages/handlers, crosses the 2.x lineage, links Jondo, writes both outputs.
def main():
    messages = load_messages()
    handlers = load_handlers()
    rows_2x, stats_2x = croiser_2x(messages, handlers)

    noms_2x = set()
    for e in stats_2x["present_emus"]:
        noms_2x |= set(messages[e].keys())
    liens_jondo = lier_jondo(messages, handlers, noms_2x)

    # croisement.tsv : jointure 2.x pure + les liens jondo en lignes annexes (meme fichier,
    # colonnes supplementaires vides pour la partie qui ne s'applique pas -- pas 2 fichiers,
    # pour que "croiser.py -> CROISEMENT-OPCODES.md + croisement.tsv" (brief) tienne en 1 TSV).
    header = ["message_nom", "presence_2x", "nb_emus_2x", "sur_n_total", "handler_2x", "tag",
              "jondo_opcode_deduit", "jondo_score"]
    jondo_by_2x_name: dict[str, list[dict]] = {}
    for l in liens_jondo:
        jondo_by_2x_name.setdefault(l["lien_2x_nom"], []).append(l)

    with (HERE / "croisement.tsv").open("w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(header) + "\n")
        for r in rows_2x:
            liens = jondo_by_2x_name.get(r["message_nom"], [])
            jopcodes = ";".join(l["jondo_opcode"] for l in liens)
            jscores = ";".join(l["score"] for l in liens)
            f.write("\t".join([r["message_nom"], r["presence_2x"], r["nb_emus_2x"],
                                r["sur_n_total"], r["handler_2x"], r["tag"], jopcodes,
                                jscores]) + "\n")

    write_report(rows_2x, stats_2x, liens_jondo, {})
    print(f"[croiser] {stats_2x['counts']} sur {stats_2x['total_noms_2x']} noms "
          f"({stats_2x['n_total']} emus 2.x : {', '.join(stats_2x['present_emus'])})")
    print(f"[croiser] liens jondo deduits : {len(liens_jondo)}")


if __name__ == "__main__":
    main()
