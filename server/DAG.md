# DAG — construction du serveur Namaste 3 (étage 3)

> Plan d'exécution en DAG explicite. Écrit le 2026-09-04.
> **Sources lues** : les mêmes que `ARCHITECTURE.md`, plus les gates `gate-g0.py`, `gate-g1.py`,
> `gate-forme.py`, `gate-g2.py`, `gate-codec.sh`. Chaque nœud porte **livrable**, **répartition du travail**,
> **entrées**, **gate déterministe** (script ou scénario bot NOMMÉ, critère CHIFFRÉ) et **« ce qui est
> faux si »**. Un nœud sans gate n'est pas un nœud.
>
> # 🟡 v0 — PLAN, À RÉVISER APRÈS LA CARTE
>
> **Décision du porteur du projet, 04/09** : *« avant de coder tu veux pas attendre la cartographie ??? »*
> ⛔ **AUCUN HANDLER NE S'ÉCRIT AVANT QUE J3.0 SOIT VERT**, et J3.0 exige désormais **G1 verte + le
> graphe `graphe-protocole` interrogeable + ce design révisé en v1**, pas seulement G2. Aucun fichier `.cs`
> n'existe (mesuré : `find server -name "*.cs"` rend **0**).
>
> **Ce que la carte peut déplacer** : les gates de J3.1 à J3.7 suivent le chemin critique tel que
> Jondo le décrit. Une carte complète peut ajouter un message obligatoire, corriger un numéro de champ,
> ou révéler qu'un opcode que je crois terminal attend une réponse. **Les critères chiffrés sont v0** ;
> la structure du DAG n'en dépend pas. Le cahier §2 (« rien avant G2 vert ») est un plancher que
> la décision relève.

---

## 0. Le graphe

```
J3.0  LA CARTE D'ABORD — G1 verte + graphe interrogeable + design v1
      + FONDATIONS rouge-bloquantes (L5)   ← aucun handler avant ce nœud
   │
   ├──► J3.A  Protocole régénéré PAR BUILD ──► J3.A2  Diff build N → N+1
   ├──► J3.B  Données cartes (BLOQUÉ)              (natures de dette, L7)
   └──► J3.C  Socle serveur + trace causale
                    │
                    ▼
  J3.1 connexion nue → écran SERVEUR
   └► J3.2 kqz + rafale → écran PERSOS
       └► J3.3 sélection perso → kva
           └► J3.4 entrée map 191105026
               ├► J3.5 déplacement validé ─► J3.6 changement de carte
               └► J3.7 deux joueurs se voient
                            │
                            ▼
                  GATE G3  →  J3.8 largeur (fan-out)
```

Séquentiel entre jalons du chemin critique, parallèle dedans. J3.A / J3.B / J3.C tournent en parallèle
dès J3.0 verte et alimentent J3.1.

---

## J3.0 — LA CARTE D'ABORD : G1 verte + graphe interrogeable + ce design révisé

> 🔴 **AUCUN HANDLER NE S'ÉCRIT AVANT QUE CE NŒUD SOIT VERT.** Décision du 04/09 : *« avant de
> coder tu veux pas attendre la cartographie ??? »* Ce nœud n'est pas une formalité de démarrage,
> c'est **le** verrou du chantier. Il porte cinq conditions, et les cinq doivent être vertes ensemble.

**Livrable** — `J3.0-PREREQUIS.md`, les cinq mesures ci-dessous **rejouées par nous** (§6 du cahier :
« on relance soi-même, jamais un seul rapport »), plus la **v1 de ce design**, révisée
fragment en main.

**Répartition du travail** — 1 passe de supervision (vérification indépendante), puis 1 passe de supervision (révision du design en v1).

**Entrées** — `tools/protocol-mapping/tools/gate-g1.py` · l'intégralité de `internal/third-party-review/` et
`internal/third-party-review/` · le graphe `graphe-protocole` (GPU dédié) · `internal/haapi-stub/gate-g2.py`
et `RUNBOOK-G2.md` · `internal/bot-testeur/` · `codec/` (**livré 23:20**) · `internal/GATE-G0-RAPPORT.md`.

**Gate déterministe — cinq conditions**

| # | Condition | Critère chiffré | État mesuré le 04/09 23:2x |
|---|---|---|---|
| 1 | **G1 VERTE** | 32/32 opcodes du chemin critique couverts **et** conformes, zéro `DÉDUIT` toléré | 🔴 **32/32 couverts, 31/32 conformes** — un seul refus, `krt`, sur le SENS |
| 2 | **Graphe `graphe-protocole` interrogeable** | une requête rend les opcodes d'une famille avec direction, champs et sources ; témoin négatif : un nom absent du metadata n'y existe pas | 🔴 pas encore interrogeable |
| 3 | **Ce design révisé en v1** | chaque marqueur « v0 — à réviser » d'`ARCHITECTURE.md` est levé, fragment en main, ou re-motivé | 🔴 v0 |
| 4 | **G0 rejouée** | 1003/1003, 0 inventé, ≥ 1000 `IBufferMessage` | 🟢 vert au 04/09 (à rejouer nous-mêmes) |
| 5 | **FONDATIONS rouge-bloquantes** (L5) | les cinq ci-dessous, toutes vertes | 🟡 codec livré, reste à rejouer |

**5 — Le détail des fondations. Aucune n'est facultative, aucune ne se contourne** (L5 : *« l'étage 2
et le design d'archi sont les fondations : ils se prouvent AVANT le premier handler »*).

| Fondation | Gate | État |
|---|---|---|
| **Codec** | `gate-codec.sh` rejouée par nous : round-trip **byte-exact** sur **322 + 2 + 31 = 355 frames** réelles, 0 écart | 🟡 livré le 04/09 23:20 (`codec/`), **jamais rejoué par nous** |
| **Transport** | pile de JEU sur DotNetty (`ProtobufVarint32FrameDecoder`), **sans octet de type** ; un test le prouve contre une trame réelle et **échoue** si l'on préfixe un octet | 🔴 |
| **Dispatch** | table `nom ↔ opcode ↔ type` **chargée au démarrage** depuis `binding-<build>.tsv` ; `grep -rnoE '"[a-z]{3}"' src/` == **0** | 🔴 |
| **Bot-testeur** | `chemin-critique --seed 42` deux fois, 2 sha256 identiques | 🟢 livré et mesuré (`SPEC.md:172-192`) |
| **Modèle de données** | migrations appliquées, carte 191105026 avec `sub_area_id = 95` et 560 cellules dont 230 marchables | 🔴 (cf. J3.B) |
| **G2** | 5 marqueurs sur 5 face au client vivant | 🟡 vert au 04/09, à rejouer |

Fixtures mesurées : 64 510 o / 322 frames, 2 348 o / 2, 90 935 o / 31
(`internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:930-947`).

**Ce qui est faux si** — trois pièges nommés. (a) On déclare J3.0 vert **parce que les fragments sont
arrivés**, sans que le graphe réponde ni que le design soit révisé : livrer n'est pas fermer.
(b) Le codec rend `rc=0` sur un fichier tronqué : la gate compte les frames **et** compare les octets,
un vert sur 0 frame décodée est un échec. (c) On contourne la condition 1 en retirant `krt` de
`chemin-critique.txt` pour faire verdir G1 : ce serait rendre l'instrument vert par l'instrument. Le
sens de `krt` se mesure par une capture réelle (cf. J3.2), il ne se supprime pas.

---

## J3.A — Protocole régénéré depuis NOTRE dump (parallèle)

**Livrable** — `Namaste3.Protocol` (assembly généré, 0 ligne écrite à la main) + `Namaste3.ProtoGen`
(le générateur, déterministe) + `protocol/binding-3.6.10.10.tsv` (constante sémantique → opcode, avec
tag et source) + la table `messages-jondo.tsv` **regénérée sur le bon fichier**.

**Répartition du travail** — 2 lots d'implémentation (générateur + transcription), 1 passe de supervision (vérification de la table de liaison).

**Entrées** — `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs` (2169 + 37 classes) ·
`tools/protocol-mapping/matcher/correspondance-noms-classes.tsv` · `tools/protocol-mapping/index/handlers-jondo.tsv` ·
`refs/JondoEmu/datos/protocolo_3.6.10.10.proto` (**seul `.proto` Jondo autorisé**, 2169 messages) ·
`internal/chemin-critique.txt` (32 opcodes).

> **Sous L6, ce jalon n'est pas un préalable : c'est le MODE DE FONCTIONNEMENT NORMAL.** Une nouvelle
> build d'Ankama = rejouer la chaîne, régénérer la table, rejouer le bot. L'étage 4 « survie aux
> patchs » n'est donc pas un durcissement final, c'est J3.A qui tourne. Patron mesuré à lire :
> `refs/otomai/tools/proto-sync/` (1201 lignes, registre versionné, snapshot par `--game-version`,
> `diff.py` entre deux versions). Objectif L7 : **une build inconnue traverse la chaîne sans main
> humaine jusqu'au bot**, et le rapport de diff nomme chaque écart.

**Gate déterministe** — script `tools/gate-j3a.py`, refus nommé par motif :
1. nombre de messages générés == **2169** (Game) + **37** (Connection) — la corroboration à deux
   natures de source (`GATE-G0-RAPPORT.md:19` et `grep -c "^message "` sur le `.proto` reconstruit)
   donne 2169 des deux côtés ;
2. les **32 opcodes** de `chemin-critique.txt` sont tous présents dans le registre généré ;
3. **témoin négatif** : 5 opcodes fictifs absents du registre ;
4. `grep -rn "Jondo.Unity.Protocol/Messages/Protocol.proto"` dans les scripts d'extraction == **0** ;
5. `messages-jondo.tsv` régénéré : le déplacement est `jrw` avec **f1 = mapId (int64)** et
   **f2 = chemin (repeated int32)**, et plus jamais `ise`.

**Ce qui est faux si** — on regénère depuis `Jondo.Unity.Protocol/Messages/Protocol.proto` (80
messages, écrit à la main). Mesuré ce tour : ce fichier **inverse f1/f2 du déplacement**, donne à
`ksl` deux champs au lieu d'un, à `kqp` dix au lieu de deux (détail et lignes :
`ARCHITECTURE.md` §5.3). Les deux formes sont des varints : **ça compile, ça passe le codec, et ça
déplace le personnage n'importe où.** C'est exactement « le type est bon, la source est fausse ».

---

## J3.A2 — Diff build N → N+1 par natures de dette (L7, le ping-pong)

**Livrable** — `Namaste3.ProtoDiff` : prend deux instantanés de build, rend un rapport de diff où
**chaque écart porte sa nature**, et régénère la table de liaison de la build N+1 en reportant le sens
déjà connu depuis N.

**Répartition du travail** — 1 lot d'implémentation (outil), 1 passe de supervision (arbitrage des écarts non résolus).

**Entrées** — les 5 natures de dette éprouvées sur un cycle réel : `absent` · `renommé` ·
`neutralisé` · `mal rempli` · `non routé` (`ARCHI-REFERENCE-JIVA.md` §F.1, `Tools/ProtoDiff273/`) ·
`refs/otomai/tools/proto-sync/` (`diff.py`, `registry.py`) · le re-mappage structurel de Jondo
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:786-833`) · plusieurs builds 3.0 via Cytrus.

**Gate déterministe**
1. **ping-pong sans main humaine** (l'objectif de L7) : une build inconnue traverse dump → matcher →
   table → bot, et le bot rend un rapport. Aucune intervention manuelle dans la chaîne ;
2. **chaque écart est NOMMÉ** par une des 5 natures — 0 écart classé « autre » ;
3. **le sens voyage, l'opcode non** : un message apparié entre N et N+1 garde son nom sémantique et
   change d'opcode ; la gate vérifie qu'aucun **sens** n'a été recopié sur une paire non appariée ;
4. **plancher de hasard mesuré** : on tire 20 appariements au hasard et on compare le score du
   matcher à cette moyenne. Un matcher qui ne bat pas le hasard est refusé.

**Ce qui est faux si** — on juge le matcher sur « son score s'effondre quand on mélange l'entrée ».
Un comptage peut coïncider par hasard à petit N alors que **toutes** les paires sont fausses : c'est
l'erreur déjà commise et corrigée dans `matcher/RAPPORT-MATCHER.md` §5 point 5, où le nombre de
correspondances restait identique sous mélange pendant que 0 paire se recoupait. La gate compare donc
**l'ensemble des paires**, jamais leur nombre.

---

## J3.B — Données de cartes 3.0 : géométrie, sous-zones, voisinage (parallèle) — 🔴 **BLOQUÉ**

> **Statut : BLOCKED, demande une main humaine.** Les bundles de scène qui portent
> `ClientMapData.cellsData` et les quatre voisins de carte **n'existent nulle part sur ce VPS** —
> mesuré : `find -iname "*.bundle"` ne trouve que les **204** bundles de DONNÉES
> (`data_assets_*dataroot.asset.bundle`) de `lot31-data-3.0-full/bundles/`
> (`DONNEES-3.0-CARTE.md:133-138`). Le client complet n'est que sur `D:\Jeux\Dofus-dofus3`.
> Fait aggravant mesuré : **même `world.db` de Jondo ne stocke aucune géométrie de cellule** — sa
> table `MapTemplates` (15 360 lignes) ne porte qu'une fiche d'identité (`:91-101`). Le trou est
> structurel, pas un oubli de notre extraction.
>
> **Déblocage, en deux gestes** : (1) rapatrier le dossier de bundles de scène depuis un PC personnel
> (chemin Addressables à confirmer, `DONNEES-3.0-CARTE.md:191-197`) ; (2) le passer à
> `lot30-data-3.0-extract/extract_bundle.py` (UnityPy 1.25.3, repli
> `FALLBACK_UNITY_VERSION=6000.3.0f1`), outil **déjà éprouvé sur les 204 autres bundles** — ne pas en
> écrire un second (`:199-208`).
>
> **Ce qui avance sans le déblocage** : la table `map` (identité + `sub_area_id` + `mov`) est
> constructible **aujourd'hui** ; elle suffit à J3.4 et à trois des quatre contrôles de J3.5. Ce qui
> attend : les 13 autres drapeaux de cellule, et les voisins de carte (donc J3.6).

**Livrable** — migration + import déterministe de la table `map` : `map_id`, `sub_area_id`,
`cells bytea(560)` ; plus la table de voisinage de cartes quand les bundles seront là.

**Répartition du travail** — 2 lots d'implémentation (extraction), 1 passe de supervision (vérification des drapeaux).

**Entrées** — `lot31-data-3.0-full/json/mapsinformation.json` (15 360 cartes ; Astrub à `:186544`) ·
`refs/JondoEmu/datos/map_walkable_cells.json` (17 211 cartes) ·
`refs/JondoEmu/datos/map_fight_cells.json` (17 222 cartes) · **le schéma cible d'une cellule est déjà
lisible dans NOTRE dump** : `ClientCellData`, 17 champs, `il2cpp.cs:123421-123458`, et `ClientMapData`
avec ses 4 voisins, `il2cpp.cs:123604-123645` (relevés par `DONNEES-3.0-CARTE.md:72-89`) · les bundles
de scène, **absents** (cf. encadré).

**Gate déterministe** — `tools/gate-j3b.py` :
1. la carte **191105026** existe et porte `sub_area_id = 95` — valeur VÉRIFIÉE, présente dans deux
   sources indépendantes (`world.db.MapTemplates` de Jondo et
   `lot31-data-3.0-full/json/mapsinformation.json:186544`, `DONNEES-3.0-CARTE.md:96-98`). Un zéro fait
   planter le client dans `MapInfoUI.SetInfoFromSubarea`
   (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:641-643`) ;
2. son `cells` fait **560 octets** et compte **exactement 230 cellules marchables** — mesuré ce tour
   par lecture de `map_walkable_cells.json` (clé `191105026` → liste de longueur 230), grille 14×40 =
   560 (`refs/JondoEmu/docs/world.md:18`) ;
3. les cellules 311, 325 et 339 (celles du scénario bot canonique,
   `internal/bot-testeur/SPEC.md:104-105`) sont **marchables** ;
4. **témoin négatif** : une cellule connue non marchable est bien à 0.

**Ce qui est faux si** — on alloue 230 cellules. **230 est le compte des MARCHABLES, pas la taille de
la grille** : le brief transmis à l'architecte disait « 230 cellules », la mesure dit 560 dont 230
marchables, avec des identifiants qui commencent à 91 et montent jusqu'à 559. Un tableau de 230 plante
au premier identifiant. Faux aussi si les drapeaux sont recopiés du format 2.x de Jiva (11 octets par
cellule, `Cell.cs:8,59-85`) sans mesure côté 3.0.

---

## J3.C — Socle serveur : transport, dispatch, Area, persistance, trace causale (parallèle)

**Livrable** — les six projets de `ARCHITECTURE.md` §2 avec 0 handler métier : transport TCP + framing
varint, codec branché, dispatch vide, une Area qui tourne à vide, migrations Postgres, `[Dette]`
listée au démarrage, `execution_trace` qui écrit.

**Répartition du travail** — 1 passe de supervision (archi du socle), 2 lots d'implémentation (implémentation cadrée).

**Entrées** — `ARCHITECTURE.md` §2-§4-§7, `INTERFACES.md` §1-§4, `ARCHI-REFERENCE-JIVA.md` §B.1/§D,
`ARCHI-REFERENCE-GINY.md` §C.2/§G.2.

**Gate déterministe** — `tools/gate-j3c.sh`, quatre mesures :
1. **isolation** : `grep -rl 'using Namaste3.Protocol' src/Namaste3.World/ | wc -l` == **0**
   (référence adverse : 414/571 = 72,5 % chez Giny, `ARCHI-REFERENCE-GINY.md` §G.3) ;
2. **garde d'Area par le type** : un fichier de test qui mute le domaine hors `AreaTick` **ne compile
   pas** — la gate compile ce fichier et exige `rc != 0` avec l'erreur attendue (contrôle positif ET
   négatif : le même fichier avec `AreaTick` doit compiler) ;
3. **taille** : `find src/ -name '*.cs' | xargs wc -l | awk '$1>=500'` == vide ;
4. **dette branchée** : le démarrage journalise N entrées `[Dette]` avec N == le compte de l'attribut
   par grep (corrige le défaut mesuré chez Giny, `AnnotationsManager.Analyse` jamais appelé, §G.2).

**Ce qui est faux si** — la gate 2 est écrite en asserttant le NOM du garde plutôt que son EFFET (un
garde asserté par son nom est toujours vert). Elle doit compiler du code fautif et exiger l'échec.

---

## J3.1 — Le vrai client atteint l'écran de **sélection de serveur**

> **Correction du brief, mesurée.** Le brief disait « J3.1 = le vrai client atteint l'écran de
> sélection de serveur (kqz → rafale de bienvenue) ». Ces deux moitiés ne vont pas ensemble : `kqz`
> présente le TICKET sur la **seconde** connexion et déclenche la rafale qui se termine par `kvi`, la
> liste des **personnages** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:369-382, 404-421`). La sélection de
> serveur se joue AVANT, sur le protocole **nu**, sans enveloppe `Any` (`:281-343`). J3.1 est donc le
> protocole nu ; `kqz` + rafale est J3.2.

**Livrable** — `namaste3-connect` : `:5555`, protobuf NU (pas d'enveloppe), racine `mhh` à **trois**
champs, `BuildAuthenticationAccepted` (compte + résumés de personnages + liste de serveurs) puis
lecture de `mhj{lang, selectedServer{serverId}}` et émission de `mhl{ticket, host, ports}`.
Ticket écrit en base, TTL 5 min, usage unique.

**Répartition du travail** — 1 passe de supervision (conception de la phase nue), 1 lot d'implémentation (implémentation).

**Entrées** — `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:281-357` (schéma `.proto` nu, capture octet à octet
`0a 0a 08 0a 01 31 22 03 08 a2 02` = `auth{lang:"1", selectedServer{serverId:290}}`) ·
`refs/JondoEmu/datos/protocolo_conexion_3.6.10.10.proto:163-178,255-257` (37 messages) ·
`internal/haapi-stub/CARTE-HAAPI.md` §2 (`connectionHosts` porte l'adresse) · J3.A, J3.C.

**Gate déterministe** — deux niveaux, le second fait foi :
1. **bot** : `run --scenario j31-server-selection --seed 42` → `OK`, et deux runs byte-identiques ;
2. **client vivant** (client réel, 3.6.10.10 non modifié) : l'écran de sélection de serveur s'affiche avec
   notre nom de serveur, `Player.log` sans exception, `netstat` montre une connexion établie sur 5555 ;
3. **décodage croisé** : la frame `mhj` reçue est décodée par le sniffer et ses champs correspondent
   à `{f1:string lang, f4:{f1:int32 serverId}}` — le tag `0x22` = `(4<<3)|2` et `0x08` sont vérifiés
   octet à octet contre l'exemple de capture ci-dessus.

**Ce qui est faux si** — on n'implémente que deux champs sur la racine `mhh`. Le `.proto` reconstruit
en déclare **trois** (`gfcd=1` auth, `gfce=2` authResult, `gfcf=3` type `mhn`), et Jondo omet le
troisième (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:906-913`). Notre codec doit le PARSER sans planter même
s'il reste vide. Faux aussi si l'écran s'affiche parce que le client a repris une session en cache :
la gate exige un profil client neuf.

---

## J3.2 — Ticket `kqz` + rafale de bienvenue → écran des **personnages**

**Livrable** — `namaste3-world` accepte la seconde connexion, décode `kqz{f2: ticket}`, consomme le
ticket **atomiquement** en base, tolère `krt` (aucun payload connu) sans le jeter en silence, puis
émet la rafale dans l'ORDRE EXACT :

```
kra → lqu → hoy → kqu → mgq → mgt → hpd → krs → mgz → kqp → kqp → kqp → kvi → kvd → jtg
```

**15 messages**, 3 `kqp` aux payloads **différents** (`{f1:1,f2:1}`, `{f1:1}`, vide) — ordre et
payloads mesurés (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:404-421`), types de champ mesurés dans le
builder (`COMPLEMENT-CHEMIN-CRITIQUE-G1.md:57-140`).

**Répartition du travail** — 1 passe de supervision (séquence + consommation du ticket), 2 lots d'implémentation (builders).

**Entrées** — `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:367-456` · `COMPLEMENT-CHEMIN-CRITIQUE-G1.md:20-140`
(les 5 types manquants : `lqu` f1/f2 varint, `hoy` f1/f2/f3 varint + f6 string + f7 varint sans f5,
`mgq` 3 varints, `hpd` 1 varint, `mgz` f1 varint = 304672615 opaque) · J3.1.

**Gate déterministe**
1. **bot** : `run --scenario j32-welcome-burst --seed 42` → `OK`, phase `Authenticated`, liste de
   personnages non vide ;
2. **ordre** : la trace serveur porte les **15** messages dans l'ordre exact ; un test rejoue la
   séquence et compare la liste ordonnée — 15/15, 0 permutation ;
3. **usage unique** : rejouer le MÊME ticket une seconde fois → **refus nommé** `TICKET_CONSUMED`,
   connexion fermée, 1 ligne dans `execution_trace`. Contrôle positif : un ticket frais passe ;
4. **client vivant** : l'écran des personnages s'affiche, et le bouton « créer un personnage » est
   actif — l'absence de `kvd` était le principal suspect de ce bouton mort chez Jondo (`:420`) ;
5. **`krt`** : capture décodée du `krt` réel. Si son payload est non vide, l'écrire dans le fragment
   de carte. **C'est le seul manque G1 que le travail parallèle n'a pas pu combler** — Jondo ne l'implémente pas
   (branche vide, aucune constante `Op.Krt`, quatre tables répètent la même absence,
   `COMPLEMENT-CHEMIN-CRITIQUE-G1.md:22-53`).

**Ce qui est faux si** — la gate 3 est verte parce que le ticket n'a jamais été écrit (jamais essayé
ressemble à jamais réussi). Elle exige le contrôle positif dans le même run. Faux aussi si le succès
vient d'une barrière voisine : si `kqz` est accepté sans ticket valide parce que le décodage a échoué
en silence, le test 3 passerait pour la mauvaise raison — d'où le refus **nommé** obligatoire.

---

## J3.3 — Sélection de personnage → `kva`, entrée en jeu

**Livrable** — handler de `kvw` (et de ses variantes), vérification que le personnage **appartient au
compte de la session**, chargement, émission de `kva`, diffusion `jsn` aux autres sessions de la carte.

**Répartition du travail** — 1 passe de supervision, 1 lot d'implémentation.

**Entrées** — `COMPLEMENT-CHEMIN-CRITIQUE-G1.md:144-235` · `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:434-541`.

**Gate déterministe**
1. **bot** : `run --scenario j33-character-select --seed 42` → `OK`, phase passe à « perso choisi » ;
2. **adversarial, le point dur** : le bot envoie un `characterId` **appartenant à un autre compte** →
   refus nommé `CHARACTER_NOT_OWNED`, 0 chargement, 1 trace. Contrôle positif : son propre personnage
   passe ;
3. **les trois formes** : `kvw`, `kvl`, `ksl` sont décodés **chacun selon SA déclaration**, pas par
   une lecture générique. Mesuré : `kvw {int64 f1}` · `kvl {bool f1; int64 f2}` ·
   `ksl {enum f1}` (`datos/protocolo_3.6.10.10.proto:13498-13500, 13459-13462, 13173-13175`, relus
   ce tour). La gate vérifie que le handler de `kvl` lit **f2**, jamais f1 ;
4. **client vivant** : le sablier se referme, le client sort de l'écran perso.

**Ce qui est faux si** — on copie la lecture générique de Jondo. Son handler lit `FieldNumber==1 &&
WireType==0` pour les trois opcodes (`CharacterSelectionHandler.cs:228`) : sur `kvl` cela lit le
**booléen** f1 comme un identifiant de personnage, sur `ksl` un **enum** valant 0 ou 1
(`COMPLEMENT-CHEMIN-CRITIQUE-G1.md:179-227`). Les trois sont des varints — ça compile, ça décode, et
ça charge le personnage n°1 ou rien. Faux aussi si la gate 2 est verte parce que le compte de test n'a
qu'un personnage : elle exige deux comptes peuplés.

---

## J3.4 — Entrée sur la carte 191105026

**Livrable** — bloc carte : `lqc` (ou premier `kqo` en secours) → `jru{f2 mapId}` → `lqu` → `hjk` ;
puis sur `jrh` → `jss` (acteurs, `f6 subAreaId` obligatoire) → `lva`. Garde **un seul envoi** du bloc
carte par entrée.

**Répartition du travail** — 1 passe de supervision (séquence), 2 lots d'implémentation (`jss` : la structure la plus lourde du chemin critique).

**Entrées** — `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:545-670` · `COMPLEMENT-CHEMIN-CRITIQUE-G1.md:239-312`
(les sept sites qui appellent `hjk`, toujours dans l'ordre `jsd → jru → lqu → hjk`) · J3.B.

**Gate déterministe**
1. **bot** : `run --scenario j34-map-entry --seed 42` → `OK`, `position` d'introspection rend
   `{"mapId":191105026,"cellId":311,"phase":"InMap"}` — exactement la forme que le bot rend déjà
   contre son faux serveur (`internal/bot-testeur/SPEC.md:126`), donc comparable ;
2. **double envoi** : forcer deux blocs carte → la garde refuse le second, 1 trace, **0 boucle de
   rechargement** côté client (l'envoyer deux fois fait boucler le client, `:610-611`) ;
3. **`jss` f6** : un test envoie `subAreaId = 0` → notre serveur **refuse d'émettre** et trace, plutôt
   que d'envoyer un message qui plante le client ;
4. **client vivant** : le personnage apparaît à Astrub, la carte porte son nom et la minimap est
   peuplée (sans `hjk`, la fenêtre de voyage affiche « No destination », `README.md:100` de Jondo).

**Ce qui est faux si** — on rejoue les `.bin` de Jondo comme le fait Jondo. Ses trois fixtures
contiennent des **données de compte tiers** et des opcodes de sa liste `NotReplayed`
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:957-961`) : elles servent de **preuve de round-trip pour le codec**
(J3.0), jamais de contenu à émettre. Un `jru` construit à partir d'un frame rejoué serait un faux vert
(le client entre en jeu, mais rien de notre serveur n'a été prouvé).

---

## J3.5 — Déplacement validé serveur-side (le nœud qui n'a aucune référence)

**Livrable** — handler `jrw` → validation **quatre contrôles** (`ARCHITECTURE.md` §6.1) → `jsj`
diffusé. Le type `Path` sans constructeur accessible.

**Répartition du travail** — 1 passe de supervision (conception de la validation), 1 lot d'implémentation (implémentation), 1 passe de supervision (adversarial).

**Entrées** — `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:672-698` (`jrw f1 mapId, f2 chemin packed, pas =
(facing<<12)|cell`) · `ARCHI-REFERENCE-JIVA.md` §B.4/§E.1 · `ARCHI-REFERENCE-GINY.md` §C.3 · J3.B.

**Gate déterministe** — `j35-movement` + **suite adversariale de 5 scénarios, tous devant être
REFUSÉS avec un motif distinct** :

| Scénario bot | Attendu |
|---|---|
| `j35-adv-wrong-map` | `REFUSED:MAP_MISMATCH` |
| `j35-adv-teleport-start` | `REFUSED:START_CELL_MISMATCH` (le contrôle que Jiva a commenté) |
| `j35-adv-through-wall` | `REFUSED:CELL_NOT_WALKABLE` (le contrôle que Giny n'a pas) |
| `j35-adv-jump` | `REFUSED:PATH_NOT_CONTIGUOUS` (personne ne l'a) |
| `j35-adv-overbudget` | `REFUSED:MOVEMENT_BUDGET` (personne ne l'a) |

Plus : **contrôle positif** `j35-movement` → `OK`, position serveur mise à jour ; **gate de
construction** `grep -rn "new Path(" src/ | grep -v "Path.cs"` == 0 ; **5 motifs distincts** dans
`execution_trace` (pas 5 fois le même).

**Ce qui est faux si** — les cinq refus sont produits par la **même** barrière. Un test adversarial
vert peut l'être par une autre barrière que celle qu'on croit mesurer : la gate exige **cinq motifs
NOMMÉS différents**, un par contrôle, sinon elle échoue même si tout est refusé. Faux aussi si un
refus est un silence : Jondo ignore silencieusement un `jrw` au mauvais mapId (`:679-682`), ce qui
laisse le joueur figé sans savoir pourquoi — chez nous un refus répond et trace.

---

## J3.6 — Changement de carte (`jqi` → `jsq` → `jqk` → `jsd`/`jru`) — dépend du déblocage de J3.B

> **Ne peut pas être déclaré vert avant J3.B.** La résolution de la carte voisine exige les quatre
> voisins de `ClientMapData` (`il2cpp.cs:123607` et ses pairs), qui vivent dans les bundles de scène
> absents du VPS (cf. J3.B). L'arithmétique de coordonnées reste un **filet**, jamais la vérité : chez
> Jondo, l'étage « table de voisinage » est quasiment inatteignable parce que l'étage précédent écrit
> presque toujours les 4 voisins, dont une part pointe vers des cartes inexistantes dans `MapPositions`
> (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:740-743`).

**Livrable** — `jqi` (vide) → `jsq` **sur le champ racine 3**, avec l'id de requête ÉCHOÉ ; puis
`jqk{f2 mapId}` traité comme une **supposition du client**, résolue serveur-side ; puis `jsd`, `jru`,
`lqu`, `hjk` dans cet ordre.

**Répartition du travail** — 1 passe de supervision, 1 lot d'implémentation.

**Entrées** — `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:700-777` (résolution du voisin en 3 étages ;
arithmétique cardinale mesurée sur 4 captures : droite −13/facing 0, gauche +13/facing 4, haut
+532/facing 6, bas −532/facing 2) · J3.B (table de voisinage).

**Gate déterministe**
1. **champ racine** : la frame `jsq` émise est comparée **octet à octet** à la capture de référence.
   Envoyée sur le champ 1 au lieu du 3, le client l'ignore, n'envoie jamais `jqk`, et le personnage
   reste bloqué au bord **définitivement** (`:718-722`) — c'est le piège le plus cher du jalon ;
2. **id de requête** : deux tests, `reqId = -1` (98,9 % des 15 583 requêtes mesurées, `:771`) **et**
   `reqId ≠ -1` — l'id doit être **lu et réinjecté**, jamais codé en dur ;
3. **supposition fausse du client** : le bot envoie `jqk` avec un mapId **inexistant** (cas réel
   mesuré : le client demande 191105029, la vraie voisine est 188745734, `:731-733`) → le serveur
   résout la bonne carte et trace la correction ;
4. **client vivant** : marcher jusqu'au bord change de carte, sans blocage ni double fondu.

**Ce qui est faux si** — on code `-1` en dur parce que 98,9 % des cas le portent. Une corroboration
sur la plage fréquente ne valide pas la plage rare : les 1,1 % restants (167 requêtes mesurées)
casseraient en silence.

---

## J3.7 — Deux joueurs se voient (`jsn`)

**Livrable** — diffusion à la map entière : `jsn` à l'entrée d'un acteur, `jsd` à sa sortie, `jsj`
sur son déplacement — vers les **autres** sessions de la carte, jamais vers l'auteur.

**Répartition du travail** — 1 passe de supervision, 1 lot d'implémentation.

**Entrées** — `COMPLEMENT-CHEMIN-CRITIQUE-G1.md:241-273` · `ARCHI-REFERENCE-JIVA.md` §B.5.

**Gate déterministe**
1. **deux bots** : deux `ScenarioRunner` sur une horloge virtuelle partagée
   (`internal/bot-testeur/SPEC.md:220-221`) ; le bot A entre, le bot B **voit** A ; A se déplace,
   B voit le déplacement ; A part, B voit la disparition. 3 assertions, 3 `OK` ;
2. **exclusion de l'auteur** : A ne reçoit **pas** son propre `jsn` — compteur à 0 ;
3. **client vivant + bot** : un humain sur le client officiel voit l'avatar du bot bouger.

**Ce qui est faux si** — la visibilité marche parce que les deux bots partagent un état en mémoire.
La gate exige deux connexions TCP distinctes. Question ouverte transmise : Jondo affirme que « le vrai
serveur envoie trois `jsn` d'affilée, un suffit » **sans dire pourquoi** (`:267-273`) — à trancher par
capture, pas par copie.

---

## GATE G3

Un joueur humain se connecte avec le client **3.6.10.10 officiel non modifié**, crée un personnage,
apparaît à Astrub (191105026), se déplace, voit un autre joueur. **Mesuré, filmé.**

Preuve additionnelle exigée : la même séquence rejouée par le bot-testeur rend un rapport `OK`
rejouable, et `execution_trace` porte la chaîne causale complète de la session, du ticket au dernier
pas.

---

## J3.8 — Largeur (fan-out, après G3)

Une famille d'opcodes par lot d'implémentation, worktree isolé, **un scénario bot par famille**, gate
identique dans sa forme : contrôle positif + suite adversariale à motifs distincts + isolation
protocole/domaine rejouée. Familles, dans l'ordre de dépendance : PNJ/dialogue → inventaire/objets →
chat/social → métiers → combat (le plus lourd ; y verser la `FightTimeline` et le synchronisateur
tolérant au lag de Giny, `ARCHI-REFERENCE-GINY.md` §D.1-D.2) → guildes/alliances → économie/HDV →
zaaps/voyage.

**Règle de fermeture, non négociable** : un handler « vert » sans
scénario bot-testeur passé est REFUTED. `dotnet test` ne ferme aucun nœud.
