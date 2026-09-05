# RAPPORT-INDEX.md — Extracteurs opcodes/handlers déterministes (Namaste 3, étage 1)

> Brief du 04/09. But : pour chaque émulateur Dofus disponible, la table
> « message ↔ identifiant de protocole ↔ handler ↔ fichier:ligne », 0-LLM, stdlib Python
> seule. Règle du projet : le déterministe précède le travail parallèle.

## Ce qui a été mesuré AVANT d'écrire les regex (règle du projet)

Avant tout script, chaque dépôt a été sondé par `grep -c`/`grep -o` pour connaître la forme
réelle des attributs de handler et des constantes de message. Ce sondage a directement changé
la conception :

| Émulateur | Attribut handler | Message porté par | Id résolu via |
|---|---|---|---|
| Jiva 2.42 (`refs/dofus-emu-dev`) | `[WorldHandler(X.Id)]` / `[AuthHandler(X.Id)]`, empilable | l'attribut lui-même | classe référencée dans l'attribut |
| Giny.NETCore 2.68, GinyCore 2.63, OneAir 2.68-docker, Symbioz 2.38 | `[MessageHandler]` **sans argument** | le **1er paramètre** de la méthode (ARCHI-REFERENCE-GINY.md §C.2, VÉRIFIÉ) | type du 1er paramètre |
| JondoEmu 3.0 (`refs/JondoEmu`) | aucun attribut — dispatch par `if/else` sur `Op.Uri(Op.X)` | table curée `datos/anclas_3.6.10.10.tsv` | colonne `handler` de cette table (prose, pas machine-générée) |

Symbioz porte aussi `[SpellEffectHandler(...)]`/`[CustomSpellHandler...]` (effets de sort, PAS
des handlers réseau) : le regex `[MessageHandler]` exact les exclut déjà sans action
supplémentaire — mesuré, pas supposé.

**Direction** : chaque ligne de `handlers-<emu>.tsv` porte `C2S`, déduit de la **position
structurelle** (un handler serveur ne route que des messages entrants) plutôt que d'une
convention de nommage — plus fort que l'heuristique `*Request/*Message` suggérée au départ,
jamais fausse par construction.

## Chiffres mesurés par émulateur

| Émulateur | Version | Handlers extraits | Messages extraits | À-classer (handlers) |
|---|---|---|---|---|
| jiva | 2.42 | 223 | 1563 | 2 |
| giny | 2.68 | 147 | 1548 | 0 |
| ginycore | 2.63 | 126 | 1477 | 0 |
| oneair | 2.68-docker | 200 | 1548 | 0 |
| symbioz | 2.38 | 130 | 1297 | 0 |
| jondo | 3.6.10.10 | 143 | 2169 (0 imbriqué, +550 enum exclus du compte) | 41 |

Partition vérifiée sur CHAQUE run réel : `len(extraits) + len(a_classer) == candidats` mesurés
par le script lui-même (pas une valeur recopiée d'un grep externe) — vrai sur les 6 émus.

## Correctif 04/09 — la source Jondo des MESSAGES était un .proto écrit à la main

**Trouvé par l'architecte, tranché par le dump, corrigé le jour même.** La 1ère version
d'`extraire_messages.py` lisait `Jondo.Unity.Protocol/Messages/Protocol.proto` (80 blocs
`message X {}`) pour construire `messages-jondo.tsv`. Ce fichier n'est **pas** produit depuis
le client : ses noms de message sont **inventés** et ses champs sont par endroits **inversés**
(`GameMapMovementRequestMessage { repeated int32 path = 1; int64 mapId = 2 }` — l'ordre
path/mapId ne correspond à rien de mesuré). La VRAIE source, reconstruite depuis le client par
`Jondo.Unity.ProtocolBuilder`, vit dans `datos/protocolo_3.6.10.10.proto` — son propre en-tête
le dit (*« Reconstruido de las clases del propio cliente […] Los números y los tipos son los
de verdad »*) et le dump `il2cpp.cs:948379` confirme mot pour mot le message correspondant au
déplacement (`jrw { int64 fuuk = 1; repeated int32 fuul = 2; bool fuum = 3 }`).

**Même famille d'erreur que `/config/dofus3.json`** (cahier des charges §2, étage 1, séquences :
« chemin HTTP DÉDUIT — `/config/dofus3.json` était une donnée JondoEmu, 0 littéral dans notre
metadata ») : un artefact **écrit par les auteurs de JondoEmu eux-mêmes** (pas extrait du
client) a été relayé comme s'il était une source dérivée du client. JondoEmu = MANUEL (cahier
L4/corollaires) — un fichier généré par son outillage n'est pas automatiquement une preuve,
même quand il porte l'extension `.proto` et vit à côté du reste.

**Chiffres avant/après** (mesurés, pas estimés) :

| | Avant (mauvaise source) | Après (source reconstruite) |
|---|---|---|
| Fichier lu | `Jondo.Unity.Protocol/Messages/Protocol.proto` | `datos/protocolo_3.6.10.10.proto` |
| Blocs `message` top-level | 80 (dont noms inventés type `hhf`, `ilc`) | **2169** |
| Blocs imbriqués exclus | 73 | 0 (mesuré : cette source n'imbrique jamais) |
| `enum` | 27 | 550 |
| Résolution `protocol_id` | via `TypeRegistry.cs` (Register liée au mauvais fichier compilé) | l'opcode **est** le nom du bloc quand il figure dans `Op.cs` — plus de table intermédiaire |
| Messages avec `protocol_id` résolu | 50 (sur 80, doublon du chiffre handlers — confusion des deux tables) | **308/2169** (contre 309 opcodes vivants dans `Op.cs` — 1 seul écart, `joi`, une étiquette historique 3.6.4.3 sans bloc dans le protocole 3.6.10.10 reconstruit, cohérent avec le reste du corpus) |
| `nom_propose` (nouvelle colonne, depuis l'anclas tsv, provenance marquée) | absente | **99/2169** portent un nom proposé (anclas n'en documente que 99, jamais inventé au-delà) |

**Ce qui n'a pas bougé** : `handlers-jondo.tsv` (143 lignes) vient toujours d'`anclas_*.tsv`,
inchangé — l'erreur touchait uniquement `extraire_messages.py`/`messages-jondo.tsv`. Le
croisement (`croiser.py`) relie Jondo à la lignée 2.x via `handlers-jondo.tsv`, donc les 87
liens déduits sont **identiques avant/après** — vérifié en relançant `croiser.py`, pas supposé.

**Gate ajoutée (DAG J3.A pt.4, demandée par l'architecte)** : `--epreuve` vérifie maintenant
qu'aucun `.py` de `index/` ne référence plus l'ancien chemin (motif construit par
concaténation dans le script pour que la gate ne se fasse pas échouer elle-même en se citant).
`grep -c 'Jondo.Unity.Protocol/Messages/Protocol.proto' index/*.py` → **0** sur les 12 `.py`
présents dans le dossier au moment du correctif (dont plusieurs qui ne sont pas les miens,
cf. « mes trous »).

### Jondo, le détail qui compte
- 143 handlers extraits sur 184 candidats (opcodes documentés avec un handler non vide dans
  l'anclas tsv). Des 41 à-classer : **36 portent sur des opcodes absents de `Op.cs`**, et en
  regardant le contenu, ce ne sont **pas des erreurs d'extraction** — ce sont des lignes que
  l'anclas tsv documente explicitement comme appartenant à la **branche morte 3.6.4.3**
  (protocole précédent, jamais vu dans les 242 captures de 3.6.10.10 selon le texte même de la
  table). Le parseur sépare correctement le vivant du mort sans avoir été conçu pour ça
  explicitement — effet de bord positif de la validation croisée avec `Op.cs`.
- Les 5 restants sont de la vraie prose non décomposable (`"GameNodeProxy -> chest or zaap"`,
  `"FightHandler builds it as a server message"`) — correctement isolés, jamais forcés dans une
  fausse structure Classe.Méthode.
- 50/176 valeurs de la colonne `handler` suivent la forme stricte `Classe.Méthode` ; le reste
  est un nom nu (`BuildActorLeft`), une liste séparée par virgule, ou un nom avec note entre
  parenthèses (`GameNodeProxy (empty branch)`) — **mesuré avant d'écrire le parseur** (une 1ère
  lecture aurait fait tomber 72 % des lignes en à-classer si le critère avait exigé
  `Classe.Méthode` partout, exactement le piège que cette règle décrit).

## Mes propres erreurs (trouvées en cours de route, corrigées, épreuvées)

1. **Sous-comptage silencieux Jiva (208 au lieu de 232 candidats)** — ma 1ère regex
   `[WorldHandler(X.Id)]` n'acceptait aucun argument nommé supplémentaire. Mesuré après coup :
   26/232 attributs Jiva portent `ShouldBeLogged = false, IsGamePacket = false` (documentés
   dans ARCHI-REFERENCE-JIVA.md §D.2). Corrigé (regex tolère `(?:,.*)?`) ; 2 attributs
   **multi-lignes** restants (`ApproachHandler.cs:200,222`) auraient encore disparu en
   silence — ajouté un filet « forme vivante non reconnue » qui les route en à-classer au lieu
   de les perdre.
2. **9 faux candidats Jiva venaient de code MORT commenté** — un grep brut sans ancrage de
   début de ligne compte `// [WorldHandler(...)]` comme un candidat ; mon script (ancré `^\s*\[`)
   les exclut correctement. Validé en diffant les deux comptages ligne par ligne, pas supposé.
3. **`public new const ushort Id`** (23 classes Giny dérivant d'une base qui déclare déjà `Id`)
   ratait le lookup — `protocol_id` restait vide pour `PartyLeaveRequestMessage` et 22 autres.
   Corrigé dans `_lib_extract.py`.
4. **Bug de logique, pas de mesure** : `extraire_messages.py` comparait la profondeur
   d'accolades à `0` pour détecter la fin d'une classe — mais une classe C# vit toujours sous
   au moins 1 niveau `namespace X { }`, donc la condition ne se déclenchait **jamais** :
   0 message extrait sur le premier `--epreuve`. Corrigé (profondeur relative au point
   d'ouverture de la classe, pas absolue) — détecté PAR l'épreuve elle-même, exactement ce
   qu'elle est censée faire.
5. **1113 messages Jiva fantômes, dupliqués** — `Tools/ProtoDiff273/out/oracle-2.42/` est un
   **instantané figé complet** de `DofusProtocol/` (bundle de référence pour le diffeur de
   version, décrit dans ARCHI-REFERENCE-JIVA.md §F.1), pas du code vivant. Sans exclusion,
   chaque classe de message y apparaissait 2×. Pareillement, 1025 `.cs` sous `obj/`/`bin/` chez
   Symbioz (30 % du dépôt !) sont des copies de build, pas des sources. Exclus dans
   `_lib_extract.iter_cs_files` (`obj/`, `bin/`, `Tools/ProtoDiff273/out/`) — mesuré avant
   d'exclure (`find -path "*/obj/*" -name "*.cs" | wc -l`), pas décidé à l'aveugle.

Sans ces 5 corrections, la table aurait été soit incomplète en silence (1, 3, 4), soit gonflée
de faux positifs (2, 5) — les deux sont pires qu'un chiffre honnêtement bas.

## `--epreuve` — résultat sur les 6 émus × 2 scripts

`extraire_handlers.py --epreuve` et `extraire_messages.py --epreuve` : **12/12 PASS**
(rejeu byte-identique sha256 sur 2 passes + sabotage conforme/cassé/doublon + assertion de
partition `len(extraits)+len(a_classer)==candidats`). Détail par émulateur disponible en
relançant les commandes (aucune sortie fichier — tout se passe dans un `tempfile.TemporaryDirectory`
jeté après coup).

## Croisement (`croiser.py`, jointure par NOM — jamais par id numérique)

Justification de la jointure par nom, pas par id : Jiva documente lui-même (ProtoDiff273,
ARCHI-REFERENCE-JIVA.md §F.1) que **868/872 classes communes changent d'id entre 2.42 et
2.73** — l'id est renuméroté à chaque version, le nom seul survit. Chaque arête du croisement
est donc **DÉDUITE**, pas VÉRIFIÉE champ par champ.

- 1807 noms de message distincts sur la lignée 2.x (jiva/giny/ginycore/oneair/symbioz).
- **INVARIANT** (présent dans les 5) : 1073. **PARTIEL** : 573. **DIVERGENT** (1 seul ému) : 161.
- 87 liens JondoEmu → lignée 2.x déduits par similarité de nom sémantique (`difflib`,
  seuil 0,55) — dont une large majorité à score **1.00** (nom proposé par l'anclas tsv
  identique caractère pour caractère au nom de classe 2.x, ex. `kra`↔`AuthenticationTicketAcceptedMessage`,
  `kqz`↔`AuthenticationTicketMessage`), un signal fort que le documentaliste Jondo a
  délibérément repris la nomenclature Ankama/2.x connue plutôt que d'inventer.

### 5 premiers invariants (triés par couverture handler, pas alphabétique)
`AdminQuietCommandMessage`, `AuthenticationTicketMessage`, `BasicPingMessage`,
`ChangeMapMessage`, `CharacterCreationRequestMessage` — les 5 ont un handler câblé dans les
**5** émus 2.x. (Le tri alphabétique brut aurait donné 20 classes `Abstract*` sans aucun
handler direct — trié différemment pour être utile en premier, pas pour flatter le chiffre.)

### 5 premiers divergents (avec handler cohérent — présence ET handler dans le MÊME ému, donc
actifs pas juste déclarés — filtré explicitement, cf. piège ci-dessous)
`BanRequestMessage` (symbioz seul), `ClearIdentificationMessage` (jiva seul — étonnant, c'est
un message d'auth basique ; probablement renommé ailleurs, PAS vérifié, cf. trous),
`ExchangeHandleMountsStableMessage` (symbioz), `OnCharacterCreationMessage` (symbioz),
`OnCharacterDeletionMessage` (symbioz).

**Piège trouvé en relisant ma propre sortie avant de la citer** : un premier passage avait
retenu `GuildInvitationByNameMessage`/`InventoryPresetItemUpdateRequestMessage`
(`presence_2x=symbioz` mais `handler_2x=jiva`) — pas un vrai croisement : ce sont 2 des 8
handlers Jiva dont la classe de message ne vit QUE dans l'oracle figé exclu (cf. « mes
trous »), donc `messages-jiva.tsv` ne la porte plus mais `handlers-jiva.tsv` si (le nom vient
de l'attribut, pas du lookup) — `presence_2x` et `handler_2x` divergent sur l'ému. Un lecteur
pressé du TSV brut prendrait ça pour un lien réel ; filtré ici après vérification `presence==handler`.

## Ce qu'une extraction automatisée NE POURRA PAS déduire de ces tables

1. **La SÉMANTIQUE des champs** — ces tables donnent `nom:type` par position, jamais ce que le
   champ *signifie* dans le jeu (un `int32 f1` de Jondo n'est pas plus parlant qu'un
   `public int truc` de Jiva sans lire le corps du handler).
2. **L'ordre et les branches d'une séquence** — le cahier (§4) demande « déclencheur » et
   « réponse attendue, dans quel ordre » : ça vit dans le CORPS des handlers, jamais dans une
   signature ou un attribut. Ces tables disent QUI répond à QUOI, pas QUAND ni DANS QUEL ORDRE.
3. **Pourquoi `ClearIdentificationMessage` est DIVERGENT** (jiva seul) alors que c'est un
   message d'authentification basique qu'on attendrait invariant — la lecture doit vérifier
   si Giny/Symbioz/etc. le nomment autrement (renommage réel) ou ne l'implémentent
   simplement pas (message non supporté). Le croisement voit le SYMPTÔME, pas la CAUSE.
4. **Les 573 PARTIEL** — présents dans 2 à 4 émus sur 5 : c'est la zone la plus intéressante
   pour comprendre CE QUI a divergé entre versions/forks, et ces tables ne disent que le
   COMPTE, jamais LA RAISON (fonctionnalité ajoutée après 2.42 ? retirée par tel fork ? bug de
   nommage ?).
5. **Le lien Jondo à score < 1.00** (parmi les 87) — un score de similarité n'est JAMAIS une
   preuve (cf. règle L2, `internal/GRAPHE-NAMASTE3-REPONSE-20260904.md` §piège embeddings) : chaque
   lien à score < 1.00 doit être relu à la main avant d'être marqué VÉRIFIÉ.
6. **Les 8 handlers Jiva à `protocol_id` vide** (`SpellModifyRequestMessage`,
   `StartupActionsObjetAttributionMessage`, etc.) — leur classe de message n'existe QUE dans
   l'instantané figé `Tools/ProtoDiff273/out/oracle-2.42/`, jamais dans le `DofusProtocol/`
   vivant. Trace probable d'un renommage/retrait pendant le portage 2.73 en cours dans ce
   dépôt — **DÉDUIT**, pas vérifié : demande une lecture du diff de portage pour confirmer.

## Mes trous (transparence, pas caché)

- **Jondo n'a pas de cross-check code↔table** : `handlers-jondo.tsv` vient de la table curée
  `anclas_3.6.10.10.tsv` (elle-même sourcée "code + 242 captures" par son propre en-tête), pas
  d'un grep frais du dispatch `if/else` de `GameNodeProxy.cs` et consorts (92+64 mentions
  `Op.Uri(Op.X)`/littéral trouvées, mesuré, mais l'appariement fiable opcode→appel de handler
  dans un if/else-if imbriqué sur ~1000 lignes est fragile à faire dans le temps imparti — j'ai
  choisi de faire confiance à la table déjà curée plutôt que de fabriquer un appariement
  heuristique risqué. Provenance clairement différente des 5 autres émus, dit ici, pas caché).
- **Types génériques multi-mots** (`Dictionary<int, string>`) : absents du compte de champs
  (0 occurrence mesurée dans les Messages/ scannés, donc sans impact réel, mais le regex ne
  les gérerait pas s'ils apparaissaient ailleurs).
- **Classes de message imbriquées dans une autre classe de message** : non observées dans les
  5 dépôts C# (classes de message = feuilles), donc jamais testées ; le parseur les ignorerait
  silencieusement si elles existaient (limite documentée dans le docstring du script, pas dans
  ce rapport seul).
- **7 scripts qui ne sont pas les miens** sont apparus dans ce même répertoire `index/` pendant
  mon travail : `extraire_protocole_otomai.py`, `extraire_protocole_gatherer.py`,
  `extraire_protocole_luaxy.py`, `extraire_protocole_deobfs.py`, `extraire_opcodes_sniffer.py`,
  `comparer_instruments.py`, `comparer_stabilite_builds.py`, `_lib_proto3.py` — manifestement le
  DAG J3.A piloté par l'architecte, avec plusieurs instruments Jondo/otomai en parallèle du
  mien. Aucune collision de nom de fichier avec mes sorties (`handlers-*`/`messages-*`/
  `a-classer-*`/`croisement.tsv` sont les miens seuls), donc rien cassé, mais mon `croiser.py`
  n'intègre aucun de ces instruments tiers — hors périmètre, à recouper plus tard si un
  croisement à N instruments est voulu.

## Fichiers produits (`index/`)
`_lib_extract.py`, `extraire_handlers.py`, `extraire_messages.py`, `croiser.py`,
`handlers-{jiva,giny,ginycore,oneair,symbioz,jondo}.tsv`,
`messages-{jiva,giny,ginycore,oneair,symbioz,jondo}.tsv`,
`a-classer-{jiva,giny,ginycore,oneair,symbioz,jondo}.tsv`,
`CROISEMENT-OPCODES.md`, `croisement.tsv`, ce fichier.
