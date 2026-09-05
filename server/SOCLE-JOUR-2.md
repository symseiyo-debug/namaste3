# SOCLE JOUR 2 — l'organisation du serveur 3.0 et le plan de la journée

> **Étage 3.** La page d'accueil du 05/09 : ce qui existe (remesuré), comment le serveur s'organise,
> ce qu'on fait aujourd'hui dans l'ordre, et ce qui attend ta main.
>
> **Sources lues** : le brief initial du projet · `ARCHITECTURE.md`, `DAG.md`,
> `INTERFACES.md`, `DECISIONS.md`, `DONNEES-3.0-CARTE.md`, `CONTRAINTES-VS-CHOIX.md` · les 64
> fragments de `internal/` (racine, `internal/third-party-review/`, `internal/third-party-review/`) ·
> `tools/protocol-mapping/matcher/RAPPORT-MATCHER-V4.md` et `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv` ·
> `tools/protocol-mapping/index/RAPPORT-INDEX.md`, `tools/protocol-mapping/index/STABILITE-BUILDS.md` ·
> `codec/CODEC.md`, `internal/haapi-stub/CARTE-HAAPI.md`,
> `internal/bot-testeur/SPEC.md` · les 4 récoltes `internal/haapi-stub/resultat-g2-*/` ·
> `protocol/extract/proto-sync/PROTO-SYNC.md`, `tools/community/cartes/RAPPORT-CARTES.md`,
> `tools/community/chaine/ETAT.md`.
>
> **Toutes les gates de ce document ont été RELANCÉES par moi**, jamais recopiées d'un rapport
> (cahier §6). Heure de mesure : **2026-09-04 entre 21:55 et 22:50 UTC** (= 05/09 00:00-00:50 heure
> locale). `PROD-DB` (base de production) : jamais ouvert, jamais cité.
>
> ⚠️ **D'autres chantiers écrivaient encore pendant que je mesurais.** Deux passes de `gate-forme.py` à 20 min
> d'écart ne rendent pas le même ensemble de rouges : `internal/reference-fragments/launcher-actuel-2026/haapi-cdn-launcher-2026.md`
> est passé ROUGE → VERT entre les deux (mtime 00:38 local, entre mes deux passes). Les chiffres
> ci-dessous portent leur heure ; un compte de fragments relu ce matin peut avoir bougé.

---

## 0. En dix lignes

1. Le seul verrou dur du design v0 — la géométrie des cartes — **est tombé cette nuit** : 17 353
   cartes × 560 cellules × 17 champs sont extraites, gate verte. `J3.B` n'est plus BLOQUÉ, il est FAIT.
2. La table de dispatch **existe déjà**, générée depuis notre dump : 2 206 messages, 6 278 champs.
3. Le codec, le bot-testeur, le dump : **trois gates vertes, remesurées ce soir**.
4. `G1` reste rouge sur **un seul** opcode, `krt`, et sur son SENS — pas sur sa forme.
5. Le chaînon manquant côté code, c'est **le chargeur de la table** (~50 lignes) et **rien d'autre**.
6. Le serveur de connexion a commencé à s'écrire **pendant que je rédigeais** : 10 fichiers en 45 min.
7. Le vrai premier obstacle n'est pas le protocole : **le client ne sait pas où aller**, et il ne
   nous parle même pas encore.
8. **Trois** essais tranchent ce point, tous sur **ton PC** : c'est la seule chose de la journée qui
   te demande la main. Le troisième, apparu cette nuit, donne en prime la capture qui nous manque.
9. Tout le reste (socle .NET, chargeur, import des cartes, scénarios du bot) tourne sur le VPS
   **sans toi**, en parallèle.
10. Trois décisions t'attendent, chacune avec un défaut choisi si tu ne réponds pas : `OPEN-QUESTIONS.md`.

---

## A. Inventaire mesuré

### A.1 Ce qui existe, étage par étage

| Étage | Ce qui existe | Chiffres remesurés par moi | Gate |
|---|---|---|---|
| **0 — dump** | dump IL2CppInspector-Redux, 143 DLL fantômes | 1 003 noms de protocole, 0 inventé, 2 319 classes `IBufferMessage`, 1 081 733 lignes de C# | 🟢 |
| **1 — carte** | 64 fragments (8 racine · 33 en 6 lots · 23 en 8 lots tiers) + 10 rapports | `gate-forme` : **55 VERT / 9 ROUGE** ; `gate-g1` : 32/32 couverts, **31/32 conformes** | 🔴 |
| **2 — codec** | `codec/`, 12 fichiers source, 71 tests | **355 trames réelles** round-trip byte-exact, sha identiques avant/après | 🟢 |
| **2 — bot** | `internal/bot-testeur/`, 3 scénarios canoniques | **21 tests**, deux exécutions du même scénario → **même sha256** | 🟢 |
| **2 — stubs** | stub Zaap v6, stub HAAPI v2, relais, 4 récoltes G2 | **3 `connect` + 3 `settings_get`** ; **4 requêtes HTTP**, toutes vers un seul hôte | 🔴 |
| **3 — serveur** | 8 documents + le serveur de connexion **en cours d'écriture** | **10 fichiers `.cs`** à 22:50 UTC (0 à 22:05 — cf. §A.4) | — |
| **5 — proto-sync** | 5 scripts + artefacts générés | **2 206 messages**, 6 278 champs, 32/32 du chemin critique présents | 🔴 |
| **5 — cartes** | extracteur + 17 353 fichiers de sortie | **9 717 680 cellules**, dont 4 826 720 marchables | 🟢 |
| **5 — chaîne** | 8 outils rejouables + état par build | 3.6.4.3 téléchargée (149 Mo) ; 3.6.10.11 non prise | 🔴 |
| **5 — commentaires** | gate transversale | **89/105 VERT**, 16 ROUGE, moyenne 89,6 % | 🔴 |

### A.2 Les gates, relancées une par une

**VÉRIFIÉ — `gate-g0.py --epreuve` rend rc=0**, source `tools/client-dump/gate-g0.py:200-225`.
Trois cas joués : le dump réel passe (aucun refus) ; +100 noms fantômes dans la référence fait
rougir (couverture 90,9 % < 95 %) ; +1 nom inventé dans le dump fait rougir. **La gate mord dans
les deux sens.** J'ai employé `--epreuve` exprès : la forme sans argument RÉÉCRIT
`internal/GATE-G0-RAPPORT.md`, hors de ma zone.

**VÉRIFIÉ — `gate-g1.py` rend rc=1**, source `tools/protocol-mapping/tools/gate-g1.py:277-289`. 32 opcodes du
chemin critique, **32 couverts, 31 conformes**. Refus unique et nommé : `krt`, « tag contient DÉDUIT ».
Son tag exact dans la carte est « VÉRIFIÉ (forme) / DÉDUIT (sens) » — nous savons à quoi il ressemble,
pas ce qu'il veut dire. C'est le seul écart entre G1 et le vert.

**VÉRIFIÉ — `gate-codec.sh` rend rc=0**, source `codec/gate-codec.sh:12-15`. Build,
puis **71 tests, 0 échec**, puis round-trip fixture par fixture : 322 trames / 2 / 31 = **355**, sha256
identiques avant et après ré-encodage sur les trois. 42 + 2 + 17 opcodes distincts rencontrés.

**VÉRIFIÉ — le bot-testeur est déterministe**, source `internal/bot-testeur/SPEC.md:172-192`.
Relancé : `dotnet test` rend **21 passés, 0 échec** ; le scénario `chemin-critique` joué deux fois avec
la même graine rend deux fois le sha256 `05439ec4…`, 8 501 octets. Rejouable, donc utilisable comme gate.

**VÉRIFIÉ — `gate-cartes.py --epreuve` rend rc=0**, source `tools/community/cartes/gate-cartes.py:20-26`.
Les cinq épreuves passent, dont le sabotage (une cellule inversée dans une copie fait rougir avec un
refus nommé) et le témoin négatif (un identifiant de carte inventé est absent, sans exception).

**VÉRIFIÉ — `gate-proto-sync.py --epreuve --rapide` rend rc=1**, source
`protocol/extract/proto-sync/gate-proto-sync.py:24-30`. Cinq témoins joués, **un seul refus** : trois
adresses d'opcode figées en dur dans `codec/tests/Namaste3.Codec.Tests/NegativeTests.cs:164`,
`:181` et `:335`. Les quatre autres témoins sont verts, dont le sabotage et le témoin négatif.

**VÉRIFIÉ — `gate-commentaires.py` rend rc=1** sur tout le chantier, source
`tools/community/gate-commentaires.py:11-21`. 89 fichiers verts sur 105. Les 16 rouges se concentrent
sur **le code C# du bot-testeur** (10 fichiers, de 16,7 % à 60 % de fonctions commentées) et sur deux
scripts du stub HAAPI. Décision du porteur du projet, du 04/09 (« tu me commentes tout le code ») : ce sont les
livrables de l'étage 2 qui ne le respectent pas encore, pas l'outillage de l'étage 5.

### A.3 Ce que la nuit a changé, et que le design v0 ne sait pas encore

**VÉRIFIÉ — la géométrie des cartes n'est plus un trou.** `ARCHITECTURE.md:496-499` écrit « les
bundles de scène n'existent nulle part sur ce VPS » et « il demande une main humaine » ; `DAG.md:169-188`
classe `J3.B` **BLOQUÉ**. Mesuré ce soir : les 577 bundles sont sur le disque, l'extraction a tourné en
11 min 54 s, elle a écrit 17 353 cartes, et la gate est verte —
`tools/community/cartes/RAPPORT-CARTES.md:139-157`. **Le seul verrou dur du design v0 a disparu pendant
qu'il était écrit.**

**VÉRIFIÉ — et la gate de `J3.B`, telle qu'elle est écrite, refuserait le bon résultat.**
`DAG.md:208-210` exige « son `cells` fait 560 octets et compte **exactement 230 cellules marchables** ».
Mesuré dans le bundle : Astrub porte **360** cellules marchables, pas 230. Le 230 vient d'un fichier
dérivé qui **rogne les bords exprès** pour que les groupes de monstres n'y apparaissent pas —
`refs/JondoEmu/docs/world.md:48`, et le serveur de référence refuse lui-même de s'en servir pour la
marchabilité, `refs/JondoEmu/Jondo.Unity.Server/Handlers/WorldMoveHandler.cs:442-445`. Une gate bâtie
sur 230 aurait gravé en vert une valeur que sa propre source déclare inadaptée. Ce qui la remplace est
plus fort : deux **égalités d'ensemble exactes** contre un fichier produit hors de notre chaîne
(357 = 357 et 85 = 85 sur Astrub, 17 174 cartes sur 17 174 comparables), plus une inclusion des 230.
La même valeur périmée vit dans `INTERFACES.md:279` (« 230 vraies sur 560 ») et
`ARCHITECTURE.md:271-284` : **trois fichiers à corriger ce matin.**

**VÉRIFIÉ — la table de dispatch existe, générée, avec sa provenance.**
`ARCHITECTURE.md:352-368` et `INTERFACES.md:117-132` la décrivent comme un fichier à produire.
Mesuré : `protocol/extract/proto-sync/out/` porte déjà la table pour notre build, **2 206 entrées**,
chacune avec sa source `il2cpp.cs:ligne`, sa direction et son statut de nom — 99 attestés par capture
tierce, 67 déduits par structure, 1 463 sans nom, `protocol/extract/proto-sync/PROTO-SYNC.md:73-88`.
Le format à adopter est **celui-là**, pas un format à réinventer.

**VÉRIFIÉ — le chaînon manquant côté code est nommé et petit.**
`protocol/extract/proto-sync/PROTO-SYNC.md:222-224` : « le chargeur, côté serveur […] il n'existe pas […]
c'est ~50 lignes, et c'est le seul chaînon manquant côté code ».

**VÉRIFIÉ — la seconde build est là, et le multi-build est arrêté.** 3.6.4.3 est téléchargée
(149 Mo, deux empreintes distinctes de la nôtre), et le portage a été arrêté le 05/09 —
`tools/community/chaine/ETAT.md:89-95`. Ce que la mesure laisse acquis : entre les deux builds, **61,7 %
seulement des noms clairs survivent**. Un handler ne peut s'ancrer ni sur le jeton obfusqué ni sur le
nom clair : il s'ancre sur le nom sémantique d'une table régénérée.

**DÉDUIT — `tools/community/chaine/ETAT.md` a vieilli en quelques heures.** Son tableau de tête écrit
« cartes ❌ » et « `.proto` ❌ » pour notre build ; les deux sont livrés depuis. Un tableau d'état daté
de 22:10 et relu à 08:00 se lit comme actuel. **Comment vérifier** : comparer sa ligne 3.6.10.10 à
`tools/community/cartes/RAPPORT-CARTES.md` et `protocol/extract/proto-sync/PROTO-SYNC.md`, tous deux
postérieurs. C'est une correction d'une ligne, à faire par son écrivain, pas par moi.

### A.4 Ce qui a bougé PENDANT que j'écrivais (mesuré à 22:50 UTC)

Deux choses sont arrivées entre le début et la fin de ce document. Les consigner vaut mieux que de
rendre un inventaire déjà faux.

**VÉRIFIÉ — le serveur de connexion s'écrit en ce moment.** À 22:05 UTC, `server/` portait
**0 fichier `.cs`**. À 22:50, il en porte **10**, dans `server/src/Namaste3.Server.Connection/`,
plus un générateur et sa table dans `server/protocol/`. Conséquence directe : **le nom des
projets du §B.1 n'est plus à décider, il est à ADOPTER.** L'écrivain vivant a choisi
`Namaste3.Server.Connection` ; renommer sa zone pendant qu'il y travaille serait un second écrivain
sur son fichier. Le §B.1 ci-dessous décrit donc la cible, et le premier geste du matin est de la
réconcilier **avec lui**, pas contre lui.

**VÉRIFIÉ — il existe maintenant DEUX tables qui nomment des opcodes, et elles portent deux builds
différentes.** `protocol/extract/proto-sync/out/dispatch-3.6.10.10.json` porte **2 206 messages**, générés
depuis le dump, chacun avec sa source et son statut de nom.
`server/protocol/binding-3.6.10.11.json` porte **25 messages**, le chemin critique seulement,
avec en plus **la charge exacte à émettre** pour chacun des 15 messages de la rafale — ce que la
première n'a pas. Les deux se déclarent « le seul fichier qui nomme des opcodes ». Elles ne sont pas
en conflit, elles sont **complémentaires** : l'une donne la forme de tout le protocole, l'autre le
contenu à émettre sur le chemin critique. Mais deux producteurs de la même chose finissent par
diverger. **À trancher au premier geste du matin**, avec l'écrivain vivant.

**VÉRIFIÉ — la seconde table déclare honnêtement son écart de build** : son champ de build dit
3.6.10.11, son champ de build des mesures dit 3.6.10.10. C'est la bonne façon de le faire. Rappel du
le brief initial : les deux binaires ont **le même sha256**, donc le protocole n'a pas bougé entre ces deux
étiquettes. Les deux tables décrivent bien le même protocole.

**DÉDUIT — cinq des noms sémantiques de la seconde table sont des ÉTIQUETTES DE PLACE, pas des sens
mesurés.** Les messages de la rafale que personne n'a nommés y reçoivent des noms de commodité. Un nom
de commodité qui a la forme d'un nom sémantique se cite ensuite comme s'il était mesuré. **Comment
vérifier** : croiser ces cinq entrées avec `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv`, qui les
liste précisément comme **sans nom**. Ce n'est pas une faute — il faut bien les appeler quelque chose
pour les émettre — mais leur statut doit être écrit dans la table, comme la table de proto-sync le
fait pour ses 1 463 entrées sans nom.

**VÉRIFIÉ — un banc d'essai Jondo a été empaqueté à 22:50** : `etage2-socle/banc-jondo/`, avec son
mode d'emploi, un analyseur de trafic et un paquet prêt à déposer sur le PC personnel du porteur du projet. Ce que ça change
pour la journée est au §C.1 : **c'est un troisième essai, et probablement le plus rentable.**

---

## B. L'organisation du serveur 3.0

### B.1 L'arborescence des projets

```
server/
├── Namaste3.sln
├── protocol/
│   └── dispatch-3.6.10.10.json      DONNÉE, copiée de proto-sync, JAMAIS éditée à la main
├── src/
│   ├── Namaste3.Protocol/           le CHARGEUR de la table + les types générés
│   ├── Namaste3.Net/                transport, dispatch, handlers — SEULE couche qui voit les deux
│   ├── Namaste3.World/              le DOMAINE — Area, Map, Character, Path
│   ├── Namaste3.Store/              Postgres, migrations, journal d'audit, trace causale
│   ├── Namaste3.Server.Connection/  exécutable, phase de connexion, protobuf nu   ← EXISTE DÉJÀ
│   └── Namaste3.World.Host/         exécutable, phase de jeu, enveloppe et opcodes
├── tools/                           les gates de cet étage
├── devlog/                          une entrée de journal par jalon (déjà écrites, cf. §C)
└── tests/
```

⚠️ **Le nom du projet de connexion n'est pas une proposition : il est mesuré.** Son écrivain l'a créé
pendant que ce document s'écrivait (§A.4). C'est la cible qui s'aligne sur lui, jamais l'inverse
pendant qu'il travaille.

Le codec **n'est pas recopié** : `codec/` est référencé en projet. Un seul écrivain par
zone (cahier §6, anti-drift) — nous le consommons, son auteur le maintient.

### B.2 Les six frontières, chacune avec sa gate déterministe

| # | Frontière | La gate, mesurable | Contre-mesure |
|---|---|---|---|
| 1 | Le domaine n'importe **jamais** le protocole | compter les fichiers de `src/Namaste3.World/` qui importent le protocole → **0** | 414 sur 571 (72,5 %) chez Giny, `ARCHI-REFERENCE-GINY.md` §G.3 |
| 2 | **Aucun opcode en dur** nulle part | témoin (a) de `protocol/extract/proto-sync/gate-proto-sync.py` étendu à `server/` → 0 refus | 3 refus mesurés ce soir dans les tests du codec |
| 3 | **Area mono-thread**, garde par le TYPE | un fichier fautif doit **ne pas compiler** ; le même avec le jeton doit compiler | le garde runtime de Jiva s'oublie ; `ARCHI-REFERENCE-GINY.md` §B.1 annote « thread safe » à tort |
| 4 | Le chemin **n'a pas de constructeur** accessible | compter `new Path(` hors du fichier qui le définit → 0 | aucune référence n'a les 4 contrôles, `ARCHITECTURE.md:396-410` |
| 5 | Fichiers **< 500 lignes** | lister les fichiers de `src/` d'au moins 500 lignes → vide | règle du projet |
| 6 | La **dette est branchée** | le démarrage journalise N entrées, N == le compte par recherche | chez Giny l'analyseur n'est jamais appelé, `ARCHI-REFERENCE-GINY.md` §G.2 |

**La frontière n°3 mérite sa phrase.** Le garde d'Area n'est pas un `if` que l'auteur doit penser à
écrire : c'est un jeton non fabricable hors de la boucle, que toute mutation du domaine exige en
paramètre. Une mutation hors Area devient une **erreur de compilation**. C'est la seule forme de garde
qui survit à la précipitation — `DECISIONS.md` D-04.

**La gate n°3 se prouve dans les deux sens ou elle ne prouve rien.** Une gate écrite en assertant le
NOM du garde est toujours verte. Celle-ci compile du code fautif et **exige l'échec**, puis compile le
même code conforme et exige le succès.

### B.3 Où se branche chaque ressource de la nuit

| Ressource | Où elle entre | Sous quelle forme |
|---|---|---|
| Codec 3.0, `codec/` | `Namaste3.Net` | référence de projet ; sa façade rend opcode, sens, identifiant de requête et charge brute |
| Table de dispatch, `protocol/extract/proto-sync/out/` | `protocol/` puis `Namaste3.Protocol` | **donnée** chargée au démarrage, indexée par nom sémantique et par opcode |
| 17 353 cartes, `tools/community/cartes/sortie/cartes/` | `Namaste3.Store` puis `Namaste3.World` | import déterministe → table des cartes : identité, sous-zone, 560 cellules, 4 voisins, interactifs |
| Matcher, `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv` | **aucun code** | le cahier des charges de la capture : 8 opcodes du chemin critique restent sans nom |
| Bot-testeur, `internal/bot-testeur/` | la gate de **chaque** jalon | via un adaptateur qui implémente le port déjà défini, `SPEC.md:194-223` |
| Récoltes G2, `internal/haapi-stub/resultat-g2-*/` | l'essai « où aller » | 4 récoltes, l'unique matière sur le comportement réel du client |
| Fragments, `internal/third-party-review/` et `internal/third-party-review/` | le journal | chaque jalon nomme les fragments qui doivent avoir été lus |

### B.4 Ce qui change dans le design v0, et ce qui ne change pas

**Ne change pas** — deux processus joints par un ticket en base plutôt que par un canal applicatif
(`DECISIONS.md` D-01, D-02) ; l'Area comme unité de sérialisation (D-05) ; les quatre contrôles de
déplacement (D-06) ; le domaine sans le protocole (D-07) ; la table régénérée (D-08) ; l'autorité de
forme sur notre dump (D-09). Ces six décisions reposent sur des mesures que la nuit n'a pas bougées.

**Change** — quatre points, chacun avec sa mesure au §A.3 : `J3.B` passe de BLOQUÉ à FAIT ; sa gate
passe de « exactement 230 » à une inclusion plus deux égalités d'ensemble ; la table de dispatch passe
de « à produire » à « produite, format arrêté » ; et le premier obstacle réel de `J3.1` n'est plus le
protocole nu mais l'adresse (§C.1).

---

## C. Le chemin critique de la journée

Deux voies avancent en parallèle. **La voie VPS ne t'attend pas.** La voie PC te demande la main, une
fois, pour un essai de dix minutes.

```
VOIE VPS (sans toi)          J-0 dettes ──► J-2 socle à vide ──► J-3 connexion ──► J-4 rafale
                                  │                                   ▲
VOIE PC (avec toi)           J-1 « où aller ? » ─────────────────────┘
                                                     puis  J-5 perso ─► J-6 Astrub ─► J-7 déplacement
```

### C.0 — J-0 : solder les rouges bon marché (déterministe, 0 IA)

**Entrée** — les trois refus mesurés au §A.2.
**Répartition du travail** — aucune : trois gestes scriptés (déterministes, 0 IA).
**Gate** — `gate-proto-sync.py --epreuve` passe de rc=1 à rc=0 ; `gate-forme.py` sur les 9 fragments
rouges passe à 0 rouge ; les trois fichiers qui portent encore « 230 marchables » sont corrigés.
**Ce qui est faux si** — on fait verdir `gate-forme` en retirant les entrées taguées au lieu de leur
ajouter leur source : ce serait rendre l'instrument vert par l'instrument. Faux aussi si on retire
`krt` du chemin critique pour faire verdir G1 (`DAG.md:95-97` le nomme déjà comme piège).

### C.1 — J-1 : **dire au client où aller** (le vrai premier obstacle)

**Ce qui est mesuré, et qui n'est pas ce que le design v0 croyait.** Sur les 4 récoltes G2, le client
compose le launcher (**3 `connect`, 3 `settings_get`**, rien d'autre), puis échoue dans le chargement
de sa configuration externe — la pile d'appel du journal montre une exception levée dans la méthode qui
télécharge le texte. Et il n'émet en tout que **4 requêtes HTTP**, toutes vers un seul hôte,
`launcher.cdn.ankama.com`, relayées en 200 par notre propre relais. **Zéro requête vers l'hôte HAAPI que
notre stub sert.** Le stub n'est donc pas en train de mal répondre : **il n'est jamais appelé.**

**Deux essais tranchent, et ils ne coûtent presque rien.**

**Essai A — le sélecteur d'hôte natif du client.** L'écran de login porte, en clair dans le binaire, un
conteneur de sélection de port et une liste déroulante d'hôte — `il2cpp.cs:390916-390951`, relevé par
`internal/third-party-review/client-3.0-clair/login-pregame-ecrans.md:47-71`. **VÉRIFIÉ** que le champ existe et
son type ; **DÉDUIT** qu'il soit visible en usage normal. **Comment vérifier** : lancer le client, ouvrir
l'écran de login, regarder. Si le sélecteur est là, on tape notre adresse et l'histoire s'arrête : aucun
patch binaire, aucun stub à deviner. **Coût : dix minutes, zéro ligne de code.** C'est de très loin le
meilleur rapport de la journée, et c'est pour ça qu'il passe en premier.

**Essai B — relancer avec les arguments de Jondo.** Notre client a été lancé avec un canal de version
générique. Le serveur de référence lance le sien avec un canal explicite, une connexion automatique et
un port de jeu — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:60-63`. **Cet essai n'a jamais été
fait.** S'il change le comportement, il dit du même coup que le chemin dépend du canal, ce qu'aucune
mesure ne dit aujourd'hui. **Coût : trente minutes, zéro ligne de code.**

**Essai C — faire tourner le serveur de référence contre ton vrai client** (apparu à 22:50, §A.4). Un
paquet complet est prêt : `etage2-socle/banc-jondo/RUNBOOK-BANC-JONDO.md`, six commandes, réversible en
une. Il ne répond pas seulement « où va le client » : **il donne la première capture complète du vrai
client officiel face à un serveur qui répond de bout en bout**, trame par trame, de la connexion à
l'entrée dans Astrub — `etage2-socle/banc-jondo/CE-QUE-JONDO-NOUS-DONNE.md`. Cette capture n'existe
nulle part sur ce VPS : le codec a mesuré que la rafale de bienvenue est **construite en code** et
qu'aucune capture n'en existe (`codec/CODEC.md:132-143`). C'est donc aussi la matière qui
nomme les 8 opcodes restants et qui tranche `krt`. **Coût : dix minutes de mise en place, plus le temps
d'une partie.** Ligne rouge à connaître : **il modifie ton client officiel**, et le mode d'emploi le dit
en première ligne avec sa commande de retour arrière.

**Le meilleur ordre est A, puis C, puis B.** A est gratuit et peut tout fermer. C rapporte le plus par
minute investie, mais touche ton client. B ne coûte rien mais ne rapporte qu'une réponse.

**Répartition du travail** — une passe pour lire les récoltes et écrire les protocoles d'essai ; le test lui-même se joue manuellement.
**Gate** — le journal du client, la sortie du relais, et l'état des connexions réseau, comparés avant et
après. Pour l'essai C, le journal de trafic du serveur de référence. Un essai qui ne change rien est un
résultat, pas un échec : il élimine une branche.
**Ce qui est faux si** — on conclut « le sélecteur n'existe pas » sur une capture d'écran sans avoir
cherché sa condition d'affichage (le corps de la méthode d'activation de l'écran n'est pas décompilé,
`internal/third-party-review/client-3.0-clair/login-pregame-ecrans.md:70`). Faux aussi si on lit un changement
de comportement comme la preuve que le canal en est la cause : les deux essais changent chacun **une**
chose, jamais deux à la fois.

### C.2 — J-2 : le socle qui tourne à vide (`J3.C` + le chargeur)

**Entrée** — `ARCHITECTURE.md` §2, §4, §7 · `INTERFACES.md` §1, §3, §4, §5, §6 ·
`protocol/extract/proto-sync/out/` pour le format de la table · `tools/community/cartes/sortie/cartes/` pour
l'import des cartes.
**Livrable** — les six projets du §B.1 avec **zéro handler métier** : transport, codec branché, table
chargée au démarrage, une Area qui tourne à vide, migrations appliquées, trace causale qui écrit, et
l'import des 17 353 cartes en base.
**Répartition du travail** — 1 passe de supervision (architecture du socle), 2 lots d'implémentation (implémentation cadrée, périmètres disjoints).
**Gate** — les six frontières du §B.2, plus l'import : la carte d'Astrub en base porte sa sous-zone
non nulle, 560 cellules, 360 marchables, et ses 4 voisins égaux à ceux mesurés dans le bundle.
**Ce qui est faux si** — on écrit le chargeur en supposant un format et on adapte la table ensuite. La
table est produite par un outil éprouvé à 6 témoins ; c'est le chargeur qui s'aligne. Faux aussi si le
socle est déclaré vert sur un `dotnet build` : le compilateur ne ferme aucun nœud (cahier §6).

### C.3 — J-3 : le client atteint l'écran de **sélection de serveur**

**Entrée** — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:281-357` (le protocole nu, capture octet
par octet) · `refs/JondoEmu/datos/protocolo_conexion_3.6.10.10.proto:163-178` · le résultat de J-1 ·
J-2.
**Livrable** — l'exécutable de connexion : phase **nue**, sans enveloppe ; racine à **trois** champs ;
émission du compte, des résumés de personnages et de la liste de serveurs ; puis lecture du choix et
émission du ticket avec l'adresse de jeu. Ticket en base, durée de vie courte, usage unique atomique.
**Répartition du travail** — 1 passe de supervision (conception de la phase nue), 1 lot d'implémentation (implémentation).
**Gate** — trois niveaux, le troisième fait foi : le scénario du bot rend OK et deux exécutions sont
identiques ; le décodage croisé de la trame reçue par le sniffer retrouve les champs attendus ; **le
client vivant affiche l'écran de sélection avec le nom de notre serveur**, sans exception au journal.
**Ce qui est faux si** — on n'implémente que deux champs sur la racine parce que le serveur de référence
en omet un (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:906-913`) : le troisième doit être **parsé sans planter**
même vide. Faux aussi si l'écran s'affiche parce que le client a repris une session en cache : la gate
exige un profil neuf.

### C.4 — J-4 : ticket et rafale de bienvenue → écran des **personnages**

**Entrée** — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:367-456` (l'ordre exact des 15 messages,
dont trois de même opcode aux charges **différentes**) · `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:20-140`
(les types de champ manquants) · J-3.
**Répartition du travail** — 1 passe de supervision (séquence et consommation du ticket), 2 lots d'implémentation (constructeurs de messages).
**Gate** — le bot atteint la phase authentifiée avec une liste de personnages non vide ; la trace
serveur porte les 15 messages **dans l'ordre**, 0 permutation ; rejouer le même ticket rend un refus
**nommé** avec un contrôle positif dans la même exécution ; le client vivant affiche l'écran des
personnages et le bouton de création est actif.
**Ce qui est faux si** — la gate d'usage unique est verte parce que le ticket n'a jamais été écrit :
jamais essayé ressemble à jamais réussi, d'où le contrôle positif obligatoire. Faux aussi si le succès
vient d'une barrière voisine : un décodage qui échoue en silence ferait passer le test pour la mauvaise
raison, d'où le refus **nommé**.
**Le manque assumé** — `krt` est toléré sans être jeté en silence, et sa charge réelle est **capturée**
ce jour-là. C'est le seul refus de G1, et il ne se lève que par une capture.

### C.5 — J-5 : sélection de personnage

**Entrée** — `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:144-235` ·
`internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:434-541`.
**Répartition du travail** — 1 passe de supervision, 1 lot d'implémentation.
**Gate** — le bot passe la phase ; **le point dur, adversarial** : un identifiant de personnage
appartenant à un **autre compte** rend un refus nommé, 0 chargement, 1 trace, avec le contrôle positif
dans la même exécution ; et les trois formes de message sont décodées **chacune selon sa propre
déclaration**.
**Ce qui est faux si** — on copie la lecture générique du serveur de référence, qui lit le même champ
pour les trois formes (`COMPLEMENT-CHEMIN-CRITIQUE-G1.md:179-227`). Les trois sont des entiers
variables : ça compile, ça décode, et ça charge le mauvais personnage ou rien. Faux aussi si la gate
adversariale est verte parce que le compte de test n'a qu'un personnage : elle exige **deux comptes
peuplés**.

### C.6 — J-6 : entrée sur la carte d'Astrub

**Entrée** — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:545-670` ·
`internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:239-312` · la table des cartes chargée en J-2.
**Répartition du travail** — 1 passe de supervision (séquence), 2 lots d'implémentation (la structure d'acteurs, la plus lourde du chemin).
**Gate** — l'introspection du bot rend la bonne carte, la bonne cellule et la bonne phase ; forcer un
double envoi du bloc carte fait refuser le second avec une trace, et **0 boucle de rechargement** côté
client ; une sous-zone nulle fait **refuser l'émission** plutôt que d'envoyer un message qui plante le
client ; et le personnage apparaît à Astrub avec sa minimap peuplée.
**Ce qui est faux si** — on rejoue les captures du serveur de référence comme lui : elles portent des
données de compte tiers et servent de preuve de round-trip au codec, jamais de contenu à émettre. Un
message construit depuis une trame rejouée serait un faux vert : le client entre en jeu, et rien de
notre serveur n'a été prouvé.

### C.7 — J-7 : déplacement validé serveur-side

**Entrée** — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:672-698` · `ARCHITECTURE.md` §6.1 ·
les 560 cellules par carte chargées en J-2.
**Répartition du travail** — 1 passe de supervision (conception de la validation), 1 lot d'implémentation (implémentation), 1 passe de supervision (adversarial).
**Gate** — un contrôle positif, plus **cinq scénarios adversariaux qui doivent tous être refusés avec
cinq motifs NOMMÉS DIFFÉRENTS** : mauvaise carte, cellule de départ falsifiée, traversée de mur, saut
non contigu, budget dépassé. Plus la gate de construction : aucun chemin ne se fabrique hors du point
de validation.
**Ce qui est faux si** — les cinq refus sont produits par la **même** barrière. Un test adversarial vert
peut l'être par une autre barrière que celle qu'on croit mesurer : la gate exige cinq motifs distincts,
sinon elle échoue **même si tout est refusé**. Faux aussi si un refus est un silence : le serveur de
référence ignore silencieusement un déplacement à la mauvaise carte
(`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:679-682`), ce qui laisse le joueur figé sans savoir pourquoi.

---

## D. Les questions qui t'attendent

Le détail tient en cinq lignes dans `OPEN-QUESTIONS.md`. Le principe : **chacune a un défaut choisi**,
et si tu ne réponds pas, on avance sur ce défaut plutôt que d'attendre.

1. **Peux-tu jouer les deux essais de J-1 ?** C'est la seule chose de la journée qui te demande la main,
   et elle débloque tout le chemin critique. Défaut sans réponse : on construit le socle et les handlers
   contre le bot seul, et le client vivant reste non prouvé — donc `G3` reste hors d'atteinte.
2. **`krt` : capture ou contournement ?** Défaut : on le tolère sans le jeter, on capture sa charge à
   J-4, et G1 reste rouge jusqu'à la capture. On ne le retire pas de la liste.
3. **Le portage multi-build reste-t-il arrêté ?** Défaut : oui, conformément à ton ordre du 05/09. La
   seconde build reste sur le disque, non dumpée.
4. **Aligne-t-on le schéma de la trace causale avec l'index existant avant d'écrire, ou après ?** Défaut : avant — un schéma décidé
   seul de chaque côté rend deux traces qui ne se joignent pas.
5. **Le code de l'étage 2 doit-il passer la gate commentaires avant qu'on construise dessus ?**
   Défaut : non bloquant, mais compté et affiché ; on ne rouvre pas la zone d'un autre écrivain.

---

## E. Ce qu'on ne fait pas aujourd'hui

- **Le portage multi-build et le ping-pong** — arrêtés sur ton ordre du 05/09 (« osef du portage de
  version pour l'instant, faisons déjà un serveur qui marche »), `tools/community/chaine/ETAT.md:89-95`.
- **La chaîne 2.x** — en pause depuis ton ordre du 04/09, `tools/community/chaine/ETAT.md:9-11`. Le SWF
  2.73 est retrouvé, l'export attend.
- **Le graphe** — il se construit sur une autre machine après sa location, ce n'est pas cette zone.
  Conséquence assumée : l'étage 3 lit des fragments et une table générée, pas un graphe.
- **La largeur** — combat, métiers, guildes, économie. Rien avant que le chemin critique tienne
  bout à bout.
- **L'épuration du code 2.x** — après le graphe, tu l'as dit le 04/09.
- **Le hook dans le client vivant** — il s'exécute sur ton PC, pas sur ce VPS ; il vient après J-1.

---

## F. Mes erreurs, et une hypothèse du brief que la mesure réfute

**Mon erreur d'instrument.** Ma première passe de `gate-forme.py` couvrait **60** fragments ; il y en a
**64**. Trois vivent un niveau plus bas que la convention, parce que leur titre contenait une barre
oblique et que l'outil d'écriture en a fait des dossiers. Une liste construite par un motif à
profondeur fixe rate ce qui est plus profond, **sans le dire**. Corrigé par une recherche récursive.

**Une hypothèse de mon brief, réfutée par les journaux sur disque.** Le brief que j'ai reçu affirme
que le client « demande `userInfo_get` et `auth_getGameToken` quand lancé avec `--gameRelease dofus3
--autoConnectType 1 --connectionPort 18420` ». Mesuré sur les **quatre** récoltes : les seuls appels au
launcher sont **3 `connect` et 3 `settings_get`** — zéro `userInfo_get`, zéro `auth_getGameToken` ; le
client a été lancé avec un **canal générique**, pas le canal `dofus3` ; et le port `18420` n'apparaît
nulle part ailleurs que dans la configuration de **notre propre stub**. La ligne d'arguments citée vient
de `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:60-63` : **ce sont les arguments du serveur de
référence, pas une mesure sur notre client.** Ce n'est pas un reproche, c'est une donnée causale : ça
veut dire que l'essai « lancer avec ces arguments-là » **n'a jamais été fait**, et c'est exactement
l'essai B de J-1. Un mandant qui transmet une hypothèse fausse est une information, pas une gêne à taire
(cahier §6bis).

**Ce que je n'ai pas mesuré, et que je ne prétends donc pas.** Je n'ai pas rejoué `gate-g2.py` contre un
client vivant — il exige ton PC. Je n'ai pas rejoué `gate-cartes.py --corpus` (les deux égalités sur les
17 353 cartes) : seulement `--epreuve`, les 5 épreuves. Je n'ai pas relancé la génération de la table de
dispatch, seulement sa gate en mode rapide, ce qui **saute** le témoin de rejeu byte-identique.
