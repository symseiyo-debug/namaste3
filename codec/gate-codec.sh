#!/usr/bin/env bash
# ============================================================================================
# QUOI : GATE du codec 3.0 (étage 2). Rejouable, déterministe, 0 jeton.
# FR :   rc=0 SEULEMENT SI : les 3 fixtures RÉELLES sont présentes et intactes (sha256), le build
#      passe, les 65 tests passent, et chaque fixture fait un round-trip BYTE-EXACT.
# POURQUOI : « Pas de vert sans frame réelle » — cahier des charges §2, étage 2 : un round-trip
#      qui ne s'exerce que sur des fixtures synthétiques ne prouve rien contre le client réel.
# EN : 3.0 codec GATE (stage 2). Replayable, deterministic, 0 token.
#      rc=0 ONLY IF: the 3 REAL fixtures are present and intact (sha256), the build passes, the
#      tests pass, and each fixture makes a BYTE-EXACT round-trip.
#
# COMMENT LANCER / USAGE :
#   ./gate-codec.sh            # gate complète / full gate
#   ./gate-codec.sh --epreuve  # + sabotage d'une fixture : la gate DOIT virer au rouge
# GATE : rc=0 ssi 0 refus (build + tests + round-trip byte-exact des 3 fixtures) ; rc=1 sinon.
# ============================================================================================
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="${NAMASTE3_FIXTURES:-refs/JondoEmu/datos}"
SNIFF="$HERE/src/Namaste3.Codec.Sniff"
EPREUVE=0
[ "${1:-}" = "--epreuve" ] && EPREUVE=1

FAILURES=0
# Ligne d'info simple (stdout). / Simple info line (stdout).
say()  { printf '%s\n' "$*"; }
# Titre de section "=== ... ===". / Section heading "=== ... ===".
head2() { printf '\n=== %s ===\n' "$*"; }
# Enregistre un refus NOMMÉ et incrémente le compteur -- jamais un rouge muet.
# / Records a NAMED refusal and bumps the counter -- never a silent red.
fail() { printf 'REFUS/REFUSED : %s\n' "$*"; FAILURES=$((FAILURES + 1)); }

# FR : sha256 des 3 captures, mesurés le 2026-09-04. Une fixture qui change SANS qu'on le sache
#      transformerait ce vert en vert d'autre chose. EN : a fixture changing unnoticed would turn
#      this green into the green of something else.
declare -A EXPECTED_SHA=(
  [world_etapa1_tras_elegir_personaje.bin]=4b08e983067d1455529a48f5a5a654e82b42087a7b1896ac283fc369efdf0432
  [world_etapa2_tras_confirmar.bin]=1bd7d1bbd5f65abc28e36f031469b2f0c8c43d64a883fda12495b6e1563e9f31
  [world_etapa3_mapa.bin]=602843eb75456f323f66aab58f87da528a72da0145e8b7fdc90aa483bd91c1ec
)
declare -A EXPECTED_FRAMES=(
  [world_etapa1_tras_elegir_personaje.bin]=322
  [world_etapa2_tras_confirmar.bin]=2
  [world_etapa3_mapa.bin]=31
)
ORDER=(world_etapa1_tras_elegir_personaje.bin world_etapa2_tras_confirmar.bin world_etapa3_mapa.bin)

head2 "0. Matière : les 3 captures RÉELLES / the 3 REAL captures"
for name in "${ORDER[@]}"; do
  path="$FIXTURES/$name"
  if [ ! -f "$path" ]; then
    fail "fixture absente / missing fixture: $path"
    continue
  fi
  sha="$(sha256sum "$path" | cut -d' ' -f1)"
  size="$(stat -c%s "$path")"
  if [ "$sha" = "${EXPECTED_SHA[$name]}" ]; then
    say "  OK   $name  $size o/bytes  sha256=$sha"
  else
    fail "$name : sha256 attendu/expected ${EXPECTED_SHA[$name]}, mesuré/measured $sha"
  fi
done

head2 "1. Build"
if dotnet build "$HERE/Namaste3.Codec.sln" -nologo -v q 2>&1 | tail -5; then
  say "  build OK"
else
  fail "dotnet build"
fi

head2 "2. Tests (xunit)"
TEST_LOG="$(mktemp)"
if dotnet test "$HERE/Namaste3.Codec.sln" -nologo -v q --no-build > "$TEST_LOG" 2>&1; then
  grep -E "^Passed!|^Failed!" "$TEST_LOG" | sed 's/^/  /'
else
  grep -E "^Passed!|^Failed!|\[FAIL\]" "$TEST_LOG" | head -20 | sed 's/^/  /'
  fail "dotnet test"
fi
rm -f "$TEST_LOG"

head2 "3. Round-trip byte-exact, fixture par fixture / fixture by fixture"
printf '  %-42s %7s %7s %8s %s\n' "fixture" "octets" "trames" "opcodes" "round-trip"
TOTAL_FRAMES=0
for name in "${ORDER[@]}"; do
  path="$FIXTURES/$name"
  [ -f "$path" ] || continue
  out="$(dotnet run --project "$SNIFF" --no-build -- "$path" --summary 2>&1)"
  rc=$?
  bytes="$(printf '%s' "$out"   | grep -oP 'octets/bytes=\K[0-9]+')"
  frames="$(printf '%s' "$out"  | grep -oP '^trames/frames\s*:\s*\K[0-9]+')"
  opcodes="$(printf '%s' "$out" | grep -oP '^opcodes distincts\s*:\s*\K[0-9]+')"
  verdict="$(printf '%s' "$out" | grep -oP '^round-trip\s*:\s*\K[A-Z-]+')"
  before="$(printf '%s' "$out"  | grep -oP 'avant/before=\K[0-9a-f]+')"
  after="$(printf '%s' "$out"   | grep -oP 'après/after=\K[0-9a-f]+')"

  printf '  %-42s %7s %7s %8s %s\n' "$name" "${bytes:-?}" "${frames:-?}" "${opcodes:-?}" "${verdict:-REFUS}"
  say  "      sha avant/before $before"
  say  "      sha après /after $after"
  printf '%s' "$out" | grep -E '^(cas racine|arbre)' | sed 's/^/      /'
  printf '%s' "$out" | grep -E '^opcodes distincts' | sed 's/^/      /'

  if [ "$rc" -ne 0 ] || [ "$verdict" != "BYTE-EXACT" ]; then
    fail "$name : round-trip ${verdict:-REFUS} (rc=$rc)"
  elif [ "$frames" != "${EXPECTED_FRAMES[$name]}" ]; then
    fail "$name : ${EXPECTED_FRAMES[$name]} trames attendues (compte Jondo), $frames mesurées"
  fi
  TOTAL_FRAMES=$((TOTAL_FRAMES + ${frames:-0}))
done
say "  total trames décodées / total frames decoded : $TOTAL_FRAMES"

if [ "$EPREUVE" = "1" ]; then
  head2 "4. ÉPREUVE — la gate DOIT virer au rouge sur une fixture sabotée"
  # FR : un octet du typeUrl de la 1re trame. Une gate qui reste verte ici ne mesure rien.
  # EN : one byte of the 1st frame's typeUrl. A gate that stays green here measures nothing.
  SAB="$(mktemp)"
  cp "$FIXTURES/world_etapa2_tras_confirmar.bin" "$SAB"
  printf '\x00' | dd of="$SAB" bs=1 seek=8 count=1 conv=notrunc status=none
  say "  sabotage : offset 8 (typeUrl) mis à 0x00 / set to 0x00"
  if dotnet run --project "$SNIFF" --no-build -- "$SAB" --summary > /dev/null 2>&1; then
    fail "ÉPREUVE : la gate est restée VERTE sur une entrée corrompue"
  else
    say "  OK   la gate a viré au ROUGE (rc != 0) / the gate turned RED"
  fi
  rm -f "$SAB"

  # FR : témoin positif de l'épreuve — la MÊME copie non sabotée doit rester verte.
  # EN : positive control — the SAME copy, unsabotaged, must stay green.
  SAB2="$(mktemp)"
  cp "$FIXTURES/world_etapa2_tras_confirmar.bin" "$SAB2"
  if dotnet run --project "$SNIFF" --no-build -- "$SAB2" --summary > /dev/null 2>&1; then
    say "  OK   témoin positif : la copie intacte reste VERTE / intact copy stays GREEN"
  else
    fail "ÉPREUVE : la copie INTACTE est rouge — le rouge ci-dessus vient de la copie, pas du sabotage"
  fi
  rm -f "$SAB2"
fi

head2 "Verdict"
if [ "$FAILURES" -eq 0 ]; then
  say "GATE CODEC : VERTE — $TOTAL_FRAMES trames réelles décodées et ré-encodées byte-exact"
  exit 0
fi
say "GATE CODEC : ROUGE — $FAILURES refus"
exit 1
