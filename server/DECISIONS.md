# DECISIONS — arbitrages d'architecture, étage 3

> # 🟡 v0 — À RÉVISER APRÈS LA CARTE
>
> **Sources lues** : les mêmes que `ARCHITECTURE.md` (liste en tête de ce fichier-là).
>
> **Lesquelles la carte peut rouvrir, dites d'avance.** Trois décisions reposent sur un corpus partiel
> et se rouvrent si la carte les contredit : **D-03** (deux ports — DÉDUIT, tranché par une capture),
> **D-05** (le découpage en Areas — aucun fragment ne donne le graphe Area/SubArea du 3.0), **D-16**
> (la géométrie, bloquée sur un rapatriement). Trois autres reposent sur un **manque mesuré chez
> toutes les références** et ne bougeront pas d'un fragment de plus : **D-06** (les quatre contrôles
> de déplacement), **D-07** (isolation du domaine), **D-14** (la preuve est le bot). **D-09**
> (l'autorité de forme du protocole) se **renforce** avec la carte, elle ne se rouvre pas.
>
> Une décision par entrée : ce qu'on retient, les alternatives **rejetées**, et la raison **sourcée**
> (fragment + fichier:ligne). Écrit le 2026-09-04.
> Une décision qui ne cite pas sa mesure n'est pas une décision, c'est une préférence.
> `ARCHITECTURE.md` renvoie ici par `D-nn`.

---

## D-00 — ⭐ AUCUN ÉMULATEUR EXISTANT COMME BASE DE CODE (L5)

**Décision du porteur du projet, 04/09, verbatim** : *« il faut que tu partes d'une base solide, une maison avec de
mauvaises fondations va finir par s'effondrer (**Stump = mauvaises fondations**). Et la complexité
d'un projet 3.0 est exponentielle par rapport à un projet 2.0. »*

**Retenu** — Jiva/Stump, Giny, Symbioz, Jondo, otomai sont des sources de **LECTURE**. Le serveur 3.0
est **écrit neuf**. Aucun fork, aucun portage, aucune reprise de fichier. C'est la décision dont
toutes les autres découlent : elle est ici en tête parce qu'elle se prend **une fois** et qu'aucune
échéance ne doit pouvoir la rouvrir.

**Alternatives rejetées** — forker Stump/Jiva et « monter » le protocole 3.0 dessus ; forker Giny pour
son `ProtocolBuilder` ; partir de Jondo, déjà en 3.0. Les trois sont tentantes parce qu'elles
donnent l'illusion d'un départ lancé.

### Les fondations qu'on REFUSE d'hériter, chacune mesurée

| Ce qu'on refuse | Mesure | Source |
|---|---|---|
| **Anti-triche écrit puis commenté** | `//Verify Hack` : le contrôle de la cellule de départ est désactivé dans du code actif | Jiva `ContextActor.cs:203-204` (§B.4, §E.1) |
| **Sécurité laissée en commentaire** | second bloc, anti-bot IP, inactif au milieu du code vivant | Jiva `ConnectionHandler.cs:166-194` (§E.6) |
| **Fichiers « dieu »** | `Character.cs` **4637** lignes, `Fight.cs` 2989, `FightActor.cs` 2368, `Map.cs` 2095 · côté Giny `Fighter.cs` **2721**, `Character.cs` 1990 | Jiva §E.5, Giny §F.3 |
| **Protocole importé par le cœur** | **414 fichiers sur 571 = 72,5 %** de `Giny.World/` importent `Giny.Protocol` | Giny §G.3 |
| **Une garantie de concurrence FAUSSE, affirmée** | `[Annotation("thread safe..")]` sur un `List<T>` réassigné entier pendant que d'autres threads l'énumèrent | Giny `MapInstance.cs:45-48,121-131,334-337` (§B.2) |
| **Un défaut par défaut qui tue le process** | `ScheduledAutomaticShutdown = true`, 6 h, hérité par Auth **et** World | Jiva `ServerBase.cs:42,48,465-470` (§E.2) |
| **Une fragilité d'échelle câblée** | `Listen(1)` en backlog TCP face à `ServersMaxCount = 10` | Jiva `IPCHost.cs:127` et `:36` (§E.3) |
| **Du code de framing jamais relu** | un seul fichier sur 2881 écrit en style décompilé (`goto label_`, `num1`…`num7`), avec un `ReadUInt()` inconditionnel qui jette 4 octets | Giny `MessagePart.cs:103-104` (§C.1) |
| **Un lookup O(n) sur un dictionnaire** | `FirstOrDefault(x => x.Key == id)` par paquet reçu, sur ~1182 types | Giny §C.2 |
| **Zéro test** | 0 fichier de test, 0 `.csproj` référençant xUnit/NUnit/MSTest | Giny §G.1 |
| **Un oracle figé DANS le dépôt** | `Tools/ProtoDiff273/out/oracle-2.42/` = **1 761 `.cs`** d'un autre build vivant dans l'arbre source, qu'il a fallu exclure par règle pour compter juste | cahier §1, ligne Jiva |
| **Un outil déclaré mais jamais branché** | `AnnotationsManager.Analyse` n'est appelé dans aucun `Program.cs` | Giny §G.2 |

**Raison, au-delà de la liste** — ces douze points ne sont pas des bugs isolés qu'on corrigerait après
un fork. Ce sont des **fondations** : la concurrence, la frontière protocole/domaine, le découpage des
fichiers, la place de la sécurité, la preuve. Chacun est un choix pris tôt et devenu structurel. Un
fork les hérite tous **et** hérite du coût de les défaire, dans un code qu'on n'a pas écrit, sur un
protocole qui a **doublé** de taille (2169 messages contre ~1030) et dont les noms changent à chaque
build (L6). C'est précisément l'addition que L5 nomme exponentielle.

**Ce que la lecture nous donne quand même, et c'est beaucoup** — l'architecture (l'Area de Jiva), les
patrons de qualité (dispatch dérivé du type chez Giny, dette interrogeable, modules), le vocabulaire
de portage (les 5 natures de dette), la méthode de déobfuscation (le matcher de Jondo), et surtout
**la carte des pièges** : chaque ligne du tableau ci-dessus est une erreur qu'on ne paiera pas.
*On hérite des contraintes, pas des solutions* — et jamais du code.

**Portée sous L4** — cette décision se combine avec « deux builds, deux mondes » : même si l'on
voulait hériter, **rien du 2.x ne se porte structurellement**. Ce qui traverse est la règle du jeu, et
chaque traversée est un `DÉDUIT` à vérifier contre le client 3.0.

---

## D-01 — Deux processus : `namaste3-connect` et `namaste3-world`

**Retenu** — un processus pour la phase de connexion nue, un pour le jeu.

**Alternatives rejetées**
- *Un seul processus multiplexant les deux protocoles sur un port* (patron Jondo). Rejeté : la
  détection de phase se fait chez lui par recherche de la sous-chaîne `type.ankama.com` dans le
  **premier frame** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:283-286`, citant
  `GameServerProxy.cs:71-104`). Deux protocoles incompatibles partagent alors le même chemin de code
  et le même état, discriminés par une heuristique de contenu.
- *Un processus par map ou par Area.* Rejeté : aucune référence ne le fait, et le handoff inter-Area
  deviendrait un problème réseau au lieu d'un passage de message en mémoire.

**Raison** — la séparation n'est pas un choix, c'est une **contrainte du protocole** : le client ferme
la connexion et en rouvre une avec le ticket (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:344-357`,
`BuildServerSelected` → « le client ferme cette connexion et en ouvre une nouvelle sur `host:port[0]`,
présentant `ticket` dans `kqz` »). Les deux références 2.x séparent aussi (Jiva `AuthServer`/
`WorldServer`, `ARCHI-REFERENCE-JIVA.md` §A.1 ; Giny `Giny.Auth`/`Giny.World`,
`ARCHI-REFERENCE-GINY.md` §G.3). C'est un **INVARIANT** au sens du graphe comparatif.

---

## D-02 — Aucun protocole IPC : Postgres est la frontière entre les deux processus

**Retenu** — la validation de ticket est un `UPDATE … WHERE consumed_at IS NULL … RETURNING` ; l'état
du monde est une ligne de table rafraîchie toutes les 10 s. **Zéro socket applicatif entre nos deux
processus.**

**Alternatives rejetées**
- *RPC corrélé par GUID sur socket TCP dédié* (Jiva, `ARCHI-REFERENCE-JIVA.md` §A.2, `IPCEntity.cs:40-131`,
  `IPCMessage.cs:22-31`).
- *RPC corrélé par `short requestId` incrémental* (Giny, `ARCHI-REFERENCE-GINY.md` §F.2,
  `IPCMessage.cs:13,18`, `IPCRequestManager.PopNextRequestId()` `:31-35`).

**Raison** — quatre défauts mesurés sont attachés à ce canal chez les références, pour une seule
question du chemin critique (« ce ticket est-il valide ? ») :

| Défaut mesuré | Source |
|---|---|
| backlog TCP `Listen(1)` alors que `ServersMaxCount = 10` | Jiva §E.3, `IPCHost.cs:127` et `:36` |
| machine à états de framing **dupliquée** aux deux bouts | Jiva §E.4, `IPCAccessor.cs:355-414` vs `IPCClient.cs:199-246` |
| un refus IPC **tue le process World entier** | Jiva §A.3 point 4, `IPCAccessor.cs:215-222` |
| verrou redondant sur `ConcurrentDictionary` déjà thread-safe | Giny §F.2, `:22-29,38-49` |
| `short` plafonné à 32 767 requêtes en vol, comportement au retour à zéro **jamais lu** | Giny §F.2 |

Et le besoin fonctionnel est déjà couvert : Jondo décrit `SessionRegistry.Redeem` comme **atomique et
à usage unique** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:377-379`), Jiva retire le ticket du cache dès
consommation (`ARCHI-REFERENCE-JIVA.md` §A.4 point 5, `IPCOperations.cs:114-128`). Une instruction SQL
porte l'atomicité, l'unicité et l'expiration ensemble.

**Ce qu'on paie, dit franchement** — Postgres devient une dépendance dure du login (elle l'était déjà
pour les comptes) ; le heartbeat a 10 s de latence (l'intervalle de Jiva lui-même, §A.3 point 5). Si
un jour plusieurs mondes doivent se coordonner en temps réel, cette décision se rouvre.

**Rejeté explicitement** — le cache **mémoire** de tickets de Jiva (`FindCachedAccountByTicket`) : son
propre fragment signale qu'il interdit tout Auth multi-instance et ne survit pas à un redémarrage
(`ARCHI-REFERENCE-JIVA.md` §A.4, paragraphe DÉDUIT).

---

## D-03 — Deux ports : `:5555` connexion, `:5556` jeu

**Retenu** — le `authResult` annonce `ports = [5556]` ; le jeu écoute ailleurs que la connexion.

**Alternative rejetée** — le port unique de Jondo. Chez lui `BuildServerSelected` renvoie **toujours**
`Program.gamePort` = 5555, et son 5556 est déclaré **mort** : « le client ne recontacte jamais 5556 »
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:29`).

**Raison** — le client suit l'adresse qu'on lui donne ; rien dans les fragments ne montre une
contrainte sur le numéro. Séparer supprime la détection de phase par contenu (D-01) sans rien coûter.

**Statut** — **DÉDUIT.** Comment le vérifier : gate J3.2, `netstat` sur le poste personnel doit montrer
la seconde connexion vers **5556**. Si le client recontacte 5555 en ignorant `ports`, on replie sur le
multiplexage — un paramètre de configuration, pas une réécriture.

---

## D-04 — Le garde d'Area est un **type**, pas un `if`

**Retenu** — `AreaTick`, `ref struct` sans constructeur public, exigé en premier paramètre de toute
mutation du domaine. Une mutation hors boucle d'Area est une **erreur de compilation**.

**Alternatives rejetées**
- *Vérification runtime du thread courant* (Jiva : `IsInContext`, comparaison de `ManagedThreadId`,
  `ARCHI-REFERENCE-JIVA.md` §B.1, `Area.cs:192-219`). Rejeté : le garde n'est actif que si l'auteur
  pense à l'appeler ; un handler qui oublie `ExecuteInContext` mute depuis le thread réseau et rien
  ne le dit.
- *Collections concurrentes sans unité de sérialisation* (Giny, §B.1). Rejeté fermement, cf. D-05.

**Raison** — l'écart entre les deux références est mesuré et instructif. Jiva a le bon modèle avec un
garde faillible ; Giny a un `[Annotation("thread safe..")]` posé sur un `List<MapElement>` qui ne
l'est pas, réassigné entier (`Reload()`, `:121-131`) pendant que d'autres threads l'énumèrent
(`GetElements<T>()`, `:334-337`) — `ARCHI-REFERENCE-GINY.md` §B.2 conclut que c'est **pire** qu'une
vérification commentée : « Giny affirme activement une garantie fausse ; un lecteur pressé fait
confiance au commentaire et ne revérifie pas le type. » Un garde qui dépend de la vigilance de son
lecteur est déjà perdu.

---

## D-05 — L'Area (la région) est l'unité de sérialisation, pas la map ni le client

**Retenu** — une tâche et une file par Area active ; démarrage à l'entrée du premier personnage, arrêt
à la sortie du dernier.

**Alternatives rejetées**
- *Par map* : plus de parallélisme, mais un déplacement entre deux maps d'une même zone devient
  inter-thread (`ARCHI-REFERENCE-JIVA.md` §B.1, invariant explicite du fragment).
- *Global* : plus simple, un seul cœur logique pour tout le monde (idem).
- *Aucune* (Giny §B.1) : `ConcurrentDictionary` pour les entités, `System.Timers.Timer` par map sur le
  ThreadPool, aucune file, aucun `ExecuteInContext` (0 occurrence de `lock (`, `Interlocked`,
  `BlockingCollection` dans `MapInstance.cs`).

**Raison** — Jiva a trouvé le point d'équilibre : une Area entière voit un état cohérent sans lock
explicite entre ses maps, et une région peu fréquentée ne coûte pas un thread permanent
(`Area.cs:480-504`). Le fragment pose lui-même la règle : reproduire ce découpage **ou justifier
explicitement un autre**. C'est ce que fait cette entrée.

**Ouvert** — le découpage Area/SubArea du 3.0 est **DÉDUIT** ; aucun fragment ne le donne. Seul fait
mesuré : `jss` porte `f6: subAreaId` et un zéro y fait planter le client
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:641-643`). Commandé en J3.B. MVP : une Area, une map.

---

## D-06 — Anti-triche déplacement : quatre contrôles, rendus obligatoires par le type `Path`

**Retenu** — `Path` sans constructeur accessible ; unique fabrique `TryBuildValidated(map, from,
budget, keys, …)` qui vérifie (1) le mapId contre la session, (2) la cellule de départ, (3) l'étendue
et la marchabilité de chaque cellule, (4) la contiguïté et un budget de pas.

**Alternatives rejetées**
- *Valider la marchabilité seulement* (Jiva) : `Path.BuildFromCompressedPath` rejette tout le chemin
  si une cellule est hors limites ou non marchable (`ARCHI-REFERENCE-JIVA.md` §B.4,
  `Path.cs:185-200`), **mais** le contrôle de la cellule de départ est écrit puis **commenté** —
  `ContextActor.cs:203-204`, `//Verify Hack` — et ni la contiguïté ni un budget de points de
  mouvement ne sont vérifiés.
- *Valider la cellule de départ seulement* (Giny) : `Character.MoveOnMap` vérifie `clientCellId ==
  CellId` (`ARCHI-REFERENCE-GINY.md` §C.3, `Character.cs:1044-1046`) et **aucune marchabilité** —
  `PathReader.cs` lu en entier, 121 lignes, aucun `IsCellWalkable`, aucune reconstruction A*.
- *Ignorer en silence une incohérence* (Jondo) : un `jrw` dont le mapId ne correspond pas à la session
  est **ignoré sans réponse** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:679-682`). Rejeté : le joueur reste
  figé sans savoir pourquoi, et l'exploitation ne laisse aucune trace.

**Raison** — les deux fragments concluent la même chose indépendamment : *« Aucun des deux émulateurs
de référence n'a le contrôle complet »* (`ARCHI-REFERENCE-GINY.md` §C.3) ; *« à concevoir avec ce
garde-fou PRÉSENT et actif dès le départ dans le serveur neuf, pas ajouté après coup »*
(`ARCHI-REFERENCE-JIVA.md` §E.1). « Par construction » n'est pas une intention : c'est l'absence de
constructeur. Il n'existe pas, dans le programme, de `Path` non validé qu'un handler pourrait
appliquer.

**Ce qu'on hérite sans discuter** — l'encodage de la clé, `(facing << 12) | cell` : invariant mesuré
sur trois émulateurs et deux générations (Jiva §B.4 ; Giny `PathReader.cs:14-21`, `cell & 4095`,
`>> 12` ; 3.0 `jrw f2`, `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:677`).

---

## D-07 — Le domaine n'importe jamais le protocole (gate à 0 fichier)

**Retenu** — `Namaste3.World` avec **zéro** `using Namaste3.Protocol`, mesuré par grep à chaque gate.
Les handlers traduisent message → commande de domaine et événement → message.

**Alternative rejetée** — laisser le domaine manipuler les types de message, ce que font les deux
références.

**Raison, chiffrée** — `grep -rl "using Giny.Protocol"` sur `Servers/Giny.World/` : **414 fichiers sur
571, soit 72,5 %** ; côté `Giny.Auth`, **13 sur 18, 72,2 %** (`ARCHI-REFERENCE-GINY.md` §G.3, « c'est
une mesure, pas une estimation »). Un rebrassage d'Ankama touche alors les trois quarts du serveur.
Le cahier fait explicitement de ce ratio le contre-exemple à ne pas reproduire.

---

## D-08 — Le protocole est **régénéré**, et un seul fichier nomme les opcodes littéraux

**Retenu** — génération complète depuis notre dump à chaque version ; les handlers référencent des
constantes sémantiques ; `protocol/binding-<version>.tsv` est le seul fichier qui écrit `"kvw"`.

**Alternatives rejetées**
- *Écrire les opcodes en dur dans les handlers* : un patch les toucherait tous.
- *Apparier les versions par identifiant numérique / opcode* : mesuré faux. En 2.x, **868 classes sur
  872 communes changent d'identifiant** entre 2.42 et 2.73, soit **99,5 %** ; seules 4 le gardent
  (`ARCHI-REFERENCE-JIVA.md` §F.1, `pump-2.42/README.md:42-54`). En 3.0, le matcher structurel de
  Jondo ne réapparie que **245 messages sur 2169 (11,3 %)** entre 3.6.4.3 et 3.6.10.10
  (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:830-833`).

**Raison** — le principe « régénérer entièrement > corriger à la main » n'est pas une mode : c'est une
constante de la lignée **Symbioz 2018 → Giny 2026**, même auteur, huit ans d'écart, mesurée des deux
côtés (`ARCHI-REFERENCE-GINY.md` §A.3 et §A.4 : chemins d'entrée identiques au caractère près,
`Directory.Delete(path, true)` avant régénération dès 2018). Ce qui **ne** se transpose pas est
l'outil : Giny suppose une source AS3 lisible, nous avons un binaire — donc matcher structurel + les
5 natures de dette de Jiva (`absent` / `renommé` / `neutralisé` / `mal rempli` / `non routé`, §F.1)
pour le diff inter-versions.

---

## D-09 — L'autorité de forme du protocole : notre dump, puis le `.proto` reconstruit. **Jamais** le `.proto` écrit à la main de Jondo

**Retenu** — hiérarchie de sources : (1) notre dump du client, (2)
`refs/JondoEmu/datos/protocolo_3.6.10.10.proto` (2169 messages, reconstruit du client), (3) rien
d'autre. `Jondo.Unity.Protocol/Messages/Protocol.proto` est **exclu**.

**Alternative rejetée** — la table `tools/protocol-mapping/index/messages-jondo.tsv` telle qu'elle existe
aujourd'hui, et le fichier dont elle est tirée.

**Raison — mesurée ce tour, c'est la trouvaille la plus dangereuse du document.** JondoEmu contient
deux `.proto` qui décrivent les mêmes opcodes et **se contredisent** :

| Opcode | `datos/protocolo_3.6.10.10.proto` (**2169** messages) | `Jondo.Unity.Protocol/Messages/Protocol.proto` (**80** messages) |
|---|---|---|
| déplacement | `jrw { int64 fuuk=1; repeated int32 fuul=2; bool fuum=3 }` → **f1 = mapId, f2 = chemin** (`:10480-10484`) | `GameMapMovementRequestMessage { repeated int32 path=1; int64 mapId=2; … }` → **f1 = chemin, f2 = mapId** (`:7-12`) |
| `ksl` | `{ ksj fyyn = 1 }`, un enum seul (`:13173-13175`) | `{ int64 fzek=1; ksl.ksk.ksj fzel=2 }` (`:406-420`) |
| `kqp` | `{ int32 fyrt=1; int32 fyru=2 }` (`:13005-13008`) | 10 champs `string/string/bytes/int64/bool/…` (`:377-388`) |

**Les numéros de champ du déplacement sont inversés.** Les deux formes sont des varints : un handler
qui suit le mauvais fichier compile, décode sans erreur, et lit le chemin comme un mapId. C'est
exactement le motif « le type est bon, la source est fausse ».

Et notre propre table déterministe est du mauvais côté : `extraire_messages.py:137` pointe
`Jondo.Unity.Protocol/Messages/Protocol.proto`. Sa première ligne étiquette
`GameMapMovementRequestMessage` avec l'opcode **`ise`**, alors que `ise` est dans le vrai `.proto` un
message à 5 champs sans rapport (`:8013-8019`) et que le déplacement est `jrw` partout ailleurs
(`handlers-jondo.tsv:38`, anclas, fragment §5.3).

**Ce qui rend la hiérarchie crédible** — le `.proto` reconstruit compte **2169** messages
(`grep -c "^message "`, mesuré) et notre dump compte **2169** classes `IBufferMessage` dans
`Ankama.Dofus.Protocol.Game.dll` (`internal/GATE-G0-RAPPORT.md:19`). Une donnée décodée et un code
déclaré, deux chemins d'extraction indépendants, le même nombre. Le fichier à 80 messages n'a aucune
corroboration de ce genre.

---

## D-10 — Le handler dérive son opcode du **type de son paramètre**

**Retenu** — `[Handler]` sans argument ; l'opcode vient de `typeof(TMessage)` ; table `TryGetValue`
en O(1).

**Alternative rejetée** — écrire l'identifiant dans l'attribut (`[WorldHandler(id)]` chez Jiva,
`ARCHI-REFERENCE-JIVA.md` §D point 1).

**Raison** — le fragment Giny le dit et le mesure : dériver l'identifiant du type du premier paramètre
**élimine une classe d'erreurs entière** (écrire le mauvais identifiant dans l'attribut) —
`ARCHI-REFERENCE-GINY.md` §C.2, `ProtocolMessageManager.cs:22,76-101`, « patron à adopter tel quel :
le handler ne peut pas mentir sur l'opcode qu'il traite ». **On n'adopte pas son défaut voisin** :
`Handlers.FirstOrDefault(x => x.Key == message.MessageId)` (`:170`), un parcours **O(n)** sur un
dictionnaire, par paquet reçu, sur ~1182 types de message.

On garde en revanche de Jiva la **garde login-requis pilotée par l'attribut** (`ShouldBeLogged`,
§D point 2) — avec une valeur par défaut **fermée**.

---

## D-11 — La dette est un attribut interrogeable, et il est **branché**

**Retenu** — `[Dette("…")]` posable sur classe/méthode/champ, énuméré par réflexion **dans le chemin
de démarrage**, et dont l'absence d'appel est une gate.

**Alternatives rejetées**
- *Tags en commentaire libre* (Jiva : `FIX-273` / `MECANIQUE-273` / `DETTE-273` / `DEAD-273`,
  `ARCHI-REFERENCE-JIVA.md` §F.2). Le vocabulaire à 4 tags est excellent — on le garde comme
  **vocabulaire** — mais un commentaire n'est pas énumérable sans grep.
- *L'attribut de Giny tel quel* (`[Annotation]`, `ARCHI-REFERENCE-GINY.md` §G.2, 30 usages dans 20
  fichiers).

**Raison** — l'attribut bat le commentaire : « un outil peut lister TOUTE la dette connue au démarrage
sans grep, avec sa localisation exacte » (§G.2). Mais le même paragraphe mesure son défaut :
`AnnotationsManager.Analyse` **n'est pas appelée** au démarrage (`grep` dans les deux `Program.cs`,
aucun appel) — « le mécanisme existe et fonctionne mais n'est pas branché en continu ; un outil
déclaré n'est pas un outil exercé ». On adopte l'outil **et** son branchement, et la gate J3.C vérifie
que le compte journalisé au démarrage égale le compte obtenu par grep.

---

## D-12 — Aucun défaut qui tue, aucune sécurité en commentaire

**Retenu** — pas d'extinction programmée par défaut ; backlog d'écoute dimensionné et configurable ;
toute vérification de sécurité est soit active, soit supprimée ; tout refus est **nommé et tracé**.

**Alternatives rejetées, chacune mesurée chez Jiva**
- `ScheduledAutomaticShutdown = true` par défaut, `AutomaticShutdownTimer = 6 × 60` minutes, vérifié
  toutes les 5 s, `Shutdown()` inconditionnel au-delà de 6 h — dans `ServerBase`, donc **hérité par
  Auth ET World** (`ARCHI-REFERENCE-JIVA.md` §E.2, `ServerBase.cs:42,48,402,465-470`). Le fragment
  nomme le piège : « ça tournait en dev, ça meurt en silence 6 h après le déploiement ».
- `m_listenSocket.Listen(1)` (§E.3, `IPCHost.cs:127`).
- Blocs de sécurité laissés en commentaire dans du code actif (§E.1 `//Verify Hack` ; §E.6 anti-bot IP,
  `ConnectionHandler.cs:166-194`). Le fragment conclut : « un commentaire de sécurité inactif se lit
  comme une protection alors qu'il n'en est pas une ».

**Raison** — ces trois-là sont des pièges d'exploitation, pas des choix d'architecture ; les recopier
serait hériter d'une solution au lieu d'une contrainte.

---

## D-13 — Pas de `sealed` sur le domaine ; fichiers < 500 lignes

**Retenu** — conception ouverte, et découpage par domaine fonctionnel **dès l'écriture**.

**Raison, mesurée des deux côtés** — Jiva : **131 classes `sealed`** dans `Server/` + `DofusProtocol/`,
dont `Character` elle-même (`ARCHI-REFERENCE-JIVA.md` §E.5, `Character.cs:105`), et des fichiers
« dieu » — `Character.cs` **4637** lignes, `Fight.cs` **2989**, `FightActor.cs` **2368**, `Map.cs`
**2095**. Giny : **une seule** classe `sealed` dans 2881 fichiers, un utilitaire
(`ARCHI-REFERENCE-GINY.md` §G.5, `AsyncRandom.cs:10`), mais les fichiers « dieu » restent —
`Fighter.cs` **2721**, `Character.cs` **1990** (§F.3, « Giny fait mieux en valeur absolue mais ne
règle pas le problème de principe »).

Le livrable de l'étage 5 est destiné à être **repris par d'autres** (cahier §5, gate G5 : « un
contributeur externe, avec le dépôt seul, déploie et entre en jeu, sans nous ») : fermer l'héritage du
domaine irait contre le brief. Règle du projet : < 500 lignes, mesuré à chaque gate.

---

## D-14 — La preuve est le bot-testeur ; le compilateur ne prouve rien

**Retenu** — chaque jalon se ferme par un scénario bot nommé, plus une vérification indépendante,
rejouée contre le client vivant.

**Raison** — règle du projet et critère de faussete explicite
(« un handler "vert" sans scénario bot-testeur passé = REFUTED »). Mesure adverse : Giny a
**0 fichier de test** et **0 `.csproj`** référençant MSTest/xUnit/NUnit (`ARCHI-REFERENCE-GINY.md`
§G.1) — sur ce point le dépôt « ne soutient PAS la discipline Test-Driven ».

L'instrument existe déjà et est déterministe : 21 tests verts, rejeu **byte-identique** à seed égale
(deux sha256 identiques mesurés), et un déterminisme **contrôlé, pas absent** — seeds différentes sur
le scénario aléatoire donnent trois rapports différents (`internal/bot-testeur/SPEC.md:172-192`).

**Nuance à ne pas confondre** — contre un vrai serveur, le rapport n'est **plus** byte-identique (la
latence réelle varie, SPEC §8.2). Le rejeu byte-identique est une propriété du **banc de test** ; la mesure
du serveur est une **mesure**. Une gate qui exigerait l'identité d'octets contre notre serveur
fabriquerait un faux rouge.

---

## D-15 — Le brief corrigé sur deux points, mesure à l'appui

**(a) « 230 cellules »** — le brief transmis à l'architecte donnait 230 comme taille de la carte
191105026. Mesuré ce tour : une carte 3.0 fait **560 cellules**, 14 × 40
(`refs/JondoEmu/docs/world.md:18`) ; **230 est le nombre de cellules MARCHABLES** de cette carte
précise, lu dans `refs/JondoEmu/datos/map_walkable_cells.json` (dictionnaire de 17 211 cartes ; clé
`191105026` → liste de longueur 230, premiers identifiants 91, 92, 104, 105, 106…). Les identifiants
montent donc jusqu'à 559. Moyenne du corpus : 173,6 marchables par carte, de 1 à 290
(`refs/JondoEmu/docs/world.md:49`). **Un tableau de 230 cellules planterait au premier identifiant.**

**Corroboration indépendante, arrivée après coup** : le fragment `DONNEES-3.0-CARTE.md:50-57`, déposé
dans ce répertoire par un travail parallèle sur les données pendant la rédaction, mesure le même 230 par une lecture Python
séparée, et pose la même distinction. Deux mesures indépendantes, même chiffre — et le même piège
signalé. En revanche il note `cellCount = 560` comme **DÉDUIT** (« valeur historique Dofus ») : notre
lecture le rend **VÉRIFIÉ**, `refs/JondoEmu/docs/world.md:18` (« A map is 560 cells, 14 across and 40
rows down »).

---

## D-16 — La géométrie des cartes est un **blocage de données**, pas un choix d'architecture

**Constat** — les bundles de scène qui portent `ClientMapData.cellsData` et les quatre voisins de
carte n'existent nulle part sur ce VPS (`find -iname "*.bundle"` ne rend que les 204 bundles de
DONNÉES, `DONNEES-3.0-CARTE.md:133-138`). Et **même le serveur 3.0 de référence n'en a pas** : la
table `MapTemplates` de `world.db` de Jondo, 15 360 lignes, ne porte qu'une fiche d'identité de 136
octets pour Astrub (`:91-101`).

**Décision** — on ne conçoit pas autour du trou, on le **nomme** et on avance sur ce qui ne dépend pas
de lui. Le schéma cible est déjà connu par notre propre dump (`ClientCellData`, 17 champs,
`il2cpp.cs:123421-123458`), donc la table est écrite avec ses 17 colonnes dès la première migration ;
13 restent nulles jusqu'au rapatriement. Conséquence de jalonnement : J3.4 et trois des quatre
contrôles de J3.5 avancent avec le seul drapeau `mov` ; **J3.6 (changement de carte) attend les
voisins** et ne peut pas être déclaré vert avant.

**Alternative rejetée** — dériver les voisins par l'arithmétique de coordonnées comme le fait Jondo en
dernier recours. Rejeté comme source primaire : son propre manuel mesure que l'étage « table de
voisinage » est **quasiment inatteignable** chez lui parce que l'étage précédent écrit presque toujours
les 4 voisins, dont une bonne partie pointe vers des cartes qui n'existent pas dans `MapPositions`
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:740-743`). On garde l'arithmétique comme **filet**, jamais comme
vérité.

**Note de tenue de dépôt** — `DONNEES-3.0-CARTE.md` est un fragment d'**étage 1** (domaine « données »,
format §4 du cahier) déposé dans `server/`. Je ne le déplace pas : un seul écrivain par
fichier, et il ne m'appartient pas. À reclasser par son auteur ou par le chef d'équipe vers
`internal/`.

**(b) L'ordre du premier jalon** — le brief demandait comme J3.1 « le vrai client atteint l'écran de
**sélection de serveur** (kqz → rafale de bienvenue) ». Les deux moitiés ne vont pas ensemble : `kqz`
présente le ticket sur la **seconde** connexion et déclenche la rafale qui se termine par `kvi`, la
liste des **personnages** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:369-382, 404-421`). L'écran de sélection
de serveur vient **avant**, du protocole **nu** sans enveloppe `Any` (`:281-343`,
`BuildAuthenticationAccepted` puis `mhj`/`mhl`). Le DAG scinde donc en J3.1 (protocole nu → écran
serveur) et J3.2 (`kqz` + rafale → écran personnages), sans rien retirer au périmètre demandé.
