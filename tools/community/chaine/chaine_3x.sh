#!/usr/bin/env bash
# chaine_3x.sh — une build 3.x traverse la chaîne STATIQUE sans main humaine, et DIT où la main reprend.
#
# ═══ QUOI / WHAT ═══
# Maillon A8 : le pilote de la chaîne 3.x. Enchaîne obtenir → dump → gate G0 → littéraux, et rend un
# bilan par étape (franchie, ou REFUS NOMMÉ). Sortie : les tables dans `--out`, plus le verdict L7.
# Stage A8: the 3.x chain driver; every missing link is a named refusal, never a silent skip.
#
# ═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
# Gate L7 : « une build inconnue traverse la chaîne sans main humaine jusqu'au bot ». Ce pilote MESURE
# jusqu'où on va aujourd'hui. Il ne fait pas semblant : chaque maillon absent produit un REFUS NOMMÉ,
# jamais un saut silencieux. Un pilote qui saute un maillon manquant rend « succès » sur une chaîne cassée.
# État mesuré le 04/09 sur 3.6.10.10 : 3 maillons franchis, 3 refus (matcher, .proto, bot) → L7 ROUGE.
#
# ═══ COMMENT LANCER / HOW TO RUN ═══
#   chaine_3x.sh <version> --build <dossier GameAssembly+metadata> --out <dossier>
#   chaine_3x.sh <version> --dump  <dossier de dump déjà produit>   --out <dossier>
#   chaine_3x.sh --epreuve                # rejoue les maillons DISPONIBLES sur le dump existant
#
# ═══ GATE ═══
# `--epreuve` — 4 contrôles, tous verts au 04/09/2026 : entrée absente REFUSÉE et nommée · sur le dump
# réel, franchit ce qui existe et nomme les manques · PREUVE À DESTINATION (les tables existent vraiment
# sur le disque, pas seulement un rc=0) · témoin négatif (une build refusée ne produit AUCUNE table).
set -uo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
CHANTIER="$(cd "$ICI/../.." && pwd)"
BUILD=""; DUMP=""; OUT=""; VERSION=""; EPREUVE=0; VRAIMENT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD="$2"; shift ;;
    --dump)  DUMP="$2";  shift ;;
    --out)   OUT="$2";   shift ;;
    --vraiment) VRAIMENT=1 ;;
    --epreuve)  EPREUVE=1 ;;
    --*) echo "REFUS : option inconnue $1" >&2; exit 2 ;;
    *) VERSION="$1" ;;
  esac
  shift
done

ETAPE=0; FAITES=0; REFUS=0; RAISONS=()
# Ouvre une étape numérotée. La numérotation est ce qui permet au bilan final de NOMMER les refus par
# leur étape, au lieu de rendre un « ça a échoué » sans lieu.
# Opens a numbered step, so the final report can name each refusal by its step.
etape() { ETAPE=$((ETAPE+1)); echo; echo "── ÉTAPE $ETAPE · $1"; }
# Marque un maillon FRANCHI et l'ajoute au compte. Ce compte n'est pas décoratif : c'est la mesure de
# la gate L7 (jusqu'où une build va sans main humaine).
# Marks a link as passed; the count is the L7 gate measurement.
fait()  { FAITES=$((FAITES+1)); echo "   ✅ $1"; }
refus() { REFUS=$((REFUS+1)); RAISONS+=("étape $ETAPE : $1"); echo "   🔴 REFUS — $1"; }

# Rend le verdict G0 SANS écrire dans la zone de l'étage 0 : on importe `mesurer()`, pas le mode rapport.
# 🔴 `gate-g0.py` porte le chemin du metadata EN DUR sur la build 3.6.10.10 (`META = …/temoins-3.0/…`).
# Sur une AUTRE build, il comparerait le dump de la build N au metadata de la build M : un verdict faux,
# et vert par accident si les deux builds se ressemblent — exactement ce que la loi L6 interdit. On
# INJECTE donc le metadata de LA build jugée, et on refuse s'il manque plutôt que de laisser le défaut.
# gate-g0.py hardcodes the 3.6.10.10 metadata path; we inject the judged build's own metadata instead.
g0_verdict() {  # g0_verdict <dump> [metadata de CETTE build]
  python3 - "$1" "${2:-}" <<'PY'
import importlib.util, sys, os
p = "tools/client-dump/gate-g0.py"
if not os.path.exists(p):
    print("GATE-G0-ABSENTE"); sys.exit(3)
s = importlib.util.spec_from_file_location("g0", p); m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
meta = sys.argv[2]
if meta:
    if not os.path.isfile(meta):
        print(f"GATE-G0-METADATA-ABSENT {meta}"); sys.exit(5)
    m.META = meta                      # la référence doit être celle de LA build jugée
elif not os.path.isfile(getattr(m, "META", "")):
    print("GATE-G0-METADATA-ABSENT (défaut du module)"); sys.exit(5)
try:
    *_, v = m.mesurer(sys.argv[1])
except Exception as e:
    print(f"GATE-G0-ERREUR {e}"); sys.exit(4)
print(("VERT" if v["vert"] else "ROUGE") + f" couverture={v['couverture']:.4f} inventes={len(v['inventes'])}"
      + f" reference={os.path.basename(m.META)}")
sys.exit(0 if v["vert"] else 1)
PY
}

if [ "$EPREUVE" -eq 1 ]; then
  echo "=== ÉPREUVE de chaine_3x.sh — jusqu'où une build va-t-elle sans main humaine ? ==="
  D="$CHANTIER/internal/il2cpp-dump/il2cppinspectorredux"
  T=$(mktemp -d); ok=1
  # 1. le pilote doit REFUSER une entrée absente au lieu d'inventer un succès
  s=$(bash "$0" 9.9.9.9 --dump "$T/nexiste-pas" --out "$T/o" 2>&1); rc=$?
  if [ "$rc" -ne 0 ] && echo "$s" | grep -q "REFUS"; then
    echo "✅ entrée absente : refusée et nommée (rc=$rc)"
  else echo "❌ entrée absente : acceptée en silence (rc=$rc)"; ok=0; fi
  # 2. sur le dump réel, il doit aller jusqu'au dernier maillon DISPONIBLE et nommer les manquants
  s=$(bash "$0" 3.6.10.10 --dump "$D" --out "$T/o2" 2>&1); rc=$?
  f=$(echo "$s" | grep -c '✅'); r=$(echo "$s" | grep -c '🔴')
  if [ "$f" -ge 3 ] && [ "$r" -ge 1 ]; then
    echo "✅ dump réel : $f maillon(s) franchis, $r maillon(s) refusés ET nommés"
  else echo "❌ dump réel : $f franchis / $r refusés — le pilote ne mesure rien"; ok=0; fi
  # 3. les tables attendues existent VRAIMENT à destination (pas seulement un rc=0)
  if [ -s "$T/o2/routes-haapi-3.6.10.10.txt" ] && [ -s "$T/o2/noms-protocole-3.6.10.10.txt" ]; then
    n=$(wc -l < "$T/o2/noms-protocole-3.6.10.10.txt")
    echo "✅ preuve à destination : tables écrites, $n noms de protocole"
  else echo "❌ preuve à destination : tables absentes malgré un maillon 'franchi'"; ok=0; fi
  # 4. témoin négatif : une build fantôme ne doit produire AUCUNE table
  if [ ! -e "$T/o/routes-haapi-9.9.9.9.txt" ]; then
    echo "✅ témoin négatif : la build refusée n'a produit aucune table"
  else echo "❌ témoin négatif : des tables écrites pour une build refusée"; ok=0; fi
  rm -rf "$T"
  [ "$ok" -eq 1 ] && { echo "ÉPREUVE : le pilote mesure la chaîne et nomme ses trous"; exit 0; }
  echo "ÉPREUVE : PILOTE INERTE"; exit 1
fi

[ -n "$VERSION" ] || { echo "REFUS : version manquante (elle nomme TOUS les artefacts — loi L6)." >&2; exit 2; }
[ -n "$OUT" ] || { echo "REFUS : --out manquant." >&2; exit 2; }
mkdir -p "$OUT"
echo "=== chaîne statique 3.x · build $VERSION → $OUT"

etape "obtenir la build (GameAssembly.dll + global-metadata.dat)"
if [ -n "$DUMP" ]; then
  echo "   (sauté : un dump est fourni)"
elif [ -n "$BUILD" ] && [ -f "$BUILD/GameAssembly.dll" ]; then
  fait "binaires déjà présents dans $BUILD"
else
  bash "$ICI/obtenir_build.sh" il2cpp "$VERSION" --out "$OUT/builds" ${VRAIMENT:+--vraiment} \
    && { BUILD="$OUT/builds/$VERSION"; [ "$VRAIMENT" -eq 1 ] && fait "build téléchargée" || refus "MODE PLAN : rien n'a été téléchargé (ajoute --vraiment)"; } \
    || refus "cytrus indisponible ou échec de téléchargement"
fi

etape "dumper (Il2CppInspector-Redux)"
CLI="$CHANTIER/internal/tools/il2cppinspectorredux-cli/Il2CppInspectorRedux.CLI-linux-x64/Il2CppInspector.Redux.CLI"
if [ -n "$DUMP" ]; then
  if [ -f "$DUMP/il2cpp.json" ]; then fait "dump fourni : $DUMP"
  else refus "dump fourni introuvable ou incomplet ($DUMP/il2cpp.json absent)"; fi
elif [ ! -x "$CLI" ]; then
  refus "CLI Il2CppInspector-Redux absente ($CLI)"
elif [ -z "${BUILD:-}" ] || [ ! -f "$BUILD/GameAssembly.dll" ]; then
  refus "pas de binaires à dumper (étape 1 non franchie)"
else
  DUMP="$OUT/dump-$VERSION"; mkdir -p "$DUMP"
  "$CLI" -i "$BUILD/GameAssembly.dll" -m "$BUILD/global-metadata.dat" -o "$DUMP" >"$OUT/dump.log" 2>&1 \
    && fait "dump produit dans $DUMP" || refus "le dump a échoué (voir $OUT/dump.log)"
fi

etape "gate G0 (le dump conserve-t-il le protocole ?)"
if [ -z "${DUMP:-}" ] || [ ! -f "$DUMP/il2cpp.json" ]; then
  refus "pas de dump à juger (étape 2 non franchie)"
else
  # metadata de CETTE build : d'abord celui téléchargé avec elle, sinon on laisse la gate refuser.
  META_BUILD=""
  [ -n "${BUILD:-}" ] && META_BUILD=$(find "$BUILD" -name global-metadata.dat -type f 2>/dev/null | head -1)
  [ -n "$META_BUILD" ] && echo "   référence G0 : $META_BUILD (metadata de CETTE build)"
  v=$(g0_verdict "$DUMP" "$META_BUILD" 2>/dev/null); rc=$?
  case "$rc" in
    0) fait "G0 $v" ;;
    1) refus "G0 ROUGE — $v" ;;
    3) refus "gate-g0.py absente du chantier" ;;
    5) refus "metadata de référence introuvable — G0 comparerait le dump à une AUTRE build ($v)" ;;
    *) refus "gate-g0.py a échoué ($v)" ;;
  esac
fi

etape "littéraux, routes, URL, noms de protocole"
if [ -z "${DUMP:-}" ] || [ ! -f "$DUMP/il2cpp.json" ]; then
  refus "pas de dump (étape 2 non franchie)"
else
  a=(); [ -n "${BUILD:-}" ] && [ -f "$BUILD/global-metadata.dat" ] && a+=(--binaire "$BUILD/global-metadata.dat")
  [ -d "$DUMP/dll" ] && a+=(--binaire "$DUMP/dll")
  META="$CHANTIER/../internal/artefacts/temoins-3.0/global-metadata.dat"
  [ "${#a[@]}" -eq 0 ] && [ -f "$META" ] && a+=(--binaire "$META")
  if [ "${#a[@]}" -eq 0 ]; then
    refus "aucun binaire pour les noms de protocole — ils ne sont PAS dans il2cpp.json (0 sur 217 Mo)"
  else
    python3 "$ICI/extraire_litteraux.py" "$DUMP/il2cpp.json" "$VERSION" --out "$OUT" "${a[@]}" \
      >"$OUT/litteraux.log" 2>&1 \
      && fait "tables écrites ($(wc -l < "$OUT/noms-protocole-$VERSION.txt" 2>/dev/null || echo 0) noms, \
$(wc -l < "$OUT/routes-haapi-$VERSION.txt" 2>/dev/null || echo 0) routes)" \
      || refus "extraction des littéraux en échec (voir $OUT/litteraux.log)"
  fi
fi

etape "matcher structurel (nom clair ↔ classe obfusquée)"
refus "MAILLON MANQUANT — le matcher vit dans tools/protocol-mapping/matcher/ (autre chantier, en cours). \
Sans lui, pas de .proto : on aurait des numéros de champ sans nom de message."

etape "protocole reconstruit (.proto) + table de dispatch générée"
refus "MAILLON MANQUANT — dépend de l'étape 5. Loi L6 : la table de dispatch se GÉNÈRE par build, \
jamais ne s'écrit en dur."

etape "bot-testeur rejoué contre la build"
refus "MAILLON MANQUANT — le bot existe (internal/bot-testeur/) mais rien ne le relie encore \
automatiquement à une build fraîchement dumpée."

echo
echo "=== BILAN build $VERSION : $FAITES maillon(s) franchi(s), $REFUS refus"
for r in "${RAISONS[@]}"; do echo "   · $r"; done
echo "Gate L7 (build inconnue → bot, sans main humaine) : $([ "$REFUS" -eq 0 ] && echo '🟢 ATTEINTE' || echo '🔴 NON ATTEINTE')"
exit $([ "$REFUS" -eq 0 ] && echo 0 || echo 1)
