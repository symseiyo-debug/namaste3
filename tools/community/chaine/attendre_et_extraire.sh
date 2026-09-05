#!/usr/bin/env bash
# attendre_et_extraire.sh — commodité 2.x : enchaîne C4 + C3 dès que ffdec a fini une version.
#
# ═══ QUOI / WHAT ═══
# Veille sur `ffdec.log`. À chaque « === <v> fin », lance l'extracteur puis la vérification de complétude
# (deux portées : le SWF entier, puis le sous-arbre réseau), et écrit un manifeste sha256 de l'arbre.
# Watches ffdec's log and chains the extractor plus both completeness checks when a version finishes.
#
# ═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
# Un export ffdec dure ~1 h 40 par version. Sans veille, l'arbre reste inexploité jusqu'à ce que
# quelqu'un y repense. N'INTERROMPT RIEN : il LIT et il attend. Aucun signal, aucun kill — l'export
# tourne, on ne le touche pas. Il s'arrête de lui-même après 8 h EN LE DISANT, plutôt que d'attendre
# en silence (un processus muet est indiscernable d'un processus bloqué).
#
# ═══ COMMENT LANCER / HOW TO RUN ═══
#   nohup bash attendre_et_extraire.sh &        # journal : out/CHAINE-2X-JOURNAL.txt
#
# ═══ GATE ═══
# Pas de `--epreuve` : ce script n'établit aucun fait, il APPELLE des outils qui ont la leur
# (`extraire_as3_protocole.py` 6/6, `verifier_arbre_as3.py` 5/5). Ce qu'il produit se juge par leurs
# gates, jamais par le fait qu'il soit allé au bout. No gate of its own: it asserts nothing.
set -uo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
AS3=internal/as3
LOG=$AS3/ffdec.log
OUT=$ICI/out
JOURNAL=$ICI/out/CHAINE-2X-JOURNAL.txt
LIMITE=$((8 * 3600))   # 8 h : au-delà, on rend la main en le DISANT plutôt que d'attendre en silence
mkdir -p "$OUT"

# Trace horodatée, à l'écran ET dans le journal : un traitement long et muet est indiscernable d'un
# traitement bloqué, ce qui pousse à le relancer et à créer des doublons.
# Timestamped trace to screen and log: a silent long job is indistinguishable from a stuck one.
dire() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$JOURNAL"; }

# Enchaîne, pour UNE version finie : extraction des tables, complétude sur les deux portées (SWF
# entier puis sous-arbre réseau), et manifeste sha256 de l'arbre. Chaque code de retour est journalisé.
# For one finished version: extract tables, check completeness at both scopes, write a sha256 manifest.
traiter() {   # traiter <version>
  local v="$1" arbre="$AS3/client${v}-as3" swf="$AS3/swf/DofusInvoker-${v}.swf"
  dire "=== $v : ffdec a fini, on enchaîne"
  local n; n=$(find "$arbre" -name '*.as' 2>/dev/null | wc -l)
  dire "$v : $n fichiers .as sur le disque"
  python3 "$ICI/extraire_as3_protocole.py" "$arbre" "$v" --out "$OUT" >>"$JOURNAL" 2>&1
  dire "$v : extraction rc=$?"
  # complétude, deux portées : le SWF entier, puis le sous-arbre réseau (la question qui compte ici)
  python3 "$ICI/verifier_arbre_as3.py" "$swf" "$arbre" --manquants 5 >>"$JOURNAL" 2>&1
  dire "$v : complétude SWF entier rc=$?"
  python3 "$ICI/verifier_arbre_as3.py" "$swf" "$arbre" --prefixe com.ankamagames.dofus.network. \
      --manquants 20 >>"$JOURNAL" 2>&1
  dire "$v : complétude sous-arbre réseau rc=$?"
  ( cd "$arbre" && find . -type f -name '*.as' -print0 | sort -z | xargs -0 sha256sum \
      > "$OUT/client${v}-as3.MANIFEST.sha256" )
  dire "$v : manifeste $(wc -l < "$OUT/client${v}-as3.MANIFEST.sha256") lignes"
}

dire "veille démarrée (limite ${LIMITE}s) — versions attendues : 268, 238, 242"
debut=$(date +%s); faits=""
while :; do
  for v in 268 238 242; do
    case "$faits" in *"|$v|"*) continue ;; esac
    if grep -q "=== $v fin" "$LOG" 2>/dev/null; then
      traiter "$v"
      faits="$faits|$v|"
    fi
  done
  [ "$faits" = "|268||238||242|" ] && { dire "les trois versions sont traitées"; break; }
  if [ $(( $(date +%s) - debut )) -gt "$LIMITE" ]; then
    dire "LIMITE ATTEINTE — versions traitées : ${faits:-aucune}. La veille s'arrête et le DIT."
    exit 1
  fi
  sleep 60
done
dire "veille terminée"
