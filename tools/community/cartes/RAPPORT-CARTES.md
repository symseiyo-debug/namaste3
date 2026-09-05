# RAPPORT — Extraction de la géométrie des cartes Dofus 3.0 (étage 5, J3.B)

> Outil : `tools/community/cartes/extraire_cartes.py` + `gate-cartes.py`.
> Entrée : `internal/artefacts/lot37-mapdata-3.0/Content/Map/Data/`.
> Schéma de référence : `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs`.
> Second instrument : `refs/JondoEmu/datos/` (lecture seule, jamais écrit).
> Tags **VÉRIFIÉ** (mesuré, fichier:ligne) / **DÉDUIT** (hypothèse + comment vérifier).
> `PROD-DB` (base de production) : jamais ouvert, jamais cité.

## 0. Le résultat en une ligne

Les 17 champs de `ClientCellData` sont **extraits pour 17 353 cartes × 560 cellules**, et
l'extraction est corroborée **exactement, ensemble par ensemble**, par une source produite hors
de notre chaîne. Le trou n°1 de `DONNEES-3.0-CARTE.md` (« 13 des 17 champs sont un trou ») est
comblé.

## 1. ⚠️ La prémisse du brief est RÉFUTÉE — et la bonne mesure est meilleure

**Le brief demandait** : « 191105026 : exactement 560 cellules, **exactement 230 marchables**
(second instrument Jondo), refus sinon ».

**VÉRIFIÉ — mesuré dans le bundle** : 191105026 porte **560 cellules** (conforme) mais
**360 cellules `mov=true`**, pas 230.

**VÉRIFIÉ — pourquoi, dit par Jondo lui-même** : `map_walkable_cells.json` **n'est pas** la
marchabilité du client. C'est un masque de **spawn de monstres**, volontairement rogné aux bords.
Trois sources internes à JondoEmu le disent en clair :

- « `map_walkable_cells.json` **trims the map borders on purpose**, so that monster groups are
  never placed on the edge » — `refs/JondoEmu/docs/world.md:48`.
- « Fight data. `map_walkable_cells.json` is no use here: it trims the map borders on purpose so
  that mobs can be placed in roleplay, and on top of that it says nothing about which cells block
  sight. **This other file comes from the same place (the client bundles)** but keeps the whole map
  and carries the `los` field » — `refs/JondoEmu/Jondo.Unity.Server/MapManager.cs:51-54`.
- « The check is against the fight walkability and not against `map_walkable_cells.json`: that file
  trims the borders on purpose […] the border is precisely where somebody arriving from the next map
  lands » — `refs/JondoEmu/Jondo.Unity.Server/Handlers/WorldMoveHandler.cs:442-445`.

Autrement dit : **le serveur de référence lui-même refuse d'utiliser le chiffre que le brief me
demandait de certifier.** Bâtir la gate sur 230 aurait gravé dans une gate verte une valeur que sa
propre source dit inadaptée à la marchabilité.

**La légende existait, dans un fichier que personne n'avait ouvert** — `refs/JondoEmu/docs/
data.md:33` dit mot pour mot ce que je n'avais reconstitué qu'empiriquement : `f` = « cells you can
stand on in a fight (`mov=1`, `nonWalkableDuringFight=0`) », `b` = « cells that break line of sight
(`los=0`) ». J'ai trouvé ces deux définitions par égalité d'ensemble avant de lire la ligne ; les
deux chemins concordent. C'est la meilleure situation possible : une mesure et un document
indépendants qui disent la même chose.

**Ce que la mesure a mis à la place — deux égalités d'ensemble EXACTES** contre
`map_fight_cells.json`, l'autre fichier Jondo, celui qui « garde toute la carte » :

| Notre extraction | Champ Jondo | 191105026 | Sur tout le corpus |
|---|---|---|---|
| `mov` ET NON `nonWalkableDuringFight` | `f` | 357 = 357, **ensembles identiques** | *(cf. §5)* |
| NON `los` | `b` | 85 = 85, **ensembles identiques** | *(cf. §5)* |

Ce n'est pas un compte qui tombe juste : ce sont les **mêmes cellules**, une par une. Et l'égalité
porte sur **trois** de nos champs (`mov`, `nonWalkableDuringFight`, `los`) — dont `los`, qui faisait
partie des 13 champs déclarés « trou complet » dans `DONNEES-3.0-CARTE.md:148`.

**Le rôle qui reste à `map_walkable_cells.json`** : une **containment** vérifiable — ses 230 cellules
sont toutes `mov` chez nous (VÉRIFIÉ, 0 exception). C'est ce que la gate teste, au lieu d'un compte
qu'elle aurait certifié faux. La borne « ≥ 230 et ≤ 560 » est aussi posée explicitement dans E1,
mais c'est la plus faible des deux : une containment sur les 230 cellules **nommées** implique la
borne, l'inverse est faux.

**Le nombre 560 n'est plus seulement mesuré, il est sourcé dans le dump** :
`private const int CellsCount = 560` — `il2cpp.cs:245096`, avec une seconde déclaration indépendante
à `il2cpp.cs:332686`. La grille « 14×40 » reste **DÉDUITE** : `private const int Column = 14`
(`il2cpp.cs:245098`) et 560/14 = 40 ; le dump n'écrit « 14×40 » nulle part tel quel.

## 2. Le schéma extrait — les 17 champs et leur source

`ClientCellData` — `il2cpp.cs:123421-123458`. Les 17 champs sortent du typetree du bundle **dans
l'ordre exact du dump**, aux mêmes noms. Aucun renommage.

| # | Champ | Type (dump) | Source | Observé sur 191105026 |
|---|---|---|---|---|
| 1 | `cellNumber` | uint | `il2cpp.cs:123424` | 0..559 |
| 2 | `speed` | int | `il2cpp.cs:123425` | 0 partout |
| 3 | `mapChangeData` | int | `il2cpp.cs:123426` | 39 cellules ≠ 0 |
| 4 | `moveZone` | int | `il2cpp.cs:123427` | 0 partout |
| 5 | `linkedZone` | int | `il2cpp.cs:123428` | {0, 16, 17} |
| 6 | `mov` | bool | `il2cpp.cs:123429` | 360 vrai |
| 7 | `los` | bool | `il2cpp.cs:123430` | 475 vrai (85 faux) |
| 8 | `nonWalkableDuringFight` | bool | `il2cpp.cs:123431` | 3 vrai |
| 9 | `nonWalkableDuringRP` | bool | `il2cpp.cs:123432` | 0 vrai |
| 10 | `farmCell` | bool | `il2cpp.cs:123433` | 0 vrai |
| 11 | `visible` | bool | `il2cpp.cs:123434` | 560 vrai |
| 12 | `havenbagCell` | bool | `il2cpp.cs:123435` | 0 vrai |
| 13 | `roleplayMonstersMovementBlocked` | bool | `il2cpp.cs:123436` | 0 vrai |
| 14 | `floor` | int | `il2cpp.cs:123437` | 0 partout |
| 15 | `red` | bool | `il2cpp.cs:123438` | 0 vrai |
| 16 | `blue` | bool | `il2cpp.cs:123439` | 0 vrai |
| 17 | `arrow` | int | `il2cpp.cs:123440` | 0 partout |

Les 4 propriétés `useTopArrow`/`useBottomArrow`/`useRightArrow`/`useLeftArrow`
(`il2cpp.cs:123443-123446`) sont **calculées** depuis `arrow`, pas sérialisées — elles ne sont donc
pas dans le bundle, et l'outil ne les invente pas.

**Normalisation assumée** : les 10 champs `bool` sortent du typetree en 0/1 et sont écrits en
`true`/`false` (le dump déclare `bool`). Une valeur hors 0/1 n'est **pas** convertie : elle est
gardée brute ET signalée en rejet `valeur_bool_inattendue` — 0 occurrence mesurée.

## 3. Ce que la carte porte EN PLUS des cellules

`ClientMapData` — `il2cpp.cs:123604-123645`. Le bundle porte **les 28 champs du dump, ni plus ni
moins** (VÉRIFIÉ : aucun rejet `champ_carte_en_trop` ni `champ_carte_manquant` sur le corpus).
L'objet Unity qui l'enveloppe est `Core.World.Metadata.Maps.MapMetadata : ScriptableObject`
(`il2cpp.cs:395458`), qui ajoute `mapData` (`:395461`), `mapTextures` (`:395472`) et
`allowMapEffects` (`:395475`).

Recopié intégralement dans chaque JSON :

- **Les 4 voisins** — `topNeighbourId`/`bottomNeighbourId`/`leftNeighbourId`/`rightNeighbourId`
  (`il2cpp.cs:123607-123610`). Pour 191105026 : 191105024 / 191105028 / 191104002 / 191106050.
  C'était la ligne « à extraire d'un bundle de scène, absent sur ce VPS » de
  `DONNEES-3.0-CARTE.md:145` — elle est extraite. **Corroboration partielle seulement : voir §5.3**,
  c'est le seul champ du lot qui ne tombe pas juste à 100 %.
- **Les 4 listes de flèches de bord** — `topArrowCellList` et pairs (`il2cpp.cs:123626-123629`).
- **`interactiveElements`** (`il2cpp.cs:123619`) — résolus depuis le registre `SerializeReference`.
  Chaque élément est un `ClientInteractiveElementTransform` (`il2cpp.cs:123588`) et porte
  `cellId`, `gfxId` **et `m_interactionId`** — l'ancre serveur des portes/zaaps/ressources.
  Exemple 191105026 : `{cellId: 94, gfxId: 62995, m_interactionId: 514829}`.
  **Correction** : `DONNEES-3.0-CARTE.md:149` dit que les clés `e`/`c`/`g` de
  `datos/interactive_elements.json` « ne sont pas légendées ». Elles le sont, dans un fichier que
  ni ce fragment ni moi n'avions ouvert : `refs/JondoEmu/docs/data.md:36` donne
  `{e: element id, c: cell, g: graphic}` — donc `c` est bien une **cellule**, et la position des
  interactifs n'a jamais été absente de `datos/`. Ce que notre extraction ajoute par-dessus, c'est
  `m_interactionId` (l'ancre serveur) et `gfxId`, et surtout une source **primaire** au lieu d'un
  dérivé.
- **`boundingBoxes`**, **`playlistSet`** (GUID FMOD musique/ambiance/combat), **`backgroundColor`**,
  **`localizedSounds`**, **`stagingSequences`**, et les 4 configurations
  `mapWind`/`mapPostProcess`/`mapWave`/`mapNoiseModifier`.

**Réduit volontairement** — les listes de RENDU pur (`backgroundElements` : 1 483 entrées sur la
seule Astrub, `sortableElements`, `foregroundElements`, `animatedElements`, `refractionElements`,
`particlesParameters`) et les 3 atlas `*MaterialData` : seul le **compte** est écrit, sous
`renderCounts`. Motif mesuré : le typetree complet d'Astrub pèse **1 298 705 octets** ; le garder
pour 17 353 cartes ferait ~22 Go de décor dont le serveur n'a aucun usage. Le contenu reste
disponible à la demande via l'outil lot30 sur le bundle nommé dans chaque JSON.

## 4. Les chiffres mesurés

Passe complète, `nice -n 10`, un seul processus, 4 vCPU partagés avec d'autres tâches.

| Mesure | Valeur |
|---|---|
| Bundles présents dans `Content/Map/Data/` | 577 (+ `catalog_1.0.bin`/`.hash`) |
| Bundles parcourus | 577 |
| Bundles ayant produit ≥ 1 carte | 569 |
| Cartes écrites (`cartes/<mapId>.json`) | 17 353 |
| Cellules extraites | 9 717 680 |
| Cartes à exactement 560 cellules | 17 353 (100 %) |
| Cellules `mov` | 4 826 720 — **278,1 par carte** en moyenne |
| Cartes dont les 4 voisins sont non nuls | 17 353 (100 %) — mais voir §5.3 : non nul ≠ juste |
| Éléments interactifs | 44 072 (2,5 par carte) |
| `boundingBoxes` | 2 237 |
| Rejets | 39 |
| Durée | **714 s (11 min 54 s)** |
| Poids sur disque | 2,9 Go |

Répartition des cartes portant au moins une cellule du champ : `nonWalkableDuringFight` 9 291 ·
`mapChangeData` ≠ 0 9 209 · `nonWalkableDuringRP` 1 459 · `farmCell` 249 · `arrow` ≠ 0 74 ·
`havenbagCell` 63. Les 74 cartes portant une cellule `arrow` ≠ 0 sont **exactement les mêmes**
(égalité d'ensembles vérifiée, pas seulement des comptes égaux) que les 74 dont au moins une
`*ArrowCellList` est non vide — deux champs sérialisés indépendamment qui se confirment.

**Les 39 rejets, par cause** (`sortie/a-classer.tsv`, jamais en silence) :

| Cause | Nombre | Ce que c'est |
|---|---|---|
| `champ_cellule_manquant` | 27 | Schéma de cellule **plus ancien** : 16 champs au lieu de 17, `roleplayMonstersMovementBlocked` absent. 23 cartes dans `mapdata_assets_world_746.bundle`, 4 dans `..._896.bundle`. **Cartes conservées**, champ écrit `null`. |
| `type_objet_inattendu` | 11 | `MonoScript` dans les 7 bundles `mapexporter_monoscripts_*` — de l'outillage d'export, pas des cartes. |
| `objet_non_carte` | 1 | `elements.asset` dans `mapelements_assets_*.bundle` — la bibliothèque d'éléments partagés. |

Aucun `bundle_illisible`, aucun `objet_non_decode`, aucun `champ_carte_manquant`, aucun
`champ_carte_en_trop`, aucun `valeur_bool_inattendue`, aucun `nb_cellules_inattendu`.

**Second chemin de comptage** (règle du cahier des charges : un compte d'extraction se remesure) —
le catalogue Addressables `catalog_1.0.bin` porte **15 360** clés `map_*.asset` uniques (le même
compte que `mapsinformation.json`, `DONNEES-3.0-CARTE.md:32`). Les deux chemins se recoupent ainsi :

- catalogue ∖ JSON écrits = **0** — aucune carte adressable n'a été ratée ;
- JSON écrits ∖ catalogue = **1 993** — des cartes qui existent dans les bundles mais que le
  catalogue n'adresse pas. **DÉDUIT** : zones non publiées ou de développement. Comment vérifier :
  chercher leurs `mapId` dans `mapsinformation.json` (elles devraient y être absentes) et regarder
  si un `subAreaId` les rattache à une zone connue.

## 5. Épreuves

### `gate-cartes.py --epreuve` — les 5, VERTES

```
[VERT ] E1 OK : 191105026 = 560 cellules, 360 mov, fight `f` 357 EXACT, `b` 85 EXACT,
                230 Jondo-walkable ⊆ mov, 4 voisins entiers
[VERT ] E2 OK : partition mov/non-mov == cellCount sur 17353 carte(s)
[VERT ] E3 OK : sabotage detecte -> E1 191105026 : 359 cellules mov, attendu 360 (mesure)
[VERT ] E4 OK : mapId invente 999999999 -> absent, sans exception
[VERT ] E5 OK : rejeu byte-identique (sha256 0c71e59e11f641f5…, 17 cartes re-extraites)
---
GATE CARTES : VERTE
```

E3 est le contrôle qui compte : un `mov` inversé dans une **copie** (jamais l'original) fait rougir
E1 avec un refus nommé. Sans lui, cinq verts ne prouveraient pas que la gate regarde quelque chose.

### `gate-cartes.py --corpus` — les confrontations rejouées sur les 17 353 cartes

```
cartes lues                       : 17353
fight `f` == mov ET NON nwFight   : EXACT 17174 | ECART 15 | hors fichier Jondo 164
fight `b` == NON los              : EXACT 17174 | ECART 15
walkable Jondo vs mov (containment): egal 1397 | sous-ensemble strict 15769 | NON inclus 12
voisins == MapScrolls (world.db)  : IDENTIQUES 16528 | ECART 825 | hors MapScrolls 0
  dans les ecarts : NOTRE id absent des 17353 cartes 1118 fois, celui de Jondo 1 fois
  reciprocite interne : nous 99.16% (27468/27702) | jondo 97.64% (28136/28816)
```

`--corpus` sort en **code 1**, à dessein : il refuse de se dire vert tant que les écarts existent.

**17 174 cartes sur 17 174 comparables** donnent une **égalité d'ensemble exacte** sur les deux
champs, contre un fichier produit hors de notre chaîne. C'est la corroboration la plus forte du
lot : deux natures de source (donnée décodée par nous / donnée dérivée par Jondo depuis le même
client) tombent sur les mêmes cellules, une par une, sur ~4,6 millions de cellules de combat.

**Les 15 écarts sont un défaut de l'AUTRE instrument, mesuré, pas un doute sur le nôtre** :

- les 15 sont **toutes dans `mapdata_assets_world_923.bundle`**, et **aucune n'est dans le
  catalogue** Addressables ;
- pour les 15, Jondo porte exactement `f` = **560** (toutes les cellules combattantes) et `b` = **0**
  (aucun bloqueur de vue) — une **valeur dégénérée de repli**, pas une mesure ;
- les 12 cartes « walkable non inclus » sont un **sous-ensemble de ces 15**, et Jondo y porte
  exactement **290** cellules pour chacune — encore une constante de repli ;
- les 164 cartes absentes du fichier de combat de Jondo sont **toutes** dans ce même bundle, et
  **aucune** n'est au catalogue.

`mapdata_assets_world_923.bundle` porte 253 cartes, **toutes hors catalogue**. **DÉDUIT** : contenu
non publié, pour lequel Jondo n'a que des valeurs par défaut. Ce que nous mesurons de notre côté sur
ces 253 cartes : `movEtCombattables` va de **438 à 560** et `losBloquees` de **0 à 58** — une
géométrie variée, là où Jondo répète 560/0. Comment lever le DÉDUIT : entrer sur une de ces 15
cartes avec le client vivant et comparer les cellules réellement bloquées.

**Ce que la gate refuse de certifier** : `--corpus` sort en code 1 tant que ces écarts existent.
Il n'est pas passé en vert par une exception « bundle connu » — un écart reste un écart, il est
nommé et compté.

### 5.3 Les voisins — le seul champ qui ne tombe pas juste, et pourquoi je ne tranche pas

Troisième second instrument, ouvert après coup : la table `MapScrolls` de la base de Jondo
(`datos/world.zip` → `world.db`), colonnes `RightMapId`/`BottomMapId`/`LeftMapId`/`TopMapId`.
Elle porte **17 353 lignes — exactement notre population**, et la différence d'ensemble des mapId
est **nulle dans les deux sens**. Sur Astrub, les 4 voisins sont identiques aux nôtres.

Sur le corpus : **16 528 cartes identiques sur les 4 côtés (95,2 %), 825 en écart.** Sur ces 825,
le désaccord ne porte que sur 1 côté (568 cartes), 2 (216) ou 3 (41) — jamais les 4.

Deux mesures internes, qui pointent en sens **opposés** :

| Signal | Nous | Jondo |
|---|---|---|
| Dans les écarts, l'id désigne une carte qui **n'existe pas** dans les 17 353 | **1 118 fois** | 1 fois |
| Réciprocité (`A.droite == B` ⟹ `B.gauche == A`), test interne sans source externe | **99,16 %** | 97,64 % |

Le premier signal accuse notre champ ; le second l'innocente. **DÉDUIT** — et je le pose comme
hypothèse, pas comme conclusion : `MapScrolls` a probablement été **réparée** par son générateur
(`extract_map_neighbours.py`, cité `docs/data.md:35`), en remplaçant les références pendantes par le
voisin géométrique ; cela expliquerait qu'elle n'ait presque plus d'id inconnu **et** qu'elle soit
moins réciproque que nous. Notre champ, lui, serait la valeur brute du client, références mortes
comprises. **Comment vérifier, sans nous croire ni les croire** : prendre 10 des 825 cartes, entrer
dessus avec le client vivant, marcher vers le bord contesté et lire le `mapId` que le serveur
reçoit. C'est le seul arbitre.

**En attendant, ne pas construire le changement de carte sur ce champ seul.** C'est la seule
donnée du lot que je ne donne pas pour acquise, et le fichier
`sortie/index-cartes.tsv` permet d'isoler les 825 en une passe.

## 6. La build — DÉDUITE, et la mesure qui a failli mentir

**VÉRIFIÉ — aucun marqueur de version n'existe dans les entrées.** Recherche de motifs de version
(`3.x.y.z`, `6000.x`, `n.n.n.n`) dans `Content/Map/Data/catalog_1.0.bin` et `aa/catalog.bin` :
**0 résultat**. L'en-tête `UnityFS` des bundles porte le placeholder `5.x.x` / `0.0.0`, comme déjà
documenté pour lot30 (`lot30-data-3.0-extract/OUTIL.md:40-47`).

**MON ERREUR, attrapée par témoin** : UnityPy annonce `SerializedFile.version = 6000.3f1`, et j'ai
d'abord lu ça comme une version **mesurée dans le fichier**. Contrôle : en changeant le repli, il
annonce `6000.2f1` puis `6000.9f9`. **C'est mon propre repli qu'il me renvoyait reformaté.** Un
instrument qui répète l'hypothèse qu'on lui donne n'est pas une mesure.

Donc : `build = "DEDUITE 2026-08-15 (aucun marqueur de version dans bundles/catalogues)"`, portée
par **chaque** JSON, par **chaque** ligne de `index-cartes.tsv` et par la gate (L6 du cahier des
charges). Ancre : la date de la copie (`ORIGINE.txt`), pas une lecture.

**Comment lever le DÉDUIT** : comparer `catalog_1.0.hash` (`e27213124ef8786bb23bd3ff3e6c98f0`) au
catalogue d'une build téléchargée par Cytrus dont le numéro est connu — deux hash égaux datent les
bundles, un hash différent les exclut.

## 7. Mes erreurs

1. **J'ai pris le repli d'UnityPy pour une mesure** (§6). Rattrapé par témoin négatif avant
   d'écrire quoi que ce soit ; sans le témoin, `build: 6000.3f1` serait parti comme VÉRIFIÉ.
2. **J'ai d'abord jeté 27 cartes** dont le bundle porte un schéma de cellule plus ancien (§5).
   Les compter en rejet était honnête, mais les perdre ne l'était pas : elles existent et le
   serveur en aura besoin. Corrigé — la carte est conservée, le champ absent est écrit `null`
   (jamais `false`, qui aurait fabriqué une valeur), et `champsCelluleAbsents` le dit dans le JSON.
   La passe complète a été **rejouée entièrement** pour que toutes les sorties soient cohérentes.
3. **Premier jet du JSON pollué** : `renderCounts` portait `null` pour les 3 atlas (des dicts
   comptés comme des listes) et la sentinelle « null » d'Unity ressortait en `{"_class": ""}`.
   Corrigé avant la passe complète.
4. **J'ai annoncé « 579 bundles » d'après le brief** : il y en a **577** (`.bundle`), les deux
   fichiers restants étant `catalog_1.0.bin` et `catalog_1.0.hash`.
5. **J'ai cherché la légende de `f`/`b` par la mesure sans ouvrir la documentation de Jondo.**
   J'ai eu raison sur le fond (les deux égalités d'ensemble tiennent sur 17 174 cartes), mais
   `docs/data.md:33` donnait la réponse en une ligne. Mesurer d'abord n'est pas une faute ;
   ne pas être allé lire ensuite en est une, et j'ai reconduit dans mon rapport l'affirmation
   « clés non légendées » de `DONNEES-3.0-CARTE.md:149` sans la vérifier — alors que la légende
   des clés `e`/`c`/`g` est à `docs/data.md:36`. **Une affirmation d'absence héritée d'un autre
   document se remesure avant d'être répétée.**
6. **Je n'avais pas ouvert `world.db`** alors que je l'avais lu cité dans `DONNEES-3.0-CARTE.md:93`.
   `MapScrolls` y donne un troisième instrument sur exactement notre population, et c'est lui qui a
   révélé les 825 écarts de voisins (§5.3). Sans lui, j'aurais rendu « 4 voisins extraits, 100 % non
   nuls » — vrai, et trompeur.

## 7bis. Ce que les corrections ont changé

| Correction | Effet sur l'extraction | Effet sur la gate |
|---|---|---|
| 230 = compte amputé, pas la marchabilité | **Aucun** — l'extraction ne lisait déjà que le bundle | Critère remplacé par : 560 exact, ids 0..559, borne ≥ 230, containment, 2 égalités exactes |
| Légende `f`/`b` (`docs/data.md:33`) | Aucun — déjà mesuré, maintenant sourcé | Le commentaire de la gate cite la ligne |
| `CellsCount = 560` (`il2cpp.cs:245096`) | Aucun | 560 passe de « mesuré » à « sourcé dans le dump » ; E1 et E2 vérifient en plus les ids 0..559 |
| Légende `e`/`c`/`g` (`docs/data.md:36`) | Aucun | Aucun — corrige une phrase fausse de mon §3 |
| `MapScrolls` = voisins | Aucun | **Nouveau critère E1** (4 voisins == MapScrolls) + nouvelle ligne `--corpus` |
| `MapMobs`, `compressedCoords` | Hors périmètre (spawns, coordonnées ≠ géométrie de cellule) | Aucun |

**Aucun JSON n'a été régénéré, et c'est mesuré, pas supposé** : le schéma de sortie n'a pas bougé
d'un octet. E5 (rejeu byte-identique) est repassé vert sur les fichiers écrits **avant** ces
corrections, avec le même sha256 `0c71e59e11f641f5…` — la preuve que les corrections portaient sur
l'interprétation des sources tierces et sur la gate, jamais sur ce que le bundle nous dit.

## 7ter. Commentaires du code (règle du projet, 04/09)

`tools/community/gate-commentaires.py`, rejouée sur `cartes/` :

```
VERT cartes/extraire_cartes.py (100.0%, 14/14 unités, en-tête=oui, 12 nombres magiques)
VERT cartes/gate-cartes.py     (100.0%, 12/12 unités, en-tête=oui, 11 nombres magiques)
TOTAL: 2 VERT / 0 ROUGE / 2 fichiers
```

Chacun des 17 champs de cellule porte son type et sa ligne de dump en commentaire de bout de ligne ;
560, 14, 230, 357, 85, 191105026 et les 4 voisins témoins portent leur source (dump, `docs/data.md`,
`world.db`, ou « MESURÉ »). Les nombres restants comptés « magiques » sont soit dans l'en-tête (déjà
sourcés en prose), soit **arbitraires par nature** — une cadence d'affichage, une troncature de log,
le mapId inventé du témoin négatif — et chacun le dit sur sa ligne.

## 8. Ce qui reste DÉDUIT

- **La build** (§6) — comment vérifier : hash du catalogue contre une build Cytrus datée.
- **Le filtre exact de `map_walkable_cells.json`** : « bords rognés » est dit par Jondo
  (`docs/world.md:48`), mais la règle exacte (combien de cellules, selon quel critère) n'est pas
  écrite ; son générateur `extract_all_map_walkable.py` est déclaré **absent** de `tools/`
  (`refs/JondoEmu/docs/data.md:34`). Sans conséquence pour nous : nous n'utilisons plus ce fichier
  que pour une containment.
- **La signification de `linkedZone`/`moveZone`** : les méthodes `HasLinkedRpZone`/`GetLinkedRpZone`/
  `HasLinkedFightZone`/`GetLinkedFightZone` (`il2cpp.cs:123452-123455`) existent, leur corps n'est
  pas lu — comment vérifier : Ghidra sur les RVA `0x1806449A0` et `0x180644960`.
- **`mapChangeData` comme masque de bits** : les valeurs observées (1, 2, 4, 6, 12, 14, 16, 24, 48,
  64, 129, 130, 131, 224) sont compatibles avec un masque de directions — comment vérifier : croiser
  les cellules `mapChangeData` non nulles d'une carte avec les 4 `*ArrowCellList` et avec la cellule
  d'arrivée côté voisin.
- **Les 1 993 cartes hors catalogue** (§4) — comment vérifier : les chercher dans
  `mapsinformation.json` et regarder leur `subAreaId`.
- 🔴 **Les 825 cartes dont les voisins divergent de `MapScrolls`** (§5.3) — le seul DÉDUIT qui
  bloque un usage : ne pas câbler le changement de carte sur ce champ seul avant l'arbitrage.
  Comment vérifier : 10 cartes, client vivant, marcher vers le bord contesté, lire le `mapId` reçu.

## 9. Rejouer

```bash
V=internal/artefacts/lot30-data-3.0-extract/.venv/bin/python
cd internal/cartes

nice -n 10 $V extraire_cartes.py --localiser 191105026   # -> mapdata_assets_world_729.bundle
nice -n 10 $V extraire_cartes.py --bundle mapdata_assets_world_729.bundle   # 17 cartes, ~1 s
nice -n 10 $V extraire_cartes.py --tout                  # 17 353 cartes, ~12 min, 2,9 Go
nice -n 10 $V gate-cartes.py --epreuve                   # les 5 epreuves -> rc 0 (VERTE)
nice -n 10 $V gate-cartes.py --corpus                    # tout le corpus -> rc 1 (825 ecarts, §5.3)

# la regle du projet sur les commentaires, rejouable :
nice -n 10 python3 ../gate-commentaires.py cartes/       # 2 VERT / 0 ROUGE
```

Dépendance unique : le venv de lot30 (UnityPy 1.25.3), déjà installé. `extraire_cartes.py` importe
`read_object` et `write_json` de `lot30-data-3.0-extract/extract_bundle.py` — le lecteur de bundle
prouvé n'a pas été réécrit. Rien n'est exécuté hors Python/UnityPy ; `refs/JondoEmu/datos/` est lu,
jamais écrit.

**Localiser une carte a coûté 401 bundles ouverts** en ordre alphabétique avant de tomber sur
191105026 — mais l'index complet des 577 bundles ne prend que **91 s** (lecture du seul
`AssetBundle.m_Container` de chaque bundle, sans décoder les cartes). C'est ce que fait
`--localiser`, et il écrit `sortie/index-bundles.json` pour que la question ne soit posée qu'une fois.

## 10. Sorties

| Fichier | Contenu |
|---|---|
| `sortie/cartes/<mapId>.json` | 17 353 fichiers — 560 cellules × 17 champs, voisins, flèches, interactifs, métadonnées |
| `sortie/index-cartes.tsv` | 17 353 lignes : mapId, bundle, cellCount, mov, losBloquees, movEtCombattables, 4 voisins, interactifs, build |
| `sortie/a-classer.tsv` | 39 rejets : cause, bundle, cible, détail |
| `sortie/index-bundles.json` | mapId → bundle (écrit par `--localiser`) |
