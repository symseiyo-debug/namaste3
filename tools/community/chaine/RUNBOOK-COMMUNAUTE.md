# RUNBOOK — rejouer les chaînes sur une build neuve, avec le dépôt seul

> Public visé : quelqu'un qui n'a écrit aucun de ces outils et qui veut le protocole d'une build de
> Dofus que nous n'avons jamais vue. Commandes exactes, gates à lire, et ce qui est **DÉDUIT**.
>
> **Deux familles, deux chaînes, aucun outil commun.** Dofus 3.x est du Unity IL2CPP (protobuf, opcodes
> obfusqués, données Addressables) ; Dofus 2.x est du Flash/AS3 (`protocolId` numérique, `d2o/d2i/d2p`).
> **Rien ne se porte de l'une à l'autre.** Va en §2 pour du 3.x, en §4 pour du 2.x. Les deux sont des
> livrables complets. Une troisième chaîne, **dynamique** (§3), n'existe que pour le 3.x.
>
> **La règle de lecture** : chaque outil a un `--epreuve`. **Lance-le avant de croire sa sortie.**
> Un outil qui n'a pas mordu sur un sabotage n'a pas prouvé qu'il regarde le terrain.

---

## 1. Prérequis (versions MESURÉES sur la machine où les chaînes ont été écrites)

| pour quoi | ce qu'il faut | version mesurée le 04/09/2026 | vérifier |
|---|---|---|---|
| tout | Python 3, **stdlib seule** | 3.12 | `python3 -V` |
| chaîne 3.x | **Il2CppInspector-Redux** (CLI) + .NET | .NET 8.0.130 | `dotnet --version` |
| données 3.x | **UnityPy** dans un venv dédié | fourni avec `lot30-data-3.0-extract/.venv` | — |
| chaîne 2.x | **ffdec** (JPEXS) + un JRE | ffdec 26.2.1, OpenJDK 21.0.12 | `ffdec -help \| head -1` |
| obtenir une build | **cytrus-v6** via npm/npx | npm 10.9.7, node 22.22.2 | `npx --yes cytrus-v6 --help` |
| — | place disque | 62 Go libres | `df -h .` |

Les outils écrits ici sont du Python standard et du bash : ni `pip install`, ni venv, ni service.

---

## 2. CHAÎNE 3.x STATIQUE — d'un `GameAssembly.dll` aux surfaces en clair

### 2.1 Obtenir une ou plusieurs builds
```bash
./obtenir_build.sh versions --release dofus3            # MODE PLAN : imprime, ne télécharge rien
./obtenir_build.sh versions --release dofus3 --vraiment # exécute
./obtenir_build.sh il2cpp 3.6.4.3 3.6.10.10 3.6.10.11 --out ./builds --vraiment
```
Chaque build atterrit dans **son propre dossier** `./builds/<version>/`, avec son `MANIFEST.sha256`.
`--out` est **obligatoire** : sans lui les builds s'écraseraient. `--vraiment` est **obligatoire** pour
qu'un octet soit téléchargé ; sans lui le script imprime la commande exacte et s'arrête.

> **Pourquoi plusieurs builds d'un coup** : en Dofus 3, l'opcode à 3 lettres **est** le nom de classe
> obfusqué, et il est rebrassé à chaque build. Une seule build ne dit pas ce qui bouge. Deux suffisent
> à lancer le ping-pong (§5).

### 2.2 Tout enchaîner, et voir où la main humaine reprend
```bash
./chaine_3x.sh --epreuve                                          # 4/4 attendus
./chaine_3x.sh 3.6.10.10 --build ./builds/3.6.10.10 --out ./sortie
```
Le pilote enchaîne obtenir → dump → gate G0 → littéraux, puis **refuse en nommant** chaque maillon
absent. Il ne saute jamais rien en silence : un pilote qui saute un maillon manquant rend « succès »
sur une chaîne cassée. Il finit par un bilan et un verdict de gate.

État mesuré le 04/09 sur 3.6.10.10 : **3 maillons franchis, 3 refus nommés** (matcher, `.proto`, bot).
Si tu veux dérouler à la main, voici les mêmes étapes.

### 2.3 Dumper
```bash
./tools/il2cppinspectorredux-cli/Il2CppInspectorRedux.CLI-linux-x64/Il2CppInspector.Redux.CLI \
    -i ./builds/3.6.10.10/GameAssembly.dll \
    -m ./builds/3.6.10.10/global-metadata.dat -o ./dump-3.6.10.10
```
> Il2CppDumper 6.7.46 **refuse** le metadata v39 : c'est pourquoi la chaîne passe par Inspector-Redux.
> Adapte les drapeaux à ta version de la CLI (`--help`) ; il faut **au minimum** `il2cpp.json`,
> `cs/il2cpp.cs` et le dossier `dll/`.

### 2.4 Gate G0 — le dump a-t-il gardé le protocole ?
```bash
python3 ../../tools/client-dump/gate-g0.py ./dump-3.6.10.10 --epreuve   # les deux sens
python3 ../../tools/client-dump/gate-g0.py ./dump-3.6.10.10             # le verdict
```
Vert exige : ≥ 95 % des noms `Com.Ankama.Dofus.Server.*` du metadata **brut** retrouvés dans les DLL
fantômes, **0 nom inventé**, 5 témoins fictifs absents, ≥ 1000 classes `IBufferMessage`.
Notre 3.6.10.10 : **100,00 %, 0 inventé, 2319 `IBufferMessage`, 1003 noms**.

### 2.5 Littéraux, routes, URL, noms
```bash
python3 extraire_litteraux.py --epreuve ./dump-3.6.10.10/il2cpp.json         # 7/7 attendus
python3 extraire_litteraux.py ./dump-3.6.10.10/il2cpp.json 3.6.10.10 --out ./tables3 \
    --binaire ./builds/3.6.10.10/global-metadata.dat \
    --binaire ./dump-3.6.10.10/dll \
    --corroborer ../../internal/noms-protocole-en-clair.v2.txt
```
🔴 **Les `--binaire` ne sont pas optionnels.** `il2cpp.json` ne contient **aucun**
`Com.Ankama.Dofus.Server.*` : **0 occurrence sur 217 Mo**, mesuré. Les noms de messages vivent dans
`global-metadata.dat` et les DLL fantômes. Sans `--binaire`, le script rend **0 nom de protocole sur un
dump parfait** — un zéro fabriqué par l'instrument.

Sur 3.6.10.10 : 32 936 littéraux · **372** routes · 47 URL · **1003** noms · 99 chemins sources.

### 2.6 Données 3.x — Addressables (jamais `d2o`, ce n'est pas la même famille)
```bash
../../internal/artefacts/lot30-data-3.0-extract/.venv/bin/python \
  ../../internal/artefacts/lot30-data-3.0-extract/extract_bundle.py \
  ./builds/3.6.10.10/StreamingAssets --out ./data3 --unity-version 6000.3.0f1
```
> L'en-tête des bundles porte une version Unity **non résolvable** (`5.x.x` placeholder) : le fallback
> explicite est nécessaire. Voir `OUTIL.md` à côté du script pour les limites. Les bundles sont **par
> build et par CDN** : un bundle d'une autre build n'est pas une source valide pour celle-ci.

### 2.7 Ce qui reste manuel en 3.x
Les types du protocole sont **obfusqués** (`class hdw`, `const int ebez = 1`). Les 1003 noms clairs sont
des **littéraux**, pas des noms de classes. Faire correspondre nom clair ↔ classe obfusquée est le
travail du **matcher structurel** (`../../tools/protocol-mapping/matcher/`).
**Une ressemblance structurelle est une hypothèse, jamais une preuve** — et une table d'opcodes prise
chez un tiers ne vaut rien tant qu'on n'a pas mesuré qu'elle colle à TA build : mesure du cahier, les
opcodes d'un bot tiers collisionnent à 84 % avec nos classes pour **0 accord de sens sur 27 opcodes
communs**, contre 30 % de collisions pour des opcodes **inventés**.

---

## 3. CHAÎNE 3.x DYNAMIQUE — ce que le dump ne dira jamais

Le dump donne la **forme** d'un message. Il ne dit ni qui l'émet, ni quand, ni dans quel ordre — il n'a
d'ailleurs **aucun corps de méthode**. Tout ce qui porte sur un comportement vient d'ici, ou reste `DÉDUIT`.

**a) Sniffer / décodeur sur le fil** — le codec existe et il est vert :
`../../codec/`, **355 trames réelles décodées et ré-encodées byte-exact, 71 tests**.
Framing **`varint32(len) ++ protobuf`**, enveloppe `Any`, `typeUrl = "type.ankama.com/<opcode>"`.
⚠️ **Le jeu n'est PAS sur la pile Spin** : Spin porte le launcher et le chat (avec un octet de type en
tête), le jeu est sur DotNetty **sans cet octet**. Un décodeur qui suivrait `SpinConnection` pour le jeu
chercherait un octet qui n'existe pas. À lire pour la capture réseau : `refs/dofus3-sniffer-tui`
(Go, 4 490 lignes, `internal/protoreg/`).

**b) Accrochage IL2CPP à l'exécution** — **le maillon manquant qui donne le sens**. But : journaliser
chaque envoi et réception **avec la pile d'appel**. Patrons à **lire, pas à exécuter** :
`refs/dofus3-native-host` (proxy `version.dll`, sans MelonLoader, 10 837 lignes) et
`refs/dofus3-public-internal` (signatures, 144 `.h`). La table de hooks se **génère** depuis
`il2cpp.json` de **ta** build : `addressMap.methodDefinitions` porte **335 415** entrées
`{virtualAddress, name, signature, group}`, dont **55 927** pour `Ankama.Dofus.Protocol.Game.dll`.
🔴 **Les RVA bougent à chaque build.** Une table de hooks en dur est fausse dès le patch suivant.

**c) Rejeu de captures** contre ton serveur, et **corrélation** des journaux client et serveur : c'est
ce qui promeut un `DÉDUIT` du matcher en `VÉRIFIÉ`. Les deux sont **à écrire**.

---

## 4. CHAÎNE 2.x — d'un `DofusInvoker.swf` aux tables du protocole

### 4.1 Obtenir le SWF
```bash
./obtenir_build.sh swf 2.70.5 --out ./builds2 --vraiment
```
> ⚠️ **DÉDUIT** : que Cytrus serve encore une version 2.x donnée. Aucun appel réseau émis d'ici. Si
> `versions` ne liste pas la tienne, il te faut une archive, et la chaîne démarre en 4.2.

### 4.2 SWF → arbre AS3
🔴 **À corriger avant de lancer, défaut mesuré.** ffdec démarre avec `-Xmx1024m`. Sur le SWF 2.68,
**4 classes du seul sous-arbre réseau déjà exporté** ont produit ceci à la place du code :
```
/* Decompilation error … Error type: ExecutionException (java.lang.OutOfMemoryError: Java heap space) */
throw new flash.errors.IllegalOperationError("Not decompiled due to error");
```
Le fichier existe, il a une taille normale, il ne contient rien : un `find | wc -l` le compte comme un
succès. Donne donc un vrai tas :
```bash
java -Xmx6g -jar /usr/share/java/ffdec/ffdec.jar -cli -export script ./client270-as3 ./builds2/2.70.5/DofusInvoker.swf
```
> **DÉDUIT** : que 6 Go suffisent. *Vérifier* : l'étape 4.4 compte les échecs sous le motif
> `ÉCHEC DE DÉCOMPILATION ffdec`. **Zéro, ou recommence avec plus.**

Débit mesuré sur 2.68 : **1,09 script/s** (1041 scripts en 952 s) → **~1 h 40** pour 6428 scripts.

### 4.3 L'arbre est-il complet ? (avant d'en tirer quoi que ce soit)
```bash
python3 verifier_arbre_as3.py --epreuve ./builds2/2.70.5/DofusInvoker.swf ./client270-as3   # 5/5
python3 verifier_arbre_as3.py ./builds2/2.70.5/DofusInvoker.swf ./client270-as3 --manquants 20
python3 verifier_arbre_as3.py ./builds2/2.70.5/DofusInvoker.swf ./client270-as3 \
        --prefixe com.ankamagames.dofus.network.        # si l'export est volontairement partiel
```
Le script ne demande rien à ffdec : il **parse le SWF lui-même** et compare au texte des `.as`.

| refus | ce qu'il veut dire | quoi faire |
|---|---|---|
| `couverture X % < seuil` | l'export a sauté des classes | relancer ffdec (souvent : tas trop petit) |
| `invention : N classes` | l'arbre contient des classes absentes du SWF | tu mélanges deux versions |
| **`paquets TROUÉS : N`** | un paquet **présent** dans l'arbre est **incomplet** | 🔴 **ne publie rien** avant de l'avoir comblé |

> **Le troisième est le plus important.** Sur notre arbre 2.42, la couverture donnait **99,44 %**, donc
> vert. Il manquait 8 classes, dont `IdentificationSuccessWithLoginTokenMessage` : **le chemin de login**.
> *Un ratio ne dit pas la forme de sa population.*

### 4.4 Arbre → tables du protocole
```bash
python3 extraire_as3_protocole.py --epreuve ./client270-as3          # 6/6 attendus
python3 extraire_as3_protocole.py ./client270-as3 270 --out ./tables
```
**Lis la ligne `REJETS` avant tout.** Elle compte par motif et donne un exemple de chacun :
- `ÉCHEC DE DÉCOMPILATION ffdec` → retour en 4.2 avec plus de tas ;
- `ligne de serializeAs_ non reconnue` → la grammaire AS3 a bougé. **Ne l'ignore pas** : chaque ligne non
  reconnue est **un octet du fil qui manque à la table**. Le `fichier:ligne` est imprimé ; ajoute la
  forme dans la liste `OPS`. Référence : **0 rejet** sur 2.42 (1420 fichiers) et 2.73 (1679).

**La colonne `ordre_serialisation` est le cœur de la table.** L'ordre déclaré n'est pas l'ordre du fil :
```
AccountCapabilitiesMessage  6216
  champs déclarés : accountId, tutorialAvailable, breedsVisible, breedsAvailable, status, canCreateNewCharacter
  ordre du fil    : tutorialAvailable:bit0 ; canCreateNewCharacter:bit1 ; #local:writeByte ;
                    accountId:writeInt ; breedsVisible:writeVarInt ; breedsAvailable:writeVarInt ; status:writeByte
```
Vocabulaire : `champ:writeX` · `champ#len:writeX` (longueur d'un vecteur) · `champ[]:writeX` (élément) ·
`champ:asType` (type imbriqué) · `champ:serialize` (polymorphe, le type voyage dans un `typeId`) ·
`champ:bitN` (booléen en position N d'un octet de drapeaux) · `#local:writeX` · `#constN:writeX` ·
`super:Parent` (partie héritée, sérialisée en premier).

### 4.5 Remesurer par un second chemin (avant de citer un chiffre)
```bash
R=./client270-as3/scripts/com/ankamagames/dofus/network
grep -rlE 'public static const protocolId' $R/messages --include='*.as' | wc -l
grep -rlE 'public static const protocolId' $R/types    --include='*.as' | wc -l
find $R/enums -name '*.as' | wc -l
```
Sur 2.42 comme sur 2.73, les deux chemins coïncident exactement (1033/288/95 et 1190/366/119).

### 4.6 Données 2.x — `d2o`, `d2i`, `d2p` (jamais UnityPy)
```bash
../../dofus-tools/d2o dump ./client/data/common/Npcs.d2o > npcs.json
python3 ../../dofus-tools/asset-index/d2p_entries.py ./client/content/gfx/…d2p
python3 ../../dofus-tools/asset-index/d2i_text.py    ./client/data/i18n/i18n_fr.d2i
```
Ces formats n'ont **rien de commun** avec les Addressables du 3.x (§2.6) : outils et pipelines disjoints.

---

## 5. Comparer deux builds (ping-pong)
```bash
python3 diff_builds.py --epreuve ./tables/messages-270.tsv                     # 11/11 attendus
python3 diff_builds.py ./tables/messages-242.tsv ./tables/messages-273.tsv --out ./tables
python3 diff_builds.py --chaine ./t/messages-3.6.4.3.tsv ./t/messages-3.6.10.10.tsv \
                                ./t/messages-3.6.10.11.tsv --out ./t
```
Deux populations, deux tables : messages (`AJOUTE · RETIRE · RENOMME · RENUMEROTE · RESTRUCTURE ·
INCHANGE`) et champs (`CHAMP_AJOUTE · CHAMP_RETIRE · TYPE_CHANGE`).

Le **renommage pur** est apparié sur la **signature structurelle** (champs typés + ordre). Si une
signature est dupliquée, l'outil **refuse d'apparier** et compte l'ambiguïté : un appariement inventé se
propagerait dans ta table de dispatch, où il serait très cher à retrouver.

🔴 **Ne joins jamais deux versions par `protocolId`.** Mesuré 2.42 → 2.73 : sur 876 messages communs,
**874 changent d'identifiant (99,8 %)**. L'ancre est le **nom**, ou la **structure**.
🔴 **Ne pointe jamais cet outil sur une paire 2.x / 3.x.** Ce sont deux mondes ; il apparierait par
signature et fabriquerait des correspondances qui n'existent pas. Le seul lien 2.x↔3.0 est sémantique,
posé à la main, et reste `DÉDUIT` jusqu'à une capture.

---

## 6. Ce qui est DÉDUIT dans ce runbook
1. **Cytrus sert encore les versions 2.x, et 3.6.10.11 existe** — aucun appel réseau émis d'ici.
   *Vérifier* : `./obtenir_build.sh versions --vraiment`.
2. **`-Xmx6g` suffit à ffdec** — déduit du message d'erreur. *Vérifier* : compter les échecs en 4.4.
3. **Les drapeaux de la CLI Inspector-Redux (§2.3)** — notre dump a été produit par quelqu'un d'autre,
   je n'ai pas rejoué la commande. *Vérifier* : `--help`, puis comparer les `MANIFEST.sha256`.
4. **Le SWF étiqueté `238` est un client 2.38** — l'étiquette d'un fichier ne prouve rien, et mon
   recoupement par messages exclusifs est **non discriminant** (160/219 contre 156/219 pour 2.42).
   *Vérifier* : comparer les `protocolId` une fois l'arbre exporté.

## 7. Si tu contribues du code : la règle des commentaires

Décision du projet, verbatim : *« tu me commentes tout le code, super important pour un projet commu »*.
Elle vaut pour toute contribution, et elle se vérifie par `gate-commentaires.py` (dans `internal/`)
**avant livraison**, au même titre qu'un `--epreuve`.

**a) Un en-tête à quatre sections, dans cet ordre.**
```
═══ QUOI / WHAT ═══            ce que le fichier fait, son maillon dans la chaîne, sa famille (2.x ou 3.x)
═══ POURQUOI / WHY (daté) ═══  le mécanisme, pas l'intention : ce qui trompe, avec ses chiffres et sa date
═══ COMMENT LANCER ═══         les commandes exactes, l'entrée attendue, la sortie produite
═══ GATE ═══                   ce que `--epreuve` contrôle, combien de contrôles, verts quand
```
Le `POURQUOI` porte une date parce qu'une affirmation non datée s'élargit toute seule avec le temps :
« éprouvé dans les deux sens » était vrai pour les formes testées ce jour-là, et s'est mis à se lire
comme une garantie générale.

**b) Un commentaire d'intention FR/EN sur chaque fonction.** Deux lignes suffisent. Écris le
**mécanisme**, pas la paraphrase de la signature : « j'ai oublié `--dir` » ne sert à rien, « un
instrument qui n'a rien lu et un terrain vide produisent la même sortie » sert pour toujours.

**c) Des constantes sourcées.** Tout seuil, tout nombre magique dit **d'où il vient et quand il a été
mesuré**. Exemple réel dans cette zone : `SEUIL_DEFAUT = 0.99` porte en commentaire qu'il ne suffit pas
à lui seul, parce que 99,44 % de couverture cachaient tout le chemin de login le 04/09.

**d) Vérifie par script, pas à l'œil.** Relire son propre fichier ne prouve rien, c'est l'angle mort de
l'auteur. Un script qui parcourt chaque `def` et compte celles sans commentaire rend un chiffre ; ton
impression, non. Et **rejoue les `--epreuve` après avoir commenté** : ajouter des lignes dans un fichier
est une modification comme une autre.

## 8. Si un chiffre te surprend
Dans cet ordre, **avant** de conclure quoi que ce soit sur le terrain :
1. **L'instrument a-t-il REGARDÉ ?** Un compte nul et un instrument qui n'a rien lu s'écrivent pareil.
   Chaque outil imprime sa progression et le volume lu : lis-les.
2. **Le compte est-il remesuré par un second chemin ?** §4.5. Un extracteur qui concatène produit un
   compte plausible qui n'est le compte de rien (ici : « 9 routes » là où il y en a 372).
3. **La gate mord-elle encore ?** Relance `--epreuve`. Une gate qui ne rougit sur aucun sabotage est
   inerte, et son vert ne vaut rien.
