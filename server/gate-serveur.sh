#!/usr/bin/env bash
# ============================================================================================
# QUOI : GATE du serveur de connexion 3.0 (étage 3). Rejouable, déterministe, 0 jeton.
# FR :   rc=0 SEULEMENT SI : la table de liaison est à jour, le build passe, tous les tests
#        passent, `src/` ne contient AUCUN opcode littéral, et le binaire refuse une table
#        incohérente. Chaque étage imprime ses CHIFFRES, pas seulement son verdict.
# POURQUOI (05/09/2026) : « un verdict ne dit jamais sa cause » — une gate qui n'imprime que
#        VERT/ROUGE oblige à la relancer pour savoir ce qu'elle a mesuré. Et « pas de vert sans
#        épreuve dans les deux sens » : `--epreuve` plante un opcode littéral dans `src/` et
#        casse la table, puis vérifie que la gate vire au ROUGE — sans quoi son vert ne
#        mesurerait rien. Le témoin positif (l'état intact reste VERT) accompagne chaque
#        sabotage, sinon le rouge pourrait venir du montage et non du sabotage.
# EN :    3.0 connection-server GATE (stage 3). rc=0 ONLY IF: the binding table is current, the
#        build passes, all tests pass, `src/` holds NO literal opcode, and the binary refuses an
#        inconsistent table. `--epreuve` proves the gate can turn RED, with positive controls.
#
# COMMENT LANCER / USAGE :
#   ./gate-serveur.sh            # gate complète / full gate
#   ./gate-serveur.sh --epreuve  # + sabotages : la gate DOIT virer au rouge
# GATE : rc=0 ssi 0 refus ; rc=1 sinon, avec chaque refus NOMMÉ.
# ============================================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLN="$HERE/Namaste3.Server.sln"
SRC="$HERE/src"
PROTOCOL="$HERE/protocol"
GATE_COMMENTAIRES="$HERE/../tools/community/gate-commentaires.py"
EPREUVE=0
[ "${1:-}" = "--epreuve" ] && EPREUVE=1

# FR : la machine a 4 vCPU et d'autres tâches tournent — on ne prend pas toute la place.
# EN : the box has 4 vCPUs and other tasks are running — we do not take the whole room.
DOTNET="nice -n 10 dotnet"

FAILURES=0
# Ligne d'info simple (stdout). / Simple info line (stdout).
say()   { printf '%s\n' "$*"; }
# Titre de section "=== ... ===". / Section heading "=== ... ===".
head2() { printf '\n=== %s ===\n' "$*"; }
# Enregistre un refus NOMMÉ et incrémente le compteur -- jamais un rouge muet.
# / Records a NAMED refusal and bumps the counter -- never a silent red.
fail()  { printf 'REFUS/REFUSED : %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

# FR : le motif qui définit « opcode littéral » : trois lettres minuscules entre guillemets.
#      C'est EXACTEMENT le motif de INTERFACES.md §2 — on ne l'assouplit pas.
# EN : the pattern defining a "literal opcode": three lowercase letters in quotes.
OPCODE_PATTERN='"[a-z]{3}"'

# FR : compte les opcodes littéraux d'un répertoire, en ignorant les artefacts de build.
# EN : counts literal opcodes in a directory, skipping build artefacts.
compter_opcodes() {
  grep -rnoE "$OPCODE_PATTERN" "$1" --include=*.cs 2>/dev/null \
    | grep -v '/obj/' | grep -v '/bin/' | wc -l
}

head2 "0. Table de liaison / binding table"
if python3 "$PROTOCOL/generer-binding.py" --verifier; then
  say "  OK   la table est à jour / the table is current"
else
  fail "table de liaison PÉRIMÉE ou incohérente — relancer / stale or inconsistent table: python3 protocol/generer-binding.py"
fi
BINDING="$(ls "$PROTOCOL"/binding-*.json 2>/dev/null | sort | tail -1)"
if [ -n "$BINDING" ]; then
  say "  table : $(basename "$BINDING")  $(stat -c%s "$BINDING") o/bytes"
  say "  sha256=$(sha256sum "$BINDING" | cut -d' ' -f1)"
else
  fail "aucune table de liaison sur disque / no binding table on disk"
fi

head2 "1. Build"
if $DOTNET build "$SLN" -nologo -v q 2>&1 | tail -4; then
  say "  build OK"
else
  fail "dotnet build"
fi

head2 "2. Tests (xunit)"
TEST_LOG="$(mktemp)"
if $DOTNET test "$SLN" -nologo -v q --no-build > "$TEST_LOG" 2>&1; then
  grep -E "^Passed!|^Failed!" "$TEST_LOG" | sed 's/^/  /'
else
  grep -E "^Passed!|^Failed!|\[FAIL\]" "$TEST_LOG" | head -20 | sed 's/^/  /'
  fail "dotnet test"
fi
rm -f "$TEST_LOG"

head2 "3. 0 opcode littéral dans src/ / 0 literal opcode in src/"
LITTERAUX="$(compter_opcodes "$SRC")"
say "  opcodes littéraux mesurés / measured literal opcodes : $LITTERAUX"
if [ "$LITTERAUX" -ne 0 ]; then
  grep -rnoE "$OPCODE_PATTERN" "$SRC" --include=*.cs | grep -v '/obj/' | grep -v '/bin/' | sed 's/^/    /'
  fail "$LITTERAUX opcode(s) littéral(aux) dans src/ — ils appartiennent à la table (D-08)"
fi

head2 "4. Commentaires / comment coverage"
# FR : on scanne TOUT l'étage, `gate-serveur.sh` COMPRIS. Une gate qui s'exempte elle-même est
#      une garde armée sur une branche que personne ne parcourt — mesuré ici même le 05/09 :
#      ce script était ROUGE pendant que sa propre étape 4 rendait VERT, parce qu'elle ne
#      scannait que src/, tests/ et protocol/.
# EN : we scan the WHOLE stage, `gate-serveur.sh` INCLUDED. A gate that exempts itself is a
#      guard armed on a branch nobody walks — measured right here on 05/09.
if [ -f "$GATE_COMMENTAIRES" ]; then
  COMMENT_LOG="$(mktemp)"
  if python3 "$GATE_COMMENTAIRES" "$HERE" > "$COMMENT_LOG" 2>&1; then
    grep -E "^TOTAL:" "$COMMENT_LOG" | sed 's/^/  /'
  else
    grep -E "^ROUGE|^TOTAL:" "$COMMENT_LOG" | head -20 | sed 's/^/  /'
    fail "gate-commentaires"
  fi
  rm -f "$COMMENT_LOG"
else
  fail "gate-commentaires.py introuvable / not found: $GATE_COMMENTAIRES"
fi

head2 "5. Fichiers < 500 lignes / files under 500 lines"
TROP_LONGS=0
while read -r count path; do
  [ "$path" = "total" ] && continue
  if [ "$count" -ge 500 ]; then
    fail "$path : $count lignes (plafond 500)"
    TROP_LONGS=$((TROP_LONGS + 1))
  fi
done < <(find "$SRC" "$HERE/tests" -name '*.cs' -not -path '*/obj/*' -not -path '*/bin/*' -exec wc -l {} + | head -n -1)
say "  fichiers au-dessus du plafond / files above the cap : $TROP_LONGS"

head2 "6. Le binaire refuse une table incohérente / the binary refuses a broken table"
BROKEN="$(mktemp --suffix=.json)"
printf '{ "build": "0.0.0", "messages": [], "rafale_bienvenue": [] }\n' > "$BROKEN"
if $DOTNET run --project "$SRC/Namaste3.Server.Connection" --no-build -- --table "$BROKEN" > /dev/null 2>&1; then
  fail "le serveur a DÉMARRÉ sur une table incohérente / server STARTED on a broken table"
else
  say "  OK   refus au démarrage / refused at start-up"
fi
rm -f "$BROKEN"

if [ "$EPREUVE" = "1" ]; then
  head2 "7. ÉPREUVE — la gate DOIT virer au rouge"

  # -- 7a. Un opcode littéral planté dans src/ doit être VU.
  # FR : on plante un fichier, on mesure, on le retire. Le `trap` garantit le retrait même si
  #      le script est interrompu — laisser ce fichier derrière rendrait la gate rouge à jamais.
  # EN : plant a file, measure, remove it. The trap guarantees removal even on interrupt.
  PLANTE="$SRC/Namaste3.Server.Connection/OpcodePlanteParLEpreuve.cs.tmp"
  trap 'rm -f "$PLANTE"' EXIT INT TERM
  printf 'internal static class Plante { public const string X = "kvw"; }\n' > "$PLANTE"
  mv "$PLANTE" "${PLANTE%.tmp}"
  PLANTE="${PLANTE%.tmp}"
  AVEC="$(compter_opcodes "$SRC")"
  rm -f "$PLANTE"
  SANS="$(compter_opcodes "$SRC")"
  say "  opcodes littéraux avec le plant / with the planted file : $AVEC"
  say "  opcodes littéraux après retrait / after removal          : $SANS"
  if [ "$AVEC" -lt 1 ]; then
    fail "ÉPREUVE : un opcode littéral planté dans src/ n'a PAS été vu — l'étage 3 ne mesure rien"
  else
    say "  OK   le plant a été VU / the planted opcode was SEEN"
  fi
  if [ "$SANS" -ne 0 ]; then
    fail "ÉPREUVE : témoin positif ROUGE — src/ n'est pas revenu à 0 après le retrait"
  else
    say "  OK   témoin positif : src/ est revenu à 0 / positive control: back to 0"
  fi

  # -- 7b. Une table SABOTÉE doit faire échouer les tests, et l'intacte doit les faire passer.
  # FR : on sabote l'ORDRE de la rafale : c'est le fait mesuré que l'étage 3 doit protéger.
  #      Une gate qui resterait verte ici ne mesurerait pas l'ordre, seulement sa présence.
  # EN : we sabotage the burst's ORDER — the measured fact stage 3 must protect.
  SAUVE="$(mktemp --suffix=.json)"
  cp "$BINDING" "$SAUVE"
  trap 'cp -f "$SAUVE" "$BINDING" 2>/dev/null; rm -f "$SAUVE"' EXIT INT TERM
  python3 - "$BINDING" <<'PY'
import json, sys
# Inverse les deux premières étapes de la rafale : l'ordre est le fait mesuré.
# / Swaps the burst's first two steps: the order is the measured fact.
p = sys.argv[1]
doc = json.load(open(p, encoding="utf-8"))
r = doc["rafale_bienvenue"]
r[0], r[1] = r[1], r[0]
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
  if $DOTNET test "$SLN" -nologo -v q --no-build > /dev/null 2>&1; then
    fail "ÉPREUVE : les tests sont restés VERTS avec la rafale dans le mauvais ordre"
  else
    say "  OK   ordre de rafale saboté -> tests ROUGES / sabotaged burst order -> tests RED"
  fi
  cp -f "$SAUVE" "$BINDING"
  rm -f "$SAUVE"
  trap - EXIT INT TERM
  if $DOTNET test "$SLN" -nologo -v q --no-build > /dev/null 2>&1; then
    say "  OK   témoin positif : table restaurée -> tests VERTS / restored -> tests GREEN"
  else
    fail "ÉPREUVE : témoin positif ROUGE — la table restaurée ne repasse pas les tests"
  fi

  # -- 7c. Le recroisement des NUMÉROS DE CHAMP contre la table de dispatch de l'étage 5.
  # FR : on fausse le numéro dont l'erreur coûterait le plus cher — l'identifiant de personnage
  #      de la PREMIÈRE sélection, dont le champ 1 est un BOOLÉEN et le champ 2 l'identifiant.
  #      Lire f1 rendrait 0 ou 1 en guise d'identifiant : du protobuf VALIDE, un round-trip VERT,
  #      et une panne visible seulement à l'écran. Si la gate reste verte ici, le recroisement
  #      des champs ne mesure rien.
  # EN : we falsify the field number whose error would cost the most — the first-selection
  #      character id, whose field 1 is a BOOL. Reading f1 yields VALID protobuf and a GREEN
  #      round-trip, with a failure visible only on screen.
  GEN="$PROTOCOL/generer-binding.py"
  GEN_SAUVE="$(mktemp --suffix=.py)"
  cp "$GEN" "$GEN_SAUVE"
  trap 'cp -f "$GEN_SAUVE" "$GEN" 2>/dev/null; rm -f "$GEN_SAUVE"' EXIT INT TERM
  sed -i 's|("kvl", 2, "int64"|("kvl", 1, "int64"|' "$GEN"
  if python3 "$GEN" > /dev/null 2>&1; then
    fail "ÉPREUVE : un numéro de champ FAUX (kvl.f1, un booléen) est passé — le recroisement des champs ne mesure rien"
  else
    say "  OK   numéro de champ faussé -> REFUS nommé / falsified field number -> NAMED refusal"
  fi
  cp -f "$GEN_SAUVE" "$GEN"
  rm -f "$GEN_SAUVE"
  trap - EXIT INT TERM
  if python3 "$GEN" > /dev/null 2>&1; then
    say "  OK   témoin positif : générateur restauré -> VERT / restored -> GREEN"
  else
    fail "ÉPREUVE : témoin positif ROUGE — le générateur restauré ne repasse pas"
  fi
fi

head2 "Verdict"
if [ "$FAILURES" -eq 0 ]; then
  say "GATE SERVEUR : VERTE — 0 opcode littéral dans src/, table à jour, tests verts"
  exit 0
fi
say "GATE SERVEUR : ROUGE — $FAILURES refus"
exit 1
