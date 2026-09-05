#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUOI / WHAT
    Récolte les noms que l'obfuscateur LAISSE FUIR à l'intérieur des classes qu'il a pourtant
    renommées, et s'en sert pour baptiser les messages protobuf du client 3.6.10.11.
    Harvests the names the obfuscator LEAKS inside the classes it did rename, and uses them to
    name the client's protobuf messages.

POURQUOI / WHY  (écrit le 2026-09-05 / written 2026-09-05)
    Le compilateur C# fabrique, pour chaque `async`, chaque lambda et chaque fermeture, un type
    imbriqué qu'il baptise d'après la MÉTHODE D'ORIGINE : `<WaitForAddingObject>d__24`. Le runtime
    les cherche par nom, donc l'obfuscateur n'y touche pas. La classe `ehl` ne dit rien ; sa
    machine d'état `_WaitForAddingObject_d__24`, si.
    Mieux que ce qui était demandé : cette machine d'état porte les PARAMÈTRES de la méthode en
    CHAMPS TYPÉS. `_WaitForAddingObject_d__24` a un champ `public itl message;` — le message
    protobuf concerné est nommé directement, pas déduit d'un voisinage.
    Better than asked: the state machine carries the method's parameters as TYPED FIELDS, so the
    protobuf message is named outright rather than inferred from neighbourhood.

    Notre matcher v3 avait mesuré « 0/2206 messages avec porteur en clair » : il regardait le nom
    de la CLASSE porteuse, jamais ses types imbriqués. L'angle mort était dans l'instrument.

COMMENT / HOW
    1. `il2cpp.cs` (1 081 733 lignes) est lu EN FLUX, avec une pile d'imbrication par tabulations.
       Le dump a assaini `<Nom>d__24` en `_Nom_d__24` (`<` et `>` → `_`) : c'est cette forme
       qu'on reconnaît. / The dump sanitises `<Name>d__24` into `_Name_d__24`.
    2. Pour chaque classe racine au nom obfusqué (jeton minuscule de 2 à 4 lettres) on récolte :
       les noms fuités (types imbriqués et méthodes lambda), les interfaces en clair, et les
       messages protobuf vus en CHAMPS de ses machines d'état.
    3. Croisement avec `contexte-appels.jsonl` (qui cite quel message) pour les indices indirects.
    4. Baptême proposé contre `nombres_reales_3.6.10.10.tsv` de Jondo — la liste FERMÉE des noms
       réels, dont on a mesuré que les 513 sont présents dans NOTRE global-metadata.dat.

GATE
    `--epreuve` : témoin positif (une classe connue rend ses noms attendus), témoin négatif (une
    classe en clair n'est jamais comptée comme trahie), rejeu byte-identique des deux sorties.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ICI = Path(__file__).resolve().parent
BASE = ICI.parent                                    # internal/
IL2CPP = BASE.parent / "internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs"
CONTEXTE = BASE / "matcher/contexte-appels.jsonl"
SIGNATURES = BASE / "matcher/signatures-obfusquees.jsonl"
NOMS_REELS = Path("refs/JondoEmu/datos/nombres_reales_3.6.10.10.tsv")

# Un jeton obfusqué : 2 à 4 minuscules, rien d'autre. / An obfuscated token: 2-4 lowercase letters.
# Les mots-clés C# ont exactement la même forme (`int`, `bool`, `void`…) : sans cette liste,
# `public int __1__state;` fabrique un faux message nommé « int ». Mesuré le 2026-09-05.
# C# keywords share the very same shape, so without this list `int` becomes a fake message.
_MOTS_CS = {"int", "bool", "byte", "char", "long", "uint", "void", "this", "base", "null",
            "true", "false", "new", "out", "ref", "in", "is", "as", "do", "if", "for", "try",
            "var", "get", "set", "add", "T", "K", "V"}
_RE_JETON_FORME = re.compile(r"^[a-z]{2,4}$")


def RE_JETON(nom: str):  # noqa: N802 — gardé en appelable pour ne rien changer aux appels
    """Vrai jeton obfusqué : la forme ET pas un mot-clé C#. / Shape AND not a C# keyword."""
    return _RE_JETON_FORME.match(nom) and nom not in _MOTS_CS

RE_CLASSE = re.compile(
    r"^(?P<tabs>\t*)(?:(?:public|private|internal|protected)\s+)?"
    r"(?:(?:sealed|abstract|static|readonly|partial|ref)\s+)*"
    r"(?P<genre>class|struct|interface|enum)\s+(?P<nom>[^\s:<]+)(?:<[^>]*>)?"
    r"(?:\s*:\s*(?P<bases>.+?))?\s*//\s*TypeDefIndex:\s*(?P<idx>\d+)")

# `_WaitForAddingObject_d__24`, `_DoBind0Async_b__0`, `_Foo_c__DisplayClass3_0`, et la machine
# d'état d'une LAMBDA async `<<Method>b__11_0>d` que le dump rend `__Method_b__11_0_d` : DEUX
# soulignés en tête. Exiger un seul en ratait 16 formes recensées. Mesuré le 2026-09-05.
# Also the state machine of an async LAMBDA, which the dump renders with TWO leading underscores;
# demanding exactly one missed those.
RE_FUITE = re.compile(
    r"^_{1,2}(?P<nom>[A-Za-z][A-Za-z0-9]{2,}[A-Za-z0-9_]*?)_(?:d__\d|b__\d|c__DisplayClass\d)")
RE_CHAMP = re.compile(
    r"^\t+(?:public|private|internal|protected)\s+(?:(?:static|readonly|const)\s+)*"
    r"(?P<type>[A-Za-z_][\w.]*)\s+(?P<nom>[A-Za-z_]\w*);")
RE_METHODE = re.compile(r"^\t+.*?(?P<nom>_{1,2}[A-Za-z][A-Za-z0-9_]*?_(?:b__\d|d__\d)[\w]*)\s*\(")
RE_IMAGE = re.compile(r"^// Image \d+: (?P<dll>\S+) - Assembly:.*? - Types (?P<a>\d+)-(?P<b>\d+)")

# Mots du protocole : un nom fuité qui en contient un est directement exploitable.
MOTS_PROTOCOLE = ("Map", "Character", "Fight", "Chat", "Inventory", "Item", "Guild", "Alliance",
                  "Party", "Exchange", "Npc", "Spell", "Quest", "Server", "Account", "Friend",
                  "Zaap", "Dungeon", "Mount", "Pet", "House", "Job", "Craft", "Market", "Bank",
                  "Trade", "Emote", "Achievement", "Breach", "Actor", "Entity", "Move", "Teleport",
                  "Login", "Auth", "Selection", "Welcome", "Interactive", "Element", "Ally")


def assemblies(chemin: Path) -> list[tuple[int, int, str]]:
    """Plages TypeDefIndex → DLL, lues dans l'en-tête. / TypeDefIndex ranges to DLL, from header."""
    # Les 141 lignes « // Image » ne forment PAS un bloc d'en-tête : Il2CppInspector les sème
    # jusqu'à la ligne 9953, entre des déclarations. S'arrêter à la première ligne qui n'est pas
    # un commentaire n'en lisait qu'UNE sur 141, et tout tombait en DLL « ? ».
    # Mesuré et corrigé le 2026-09-05.
    # The 141 "// Image" lines are NOT a header block; stopping at the first non-comment line read
    # only 1 of 141 and every class fell back to DLL "?".
    plages = []
    with chemin.open(encoding="utf-8", errors="replace") as fh:
        for no, ligne in enumerate(fh, 1):
            if no > 20000:
                break
            if ligne.startswith("// Image "):
                m = RE_IMAGE.match(ligne)
                if m:
                    plages.append((int(m["a"]), int(m["b"]), m["dll"]))
    return sorted(plages)


def dll_de(idx: int, plages: list[tuple[int, int, str]]) -> str:
    for a, b, dll in plages:
        if a <= idx <= b:
            return dll
    return "?"


def recolter(chemin: Path) -> dict[str, dict]:
    """
    Une passe en flux : pour chaque classe RACINE obfusquée, ce qui a fui d'elle.
    One streaming pass: for every obfuscated ROOT class, everything that leaked out of it.
    """
    # Contrairement aux trois chargeurs secondaires (charger_reels/messages/porteurs), l'absence
    # d'IL2CPP n'est PAS un cas à dégrader en silence vers un résultat vide : `chemin` est l'ENTRÉE
    # dont ce script mesure quelque chose. Un dict vide se lirait comme « 0 fuite trouvée » — un
    # faux négatif — au lieu de « je n'ai pas pu mesurer ». Refus nommé, mesuré le 05/09.
    # Unlike the three secondary loaders, a missing IL2CPP is not something to degrade silently
    # into an empty result: `chemin` is the INPUT this script measures. An empty dict would read
    # as "0 leaks found" — a false negative — instead of "I couldn't measure". Named refusal.
    if not chemin.exists():
        raise FileNotFoundError(
            f"IL2CPP absent / IL2CPP missing: {chemin} — rien à récolter, "
            f"pas un résultat vide qui se ferait passer pour une mesure "
            f"/ nothing to harvest, not an empty result posing as a measurement")

    plages = assemblies(chemin)
    trahies: dict[str, dict] = {}
    # Pile des classes ouvertes : (profondeur, nom, nom fuité si c'en est une).
    # Sans la profondeur, en sortant d'une machine d'état on continue d'attribuer les champs de la
    # classe parente à cette machine. Défaut mesuré et corrigé le 2026-09-05.
    # Stack of open classes; without the depth, fields of the parent class keep being credited to
    # the last state machine after leaving it.
    pile: list[tuple[int, str, str | None]] = []
    racine: str | None = None

    def fuite_a(prof: int) -> str | None:
        """Le nom fuité de la classe ouverte à cette profondeur. / Leaked name at that depth."""
        for p, _n, f in reversed(pile):
            if p == prof:
                return f
        return None

    with chemin.open(encoding="utf-8", errors="replace") as fh:
        for no, ligne in enumerate(fh, 1):
            m = RE_CLASSE.match(ligne)
            if m:
                prof = len(m["tabs"])
                while pile and pile[-1][0] >= prof:
                    pile.pop()
                nom, idx = m["nom"], int(m["idx"])
                if prof == 0:
                    racine = nom if RE_JETON(nom) else None
                    pile.append((0, nom, None))
                    if racine:
                        bases = [b.strip() for b in (m["bases"] or "").split(",") if b.strip()]
                        claires = [b for b in bases if not RE_JETON(b)]
                        trahies.setdefault(racine, {
                            "typedef_index": idx, "ligne": no,
                            "dll": dll_de(idx, plages),
                            "fuites": [], "interfaces": claires, "messages": [],
                            "champs_par_fuite": defaultdict(list)})
                    continue
                f = RE_FUITE.match(nom)
                nom_fuite = f["nom"] if f else None
                pile.append((prof, nom, nom_fuite))
                if racine and nom_fuite and nom_fuite not in trahies[racine]["fuites"]:
                    trahies[racine]["fuites"].append(nom_fuite)
                continue

            if not racine:
                continue

            # Un champ typé par un jeton, dans une machine d'état : le message est NOMMÉ.
            c = RE_CHAMP.match(ligne)
            if c and RE_JETON(c["type"]):
                jeton = c["type"]
                if jeton != racine and jeton not in trahies[racine]["messages"]:
                    trahies[racine]["messages"].append(jeton)
                # La classe englobante d'un champ est celle d'un cran moins profond.
                porteuse = fuite_a(len(ligne) - len(ligne.lstrip("\t")) - 1)
                if porteuse and jeton != racine:
                    trahies[racine]["champs_par_fuite"][porteuse].append(jeton)
                continue

            # Une lambda garde le nom de sa méthode d'origine, même sans type imbriqué.
            mm = RE_METHODE.search(ligne)
            if mm:
                f = RE_FUITE.match(mm["nom"])
                if f and f["nom"] not in trahies[racine]["fuites"]:
                    trahies[racine]["fuites"].append(f["nom"])

    return {k: v for k, v in trahies.items() if v["fuites"] or v["interfaces"]}


# ── Baptême / Naming ──────────────────────────────────────────────────────────────────────────
def mots(nom: str) -> list[str]:
    """
    Découpe un CamelCase en mots, singulier normalisé.
    Sans la normalisation du pluriel, le nom fuité `…HavenBagFurnituresEvent` ne rejoignait pas
    le nom réel `HavenBagFurnitureOpenRequest` (« Furnitures » ≠ « Furniture ») et la proposition
    partait sur `HavenBagDailyLotteryEvent`. Mesuré le 2026-09-05.
    Splits CamelCase into words with plural normalisation; without it a leaked "Furnitures" missed
    the real "Furniture" and the proposal drifted to the wrong message.
    """
    bruts = re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", nom)
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            for w in bruts]


BRUIT = {"wait", "for", "on", "do", "process", "handle", "async", "task", "get", "set", "the",
         "and", "with", "from", "to", "run", "start", "stop", "update", "init", "load"}


def noyau(nom: str) -> list[str]:
    """Les mots porteurs de sens d'un nom fuité. / The meaning-bearing words of a leaked name."""
    return [w for w in mots(nom) if w.lower() not in BRUIT and len(w) > 2]


def rarete(reels: list[str]) -> dict[str, float]:
    """
    Poids d'un mot = sa rareté dans les 513 noms réels.
    « Event » est dans un nom sur trois et ne désigne rien ; « Furniture » désigne un message.
    Compter les mots communs à poids égal mettait `…HavenBagFurnitures…` à ÉGALITÉ entre
    `HavenBagFurnitureOpenRequest` et `HavenBagDailyLotteryEvent`, et l'ordre du fichier tranchait.
    Weighting by rarity: "Event" appears in a third of the names and designates nothing, whereas
    "Furniture" designates one message. Equal weighting let file order break a tie.
    """
    freq: dict[str, int] = defaultdict(int)
    for r in reels:
        for w in set(mots(r)):
            freq[w.lower()] += 1
    n = max(1, len(reels))
    return {w: n / (1.0 + c) for w, c in freq.items()}


def proposer(fuites: list[str], reels: list[str],
             poids: dict[str, float]) -> tuple[str, str, int, int]:
    """
    Propose un nom réel pour un message, d'après les noms fuités qui le touchent.
    Le nom réel doit partager AU MOINS DEUX mots porteurs avec un nom fuité : un seul mot commun
    (« Map ») désigne des dizaines de messages et ne prouve rien. Rend aussi le nombre de
    candidats EX ÆQUO — une proposition à égalité n'est pas une proposition.
    A real name must share AT LEAST TWO meaningful words; also returns how many candidates tied,
    because a tied proposal is not a proposal.
    """
    best, best_src, best_n, best_p, exaequo = "", "", 0, 0.0, 0
    for f in fuites:
        nf = {w.lower() for w in noyau(f)}
        if len(nf) < 2:
            continue
        for r in reels:
            nr = {w.lower() for w in mots(r)}
            communs = nf & nr
            if len(communs) < 2:
                continue
            p = sum(poids.get(w, 1.0) for w in communs)
            if p > best_p + 1e-9:
                best, best_src, best_n, best_p, exaequo = r, f, len(communs), p, 1
            elif abs(p - best_p) <= 1e-9 and r != best:
                exaequo += 1
    return best, best_src, best_n, exaequo


def charger_reels() -> list[str]:
    if not NOMS_REELS.exists():
        return []
    out = []
    for l in NOMS_REELS.read_text(encoding="utf-8").splitlines():
        if l.strip() and not l.startswith("#"):
            out.append(l.split("\t")[0].strip())
    return [x for x in out if x]


def charger_messages() -> dict[str, int]:
    """Les 2 206 messages protobuf et leur TypeDefIndex. / The 2,206 protobuf messages."""
    out = {}
    if SIGNATURES.exists():
        for l in SIGNATURES.read_text(encoding="utf-8").splitlines():
            if l.strip():
                o = json.loads(l)
                out[o["obf_name"]] = o["typedef_index"]
    return out


def charger_porteurs() -> tuple[dict[str, set[str]], dict[str, int]]:
    """
    message → classes qui le citent, et pour chaque classe COMBIEN de messages elle cite.
    Le second chiffre est ce qui sépare un indice d'un bruit : une classe qui cite 80 messages
    ne nomme aucun d'entre eux, une classe qui en cite deux les désigne.
    message → citing classes, plus how many messages each class cites. A class citing 80 messages
    names none of them; a class citing two points at them.
    """
    out: dict[str, set[str]] = defaultdict(set)
    portee: dict[str, int] = defaultdict(int)
    if CONTEXTE.exists():
        for l in CONTEXTE.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            o = json.loads(l)
            for c in {p.get("carrying_class") for p in o.get("porteurs", [])}:
                if c and c != o["obf_token"]:
                    out[o["obf_token"]].add(c)
                    portee[c] += 1
    return out, portee


def ecrire(trahies: dict, sortie: Path) -> dict:
    """Écrit les deux TSV et rend les chiffres. / Writes both TSVs and returns the numbers."""
    messages = charger_messages()
    porteurs, portee = charger_porteurs()
    reels = charger_reels()
    poids = rarete(reels)
    SEUIL_SPECIFIQUE = 5      # au-delà, le porteur ne désigne plus rien / beyond this, no signal

    lignes = ["token\ttypedef_index\tdll\tligne\tnb_fuites\tnoms_fuites\tinterfaces_claires\t"
              "messages_touches"]
    for t in sorted(trahies):
        v = trahies[t]
        lignes.append("\t".join([
            t, str(v["typedef_index"]), v["dll"], str(v["ligne"]), str(len(v["fuites"])),
            ",".join(v["fuites"]), ",".join(v["interfaces"]), ",".join(v["messages"])]))
    (sortie / "classes-trahies.tsv").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    # message → indices
    directs: dict[str, list[str]] = defaultdict(list)     # nom de méthode qui PORTE le message
    for t, v in trahies.items():
        for fuite, jetons in v["champs_par_fuite"].items():
            for j in jetons:
                if j in messages:
                    directs[j].append(f"{t}:{fuite}")

    out = ["message_obf\ttypedef_index\tscore\tindices_directs\tporteurs_specifiques\t"
           "porteurs_trahis\tnoms_fuites_des_porteurs\tmot_protocole\tnom_propose\tfuite_source\t"
           "mots_communs\tcandidats_exaequo"]
    nommes = proposes = specifiques = 0
    resume: dict[str, dict] = {}
    for msg in sorted(messages):
        d = directs.get(msg, [])
        pts = sorted(porteurs.get(msg, set()) & trahies.keys())
        spec = [p for p in pts if portee.get(p, 999) <= SEUIL_SPECIFIQUE]
        # Seuls les porteurs SPÉCIFIQUES nourrissent la proposition de nom : un porteur qui cite
        # quatre-vingts messages apporterait ses quatre-vingts noms fuités à chacun d'eux.
        # Only SPECIFIC carriers feed the naming, otherwise one carrier pollutes all its messages.
        fuites: list[str] = []
        for p in spec:
            fuites += trahies[p]["fuites"]
        for x in d:
            fuites.append(x.split(":", 1)[1])
        fuites = sorted(set(fuites))
        if not d and not pts:
            continue
        nommes += 1
        if d or spec:
            specifiques += 1
        score = 3 * len(d) + 2 * len(spec) + len(pts)
        mot = next((w for w in MOTS_PROTOCOLE for f in fuites if w in f), "")
        nom, src, n, exaequo = proposer(fuites, reels, poids)
        if nom:
            proposes += 1
        resume[msg] = {"score": score, "directs": d, "specifiques": spec,
                       "nb_porteurs": len(pts), "nom_propose": nom, "mot": mot}
        out.append("\t".join([
            msg, str(messages[msg]), str(score), ",".join(d), ",".join(spec), ",".join(pts),
            ",".join(fuites[:12]), mot, nom, src, str(n), str(exaequo)]))
    (sortie / "messages-nommes-par-fuite.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")

    # Ventilation par DLL : Jondo compte 377 classes trahies sur `Core.dll` SEUL. Comparer notre
    # total tous assemblages confondus à son chiffre comparerait deux populations différentes.
    # Per-DLL split: Jondo's 377 is Core.dll ONLY; comparing our all-assembly total would compare
    # two different populations.
    par_dll: dict[str, int] = defaultdict(int)
    for v in trahies.values():
        par_dll[v["dll"]] += 1

    # Les 8 opcodes du chemin critique que le matcher laissait « à nommer par capture ».
    # The 8 critical-path opcodes the matcher had left to be named by a live capture.
    huit = ("mgq", "mgt", "hpd", "krs", "kqp", "ksl", "krt", "hjk")
    etat_huit = {t: (resume.get(t) or {"score": 0, "directs": [], "specifiques": [],
                                       "nb_porteurs": 0, "nom_propose": "", "mot": ""})
                 for t in huit}

    return {"classes_trahies": len(trahies),
            "classes_trahies_par_dll": dict(sorted(par_dll.items(), key=lambda x: -x[1])[:8]),
            "classes_trahies_Core_dll": par_dll.get("Core.dll", 0),
            "messages_total": len(messages),
            "messages_avec_indice": nommes,
            "messages_avec_indice_specifique": specifiques,
            "messages_avec_indice_direct": len(directs),
            "messages_avec_nom_propose": proposes,
            "noms_reels_charges": len(reels),
            "opcodes_chemin_critique_avec_indice": sum(1 for v in etat_huit.values()
                                                       if v["score"] > 0),
            "opcodes_chemin_critique": etat_huit}


def epreuve(sortie: Path) -> int:
    """GATE : témoin positif, témoin négatif, rejeu. / Gate: positive, negative, replay."""
    verts = []
    trahies = recolter(IL2CPP)

    # 1. TÉMOIN POSITIF : `ehl` doit rendre les noms lus À LA MAIN dans le dump.
    v = trahies.get("ehl", {})
    attendu = "WaitForAddingObject"
    ok1 = attendu in v.get("fuites", []) and "itl" in v.get("messages", [])
    verts.append(ok1)
    print(f"[1] TÉMOIN POSITIF ehl : {'VERT' if ok1 else 'ROUGE'} — "
          f"fuites={len(v.get('fuites', []))} dont '{attendu}'={attendu in v.get('fuites', [])}, "
          f"messages touchés={v.get('messages', [])[:6]}")

    # 2. TÉMOIN NÉGATIF : une classe au nom CLAIR ne doit jamais figurer comme trahie.
    clairs = [t for t in trahies if not RE_JETON(t)]
    ok2 = not clairs
    verts.append(ok2)
    print(f"[2] TÉMOIN NÉGATIF (aucune classe en clair retenue) : "
          f"{'VERT' if ok2 else 'ROUGE'} — {len(clairs)} intrus {clairs[:5]}")

    # 3. REJEU byte-identique des deux sorties.
    a = ecrire(trahies, sortie)
    t1 = (sortie / "classes-trahies.tsv").read_bytes()
    m1 = (sortie / "messages-nommes-par-fuite.tsv").read_bytes()
    ecrire(recolter(IL2CPP), sortie)
    ok3 = (t1 == (sortie / "classes-trahies.tsv").read_bytes()
           and m1 == (sortie / "messages-nommes-par-fuite.tsv").read_bytes())
    verts.append(ok3)
    print(f"[3] REJEU byte-identique : {'VERT' if ok3 else 'ROUGE'} — "
          f"{len(t1)} + {len(m1)} octets")
    print(f"\nGATE : {sum(verts)}/3 verts\n{json.dumps(a, ensure_ascii=False, indent=2)}")
    return 0 if all(verts) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epreuve", action="store_true")
    ap.add_argument("--sortie", default=str(ICI))
    args = ap.parse_args()
    sortie = Path(args.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    if args.epreuve:
        return epreuve(sortie)
    bilan = ecrire(recolter(IL2CPP), sortie)
    (sortie / "mesure-fuites.json").write_text(
        json.dumps(bilan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
