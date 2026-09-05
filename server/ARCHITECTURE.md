# ARCHITECTURE — Serveur Dofus 3.0 souverain « Namaste 3 » (étage 3)

> # 🟡 v0 — DESIGN, À RÉVISER APRÈS LA CARTE
>
> Document d'architecture FALSIFIABLE, étage 3. Écrit le 2026-09-04.
> **Sources lues** : le brief initial du projet · les 5 fragments d'archi et de séquence de
> `internal/` · `chemin-critique.txt` · `index/` · `matcher/RAPPORT-MATCHER.md` ·
> `internal/third-party-review/otomai-bubblebot/` · `internal/` (G0, littéraux) · `internal/haapi-stub/` (CARTE-HAAPI,
> bot-testeur) · `server/DONNEES-3.0-CARTE.md` · `refs/JondoEmu/` (lecture seule) ·
> `refs/dofus-server-client-2.68/docker-compose.yml`.
>
> **Décision du porteur du projet, 04/09** : *« avant de coder tu veux pas attendre la cartographie ??? »* Ceci est un
> **design v0**, pas un feu vert. **Aucun fichier `.cs` n'est écrit** (mesuré : 0). **Chaque section
> porte son marqueur de révision** : ce qu'elle attend, nommément, pour être fermée.
>
> **Mesuré au 04/09 23:2x** — le travail parallèle a livré 7 fragments (4 `internal/reference-fragments/jiva-2.42/`, 3
> `internal/third-party-review/otomai-bubblebot/`) ; le graphe `graphe-protocole` n'est pas interrogeable ; **G1** rejouée
> donne **32/32 couverts, 31/32 conformes** — seul `krt` refuse, sur le SENS.
>
> Convention du cahier §4 : `chemin/Fichier.ext:NNN`, dossier terminé par `/`, chaque affirmation
> portant **VÉRIFIÉ** ou **DÉDUIT**. DAG dans `DAG.md`, contrats dans `INTERFACES.md`, arbitrages
> dans `DECISIONS.md` — chaque « on choisit X » ici renvoie à une décision `D-nn` là-bas.
>
> ⛔ **Étage 3 est bloqué tant que J3.0 n'est pas vert** — J3.0 exige G1 verte, le graphe interrogeable
> et ce design révisé, pas seulement G2. **Le codec est arrivé pendant cette rédaction**
> (`codec/`) — à rejouer nous-mêmes, pas à croire sur rapport.

---

## 0. Ce qui absorbe l'exponentielle (L4 → L7)

> **v0 — à réviser après la carte.** Ferme sur : le graphe `graphe-protocole` interrogeable · le ratio réel
> d'imports du protocole une fois le socle écrit · une seconde build pour éprouver la régénération.

**Quatre règles du projet, gravées au §0, gouvernent ce document.** L4 : Dofus 2 et 3 sont **deux
builds, deux mondes**, rien ne s'y porte tel quel. L5 : *« une maison avec de mauvaises fondations va
finir par s'effondrer (Stump = mauvaises fondations) »*, et la complexité 3.0 est **exponentielle**.
L6 : *« Dofus 3 est dynamique et non statique »*. L7 : seule l'**analyse dynamique** du client donne le
SENS et l'ORDRE — le dump ne donne que la FORME.

**L'exponentielle se chiffre** : 2169 messages contre ~1030 en 2.42, des noms **obfusqués et
re-brassés à chaque build**, des bundles Unity au lieu de `.d2o`, une couche HAAPI et un launcher
Electron en plus. On ne l'absorbe pas par de la discipline, qui s'érode, mais par **cinq mécanismes
structurels**, chacun avec sa mesure.

**0.1 — La génération du protocole, pas la transcription.** Le protocole est **régénéré** depuis notre
dump à chaque build. Patron à lire : `refs/otomai/tools/proto-sync/`, mesuré à **1201 lignes** en cinq
fichiers (`parser.py` 399, `main.py` 261, `diff.py` 224, `codegen.py` 173, `registry.py` 144) — un
**registre de schémas versionné**, instantané par `--game-version`, diff entre deux versions,
régénération. **La build y est une clé**, ce que L6 exige. Lire, pas copier (GPL-3.0).

**0.2 — La frontière couche générée / cœur, mesurée.** Cible : **< 10 % des fichiers** importent le
protocole, **0 %** dans le domaine. Contre-mesure : **72,5 %** chez Giny (414/571, §G.3).

**0.3 — Aucune constante d'opcode dans le code (L6).** Mesure qui fonde la loi : l'opcode 3 lettres
**EST** le nom de classe obfusqué, donc il est re-brassé à chaque build. Entre Jondo et otomai, tous
deux étiquetés « 3.6.10.10 », **84 % des opcodes se collisionnent mais 0 accord de sens sur 27
examinés** — `jru` charge la carte chez l'un et répond d'arène chez l'autre, pour un bruit de fond
de 30 %. **Un opcode venu de la table d'une autre build est pire qu'inutile : il est plausible et
faux.** Conséquence : les handlers sont écrits contre des **noms sémantiques stables**
(`MapCurrentEvent`), et la table `nom ↔ opcode ↔ type` est **générée par build et chargée au
démarrage**, jamais compilée en dur (contrat en `INTERFACES.md` §2). Gate : `grep` d'une constante
d'opcode dans `src/` doit rendre **0**.

**0.4 — Le graphe interrogeable plutôt que la relecture.** Le travail parallèle **interroge** `graphe-protocole` au lieu
de relire les sources (coût ÷ 40 mesuré) ; sans lui, chaque chantier repaie la carte.

**0.4bis — Les sondes DYNAMIQUES côté client répondent au bot côté serveur (L7).** Le dump donne la
FORME ; seul le client **qui tourne** donne le SENS et l'ORDRE. Trois instruments, chacun face à un
instrument serveur déjà là : **sniffer/décodeur** sur le fil (patron `refs/dofus3-sniffer-tui`) face
au codec · **accrochage IL2CPP à l'exécution** sans MelonLoader (patron `refs/dofus3-native-host`,
`version.dll`), journalisant quel manager émet quel opcode et quand, face à `execution_trace` ·
**rejeu de captures** face au bot. Un désaccord entre les deux côtés localise un défaut.

**0.5 — Une gate par nœud, un écrivain par fichier.** Chaque jalon du `DAG.md` porte sa gate et son critère de faussete ; les fondations sont **rouge-bloquantes** avant tout handler.

**Ce que L4 interdit.** Rien du 2.x ne se porte **structurellement**. Se transpose la **règle du jeu**
(Area, anti-triche, combat, économie), et **chaque transposition est un `DÉDUIT`** à vérifier contre le
client 3.0. Ne se transpose jamais : un numéro de champ, un format, un identifiant, un outil. Quand ce
document cite Jiva sur les cellules, il cite un **principe de stockage**, jamais un gabarit.

**Ce que L6 interdit, au-delà des opcodes.** Configuration externe, données Addressables et HAAPI sont
**téléchargées par version côté client** : le serveur ne suppose jamais un contenu statique, ni
catalogue figé, ni route en dur, ni identifiant de contenu constant. La build est une **clé** partout
où l'on range quelque chose : fixtures, `.tsv`, tables de protocole, schéma de base.

---

## 1. Vue d'ensemble — les processus

> **v0 — à réviser après la carte.** Ferme sur : `internal/third-party-review/otomai-bubblebot/Séquence login…md`
> (**livré**, seconde source CLIENT sur la phase de connexion nue, à confronter à mon §1.1) · le graphe
> `graphe-protocole` pour les arêtes `ENVOIE`/`ATTEND` et les nœuds `Sequence`/`Etape` (**pas encore
> interrogeable**) · une capture réelle qui dit si le client suit le champ `ports` (tranche D-03).

### 1.1 Deux processus, et **aucun protocole IPC** (D-01, D-02)

```
 client 3.6.10.10 ──(1) mhj auth──►┌ namaste3-connect  TCP :5555, protobuf NU ────┐
                  ◄─(2) mhl ticket─┤   mhh{ gfcd=1 auth | gfce=2 authResult }     │
                                   └──────────────┬───────────────────────────────┘
                                    ticket en base │ usage unique, TTL 5 min
                  ──(3) kqz ticket─►┌ namaste3-world  TCP :5556 ─────────────────┐
                  ◄─(4) rafale… ────┤   enveloppe Any + typeUrl, Areas, domaine   │
                                   └──────────────┬───────────────────────────────┘
                                                  ▼
                    PostgreSQL 16 — la SEULE frontière entre les deux processus

 hors périmètre étage 3 (livrés étage 2) : zaap-stub (:26116), haapi-stub (:443)
```

**Pourquoi deux processus** — VÉRIFIÉ, contrainte du protocole : le client **ferme la connexion et en
rouvre une** entre la sélection de serveur et le jeu (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:344-357` :
`BuildServerSelected` renvoie `{ticket, host, ports}`, « le client ferme cette connexion et en ouvre
une nouvelle sur `host:port[0]` »). Le multiplexage sur un port unique chez Jondo est une décision
d'implémentation, pas du protocole (`GameServerProxy.cs:71-104`). Les deux références 2.x séparent
aussi (Jiva `AuthServer`/`WorldServer`, Giny `Giny.Auth`/`Giny.World`).

**Pourquoi aucun IPC** — notre divergence la plus structurante (D-02). Les deux références paient un
canal IPC applicatif pour une seule question du chemin critique : « ce ticket est-il valide ? ». Quatre
défauts mesurés y sont attachés : backlog `Listen(1)` face à `ServersMaxCount=10` (Jiva §E.3), framing
dupliqué aux deux bouts (§E.4), un refus IPC qui tue le process World entier (§A.3), un verrou
redondant sur structure déjà thread-safe (Giny §F.2). **Nous remplaçons ce canal par une consommation
atomique en base** :

```sql
UPDATE session_ticket SET consumed_at = now()
 WHERE ticket = $1 AND consumed_at IS NULL AND expires_at > now()
RETURNING account_id, server_id, language;   -- 0 ligne = refus, 1 ligne = succès
```

Une seule instruction porte l'atomicité, l'usage unique et l'expiration que Jondo décrit comme trois
propriétés distinctes de `SessionRegistry.Issue`/`Redeem` (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:355-357,
377-379`). Le plan de contrôle restant (état du monde, nombre de joueurs) est une **ligne de table**
`world_server` rafraîchie toutes les 10 s — même intervalle que le heartbeat IPC de Jiva
(`ARCHI-REFERENCE-JIVA.md` §A.3 point 5), sans le protocole.

**Ce qu'on paie** : Postgres devient une dépendance dure du login. Elle l'était déjà (comptes,
personnages). **Ce qu'on refuse de faire** : mettre le ticket dans un cache mémoire de process comme
Jiva (`FindCachedAccountByTicket`, §A.4 point 5) — le fragment Jiva signale lui-même que ce cache
interdit tout Auth multi-instance et ne survit pas à un redémarrage.

### 1.2 Un seul port, ou deux ?

**DÉDUIT, tranché en faveur de DEUX ports** (D-03). Jondo multiplexe sur 5555 et détecte la phase par
la présence d'une chaîne dans le premier frame : deux protocoles incompatibles dans le même chemin de
code. Le client n'impose rien, il suit `host:ports[0]` de NOTRE `authResult`. **Comment vérifier** :
gate J3.2, `netstat` doit montrer la seconde connexion vers 5556. S'il ignore `ports`, on replie sur
le multiplexage — une ligne de configuration, pas une réécriture.

---

## 2. Les couches

> **v0 — à réviser après la carte.** Ferme sur : `internal/third-party-review/otomai-bubblebot/Transport & framing…md`
> (**livré**) · `codec/CODEC.md` (**livré pendant cette rédaction**, à rejouer).
>
> **Deux corrections apportées par d'autres pendant que j'écrivais, toutes deux retenues.**
> (a) Le trafic de jeu est du **TCP nu, sans TLS**, sur le 5555 **et** sur le 443 : otomai porte un
> chemin TLS complet mais `useTls` y est une constante fausse, et **aucune occurrence de
> `UseTls = true` n'existe dans le dépôt** (§F.1-F.2, `TcpClient.cs:1344-1412`, `BotClient.cs:231`).
> **Un port qui ressemble à du TLS n'en est pas une preuve.**
> (b) 🔴 **Le jeu n'est PAS sur la pile Spin** — mesuré par le codec contre 355 trames réelles
> (`internal/LITTERAUX-RESEAU-EN-CLAIR.md`, correction du 04/09 23 h). Il y a **deux piles** :
> `SpinConnection` porte le **launcher et le chat**, avec un octet de type en tête
> (Application=0, Ping=1, Pong=2, Heartbeat=3, `il2cpp.cs:579716`) ; le **socket de jeu** est sur
> **DotNetty**, `ProtobufVarint32FrameDecoder` (`il2cpp.cs:487219`), `gjv : MessageToMessageCodec<hea,
> object>` portant le littéral `type.ankama.com` (`:825181`). Sur le fil de jeu, **pas d'octet de
> type** : la longueur varint couvre exactement le protobuf. Mon contrat de codec (§1 d'`INTERFACES.md`)
> était juste ; ce qu'il ne disait pas, c'est qu'une pile voisine porte un préfixe qui n'existe pas
> ici. Un codec écrit sur la section Spin aurait cherché un octet absent.

```
  ┌──────────────────────────────────────────────────────────────────────┐
  │ Namaste3.Transport   TCP, accept, backlog dimensionné, quotas        │
  │                      FrameDelimiter : varint(len) ++ bytes[len]      │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Namaste3.Codec       root{ 1:Any push | 2:Any+reqId | 3:Any+reqId }  │
  │                      Any{ 1:typeUrl string, 2:bytes payload }        │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Namaste3.Protocol    ★ GÉNÉRÉ ★ 2169 messages + registre d'opcodes   │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Namaste3.Net         dispatch (opcode → handler) + handlers          │
  │                      SEUL endroit où protocole et domaine se voient  │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Namaste3.World       DOMAINE — Area, Map, Character, Path            │
  │                      ZÉRO `using Namaste3.Protocol` (gate mesurée)   │
  ├──────────────────────────────────────────────────────────────────────┤
  │ Namaste3.Store       Postgres, UUIDv7, migrations, audit             │
  └──────────────────────────────────────────────────────────────────────┘
```

**La frontière qui compte est celle entre `Namaste3.Net` et `Namaste3.World`.** Mesure de référence :
chez Giny, **414 fichiers sur 571 (72,5 %)** de `Servers/Giny.World/` importent directement le
protocole (`ARCHI-REFERENCE-GINY.md` §G.3, `grep -rl "using Giny.Protocol"`). Un rebrassage d'Ankama
touche alors les trois quarts du serveur. Notre cible est **0 fichier du domaine** qui importe le
protocole, et c'est une **gate déterministe rejouable**, pas une intention :

```bash
test "$(grep -rl 'using Namaste3.Protocol' src/Namaste3.World/ | wc -l)" -eq 0
```

Les handlers traduisent : message protocole → **commande de domaine** (record C# sans dépendance
protocole) ; événement de domaine → message protocole. Le domaine ne sait pas qu'un opcode existe.

---

## 3. Concurrence — l'Area, et pourquoi le garde est un TYPE

> **v0 — à réviser après la carte.** Ferme sur : `internal/reference-fragments/jiva-2.42/combat-tour-par-tour.md`
> (**livré** — le combat est le consommateur le plus exigeant de la frontière d'Area, il dira si
> l'unité de sérialisation tient) · `internal/reference-fragments/jiva-2.42/social-guilde-groupe-chat.md` (**livré** — le
> social est ce qui traverse les Areas, donc ce qui teste le passage de message inter-Area) · le
> découpage Area/SubArea du 3.0, qui n'existe dans **aucun** fragment à ce jour (cf. J3.B).

### 3.1 Ce qu'on reprend, ce qu'on durcit

**VÉRIFIÉ** — Jiva sérialise par **Area** (une région, plusieurs maps) : file lock-free + roue de
timers, tick auto-replanifié toutes les `DefaultUpdateDelay=50` ms, Area démarrée à l'entrée du
premier `Character` et arrêtée à la sortie du dernier (`ARCHI-REFERENCE-JIVA.md` §B.1, citant
`Game/Maps/Area.cs:21,26,38-57,252-274,344-470,480-504`). Giny fait l'inverse : `ConcurrentDictionary`
partagés sans unité de sérialisation, et une `List<MapElement>` annotée `[Annotation("thread safe..")]`
alors que `List<T>` ne l'est pas, réassignée entière pendant que d'autres threads l'énumèrent
(`ARCHI-REFERENCE-GINY.md` §B.1-B.2, `MapInstance.cs:45-48,121-131,334-337`).

On prend l'Area de Jiva. **On ne prend pas son garde.** Chez Jiva le garde est un appel runtime que
l'auteur doit penser à faire (`IsInContext`, comparaison de `ManagedThreadId`, §B.1) : un handler qui
oublie `ExecuteInContext` mute l'état depuis le thread réseau, et rien ne le dit. Notre garde est un
**type non fabricable hors de la boucle** (D-04) :

```csharp
public readonly ref struct AreaTick { }        // pas de constructeur public
public sealed class Character { public void MoveTo(AreaTick _, Cell c); }
```

Toute mutation du domaine exige un `AreaTick` ; seul le corps de la boucle d'Area en produit un ;
`ref struct` interdit de le capturer dans une lambda, un champ ou un `async`. **Une mutation hors
Area devient une erreur de COMPILATION, pas un assert runtime.** C'est la seule forme de garde qui
survit à la précipitation.

### 3.2 Frontières

| Portée | Contenu | Règle |
|---|---|---|
| **Area** (1 tâche, 1 file `Channel<AreaCommand>`) | Maps de la région, acteurs, timers | mutation uniquement sous `AreaTick` |
| **Inter-Area** | changement de région | message + **snapshot immuable**, jamais une référence d'objet |
| **Global** | index `characterId → AreaId`, registre de sessions, état du monde, écrivains de socket | structures immuables ou `Channel`, jamais un objet de domaine |

MVP (J3.1 → J3.7) : **une seule Area**, « Astrub », contenant la map 191105026. Le découpage réel est
**DÉDUIT** — aucun fragment ne donne le graphe Area/SubArea du 3.0. Mesuré en revanche : `jss` porte
`f6: subAreaId` et il est **OBLIGATOIRE** (un zéro plante le client,
`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:641-643`). Comment vérifier : extraire `MapPositions`/`SubArea` de
`lot31-data-3.0-full/json/` (15 360 cartes), commandé en `DAG.md` J3.B.

---

## 4. Modèle de données minimal — format 3.0

> **v0 — à réviser après la carte.** Ferme sur : les **bundles de scène** rapatriés d'un PC personnel
> (**bloqué**, cf. §9 et J3.B — c'est le seul verrou dur de cette section) ·
> `server/DONNEES-3.0-CARTE.md` (**livré**, déjà intégré ci-dessous) ·
> `internal/reference-fragments/jiva-2.42/inventaire-objets-effets.md` (**livré** — pour le modèle d'objet, hors MVP mais
> il conditionne la forme des tables `character`).
>
> ⚠️ **Règle ajoutée le 04/09 pendant la rédaction** : Dofus 2 et Dofus 3 sont **deux
> builds, deux mondes**, et *« rien ne se porte tel quel entre les deux : ni le protocole, ni les
> formats de données, ni les outils »*. Cette section est donc la plus exposée : tout ce qui vient de
> Jiva y est un **patron d'architecture**, jamais un format. Les 11 octets par cellule de Jiva sont
> cités comme principe de stockage, pas comme gabarit — c'est explicite en fin de §4.1.

### 4.1 Les cartes : 560 cellules, dont 230 marchables pour Astrub (chiffre du brief corrigé)

**VÉRIFIÉ, mesuré ce tour** : une carte 3.0 fait **560 cellules**, 14 de large sur 40 rangées
(`refs/JondoEmu/docs/world.md:18`). Le brief qui m'a été transmis disait « 230 cellules » pour
191105026 : **230 est le nombre de cellules MARCHABLES, pas la taille de la grille** — mesuré
directement par lecture de `refs/JondoEmu/datos/map_walkable_cells.json` (dict de 17 211 cartes ;
clé `191105026` → liste de longueur **230**, premiers identifiants `91, 92, 104, 105, 106…`). Les
identifiants de cellule montent donc jusqu'à 559. **Un serveur qui allouerait un tableau de 230
cellules serait faux et planterait sur l'identifiant 91.** Moyenne mesurée sur le corpus : 173,6
cellules marchables par carte, de 1 à 290 (`refs/JondoEmu/docs/world.md:49`).

**Corroboration indépendante** : le fragment `DONNEES-3.0-CARTE.md:50-57` (déposé dans ce répertoire
par un travail parallèle sur les données pendant la rédaction de ce document) mesure le même 230 par une lecture Python
séparée du même fichier, et note lui aussi la distinction. Deux mesures indépendantes, même chiffre.

**Le schéma d'une cellule 3.0 est CONNU, ses valeurs sont ABSENTES.** `ClientCellData` est en clair
dans notre dump — `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs:123421-123458` — avec **17
champs** (`cellNumber`, `mov`, `los`, `floor`, `arrow`, `red`/`blue`, `moveZone`, `linkedZone`,
`mapChangeData`, `farmCell`, `havenbagCell`, les non-marchables combat/RP…, relevé
`DONNEES-3.0-CARTE.md:72-81`). Nos données ne couvrent que **`mov`** et le sous-ensemble combat :
**13 champs sur 17 sont un trou mesuré**. `ClientMapData` porte en plus les **4 voisins de carte**
(`il2cpp.cs:123607`), nécessaires à J3.6.

Stockage : **un `bytea` de 560 octets par carte**, un octet de drapeaux par cellule, plus les colonnes
scalaires (`floor`, `arrow`, `moveZone`, `linkedZone`) dans un second blob quand elles seront extraites.
Jiva stocke un blob gzip de structs de 11 octets par cellule (`ARCHI-REFERENCE-JIVA.md` §B.2,
`Cell.cs:8,59-85`, `StructSize=11`) — on garde le principe « un blob par carte, pas une table
normalisée », on n'hérite pas du format 2.x.

`sub_area_id` d'Astrub = **95**, VÉRIFIÉ : `world.db.MapTemplates` de Jondo donne pour 191105026
`{"id":191105026,"m_flags":78763165,"nameId":0,"posX":5,"posY":-18,"subAreaId":95,
"tacticalModeTemplateId":0,"worldMap":1}` (`DONNEES-3.0-CARTE.md:96-98`), et la même fiche existe dans
`lot31-data-3.0-full/json/mapsinformation.json:186544`. C'est la valeur que `jss f6` doit porter.

**Pas de table de voisinage de cellules.** Jiva calcule les voisins géométriquement à la volée
(`ARCHI-REFERENCE-JIVA.md` §B.2, `Pathfinder.cs:38-48,116-132`). On fait pareil.

### 4.2 Tables

| Table | Clé | Colonnes qui portent une contrainte mesurée |
|---|---|---|
| `account` | UUIDv7 | `login`, `password_hash` (argon2id), `nickname`, `tag`, `banned_at` |
| `session_ticket` | `ticket` (24 o CSPRNG → base64url) | `account_id`, `server_id`, `issued_at`, `expires_at` (**5 min**), `consumed_at` — usage unique atomique §1.1 |
| `character` | UUIDv7 | `account_id`, `name`, `breed`, `sex`, `level`, `look bytea`, `map_id bigint`, `cell_id smallint`, `direction smallint`, `kamas bigint` |
| `map` | `map_id bigint` | `sub_area_id int **NOT NULL**` (un zéro plante le client, §3.2), `cells bytea(560)` |
| `world_server` | `id` | `name`, `host`, `port`, `state`, `chars_count`, `last_heartbeat_at` — remplace l'IPC (§1.1) |
| `audit_event` | UUIDv7 | append-only : qui, quoi, dans quel cadre, avec quelle permission |
| `execution_trace` | UUIDv7 | **action → conséquence** (journal causal, §7) |

`map_id` est un `bigint` : Jondo déclare `StartingMap = 191105026L` (`:536`) et `jru` porte
`f2: mapId(varint)` (`:604-606`). **RLS** : pas au démarrage (cadrage du brief), mais la colonne de
portée `space_id` est présente **dès la première migration**, non contrainte — activer RLS plus tard
devient une migration de politique, pas de schéma. Sous L6, **la build est une colonne** partout où
l'on range un artefact de protocole.

---

## 5. Génération du protocole — où passe la frontière

> **v0 — à réviser après la carte.** Ferme sur : `tools/protocol-mapping/matcher/correspondance-noms-classes.tsv`
> **complété** — aujourd'hui **511 lignes sur 515 en `À_CLASSER`**, seulement 4 correspondances
> proposées, toutes `DÉDUIT` (`matcher/RAPPORT-MATCHER.md` §1 et §6) · le graphe `graphe-protocole` pour
> l'ancrage `ÉQUIVALENT`/`INVARIANT`/`DIVERGENT`/`ÉVOLUTION` (**pas encore interrogeable**) ·
> `tools/protocol-mapping/index/messages-jondo.tsv` **régénéré** sur le bon `.proto` (cf. §5.3, D-09).
>
> **La table de liaison sémantique → opcode ne peut pas être écrite avant cette fermeture.** C'est
> précisément ce que le projet veut éviter : coder des handlers sur une correspondance à 4 lignes sur 515.

### 5.1 Ce qui est généré

**VÉRIFIÉ, corroboration à deux natures de source indépendantes** : notre dump compte **2169 classes
`IBufferMessage` dans `Ankama.Dofus.Protocol.Game.dll`** (`internal/GATE-G0-RAPPORT.md:19`), et le
`.proto` reconstruit par Jondo depuis le même client compte **2169 `message`** (`grep -c "^message "`,
mesuré ce tour). Une donnée décodée et un code déclaré, deux chemins sans rapport, **le même nombre**.

Sont **générés** (0 jeton, script) depuis NOTRE dump : les 2169 + 37 classes de message avec numéros
et types de champ · le **registre d'opcodes** (`typeUrl` → type CLR → délégué de parse), **par build** ·
les **signatures structurelles** (Weisfeiler-Lehman, algorithme décrit
`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:786-833`) pour le re-mappage inter-versions de l'étage 4.
Sont **écrits à la main** : handlers, domaine, persistance, outillage.

### 5.2 La frontière : la table de liaison est une DONNÉE, chargée au démarrage (L6)

Les noms rotent. Mesuré chez Jondo : sur 3.6.4.3→3.6.10.10, le matcher structurel ne réapparie que
**245 messages sur 2169 (11,3 %)** (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:830-833`), et 3 patchs sur 7 ne
rotent pas du tout (`:862-864`). Côté 2.x, 868 classes sur 872 sont renumérotées entre 2.42 et 2.73
(**99,5 %**, `ARCHI-REFERENCE-JIVA.md` §F.1).

**Conséquence, durcie par L6** : aucun handler n'écrit jamais `"kvw"`, et la liaison n'est même pas
**compilée**. `protocol/binding-<build>.tsv` associe chaque nom sémantique à l'opcode et au type de
CETTE build ; il est **généré par la chaîne proto-sync et chargé au démarrage**. Changer de build =
régénérer une donnée, pas recompiler un binaire. La build est une clé du nom de fichier, pas un
commentaire. Principe « régénérer > corriger à la main » de la lignée Symbioz 2018 → Giny 2026
(`ARCHI-REFERENCE-GINY.md` §A.3-A.4), appliqué à une source binaire.

**Gate mesurable** : `grep -rnoE '"[a-z]{3}"' src/ --include=*.cs` doit rendre **0** — la table étant
une donnée, aucun opcode littéral ne subsiste nulle part dans les sources, pas même dans un fichier
de liaison compilé.

### 5.3 ⚠️ Un piège mesuré dans les tables de l'étage 1 — à ne pas propager

**VÉRIFIÉ ce tour.** JondoEmu contient DEUX `.proto` décrivant les mêmes opcodes qui **ne s'accordent
pas** — `datos/protocolo_3.6.10.10.proto:10480-10484,13005-13008,13173-13175` (reconstruit du client,
2169 messages) contre `Jondo.Unity.Protocol/Messages/Protocol.proto:7-12,377-388,406-420` (écrit à la
main, 80 messages). Sur le déplacement, **les numéros de champ du chemin et du mapId sont inversés** ;
`ksl` et `kqp` divergent aussi. Les deux formes sont des varints : ça compile, ça passe le codec, et ça
déplace le personnage n'importe où. Notre table `index/messages-jondo.tsv` a été construite sur le
mauvais fichier (`extraire_messages.py:137`). **Autorité : notre dump, à défaut le `.proto`
reconstruit.** Détail et table comparative : `DECISIONS.md` **D-09** ; régénération en `DAG.md` **J3.A**.

---

## 6. Sécurité par construction

> **v0 — à réviser après la carte.** Ferme sur : `internal/third-party-review/otomai-bubblebot/Séquence in-game
> (perso→map→déplacement) — GameClientServiceBase & handlers.md` (**livré** — c'est la seconde source
> qui dit ce qu'un client 3.0 réimplémenté ENVOIE vraiment, donc ce que notre validation doit accepter
> sans être permissive) · **G1 verte**, aujourd'hui bloquée sur le seul `krt` (sens inconnu) ·
> `internal/reference-fragments/jiva-2.42/combat-tour-par-tour.md` (**livré** — l'anti-triche de combat, hors MVP).
>
> Les quatre contrôles de déplacement (§6.1) ne bougeront pas : ils viennent d'un manque mesuré chez
> **toutes** les références, pas d'une lecture partielle. Ce qui peut bouger, c'est le **budget de
> pas**, dont la valeur n'est encore sourcée nulle part.

### 6.1 Anti-triche déplacement — les quatre contrôles, et le type qui les rend obligatoires

**VÉRIFIÉ — aucune référence ne les a tous.** Jiva valide la marchabilité cellule par cellule
(`ARCHI-REFERENCE-JIVA.md` §B.4) mais a **commenté** le contrôle de la cellule de départ
(`ContextActor.cs:203-204`, `//Verify Hack`) et ne vérifie ni la contiguïté ni un budget de points de
mouvement. Giny fait l'inverse exact : cellule de départ vérifiée (`Character.cs:1044-1046`),
**aucune marchabilité** (§C.3, `PathReader.cs` lu en entier). Jondo vérifie le `mapId` et **ignore
silencieusement** en cas d'écart (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:679-682`).

Notre serveur valide **quatre** choses, serveur-side, dès l'écriture initiale :

1. **mapId** annoncé == map de la session (Jondo) — mais **refus NOMMÉ**, jamais un silence.
2. **Cellule de départ** == position serveur connue (Giny).
3. **Chaque cellule du chemin** dans `[0,559]` **et marchable** selon NOTRE carte (Jiva).
4. **Contiguïté** : chaque pas est un voisin géométrique du précédent, et **budget de pas** — que
   personne n'a.

« Par construction » veut dire une chose précise (D-05) : le type `Path` **n'a aucun constructeur
accessible**. Le seul chemin d'obtention est

```csharp
static bool TryBuildValidated(Map map, Cell from, ReadOnlySpan<int> keys,
                              out Path path, out MoveRefusal refusal);
```

Un handler ne peut pas appliquer un chemin non validé : il n'existe pas de `Path` non validé dans le
programme. **Gate** : `grep -rn "new Path(" src/ | grep -v Path.cs` == 0, plus la suite adversariale
de J3.5 (5 scénarios bot qui doivent TOUS être refusés, chacun avec son motif).

Encodage des clés — **INVARIANT sur trois émulateurs et deux générations** : 12 bits de cellule,
direction dans les bits hauts. Jiva `Path.cs:185-200` · Giny `PathReader.cs:14-21` · 3.0 `jrw f2`
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:677`). Seul invariant 2.x que L4 laisse traverser tel quel, parce
qu'il est **mesuré des deux côtés** et non transposé.

### 6.2 Le reste des limites, chacune avec sa mesure

| Limite | Valeur | Source |
|---|---|---|
| Taille max d'un frame | **131 072 octets**, refus avant allocation | plafond client mesuré, `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:260-262` |
| Longueur d'opcode | exactement 3 lettres, sinon refus tracé | `NetworkEnvelope.cs:11-20` (Jondo avertit et ignore ; nous refusons et comptons) |
| `jru` envoyé deux fois | interdit par construction (`hasSentMapBlock`-like) | boucle de rechargement client mesurée, `:610-611` |
| TTL du ticket | 5 min, usage unique atomique | `docs/sessions.md` §2.5 via `:355-357` |
| Extinction automatique | **aucune** valeur par défaut qui tue le process | anti-pattern Jiva §E.2 (`ScheduledAutomaticShutdown=true`, 6 h, hérité par Auth ET World) |
| Backlog d'écoute | dimensionné et configurable | anti-pattern Jiva §E.3 (`Listen(1)` face à `ServersMaxCount=10`) |

**Aucune sécurité en commentaire.** Jiva laisse deux blocs de contrôle désactivés dans du code actif
(§E.1, §E.6) : un commentaire de sécurité inactif se lit comme une protection. Soit implémenté, soit
supprimé. **Secrets** : jamais en clair, jamais commités ; argon2id ; connexion et jetons par
variables d'environnement ou Vault, jamais par chaîne formatée en dur (contre-exemple Giny §E.2,
`DatabaseManager.cs:18,39`).

---

## 7. Observabilité — le refus est une donnée, pas un silence

> **v0 — à réviser après la carte**, mais c'est la section la **moins** dépendante : elle ne décrit
> aucun opcode. Ferme sur le schéma d'`execution_traces` retenu par l'index causal existant — nos deux
> schémas doivent être **le même**, sinon la trace du bot, celle du serveur et celle du graphe ne se
> joignent pas. À aligner avec l'index causal existant, pas à décider seul.

Trois flux, tous en Postgres, tous append-only :

1. **`audit_event`** — qui a fait quoi, dans quel cadre, avec quelle permission. Les actes
   d'administration et tout accès hors du périmètre d'un compte y passent.
2. **`execution_trace`** — l'**index causal** (action → conséquence) que le cahier §5 désigne comme le
   différenciateur souverain. Une entrée par décision de handler : opcode sémantique, acteur, entrée
   normalisée, **verdict**, **motif nommé**, état avant/après. Le bot-testeur produit déjà cette forme
   (`internal/bot-testeur/SPEC.md:55-57` : `TraceEntry{tick,timeMs,kind,name,relevance,result,why}`,
   « cause = `push.why`, conséquence = `action.result` ») — le serveur écrit le même schéma, ce qui
   rend la trace du bot et celle du serveur **jointes sur le même axe**.
3. **`[Dette]`, la dette interrogeable** — attribut C# listé au démarrage par réflexion. Patron
   `[Annotation]` de Giny (§G.2), supérieur aux tags en commentaire de Jiva (§F.2) parce qu'un outil
   l'énumère sans grep. **On corrige son défaut mesuré** : chez Giny `AnnotationsManager.Analyse`
   n'est jamais appelé au démarrage. Chez nous l'appel est dans le chemin de démarrage, et son
   absence est une gate.

**Aucun refus muet.** Chaque rejet (ticket invalide, mapId incohérent, cellule non marchable, opcode
inconnu) écrit une trace nommée ET incrémente un compteur par motif. Un motif qui domine les refus est
une consigne à reformuler, pas un bruit à filtrer.

---

## 8. Contraintes héritées vs choix

> **v0 — la section la PLUS dépendante de la carte.** Un « invariant » se calcule sur le corpus
> **complet** ; l'affirmer sur sept fragments quand d'autres passes en produiront des dizaines, c'est
> généraliser depuis un échantillon.

**Règle du cahier** (§2 étage 1) : ce que TOUS les émulateurs font est une contrainte du protocole,
obligatoire. Ce qu'un seul fait est un choix d'auteur, libre. *On hérite des contraintes, pas des
solutions.* Sous L4, cette règle se lit **par génération** : un invariant mesuré sur trois émulateurs
2.x est une contrainte du **jeu**, pas du protocole 3.0, et sa transposition reste un `DÉDUIT`.

**La table complète — 6 invariants, 7 choix, 4 manques — vit dans `CONTRAINTES-VS-CHOIX.md`**,
extraite ici pour tenir l'invariant des fichiers < 500 lignes après l'ajout du §0. C'est exactement
la table que le graphe comparatif calculera mécaniquement, et qui sera alors **remplacée** par
sa sortie plutôt que complétée.

## 9. Ce qui manque, et à qui le commander

Chaque manque est rattaché à son nœud du DAG avec sa mesure et son destinataire : `DAG.md`, encadrés
**J3.0** (verrous de démarrage), **J3.A** (`messages-jondo.tsv`), **J3.B** (géométrie), **J3.2**
(`krt`), **J3.3** (`kvl`). Corrections au brief : `DECISIONS.md` D-15. Le plus dur : **les bundles de
scène n'existent nulle part sur ce VPS**, et `world.db` de Jondo n'en stocke aucune non plus — trou
structurel, il demande une main humaine.
