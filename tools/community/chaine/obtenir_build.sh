#!/usr/bin/env bash
# obtenir_build.sh — enveloppe documentée de cytrus-v6 : « des versions » → « un dossier PAR BUILD + un sha256 ».
#
# ═══ QUOI / WHAT ═══
# Maillon A1 (3.x) ET C1 (2.x). Entrée : une ou plusieurs versions. Sortie : un dossier par build, avec
# son MANIFEST.sha256. Seul outil des deux chaînes, parce qu'il ne touche PAS au contenu — il transporte.
# Stages A1 and C1: the only tool shared by both chains, because it never looks inside the files.
#
# ═══ POURQUOI / WHY (écrit le 04/09/2026) ═══
# MULTI-BUILDS (loi L7) : plusieurs versions en une commande, chacune dans SON dossier `<out>/<version>/`.
# Le chemin porte la build, toujours — sans elle, deux dumps se mélangent et le diff compare du bruit.
# Multi-build by design: every artefact path carries its build.
#
# NE TÉLÉCHARGE RIEN PAR DÉFAUT. Sans --vraiment, il IMPRIME les commandes exactes et s'arrête (mode plan).
# Raison : le client complet 3.0 pèse plusieurs Go et la place disque est partagée.
#
# ═══ COMMENT LANCER / HOW TO RUN ═══
#   obtenir_build.sh versions [--release main|beta|dofus3]
#   obtenir_build.sh swf    <version>… --out <dossier>     # 2.x : DofusInvoker.swf seul (~4-8 Mo/build)
#   obtenir_build.sh il2cpp <version>… --out <dossier>     # 3.x : GameAssembly.dll + metadata (~150 Mo/build)
#   obtenir_build.sh complet <version>… --out <dossier>    # tout le client (PLUSIEURS Go par build)
#   … + --vraiment pour exécuter, --release R, --platform P
#   obtenir_build.sh --epreuve                             # éprouve le script sans réseau
#
# Exemple L7 (les trois builds 3.0 à comparer) :
#   ./obtenir_build.sh il2cpp 3.6.4.3 3.6.10.10 3.6.10.11 --out ./builds --vraiment
#
# ═══ GATE ═══
# `--epreuve` — 12 contrôles au 05/09/2026. Dix ne touchent PAS le réseau : mode plan écrit 0 fichier ·
# garde de place refuse 999999999 Mo ET laisse passer 1 Mo (une garde qui refuse tout ne mesure rien) ·
# manifeste refuse un dossier vide (0 fichier ≠ succès) et vérifie un sha256 juste · option inconnue
# refusée · 3 versions → 3 dossiers distincts portant la build normalisée · une build non demandée
# n'apparaît pas · `--out` absent → refusé · normalisation (nue → préfixée, préfixée inchangée, latest
# intacte). Deux INTERROGENT le CDN : une build réelle passe, une build inventée est refusée ; sans
# réseau ils ne sont ni verts ni rouges, et le disent.
# ⚠️ Le téléchargement réel a été fait le 05/09 (build 6.0_3.6.4.3) : ce n'est plus un mode plan seul.
set -uo pipefail

RELEASE=main; PLATFORM=windows; VRAIMENT=0; EPREUVE=0; OUT=""
# Préfixe de version majeure exigé par le CDN Ankama, MESURÉ le 05/09/2026 (403 sans, 200 avec) et
# documenté par l'aide de cytrus-v6 (« ex: 6.0_3.1.10.11 »). S'il change un jour, c'est ici.
# Major-version prefix required by the CDN, measured 2026-09-05 (403 without, 200 with).
PREFIXE_VERSION="6.0_"
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --vraiment) VRAIMENT=1 ;;
    --epreuve)  EPREUVE=1 ;;
    --release)  RELEASE="$2"; shift ;;
    --platform) PLATFORM="$2"; shift ;;
    --out)      OUT="$2"; shift ;;
    --*) echo "REFUS : option inconnue $1" >&2; exit 2 ;;
    *) ARGS+=("$1") ;;
  esac
  shift
done

# --- La commande cytrus : globale, puis npx, puis CYTRUS_CMD. Aucune n'est supposée présente. ---
cytrus_cmd() {
  if [ -n "${CYTRUS_CMD:-}" ]; then echo "$CYTRUS_CMD"; return 0; fi
  if command -v cytrus-v6 >/dev/null 2>&1; then echo "cytrus-v6"; return 0; fi
  if command -v npx >/dev/null 2>&1; then echo "npx --yes cytrus-v6"; return 0; fi
  return 1
}

# Normalise un numéro de build vers la forme attendue par Cytrus. MESURÉ le 05/09/2026 : le CDN veut un
# préfixe de version majeure — `3.6.4.3` rend 403, `6.0_3.6.4.3` rend 200. L'aide de cytrus-v6 le
# documente (« ex: 6.0_3.1.10.11 ») mais rien ne l'impose, et un 403 ressemble à « build inexistante ».
# `latest` et une version DÉJÀ préfixée passent inchangées.
# Normalises a build number to Cytrus's form: the CDN requires the `6.0_` major prefix (measured).
normaliser_version() {  # normaliser_version <version>
  local v="$1"
  case "$v" in
    latest|*_*) echo "$v" ;;
    [0-9]*.[0-9]*) echo "${PREFIXE_VERSION}${v}" ;;
    *) echo "$v" ;;
  esac
}

# Contrôle que le manifeste de la build EXISTE avant de lancer quoi que ce soit. Fail-closed : un 403
# n'est pas « pas de chance », c'est un refus NOMMÉ qui dit quoi corriger. Sans réseau, on le DIT et on
# laisse passer plutôt que de bloquer sur une panne locale — mais on ne prétend jamais avoir vérifié.
# Pre-flight check on the manifest; a 403 becomes a named refusal, and no network is said, never faked.
verifier_manifeste() {  # verifier_manifeste <version normalisée> <release>
  local v="$1" rel="$2" url code
  [ "$v" = latest ] && { echo "   contrôle manifeste : sauté (version courante du canal)"; return 0; }
  url="https://cytrus.cdn.ankama.com/dofus/releases/${rel}/${PLATFORM}/${v}.manifest"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$url") || {  # sec-ok: S3 -- declared: same CDN as above, $url built from it two lines up
    echo "   ⚠️ contrôle manifeste IMPOSSIBLE (pas de réseau) — on continue SANS avoir vérifié"; return 0; }
  case "$code" in
    200) echo "   contrôle manifeste : 200 sur $url"; return 0 ;;
    403|404)
      cat >&2 <<EOF
REFUS : le manifeste de la build « $v » rend $code sur le CDN Ankama.
  url    : $url
  causes : (a) le préfixe de version majeure manque — mesuré le 05/09, \`3.6.4.3\` rend 403 et
               \`6.0_3.6.4.3\` rend 200 ; ce script préfixe « $PREFIXE_VERSION » automatiquement ;
           (b) la build n'existe pas ou n'est plus servie sur le canal « $rel ».
  remède : \`obtenir_build.sh versions --release $rel --vraiment\` pour lire la version courante,
           ou consulter https://cytrus.cdn.ankama.com/cytrus.json (canaux et versions déclarés).
EOF
      return 1 ;;
    *) echo "REFUS : code HTTP inattendu $code sur $url" >&2; return 1 ;;
  esac
}

# --- Fail-closed sur la place disque : on refuse AVANT, pas au milieu du téléchargement. ---
exiger_place() {  # exiger_place <dossier> <Mo requis>
  local d="$1" besoin="$2" dispo
  mkdir -p "$d" || { echo "REFUS : impossible de créer $d" >&2; exit 1; }
  dispo=$(df -Pm "$d" | awk 'NR==2{print $4}')
  echo "place disque : ${dispo} Mo libres, ${besoin} Mo exigés dans $d"
  if [ "$dispo" -lt "$besoin" ]; then
    echo "REFUS : place insuffisante (${dispo} Mo < ${besoin} Mo). Rien n'a été téléchargé." >&2
    exit 1
  fi
}

# --- La preuve est prise À DESTINATION : sha256 des octets écrits, jamais le code de retour seul. ---
manifeste() {  # manifeste <dossier>
  local d="$1"
  ( cd "$d" && find . -type f ! -name 'MANIFEST.sha256' -print0 | sort -z \
      | xargs -0 -r sha256sum > MANIFEST.sha256 )
  local n; n=$(wc -l < "$d/MANIFEST.sha256")
  echo "MANIFEST : $d/MANIFEST.sha256 ($n fichiers)"
  du -sh "$d" | sed 's/^/taille  : /'
  if [ "$n" -eq 0 ]; then
    echo "REFUS : 0 fichier écrit — un dossier vide et un téléchargement raté s'écrivent pareil." >&2
    return 1
  fi
}

# Exécute UNE récupération, ou l'imprime sans rien faire en mode plan. La place disque est exigée
# AVANT le premier octet, et la preuve est prise À DESTINATION (sha256 des fichiers écrits) : un rc=0
# dit que la commande s'est terminée, pas que l'octet est arrivé.
# Runs one fetch (or prints it in plan mode); disk is required up front, proof taken at destination.
lancer() {  # lancer <description> <Mo requis> <dossier> <arguments cytrus…>
  local desc="$1" besoin="$2" dest="$3"; shift 3
  local cy; cy=$(cytrus_cmd) || {
    echo "REFUS : ni cytrus-v6 ni npx. Remède : npm install -g cytrus-v6 (ou CYTRUS_CMD=…)." >&2; exit 1; }
  echo "== $desc"
  echo "commande : $cy $*"
  if [ "$VRAIMENT" -ne 1 ]; then
    echo "MODE PLAN — rien n'est téléchargé. Ajoute --vraiment pour exécuter."
    echo "attendu   : ~${besoin} Mo dans $dest"
    return 0
  fi
  exiger_place "$dest" "$besoin"
  # shellcheck disable=SC2086
  $cy "$@" || { echo "REFUS : cytrus a échoué (rc=$?)." >&2; return 1; }
  manifeste "$dest"
}

# --- Boucle multi-builds : une version = un dossier. Les échecs sont COMPTÉS et NOMMÉS à la fin. ---
pour_chaque_build() {  # pour_chaque_build <desc> <Mo> <release> <selecteurs…> -- <versions…>
  local desc="$1" besoin="$2" rel="$3"; shift 3
  local sel=(); while [ "$1" != "--" ]; do sel+=("$1"); shift; done; shift
  local ok=0 ko=0 rates=()
  for v0 in "$@"; do
    local v; v=$(normaliser_version "$v0")
    [ "$v" != "$v0" ] && echo "   version normalisée : $v0 → $v (préfixe exigé par le CDN)"
    # le dossier porte la version NORMALISÉE : c'est elle qui identifie la build sur le CDN (L6)
    local dest="$OUT/$v"
    local a=(download --game dofus --release "$rel" --platform "$PLATFORM" --output "$dest")
    for s in "${sel[@]}"; do a+=(--select "$s"); done
    [ "$v" != latest ] && a+=(--version "$v")
    if [ "$VRAIMENT" -eq 1 ] && ! verifier_manifeste "$v" "$rel"; then
      ko=$((ko+1)); rates+=("$v"); continue
    fi
    if lancer "$desc · build $v" "$besoin" "$dest" "${a[@]}"; then ok=$((ok+1)); else ko=$((ko+1)); rates+=("$v"); fi
  done
  echo "— builds traitées : $ok réussie(s), $ko en échec${rates[*]:+ (${rates[*]})}"
  [ "$ko" -eq 0 ]
}

if [ "$EPREUVE" -eq 1 ]; then
  echo "=== ÉPREUVE de obtenir_build.sh (10 contrôles hors ligne + 2 qui interrogent le CDN) ==="
  ok=1
  t=$(mktemp -d)
  # 1. le mode plan ne doit RIEN écrire
  out=$(lancer "essai" 10 "$t/vide" download --game dofus 2>&1)
  n=$(find "$t/vide" -type f 2>/dev/null | wc -l)
  if [ "$n" -eq 0 ] && echo "$out" | grep -q "MODE PLAN"; then
    echo "✅ mode plan : 0 fichier écrit, commande imprimée"
  else echo "❌ mode plan : $n fichier(s) écrits"; ok=0; fi
  # 2. la garde de place doit REFUSER quand on exige l'impossible (témoin positif)
  if ( exiger_place "$t/place" 999999999 ) >/dev/null 2>&1; then echo "❌ garde de place inerte"; ok=0
  else echo "✅ garde de place : refuse 999999999 Mo"; fi
  # 3. … et LAISSER PASSER 1 Mo (témoin négatif : une garde qui refuse tout ne mesure rien)
  if ( exiger_place "$t/place" 1 ) >/dev/null 2>&1; then echo "✅ garde de place : laisse passer 1 Mo"
  else echo "❌ garde de place paranoïaque (refuse 1 Mo)"; ok=0; fi
  # 4. le manifeste doit REFUSER un dossier vide
  mkdir -p "$t/vide2"
  if ( manifeste "$t/vide2" ) >/dev/null 2>&1; then echo "❌ manifeste : accepte un dossier vide"; ok=0
  else echo "✅ manifeste : refuse un dossier vide (0 fichier ≠ succès)"; fi
  # 5. … et ACCEPTER un dossier non vide, avec un sha juste
  mkdir -p "$t/plein"; printf 'temoin' > "$t/plein/f.bin"
  if ( manifeste "$t/plein" ) >/dev/null 2>&1 \
     && grep -q "$(printf 'temoin' | sha256sum | cut -d' ' -f1)" "$t/plein/MANIFEST.sha256"; then
    echo "✅ manifeste : accepte 1 fichier et son sha256 est juste"
  else echo "❌ manifeste : faux sur un dossier non vide"; ok=0; fi
  # 6. une option inconnue doit être refusée (pas ignorée en silence)
  if bash "$0" --option-qui-nexiste-pas >/dev/null 2>&1; then
    echo "❌ options : une option inconnue passe en silence"; ok=0
  else echo "✅ options : une option inconnue est refusée"; fi
  # 7. MULTI-BUILDS : trois versions → trois dossiers DISTINCTS, chacun nommé par sa build (L6/L7)
  OUT="$t/multi"; plan=$(pour_chaque_build "essai multi" 10 dofus3 'GameAssembly.dll' -- 3.6.4.3 3.6.10.10 3.6.10.11 2>&1)
  n=$(echo "$plan" | grep -c 'MODE PLAN')
  d=$(echo "$plan" | grep -o "$t/multi/[0-9._]*" | sort -u | wc -l)
  if [ "$n" -eq 3 ] && [ "$d" -eq 3 ]; then
    echo "✅ multi-builds : 3 versions → 3 dossiers distincts, chacun portant sa build"
  else echo "❌ multi-builds : $n plans, $d dossiers (3 et 3 attendus)"; ok=0; fi
  # 8. … et le dossier porte la build NORMALISÉE (témoin : une version absente ne doit pas apparaître)
  if echo "$plan" | grep -q "$t/multi/6.0_3.6.4.3" && ! echo "$plan" | grep -q "$t/multi/9.9.9.9"; then
    echo "✅ multi-builds : le chemin porte la build normalisée ; une build non demandée n'apparaît pas"
  else echo "❌ multi-builds : chemin sans build, ou build fantôme"; ok=0; fi
  # 9. --out manquant doit être REFUSÉ (sinon les builds s'écrasent dans le même dossier)
  if bash "$0" il2cpp 3.6.10.10 >/dev/null 2>&1; then
    echo "❌ --out : absent et accepté — les builds s'écraseraient"; ok=0
  else echo "✅ --out : absent → refusé"; fi
  # 10. NORMALISATION : une version nue doit recevoir le préfixe, une version préfixée ne doit PAS
  #     être préfixée deux fois, et `latest` doit passer intacte.
  n1=$(normaliser_version 3.6.4.3); n2=$(normaliser_version 6.0_3.6.4.3); n3=$(normaliser_version latest)
  if [ "$n1" = "6.0_3.6.4.3" ] && [ "$n2" = "6.0_3.6.4.3" ] && [ "$n3" = "latest" ]; then
    echo "✅ normalisation : 3.6.4.3 → $n1 · 6.0_3.6.4.3 → $n2 (pas de double préfixe) · latest → $n3"
  else echo "❌ normalisation : $n1 / $n2 / $n3"; ok=0; fi
  # 11-12. CONTRÔLE DU MANIFESTE, avec témoin POSITIF (build réelle) et NÉGATIF (build inventée).
  #        Sans réseau, on le DIT et on ne compte pas le contrôle comme réussi.
  if curl -s -o /dev/null --max-time 20 https://cytrus.cdn.ankama.com/cytrus.json; then  # sec-ok: S3 -- declared: Ankama's public build-manifest CDN, this tool's documented purpose
    if ( verifier_manifeste 6.0_3.6.4.3 dofus3 ) >/dev/null 2>&1; then
      echo "✅ manifeste : une build RÉELLE (6.0_3.6.4.3) passe le contrôle"
    else echo "❌ manifeste : une build réelle est refusée"; ok=0; fi
    if ( verifier_manifeste 6.0_9.9.9.9 dofus3 ) >/dev/null 2>&1; then
      echo "❌ manifeste : une build INVENTÉE passe le contrôle — la garde est inerte"; ok=0
    else echo "✅ manifeste : une build INVENTÉE (6.0_9.9.9.9) est refusée"; fi
  else
    echo "ℹ️  manifeste : réseau indisponible — les 2 contrôles n'ont PAS été faits (ni verts, ni rouges)"
  fi
  rm -rf "$t"
  cy=$(cytrus_cmd) && echo "ℹ️  cytrus disponible via : $cy" || echo "ℹ️  cytrus ABSENT ici (npm install -g cytrus-v6)"
  [ "$ok" -eq 1 ] && { echo "ÉPREUVE : le script refuse ce qu'il doit refuser"; exit 0; }
  echo "ÉPREUVE : SCRIPT INERTE"; exit 1
fi

CMD="${ARGS[0]:-}"; VERSIONS=("${ARGS[@]:1}")
case "$CMD" in
  versions)
    cy=$(cytrus_cmd) || { echo "REFUS : ni cytrus-v6 ni npx." >&2; exit 1; }
    for r in "$RELEASE"; do
      echo "commande : $cy version --game dofus --release $r --platform $PLATFORM"
      [ "$VRAIMENT" -eq 1 ] && $cy version --game dofus --release "$r" --platform "$PLATFORM"
    done
    ;;
  swf|il2cpp|complet)
    [ "${#VERSIONS[@]}" -gt 0 ] || { echo "REFUS : aucune version donnée." >&2; exit 2; }
    [ -n "$OUT" ] || { echo "REFUS : --out <dossier> est obligatoire (une build = un dossier ; sans lui elles s'écrasent)." >&2; exit 2; }
    # Les seuils de place sont SOURCÉS sur nos artefacts mesurés le 04/09, avec une marge :
    #   swf     64 Mo ← nos SWF pèsent 3,9 à 7,9 Mo (238/242/268/273)
    #   il2cpp 512 Mo ← GameAssembly.dll 115 Mo + global-metadata.dat 40 Mo = 155 Mo mesurés
    #   complet 12 Go ← le client 2.42 complet pèse 2,6 Go zippé ; le 3.0 n'a jamais été mesuré ici
    # Disk thresholds sourced from artefacts measured on 2026-09-04, with margin.
    case "$CMD" in
      swf)     pour_chaque_build "2.x — DofusInvoker.swf seul (entrée de la chaîne AS3)" 64 "$RELEASE" \
                 'DofusInvoker.swf' -- "${VERSIONS[@]}" ;;
      il2cpp)  pour_chaque_build "3.x — GameAssembly.dll + global-metadata.dat (entrée de la chaîne IL2CPP)" 512 dofus3 \
                 'GameAssembly.dll' '**/global-metadata.dat' -- "${VERSIONS[@]}" ;;
      complet) pour_chaque_build "CLIENT COMPLET — PLUSIEURS Go PAR BUILD" 12288 "$RELEASE" \
                 '**' -- "${VERSIONS[@]}" ;;
    esac
    ;;
  *)
    sed -n '2,22p' "$0"; exit 2 ;;
esac
