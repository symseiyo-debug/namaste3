# Fragment carte étage 1 — Données 3.0 nécessaires à l'entrée sur Astrub (191105026)

> Domaine : **données** (étage 1 — modèle de données). Question : quelles
> données le serveur 3.0 neuf doit tenir pour faire entrer un joueur sur Astrub (191105026) et le
> faire marcher, et lesquelles avons-nous déjà. Sources lues :
> `internal/artefacts/lot31-data-3.0-full/`, `internal/artefacts/lot30-data-3.0-extract/`,
> `internal/artefacts/lot37-mapdata-3.0/`, `dofus-tools/`, `refs/JondoEmu/datos/`,
> **`refs/JondoEmu/docs/`** (la légende des données Jondo — le dossier qui manquait à la v1),
> `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs`,
> `<sauvegarde interne datée du 04/09>/world_dev.sql.gz`.
> `PROD-DB` (base de production) jamais ouvert, jamais cité comme source. Tags **VÉRIFIÉ** (lu, fichier:ligne) / **DÉDUIT**
> (hypothèse, comment vérifier).
>
> **v2 du 05/09/2026** — révision après réfutation dédiée (`internal/REFUTATION-DEDIEE-DONNEES-3.0-20260904.md`)
> et REMESURE indépendante de chaque point. Détail point par point : `server/CORRECTIONS-DONNEES-3.0.md`.
> Trois corrections de fond : les bundles de géométrie sont ICI (§C), le gate de l'outil d'import était
> faux sur ses deux contrôles (§D), et la légende `f`/`b`/`c`/`g` était écrite dans un fichier du dépôt
> Jondo que la v1 n'a jamais ouvert (§0, §E).

## 0. Constats

**VÉRIFIÉ** — L'extraction de données 3.0 (lot31) se fait par bundle Unity Addressable, pas par
décompilation directe du client : `lot30-data-3.0-extract/extract_bundle.py` (UnityPy 1.25.3, un venv
local, aucune autre lib réseau que pip) lit chaque `.asset.bundle`, dump le `typetree` complet (source
de vérité) et reconstruit une liste `records` par une heuristique DataRoot/`objectsById`+`RefIds` —
`lot30-data-3.0-extract/OUTIL.md:1-58`. Mesuré sur l'échantillon du lot30 : `luaformulas.json` pèse
63 432 octets, porte 38 formules Lua lisibles, `object_count` 2, `decoded_count` 2. La copie du même
JSON dans lot31 pèse 63 522 octets — deux extractions, deux tailles : **citer le lot avec le chiffre**.

**VÉRIFIÉ** — `lot31-data-3.0-full/bundles/` porte **207 fichiers** : **205 `.bundle`** (204
`data_assets_<table>dataroot.asset.bundle` + `dd1a58a0aef1bbbf5107819064dfac09_monoscripts.bundle`)
plus `catalog_1.0.bin` (107 484 octets) et `catalog_1.0.hash`. **La v1 annonçait 204 : elle comptait
les `data_assets_` et oubliait le bundle de scripts, que le catalogue cite pourtant.** Ce catalogue est
complet pour lui-même, mais c'est un catalogue Addressables scindé aux seules données DataCenter
(items/sorts/monstres/cartes/…) : le catalogue de la géométrie est un AUTRE fichier, et il est
maintenant sur ce VPS lui aussi (§C).

**VÉRIFIÉ** — `lot31-data-3.0-full/json/` porte 206 fichiers JSON décodés depuis ces 205 bundles
(204 tables + `_manifest.json` + le bundle de scripts). Comptes mesurés via le champ `records_count`
de chaque JSON (source citée, valeur mesurée à part) : items 21 748 (`items.json:4137319`), monstres
5 134 (`monsters.json:4343961`), PNJ 6 467 (`npcs.json:1847657`), informations de carte 15 360
(`mapsinformation.json:506917`), coordonnées de carte 6 673 (`mapscoordinates.json:190958`),
références de carte 571 (`mapreferences.json:13170`). Les quatre premiers chiffres confirment ceux
annoncés dans le brief initial du projet, et non à une ligne différente comme
l'écrivait la v1 : le document source avait bougé sous la citation.

**VÉRIFIÉ** — La carte Astrub existe dans `mapsinformation.json` : `id: 191105026` apparaît deux fois
(entrée réelle + index `objectsById`) — `mapsinformation.json:186544` et `:414385`. Le record porte
`posX`, `posY`, `nameId`, `subAreaId`, `worldMap`, `tacticalModeTemplateId`, `m_flags` (plus `_class`
et `id`) — **aucun champ de géométrie de cellule** (pas de liste de cellules, pas de voisins). C'est
une fiche d'identité de carte, pas sa forme jouable. Valeurs mesurées : `posX` 5, `posY` −18,
`subAreaId` 95, `worldMap` 1.

**VÉRIFIÉ** — `mapscoordinates.json` relie coordonnées compressées → liste de `mapIds`. Premier record
reconstruit : `{"id": -327722, "_class": "MapsCoordinateData", "compressedCoords": -327722, "mapIds":
[156238850]}` — `mapscoordinates.json:128885-128891`. **La v1 citait `:1-10`, qui est l'en-tête du
dump** (`source_bundle`, `size_bytes`, `object_count`…) ; la forme BRUTE du même record, sans champ
`id`, est ailleurs encore, à `mapscoordinates.json:26779-26785`. Un dump `extract_bundle.py` porte donc
**deux vues du même record** — la brute (typetree) et la reconstruite (`records`) — et une citation qui
ne dit pas laquelle est ambiguë.

**VÉRIFIÉ** — `compressedCoords` encode bien `(posX << 16) | (posY & 0xFFFF)` : vérifié sur la
population entière, **15 360 correspondances sur 15 360, zéro écart**, en joignant chaque `mapIds` de
`mapscoordinates.json:128885-128891` au record de `mapsinformation.json:186544`, tous deux dans
`lot31-data-3.0-full/json/`. Astrub (5, −18) donne 393 198. **C'était un
DÉDUIT de la v1 ; la vérification coûtait trente secondes et n'avait pas été faite.**

**VÉRIFIÉ** — `refs/JondoEmu/datos/map_walkable_cells.json` (15 123 423 octets, une seule ligne —
`map_walkable_cells.json:1`) porte un dict `{mapId: [cellIds]}` sur **17 211 cartes** (mesuré
`len(json)`). La clé `"191105026"` porte **230 entiers** (ids de 91 à 487). **Mais ces 230 ne sont PAS
les cellules marchables d'Astrub** : `refs/JondoEmu/docs/world.md:48` et `refs/JondoEmu/docs/data.md:64`
disent que ce fichier **rogne les bords exprès** — colonnes 0-1 et 12-13, rangées 0-5 et 35-39 — pour
que les groupes de monstres n'apparaissent jamais sur un bord. C'est un **compte amputé**, produit par
`extract_all_map_walkable.py` (`data.md:34`). Le fichier entier porte 2 987 103 cellules, 173,6 par
carte, de 1 à 290. **La v1 y voyait un « second instrument » en CONCORDANCE EXACTE avec le brief :
c'est le même et unique fichier, et la coïncidence de deux chiffres identiques masquait une
sémantique différente.**

**VÉRIFIÉ** — `map_fight_cells.json` (20 682 578 octets, 17 222 cartes) porte pour CHAQUE carte un
sous-dict à **deux** clés, `f` et `b` — mesuré : les 17 222 entrées portent exactement ce jeu de clés,
sans exception. `refs/JondoEmu/docs/data.md:33` en donne la légende : `f` = cellules où l'on peut se
tenir en combat (`mov=1` ∧ `nonWalkableDuringFight=0`), `b` = cellules qui coupent la ligne de vue
(`los=0`). Sur Astrub : |f| = 357 (ids 7 à 554), |b| = 85. Ce fichier **garde la grille entière** —
`world.md:48` — là où le fichier marchable la rogne. **La v1 ne mentionnait jamais `b`, et déduisait
pour `f` un « placement de combat » que la doc contredit.**

**VÉRIFIÉ** — `refs/JondoEmu/datos/interactive_elements.json` (1 519 398 octets, 9 840 cartes) porte
par carte une liste d'objets `{"e": …, "c": …, "g": …}` — ex. carte 154644 :
`{"e": 435471, "c": 196, "g": 19726}` ; Astrub porte 4 éléments, le premier
`{"e": 514829, "c": 94, "g": 62995}` (`interactive_elements.json:1`). **La légende est écrite dans
`refs/JondoEmu/docs/data.md:36` : `{e: element id, c: cell, g: graphic}`.** Donc **`c` est une
CELLULE**, pas une catégorie : mesuré sur les 46 309 éléments du fichier, `c` prend 558 valeurs
distinctes toutes comprises dans 0..559, zéro hors bornes. Et la jointure vers
`tipos_interactivos_3.6.10.10.json` (415 entrées) se fait **sur `g` — 415 sur 415** ; sur `e` elle rend
**0 sur 415**. **La v1 déduisait `c` = catégorie et prescrivait de croiser sur `e` : les deux sont
faux, et l'épreuve prescrite aurait rendu zéro sans dire pourquoi.**

**VÉRIFIÉ** — Le client (`il2cpp.cs`) porte la classe cible côté cellule : `ClientCellData` —
`il2cpp.cs:123421-123458` — 17 champs : `cellNumber`(uint) `il2cpp.cs:123424`, `speed`(int),
`mapChangeData`(int), `moveZone`(int), `linkedZone`(int), `mov`(bool, marchable) `il2cpp.cs:123429`,
`los`(bool, ligne de vue) `il2cpp.cs:123430`, `nonWalkableDuringFight`(bool), `nonWalkableDuringRP`
(bool), `farmCell`(bool), `visible`(bool), `havenbagCell`(bool), `roleplayMonstersMovementBlocked`
(bool), `floor`(int) `il2cpp.cs:123437`, `red`(bool), `blue`(bool), `arrow`(int) `il2cpp.cs:123440`,
plus 4 propriétés `useTopArrow`/`useBottomArrow`/`useLeftArrow`/`useRightArrow`. (**La v1 plaçait
`cellNumber` à `il2cpp.cs:123422` : la ligne réelle est 123424.**)

**VÉRIFIÉ** — Des 17 champs de `ClientCellData`, **4 sont couverts par les fichiers Jondo et 13 ne le
sont pas** — l'ensemble de différence, que la v1 annonçait sans jamais l'écrire. Couverts :
`cellNumber` (l'identifiant lui-même), `mov` (via le fichier marchable, **rogné**),
`nonWalkableDuringFight` (déductible de `f`, combiné à `mov`), `los` (via la clé `b`, 85 cellules sur
Astrub) — `data.md:33`. Non couverts : `speed`, `mapChangeData`, `moveZone`, `linkedZone`,
`nonWalkableDuringRP`, `farmCell`, `visible`, `havenbagCell`, `roleplayMonstersMovementBlocked`,
`floor`, `red`, `blue`, `arrow`. **La v1 comptait `los` parmi les trous : il n'en était pas un.**

**VÉRIFIÉ** — `ClientMapData` — `il2cpp.cs:123604-123645` — porte, en plus de `cellsData:
List<ClientCellData>` (`il2cpp.cs:123625`), les 4 voisins (`topNeighbourId` `il2cpp.cs:123607` et ses 3
pairs), les listes d'éléments (`backgroundElements`, `foregroundElements`, `animatedElements`,
`interactiveElements`), les flèches de bord de carte (`topArrowCellList`…), le son/playlist, la météo.
**Deux de ces familles ne sont PAS des trous** : les 4 voisins sont dans `world.db.MapScrolls` et les
interactifs dans `datos/interactive_elements.json`. Restent en trou la géométrie par cellule, le décor
et la météo — jusqu'aux bundles du §C.

**VÉRIFIÉ** — Le nombre de cellules d'une carte vaut **560** : `private const int CellsCount = 560` —
`il2cpp.cs:245096` (classe `FightMapPreviewUi`) et `il2cpp.cs:332686`. La même classe porte
`Column = 14` (`il2cpp.cs:245097`), et 14 × 40 fait 560 — ce qui **recoupe indépendamment** la
description du rognage de `data.md:64` (colonnes 0..13, rangées 0..39). Troisième contrôle : sur
Astrub, l'id de cellule le plus haut mesuré vaut 554 (fichier de combat) et 487 (fichier marchable),
tous deux sous 560. **C'était un DÉDUIT « valeur historique Dofus, à confirmer sur un bundle » ; la
constante était dans le fichier déjà ouvert par ailleurs.** Réserve honnête : elle est déclarée dans
deux classes d'INTERFACE, pas dans la classe de données — c'est ce que le client dessine.

**VÉRIFIÉ** — Dans `JondoEmu/datos/`, l'archive `world.zip` contient un unique fichier `world.db`
(SQLite, 249 262 080 octets), le SGBD SERVEUR de Jondo lui-même — **40 tables** (41 avec
`sqlite_sequence`). `MapTemplates` a 3 colonnes (`Id`, `SubAreaId`, `Data` texte JSON) et 15 360
lignes — même population que `mapsinformation.json`. `InteractiveTeleports` compte 3 815 lignes, dont
**0 pour Astrub**. Le `Data` d'Astrub fait 136 octets et porte la même fiche d'identité que lot31, sans
géométrie. **Nuance que la v1 écrasait en disant « exactement »** : la chaîne réelle sépare ses champs
par `", "` (136 octets), la chaîne recopiée dans la v1 était compactée (121 caractères) — même contenu,
**pas les mêmes octets**, et « exactement » ne se dit pas d'une valeur qu'on a reformatée.

**VÉRIFIÉ** — **Les 4 voisins d'Astrub sont dans la base Jondo, en 3.0** : `world.db.MapScrolls`
(colonnes `MapId`, `RightMapId`, `BottomMapId`, `LeftMapId`, `TopMapId`), **17 353 lignes** —
`refs/JondoEmu/docs/world.md:31`. Astrub : droite 191106050, bas 191105028, gauche 191104002, haut
191105024. **La v1 listait cette table au §0 puis déclarait les voisins absents au tableau (A) : la
réponse était dans une ligne qu'elle avait elle-même écrite.**

**VÉRIFIÉ** — **Les spawns de monstres par carte existent aussi** : `world.db.MapMobs` (`Id`, `MapId`,
`MobId`, `CellId`, `MembersJson`), **38 744 groupes sur 12 907 cartes** — `world.md:35`. Astrub porte
**3 groupes**, sur les cellules 350, 344 et 327, chacun avec sa composition en JSON. La table que la v1
désignait, `world.db.NpcSpawns`, porte **53 lignes au total et 0 pour Astrub** : elle existe, mais ce
n'est pas celle qui peuple une carte de monstres.

**VÉRIFIÉ** — L'opcode d'entrée en carte est identifié côté Jondo (manuel, non confronté au client
vivant dans ce fragment) : `jru` = `CurrentMapMessage`, S2C, `f2` = mapId — `anclas_3.6.10.10.tsv:39`
(« Carga este mapa; enviarlo dos veces hace que el cliente recargue el mundo en bucle »). `hjk` voyage
avec `jru` à chaque changement de carte, `f1` = liste empaquetée d'ids de cartes (`BuildMapDiscovered`)
— `anclas_3.6.10.10.tsv:40`. Côté implémentation Jondo :
`Push("jru", Pb.New().Var(2, mapId).Build())` — `opcodes_emulador_3.6.10.10.tsv:317`. Les deux sigles
sont bien dans le bloc `# CARTE (§5.1-5.2)` de `chemin-critique.txt:32`, `jru` à
`chemin-critique.txt:35` et `hjk` à `:36` — **mais ce fichier ne porte AUCUNE numérotation** : la v1
parlait d'un « J3.3 tel que numéroté par `chemin-critique.txt` » qui n'existe pas. La confrontation au
protocole reste à faire par NUMÉRO de champ : `protocolo_3.6.10.10.proto` porte 2 169 messages nommés
par sigle obfusqué (`protocolo_3.6.10.10.proto:4444` pour `hdw`) et **zéro occurrence** de la chaîne
« CurrentMapMessage ».

**VÉRIFIÉ** — Jiva 2.42 (réf. archi, pas une source 3.0) stocke la géométrie dans une seule colonne
compressée : `world_maps` — `CompressedCells longblob`, plus `BlueCellsCSV`/`RedCellsCSV mediumtext`,
plus les 4 voisins + 4 cellules de raccord (`TopNeighbourCellId`…) — schéma lu via `zcat` sur
`world_dev.sql:1874228`. `world_maps_positions` porte `PosX`/`PosY`/`Outdoor`/`SubAreaId`/
`Capabilities`/`WorldMap` — `world_dev.sql:1898055`. `world_worldmaps` porte l'échelle/chunks du monde
— `world_dev.sql:1916899`. `interactive_datas` — `world_dev.sql:1191045` — et `interactives_spawns`
(`Id`,`TemplateId`,`MapId`,`CellId`,`ElementId`,`Animated`) — `world_dev.sql:1192313` — sont le patron
ému mature pour poser les interactifs sur une carte, à transposer (pas copier). **Les 5 citations
retombent sur les 5 `CREATE TABLE`, remesurées une à une.**

**VÉRIFIÉ** — `dofus-tools/` (445 Mo, 12 006 fichiers mesurés `find -type f`, 14 978 entrées avec les
répertoires) ne porte AUCUN outil de lecture de bundle Unity Addressable : recherche insensible à la
casse `assetstudio|assetripper|unitypy` sur tout l'arbre rend 0 fichier. Son seul répertoire proche du
sujet, `asset-index/`, lit le format LEGACY `.d2o`/`.d2i`/`.d2p` du client 2.x — **pas réutilisable tel
quel pour des bundles 3.0**. L'outil 3.0 réel est `lot30-data-3.0-extract/extract_bundle.py`.
⚠️ **Piège d'instrument à connaître** : `dofus-tools/` est en réalité un **symlink** vers un autre
emplacement sur la même machine ; `find` et `du` ne le traversent pas et rendent 0 fichier et 4 Ko sur
le lien. Le compte n'est reproductible que **par le chemin réel**.

## (A) Tableau — donnée nécessaire → l'avons-nous ? → où → forme → trou

| Donnée nécessaire (entrée sur Astrub) | Avons-nous ? | Où | Forme | Trou |
|---|---|---|---|---|
| Identité de carte (id, subArea, worldMap, coords) | Oui | `lot31-data-3.0-full/json/mapsinformation.json` (doublon Jondo `world.db.MapTemplates`) | JSON décodé, 15 360 cartes | aucun |
| Coordonnées compressées ↔ (posX,posY) | Oui | `lot31-data-3.0-full/json/mapscoordinates.json` | formule close, 15 360/15 360 | aucun |
| Voisins de carte (haut/bas/gauche/droite) | **Oui** | `world.db.MapScrolls` (17 353 l.), doc `refs/JondoEmu/docs/world.md:31` | 4 colonnes d'ids par carte | aucun — **la v1 le déclarait à tort absent** |
| Cellules « où poser un monstre » | Oui | `JondoEmu/datos/map_walkable_cells.json` | JSON dérivé, 230 sur Astrub | **bords rognés exprès** : ce n'est PAS l'ensemble marchable |
| Cellules tenables en combat (`f`) | Oui | `JondoEmu/datos/map_fight_cells.json` | JSON dérivé, 357 sur Astrub | aucun ; sémantique donnée par `data.md:33` |
| Cellules opaques / `los` (`b`) | Oui | même fichier, clé `b` | 85 sur Astrub | aucun — **la v1 comptait `los` en trou** |
| `floor`, `farmCell`, `havenbagCell`, `nonWalkableDuringRP`, `arrow`, `speed`, `moveZone`, `linkedZone`, `mapChangeData`, `visible`, `red`, `blue`, `roleplayMonstersMovementBlocked` | Pas encore décodés | bundles `Content/Map/Data/` rapatriés (§C) | `.bundle` Unity non ouverts | **13 champs sur 17 — extraction à faire, plus un rapatriement** |
| Éléments interactifs (portes, coffres, zaaps…) | Oui | `interactive_elements.json` ; types via `tipos_interactivos_3.6.10.10.json` | `{e, c, g}`, `c` = cellule, jointure sur `g` | aucun — légende à `data.md:36` |
| Objets (armes, sets, effets) | Oui | `lot31-data-3.0-full/json/items.json` | JSON décodé, 21 748 | aucun |
| Sorts | Oui | `lot31-data-3.0-full/json/spells.json` | JSON décodé | aucun |
| Monstres (templates) | Oui | `lot31-data-3.0-full/json/monsters.json` | JSON décodé, 5 134 | aucun |
| Groupes de monstres PAR CARTE | **Oui** | `world.db.MapMobs` (38 744 groupes, 3 sur Astrub) | `MapId`+`CellId`+composition JSON | non extrait d'un bundle 3.0 ; source = base Jondo |
| PNJ (templates, dialogues) | Oui | `lot31-data-3.0-full/json/npcs.json` | JSON décodé, 6 467 | positions PNJ : `world.db.NpcSpawns` ne porte que 53 lignes, 0 sur Astrub |
| Comptes / persos (état de jeu) | Patron seulement | `world.db.Characters` (24 colonnes dont `MapId`, `CellId`, `Look`, `Kamas`) + Jiva `world_dev.Characters` | schéma lisible, 3 lignes de test | schéma 3.0 à construire |
| Géométrie de rendu (décor, cellules complètes) | **Rapatriée, non décodée** | `internal/artefacts/lot37-mapdata-3.0/Content/Map/Data/` — 577 bundles | `.bundle` Unity compressés | **décodage à faire (§C) — ce n'est plus un trou de rapatriement** |

## (C) Géométrie des cartes — rapatriée le 04/09, reste à décoder

**VÉRIFIÉ** — **Les bundles de géométrie sont sur ce VPS.**
`internal/artefacts/lot37-mapdata-3.0/Content/Map/Data/` porte **579 fichiers** : **577 `.bundle`**
(569 `mapdata_assets_world_<N>.bundle`, 7 `mapexporter_monoscripts_<hash>.bundle`, 1
`mapelements_assets_.bundle`) plus `catalog_1.0.bin` (1 681 445 octets) et `catalog_1.0.hash`. Le lot
entier pèse 459 Mo, 791 fichiers, et son manifeste `MANIFEST-origine.sha256` porte **788 lignes
vérifiées, 788 OK et 0 FAILED** (`lot37-mapdata-3.0/verif.txt`). **Le §C de la v1 planifiait un
rapatriement depuis un PC personnel pour des données déjà posées ici.**

**VÉRIFIÉ** — **Astrub est adressable dans ce catalogue.** `Content/Map/Data/catalog_1.0.bin` nomme
**15 360 entrées `map_<id>.asset`** — exactement la population de `mapsinformation.json` — dont
`map_191105026.asset`, entourée dans le binaire de `map_191105024.asset`, `map_191105028.asset` et
`map_191106050.asset`, c'est-à-dire de **trois de ses quatre voisins de `MapScrolls`**. Deuxième nature
de source, même réponse.

**VÉRIFIÉ** — **Le jeu local couvre tout ce que le catalogue nomme** (comparaison du binaire
`Content/Map/Data/catalog_1.0.bin` au contenu de `lot37-mapdata-3.0/Content/Map/Data/`). Le catalogue
cite chaque bundle de carte sous deux formes (nue `mapdata_assets_world_<N>.bundle` et hachée
`mapdata_assets_world_<N>_<hash>.bundle`), soit **541 indices distincts** ; **les 541 sont présents sur
disque**, et **0 bundle cité manque**. Le disque en porte 28 de plus (indices 64, 248, 269, 301, 361,
462, 479, 540 et suivants) que le catalogue ne nomme sous aucune forme. Le catalogue nomme aussi 542
bundles à nom de hache pur, absents du lot — ils appartiennent à d'autres domaines que la carte.

**VÉRIFIÉ** — **Le chemin déduit par la v1 était faux, et sa source le disait.** Le vrai chemin est
`Content\Map\Data\` sous la racine du client, pas `StreamingAssets/aa/`. Le brief initial du projet le
nommait déjà : « Manque : géométrie des cartes (`Map/Data`, 577
bundles jamais harvestés) » — **la v1 a cité cette ligne (sous un mauvais numéro) pour le compte de
577, et a déduit un autre chemin que celui écrit dans la même parenthèse.** Nuance mesurée : un dossier
`aa/` existe bien dans le lot (`lot37-mapdata-3.0/aa/`, 2 fichiers, `catalog.bin` de 893 150 octets),
mais il ne nomme **aucune** carte — 0 `map_<id>.asset`, 0 bundle de carte. Les deux moitiés étaient
vraies séparément : le dossier existe, la géométrie n'y est pas.

**VÉRIFIÉ** — L'outil de lecture de bundle existe et est éprouvé **sur le domaine DataCenter
seulement** : `lot30-data-3.0-extract/extract_bundle.py` + venv UnityPy 1.25.3, avec repli de version
Unity (`FALLBACK_UNITY_VERSION=6000.3.0f1`, nécessaire car l'en-tête `UnityFS` porte une version
placeholder — `lot30-data-3.0-extract/OUTIL.md:33-40`, confirmé en lisant l'en-tête d'un bundle de
carte : `UnityFS`, `5.x.x`, `0.0.0`). Il a produit 206 JSON depuis 205 bundles `data_assets_`. **Il n'a
jamais été lancé sur un `mapdata_assets_` : « prouvé » ne se transporte pas d'un domaine à l'autre.**

**DÉDUIT** — `extract_bundle.py` décodera `ClientMapData`/`ClientCellData` depuis un
`mapdata_assets_world_<N>.bundle` (mêmes classes `MonoBehaviour` `[Serializable]`, même moteur Unity).
Deux risques nommés : les 7 `mapexporter_monoscripts_<hash>.bundle` forment un jeu de scripts distinct
du `monoscripts` de lot31, et le venv de l'outil est en cpython-3.12 alors que l'hôte est en 3.14.
**Comment vérifier** : lancer `lot30-data-3.0-extract/extract_bundle.py` sur UN bundle de
`lot37-mapdata-3.0/Content/Map/Data/` et comparer les clés du `typetree` obtenu à
`il2cpp.cs:123421-123458`. Épreuve de refus : si `_manifest.json` rend `decoded_count` 0, c'est le venv
ou le jeu de scripts, pas la donnée.

**DÉDUIT** — Le bundle qui porte `map_191105026.asset` est présent sur disque, puisque tout bundle
nommé par le catalogue l'est (mesuré ci-dessus) et que le client ne charge une carte que par ce
catalogue. **Comment vérifier** : décoder les bundles de
`lot37-mapdata-3.0/Content/Map/Data/` et chercher l'objet nommé `map_191105026`. Une recherche binaire
directe ne suffit PAS et a été essayée : les bundles sont compressés (`UnityFS`), `grep` sur les 577
fichiers ne rend aucune occurrence — **absence dans un fichier compressé n'est pas absence.**

## (B) Schéma minimal 3.0 proposé

**Maps** — `id` (VÉRIFIÉ `mapsinformation.json:186544`), `subAreaId`/`worldMap`/`posX`/`posY`
(VÉRIFIÉ, même source), `compressedCoords` (VÉRIFIÉ, formule close), `neighbourTop/Bottom/Left/Right`
(VÉRIFIÉ, `world.db.MapScrolls`, 17 353 lignes — **plus une extraction à faire**), `cellCount` = 560
(VÉRIFIÉ `il2cpp.cs:245096`).

**Cellules** (par map, indexées `cellNumber`, ids 0..559) — `mov` couvert de façon **partielle** par
`map_walkable_cells.json` (rogné), `los` couvert par la clé `b` de `map_fight_cells.json`,
`nonWalkableDuringFight` déductible de `f` combiné à `mov` — les trois VÉRIFIÉS via `data.md:33`.
Les 13 autres champs de `ClientCellData` (`il2cpp.cs:123421-123458`) sont **à extraire des bundles du
§C** ; schéma-cible connu, valeurs non décodées.

**Entités (interactifs)** — `elementId` (`e`), `cellId` (`c`, VÉRIFIÉ `data.md:36`), `graphicId` (`g`,
clé de jointure VÉRIFIÉE vers `tipos_interactivos_3.6.10.10.json`, 415/415). Patron d'écriture à
transposer de Jiva `interactives_spawns` — `world_dev.sql:1192313`. ⚠️ `lot31-data-3.0-full/json/
interactives.json` ne sert PAS à positionner : ses 446 records ne portent que `_class`, `id`, `nameId`
— ni `mapId`, ni `cellId` (mesuré). **La v1 proposait de l'y croiser.**

**Monstres/PNJ sur Astrub** — groupes VÉRIFIÉS dans `world.db.MapMobs` (`MapId`, `CellId`,
`MembersJson`), 3 sur Astrub. PNJ : `world.db.NpcSpawns` porte 53 lignes et rien sur Astrub, donc les
positions PNJ 3.0 restent à trouver. **DÉDUIT** que ces positions vivent dans les bundles de carte, aux
côtés des interactifs — **comment vérifier** : chercher un champ de PNJ dans le `typetree` décodé d'un
bundle de `lot37-mapdata-3.0/Content/Map/Data/`, et à défaut relire `refs/JondoEmu/docs/world.md`,
qui documente ce que l'ému sait d'une carte.

**Comptes/Persos** — patron VÉRIFIÉ : `world.db.Characters`, 24 colonnes dont `MapId`, `CellId`,
`Look`, `Kamas`, `Breed`, `Level`, `Experience`. Côté Jiva, `world_dev.sql` porte l'équivalent mature.
Schéma 3.0 à trancher à la synthèse.

## (D) Plan d'outil d'import 0-LLM (étage 5 « développer »)

**Entrées** : les 577 bundles de `lot37-mapdata-3.0/Content/Map/Data/` + les JSON décodés de
`lot31-data-3.0-full/json/` (identité de carte) + `world.db` (voisins `MapScrolls`, groupes `MapMobs`)
+ les deux JSON Jondo de cellules (témoins de contrôle, **pas de vérité**).

**Traitement** : (1) `extract_bundle.py` sur chaque bundle de carte → JSON `ClientMapData` complet ;
(2) script Python déterministe qui fusionne ce JSON avec `mapsinformation.json` (identité),
`MapScrolls` (voisins) et `interactive_elements.json` (interactifs, `c` = cellule, jointure `g`) en un
enregistrement carte + N enregistrements cellule ; (3) écriture DB dans un schéma natif 3.0, inspiré de
Jiva `world_maps` sans le blob compressé.

### Le gate — refait, l'ancien refusait le bon résultat

L'ancien gate exigeait **exactement 230 cellules `mov=true` sur Astrub** et **`f ⊆ mov`**. Les deux
contrôles sont faux, mesurés :

| Contrôle v1 | Ce qu'il supposait | Mesure | Effet |
|---|---|---|---|
| « exactement 230 » | 230 = l'ensemble marchable d'Astrub | 230 est un compte **rogné** (`world.md:48`, `data.md:64`) | un extracteur CORRECT rend plus que 230 → **le gate refuse le bon résultat** |
| « `f ⊆ mov` » | `f` est un sous-ensemble des marchables | |f| = 357 > 230 ; 127 cellules d'Astrub hors ; **15 774 cartes sur 17 211 violent le contrôle**, 1 702 974 cellules hors au total | le gate crie sur 92 % du corpus |

**Le nouveau gate (0-LLM), sur Astrub :**

1. **Cardinalité** : `len(cellsData)` extrait **doit valoir 560** — `CellsCount` à `il2cpp.cs:245096`,
   recoupé par 14 × 40 (`il2cpp.cs:245097` et `data.md:64`).
2. **Domaine** : les `cellNumber` forment exactement l'ensemble 0..559, sans trou ni doublon.
3. **Partition** : chaque cellule porte un `mov` booléen ; l'ensemble `mov=true` extrait doit
   **contenir strictement les 230** de `map_walkable_cells.json` (borne INFÉRIEURE, jamais une
   égalité) et **contenir les 357 de `f`** (une cellule tenable en combat est marchable par
   définition, `data.md:33`).
4. **Ligne de vue** : l'ensemble `los=false` extrait doit **contenir les 85** de la clé `b`.
5. **Voisins** : les 4 `neighbourId` extraits doivent **égaler** la ligne `MapScrolls` d'Astrub
   (191106050, 191105028, 191104002, 191105024) — quatre ids, comparaison exacte, deux sources de
   nature différente (bundle client vs base serveur).
6. **Interactifs** : chaque `c` de `interactive_elements.json` pour Astrub doit tomber dans 0..559 et
   désigner une cellule existante ; les 4 éléments d'Astrub doivent se retrouver dans les
   `interactiveElements` du bundle.

Tout écart est un **refus motivé** qui nomme le contrôle, jamais un warning silencieux. Un contrôle
d'inclusion qui deviendrait une égalité est un **bug de gate**, pas un succès.

**Sorties** : un enregistrement `Maps` + 560 `Cells` par carte, prêts à charger dans le socle étage
2/3 ; le `_manifest.json` d'`extract_bundle.py` réutilisé tel quel, listant les bundles en échec.

## (E) Leçon — ce qui a réellement échoué

**Le défaut n'était pas la mesure.** Les mesures de la v1 sont justes, et plusieurs le sont au
caractère près : les 7 citations d'opcodes, les 5 lignes du dump Jiva qui retombent sur leurs
`CREATE TABLE`, les 17 champs de `ClientCellData`, les 6 `records_count`, la fiche d'Astrub, l'outil
d'extraction du lot30. Remesurés un à un, ils tiennent.

**Le défaut est d'avoir DÉDUIT une sémantique et DÉCLARÉ des trous sans ouvrir la source qui la
donnait — déjà sur le disque, et déjà à moitié citée.** Trois formes du même geste :

- `refs/JondoEmu/docs/` n'a jamais été ouvert, alors que `refs/JondoEmu/datos/` l'était en
  permanence : un répertoire d'écart. Il porte la légende de `f`, `b`, `e`, `c`, `g`, la raison du
  rognage des bords, et le nom du générateur que la v1 partait chercher. **Quatre DÉDUIT et trois
  « à vérifier » tombent d'un seul coup à la lecture de deux lignes** — `data.md:33` et `:36`.
- Le brief initial du projet nommait `Map/Data` dans la parenthèse même d'où la v1 a tiré son compte de
  577 bundles. Elle a pris le chiffre et laissé le chemin, puis
  déduit `StreamingAssets/aa/` — qui existe, mais ne porte aucune carte.
- Le fragment listait `world.db.MapScrolls` dans son propre §0, puis déclarait les voisins absents
  dans son tableau. **Une source citée n'est pas une source lue.**

**Et le réfutateur a failli commettre exactement la même faute.** Devant les clés `f` et `b`, il a
d'abord lu « rouge / bleu », d'après les champs `red` et `blue` de `ClientCellData`
(`il2cpp.cs:123421-123458`) : une hypothèse plausible, tirée d'une source vraie, et fausse. Il ne l'a
abandonnée qu'en cherchant si quelqu'un avait écrit la légende. **La faute n'est pas de deviner : c'est
de ne pas chercher d'abord si la réponse est écrite.**

**Trois pièges d'instrument mesurés pendant cette révision**, à porter au corpus :

- `dofus-tools/` est un **symlink** : `find -type f` rend 0 fichier et `du` rend 4 Ko. Le
  réfutateur, qui mesurait depuis un autre hôte, a conclu que « 12 006 » était irreproductible. Par le
  chemin réel, le compte tombe **exactement à 12 006**. L'instrument avait bougé, pas le terrain.
- Le chemin `<sauvegarde interne datée du 04/09>/world_dev.sql.gz` **existe sur
  ce VPS** ; le réfutateur, sur une autre machine, l'a noté absent. Une affirmation d'absence porte
  l'hôte où elle a été prise, pas seulement l'heure.
- Une recherche binaire sur un bundle **compressé** rend zéro même quand la donnée est là : `grep` sur
  les 577 bundles ne trouve pas `map_191105026`. Cette absence-là ne prouve rien.
