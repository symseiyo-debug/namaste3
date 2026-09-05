# CHAINE.md — décompiler, désobfusquer, consigner : les chaînes par build

> Étage 5 du projet. Décision du 04/09 : *« tu me fais tous les outils pour nos versions, tu
> décompiles tout, tu désobfusques tout, tu consignes tout, comme ça on pourra tout partager à la
> communauté »* · *« donc autant faire des outils pour toutes nos versions, gros apport pour la commu »*.
>
> **Loi L4 — deux mondes, jamais un outil « commun ».** Dofus 2.x = Flash/AS3, `protocolId` numérique,
> `serializeAs_*`, données `d2o/d2i/d2p`. Dofus 3.x = Unity IL2CPP, protobuf `varint` + `Any`/`typeUrl`,
> opcode 3 lettres obfusqué, données Addressables. **Rien ne se porte tel quel.** Chaque outil ci-dessous
> appartient à UNE chaîne. Un outil qui prétendrait servir les deux ferait semblant.
> **Loi L6 — Dofus 3 est dynamique.** L'opcode EST le nom de classe obfusqué, rebrassé à chaque build.
> Donc : rien en dur, tout artefact porte sa build dans son chemin et dans ses colonnes.
> **Loi L7 — l'analyse dynamique est la voie du debug.** Le dump donne la FORME ; le client qui tourne
> donne le SENS et l'ORDRE. D'où une troisième chaîne, et le ping-pong multi-builds.
>
> **Ordre de traitement (décision du 04/09) : « focus sur Dofus 3 avant la 2 »)** : §A et §B d'abord, §C ensuite.
> Les deux restent des livrables complets pour la communauté. État par build : `ETAT.md`. Rejeu : `RUNBOOK-COMMUNAUTE.md`.

**La loi de ce document** — cahier §4 : *tout compte issu d'une extraction se remesure par un SECOND
CHEMIN avant d'être cité.* Les chiffres portent leur second chemin, ou disent « non remesuré ».

---

# §A — CHAÎNE 3.x STATIQUE (Unity IL2CPP)

### A1 · Obtenir une ou PLUSIEURS builds
| | |
|---|---|
| entrée | une ou plusieurs versions (`3.6.4.3 3.6.10.10 3.6.10.11`) |
| outil | **`obtenir_build.sh il2cpp <versions…> --out <dir>`** (écrit ici) — enveloppe de `refs/cytrus-v6/` |
| sortie | **un dossier par build** `<out>/<version>/` + `MANIFEST.sha256` — le chemin porte la build (L6) |
| 🔴 le piège du CDN | **le numéro de build seul rend 403.** Le CDN Ankama exige un préfixe de version majeure. Mesuré le 05/09 avec témoins : `3.6.4.3` → **403** · `6.0_3.6.4.3` → **200** · `6.0_3.6.10.11` → **200** · `6.0_9.9.9.9` → **403**. Un 403 se lit comme « cette build n'existe pas » alors qu'il dit « ce nom est mal formé ». Le script **préfixe automatiquement** et **contrôle le manifeste en HTTP avant** de télécharger, avec un refus qui nomme les deux causes possibles |
| gate | `--epreuve` **12/12** : 10 hors ligne (mode plan écrit 0 fichier · garde de place refuse 999999999 Mo et **laisse passer** 1 Mo · manifeste refuse un dossier vide et vérifie un sha256 juste · option inconnue refusée · 3 versions → 3 dossiers distincts portant la build normalisée · build non demandée absente · `--out` absent → refusé · **normalisation** : nue → préfixée, préfixée inchangée, `latest` intacte) et 2 qui **interrogent le CDN** (une build réelle passe, une build inventée est refusée). Sans réseau, ces 2 ne sont **ni verts ni rouges** et le disent |
| durée | **mesurée le 05/09** : build `6.0_3.6.4.3`, **12 s** au total dont 8 s de transfert cytrus, **149 Mo** écrits en 2 fichiers. Le manifeste seul pèse 51,7 Mo |

### A2 · Binaires → dump
| | |
|---|---|
| entrée | `GameAssembly.dll` (115 367 424 o) + `global-metadata.dat` (40 335 992 o), metadata **v39** |
| outil | **existant** : `../../internal/tools/il2cppinspectorredux-cli/` (.NET 8.0.130) |
| sortie | `il2cpp.json` 217 Mo · `il2cpp.h` 132 Mo · `cs/il2cpp.cs` **1 081 733 lignes** · `dll/` **143 DLL fantômes** |
| gate | A3 |
| ⚠️ | Il2CppDumper 6.7.46 **refuse** le metadata v39 — d'où Inspector-Redux |

### A3 · Gate G0 — le dump conserve-t-il le protocole ?
| | |
|---|---|
| outil | **existant** : `../../tools/client-dump/gate-g0.py` |
| gate | ≥ 95 % des noms `Com.Ankama.Dofus.Server.*` du metadata BRUT retrouvés dans les DLL fantômes · **invention = 0** · 5 témoins fictifs absents · ≥ 1000 classes `IBufferMessage` |
| rejouée par moi | 🟢 **VERT · 100,00 % · 0 inventé · 2319 `IBufferMessage` · 0,7 s** — appel de `mesurer()`, **aucune écriture** dans la zone d'un autre |

### A4 · Dump → table EXACTE des littéraux et des surfaces
| | |
|---|---|
| outil | **`extraire_litteraux.py`** (écrit ici) — remplace les one-liners inline |
| sortie | `litteraux-<build>.tsv` **32 936** · `routes-haapi` **372** · `urls` **47** · `noms-protocole` **1003** · `chemins-source` **99** · `zaap` **19** · `config-candidats` **5** |
| gate | `--epreuve` **7/7** : rejeu byte-identique · **second chemin de comptage** (JSON 32936 == regex 32936) · partition exacte · URL injectée vue 47→48 · route retirée 372→371 · témoin négatif absent · **entrée vide → 0 classés** |
| remesure | 372 routes **identiques** (`diff` vide) au `routes-haapi-catalogue.txt` produit par un autre chemin ; 1003 noms **identiques** au `noms-protocole-en-clair.v2.txt` de gate-g0 |
| 🔴 mesuré | `il2cpp.json` ne contient **aucun** `Com.Ankama.Dofus.Server.*` (**0 sur 217 Mo**). Les noms vivent dans `global-metadata.dat` (1003) et les DLL (982 + 21). D'où `--binaire`, répétable. Chercher les noms dans le JSON aurait rendu **0 sur un dump parfait**. *(Corrigé depuis en amont dans `LITTERAUX-RESEAU-EN-CLAIR.md`.)* |

### A5 · Matcher structurel (désobfuscation nom clair ↔ classe obfusquée)
**Existant, autre chantier, EN COURS** : `../../tools/protocol-mapping/matcher/`. Gate du cahier : éprouvé par **≥ 5
instruments** (Jondo, otomai, gatherer, deobfs, LuaxY). **Non rejoué par moi** — un seul écrivain par zone.
⚠️ L6 : une table tierce ne se consomme jamais sans avoir mesuré qu'elle colle à NOTRE build. Mesure du
cahier : les opcodes d'otomai collisionnent à 84 % avec nos classes mais **0 accord de sens sur 27 opcodes
communs** ; bruit de fond 30 %. Une ressemblance structurelle est une hypothèse, jamais une preuve.

### A6 · `.proto` reconstruit + table de dispatch **générée**
**MANQUANT** (`rendre_proto.py`). Patrons à lire : `refs/dofus-unity-protocol-builder` (LuaxY),
`Jondo.Unity.Reversing`, `refs/otomai/tools/proto-sync/` (`codegen.py` 173 l., `registry.py` 144 l.).
L6 : la table de dispatch se **génère par build** et se charge au démarrage ; aucun opcode en dur.
Gate à écrire : round-trip `.proto` → encodage → décodage **byte-exact** contre une trame réelle.

### A7 · Données 3.x — Addressables
| | |
|---|---|
| entrée | `**/StreamingAssets/**/*.bundle` de la build |
| outil | **existant, à réutiliser** : `../../internal/artefacts/lot30-data-3.0-extract/extract_bundle.py` (UnityPy, `.venv/`, `OUTIL.md`) — bundle → JSON |
| ⚠️ | l'en-tête du bundle porte une version Unity non résolvable (`5.x.x` placeholder) : un fallback explicite `6000.3.0f1` est nécessaire, mesuré sur l'échantillon. Les bundles sont **par build et par CDN** (L6) |
| manque | les 577 bundles `Map/Data` (géométrie des cartes) jamais moissonnés |

### A8 · Pilote — jusqu'où une build va-t-elle SANS main humaine ?
| | |
|---|---|
| outil | **`chaine_3x.sh <version> --build\|--dump … --out …`** (écrit ici) |
| sortie | un bilan par étape : franchi ✅ ou **REFUS NOMMÉ** 🔴. Il ne saute jamais un maillon en silence |
| gate | `--epreuve` **4/4** : entrée absente refusée et nommée · sur le dump réel, franchit ce qui existe et nomme les manques · **preuve à destination** (les tables existent vraiment, 1003 noms) · **témoin négatif** (une build refusée ne produit aucune table) |
| **mesure L7** | build 3.6.10.10 : **3 maillons franchis (dump, G0, littéraux), 3 refus nommés (matcher, `.proto`, bot)**. **Gate L7 : 🔴 NON ATTEINTE**, et le pilote dit exactement où la main reprend |

---

# §B — CHAÎNE 3.x DYNAMIQUE (le client qui tourne)

> L7 : *« c'est en créant des outils d'analyse dynamique de notre client qu'on va full debug notre
> serveur 3.0 »*. Le dump donne la forme d'un message ; il ne dit ni **qui** l'émet, ni **quand**, ni
> **dans quel ordre**. Le dump n'a d'ailleurs **aucun corps de méthode** (déclarations, champs,
> constantes, RVA seulement) — tout ce qui porte sur un COMPORTEMENT vient d'ici ou reste `DÉDUIT`.

### B1 · Sniffer / décodeur sur le fil
| | |
|---|---|
| outil | **existant, livré, VERT** : `../../codec/` (.NET 8, `gate-codec.sh`, `CODEC.md`) — **355 trames réelles décodées et ré-encodées byte-exact, 71 tests, 0 échec**. **Je ne le réécris pas** |
| interface | entrée : flux TCP du socket de jeu. Framing **`varint32(len) ++ protobuf`**, sans octet de type. Enveloppe `google.protobuf.Any`, `typeUrl = "type.ankama.com/<opcode>"`. Sortie : `(sens, opcode, octets)` |
| fait majeur | **le jeu n'est PAS sur la pile Spin** : Spin porte le launcher et le chat (octet de type `Application=0…`), le jeu est sur **DotNetty** (`ProtobufVarint32FrameDecoder`, `gjv : MessageToMessageCodec`). Un codec suivant la doctrine « SpinConnection » aurait cherché un octet qui n'existe pas |
| à lire | `refs/dofus3-sniffer-tui` (Go, **4 490 lignes**, gopacket + BubbleTea ; `internal/protoreg/` : `registry.go`, `envelope.go`, `compiler.go`, `mappings.go` + leurs tests) — reconstruction TCP et registre d'opcodes |
| gate | rejeu des captures `refs/JondoEmu/datos/world_etapa*.bin` : round-trip **byte-exact** |

### B2 · Accrochage IL2CPP à l'exécution — le maillon qui donne le SENS
| | |
|---|---|
| but | journaliser **chaque envoi et chaque réception avec la pile d'appel** : quel manager émet quel opcode, quand, après quoi |
| patron à LIRE | `refs/dofus3-native-host` (Rust + C++, **10 837 lignes** ; `bootstrap/src/version_proxy.cpp` = proxy `version.dll`, sans MelonLoader ; `crates/host`, `crates/mod-api`, `crates/mod-sdk` 611 l. = l'ABI de mods) et `refs/dofus3-public-internal` (C++, **144 `.h`**, `common/common.proto`) pour les signatures |
| table de hooks | **générée depuis `il2cpp.json` de LA build** : `addressMap.methodDefinitions` porte **335 415** entrées `{virtualAddress, name, signature, dotNetSignature, group}`, dont **55 927** dans `Ankama.Dofus.Protocol.Game.dll` |
| 🔴 L6 | **les RVA bougent à chaque build.** Une table de hooks écrite en dur est fausse dès le patch suivant. Elle se régénère, comme la table de dispatch |
| gate à écrire | pour un opcode connu, le journal doit **nommer le manager émetteur** ; **témoin négatif** : un opcode jamais émis ne doit apparaître nulle part dans le journal |
| ⚠️ où | sur un **PC Windows personnel**, pas sur le VPS. Et la règle du projet interdit d'exécuter un binaire tiers : `dofus3-native-host` est un **patron à lire**, on écrit le nôtre |
| état | **MANQUANT** — rien d'écrit |

### B3 · Rejeu de captures contre notre serveur
Les captures Jondo (242 disponibles selon le cahier) et les nôtres, rejouées contre le serveur : le
serveur doit répondre la même séquence. **MANQUANT** (`rejouer_capture.py`), dépend de B1.

### B4 · Introspection d'état en direct
**Existant** : le bot-testeur (`../../internal/bot-testeur/`) expose un canal TCP d'introspection
(`position`/`state`/`action`, machine-lisible). Le relier au journal de B2 est ce qui ferme la boucle.

### B5 · Corrélation client ↔ serveur
Journal client (B2) + journal serveur + trace du bot (B4), alignés sur l'horloge et l'opcode → **le SENS**.
C'est ce qui transforme un `DÉDUIT` du matcher en `VÉRIFIÉ`. **MANQUANT.**

---

# §C — CHAÎNE 2.x STATIQUE (Flash / AS3)

> Livrable à part entière, pas une annexe du 3.0. Les émulateurs 2.x nous apprennent l'**architecture**
> et les **règles du jeu** ; le protocole 2.x, lui, est complet et lisible — c'est ce qui en fait un
> cadeau pour la communauté.

### C1 · Obtenir le SWF
`obtenir_build.sh swf <versions…> --out <dir>` — même outil, même gate, sous-commande différente.
⚠️ **DÉDUIT** : que Cytrus serve encore les versions 2.x. Aucun appel réseau émis. Nos trois SWF viennent
d'archives. *Vérifier* : `obtenir_build.sh versions --vraiment`.

### C2 · SWF → arbre AS3
**Existant** : `../../internal/as3/export-as3.sh` (ffdec 26.2.1 headless, Java 21).
Débit **mesuré sur 2.68 : 1,09 script/s** (1041 scripts en 952 s) → 6428 scripts ≈ **98 min, extrapolé**.

> 🔴 **Défaut MESURÉ** : ffdec tourne avec `-Xmx1024m`. Sur 2.68, **4 fichiers du seul sous-arbre réseau
> déjà exporté** portent `Decompilation error … OutOfMemoryError` à la place du code. Le fichier existe,
> a une taille normale, et ne contient rien : un `find | wc -l` le compte comme un succès. Remède
> `-Xmx6g` (**DÉDUIT du message d'erreur**). **Non corrigé** : `export-as3.sh` n'est pas dans ma zone.

### C3 · L'arbre est-il complet ?
| | |
|---|---|
| outil | **`verifier_arbre_as3.py`** (écrit ici) — **parseur ABC maison** (zlib → tags → pool de constantes → `instance_info`), indépendant de ffdec |
| gate | trois refus : **couverture** ≥ seuil · **invention** = 0 · **aucun paquet troué** |
| sabotage | `--epreuve` **5/5**, chaque barrière mord sur **SON** sabotage, vérifié par le motif du refus |
| durée | **0,64 s** (SWF 6,2 Mo + 1420 `.as`), 53 Mo RSS |

> **Le refus PAR PAQUET est né d'un faux vert mesuré ici.** L'arbre 2.42 rendait **99,44 %** : au-dessus
> du seuil, donc vert. Il manquait 8 classes, dont `IdentificationSuccessWithLoginTokenMessage` et
> `CredentialsAcknowledgementMessage` — **le chemin de login**. *Un ratio ne dit pas la forme de sa
> population.* La bonne question est « chaque paquet que l'arbre CONTIENT est-il ENTIER ? ».

### C4 · Arbre → tables du protocole
| | |
|---|---|
| outil | **`extraire_as3_protocole.py`** (écrit ici) |
| sortie | `messages/types/enums-<v>.tsv` : nom, `protocolId`, `fichier:ligne`, champs `nom:type`, **ordre de sérialisation**, parent |
| gate | `--epreuve` **6/6** : rejeu byte-identique · partition assertée · sabotage `protocolId` vu · sabotage d'ordre vu · 1 fichier retiré → compte −1 · témoin inventé absent. **Rejets comptés par motif** |
| durée | **0,49 s** (1420 `.as`) · **0,7 s** (1679 `.as` de 2.73) |

**L'ordre de sérialisation est le cœur du maillon.** L'ordre déclaré n'est pas l'ordre du fil :
`AccountCapabilitiesMessage` écrit `tutorialAvailable:bit0 ; canCreateNewCharacter:bit1 ;
#local:writeByte ; accountId:writeInt ; …` — les booléens groupés en tête dans un octet de drapeaux.
Un serveur qui sérialise dans l'ordre de déclaration produit des trames que le client refuse.

> **La grammaire AS3 change entre versions** : 2.42 nomme `param1`/`_loc2_`, 2.68 nomme `output`/`_box0`.
> Un extracteur ancré sur ces noms aurait rendu « 0 ordre » sur 2.68 — un zéro fabriqué par l'instrument.

### C5 · Croisement multi-émulateurs
**Existant, autre chantier** : `../../tools/protocol-mapping/index/croiser.py`. Mes 5 premières colonnes sont
**identiques** aux siennes ; mes colonnes en plus sont **à la fin**. Sa table et la mienne se lisent
avec le même découpeur.

### C6 · Données 2.x — `d2o` / `d2i` / `d2p`
| | |
|---|---|
| outils | **existants, à réutiliser** : `dofus-tools/d2o` + `d2o_lib.py` (lecture/dump JSON), `dofus-tools/asset-index/d2p_entries.py`, `d2i_text.py`, `build_index.py`, `queries.sql` ; skill `d2o` pour lire/patcher un enregistrement |
| ⚠️ | **rien de commun avec les Addressables du 3.x** (A7) : formats, outils et pipelines disjoints. C'est exactement ce que dit L4 |

### C7 · Tables → docs publiables
**MANQUANT** (`rendre_docs.py`) : une fiche par message au format §4 du cahier, générée, jamais écrite
à la main ; chaque fiche porte `fichier:ligne`, aucun `DÉDUIT` sans « comment vérifier ».

---

# §D — PING-PONG : build N vs build N+1 (à l'intérieur d'une même famille)

| | |
|---|---|
| outil | **`diff_builds.py`** (écrit ici) ; `--chaine t1 t2 t3…` fait tous les N vs N+1 d'un coup |
| natures | **deux populations, deux partitions** — messages : `AJOUTE · RETIRE · RENOMME · RENUMEROTE · RESTRUCTURE · INCHANGE` ; champs : `CHAMP_AJOUTE · CHAMP_RETIRE · TYPE_CHANGE · CHAMP_INCHANGE`. `ORDRE_CHANGE` reste au niveau message (c'est une propriété de la trame) |
| **renommage pur** | indispensable en 3.x (L6 : l'opcode EST le nom, rebrassé à chaque build). Appariement sur la **signature structurelle** (champs typés + ordre). **Si une signature est dupliquée, l'outil REFUSE d'apparier** et compte l'ambiguïté : un appariement inventé se propagerait dans la table de dispatch |
| gate | `--epreuve` **11/11**, mutations injectées retrouvées **nominativement** : 6 renommages (et **aucun compté comme RETIRE**), 8 renumérotations, 3 retraits, 4 ajouts, 5 champs ajoutés, 4 retirés, 3 types changés · **ambiguïté** : 2 signatures dupliquées laissées non appariées · **témoin négatif** A vs A → 0 changement, 0 renommage inventé · partition des champs |
| patrons lus | `refs/dofus-emu-dev/Tools/ProtoDiff273/`, `refs/otomai/tools/proto-sync/` (`diff.py` 224 l.), `Jondo.Unity.Reversing` (« match two versions », 71 % auto chez Jondo, ~11 % si tout est rebrassé) |
| outil frère | `diff_protocole.py` (natures grossières, `--epreuve` **8/8**) : plus lisible pour un survol, même moteur de lecture de tables |

**Mesure réelle 2.42 → 2.73** (1033 vs 1190 messages) :

| population | natures |
|---|---|
| messages | AJOUTE 310 · RETIRE 153 · **RENOMME 4** · RENUMEROTE 716 · RESTRUCTURE 158 · **INCHANGE 2** |
| champs | CHAMP_AJOUTE 87 · CHAMP_RETIRE 85 · TYPE_CHANGE 53 · inchangés 1196 |

Renommages trouvés, sémantiquement justes : `ExchangeHandleMountsStableMessage → ExchangeHandleMountsMessage`,
`PartyCompanionUpdateLightMessage → PartyEntityUpdateLightMessage`. Ambiguïtés **refusées** : 5 côté A, 4 côté B.

> **874 des 876 messages communs changent d'identifiant : 99,8 %.** Seuls `NetworkDataContainerMessage`
> et `RawDataMessage` traversent intacts. C'est la **confirmation par un second chemin** d'une révision indépendante
> (« 868/872 renumérotées »), mesurée sur d'autres tables, par un autre outil.

### Ce qui survit entre deux builds 3.x — mesure ACQUISE le 05/09

Lue dans les deux `global-metadata.dat`, **sans dump** ; second chemin par `grep -aoE` sur le binaire :
même compte.

| population | 3.6.4.3 | 3.6.10.10 | communs | apparus | disparus |
|---|---|---|---|---|---|
| nom complet | 985 | 1003 | 599 | 404 | 386 |
| **nom de feuille** | 959 | 982 | **592 (61,7 %)** | 390 | 367 |
| messages de tête | 498 | 513 | 310 | 203 | 188 |

Partition assertée : 599 + 404 + 386 = 1389 noms de l'union. L'écart n'est **pas** un déménagement de
namespace : **9 noms seulement** changent de chemin complet, **583** gardent feuille ET chemin.

> ⚠️ **C'est un PLANCHER de stabilité, pas une mesure de rotation.** Un nom « disparu » peut être un
> message **renommé** — le nom ne peut pas trancher, seule la signature protobuf le pourrait, et elle
> demande le dump de 3.6.4.3, **non fait** (arrêt du multi-build, décision du 05/09 : *« osef
> du portage de version pour l'instant, faisons déjà un serveur qui marche »*).
> **Ce qui est acquis et suffit pour écrire les handlers** : ils ne peuvent s'ancrer ni sur le token
> obfusqué (rebrassé à chaque build, L6), ni sur le nom clair (61,7 % de survie mesurée). Il reste la
> **forme protobuf** et le **nom sémantique** porté par une table régénérée — ce que fait `proto-sync`.

**Reprise du ping-pong quand on y reviendra** : `obtenir_build.sh il2cpp <versions…> --out ./builds
--vraiment`, puis `chaine_3x.sh` sur chacune, puis `tabler_protobuf_3x.py` sur chaque dump, puis
`diff_builds.py --chaine`. Les quatre maillons sont écrits et éprouvés ; il ne manque que le dump.

---

# §E — ÉVOLUTION 2.x ↔ 3.0 : SÉMANTIQUE, jamais structurelle

L4 : deux espaces de noms **disjoints**. Aucune jointure automatique entre un `protocolId` numérique 2.x
et un opcode 3 lettres 3.x — ce sont deux systèmes de nommage sans rapport. En 3.0 l'ancre `*Message`
n'existe même plus (2 classes `*Message` sur 206 chez Jondo).
Le seul lien légitime est `ÉVOLUTION_DÉDUITE`, ancré sur le **nom sémantique** et **promouvable champ par
champ** par une capture. Ce que 2.x apporte au 3.0 : l'**architecture** et les **règles du jeu**, jamais
le protocole ni les formats. **`diff_builds.py` ne doit pas être pointé sur une paire 2.x/3.x** : il
apparierait par signature et fabriquerait des correspondances qui n'existent pas.

---

# §F — MAILLON TRANSVERSAL : la gate commentaires (avant TOUTE livraison de code)

> Décision du 04/09, verbatim : *« tu me commentes tout le code, super important pour un projet
> commu »*. Ce maillon n'appartient à aucune chaîne : il les traverse toutes. Un outil que la communauté
> doit pouvoir reprendre sans nous se juge autant sur ses commentaires que sur ses gates — un script
> juste dont personne ne comprend le POURQUOI se fait réécrire de travers au premier patch d'Ankama.

| | |
|---|---|
| entrée | tout fichier de code livré (`.py`, `.sh`) |
| outil | **`../gate-commentaires.py`** — écrit ailleurs dans le projet, dans `internal/` |
| quand | **avant toute livraison**, au même titre qu'un `--epreuve` |
| ce qu'elle exige | en-tête **QUOI / POURQUOI daté / COMMENT LANCER / GATE** · un commentaire d'intention **FR/EN** sur chaque fonction · **constantes sourcées** (d'où vient le chiffre, mesuré quand) |
| état, **daté** | 🔴 **absente à 21:47 UTC** (recherche non bornée sur tout l'espace de travail : 0 fichier) · 🟢 **présente et lancée à 21:56 UTC** — elle a été écrite entre mes deux mesures. *Une affirmation d'absence porte l'heure de sa mesure, sinon elle vieillit en silence et devient fausse sans que personne ne s'en aperçoive.* |
| son critère | VERT par fichier si l'en-tête porte les 4 sections **ET** ≥ 90 % des fonctions/classes/méthodes ont un commentaire. Les nombres magiques sont **comptés sans bloquer** — une mesure, pas une gate |
| **verdict sur cette zone** | 🟢 **8 VERT / 0 ROUGE / 8 fichiers**, 100 % des unités commentées sur chacun. Elle a d'abord refusé **3 fichiers** (`attendre_et_extraire.sh` 0 %, `chaine_3x.sh` 50 %, `obtenir_build.sh` 80 %) : mes fonctions bash portaient leur commentaire **sur la même ligne**, pas au-dessus. Corrigé, puis rejouée |
| non-régression | **50 contrôles d'épreuve, 50 verts** après l'opération, identiques à avant. Ajouter des lignes dans un fichier est une modification comme une autre : 39 commentaires posés en Python, 5 en bash, tous relus après écriture |

**Pourquoi pas à l'œil** : relire son propre fichier ne prouve rien, c'est l'angle mort de l'auteur.
Mon script de contrôle rendait déjà 0 fonction non commentée quand la gate d'un autre chantier en a trouvé
**5** : elle attend le commentaire **au-dessus** de la fonction, mon script acceptait aussi la même
ligne. *Deux instruments au même grain se confirment leurs angles morts ; c'est celui écrit par
quelqu'un d'autre qui a mordu.* Le chiffre à citer est le sien, pas le mien.

# §G — LA FAMILLE DES FAUX VERTS À CODE DE RETOUR

> Un maillon de chaîne se juge sur les **octets qu'il a produits**, jamais sur ce qu'il a *rendu*. Trois
> formes de la même faute ont été rencontrées ici, chacune sur un outil différent :

| forme | ce qui trompe | mesuré |
|---|---|---|
| **`rc=0` sur SIGTERM** | la CLI Il2CppInspector attrape le signal et **sort proprement avec 0**. Un dump interrompu au quart s'écrit donc « rc=0, 363 s », dossier `cs/` **vide** | 05/09, mon propre lanceur |
| **code de retour derrière un tube** | `cmd \| head` rend le code de `head`, pas de `cmd`. Ma garde de ressources refusait bien (rc=1) et mon test affichait 0 | 05/09, mon propre test |
| **outil qui rend « propre » sans avoir lu** | un garde appelé sans son argument, une recherche bornée, un compteur qui n'a rien ouvert | règle du projet, §5 |

**La règle qui les couvre toutes** : après tout travail long, on vérifie **à destination** — le fichier
attendu existe, il dépasse une taille plancher, et son contenu porte la marque cherchée. Mon lanceur de
dump rend désormais `VERDICT=INCOMPLET` quand `cs/il2cpp.cs` est absent ou sous 10 Mo, quel que soit son
code de retour. Un `rc=0` n'a jamais dit qu'un octet était arrivé.

# §H — COMMENT CETTE CHAÎNE ALIMENTE LA TABLE DE DISPATCH

Le serveur ne doit contenir **aucun opcode en dur** (L6) : il charge une table générée. Cette table est
produite par `../proto-sync/generer_dispatch.py`, qui lit `cs/il2cpp.cs` — et prend son chemin en
**paramètre** (`charger_dump(chemin, assemblies)`), donc il est déjà prêt pour plusieurs builds.

1. `obtenir_build.sh il2cpp <version> --out <dir>` → les deux binaires, dans un dossier qui porte la build.
2. `chaine_3x.sh <version> --build <dir> --out <dir>` → le dump, la gate G0 (avec le metadata de **cette**
   build, jamais celui d'une autre), et les littéraux.
3. `generer_dispatch.py` lit ce dump → `dispatch-<build>.json` + `.cs`, que le serveur charge au démarrage.
4. `tabler_protobuf_3x.py <dump> <build>` → la table de signatures protobuf de la build.
5. `diff_builds.py --chaine <tables…>` → ce qui a bougé entre deux builds, par nature de dette, **avec les
   ambiguïtés refusées et non devinées**.

C'est l'étape 5 qui donne à `proto-sync` ce qu'il ne peut pas déduire seul : la **continuité** d'un
message d'une build à l'autre. Le nom sémantique reste stable parce qu'un appariement structurel le
rattache à son token de la build précédente ; sans lui, chaque build repart de zéro et tous les handlers
sont à renommer. Les étapes 1, 2, 4 et 5 sont écrites et éprouvées ; seule l'exécution sur une seconde
build manque, et elle est en pause sur ordre.

## Durées mesurées

| maillon | durée | conditions |
|---|---|---|
| A3 `gate-g0.py` (rejeu) | 0,7 s | fichiers en cache ; **à froid : non mesuré** |
| A4 `extraire_litteraux.py` | 1,00 s | `il2cpp.json` 217 Mo **en cache** ; à froid ≈ 4 s (une observation) |
| A8 `chaine_3x.sh` | ~3 s | sur un dump déjà produit |
| C2 ffdec 2.68 | 1,09 script/s | 1041 scripts en 952 s ; **98 min pour 6428 = extrapolé** |
| C3 `verifier_arbre_as3.py` | 0,64 s | SWF 6,2 Mo + 1420 `.as`, 53 Mo RSS |
| C4 `extraire_as3_protocole.py` | 0,49 s | 1420 `.as`, 21 Mo RSS |
| D `diff_builds.py` | < 2 s | 1033 × 1190 messages |
| A1/C1 `obtenir_build.sh` | non mesurée | rien n'a été téléchargé |

## Les fichiers de cette zone

| fichier | chaîne | épreuve |
|---|---|---|
| `extraire_litteraux.py` | A4 · 3.x | **7/7** |
| `chaine_3x.sh` | A8 · 3.x (pilote L7) | **4/4** |
| `verifier_arbre_as3.py` | C3 · 2.x | **5/5** |
| `extraire_as3_protocole.py` | C4 · 2.x | **6/6** |
| `diff_builds.py` | D · ping-pong | **11/11** |
| `diff_protocole.py` | D · survol | **8/8** |
| `obtenir_build.sh` | A1 et C1 (multi-builds) | **9/9** |
| `attendre_et_extraire.sh` | commodité 2.x : enchaîne C4+C3 quand ffdec finit. Ne tue rien | — (arrêté : export 2.x en pause) |
| `CHAINE.md` · `RUNBOOK-COMMUNAUTE.md` · `ETAT.md` · `out/` | — | — |

## Ce qui est DÉDUIT dans ce document
1. **98 min pour l'export 2.68** — extrapolé d'un débit mesuré sur 16 % du travail.
2. **Cytrus sert encore les versions 2.x** — aucun appel réseau émis. *Vérifier* : `versions --vraiment`.
3. **`-Xmx6g` suffit à ffdec** — déduit du message d'erreur. *Vérifier* : compter les `ÉCHEC DE
   DÉCOMPILATION ffdec` après relance ; zéro, ou recommencer.
4. **Le SWF étiqueté `238` est bien un 2.38** — mon recoupement par messages exclusifs est **non
   discriminant** (160/219 contre 156/219 pour 2.42). *Vérifier* : comparer les `protocolId` une fois
   l'arbre 2.38 exporté.
5. **Les drapeaux de la CLI Inspector-Redux (A2)** — le dump existant a été produit ailleurs dans le projet,
   je n'ai pas rejoué la commande. *Vérifier* : `--help`, puis comparer les `MANIFEST.sha256`.
