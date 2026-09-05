# Corrections de `DONNEES-3.0-CARTE.md` — point par point, après remesure indépendante

> Étage 3 (serveur), pièce d'accompagnement du fragment `server/DONNEES-3.0-CARTE.md`.
> Entrée : la réfutation dédiée `internal/REFUTATION-DEDIEE-DONNEES-3.0-20260904.md` (le réfutateur,
> 04/09, couverture déclarée 25/25 VÉRIFIÉ + 17/17 DÉDUIT — 12 confirmés, 28 réfutés, 2
> invérifiables). Sources relues pour cette révision : `refs/JondoEmu/docs/`, `refs/JondoEmu/datos/`,
> `internal/artefacts/lot31-data-3.0-full/`, `internal/artefacts/lot37-mapdata-3.0/`,
> `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs`,
> `<sauvegarde interne datée du 04/09>/world_dev.sql.gz`, `dofus-tools/`.
> **Règle appliquée : aucune correction n'a été portée sur le seul dire du réfutateur.** Chaque point
> a été remesuré ici ; là où ma mesure contredit la sienne, le texte d'origine est GARDÉ et la preuve
> est écrite.

## 1. Compteurs

| Verdict après remesure | Nombre |
|---|---|
| **CORRIGÉ** — réfutation vérifiée, fragment réécrit | 25 |
| **CONTESTÉ** — le réfutateur a tort, texte gardé + preuve | 1 |
| **RÉTROGRADÉ** — réfutation partiellement fondée, portée réduite | 2 |
| Total des 28 réfutations traitées | **28** |
| Confirmés par le réfutateur, revérifiés par moi et tenus | 12 |
| Invérifiables, maintenus tels quels | 2 |
| **Défauts trouvés par MOI, que le réfutateur avait validés** | **1** |

### Compteurs par motif de défaut (les 28 réfutations)

| Motif | Nombre | Ce que c'est |
|---|---|---|
| **M1 — sémantique DÉDUITE quand une source du dépôt la donnait** | **12** | `refs/JondoEmu/docs/` jamais ouvert, à un répertoire de `datos/` lu en permanence |
| **M2 — trou DÉCLARÉ alors que la donnée était déjà là** | **7** | voisins, spawns, interactifs, bundles de géométrie |
| M3 — citation fausse ou périmée (mesure juste, coordonnée fausse) | 2 | le document a bougé sous la citation |
| M4 — compte inexact | 2 | 204 au lieu de 205 ; « voisine d'Astrub » fausse |
| M5 — gate bâti sur une sémantique fausse | 1 | les deux contrôles du §D |
| M6 — contrat de forme de la légende | 2 | une citation sur 25 était fausse, pas le contrat |
| M7 — portée d'une preuve étendue hors du domaine mesuré | 1 | « prouvé » sur `data_assets_`, pas sur `mapdata_assets_` |
| M8 — la réfutation elle-même est fausse | 1 | instrument déplacé, terrain immobile |

**Lecture** : 19 des 28 défauts sur 28 (M1 + M2) sont **le même geste** — conclure sans ouvrir une
source disponible. Ce n'est pas une dispersion de petites fautes, c'est une seule habitude qui a frappé
dix-neuf fois.

## 2. Les 16 réfutations sur les entrées VÉRIFIÉ

| L | Ce que le réfutateur dit | Ce que JE mesure | Verdict | Nouvelle source |
|---|---|---|---|---|
| 9 | Légende « VÉRIFIÉ (lu, fichier:ligne) » non tenue : 5 entrées sans fichier:ligne, L44 fausse | `gate-forme.py` rend **VERT** sur le fragment d'origine, 0 violation : `dossier/` est une forme de source admise par la grammaire commune. Une seule citation est réellement fausse, L44 | **RÉTROGRADÉ** — d'un contrat non tenu à une citation fausse | `tools/protocol-mapping/tools/gate-forme.py` |
| 21 | 207 fichiers, pas 204 ; le bundle `monoscripts` est omis | 207 fichiers, **205 `.bundle`** (204 `data_assets_` + 1 `monoscripts`), + `catalog_1.0.bin` + `catalog_1.0.hash` | **CORRIGÉ** → 205 bundles, 207 fichiers | `lot31-data-3.0-full/bundles/` |
| 44 | `mapscoordinates.json:1-10` = l'en-tête du dump ; 1ᵉʳ record ligne 26779, sans `id` | Confirmé, et **précisé** : l'en-tête occupe les lignes 1-12 ; la forme BRUTE (sans `id`) est à 26779-26785 ; la forme RECONSTRUITE, celle que le fragment cite, est à **128885-128891** et porte bien `id` | **CORRIGÉ** → `:128885-128891`, avec la distinction brut/reconstruit | `mapscoordinates.json:128885-128891` |
| 50 | 230 n'est pas l'ensemble marchable : bords rognés exprès | Confirmé aux deux endroits : `world.md:48` et `data.md:64` (colonnes 0-1/12-13, rangées 0-5/35-39). Fichier entier : 2 987 103 cellules, 173,6/carte, de 1 à 290 | **CORRIGÉ** — 230 devient une **borne inférieure** | `refs/JondoEmu/docs/world.md:48` |
| 59 | Les 17 222 entrées portent `f` **et** `b` ; `b` jamais mentionné | Confirmé et durci : **les 17 222 sans exception** portent exactement ce jeu de deux clés. Astrub : \|f\| 357, \|b\| 85 | **CORRIGÉ** — `b` entre au modèle | `refs/JondoEmu/docs/data.md:33` |
| 64 | 154644 n'est pas voisine d'Astrub : subArea 466 contre 95 | Confirmé : 154644 est en (−46, 20), subArea 466 ; Astrub en (5, −18), subArea 95. Les vrais voisins sont ceux de `MapScrolls` | **CORRIGÉ** — le mot « voisine » retiré | `world.db.MapScrolls` |
| 72 | 17 champs exacts, mais `cellNumber` est en 123424, pas 123422 | Confirmé au comptage de lignes : classe à 123421, `cellNumber` à **123424**. Les 4 autres lignes citées (`mov` 123429, `los` 123430, `floor` 123437, `arrow` 123440) sont exactes | **CORRIGÉ** (1 ligne sur 5) | `il2cpp.cs:123424` |
| 83 | Les 4 voisins sont dans `MapScrolls`, table que le fragment liste lui-même ; les interactifs sont dans `datos/` | Confirmé : `MapScrolls` **17 353 lignes**, Astrub → 191106050 / 191105028 / 191104002 / 191105024 | **CORRIGÉ** — 2 familles sortent du trou | `refs/JondoEmu/docs/world.md:31` |
| 125 | « 12 006 fichiers » irreproductible : il mesure 11 975 et 14 930 | **Le réfutateur a tort sur ce VPS.** `dofus-tools` est un **symlink** ; `find -type f` sur le lien rend 0. Par le chemin réel : **exactement 12 006** fichiers, 14 978 entrées, 445 Mo, 0 outil Unity | **CONTESTÉ** — texte gardé, piège d'instrument documenté | `dofus-tools/` (chemin réel) |
| 133 | « Aucun bundle de scène sur ce VPS » est faux : 577 bundles de géométrie | Confirmé et étendu : **577 `.bundle`** dans `Content/Map/Data/` (569 + 7 + 1), 579 fichiers, 459 Mo, **788 sha256 OK et 0 FAILED** | **CORRIGÉ** — §C entièrement réécrit | `lot37-mapdata-3.0/Content/Map/Data/` |
| 162 | `walkableCells` n'est pas l'ensemble marchable ; `fightCells` recouvre deux populations | Confirmé (voir L50 et L59) | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:33-34` |
| 166 | Il n'existe pas de champ `fight` : `f` = `mov=1 ∧ nonWalkableDuringFight=0` | Confirmé mot pour mot dans la doc | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:33` |
| 173 | `c` = **cellule**, pas catégorie : 558 valeurs distinctes dans 0..559 | Confirmé : `c` prend **558 valeurs distinctes**, toutes dans 0..559, **0 hors bornes**. Précision : le fichier porte **46 309 éléments** ; les 31 440 annoncés par le réfutateur sont le nombre de `e` **distincts**, pas d'éléments | **CORRIGÉ**, avec le compte rectifié | `refs/JondoEmu/docs/data.md:36` |
| 174 | La jointure vers les types se fait sur `g` (415/415), pas sur `e` (0) | Confirmé exactement : `e` rend **0 sur 415**, `g` rend **415 sur 415** | **CORRIGÉ** | `tipos_interactivos_3.6.10.10.json` |
| 179 | La table de spawns est `MapMobs` (38 744 lignes, 3 groupes sur Astrub), jamais nommée | Confirmé : `MapMobs` 38 744 lignes, colonnes `MapId`/`CellId`/`MembersJson`, **3 groupes sur Astrub** (cellules 350, 344, 327) | **CORRIGÉ** | `world.db.MapMobs`, `world.md:35` |
| 199 | « Prouvé » ne porte que sur `data_assets_`, rien sur un `mapdata_assets_` | Confirmé : l'outil n'a jamais tourné sur un bundle de carte. Vérifié en plus que l'en-tête d'un bundle de carte est bien `UnityFS` / `5.x.x` / `0.0.0`, donc le repli de version reste nécessaire | **CORRIGÉ** — la portée de « prouvé » est nommée | `lot30-data-3.0-extract/OUTIL.md:33-40` |
| 230 | Le 230 du gate est exact comme chiffre, faux comme critère | Confirmé, voir §3 | **CORRIGÉ** — gate refait à 6 contrôles | `refs/JondoEmu/docs/world.md:48` |

## 3. Les 12 réfutations sur les entrées DÉDUIT

| L | Ce que le réfutateur dit | Ce que JE mesure | Verdict | Nouvelle source |
|---|---|---|---|---|
| 9 | 3 DÉDUIT renvoient à un canal indisponible ou à rien de falsifiable | Deux des trois (L191, L210) ne sont plus des DÉDUIT du tout : la donnée est arrivée. Le troisième (L225) est un choix de conception, jamais falsifiable | **RÉTROGRADÉ** — défaut réel, mais dissous par le rapatriement | §C du fragment |
| 46 | `compressedCoords` : formule close, 15 360/15 360 | Confirmé indépendamment sur la population entière : **15 360 correspondances, 0 écart**. Astrub (5, −18) → 393 198 | **CORRIGÉ** — promu VÉRIFIÉ | `mapscoordinates.json:128885-128891` |
| 55 | Le générateur est nommé dans la doc : `extract_all_map_walkable.py` ; le fichier rogne exprès | Confirmé | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:34` |
| 60 | `f` = cellules tenables en combat, pas placement ; \|f\| 357 > \|walkable\| 230 | Confirmé : 357 contre 230, et 127 cellules de `f` hors de l'ensemble marchable d'Astrub | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:33` |
| 67 | `{e: element id, c: cell, g: graphic}` ; croiser sur `e` rend 0 | Confirmé sur les deux moitiés | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:36` |
| 108 | Les sigles sont au bloc `# CARTE`, mais le fichier ne numérote rien | Confirmé : `chemin-critique.txt:32` porte `# CARTE (§5.1-5.2)`, `jru` à `:35`, `hjk` à `:36`, et **aucune numérotation « J3.3 » nulle part** | **CORRIGÉ** | `chemin-critique.txt:32` |
| 147 | La sémantique de `f` est écrite noir sur blanc dans le même dépôt | Confirmé | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:33` |
| 160 | Les voisins ne sont pas à peupler : ils sont dans `MapScrolls` | Confirmé, ligne d'Astrub relue en base | **CORRIGÉ** | `world.db.MapScrolls` |
| 163 | `CellsCount = 560` est dans le fichier déjà ouvert | Confirmé aux deux lignes, **plus deux recoupements que le réfutateur ne donne pas** : la même classe porte `Column = 14` (`il2cpp.cs:245097`) et 14 × 40 = 560, ce qui recoupe le rognage de `data.md:64` ; et sur Astrub l'id de cellule le plus haut mesuré vaut 554, sous 560. **Réserve** : la constante vit dans deux classes d'interface, pas dans la classe de données | **CORRIGÉ** — promu VÉRIFIÉ, avec la réserve écrite | `il2cpp.cs:245096` |
| 168 | `los` n'est pas un trou : c'est la clé `b`, 85 cellules sur Astrub | Confirmé : 85 exactement | **CORRIGÉ** | `refs/JondoEmu/docs/data.md:33` |
| 175 | La position **est** `c` ; `interactives.json` ne porte ni `mapId` ni `cellId` | Confirmé : les 446 records de `interactives.json` ne portent que `_class`, `id`, `nameId` | **CORRIGÉ** | `lot31-data-3.0-full/json/interactives.json` |
| 180 | `NpcSpawns` rend 0 ligne pour Astrub, 53 au total ; la vraie table est `MapMobs` | Confirmé aux trois chiffres | **CORRIGÉ** | `world.db.NpcSpawns`, `world.db.MapMobs` |
| 191 | Le chemin réel est `Content\Map\Data\`, pas `aa/` | Confirmé **avec une nuance que ni le fragment ni la réfutation ne donnent** : un dossier `aa/` existe bien dans le lot (`lot37-mapdata-3.0/aa/`, `catalog.bin` de 893 150 octets) — mais il nomme **0 carte et 0 bundle de carte**. Le dossier existait, la géométrie n'y était pas | **CORRIGÉ** avec la nuance | `lot37-mapdata-3.0/aa/` |
| 210 | Les bundles étaient déjà là, 3 h 34 avant le fragment | Confirmé par le manifeste : 788 fichiers, 788 OK, 0 FAILED | **CORRIGÉ** | `lot37-mapdata-3.0/verif.txt` |

## 4. Le gate §D — pourquoi les deux contrôles étaient faux

| Contrôle v1 | Mesure indépendante | Conséquence |
|---|---|---|
| « exactement 230 cellules `mov=true` sur Astrub » | 230 est un compte **rogné** (`world.md:48`) : colonnes 0-1/12-13 et rangées 0-5/35-39 retirées exprès | un extracteur **correct** rend strictement plus que 230 → le gate **refuse le bon résultat** |
| « les cellules `fight` ⊆ les cellules `mov=true` » | Astrub : \|f\| 357 contre 230, **127 cellules hors**. Sur le corpus : **15 774 cartes sur 17 211 violent le contrôle**, 1 702 974 cellules hors au total | le gate crie sur **92 %** du corpus |

Le nouveau gate (§D du fragment) part de `CellsCount = 560` (`il2cpp.cs:245096`), des ids 0..559, d'une
partition exacte, et n'utilise 230 / 357 / 85 **que comme bornes inférieures d'inclusion**. Il ajoute
deux contrôles de nature différente : les 4 voisins contre `MapScrolls` (base serveur contre bundle
client) et les 4 interactifs d'Astrub contre `interactive_elements.json`.

## 5. Ce que le réfutateur a manqué — défaut trouvé pendant la remesure

**L91, que le réfutateur note « confirmé, exact ».** Le fragment écrit que le champ `Data` de
`world.db.MapTemplates` pour Astrub est « **exactement** » une certaine chaîne, et la recopie sans
espaces. Mesuré : la valeur réelle fait **136 octets** et sépare ses champs par `", "` ; la chaîne
recopiée dans le fragment en fait **121**. Même contenu, **pas les mêmes octets**. Le fragment
annonçait d'ailleurs « 136 octets » juste à côté de sa citation de 121 caractères : les deux chiffres
se contredisaient dans la même phrase, et ni l'auteur ni le réfutateur ne l'ont vu. *« Exactement » ne
se dit pas d'une valeur qu'on a reformatée pour la lire.*

## 6. Les 12 points confirmés, revérifiés et tenus

Aucun n'a été touché dans le fragment. Revérifiés un à un ici : les 7 citations d'opcodes
(`anclas_3.6.10.10.tsv:39-40`, `opcodes_emulador_3.6.10.10.tsv:317`,
`protocolo_3.6.10.10.proto:4444`, 2 169 messages, 0 occurrence de « CurrentMapMessage ») ; les 5 lignes
du dump Jiva, qui retombent toutes sur leur `CREATE TABLE` (`world_dev.sql:1191045`, `:1192313`,
`:1874228`, `:1898055`, `:1916899`) ; les 17 champs de `ClientCellData` (`il2cpp.cs:123421-123458`) ;
les 6 `records_count` (`items.json:4137319`, `monsters.json:4343961`, `npcs.json:1847657`,
`mapsinformation.json:506917`, `mapscoordinates.json:190958`, `mapreferences.json:13170`) ; la fiche
d'Astrub (`mapsinformation.json:186544`) ; l'extraction du lot30 (`lot30-data-3.0-extract/OUTIL.md:1-58`).

**Deux notes du réfutateur sont fausses sur ce VPS**, et elles portent toutes deux sur des points qu'il
avait par ailleurs confirmés :

1. **L114** — il écrit « seul le chemin cité n'existe pas ici ». Le chemin
   `<sauvegarde interne datée du 04/09>/world_dev.sql.gz` **existe sur ce VPS**,
   43 818 436 octets, et les 5 citations de ligne y retombent juste.
2. **L125** — voir la ligne CONTESTÉ ci-dessus.

Ces deux erreurs ont la même cause : le réfutateur travaille depuis un autre hôte. **Une affirmation
d'absence porte la machine où elle a été prise, pas seulement l'heure.**

## 7. Les 2 invérifiables, maintenus

| L | Sujet | Pourquoi il reste invérifiable |
|---|---|---|
| 203 | `extract_bundle.py` décodera-t-il `ClientMapData` depuis un bundle de carte ? | Le venv de l'outil est en cpython-3.12, l'hôte en 3.14 ; l'outil n'a jamais tourné sur ce domaine. Épreuve écrite dans le fragment, non exécutée ici. **Tentative faite et négative** : `grep` binaire sur les 577 bundles ne trouve pas `map_191105026` — les bundles sont compressés, cette absence-là ne prouve rien |
| 225 | JSON structuré contre blob compressé pour le stockage des cellules | Choix de conception, rien de falsifiable. Arbitrage à la synthèse |
