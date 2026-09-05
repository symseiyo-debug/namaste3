# Descripteur brut + noms fuités — ce que la méthode Jondo donne sur NOTRE client

> **Statut : DONE_WITH_CONCERNS.** Les trois réponses sont mesurées, gates vertes (3/3 × 3).
> **La réponse 1 de l'ordre est FAUSSE, et c'est la mesure qui le dit** — mais la chasse a
> déterré deux choses que l'ordre ne demandait pas et qui valent bien davantage.
>
> Client mesuré : **3.6.10.11**, `global-metadata.dat` (40 335 992 o) et `GameAssembly.dll`
> (115 367 424 o), témoins de `internal/artefacts/temoins-3.0/`.
> Écrit le 2026-09-05. Tout chiffre ci-dessous est mesuré ; aucun n'est estimé.

---

## 0. Les deux trouvailles hors périmètre, à lire en premier

Elles changent plus le chantier que les trois réponses demandées.

### 0.1 Entre 3.6.10.10 et 3.6.10.11, les jetons NE TOURNENT PAS — 2 169 sur 2 169 identiques

`refs/JondoEmu/datos/mapeo_3.6.10.10_a_3.6.10.11.tsv` est la table qui aboutit à **notre**
version. Ses 2 169 lignes sont l'**identité** : `hdw→hdw`, `hdx→hdx`, …, `origen=estructura`
partout, **zéro rotation**.

| mesure | valeur |
|---|---:|
| lignes de la table | 2 169 |
| jetons identiques 3.6.10.10 → 3.6.10.11 | **2 169** |
| rotations entre ces deux correctifs | **0** |

**Conséquence** : tout le travail 3.6.10.10 de Jondo s'applique **verbatim** à notre client, sans
réappariement. Son `.proto` reconstruit, ses 293 ancres, ses 513 noms réels, son index de
2 169 messages — directement utilisables. L'hypothèse « même build des deux côtés » que
`matcher/ACCORD-JONDO.md` posait sans preuve est désormais **mesurée**.

L'ordre désignait `mapeo_3.6.10.10_a_DofusClient.tsv` et
`mapeo_Ankama.Dofus.Protocol.Game_a_3.6.10.10.tsv` comme « jeton → nom clair ». **Ce n'est pas ce
qu'elles contiennent** : leurs deux premières colonnes sont deux jetons obfusqués, et la seconde
n'a aucune colonne de nom renseignée (0 sur 1 530). La table utile n'était ni l'une ni l'autre.

### 0.2 Les vrais noms des messages SONT dans le fichier, mais orphelins — 513 sur 513 présents

Jondo l'a écrit dans l'en-tête de `nombres_reales_3.6.10.10.tsv` : l'obfuscateur renomme les
classes en trois lettres mais **laisse les chaînes de noms réels** dans `global-metadata.dat`,
dans la région `fieldAndParameterDefaultValueData`. Elles sont **orphelines** : personne ne les
référence (3 coïncidences sur 2 687 chez lui, c'est-à-dire du bruit). On ne peut donc pas savoir
par le client quelle chaîne va avec quel jeton.

Vérifié sur **notre** fichier 3.6.10.11 : **513 des 513 noms** sont présents, octet pour octet.

C'est la **liste FERMÉE des noms valides** de cette version. Elle ne dit pas quel nom va avec quel
jeton, mais elle borne l'espace de recherche — et c'est elle qui sert de cible au baptême du §2.

---

## 1. RÉPONSE 1 — le descripteur brut : RÉFUTÉ, mesuré sur notre client

### 1.1 Le résultat

| chemin de mesure | conteneur | occurrences `.proto` | candidats | **descripteurs valides** |
|---|---|---:|---:|---:|
| A — brut (méthode Jondo) | `global-metadata.dat` | 118 | 0 | **0** |
| B — base64 (générateur C# de bureau) | `global-metadata.dat` | — | 4 684 (3 684 décodables) | **0** |
| C — brut | `GameAssembly.dll` | **0** | 0 | **0** |

`descripteurs-3.6.10.11.jsonl` : **0 ligne**. `protocole-descripteur.proto` : en-tête seul.
Aucun message, aucun champ, aucun enum. Il n'y a **rien** à comparer aux 2 206 classes / 6 277
champs de `matcher/extraction-stats.json` ni aux 2 169 de Jondo.

Le chiffre qui tranche est le **contraste** : 118 occurrences du texte `.proto`, et **pas une
seule** précédée d'un en-tête protobuf `0x0A <longueur>`. Ce sont des chaînes, pas des
descripteurs. Détail des 118 : **103** sont des chemins de paquet Unity
(`…\PackageCache\com.ankama.dofus.protocol.…` — le mot *protocol* contient *.proto*, coïncidence
bête) et les ~15 restantes sont les noms de fichiers des types bien connus de Google
(`google/protobuf/any.proto`, `…/timestamp.proto`, …), stockés à la file dans la table des
littéraux, sans préfixe de longueur.

### 1.2 Pourquoi l'ordre se trompait — la contradiction est DANS le dépôt Jondo

L'ordre cite l'en-tête de `Jondo.Unity.Reversing/DescriptorExtractor.cs` : *« está EN CRUDO…
los bytes del FileDescriptorProto tal cual »*. Mais `docs/desofuscacion.md`, seconde passe du
19/08/2026, **§3.1 « El descriptor serializado no está en el cliente »**, réfute exactement cela,
mesures à l'appui : pas de base64, pas de brut (les `.proto` sont des chemins PackageCache), rien
dans `GameAssembly.dll`. Et sa propre table des fichiers, ligne 629, classe le fichier :

> `DescriptorExtractor.cs` — *el camino muerto del descriptor serializado (§3.1)*

**L'en-tête du C# est l'hypothèse ; le §3.1 est sa réfutation.** Les deux cohabitent dans le dépôt,
le code mort n'ayant pas été supprimé. Lire le premier sans le second, c'est prendre une piste
abandonnée pour une réponse acquise.

Et le §2.1 dit d'où sort réellement son `.proto` : du **volcado des classes par Cpp2IL**, où le
générateur C# laisse une constante par numéro de champ. **Son `.proto` n'a jamais eu de descripteur
pour source.** L'ordre affirmait le contraire.

Notre chantier matcher, qui avait conclu « piste fermée : ce sont les descripteurs de Google »,
**avait raison**. La correction qu'on lui a opposée était l'erreur.

### 1.3 La phrase demandée ne peut pas être écrite

L'ordre prévoyait, *si le descripteur brut est trouvé*, d'écrire « le `.proto` est désormais
VÉRIFIÉ depuis le client, plus DÉDUIT depuis Jondo ». Il n'est pas trouvé.
**Le `.proto` reste DÉDUIT** — reconstruit depuis la structure des classes IL2CPP. C'est la même
nature de preuve que celle de Jondo, sur le même client, ce qui est déjà solide ; ce n'est pas une
vérification par la source d'autorité.

### 1.4 Pourquoi ce zéro est une mesure et pas une panne

Un instrument aveugle et un terrain vide écrivent le même « 0 ». `--epreuve` rend **3/3 verts** :

| épreuve | résultat |
|---|---|
| **Témoin positif** — un `FileDescriptorProto` synthétique écrit à la main, injecté à l'offset 0xf4240 **dans la zone réelle du fichier qui contient déjà des chaînes `.proto`** | **retrouvé, 1 fichier / 1 message / 3 champs, longueur exacte** |
| **Sabotage** — 1 octet inversé, aux 106 positions du témoin | **106/106 rejetés en décodage strict, 0 message faux produit** |
| **Rejeu** — deux passes sur la même entrée | **byte-identique, 300 o** |

Le décodage strict est un aller-retour byte-identique : re-sérialiser depuis la valeur décodée doit
rendre les mêmes octets. S'y ajoutent numéros de champ non décroissants, varints minimaux, UTF-8
strict. C'est ce qui fait que 3 684 blobs base64 décodables n'en produisent aucun de valide.

---

## 2. RÉPONSE 2 — les noms fuités : la veine est réelle, et plus riche qu'annoncé

### 2.1 Ce que l'ordre décrivait, et ce qu'il y a en plus

L'ordre décrivait le lien `classe → noms de ses machines d'état`. Il y a mieux : **la machine
d'état porte les paramètres de la méthode en CHAMPS TYPÉS**. Le message n'est pas déduit d'un
voisinage, il est **nommé directement** :

```
public class ehl                                    ← le nom ne dit rien
  private struct _WaitForAddingObject_d__24         ← mais celui-ci, si
      public itl message;                           ← et il NOMME le message : itl
```

`ehl` est bien la classe que Jondo cite en exemple, et elle est là dans notre dump 3.6.10.11.

### 2.2 Les chiffres

| mesure | valeur |
|---|---:|
| classes obfusquées retenues (nom fuité **ou** interface en clair) | 2 814 |
| dont `Ankama.Dofus.Protocol.Game.dll` | 1 601 |
| dont `Core.dll` | 1 178 |
| **`Core.dll` avec au moins un NOM FUITÉ** (le critère des 377 de Jondo) | **142** |
| noms fuités distincts, tous assemblages | 280 |
| messages (sur 2 206) avec au moins un indice | 1 664 |
| messages avec un indice **spécifique** (porteur citant ≤ 5 messages) | 762 |
| messages avec un indice **DIRECT** (champ d'une machine d'état nommée) | **14** |
| propositions de nom contre les 513 noms réels | 31 |
| **propositions retenues** (nom unique, aucun ex æquo) | **6** |

**Écart avec Jondo : 142 contre ses 377, à critère et assemblage égaux.** Nous en voyons **un peu
plus du tiers**. La cause la plus probable — et je l'écris comme **hypothèse non mesurée** — est
l'outil de dump : Jondo lit du **Cpp2IL**, nous lisons de l'**Il2CppInspectorRedux**. J'ai vérifié
que ce n'est pas mon motif qui rate : j'ai recensé toutes les formes de types imbriqués générés par
le compilateur dans le fichier (`__c`, `__c__DisplayClassN_N`, `_Nom_d__N`, `__Nom_b__N_d`, …) et
le motif les couvre. **Si l'hypothèse est bonne, refaire l'étage 0 avec Cpp2IL multiplierait cette
veine par ~2,6.** C'est le chantier que ce rapport recommande en premier.

### 2.3 Les 14 indices directs — la récolte de haute confiance

| message | machine d'état qui le porte | nom proposé |
|---|---|---|
| `lfg` | `eoi:PrepareAndDispatchFightMapData` | FightMapContext *(ex æquo)* |
| `jxu` | `fke:HandleFightResume` | **FightResume** |
| `hlm` | `eqq:RefreshTagsWhenContentReceived` | **TagStoragesRefreshEvent** |
| `ihb` | `eqq:PresetListEventWhenCharacterInfo` | **CharacterPresetInfoResponse** |
| `ioc` | `epd:NpcDialogCreationWhenAvailable` | **NpcDialogCreationEvent** |
| `jbu` | `erd:OnWaitHavenBagFurnituresEvent` | **HavenBagFurnitureOpenRequest** |
| `ijq` | `fhr:ManageFightPings` | FightPingCellRemoveRequest *(ex æquo)* |
| `inv` | `ern:OnPlayEmoteOnNpcEventAsync` | EmotePlayEvent *(collision)* |
| `iny` | `ern:OnPlayAnimationOnNpcEventAsync` | EmotePlayEvent *(collision)* |
| `jss` | `eoi:DelayUntilLoaded` | — |
| `itl` | `ehl:WaitForAddingObject` | — |
| `ite` | `ehl:WaitForDroppingObjects` | — |
| `idu` | `eps:UpdateQuestWhenSubAreaLoaded` | — |
| `kba` | `fjw:DelayPlacementDisplay` | — |

Cinq de ces baptêmes sont propres. Le sixième retenu, `kva → TokenRequest`, est **un faux positif
que je signale** : ses porteurs `eau`/`ecv` sont des classes du **launcher Zaap** (leurs noms
fuités sont `RequestAPIToken`, `PayCart`, `RequestZaapLanguage`…), et Jondo mesure sur capture que
`kva` est `CharacterSelectedSuccessMessage`. **La capture l'emporte sur la fuite.**

Recoupement indépendant qui, lui, tient : mon baptême par fuite propose `MapCurrentEvent` pour
`jru`, là où Jondo propose `CurrentMapMessage` et où **nos propres captures** disent la même chose.
Trois chemins qui convergent — et au passage, `MapCurrentEvent` est le nom **réel** (il est dans la
liste fermée des 513), tandis que celui de Jondo est une proposition de style Dofus 2.x.

### 2.4 Les 8 opcodes du chemin critique : la fuite ne les nomme pas

`matcher/A-NOMMER-PAR-CAPTURE.tsv` en listait 8. Résultat, sans détour :

| | mgq | mgt | hpd | krs | kqp | ksl | krt | hjk |
|---|---|---|---|---|---|---|---|---|
| indice par fuite | — | faible | faible | — | faible | faible | faible | faible |
| indice **direct** | — | — | — | — | — | — | — | — |
| nom proposé | — | — | — | — | — | — | — | — |

**6 sur 8 reçoivent un indice, tous faibles (score 1 à 3), aucun exploitable. Zéro nom.**
Ces huit-là **restent à nommer par capture** ; ce chantier ne les débloque pas.

Ce qu'il apporte quand même, via les ancres de Jondo (§3) : **7 des 8 sont dans `anclas`** avec
leur **direction** (7 S2C, `krt` en C2S), le **handler** qui les émet (`BuildWelcomeBurst` pour
cinq d'entre eux, `BuildMapDiscovered` pour `hjk`) et leur **forme capturée**. Trois portent en
plus une signification mesurée. **`ksl` est absent d'`anclas`** : Jondo ne l'a jamais vu passer.

---

## 3. RÉPONSE 3 — les tables Jondo, triées par fiabilité réelle

### 3.1 Le tri

`origen` de Jondo → notre fiabilité : `estructura` = **FIABLE**, `modelo` = **DÉDUIT** (un LLM a
choisi), `duda` = **JAMAIS**, `retirado` = **ABSENT**. Témoin négatif de la gate : **0 ligne
`duda`/`retirado`** n'a franchi le tri, sur 274 lignes retenues.

Mais le tri par `origen` ne suffit pas, et c'est Jondo lui-même qui le dit dans l'en-tête
d'`anclas` : **« El NOMBRE es una propuesta, no un dato »** — le nom est écrit *au style de Dofus*
d'après ce que le message fait. La **signification**, elle, est mesurée en croisant le code de
l'émulateur avec **242 captures du jeu réel**. Deux fiabilités dans la même ligne :

| colonne | fiabilité | volume |
|---|---|---:|
| jeton (`origen=estructura`) | **FIABLE** | 2 169 / 2 169 |
| signification | **MESURÉE** (242 captures) | 274 |
| nom | **PROPOSÉ** (l'auteur le dit) | 99 |

Les importer sous une seule étiquette « Jondo » ferait passer une proposition pour une mesure.

### 3.2 Confrontation avec nos 208 — et la circularité qu'il fallait retirer

Premier calcul : **96 accords sur 99**. Invraisemblable, donc suspect. Vérification : **72 de nos
208 correspondances `DÉDUIT` de `correspondance-v4.tsv` portent la provenance
`proposition_jondo_seule`** — elles sont **recopiées d'`anclas`**. Les compter comme un accord avec
Jondo, c'est se faire confirmer par sa propre copie.

Après exclusion des lignes circulaires :

| verdict | nombre |
|---|---:|
| **accord INDÉPENDANT** | **24** |
| désaccord | **1** |
| accord circulaire, exclu du compte | 72 |
| apporté par Jondo, absent de chez nous | 2 |
| chez nous seulement | 111 |

Les **24 accords indépendants viennent tous de `capture_verifiee`** — nos propres captures. Ce sont
deux natures de source différentes qui tombent d'accord (nos paquets vs son code d'émulateur croisé
à 242 captures), donc une corroboration réelle, pas un tampon.

**L'unique désaccord** : `hjj` — Jondo dit `TeleportDestinationsMessage` (proposition), nous disons
`GuildCardEvent` (provenance `structure_v2`, forme + champs). Une proposition contre une déduction
structurelle : **ni l'une ni l'autre n'est mesurée**, le point reste ouvert.

---

## 4. Ce que ça change pour le matcher

**Combien de messages nommés au total, en fusionnant les trois sources** — sur 2 206 :

| source | apport | nature |
|---|---:|---|
| Jondo `anclas`, jetons `estructura` | 99 | nom **PROPOSÉ**, sens **MESURÉ** sur 242 captures |
| nos captures (`capture_verifiee`) | 24 dont 24 en accord avec Jondo | **MESURÉ** |
| fuites, propositions retenues | 6, dont **1 faux positif avéré** (`kva`) | **DÉDUIT** |
| fuites, indices directs sans nom | 8 de plus (`jss`, `itl`, `ite`, `idu`, `kba`, …) | piste **forte**, à nommer |

Nommés avec une preuve qui tient : **~104 jetons distincts** (99 de Jondo, dont 24 corroborés par
nos captures, plus 5 baptêmes propres par fuite). Les 1 664 messages « avec indice » ne sont **pas**
des messages nommés : c'est un espace de recherche réduit, rien de plus.

Les quatre gestes qui rapportent, dans l'ordre :

1. **Refaire l'étage 0 avec Cpp2IL** au lieu d'Il2CppInspectorRedux — hypothèse : ×2,6 sur la veine
   des noms fuités (142 → ~377 sur `Core.dll`). C'est le seul geste qui change un ordre de grandeur.
2. **Consommer `indice_3.6.10.10.json`** (2 169 entrées : sightings, contexte, voisinage), valide
   verbatim chez nous d'après le §0.1. C'est l'équivalent Jondo de notre `contexte-appels.jsonl`,
   **produit par un autre instrument** (analyse ISIL par Cpp2IL) — donc une corroboration
   indépendante, message par message, sur les 2 169.
3. **Retirer les 72 lignes circulaires** du décompte de `correspondance-v4.tsv`, ou les marquer :
   telles quelles, elles gonflent tout accord futur avec Jondo.
4. **Capturer les 8 opcodes** : rien ici ne les nomme, et `ksl` n'a même jamais été vu par Jondo.

---

## 5. Mes erreurs

Cinq défauts, tous dans mon propre instrument, tous trouvés en mesurant et corrigés :

1. **`int` compté comme un jeton obfusqué.** `^[a-z]{2,4}$` matche aussi les mots-clés C# ;
   `public int __1__state;` fabriquait un message nommé « int ». Liste d'exclusion ajoutée.
2. **Les champs de la classe parente attribués à la dernière machine d'état.** Ma pile
   d'imbrication ne portait pas la profondeur, donc en sortant d'un type imbriqué l'attribution
   continuait. Corrigé en indexant la pile par profondeur de tabulation.
3. **1 ligne `// Image` lue sur 141.** Je m'arrêtais à la première ligne non commentée, or
   Il2CppInspector sème ces lignes jusqu'à la ligne 9953 entre des déclarations. Toutes les classes
   tombaient en DLL « ? », ce qui rendait impossible la comparaison à population égale avec les 377
   de Jondo. Corrigé — et c'est ce qui a donné les 142.
4. **Motif trop étroit : 16 formes de machines d'état ratées.** Les machines d'état de lambdas
   async portent **deux** soulignés en tête (`__Nom_b__N_d`), j'en exigeais un.
5. **Un ex æquo tranché par l'ordre du fichier.** `…HavenBagFurnitures…` était à égalité (3 mots)
   entre `HavenBagFurnitureOpenRequest` et `HavenBagDailyLotteryEvent` : le premier rencontré
   gagnait. Corrigé par une pondération à la rareté du mot (« Event » est dans un nom sur trois et
   ne désigne rien) plus normalisation des pluriels, et les ex æquo sont désormais **comptés et
   affichés** au lieu d'être tranchés en silence.

Et une erreur de méthode que je signale sur le brief lui-même : j'ai commencé par lire l'en-tête
du C# que l'ordre citait. C'est `docs/desofuscacion.md` §3.1 — dans le **même dépôt** — qui le
réfute. **Un ordre qui cite une source la cite à une date ; le dépôt, lui, a continué d'avancer.**

---

## 6. Fichiers

Répertoire : `tools/protocol-mapping/descripteur/`

| fichier | contenu |
|---|---|
| `protobuf_strict.py` | parseur protobuf strict, stdlib, schéma `descriptor.proto` (336 l.) |
| `extraire_descripteurs.py` | chasse aux descripteurs bruts, 3 chemins + gate (424 l.) |
| `noms_fuites.py` | récolte des noms fuités et baptême (451 l.) |
| `importer_mapeos.py` | import et tri des tables Jondo, confrontation (261 l.) |
| `descripteurs-3.6.10.11.jsonl` | **vide — 0 descripteur trouvé, c'est le résultat** |
| `protocole-descripteur.proto` | en-tête seul, aucun message |
| `mesure-descripteur.json` | les 3 chemins de mesure et leurs comptes |
| `classes-trahies.tsv` | 2 814 classes, leurs noms fuités, interfaces, messages touchés |
| `messages-nommes-par-fuite.tsv` | 1 664 messages avec indice, score, nom proposé, ex æquo |
| `mesure-fuites.json` | chiffres §2, dont l'état des 8 opcodes |
| `noms-jondo-fiables.tsv` | 274 lignes triées, nom PROPOSÉ vs signification MESURÉE |
| `confrontation-jondo-v4.tsv` | accord indépendant / circulaire / désaccord / nouveau |
| `mesure-mapeos.json` | chiffres §3 |

Reproduire : `python3 <script>.py --epreuve` (gate) puis `python3 <script>.py` (mesure).
Aucun `.exe` de Jondo n'a été exécuté ; aucune ligne de son C# n'a été copiée — seule la méthode
est réimplémentée, en Python stdlib. Écriture confinée à ce répertoire ; tout le reste lu seul.
