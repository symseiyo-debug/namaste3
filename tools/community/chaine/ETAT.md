# ETAT.md — une ligne par build, avec ses chiffres

> Mesuré le **04/09/2026 entre 21:00 et 22:10 UTC**. Chaque chiffre porte l'instrument qui l'a produit.
> Un compte non remesuré par un second chemin est marqué **« 1 chemin »**.
> **L4** : les 2.x ne sont pas des annexes du 3.0 — chaque build a sa ligne et son livrable.
> **L6** : chaque artefact porte sa build dans son chemin et dans ses colonnes.
> Les chaînes : `CHAINE.md` · le rejeu par un externe : `RUNBOOK-COMMUNAUTE.md`.
>
> ⚠️ **Contexte du soir** : l'export ffdec 2.x a été **arrêté à 21:21 UTC** sur décision du projet
> (*« focus Dofus 3 avant la 2 »*). La chaîne 2.x est **en pause, pas en échec**.
> Reprise : `bash ../../internal/as3/export-as3.sh 268 238 242`.

---

## Vue d'ensemble — les maillons, build par build

| build | famille | obtenir | décompiler | complétude | tables protocole | données | dynamique |
|---|---|---|---|---|---|---|---|
| **3.6.10.10** | 3.x | ✅ binaires | ✅ dump complet | 🟢 **G0 VERTE** | ⚠️ littéraux ✅, `.proto` ❌ | ⚠️ lot31 ✅, cartes ❌ | ⚠️ codec ✅, hook ❌ |
| **3.6.4.3** | 3.x | ❌ jamais téléchargée | — | — | — | — | — |
| **3.6.10.11** | 3.x | ❌ existence non vérifiée | — | — | — | — | — |
| **2.73** | 2.x | ✅ SWF **retrouvé** | ⚠️ réseau seul | 🔴 3 paquets troués | ✅ **1190 / 366 / 119** | ✅ outils d2o/d2p | s.o. |
| **2.68** | 2.x | ✅ SWF | ⚠️ 16,6 %, **arrêté** | 🔴 4,70 % | ⚠️ 40 / 31 / 4 | ✅ outils | s.o. |
| **2.42** | 2.x | ✅ SWF | ⚠️ réseau seul | 🔴 4 paquets troués | ✅ **1033 / 288 / 95** | ✅ outils | s.o. |
| **2.38** | 2.x | ✅ SWF | ❌ jamais lancé | — | ❌ | ✅ outils | s.o. |
| **toute autre build** | 2.x ou 3.x | `obtenir_build.sh` ✅ (mode plan) | ✅ chaînes rejouables | ✅ gates rejouables | ✅ | ✅ | ⚠️ partiel |

`tables protocole` en 2.x = messages / types / enums.

---

# Famille 3.x

## 3.6.10.10 — la build de référence, seule chaîne statique verte

| maillon | état | chiffres |
|---|---|---|
| binaires | ✅ | `GameAssembly.dll` 115 367 424 o · `global-metadata.dat` 40 335 992 o · metadata **v39** |
| dump | ✅ | `il2cpp.json` 217 Mo · `il2cpp.h` 132 Mo · `cs/il2cpp.cs` **1 081 733 lignes** · `dll/` **143 DLL fantômes** · `MANIFEST.sha256` 6 lignes |
| **gate G0** | 🟢 | **rejouée par moi** (appel de `mesurer()`, **aucune écriture** ailleurs) : **VERT · 100,00 % · 0 inventé · 2319 `IBufferMessage` · 0,7 s** |
| littéraux | ✅ | **32 936** — JSON **32936** == regex **32936** (second chemin, écart 0) |
| routes HAAPI | ✅ | **372** — `diff` **vide** contre `routes-haapi-catalogue.txt` (autre chemin) |
| noms de protocole | ✅ | **1003** — metadata 1003, DLL 982 + 21 = 1003 ; `diff` **vide** contre `noms-protocole-en-clair.v2.txt` |
| autres surfaces | ✅ | 47 URL · 99 chemins sources · 19 littéraux Zaap · 5 candidats de configuration |
| matcher | ⚠️ en cours | `../../tools/protocol-mapping/matcher/` (autre chantier). **Non rejoué par moi** |
| `.proto` + dispatch | ❌ | dépend du matcher. L6 : la table de dispatch se **génère par build** |
| données Addressables | ⚠️ | `lot30-data-3.0-extract/extract_bundle.py` lit les bundles ; lot31 déjà décodé (21 748 items, 17 054 sorts, 15 360 cartes). **Manque : les 577 bundles `Map/Data`** (géométrie), jamais moissonnés |
| **dynamique — codec** | ✅ | `../../codec/` **VERT : 355 trames réelles round-trip byte-exact, 71 tests, 0 échec** |
| **dynamique — hook IL2CPP** | ❌ | rien d'écrit. Matière prête : `il2cpp.json` porte **335 415** méthodes avec RVA, dont **55 927** dans `Ankama.Dofus.Protocol.Game.dll` |
| **dynamique — rejeu / corrélation** | ❌ | dépend du hook |
| **gate L7** | 🔴 | `chaine_3x.sh 3.6.10.10` : **3 maillons franchis** (dump, G0, littéraux), **3 refus nommés** (matcher, `.proto`, bot). Une build ne va donc **pas** encore jusqu'au bot sans main humaine |

## 6.0_3.6.4.3 — TÉLÉCHARGÉE le 05/09, la seconde build est là

| | |
|---|---|
| binaires | `internal/artefacts/builds/6.0_3.6.4.3/` — **149 Mo, 2 fichiers**, `MANIFEST.sha256` écrit |
| `GameAssembly.dll` | 115 427 328 o · sha256 `baa59e710b479cbb…` |
| `global-metadata.dat` | 40 323 424 o · sha256 `ea6534f229625b40…` (sous `Dofus_Data/il2cpp_data/Metadata/`) |
| second chemin | ✅ sha256 recalculés à la main, **identiques** au manifeste écrit par le script |
| distincte de 3.6.10.10 | ✅ les 4 empreintes diffèrent : ce sont bien **deux builds différentes**, pas deux copies |
| durée | **12 s** au total (8 s de transfert annoncés par cytrus) · disque : 59 Go libres avant **et** après, le coût ne se voit pas à ce niveau |
| suite | dump (≈ 468 Mo attendus), gate G0, littéraux, puis `diff_builds.py --chaine` contre 3.6.10.10 : **c'est là que le rebrassage 3.x cessera d'être une loi lue pour devenir une mesure à nous** |

### Première mesure À NOUS : ce qui survit entre deux builds 3.x (noms clairs)

Lue **directement dans les deux `global-metadata.dat`**, sans dump : `3.6.4.3` porte **985** noms clairs
`Com.Ankama.Dofus.Server.*`, `3.6.10.10` en porte **1003**. Second chemin (`grep -aoE` sur le binaire) :
**985**, identique.

| population | 3.6.4.3 | 3.6.10.10 | communs | apparus | disparus |
|---|---|---|---|---|---|
| nom complet | 985 | 1003 | **599** | 404 | 386 |
| nom de feuille | 959 | 982 | **592** | 390 | 367 |

**61,7 % des noms de feuille survivent.** La partition est assertée des deux côtés (599+404+386 = 1389
noms de l'union). J'ai vérifié que l'écart n'était pas un simple déménagement de namespace : seuls **9**
noms communs changent de chemin complet, **583** gardent feuille ET chemin. Le reste est de la vraie
rotation de protocole entre les deux builds.

> ⚠️ **Ce que ce chiffre ne dit PAS.** Un nom « disparu » peut être un message **renommé**, pas supprimé —
> `AchievementFinishedEvent` d'un côté, `AchievementRewardResultEvent` de l'autre, est-ce le même message ?
> Le NOM ne peut pas répondre. Seule la **signature protobuf** (numéros de champ et types) le peut, et
> elle demande le dump de 3.6.4.3. Tant qu'il manque, « 38 % de rotation » est un **plancher** de
> stabilité, pas une mesure de churn réel.
> **Conséquence pour nos handlers** : ils ne doivent s'ancrer ni sur le token obfusqué (rebrassé), ni sur
> le nom clair (61,7 % de survie mesurée), mais sur la **forme protobuf**, la seule ancre restante.

### ⏹️ Multi-build ARRÊTÉ sur ordre le 05/09 — la mesure ci-dessus est acquise

Décision du projet, verbatim : *« osef du portage de version pour l'instant, faisons déjà un serveur qui
marche »*. Le dump de 3.6.4.3, le diff structurel et le ping-pong sont **arrêtés**, pas échoués. Les
binaires (149 Mo) et les quatre maillons d'outillage restent en place pour la reprise.
Ce qui reste utile au serveur dès maintenant : ses handlers ne peuvent s'ancrer ni sur le token
obfusqué ni sur le nom clair, donc sur le **nom sémantique d'une table régénérée** (`proto-sync`).

### Pourquoi le dump avait été arrêté avant l'ordre (contexte machine, 05/09 00:20)

Lancé à 00:14 (nice 10, port SignalR déplacé sur 5099 pour ne pas gêner le dump voisin sur 5000),
**arrêté par moi à 00:20 après 6 minutes**. Raison mesurée au moment de la décision :

| indicateur | valeur |
|---|---|
| charge sur 4 vCPU | 9,5 puis 11,2 |
| mémoire disponible | 2,5 Go puis 2,3 Go |
| swap | **10 240 Mo sur 10 240, soit 100 %** |
| travaux lourds concurrents | ffdec 2.73 (5,7 Go, nice 15) · un second dump 3.6.10.10 (4,8 Go, 2 h 30, 10 % CPU) |

Trois travaux lourds sur 4 cœurs avec le swap plein : le prochain manque de mémoire aurait fait tuer le
plus gros processus, c'est-à-dire **le travail d'un autre chantier**, pas le mien. J'ai donc arrêté le mien,
qui était le plus jeune. Les deux voisins ont été vérifiés vivants après coup.
**Reprise** : `bash internal/artefacts/builds/6.0_3.6.4.3/dump/lancer-dump.sh` quand ffdec ou le dump
voisin aura fini.

> 🔴 **Piège trouvé sur mon propre lanceur.** La CLI Il2CppInspector **sort avec `rc=0` sur SIGTERM** :
> mon script a donc enregistré `rc=0 duree=363s` pour un dump interrompu au quart, dossier `cs/` **vide**.
> Un code de retour ne dit pas qu'un octet est arrivé. Le lanceur juge désormais les **octets produits**
> (`cs/il2cpp.cs` présent et > 10 Mo), et rend `VERDICT=INCOMPLET` sinon.

## 6.0_3.6.10.11 — existe, non téléchargée

`https://cytrus.cdn.ankama.com/dofus/releases/dofus3/windows/6.0_3.6.10.11.manifest` rend **200**
(manifeste 51,9 Mo), mesuré le 05/09. `cytrus.json` la déclare comme la version courante du canal
`dofus3`. Coût attendu : ~150 Mo, quelques secondes. Non prise : une seconde build suffit à démarrer
le ping-pong, et une troisième se justifiera quand la chaîne aura tourné sur les deux premières.

---

# Famille 2.x

## 2.73 — le SWF EST sur le VPS (le cahier le disait perdu)

| | |
|---|---|
| SWF | ✅ `internal/infra-backup/DofusInvoker.swf.LIVE-backup-avant-deploiement` · 7 855 386 o · sha256 `b5f0fcf11f37…` — **la sauvegarde AVANT patch** |
| autres exemplaires | `…PATCHED-activelog` (sha `8a4bab6a6908…`) · `dofus-tools/swf-patch/DofusInvoker-273-stumpkey.swf.DEFECTUEUX-NE-PAS-PUBLIER` (sha `e8e026628a59…`) — **même jeu de classes**, contenus patchés |
| contenu (parseur ABC) | CWS v40, 21,5 Mo, **6594 classes**, **1685** réseau, **1201** messages |
| arbre AS3 | `dofus-tools/client273-as3/network/` — **1679 `.as`** |
| **tables** | **1190 messages · 366 types · 119 enums** (810 valeurs) · **0 rejet** · ordre de sérialisation sur **1046 / 1190** |
| second chemin | ✅ `grep` rend 1190 et 366, `find` rend 119. Coïncidence exacte |
| complétude | 🔴 1679/1685 = **99,64 %**, **0 inventée**, **3 paquets troués, 6 classes** : `CredentialsAcknowledgementMessage`, `IdentificationSuccessWithLoginTokenMessage`, `ReloginToken{Request,Status}Message`, `HaapiToken{,Request}Message` |
| appariement SWF ↔ arbre | **VÉRIFIÉ par l'invention** : 0 classe inventée contre ce SWF, **28** contre le SWF 2.68. Un arbre ne peut pas contenir des classes absentes du binaire dont il sort |
| rôle | **SOURCE de lecture, jamais une cible** (L4 : « pas de serveur 2.73 ») |
| pour débloquer | copier ce SWF dans `../../internal/as3/swf/DofusInvoker-273.swf` (hors de ma zone) puis export ffdec complet |

> 🔴 **MON ERREUR, corrigée sur mesure.** J'avais écrit « SWF 2.73 **ABSENT** du VPS » sur la foi d'un
> `find -maxdepth 4` sur deux racines. **Une recherche bornée ne prouve jamais une absence** : le fichier
> était hors de mes racines. Le cahier porte la même affirmation (« Le 2.73 SWF n'est plus sur le VPS ») —
> **elle est fausse**, et probablement pour la même raison. La recherche non bornée a pris 3 secondes.

## 2.68 — export interrompu à 16,6 %

| | |
|---|---|
| SWF | `DofusInvoker-268.swf` · 7 906 576 o · sha256 `1cd92aee26960461…` |
| contenu (ABC) | CWS v40, 21,5 Mo, **6569 classes**, **1659** réseau, **1188** messages |
| arbre AS3 | **1064 fichiers `.as`** pour **6428 scripts** annoncés (16,6 %). Trois nombres circulent dans le journal — fichiers écrits **1064**, index à l'arrêt **967**, dernier index journalisé **1041** : l'export est parallèle, l'index n'est pas un compteur de fichiers. Le seul qui compte est **1064, mesuré sur le disque**. Sous `network/` : **83** |
| tables (partielles) | **40 / 31 / 4** — le suffixe `-partiel` est dans le nom **exprès** : une table partielle qui porte le nom de la version se fait citer comme complète |
| complétude | 🔴 **4,70 %** (78/1659), 15 paquets troués |
| 🔴 défaut ffdec | **4 fichiers** portent `OutOfMemoryError` à la place du code (`-Xmx1024m`). Taille normale, contenu vide |

## 2.42 — la mieux servie, et son trou nommé

| | |
|---|---|
| SWF | `DofusInvoker-242.swf` · 6 487 395 o · sha256 `a0b7090bb6528988…` |
| contenu (ABC) | CWS v14, 12,0 Mo, **5171 classes**, **1428** réseau, **1045** messages |
| arbre AS3 | `dofus-tools/client242-as3/` — **1420 `.as`, réseau UNIQUEMENT** (27,5 % du SWF) |
| **tables** | **1033 messages · 288 types · 95 enums** (731 valeurs) · **0 rejet** · ordre sur **938 / 1033** (les 95 sans ordre ont **tous 0 champ**) |
| second chemin | ✅ 1033 / 288 / 95 / 731 par `grep`+`find`. Coïncidence exacte |
| complétude | 🔴 1420/1428 = **99,44 %**, 0 inventée, **4 paquets troués, 8 classes** dont tout le chemin de login |

## 2.38 — le SWF est là, rien n'en a été tiré

| | |
|---|---|
| SWF | `DofusInvoker-238.swf` · 3 942 973 o · sha256 `75b9ebb7189759b8…` |
| contenu (ABC) | CWS v14, 9,2 Mo, **5085 classes**, **1402** réseau, **1023** messages |
| arbre AS3 | **vide** — l'export n'a jamais démarré |
| tables | aucune |
| 🔴 étiquette non prouvée | « 238 » est le nom du fichier. Mon recoupement par exclusives est **non discriminant** : 160/219 exclusives-Symbioz vues ici contre **156/219 dans le SWF 2.42**. Écart de jeux de messages avec 2.42 : **26 en plus, 4 en moins** côté 2.42. *Trancher* : exporter l'arbre puis `diff_builds.py` sur les `protocolId` |

---

## 🔴 Les arbres `dofus-tools/client242-as3` et `client273-as3` sont PARTIELS et FILTRÉS — à REMPLACER

Ils ne contiennent que `com/ankamagames/dofus/network/` (1420 et 1679 `.as`, soit 27,5 % et 25,5 % de
leur SWF), et leur export d'origine **écartait en plus la famille jeton / relogin / HAAPI** (motif
ci-dessous). **Ne les cite jamais comme des arbres complets.** Les tables `messages-242.tsv` et
`messages-273.tsv` qui en sortent sont justes **sur ce qu'elles couvrent**, et incomplètes par le bas.
Remplacement en cours : export ffdec COMPLET, 2.42 dans l'autre chantier et 2.73 ici. Quand ils arrivent :
`verifier_arbre_as3.py` **sans** `--prefixe` (la question devient « tout le SWF »), puis
`extraire_as3_protocole.py`, puis `diff_builds.py` contre les tables actuelles — l'écart mesurera
exactement ce que le filtre avait mangé.

> ⚠️ **Le run 2.73 lancé ce soir tourne avec `-Xmx1024m`** (lu dans la ligne de commande du processus).
> C'est le tas qui a produit **9 fichiers sans corps sur 1064** en 2.68. Le nouvel arbre 2.73 aura donc
> probablement le même défaut, sous une forme parfaitement normale. Relancer avec `-Xmx6g`, ou compter
> les `ÉCHEC DE DÉCOMPILATION ffdec` à l'arrivée et refaire les classes touchées.

## Un motif, pas une coïncidence : les messages de JETON manquent dans DEUX arbres

| arbre | classes manquantes |
|---|---|
| 2.42 (1420 `.as`) | `CredentialsAcknowledgementMessage` · `IdentificationSuccessWithLoginTokenMessage` · `ReloginToken{Request,Status}Message` · `HaapiTokenTypeEnum` · 3 × `KrosmasterAuthToken*` |
| 2.73 (1679 `.as`) | `CredentialsAcknowledgementMessage` · `IdentificationSuccessWithLoginTokenMessage` · `ReloginToken{Request,Status}Message` · `HaapiToken{,Request}Message` |

**Les quatre premiers sont identiques dans les deux arbres, exportés à des dates différentes.** Deux
arbres ne perdent pas les mêmes quatre classes par hasard : l'export d'origine avait un filtre, et il
écartait la famille **jeton / relogin / HAAPI** — celle dont un serveur a besoin pour le chemin de login,
et que le cahier signale déjà comme manquante à la gate G1. **Confirmer** : relancer un export ffdec non
filtré d'une seule de ces classes. Tant que ce n'est pas fait, c'est un **DÉDUIT à forte présomption**.

## Ping-pong mesuré (2.42 → 2.73, à l'intérieur de la famille 2.x)

| population | natures |
|---|---|
| messages | AJOUTE 310 · RETIRE 153 · **RENOMME 4** · RENUMEROTE 716 · RESTRUCTURE 158 · **INCHANGE 2** |
| champs | CHAMP_AJOUTE 87 · CHAMP_RETIRE 85 · TYPE_CHANGE 53 · inchangés 1196 |

**874 des 876 messages communs changent d'identifiant : 99,8 %.** Renommages trouvés, sémantiquement
justes : `ExchangeHandleMountsStableMessage → ExchangeHandleMountsMessage`,
`PartyCompanionUpdateLightMessage → PartyEntityUpdateLightMessage`. Ambiguïtés **refusées** : 5 + 4.
**Sur 3.x : NON MESURÉ**, une seule build dumpée.

---

## Les outils : état et épreuve

| outil | chaîne | épreuve | état |
|---|---|---|---|
| `extraire_litteraux.py` | A4 · 3.x | **7/7** | ✅ reproduit 372 routes et 1003 noms à l'identique |
| `chaine_3x.sh` | A8 · 3.x | **4/4** | ✅ mesure la gate L7 et nomme ses trous |
| `verifier_arbre_as3.py` | C3 · 2.x | **5/5** | ✅ parseur ABC maison, indépendant de ffdec |
| `extraire_as3_protocole.py` | C4 · 2.x | **6/6** | ✅ 0 rejet sur 2.42 (1420) et 2.73 (1679) |
| `diff_builds.py` | D | **11/11** | ✅ renommage pur + champs, refuse les ambiguïtés |
| `diff_protocole.py` | D · survol | **8/8** | ✅ |
| `obtenir_build.sh` | A1 et C1 | **9/9** | ⚠️ multi-builds prouvé en mode plan ; **jamais exécuté en vrai** |
| `attendre_et_extraire.sh` | commodité 2.x | — | ⏹️ arrêté (export 2.x en pause) |
| `gate-commentaires.py` | transversale, zone voisine | la sienne | 🟢 **8 VERT / 0 ROUGE** sur mes 8 fichiers (100 % des unités commentées). Elle avait d'abord refusé 3 fichiers bash : commentaire sur la même ligne au lieu d'au-dessus. Corrigé, rejouée |
| `gate-g0.py` · `codec` · `croiser.py` · matcher | zones voisines | les leurs | non modifiés ; G0 et le codec rejoués/lus, pas touchés |
| `export-as3.sh` | zone étage 0 | — | ⚠️ défaut `-Xmx1024m` signalé, **non corrigé** (pas ma zone) |

## Maillons MANQUANTS, et pourquoi

| maillon | chaîne | pourquoi ce n'est pas fait |
|---|---|---|
| hook IL2CPP à l'exécution | B2 · 3.x | s'exécute sur un **PC Windows personnel**, pas sur ce VPS ; et le patron `dofus3-native-host` se lit, ne s'exécute pas (cahier). La table de hooks devra être **générée par build** (les RVA bougent) |
| rejeu de captures · corrélation | B3, B5 · 3.x | dépendent de B2 |
| `.proto` + table de dispatch | A6 · 3.x | dépend du matcher, en cours dans un autre chantier. Sans lui, un `.proto` serait un fichier de noms inventés |
| bundles `Map/Data` | A7 · 3.x | 577 bundles jamais moissonnés ; l'outil de lecture existe |
| builds 3.6.4.3 / 3.6.10.11 | A1 · 3.x | téléchargement non lancé (≈ 512 Mo/build) ; c'est ce qui bloque le ping-pong 3.x |
| exports 2.38 / 2.68 / 2.73 complets | C2 · 2.x | **arrêtés sur ordre** (« focus Dofus 3 avant la 2 ») ; je n'ai pas relancé un travail tout juste arrêté |
| `rendre_docs.py` | C7 · 2.x | pas écrit ; j'ai préféré finir le ping-pong et le pilote L7, mesurables aujourd'hui |
| vérification Cytrus | A1/C1 | aucun appel réseau émis ; `--vraiment` téléchargerait des Go sur un disque partagé |
