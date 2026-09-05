# RAPPORT-EXTRACTION-TIERS — otomai, sniffer, gatherer/luaxy, deobfs, classes-matcher

> Étage 1 (Namaste 3). Brief initial : deux extracteurs déterministes (0-LLM,
> stdlib) pour otomai/sniffer. **Étendu en deux passages successifs (même
> soirée, ordre team-lead)** : ajout de dofus3-gatherer + dofus3-classes-matcher,
> puis dofus-deobfs + dofus-unity-protocol-builder (LuaxY). Sources lues (lecture
> seule, rien exécuté, rien modifié) : `refs/otomai` (GPL-3), `refs/dofus3-sniffer-tui`
> (Go), `refs/dofus3-gatherer` (TS/Electron), `refs/dofus3-classes-matcher` (C#),
> `refs/dofus-deobfs` (Go), `refs/dofus-unity-protocol-builder` (Go, LuaxY).
> Outils écrits : `extraire_protocole_otomai.py`, `extraire_opcodes_sniffer.py`,
> `extraire_protocole_gatherer.py`, `extraire_protocole_luaxy.py`,
> `extraire_protocole_deobfs.py`, `_lib_proto3.py`, `comparer_instruments.py`,
> `comparer_stabilite_builds.py` (rapport séparé : `STABILITE-BUILDS.md`).

## 1. Chiffres mesurés (chaque compte remesuré par un second chemin, §00-CAHIER §ETAGE1)

| Fait | Valeur | 1ère mesure | 2ème mesure (indépendante) |
|---|---|---|---|
| Classes ProtoContract otomai (Game+Connection) | 1558 | `extraire_protocole_otomai.py` (parseur récursif à accolades) | `re.findall(r'public partial class \w+\s*:')` sur les mêmes fichiers |
| Champs ProtoMember otomai | 3698 | idem (après correction, voir §5) | `grep -c 'ProtoBuf.ProtoMember('` |
| Enums protobuf réels otomai | 149 | idem | `grep -c 'public enum'` = 217, moins 68 enums `XxxOneofCase` **sans** attribut `[ProtoContract]` (discriminateurs C# internes, pas des types protobuf — vérifié un par un, cf. §5) |
| Opcodes 3 lettres top-level otomai | 1285 | idem | `grep -ohE 'TypeUrl => "[a-z]{3}"'` \| sort -u |
| Lignes du dump 1003 noms | 1003 total, 513 top-level | `wc -l` + filtre `'+' not in ligne` | conforme au 513 déjà cité par `internal/GATE-G0-RAPPORT.md` |
| Noms feuille uniques du dump (top-level) | 512 | `set()` des 513 | doublon isolé : `CharacterInformation` existe dans `Connection.Protocol` ET `Game.Protocol.Infinite.Dream` (2 espaces de noms distincts, sans conséquence) |
| JondoEmu `anclas_3.6.10.10.tsv` | 293 opcodes documentés, **99 nommés** | lecture directe du TSV curé | — (fichier déjà curé par Jondo, pas de recomptage indépendant pertinent) |
| JondoEmu `protocolo_3.6.10.10.proto` | 2169 blocs `message` | `re.findall(r'^message (\w+) \{')` | `grep -c '^message '` = 2169 |
| JondoEmu `mapeo_..._a_3.6.10.10.tsv` | 1530 lignes, **0 avec un nom rempli**, 245 "estructura", 1285 "duda" | lecture directe | — ce fichier sert au matcher STRUCTUREL inter-versions de Jondo, **pas** à une table de noms ; à ne pas lire comme telle par erreur |
| dofus3-sniffer-tui : `.proto` embarqués | **0** | `find *.proto *.pb *.bin` sur tout l'arbre | `grep -rn embed` (aucun `go:embed`) sur tout l'arbre — même verdict |
| dofus3-sniffer-tui : lignes opcode↔nom littérales | 8 (aucune n'est une donnée Dofus mesurée — voir §4) | `extraire_opcodes_sniffer.py` sur les 3 seuls fichiers qui en portent | recherche manuelle `grep -n 'type.ankama.com\|type\.x/\|type\.test/'` sur tout le dépôt → mêmes 3 fichiers, rien ailleurs |
| otomai ∩ dump (noms clairs) | **335/512 (65%)** | `comparer_instruments.py` | recoupé à la main sur 15 noms avant d'écrire le script (§3) |
| otomai ∩ JondoEmu (noms clairs) | **2/99** (`MapMovementConfirmRequest`, `MapMovementConfirmResponse`) | idem | idem |
| otomai ∩ JondoEmu (mêmes 27 OPCODES, accord sur le nom) | **0/27** | idem | vérifié à la main sur les 10 premiers désaccords |
| gatherer : `.proto` clairs | 79 fichiers, 1480 messages, 3222 champs | `extraire_protocole_gatherer.py` | `re.findall` indépendant sur les mêmes fichiers → 1480/140 enums/3222, exact |
| gatherer vs luaxy (dofus-unity-protocol-builder) `.proto` | **byte-identiques, 79/79, 0 différence** | `diff -rq` (shell) | `sha256` par fichier dans `comparer_stabilite_builds.py`, même verdict — **ce n'est PAS un second instrument** |
| dofus-deobfs `.proto` (tout le dépôt) | 1441 au total, mais **1362 seulement** sont une donnée obfusquée propre à l'outil | `find -iname` naïf = 1441 | `protos/clear/` (79) = une 3ᵉ copie byte-identique de LuaxY, mesurée par `sha256` — vrai compte deobfs = 1362 |
| gatherer ∩ otomai (noms) | **1202/1239 (97%)** | `comparer_stabilite_builds.py` | recoupé à la main sur 10 noms avant d'écrire le script |
| gatherer vs otomai, champs sur les 1202 communs | 80.3% même NOMBRE de champs, 59.5% même catégorie de type | idem | — (échantillon déjà 50× plus grand que otomai/Jondo, pas de recomptage manuel séparé jugé nécessaire) |
| `dofus-deobfs/protos/filtered` : noms clairs présents | **0/1362** | lecture des noms de fichiers (tous 3 lettres) | confirmé par le README du dépôt lui-même (mapping produit au runtime, `reports/` gitignored) |

## 2. La méthode `proto-sync` d'otomai — patron pour notre étage 4 (15 lignes)

`otomai/tools/proto-sync/` (Python, `main.py`+`parser.py`+`registry.py`+`diff.py`+`codegen.py`)
régénère le protocole d'otomai à chaque changement de build client. Méthode :

1. **`snapshot`** : parse tous les `.cs` d'un dossier source (`vendor/Bubble.D3.Bot/.../Protocol/Game`)
   avec des regex sur les attributs `protobuf-net` (`ProtoContract`, `TypeUrl =>`, `ProtoMember(N, Name=@"x")`).
2. Chaque message parsé devient un `MessageDef` (nom, typeUrl, champs, imbrications, enums) — une structure,
   pas du texte.
3. Le snapshot est **horodaté et versionné** dans un `registry/` sur disque (JSON).
4. **`diff`** compare deux snapshots (versions successives) et produit un rapport Markdown des messages
   ajoutés/retirés/modifiés — sert de **radar de changement de build**, pas juste de doc.
5. **`generate`** régénère les `.cs` protobuf-net depuis un snapshot, et un `game_mappings.json`
   (opcode → nom clair) dérivé mécaniquement des `MessageDef` déjà nommés.
6. **`sync`** enchaîne les 4 étapes en une commande.
7. Le point clé pour nous : **la source de vérité est le CODE C# généré par LEUR pipeline de
   décompilation**, pas une liste éditée à la main — `game_mappings.json` est un SOUS-PRODUIT du
   snapshot, jamais l'inverse.

**Pour notre étage 4** (« régénération du protocole à chaque version », §5 cahier) : le même patron
s'applique à notre dump — un `snapshot` de nos 1003 noms + champs résolus par version de client, un
`diff` entre deux dumps successifs pour voir ce qu'Ankama a changé, avant de relancer le matcher.

## 3. Version de client visée par chaque tiers (mesuré, pas déduit du nom du dossier)

- **otomai** : **aucune chaîne de version `3.x.x.x` trouvée nulle part dans le dépôt** (`.md`, `.json`,
  `.csproj`, `.txt` — mesuré, 0 résultat). Le seul signal disponible est **le vocabulaire des noms
  clairs** : 65% (335/512) des noms top-level du dump s'y retrouvent à l'identique — un signal bien
  plus fort qu'une collision d'opcode (voir §4), parce qu'un nom de classe anglais est un espace
  d'environ 10⁶+ possibilités contre ~17 576 pour un opcode 3 lettres. **Conclusion mesurée : otomai
  vise un build PROCHE du nôtre (3.6.x), pas forcément 3.6.10.10 exactement** — 35% des noms divergent,
  compatible avec quelques builds d'écart.
- **JondoEmu** : **3.6.10.10 explicite** (nom de fichier `anclas_3.6.10.10.tsv`, `protocolo_3.6.10.10.proto`) —
  notre build cible exact.
- **dofus3-sniffer-tui** : **3.5.11.14 explicite**, mais UNIQUEMENT dans l'exemple d'usage du README
  (`README.md:31` : « For `3.5.11.14` : connection envelope = `leo`, game envelope = `gui` ») — un build
  **antérieur** au nôtre. Le code lui-même ne vise AUCUNE version : il charge n'importe quel `.proto`
  fourni au runtime (voir §4). Cette différence de build explique et RELATIVISE (sans l'excuser comme
  faux) le désaccord `iri` du §4 : ce n'est pas une erreur du sniffer, c'est un autre instantané.
- **dofus3-gatherer / dofus-unity-protocol-builder (LuaxY)** : **aucune chaîne de version trouvée**
  (0 résultat `3.x.x.x` dans les deux dépôts). Datation indirecte convergente : (a) le `go_package`
  interne des `.proto` (`go-xp-dofus-unity-proto-builder`) et le commit LuaxY d'origine sont d'octobre
  2024 ; (b) le protocole qu'ils décrivent utilise `type.ankama.com/<nom.complet.clair>` comme identifiant
  de fil — **jamais un opcode 3 lettres** (mesuré dans `dofus-unity-protocol-builder/src/protocol/
  protocol.go:100` : `TypeUrl: typeUrlPrefix + string(...Descriptor().FullName())`). Si cette lecture du
  code reflète bien le protocole réel de l'époque (pas juste une convention interne à l'outil, à
  vérifier contre une vraie capture 2024 si elle existe), **l'obfuscation en codes 3 lettres serait
  arrivée APRÈS ce snapshot** — cohérent avec le statut « outdated » assumé par l'auteur et avec le fait
  que otomai/JondoEmu (2026) portent tous deux des opcodes 3 lettres alors que gatherer/luaxy n'en ont
  aucun. DÉDUIT, à vérifier : chercher une capture réseau Dofus 3.0 antérieure à 2025 et voir si son
  `type_url` est un nom clair ou un code court.
- **dofus-deobfs** : **aucune chaîne de version trouvée** dans le dépôt ; son README ne mentionne pas de
  build cible et le snapshot commité (`protos/filtered/`) ne porte aucun horodatage. Contrairement à
  gatherer/luaxy, ses identifiants SONT des codes 3 lettres obfusqués (comme otomai/Jondo) — donc il vise
  un build POSTÉRIEUR à l'introduction de l'obfuscation, mais rien ne permet de dater plus précisément
  sans les rapports de matching (absents du commit, voir §4bis).

## 4. Ce que porte réellement dofus3-sniffer-tui — la trouvaille structurelle

Avant d'écrire l'extracteur, la lecture de `internal/protoreg/mappings.go` et `registry.go` a montré
que ce dépôt **ne contient aucune table opcode↔nom** : `mappings.go` est du code GÉNÉRIQUE qui charge un
JSON de renommage fourni par l'opérateur au runtime (`--mapping-paths`), et `registry.go`/`compiler.go`
COMPILENT des `.proto` également fournis au runtime (extraits ailleurs, par un AUTRE outil, des DLL
`Ankama.Dofus.Protocol.{Connection,Game}`). Mesuré : 0 fichier `.proto`, 0 JSON de mapping, 0
`go:embed` dans tout l'arbre. Les 8 lignes que l'extracteur sort sont :
- 2 exemples du **README** (`iri`→`MapMovementRequest`, `irl`→`MapMovementEvent`+champ `fhtj`→`actor_id`,
  build 3.5.11.14, cf. §3) — les seules à ressembler à de vraies données Dofus, mais non vérifiables ici.
- 2 exemples du **docstring** de `mappings.go` (`ij`→`Hello`, `kl`→`Goodbye`) — **fictifs, le code le
  dit lui-même** (« simple: just message rename »).
- 4 fixtures des **tests unitaires** `mappings_test.go` (`ab`→`Alpha`, `cd`→`Charlie`, `ij`→`Hello`,
  `Inner`→`FriendlyInner`) — des noms de test Go (`tiny.proto`), sans rapport avec Dofus.

Conséquence pour le chantier : **le sniffer est un outil de FRAMING/DÉCODAGE (varint + enveloppe Any/
imbriquée + reassembly TCP), pas une source de noms**. Sa vraie valeur pour Namaste 3 est décrite dans
son propre brief (§1, ligne « sniffer/décodeur de trames 3.0 ») : le patron d'auto-détection
d'enveloppe (`detectEnvelope`, styles `AnyWrapped` vs `Nested`) et le resync sur flux TCP déjà en cours
(`internal/capture/stream.go`, glissement d'un octet sur varint invalide) sont directement réutilisables
pour notre étage 5 (sniffer/décodeur), **indépendamment** de toute table de noms.

## 4bis. gatherer/luaxy/deobfs — détail complet dans `STABILITE-BUILDS.md`

Trois trouvailles condensées ici (le rapport dédié porte l'annexe complète) :

1. **gatherer VENDORISE luaxy à l'octet près** (`diff -rq` sur les 79 `.proto` → 0 différence ; `go_package`
   interne encore `go-xp-dofus-unity-proto-builder`). Et `dofus-deobfs/protos/clear/` est une **3ᵉ copie**
   de la même chose. Ces trois occurrences comptent pour **UN SEUL instrument** dans tout calcul
   d'accord — le compte naïf « 1441 .proto chez deobfs » mélange 1362 fichiers réellement propres à
   l'outil et 79 qui sont LuaxY une fois de plus.
2. **gatherer ∩ otomai (noms) = 1202/1239 (97%)**, sur un échantillon 50× plus grand que otomai/JondoEmu —
   la stabilité des NOMS et du NOMBRE DE CHAMPS (80,3% identiques) entre un snapshot ~2024 et notre build
   3.6.10.10 est réelle et forte, là où l'accord sur les OPCODES reste nul (§5). **Ce qui survit aux
   patchs : le nom et la structure. Ce qui ne survit jamais : le code 3 lettres.**
3. **`dofus-deobfs/protos/filtered` (1362 fichiers) ne porte AUCUN nom clair** dans ce commit (le mapping
   est un produit de runtime non committé) — 0 jointure par nom possible. Sa valeur pour nous est
   MÉTHODOLOGIQUE (matcher structurel contre les protos clairs de LuaxY), pas tabulaire.

## 4ter. La méthode de dofus3-classes-matcher — pour le chantier matcher, pas pour moi

`SourceMatcher` (C#/.NET 8, Roslyn, prototype inachevé assumé par son auteur) répond à un problème
DIFFÉRENT du nôtre — pas « nommer un build jamais vu », mais **suivre un nom déjà connu d'un build à
l'autre** (le problème de l'ÉTAGE 4, pas de l'étage 1) :
- **Entrée** : le C# décompilé de DEUX versions (`v1` déjà étiqueté par nous, `v2` fraîchement obfusqué)
  + un manifeste JSON nommant QUOI mapper (classes/champs/fonctions ciblés — semi-supervisé, ne découvre
  rien seul).
- **Critère** : un score de similarité structurelle PONDÉRÉ par classe — champs `const` (littéraux, poids
  0,40, le signal le plus fort car jamais obfusqué), nombre de classes de base (0,40), attributs
  `[DependsOnService]` (0,40), écart de nombre de méthodes/types imbriqués (0,40 chacun), recouvrement
  de types de champs (0,10), signatures de méthode (0,05) — le meilleur candidat `v2` gagne, avec alerte
  si l'écart avec le 2ᵉ est `< 0,10` (zone à faux positifs). Champs appariés PAR POSITION dans la classe
  gagnante ; fonctions par signature exacte, puis par signature avec types non-primitifs normalisés à
  `object`.
- **Sortie** : un `Defines.h` (`#define NomAmi "Class_obfusquée"`), pas un graphe ni une base de données.
- **Différence avec Jondo (WL round-0, `matcher.py` de ce dépôt)** : Jondo/notre matcher opèrent sur des
  MESSAGES PROTOBUF exclusivement (numéros de champ + types + voisinage du graphe de références,
  un domaine homogène et étroit) et n'ont PAS besoin d'un `v1` déjà étiqueté pour chaque candidat.
  SourceMatcher vise des CLASSES C# GÉNÉRALES (logique de jeu : méthodes, héritage, attributs DI,
  membres générés par le compilateur) et EXIGE un côté `v1` déjà résolu — inutilisable pour notre
  bootstrap (aller de 0 nom à un premier nom), mais c'est EXACTEMENT le bon outil pour l'étage 4 une
  fois nos 3.6.10.10 étiquetés : suivre ces noms dans 3.6.10.11, 3.6.11.x, etc., avec un vocabulaire de
  fingerprint plus riche que les seuls numéros de champ.

## 5. Accord/désaccord entre instruments — la trouvaille centrale (détail : `ACCORD-INSTRUMENTS.md`)

**otomai ∩ JondoEmu, jointure par OPCODE (27 collisions) : 0/27 accord sur le nom.** Zéro. Cela confirme
EXACTEMENT le piège déjà écrit dans le cahier des charges pour 2.42→2.73 (« une jointure par id
rendrait ~872 paires TOUTES fausses avec l'apparence d'un succès ») — ici mesuré ENTRE DEUX OUTILS
visant nominalement le MÊME build. **Un opcode 3 lettres identique dans deux extractions indépendantes
ne prouve rien : c'est une collision dans un espace de ~17 576 codes, pas un identifiant stable.**

**otomai ∩ JondoEmu, jointure par NOM (la voie qui marche)** : 2 messages seulement partagent un nom
(`MapMovementConfirmRequest`, `MapMovementConfirmResponse`) — et même là, les OPCODES diffèrent
(`igg`/`jqi`, `ifs`/`jsq`). Le nom est le seul axe qui survit à la comparaison ; l'opcode ne l'est pas.

### Les 5 désaccords les plus parlants

1. **`jru` — l'opcode du CHEMIN CRITIQUE** (« charger la carte », `chemin-critique.txt`, cahier §ETAGE1).
   otomai : `jru` = `ReadyToLeaveArenaResponse`. JondoEmu (99 captures + code, doc `opcodes.md`) : `jru` =
   « Load this map » (nommé `CurrentMapMessage` dans `anclas_3.6.10.10.tsv:41`). **Si l'étage 1
   avait pris la table otomai telle quelle pour `jru`, il aurait câblé le mauvais handler sur l'opcode le
   plus rejoué des 242 captures (719 occurrences).**
2. **`jsj` — le mouvement confirmé**. otomai : `ArenaFightAnswerResponse`. JondoEmu : `GameMapMovementMessage`
   (« le mouvement confirmé ; le sauter laisse l'acteur avec une orientation à zéro »). Même famille de
   risque que `jru` : un opcode du chemin de déplacement, totalement mal identifié par simple lecture
   opcode-à-opcode entre les deux tables.
3. **`jqi`**. otomai : `BakBufferListRequest`. JondoEmu : `MapMovementConfirmRequest` — et la jointure par
   NOM (§ci-dessus) montre que `MapMovementConfirmRequest` existe bien chez otomai, mais sous l'opcode
   `igg`, pas `jqi`. Triangulation propre : le nom est fiable, l'opcode ne l'est pas, sur CE cas précis
   on peut le prouver par un chemin indépendant.
4. **Champs de `MapMovementConfirmRequest`/`Response` — MISE À JOUR après ajout de gatherer** : otomai
   déclare les deux messages **vides** (0 champ). Le `.proto` de Jondo leur donne **1 champ chacun** (`f1`,
   type message). Ajout de gatherer/luaxy (indépendant des deux, ~2024) : `gamemap.proto:19` donne aussi
   **0 champ** pour `MapMovementConfirmRequest`. **2 instruments indépendants sur 3 (gatherer ET otomai)
   s'accordent sur « vide » ; seul le `.proto` reconstruit de Jondo déclare un champ — et la propre table
   `anclas_3.6.10.10.tsv:jqi` de Jondo (issue des 242 CAPTURES RÉELLES, pas de la reconstruction structurelle)
   dit elle-même `forma: empty`.** Triangulation complète : le contenu observé sur le fil (Jondo/anclas) et
   deux reconstructions de schéma indépendantes (otomai, gatherer) s'accordent contre le SEUL `.proto`
   structurel de Jondo — ce dernier porte vraisemblablement un champ jamais réellement peuplé/envoyé
   (cohérent avec le §2.3 de `opcodes.md` : proto3 omet les champs à valeur zéro, un champ déclaré peut
   très bien n'apparaître nulle part en pratique).
5. **`iri` (sniffer vs otomai)** : le seul exemple non-synthétique du sniffer (README, build 3.5.11.14)
   donne `iri` = `MapMovementRequest`. otomai (build plus récent, §3) donne `iri` = `ObjectAveragePricesRequest`.
   Dérive de build concrètement visible sur un seul opcode, cohérente avec la loi du cahier sur le
   renumérotage inter-versions.

## 6. Ce que ça change pour le matcher (`tools/protocol-mapping/matcher/`, jamais modifié ici)

Le commentaire d'en-tête de `matcher.py` explique le problème central : les 1003 noms clairs du dump
sont des **littéraux orphelins** — aucun numéro de champ, aucun type résolu ne leur est associé côté
dump, seulement une position dans l'arbre d'imbrication (`Foo+Types+Bar`). Le seul axe de score
actuel du matcher est donc la FORME D'IMBRICATION, un signal faible (beaucoup de candidats à égalité,
ex. 18 candidats à égalité pour `CharacterInformation`, cf. `correspondance-noms-classes.tsv`).

**otomai comble une partie de ce trou, sous conditions strictes** : pour les **335 noms** confirmés
communs à otomai et au dump (§1), `protocole-otomai.tsv` donne un NOMBRE DE CHAMPS et des TYPES
GROSSIERS (numérique/string/liste/message…) pour ce nom. Le matcher pourrait s'en servir comme
**second axe de score DÉDUIT** (jamais `VÉRIFIÉ`) : parmi les candidats obfusqués à égalité de forme
pour un nom donné, préférer celui dont le nombre de champs propres (déjà résolu par
`extraire_signatures.py`, 6277 champs résolus sur 2206 classes `IBufferMessage`, cf.
`extraction-stats.json`) est le plus proche du nombre de champs otomai pour ce nom.

**Mise en garde mesurée dans ce même rapport (§5, point 4)** : le nombre de champs N'EST PAS un signal
fiable à 100% même sur un nom confirmé — sur les 2 seuls cas croisés avec Jondo, otomai sous-compte
d'1 champ à chaque fois. Ce signal doit donc rester un DÉPARTAGEUR de candidats à égalité, jamais un
critère d'élection seul, et toute correspondance qu'il produit reste `À_CLASSER`→`DÉDUIT` avec
`comment_verifier` explicite (contre une capture réelle), jamais `VÉRIFIÉ`, exactement dans l'esprit
du garde déjà écrit par matcher.py.

Second usage possible, plus modeste : otomai porte, pour une partie de ses champs, un nom déjà
DÉOBFUSQUÉ en snake_case lisible (ex. `map_id`, `start_map_id` — mesuré : field `Name=@"..."` contient
un `_` dans une fraction notable des 3698 champs, non chiffrée précisément ici faute de temps ; à
mesurer si l'étage 1 veut s'en servir comme SEED pour le renommage de champs, §1 du cahier
« déobfuscation »). Ce n'est utile qu'APRÈS qu'un nom de message ait été validé par ailleurs — jamais
comme preuve d'identité du message lui-même.

**Mise à jour après ajout de gatherer** : `protocole-gatherer.tsv` renforce ce départageur plutôt que de
le remplacer — 1202 noms croisent DÉJÀ otomai (97% d'accord sur le nombre de champs à 80%, §4bis), donc
pour un nom candidat présent dans les DEUX tables, le matcher dispose de deux votes indépendants (pas
un seul) avant de préférer un candidat obfusqué. Gatherer porte aussi des noms de CHAMPS toujours en
clair (`snake_case` complet, jamais obfusqué contrairement à otomai qui ne l'est que partiellement) —
la meilleure graine disponible pour le renommage de champs une fois un message identifié, MAIS datée
~2024 (§3) : à ne proposer qu'en `DÉDUIT`, jamais `VÉRIFIÉ`, un champ ajouté/retiré/renommé depuis reste
possible (mesuré : 9,4% des champs communs otomai/gatherer sont présents d'un seul côté, §4bis point 3
de `STABILITE-BUILDS.md`).

## 7. Mes trous et mes erreurs (ce qui a raté avant d'être corrigé, mesuré dans les deux sens)

1. **Récursion infinie** (`extraire_protocole_otomai.py`) : ma première version de `walk()` rappelait
   `collect_children` sur `[attr_start, close_end)` d'un nœud — un intervalle qui contient TOUJOURS le
   nœud lui-même — et rescannait donc indéfiniment sa propre étiquette `[ProtoContract]`. Corrigé en
   ne recursant que sur l'INTÉRIEUR des accolades (`body_start, body_end`). Repéré immédiatement par
   `--epreuve` (RecursionError sur le témoin imbriqué).
2. **Arguments nommés en trop sur `ProtoMember`** : `[ProtoMember(1, Name=@"dzne", IsPacked = true)]`
   (Hdb.cs, Hej.cs) ne matchait pas une regex ancrée juste après `Name`. Perte SILENCIEUSE mesurée :
   68 champs sur 3698. Corrigé (`[^)]*` avant la parenthèse fermante) — même famille de piège que celle
   déjà notée dans `extraire_handlers.py` pour les attributs Jiva (26/232 ratés pour la même raison).
3. **Classe de caractères du type incomplète** : `global::System.Collections.Generic.List<int>` ne
   matchait pas une regex de type sans `:` dans sa classe de caractères. Perte silencieuse mesurée :
   470 champs supplémentaires (tous les champs `List<>`/`Dictionary<>` qualifiés). Les deux bugs
   combinés faisaient chuter le compte de champs de 3698 (vrai, mesuré par grep) à 3228 — un écart de
   470 qui aurait pu passer pour "normal" sans le second comptage indépendant systématique.
4. **`extraire_opcodes_sniffer.py`** : la forme étendue du docstring Go (`"kl": {  // extended: ...`
   suivi de `"name": "Goodbye"` sur la ligne d'après, préfixée `//`) ne matchait pas ma regex ancrée sur
   des espaces purs après `\n`. Conséquence en cascade : la regex de repli (forme plate) capturait alors
   la clé RÉSERVÉE `"name"` comme si c'était un opcode (`"name" → "Goodbye"`), et l'opcode réel `kl`
   disparaissait. Corrigé par une regex tolérante au commentaire ET une exclusion explicite des clés
   `name`/`fields`.
5. **Rattachement des renommages de champ à un mauvais message parent** : mon 1er rattachement prenait
   le premier candidat trouvé dans un ordre de liste arbitraire (pas forcément le plus proche en ligne),
   et attachait le bloc `"fields"` de `kl`/`Goodbye` (ligne 25-31) au message `ij`/`Hello` (ligne 24) au
   lieu de `kl`. Corrigé par une sélection de distance minimale.

Tous ces bugs ont été trouvés par le SECOND comptage indépendant (grep brut vs sortie du script), pas
par relecture — exactement la discipline que le cahier demande (« tout compte se remesure par un
second chemin avant d'être cité »). Tous les extracteurs et les deux comparateurs passent `--epreuve`
(rejeu sha256 identique + sabotage détecté + partition vérifiée) après correction.

6. **Second passage (gatherer/luaxy/deobfs)** : aucun bug de PARSING cette fois (le parseur `_lib_proto3.py`
   a été validé sur les deux comptages indépendants dès la 1ʳᵉ tentative — profité de l'expérience du
   1er passage). L'erreur ici a été de PREMIÈRE INTENTION prendre le compte naïf `find -iname "*.proto"`
   de dofus-deobfs (1441) pour argent comptant sans vérifier sa composition — corrigé en mesurant
   `protos/clear/` vs `protos/filtered/` séparément avant d'écrire l'extracteur, pas après (§4bis).
   Piège évité, pas piège vécu — mais je le note car c'est le même réflexe (« tout compte issu d'une
   extraction se remesure ») qui l'a évité.

## 8. Sorties de ce chantier

- `extraire_protocole_otomai.py`, `protocole-otomai.tsv` (1558 lignes), `a-classer-otomai.tsv` (2 lignes)
- `extraire_opcodes_sniffer.py`, `opcodes-sniffer.tsv` (8 lignes, toutes non-authoritatives — voir §4)
- `_lib_proto3.py` (parseur .proto3 partagé), `extraire_protocole_gatherer.py` → `protocole-gatherer.tsv`
  (1480 messages), `extraire_protocole_luaxy.py` → `protocole-luaxy.tsv` (identique au précédent, voir
  §4bis), `extraire_protocole_deobfs.py` → `protocole-deobfs.tsv` (1553 messages, 0 nom clair)
- `comparer_instruments.py`, `ACCORD-INSTRUMENTS.md` (croisement otomai/sniffer/dump/JondoEmu)
- `comparer_stabilite_builds.py`, `STABILITE-BUILDS.md` (croisement gatherer/luaxy/deobfs, stabilité 18 mois)
- Ce rapport.

## 9. Statut

**DONE_WITH_CONCERNS.** Tous les extracteurs et les deux comparateurs sont verts (`--epreuve` inclus),
les chiffres sont mesurés deux fois. Le "concern" n'est pas un défaut d'outillage : c'est le RÉSULTAT
lui-même, sur deux plans distincts :
1. Par OPCODE, aucun des instruments tiers ne se recoupe avec notre build (0/27 otomai↔Jondo). Aucun
   consommateur en aval ne doit consommer une table tierce comme source d'opcodes pour NOTRE build sans
   revalider par le nom d'abord (§5-6).
2. Par NOM, l'accord est réel et même FORT quand l'échantillon est assez grand pour compter (gatherer↔
   otomai 97% sur 1202 noms, 80% de champs identiques) — mais ce même échantillon révèle que notre PROPRE
   dump (512 noms top-level) est nettement plus petit que ce que ces deux tiers indépendants couvrent
   (1239-1286 noms), une question ouverte pour étage0 (§3, à trancher par un grep direct dans le
   metadata). `opcodes-sniffer.tsv` et `protocole-deobfs.tsv` (0 nom clair) ne doivent jamais être cités
   comme preuve de quoi que ce soit sur le protocole — seulement comme preuve de ce que ces dépôts NE
   contiennent PAS en l'état.
