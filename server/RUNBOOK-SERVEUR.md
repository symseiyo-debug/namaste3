# RUNBOOK — serveur de connexion 3.0 « Namaste 3 » (étage 3)

> Livré le 2026-09-05. .NET 8 (SDK 8.0.130), code À NOUS. Aucune ligne reprise d'un émulateur
> tiers : la séquence est **transcrite** de `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` et
> `COMPLEMENT-CHEMIN-CRITIQUE-G1.md`, chaque forme **recroisée** contre le dump de notre client.
> Gate : `./gate-serveur.sh` (`--epreuve` = sabotage + témoins positifs). **VERTE** :
> 36 tests, 0 échec, 0 opcode littéral dans `src/`.
>
> Objectif de la soirée, tel que posé par le porteur du projet : *« osef du portage de version pour l'instant,
> faisons déjà un serveur qui marche »*. Un seul critère mesurable — **le client 3.6.10.10 se
> connecte et affiche un écran**. Ce document dit comment le lancer, et surtout **ce qui est
> encore faux**.
>
> **Aligné le 05/09** sur ordre du porteur du projet — *« mon serveur est la version 3.6.10.10 [...]
> on essaye sur le mien et non celui de Dofus à jour »* : `3.6.10.10` est la cible de référence.
> `3.6.10.11` reste mentionnée dans ce document là où c'est un fait mesuré (le même binaire, sha256
> identique) — jamais comme cible.

---

## 1. Lancer

```bash
cd server
python3 protocol/generer-binding.py          # (re)génère la table de liaison
dotnet build Namaste3.Server.sln
dotnet run --project src/Namaste3.Server.Connection
```

Au démarrage, le serveur **imprime l'état de sa table AVANT d'ouvrir le port** :

```
table de liaison / binding table : .../protocol/binding-3.6.10.10.json
  build                : 3.6.10.10
  opcodes liés / bound : 25
  recroisés étage 1    : 18
  rafale / burst       : 15 messages, 13 opcodes distincts
  garde de ticket      : FERMÉ — seul un ticket émis par la phase nue est accepté
écoute / listening on 0.0.0.0:18420  (build 3.6.10.10)
annoncé au client / announced to the client: 127.0.0.1:18420
```

C'est voulu : un serveur qui démarre en silence sur une table périmée fait chercher la panne
dans le client.

### Options

| Drapeau | Défaut | À quoi ça sert |
|---|---|---|
| `--port N` | `18420` | le port sur lequel on **écoute** |
| `--annonce-hote H` | `127.0.0.1` | l'hôte **annoncé** au client dans « serveur sélectionné » |
| `--annonce-ports N,N` | le port d'écoute | les ports **annoncés** ; le client prend le premier |
| `--table CHEMIN` | la plus récente sous `protocol/` | forcer une autre table de liaison |
| `--silencieux` | non | ne pas imprimer l'arbre des champs sous chaque trame |
| `--ticket-externe` | **non** | accepter un ticket que nous n'avons pas émis — cf. §4.1 |

⚠️ **Écouter et annoncer ne sont pas la même chose.** `--port` dit où on écoute ;
`--annonce-ports` dit où le client ira ensuite. Par défaut les deux valent 18420, donc le client
revient au même endroit et la phase se décide par le contenu de la première trame.

---

## 2. Comment le client arrive jusqu'ici

Le stub HAAPI/Zaap de l'étage 2 (`internal/haapi-stub/`) sert déjà, **vérifié dans ses
captures du 04/09** :

- `connectionHosts: ["Namaste:127.0.0.1:18420"]` (`captures/02_config_response.txt`) ;
- la liste de serveurs `{ Host: "127.0.0.1", Port: 18420 }` (`captures/06_servers_response.txt`).

Le client ouvre donc une connexion TCP sur **18420**, et c'est là que ce serveur écoute.

### La séquence que nous servons

```
1. Le client ouvre 18420 et envoie une trame NUE (protocole de connexion, pas d'opcode)
   -> nous répondons « accès accepté » : compte + liste des serveurs + résumé du personnage
      (c'est CE message qui peuple l'écran de sélection de serveur)
2. Le client choisit un serveur (trame nue portant f4{f1: serverId})
   -> nous répondons « serveur sélectionné » : ticket + hôte + ports
3. Le client ferme, rouvre, et présente le ticket (phase JEU)
   -> nous émettons la RAFALE DE BIENVENUE : 15 messages, 13 opcodes distincts, dans l'ordre
      exact, dont la liste des personnages en avant-dernier et sa marque de fin juste après
4. Le client sélectionne le personnage
   -> nous répondons « personnage sélectionné avec succès »
5. Le client demande l'entrée en monde (ou, à défaut, envoie son premier battement)
   -> nous émettons la carte courante (191105026, le zaap d'Astrub) + les cartes découvertes,
      UNE SEULE FOIS
6. Le client demande qui est sur la carte
   -> nous répondons « carte chargée »
```

Chaque trame reçue et émise est **journalisée** : sens, phase, opcode, nom sémantique, taille,
et l'arbre des champs décodés. Le journal est l'instrument : un client qui reste sur un écran
noir sans journal ne nous apprend rien.

---

## 3. La table de liaison — pourquoi aucun opcode n'est dans le code

`protocol/binding-3.6.10.10.json` est **le seul fichier qui nomme des opcodes 3 lettres**. Le
C# ne connaît que des noms sémantiques stables (`AuthTicket`, `CharactersList`, …).

La raison est mesurée, pas esthétique : l'opcode 3 lettres **est** le nom de classe obfusqué du
client, re-brassé à chaque build — le matcher structurel ne réapparie que **245 messages sur
2169 (11,3 %)** entre deux versions. Un opcode écrit dans du C# ferait d'un patch client une
réécriture du serveur.

La gate le mesure : `grep -rnoE '"[a-z]{3}"' src/ --include=*.cs` doit rendre **0**.

Le générateur ne se croit pas lui-même. Il est recroisé contre **deux instruments indépendants**,
et un désaccord est un refus, pas un avertissement.

| Instrument | Ce qu'il confirme | Mesure du 05/09 |
|---|---|---|
| `tools/protocol-mapping/matcher/correspondance-v4.tsv` | nom clair ↔ opcode | 18/25 confirmés, 7 sans nom clair, **0 désaccord** |
| `protocol/extract/proto-sync/out/dispatch-3.6.10.10.json` | l'opcode existe dans le dump ; son nom ; **et le type de chaque champ dont le serveur dépend** | 25/25 opcodes présents, 18 noms confirmés, **20/20 champs confirmés**, 0 désaccord |

### Pourquoi la table de dispatch ne REMPLACE pas ce fichier

Elle nomme **166 messages sur 2 206**. Sur nos 25, elle en nomme **18** — et les **7** qu'elle
laisse sans nom sont exactement les 7 que `correspondance-v4` laisse sans nom : `krt`, `mgq`,
`mgt`, `hpd`, `krs`, `kqp`, `hjk`. Les deux instruments s'accordent sur le trou, ce qui est une
corroboration et non une lacune.

Mais **six de ces sept sont dans la rafale de bienvenue** (`mgq`, `mgt`, `hpd`, `krs`, `kqp` ×3),
plus `hjk` dans le bloc de carte : **8 des 15 émissions**. Un chargeur qui résoudrait ses
sémantiques *par le nom* de la table de dispatch ne saurait donc pas émettre la moitié de la
rafale. C'est pour ça que la colonne `semantique → opcode` reste ici : c'est le seul endroit où
un message **sans nom clair** peut être lié. La table de dispatch, elle, sert d'**autorité de
vérification** — le rôle où elle est irremplaçable.

### Le recroisement qui manquait : les NUMÉROS de champ

C'est l'apport le plus utile de l'intégration. Un mauvais numéro de champ produit du protobuf
**valide** : le compilateur ne dit rien, le round-trip est vert, et la panne n'apparaît qu'à
l'écran. Les 20 numéros dont le serveur dépend sont désormais vérifiés, un par un, contre les
types lus dans le dump par un **autre extracteur que le mien**.

Le piège que ça garde, et il est réel : `kvl` (première sélection de personnage) a un **booléen**
en champ 1 et l'identifiant en champ 2. Lire le champ 1 rendrait `0` ou `1` en guise
d'identifiant de personnage. L'épreuve de la gate fausse exactement ce numéro et exige un refus.

Le recroisement n'est **plus cross-build** depuis l'alignement du 05/09 : la table de dispatch et
la table de liaison sont désormais mesurées sur la **même** build, `3.6.10.10` — celle réellement
utilisée par notre serveur. *Avant l'alignement*, la table visait `3.6.10.11` et ça tenait déjà :
les 25 opcodes du chemin critique portent le même nom obfusqué dans les deux builds, parce que
`3.6.10.10` et `3.6.10.11` sont **le même binaire** (sha256 identique sur `GameAssembly.dll` et
`global-metadata.dat`, rotation nulle sur 2 169 identités) — **et c'est vérifié ici même** : un
opcode qui aurait bougé serait rendu `ABSENT`, pas silencieusement accepté. Le détail de ce qui a
été vérifié est écrit dans le produit (`recroisement_etage5` du JSON), pas seulement imprimé en
console.

Régénérer après tout changement de build :

```bash
python3 protocol/generer-binding.py            # écrit
python3 protocol/generer-binding.py --verifier # rc=1 si le fichier sur disque est périmé
```

---

## 4. ⚠️ CE QUI EST ENCORE FAUX

### 4.1 Le ticket ne viendra probablement pas de nous — c'est le premier mur

**Mesuré le 05/09.** Le stub HAAPI n'émet **aucun jeton de jeu à lui** : il retient le jeton
d'entrée accepté par `SignOnWithToken` et le réutilise tel quel
(`haapi-stub/haapi_stub_v2.py`, commentaire lignes 105-115). Le ticket que le vrai client
présentera vient donc très probablement de cette chaîne-là, **pas de notre phase nue** — et
notre registre le refusera, à juste titre, puisqu'il ne l'a jamais émis.

**Symptôme attendu** : dans le journal, `REFUS/REFUSED : ticket refusé / ticket refused:
UnknownOrConsumed`, puis la connexion se ferme, et le client reste sur son écran de chargement.

**Le contournement, et c'est le premier commutateur à basculer** :

```bash
dotnet run --project src/Namaste3.Server.Connection -- --ticket-externe
```

Le serveur accepte alors **tout ticket non vide** et le journalise nommément. C'est un
affaiblissement RÉEL du garde, dit comme tel au démarrage (`garde de ticket : DESSERRÉ`) et
éprouvé dans les deux sens par un test. Il existe pour la première mise en route, **pas pour
tourner ainsi** : le refermer est la première chose à faire une fois la chaîne de jetons
branchée bout en bout.

### 4.2 La place du message « accès accepté » est DÉDUITE

La source envoie « accès accepté + liste des serveurs » en réponse au **premier** frame nu, et
note elle-même que ce peut être une simplification : elle n'a pas recroisé ce point avec une
capture. Nous faisons pareil, et nous journalisons la branche et l'identifiant de **chaque**
trame nue reçue — c'est ainsi qu'on verra ce que le vrai client fait, au lieu de le supposer.

**Si l'écran de sélection de serveur reste vide**, c'est ici qu'il faut regarder en premier : le
journal dira si le client a envoyé un serverId dès sa première trame (auquel cas il attend
peut-être le ticket tout de suite, pas la liste).

### 4.3 La bascule de phase se fait par le CONTENU — limite connue et testée

La phase est décidée sur la première trame par la présence du préfixe `type.ankama.com/`. Une
**première** trame de jeu dont le typeUrl serait abîmé est donc **indiscernable** d'une trame de
connexion nue, et part dans la phase nue au lieu d'être refusée. Ce n'est pas un défaut
d'implémentation, c'est la propriété d'un critère de contenu ; un test le nomme
(`LimiteConnue_UnePremiereTrameAbimeeEstPriseePourUneTrameNue`).

**Symptôme** : le client reçoit une liste de serveurs alors qu'il présentait un ticket.
**Le remède** : la variante à deux ports prévue par `DECISIONS.md` D-03, qu'un seul paramètre
suffit à activer — `--annonce-ports 5556` et un second serveur sur 5556.

### 4.4 Les valeurs sont inventées ; seules les FORMES sont vérifiées

Un seul personnage, en dur dans la table : nom, niveau, race, apparence, identifiant — **tout
est inventé**. Ce qui ne l'est pas, ce sont les numéros et types de champ, chacun tiré du dump
de notre client (`il2cpp.cs:ligne`) et, pour la liste de personnages, **recoupé sur une trame
réelle décodée le 05/09** (voir §5).

Aucune donnée de compte tiers n'est reprise : le nom du personnage de la capture n'apparaît
nulle part.

### 4.5 Ce qui n'est pas servi du tout

- **`jss` (qui est sur la carte)** : pas émis. La carte se dessinera **vide** — aucun avatar,
  aucun PNJ, aucun monstre. C'est la prochaine brique, et c'est la plus grosse : la source
  avertit qu'un champ `f6` à zéro y fait planter le client dans son affichage de carte.
- **Le déplacement, le changement de carte, le combat** : rien.
- **Les comptes** : un seul, en dur, identifiant 1. Pas de base de données.
- **`krt`** : reçu, journalisé, aucune réponse — son SENS est inconnu de nos sources
  elles-mêmes, et quatre tables indépendantes répètent la même absence.
- **Le troisième champ du protocole de connexion nu (`mhn`)** : parsé génériquement, donc jamais
  perdu, mais rien n'en est fait.

### 4.6 RESTE-À-FAIRE hors de cette zone : trois opcodes figés dans les tests du codec

`codec/tests/Namaste3.Codec.Tests/NegativeTests.cs` fige `type.ankama.com/jru` aux
lignes **164**, **181** et **335**. La gate `gate-proto-sync.py` en est rouge. **Je n'ai pas
touché au codec** — mon serveur le référence sans le modifier, et un seul écrivain par dépôt.

**Mais les trois lignes ne sont pas le même cas, et les traiter pareil abîmerait la troisième.**
Mesuré le 05/09 :

| Ligne | Test | L'opcode y sert à quoi | Ce qu'il faut en faire |
|---|---|---|---|
| 164 | `RootWithoutCase_IsNamed` | **remplissage** — aucune assertion ne le regarde | remplacer par une constante `FillerOpcode` documentée, non liée par aucune build |
| 181 | `RootWithTwoCases_IsNamed` | **remplissage** — idem | idem |
| 335 | `WellFormedSyntheticFrame_IsAccepted` | **charge sémantique réelle** : le test asserte `Assert.Equal("jru", …)` et décode `jru { f2: mapId }` avec le `mapId` d'une capture réelle | **garder le littéral**, marqué `TEST_ONLY` et commenté |

Pourquoi la ligne 335 doit garder son littéral : ce test est une **seconde transcription
indépendante** d'un fait mesuré sur une capture. Le faire lire la table de liaison le ferait
comparer la table à elle-même — si la table était régénérée de travers, le test resterait vert.
C'est exactement le motif « vérifier par le même chemin est un tampon, pas une mesure », et c'est
la même raison qui me fait garder l'ordre de la rafale en dur dans `SequenceTests`.

---

## 5. La mesure qui a tranché la forme de la liste de personnages

Le point le plus délicat de la soirée, et il vaut d'être écrit parce qu'il a failli partir de
travers.

La transcription de la séquence donne, pour une entrée de la liste :
`f1 { f2:nom, f3:niveau, f4 { f2:sexe, f6:apparence, f7:race } }, f2: characterId`.

Le `.proto` reconstruit, lui, décrit `lpg { f1: lpe, f2: int64, f3: lpj }` avec
`lpe { f1: repeated bool, f2: string, f3: int32, f4: bool, … }` — et un `f4` **booléen** ne peut
pas porter le sous-message que la transcription y met. **Les deux sources semblaient se
contredire.**

Ce qui a tranché n'est ni l'une ni l'autre : c'est **une trame réelle**. La capture
`world_etapa1_tras_elegir_personaje.bin`, à l'offset 138, porte un message « personnage
sélectionné » — et le dump prouve qu'il enveloppe **exactement le même type `lpg`** que la liste
(`kuy { lpg = 1 }`, `il2cpp.cs:998547`). Décodée, cette trame donne :

```
f1 > f1 > { f1 { f2:"<nom>", f3:varint, f4 { f1:date, f2:len(0), f4:date, f6:{apparence}, f7:11 } },
            f2:varint }
```

Trois accords indépendants avec la transcription, sur des octets réels : le nom en `f2`, le
sous-message **vide** en `f4.f2` quand le sexe vaut 0 (règle que la transcription énonce
explicitement), et la race en `f4.f7`. **La transcription était juste ; c'est ma lecture du dump
qui était fausse.**

**Leçon d'instrument, et elle m'a coûté du temps** : mon extracteur associait chaque
`public const int X = N;` au **champ typé qui le suit**. Cette heuristique est fausse dès qu'un
`oneof` est présent — les membres d'un `oneof` partagent un seul stockage `private object`, donc
les constantes et les champs ne s'alignent plus. Les **propriétés** (`public lpd.lpc gclb { get;
set; }`), elles, portent le vrai type. *Un extracteur qui suppose un alignement produit des types
plausibles et faux, exactement là où le protobuf est le plus subtil.*

## 5 bis. La gate ne s'exempte pas elle-même — mesuré ici, le 05/09

Première version de `gate-serveur.sh` : son étape « commentaires » scannait `src/`, `tests/` et
`protocol/`. Elle rendait **VERT**. Or `gate-serveur.sh` lui-même était **ROUGE** sur cette même
gate — deux de ses fonctions n'étaient pas commentées.

Le vert était donc exact **et** trompeur : il portait sur trois répertoires, pas sur l'étage.
*Une gate qui choisit son propre périmètre finit par s'en exclure, et le fait sans mentir —
c'est ce qui la rend difficile à voir.* Corrigé en scannant **tout l'étage** ; le compte est passé
de « 19 fichiers » à « 20 fichiers », et c'est ce vingtième qui manquait.

---

## 6. Ce que la gate mesure vraiment (et ses angles morts)

`./gate-serveur.sh` — rejouable, déterministe, 0 jeton.

| Étage | Ce qui est vérifié |
|---|---|
| 0 | la table de liaison est **régénérable à l'identique** (sinon elle est périmée), + son sha256 |
| 1 | `dotnet build` |
| 2 | `dotnet test` — **36 tests** |
| 3 | **0 opcode littéral** dans `src/` |
| 4 | la gate de commentaires de l'étage 5 rend **VERT** sur les 20 fichiers de l'étage, **`gate-serveur.sh` compris** — elle ne s'exempte pas elle-même (cf. §5 bis) |
| 5 | aucun fichier ≥ 500 lignes |
| 6 | le binaire **refuse de démarrer** sur une table incohérente |
| 7 (`--epreuve`) | trois sabotages, chacun avec son **témoin positif** : un opcode planté dans `src/` doit être **VU** ; l'ordre de la rafale inversé doit rendre les tests **ROUGES** ; un numéro de champ faussé (`kvl.f1`, un booléen) doit rendre un **REFUS nommé** |

**Angles morts, nommés** :

- **La gate ne prouve pas qu'un client vivant accepte ce que nous émettons.** Le round-trip
  prouve la fidélité au format, pas l'acceptabilité. Cette preuve-là est un **écran**, pas un
  test — et c'est exactement ce qui reste à faire.
- Le sens **C2S n'est éprouvé sur aucune trame réelle** : nous n'avons aucune capture
  client→serveur. Toutes les trames de nos faux clients sont **synthétiques**.
- La **rafale de bienvenue n'existe dans aucune capture** de ce VPS. Son ordre vient d'une
  transcription de code, corroborée par les formes du dump — pas d'octets observés.
- Les trois captures rejouées sont des blocs d'**entrée monde**. Ni la connexion, ni la rafale,
  ni la sélection de personnage n'y figurent.
- Le test de socket (`LoopbackTests`) parcourt `TcpServer`, mais sur **loopback** : il ne dit
  rien d'un réseau réel, d'un pare-feu, ni de la latence.

---

## 7. Arborescence

```
server/
├── Namaste3.Server.sln · gate-serveur.sh · RUNBOOK-SERVEUR.md
├── protocol/
│   ├── generer-binding.py          générateur déterministe, recroise l'étage 1
│   └── binding-3.6.10.10.json      LE seul fichier qui nomme des opcodes
├── src/Namaste3.Server.Connection/ (net8.0, référence le codec de l'étage 2, max 460 lignes)
│   ├── SemanticOp.cs         les noms sémantiques stables
│   ├── FieldSpec.cs          la forme d'une charge, en donnée + son encodeur
│   ├── FieldSpecReader.cs    JSON -> arbre de champs, refus nommé sur type inconnu
│   ├── OpcodeTable.cs        la table chargée au démarrage
│   ├── GameEnvelope.cs       émission d'une trame de JEU (enveloppe + Any + longueur)
│   ├── ConnectEnvelope.cs    le protocole de connexion NU (phase 1)
│   ├── TicketRegistry.cs     tickets à usage unique, horloge injectée, verdicts nommés
│   ├── ConnectionSession.cs  la machine à états, sans aucun socket
│   ├── TcpServer.cs          la SEULE couche qui touche un socket
│   ├── ServerOptions.cs      configuration + source d'injection
│   ├── FrameLog.cs           le journal, notre instrument d'observation
│   └── Program.cs            point d'entrée
└── tests/Namaste3.Server.Tests/  36 tests
    ├── FixtureReplayTests.cs      les 3 captures réelles, sha vérifiés
    ├── RoundTripEmissionTests.cs  ce que NOUS émettons se re-décode en lui-même
    ├── SequenceTests.cs           le faux client joue tout le scénario
    ├── NegativeTests.cs           les témoins négatifs, chacun avec son témoin positif
    └── LoopbackTests.cs           l'unique épreuve qui passe par un vrai socket
```

---

## 8. Si le client ne montre rien — l'ordre dans lequel regarder

1. **Le serveur a-t-il vu une connexion ?** Le journal imprime `connexion acceptée`. Sinon, le
   client ne vient pas jusqu'ici : vérifier le stub HAAPI et le port 18420.
2. **Quelle phase a été décidée ?** Le journal l'imprime sur la première trame. Si c'est `Game`
   alors qu'on attendait `Naked`, le client saute la sélection de serveur — passer
   `--ticket-externe` (§4.1).
3. **Un refus nommé ?** Chercher `REFUS/REFUSED` dans le journal. Le motif est distinct pour
   chaque cause : ticket vide, inconnu, expiré, sélection avant ticket, mauvais personnage.
4. **La rafale est-elle partie ?** Le journal imprime `rafale émise / burst emitted: 15 messages`.
   Si oui et que l'écran reste vide, le problème est dans le CONTENU d'un message, pas dans la
   séquence — et c'est le §4.4 qu'il faut creuser, avec l'arbre des champs du journal.
5. **Un opcode non lié ?** Le journal l'écrit `(non lié / unbound)` avec ses octets. C'est la
   liste des prochaines briques, donnée par le client lui-même.
