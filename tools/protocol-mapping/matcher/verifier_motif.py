#!/usr/bin/env python3
"""
verifier_motif.py — Étage 1 (Namaste 3), matcher v1.

QUOI : garde exécutable du motif « const N précède immédiatement son champ porteur »,
    rejouée sur 3 classes Google.Protobuf EN CLAIR au schéma connu.
POURQUOI (04/09/2026, demandé par l'ordre de mission) : avant de faire confiance à
    `extraire_signatures.py` sur les 2206 classes obfusquées (schéma inconnu), le même
    mécanisme doit d'abord réussir sur 3 classes dont on CONNAÎT la bonne réponse.
COMMENT LANCER : `python3 verifier_motif.py` (appelé automatiquement par
    `extraire_signatures.py` avant l'extraction ; rejouable seul).
GATE : les 3 témoins (Any, Api, Duration) doivent tous rendre PASS — "3/3 ✅" — sinon
    `extraire_signatures.py` s'arrête (`sys.exit(3)`), la garde AMONT.

FR : rejoue le PAIRAGE const→champ avec les MÊMES primitives que le parseur principal
     (`CONST_RE`, `parse_backing_line`, `SKIP_BACKING_*`, `MAX_FIELD_NUMBER`) sur 3
     classes EN CLAIR dont le schéma protobuf réel est connu et vérifiable à l'œil :
     `Google.Protobuf.WellKnownTypes.Any`, `Api`, `Duration` (mêmes noms, non obfusqués,
     ailleurs dans le même `cs/il2cpp.cs`). Imprime PASS/FAIL par classe, jamais un
     verdict global muet.
     Trouvaille en cours de route : `Duration` porte des `public const int` qui ne sont
     PAS des numéros de champ (`NanosecondsPerSecond = 1000000000`,
     `NanosecondsPerTick = 100`) — un vestige de code Google écrit à la main, pas généré
     par protoc. `extraire_signatures.py` s'en protège via `MAX_FIELD_NUMBER` (grande
     valeur écartée) et la garde de section (`// Fields` uniquement) — les deux gardes
     sont rejouées ici à l'identique pour que ce témoin teste le VRAI comportement.
EN : replays the const→field pairing with the SAME primitives as the main parser on 3
     CLEAR classes with a known, eyeball-verifiable real protobuf schema. Found along
     the way: `Duration` carries `public const int` that are NOT field numbers — a
     hand-written Google vestige, not protoc-generated. The main parser guards against
     it (`MAX_FIELD_NUMBER` + section gate); both guards are replayed here identically.

Rejouable seul : `python3 verifier_motif.py`. Stdlib seule. 0 LLM.
"""
import re
import sys

from extraire_signatures import (
    CS_PATH, CONST_RE, SECTION_RE, CLOSE_RE, MAX_FIELD_NUMBER,
    SKIP_BACKING_PREFIXES, SKIP_BACKING_EXACT, parse_backing_line, log,
)

# Témoins EN CLAIR du motif — le schéma réel de ces 3 classes Google.Protobuf est
# public et stable, vérifiable indépendamment de ce dump.
WITNESS_CLASSES = {
    "Any": [("TypeUrlFieldNumber", 1), ("ValueFieldNumber", 2)],
    "Api": [("NameFieldNumber", 1), ("MethodsFieldNumber", 2), ("OptionsFieldNumber", 3),
            ("VersionFieldNumber", 4), ("SourceContextFieldNumber", 5),
            ("MixinsFieldNumber", 6), ("SyntaxFieldNumber", 7)],
    "Duration": [("SecondsFieldNumber", 1), ("NanosFieldNumber", 2)],
}


# Rejoue le pairage const->champ sur les 3 classes témoin, imprime PASS/FAIL par classe.
# / Replays const->field pairing on the 3 witness classes, prints PASS/FAIL per class.
def verifier_temoins(lines):
    all_ok = True
    for cls_name, expected in WITNESS_CLASSES.items():
        start = None
        for i, l in enumerate(lines):
            if re.match(rf"^\t*(?:public|internal)\s+sealed\s+class\s+{re.escape(cls_name)}\b.*TypeDefIndex:", l):
                start = i
                break
        if start is None:
            log(f"[témoin] {cls_name} : INTROUVABLE — épreuve incomplète")
            all_ok = False
            continue
        found, pending = [], []
        i = start
        base_tabs = len(lines[start]) - len(lines[start].lstrip("\t"))
        while i < len(lines) and i < start + 400:
            line = lines[i]
            if CLOSE_RE.match(line) and len(CLOSE_RE.match(line).group(1)) == base_tabs:
                break
            if SECTION_RE.match(line) and "Fields" not in line:
                break  # même garde que le parseur principal : hors "// Fields", on arrête
            cst = CONST_RE.match(line)
            if cst:
                champ_num = int(cst.group(2))
                if 0 <= champ_num <= MAX_FIELD_NUMBER:  # même garde que le parseur principal
                    pending.append((cst.group(1), champ_num))
            else:
                parsed = parse_backing_line(line)
                if parsed and pending:
                    type_str, _ = parsed
                    if not (type_str.startswith(SKIP_BACKING_PREFIXES) or type_str in SKIP_BACKING_EXACT):
                        for name, num in pending:
                            found.append((name, num))
                        pending = []
            i += 1
        ok = found == expected
        log(f"[témoin] {cls_name} : {'✅ PASS' if ok else '❌ FAIL'} — attendu {expected}, obtenu {found}")
        all_ok = all_ok and ok
    return all_ok


# Point d'entrée : lit cs/il2cpp.cs, lance les témoins, imprime le bilan et le code de sortie.
# / Entry point: reads cs/il2cpp.cs, runs the witnesses, prints the verdict and exit code.
def main():
    with open(CS_PATH, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    ok = verifier_temoins(lines)
    print(f"\n=== BILAN TÉMOINS : {'3/3 ✅' if ok else 'ÉCHEC ❌'} ===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
