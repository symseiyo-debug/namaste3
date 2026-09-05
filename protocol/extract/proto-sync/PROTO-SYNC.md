# PROTO-SYNC — régénérer le protocole 3.x et sa table de dispatch, par build

> Maillon **A6** de `../chaine/CHAINE.md`, qui le déclarait **MANQUANT**. Cahier : étage 4,
> lois **L6** (« Dofus 3 est dynamique ») et **L7** (« l'analyse dynamique est la voie du debug »).
> Parole des devs de la communauté, relayée le 04/09 : *« l'analyse statique, c'est
> vraiment la cible si tu veux pouvoir upgrader sans problème, notamment dans les handlers »*.
>
> **Ce que ce maillon retourne** : l'opcode 3 lettres n'est plus quelque part dans le code,
> il est **uniquement** dans une table générée. Les handlers sont écrits contre le **nom
> sémantique**. À la build suivante, on régénère ; on ne réécrit rien.

---

## 1. Régénérer pour une nouvelle build — trois commandes

```bash
cd protocol/extract/proto-sync
D=../../internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs      # le dump de LA build

python3 generer_proto.py    --dump $D --build 3.6.10.11 --out ./out --verifier
python3 generer_dispatch.py --dump $D --build 3.6.10.11 --out ./out --verifier
python3 gate-proto-sync.py  --out ./out --build 3.6.10.11 --epreuve
```

Sorties dans `out/` : `protocole-<build>.proto`, `protocole-<build>.mesures.json`,
`dispatch-<build>.json`, `dispatch-<build>.cs`.
Durées **mesurées** sur ce VPS, dump de 57 Mo / 1 081 734 lignes, fichiers en cache :

| commande | durée |
|---|---|
| `generer_proto.py --verifier` | 10,1 s |
| `generer_dispatch.py --verifier` | 9,2 s |
| `gate-proto-sync.py --epreuve` | 16,3 s |

Ajouter `--horodatage <ISO>` aux deux générateurs pour un rejeu **byte-identique** ; sans lui,
l'en-tête porte l'heure courante et deux rejeux diffèrent forcément. La gate le passe elle-même.

**Ensuite**, `diff_builds.py` (maillon D, `../chaine/`) compare build N et N+1 par natures de
dette — `RENOMME`, `RENUMEROTE`, `RESTRUCTURE`, `CHAMP_AJOUTE`, `TYPE_CHANGE`… Il apparie sur la
**signature structurelle** et **refuse d'apparier** une signature dupliquée. C'est là que le
re-brassage d'Ankama devient une liste d'écarts nommés au lieu d'une panne.

---

## 2. Ce qui est VÉRIFIÉ, ce qui est DÉDUIT

**VÉRIFIÉ — lu dans NOTRE dump, avec `il2cpp.cs:ligne` sur chaque message et chaque champ :**

| fait | mesure |
|---|---|
| messages protobuf des 2 assemblies du protocole | **2 206** (Game.dll 2 169 · Connection.dll 37) |
| champs | **6 278** |
| énumérations du protocole / valeurs | **451** / **2 391** |
| `oneof` / membres de `oneof` | **118** / **375** |
| `repeated` · `map` · `optional` (présence explicite) | **807** · **167** · **348** |
| messages de tête (porteurs d'un opcode) · imbriqués | **1 629** · **577** |

La **forme** est vérifiée : quels messages existent, quel numéro porte quel champ, quel type,
quelle imbrication, quel `oneof`. Elle est lue deux fois par deux chemins différents (§4).

**DÉDUIT, et pourquoi ça ne peut pas être mieux aujourd'hui :**

1. **Les noms sémantiques.** Aucun n'est lisible dans notre binaire : le matcher v3 a mesuré
   **0/2206** classes obfusquées avec un porteur en clair (`../../tools/protocol-mapping/matcher/RAPPORT-MATCHER-V3.md` §2).
   Tout nom vient d'un tiers, porte sa provenance et son statut, et n'apparaît **jamais comme
   identifiant** dans le `.proto` — seulement en commentaire.
2. **`int32` contre `sint32` / `sfixed32`.** Le C# généré compile les trois vers `int` : le type
   de **fil** exact n'est pas récupérable du dump. Jondo fait le même choix. Ça ne se prouve que
   par une capture (chaîne L7). Même remarque pour `int64` et `uint32`.
3. **Le nom d'un `oneof`** est le token du champ de stockage C# (ex. `ebfz`), pas le nom proto
   d'origine, qui n'existe nulle part dans le binaire.

### Le vocabulaire des statuts — dit une fois, précisément

`statut` d'une entrée porte sur le **NOM**, jamais sur la structure (toujours VÉRIFIÉE) :

| statut | ce qu'il dit exactement | compte |
|---|---|---|
| `VERIFIE` | nom **attesté par capture d'un tiers** — JondoEmu, 242 captures sur la même build. **Pas encore par une capture à nous.** | **99** |
| `DEDUIT` | nom proposé par appariement **structurel** (matcher v3) | **67** |
| `SANS_NOM` | aucun nom ; à obtenir par capture (chaîne L7) | **1 463** |

`166 / 1629 = 10,19 %` des opcodes ont un nom sémantique. Chaque entrée porte aussi
`statut_detail`, qui écrit la phrase entière : *« un VÉRIFIÉ nu s'élargit tout seul avec le temps. »*

**Directions** : 45 C2S, 86 S2C, 1 498 inconnues. La direction est lue sur l'arête
(`anclas`, `handlers-jondo.tsv`), **jamais inférée d'un nom**.

### Hiérarchie des sources de noms, et les conflits qu'elle ne cache pas

Trois niveaux, dans cet ordre : `jondo-anclas` (capture) > `matcher-v3` (structure) >
`messages-jondo`. C'est **exactement** la hiérarchie que l'auteur du matcher demandait sans avoir
eu le temps de la construire (RAPPORT-MATCHER-V3.md §3 et §5).

Elle règle d'elle-même le cas qu'il avait signalé nommément : **`jtg` → `GiftsListMessage`**
reprend le nom (attesté par capture) et **`kmz`** le perd, avec la raison écrite dans son entrée.

**10 collisions** de nom sémantique au total. Quand la hiérarchie départage (3 cas), le perdant
est démoté `SANS_NOM` avec sa raison. Quand elle ne départage pas (**7 cas**, deux prétendants de
même rang — `Channel`, `Character`, `EntityLook`, `FightCharacteristics`, `HouseInstance`,
`ObjectItemInventory`, `Teleporter`), **le nom est retiré aux deux**. Un nom donné au hasard à
l'un des deux serait une clé fausse à l'apparence d'une clé juste.

---

## 3. La table de dispatch — pourquoi l'opcode n'est plus dans le code

`dispatch-<build>.json` et `dispatch-<build>.cs` portent, par message :

```
opcode · type_url · token_obfusque · chemin_proto · niveau (tete|imbrique)
nom_semantique · direction · statut · statut_detail · provenance · conflits
structure { source: il2cpp.cs:ligne, typedef_index, assembly }
champs [ { num, type, nom, label, presence_explicite, cle_map, source } ]
```

Le `.cs` est une **classe de données** : deux `record` et un tableau de littéraux. Aucune logique,
aucun index construit par du code — la gate le vérifie en refusant `if`, `for`, `while`, `switch`,
`return`, `foreach`, `=>`. **L'indexation est le travail du chargeur**, au démarrage du serveur.

**La règle pour les handlers** : un handler nomme `NomSemantique` et rien d'autre. L'opcode ne
traverse jamais son code. Un opcode figé dans un handler compile, passe les tests, et devient
faux au patch suivant **sans que rien ne s'allume** — c'est le défaut exact que L6 vise.

---

## 4. Comment on sait que c'est juste — quatre mesures indépendantes

**(1) Deux chemins de lecture dans le même fichier, qui doivent tomber d'accord.**
Le numéro d'un champ vient des `const int` ; son nom et son type viennent des propriétés
publiques. Les deux populations sont comptées séparément : **6 278 == 6 278, 0 désaccord sur
2 206 messages**. La partition ferme exactement : les 386 propriétés `bool` sans setter se
répartissent en **348** vrais `optional` + **38** accesseurs de membre scalaire de `oneof`, et
les 118 propriétés de cas de `oneof` sont écartées.

**(2) Un second chemin de comptage, par expressions régulières, sans le parseur à pile** —
`compter_par_grep()`. Il compte la même population que la gate G0 (`IMessage<self>, IBufferMessage`) :
**2 206 messages, 6 278 champs**, identiques. Un compte produit deux fois par le même instrument
ne mesure que l'instrument.

**(3) protoc, le seul juge qui ne soit pas nous.**
`protoc --descriptor_set_out=/dev/null` (libprotoc 3.21.12) compile le `.proto` **sans erreur**.

**(4) Un instrument entièrement indépendant : la reconstruction de Jondo.**
Autre auteur, autre méthode, même build. Sur les **2 169** messages de Game.dll :

| mesure | résultat |
|---|---|
| noms de messages | **2 169 communs, 0 chez l'un seul** |
| messages ayant le même nombre de champs | **2 169 / 2 169** |
| messages **sans** `map`, `optional` ni `oneof` (là où sa méthode tient) | **1 716** |
| champs identiques (nom **et** type) sur ces 1 716 | **4 058 / 4 058 = 100,000 %** |

**Les écarts restants sont TOUS des limites de Jondo, aucun n'est un écart du lecteur** — vérifié
un par un sur les 33 cas de la population « propre » et sur les familles :
son `.proto` contient **0 `oneof`** et **0 `optional`**, et il compte les accesseurs `HasXxx` du
C# généré comme de vrais champs `bool` (767 chez lui). Exemple mesuré, `heo` : Jondo lit
`{int32, bool, int64, int32}` là où le dump dit `{int32 optional, int64, int32, map<int32,string>}`
— il invente un `bool` et perd le `map`.

**Ce que notre `.proto` porte en plus du sien** : 348 `optional`, 118 `oneof` (375 membres), et
l'imbrication réelle des 577 messages imbriqués.

---

## 5. Les pièges du dump, mesurés ici — à ne pas re-payer

1. **Un identifiant échappé échappe au regex.** `public const int @enum = 1;` (classe `jin`) :
   le décompilateur préfixe `@` sur un token qui heurte un mot-clé C#. Un motif `\w+` rend
   **6 277** champs au lieu de 6 278 — un compte plausible, faux d'un, et c'est le compte qui
   circulait. Un seul cas dans tout le dump ; il suffit.
2. **Une vraie classe protobuf s'appelle `int`** (`il2cpp.cs:895280`). Le token `int` est donc
   ambigu en position de type. Mesure décisive par un instrument indépendant : **0 champ de type
   `int`-la-classe** dans la reconstruction de Jondo (elle-même écrit `message int { int32 fqhm = 1; }`).
   On lit donc `int` comme `int32`.
3. **Le texte `namespace X` ne délimite rien** dans ce décompilateur (mesuré par le matcher v3).
   L'assembly se lit par `TypeDefIndex` contre les plages `// Image N:`, jamais par le namespace.
4. **Le conteneur `Types` de protoc est obfusqué lui aussi** (`jrt` dans `jru`). On le reconnaît
   à son attribut `[GeneratedCode("protoc", null)]` — et il faut lire la ligne **brute**, car
   dépurer les chaînes efface justement le marqueur cherché.
5. **118 énumérations du dump n'existent pas dans le protocole** : ce sont les `XxxOneofCase`
   fabriqués par le générateur C#. Règle prouvée par **égalité d'ensembles**, pas supposée :
   l'ensemble des parents de ces 118 enums est **exactement** l'ensemble des 118 messages
   porteurs d'un `oneof`. Les émettre aurait ajouté 118 types qui n'existent nulle part.
6. **Un littéral de 3 minuscules est un signal faible.** 1 629 opcodes sur 17 576 triplets
   possibles : ~9 % des mots de 3 lettres collisionnent. La première version du témoin (a)
   rendait 8 occurrences dont **4 sans aucun rapport** — `"meh"` (un nom d'action du bot-testeur)
   et `"len"` (une étiquette d'erreur du codec). Le témoin mesure désormais un **geste**
   (constante, `typeUrl`, affectation à un `opcode`), pas un mot, et il **prouve d'abord qu'il
   sait mordre** sur un témoin positif et se taire sur un témoin négatif.

---

## 6. La gate — six témoins, refus nommés

```bash
python3 gate-proto-sync.py --out ./out --build 3.6.10.10 --epreuve
```

| | témoin | état mesuré le 05/09 |
|---|---|---|
| a | aucun opcode écrit en dur hors de la table (`etage2-socle/`, `server/`) | 🔴 **3 refus** — `type.ankama.com/jru` figé dans `codec/tests/…/NegativeTests.cs:164,181,335` |
| b | tout opcode du chemin critique présent | 🟢 **32/32** ; 24 avec nom, 29 avec direction |
| c | provenance **et** statut sur chaque entrée | 🟢 **2 206/2 206** |
| d | rejeu byte-identique (sha256) | 🟢 3 artefacts identiques sur deux exécutions |
| e | **sabotage** : renommer un token du dump change la table | 🟢 contrôle positif `{jru}`, puis `jru→zzq` ⇒ `{zzq}`, champs inchangés |
| f | **témoin négatif** : un opcode inventé est absent | 🟢 `zzq`, `zzw`, `zzx` absents des 2 206 tokens |

**Le refus (a) est un vrai défaut, pas du bruit** : ces trois `typeUrl` construisent des trames
**synthétiques**. Le test resterait **vert** avec un opcode périmé — la panne silencieuse exacte
que L6 vise. *Pour sortir* : lire `type_url` dans `dispatch-<build>.json`. C'est la zone du codec,
pas la mienne : signalé, pas corrigé (un seul écrivain par zone).

Les 8 autres collisions (`meh`, `len`, `ivx`, `jtg`, `ivi`, `jru`) sont listées **non bloquantes**
et nommées : ce sont des mots qui heurtent un token par hasard, ou des assertions sur des trames
réellement capturées.

---

## 7. Ce qui manque encore pour écrire un handler SANS aucun opcode

1. **Le chargeur, côté serveur** — `dispatch-<build>.json` lu au démarrage, indexé par
   `NomSemantique` et par `Opcode`. Il n'existe pas : `server/` ne contient aujourd'hui
   que des documents, aucun `.cs`. C'est ~50 lignes, et c'est le seul chaînon manquant côté code.
2. **Les 8 opcodes du chemin critique sans nom sémantique.** 24/32 en ont un. Tant qu'un opcode
   n'a pas de nom, son handler ne peut pas être écrit sans le nommer par son token. Ils ne
   viendront que d'une **capture** (0/2206 porteur en clair dans le statique) — c'est le brief
   de la chaîne L7 (§B de `CHAINE.md`, maillons B2/B5, tous deux **MANQUANTS**).
3. **La promotion DÉDUIT → VÉRIFIÉ par NOTRE capture.** Les 99 `VERIFIE` d'aujourd'hui reposent
   sur les captures de Jondo. Le champ `statut_detail` le dit dans chaque entrée ; il faudra une
   capture à nous pour que la phrase change.
4. **Le type de fil des entiers** (`int32` / `sint32` / `sfixed32`), non récupérable du statique.
5. **Le ping-pong lui-même reste NON MESURÉ sur 3.x** : nous n'avons qu'**une** build dumpée.
   *Débloquer* : `obtenir_build.sh il2cpp 3.6.4.3 3.6.10.11 --out ./builds --vraiment`, puis
   cette chaîne sur chacune, puis `diff_builds.py --chaine`.

### Un chiffre du cahier, affiné par un second chemin

Le cahier dit « 290/293 anclas existent comme classes dans notre dump ». Re-mesuré ici, la
population compte :

| les 293 opcodes d'`anclas_3.6.10.10.tsv` | |
|---|---|
| messages protobuf **de tête** (donc dispatchables) | **274** |
| messages protobuf **imbriqués** (pas de `typeUrl` propre) | **6** |
| présents comme **autre chose** qu'un message — 8 conteneurs `Types`, 3 enums, 2 classes | **13** |

**293/293 existent comme un type ; 280 comme un message ; 274 seulement sont dispatchables.**
Le « 290 » n'était pas faux, il comptait des **noms** là où il fallait compter des **messages** :
un conteneur `Types` ne voyage pas sur le fil.

---

## 8. Les fichiers de cette zone

| fichier | rôle | lignes |
|---|---|---|
| `_lib_dump.py` | lecture du dump : arbre des types, champs, `oneof`, résolution | 483 |
| `_lib_noms.py` | fusion des noms sémantiques par hiérarchie, conflits rendus | 244 |
| `generer_proto.py` | dump → `protocole-<build>.proto` + gate protoc | 388 |
| `generer_dispatch.py` | dump → `dispatch-<build>.json` + `.cs` + gate | 313 |
| `gate-proto-sync.py` | les 6 témoins | 427 |
| `out/` | artefacts générés — **jamais édités à la main** | — |

Les 5 fichiers sont sous le plafond de 500 lignes du projet (le plus gros, `_lib_dump.py`,
est à 483 : il faudra le scinder avant de lui ajouter quoi que ce soit).

Gate commentaires (`../gate-commentaires.py proto-sync`) : **6 VERT / 0 ROUGE**, en-têtes 6/6.
Zone à un seul écrivain. `../../tools/protocol-mapping/matcher/` est lu, **jamais écrit**.
