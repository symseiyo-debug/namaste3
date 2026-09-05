# CODEC 3.0 — framing, enveloppe, opcodes (étage 2, socle)

> Livré le 2026-09-04. .NET 8 (SDK 8.0.130), code À NOUS, 0 dépendance dans le cœur.
> Gate : `./gate-codec.sh` (`--epreuve` = sabotage + témoin positif). **VERTE** :
> 355 trames réelles décodées et ré-encodées **byte-exact**, 71 tests, 0 échec.
>
> Sources, par ordre d'autorité :
> 1. **le dump du client** `internal/il2cpp-dump/il2cppinspectorredux/cs/il2cpp.cs` (57 Mo) — fait foi ;
> 2. **les 3 captures réelles** `refs/JondoEmu/datos/world_etapa*.bin` — la mesure ;
> 3. **le fragment Jondo** `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` — la spec lue, jamais copiée.
>
> Le dump n'a **pas de corps de méthode** (déclarations, champs, constantes, RVA seulement). Tout ce
> qui porte sur un COMPORTEMENT est donc soit mesuré sur les captures, soit tagué `DÉDUIT`.

---

## 1. Le fait le plus important : le jeu n'est PAS sur la pile Spin

Le client embarque **deux piles réseau distinctes**, et la doctrine de l'étage 1 les confondait.

| Pile | Classes (dump) | Ce qu'elle porte |
|---|---|---|
| **Spin** | `SpinConnection` (`il2cpp.cs:579462`), `SpinProtocol` (`:579681`), `SpinTransportLayer` (`:579841`), `FrameDelimiter` (`:261570`), `FrameDataBuffer` (`:261577`), `TcpConnectionLayer` (`:608091`) | launcher + **chat** — l'unique `IApplicationCodec` trouvé, `erq` (`:788406`), est typé sur `Core.Services.ChatService.AnkamaChatService.Protocol.Frame.Types.Payload` (`:788413-788414`) |
| **DotNetty** | `ProtobufVarint32FrameDecoder` (`:487219`), `ProtobufVarint32LengthFieldPrepender` (`:487229`), `gjv : MessageToMessageCodec<hea, object>` (`:825175-825205`), `gju : SimpleChannelInboundHandler<GameMessage>` (`:825162`), `GameMessage` (`:277004`) | **le jeu** — `gjv` porte le littéral `"type.ankama.com"` (`:825181`) et manipule `Any` ; `gjx : gjw<kqy>` (`:825218`) est un handler d'opcode de jeu (`kqy` = pong) |

**Pourquoi ce n'est pas qu'une curiosité d'architecture** : la pile Spin met un **octet de type de
message** en tête de chaque charge utile — `SpinProtocol.MessageType` (`il2cpp.cs:579716-579724`) :
`Application=0, Ping=1, Pong=2, Heartbeat=3, ApplicationCompressed=4, Capabilities=5`, écrit par
`MessageWithPayload.Serialize(MessageType, …)` (`:579768`). Un codec de jeu qui aurait suivi le dump
« SpinConnection » aurait cherché cet octet.

**Mesure qui tranche** (VÉRIFIÉ, sur les 3 fixtures) : la première trame de `world_etapa1` est
`19 0a 17 0a 15 0a 13 "type.ankama.com/kqp"`. `0x19 = 25`, et il reste **exactement 25 octets**
qui commencent par `0a` = *(champ 1, wire type 2)*. **Aucun octet de type de message.** Les 355
trames se décodent sans lui, et se ré-encodent byte-exact. La pile de jeu est donc bien
`varint(len) ++ protobuf`, sans en-tête Spin.

> **Écart de doctrine à corriger en amont** : `internal/LITTERAUX-RESEAU-EN-CLAIR.md` §« Couche
> transport » oriente l'étage 1 vers `SpinConnection.cs` / `FrameDelimiter.cs` pour la famille
> transport. C'est la bonne piste pour **le launcher et le chat**, pas pour le socket de jeu.

---

## 2. Le framing (VÉRIFIÉ)

```
frame := varint(len) ++ bytes[len]          # len EXCLUT ses propres octets
```

- **Varint32, longueur exclusive** : c'est le contrat de `ProtobufVarint32FrameDecoder` /
  `ProtobufVarint32LengthFieldPrepender` (`il2cpp.cs:487219`, `:487229`), et c'est ce que
  **mesurent les 3 fixtures** (355 trames, 0 octet en trop, 0 octet manquant).
- **Plafond 131 072 octets** : `SpinConnection.DefaultMaximumMessageSize` (`il2cpp.cs:579468`).
  Jondo mesure la MÊME valeur, par une autre voie (message d'erreur du `Player.log` client). Deux
  natures de source qui concordent. La plus grosse trame réelle mesurée fait 87 878 o (`ivi`), soit
  67 % du plafond — le plafond est réel, pas théorique.
- **Un varint de longueur peut arriver coupé.** `FrameDataBuffer.TryGetPayload` / `CompactIfNeeded`
  (`il2cpp.cs:261589-261590`) décrit la même mécanique de recollage côté client. Notre `FrameReader`
  distingue strictement **incomplet** (rendre `false`, attendre) de **invalide** (refus nommé) — un
  délimiteur qui confond les deux ferme la connexion sur un simple segment TCP court.

### Le drapeau `headerSizeIncludesItself` — un écart réel entre les deux piles

`FrameDelimiter(…, bool headerSizeIncludesItself, …)` (`il2cpp.cs:261595`) et
`FrameDataBuffer.TryGetPayload(bool messageSizeIncludesItself, …)` (`:261589`) ; et
`SpinConnection.SpinHeaderSizeIncludesItself = true` (`il2cpp.cs:579474`).
**Sur les fixtures de jeu, la longueur EXCLUT l'en-tête** (mesuré). Les deux modes existent donc
dans le client, sur deux piles différentes. Notre codec expose le drapeau, par défaut « exclut », et
le mode « inclut » est **éprouvé** (`VarintTests.SelfIncludingHeader_RoundTrips`, 8 tailles dont les
frontières 127/128) plutôt que déclaré et jamais parcouru.

---

## 3. L'enveloppe (VÉRIFIÉ sur le dump, structure exacte)

```proto
message hea {                 // racine / root — il2cpp.cs:839326-839367
  oneof {                     // discriminant hdz : None=0, 1, 2, 3  (:839361-839367)
    hdx f1 = 1;               // :839331
    hdy f2 = 2;               // :839332
    hdw f3 = 3;               // :839333
  }
}
message hdx { Any f1 = 1; repeated int32 f2 = 2; }   // :839134-839144
message hdy { Any f1 = 1; int32        f2 = 2; }     // :839224-839234
message hdw { Any f1 = 1; int32        f2 = 2; }     // :839045-839054
message Any { string type_url = 1; bytes value = 2; } // google.protobuf.Any, préfixe "type.ankama.com/"
```

Le préfixe est le littéral `dxji = "type.ankama.com"` (`il2cpp.cs:825181`), champ de la classe qui
fabrique les `Any` (`gjv`, `:825189-825203` : `noo`, `mlz`, `bkng`, `xt`, `nrs` rendent toutes un `Any`).

### Sens (`Direction`) — VÉRIFIÉ pour la forme, DÉDUIT pour le sens

Le dump donne les **formes**, pas les **sens**. La table `f1 = push S2C / f2 = requête C2S /
f3 = réponse S2C` vient de Jondo (§3.1, mesuré sur 103 808 frames). Ce que **nous** mesurons :

| Fixture | f1/Push | f2/Request | f3/Answer |
|---|---:|---:|---:|
| `world_etapa1_tras_elegir_personaje.bin` | 322 | **0** | 0 |
| `world_etapa2_tras_confirmar.bin` | 2 | **0** | 0 |
| `world_etapa3_mapa.bin` | 30 | **0** | 1 |

Les 3 fixtures sont des captures **serveur→client**. Zéro trame de cas f2 sur 355 : cohérent avec
« f2 = requête client ». C'est une **corroboration**, pas une preuve — un f2 absent d'un flux S2C ne
dit rien de ce que le client envoie. **Comment le prouver** : décoder une capture client→serveur
(aucune sur ce VPS) ou brancher le sniffer sur le client vivant à G2.

`hdy` et `hdw` ont exactement la même forme ; **rien dans le dump ne dit lequel est f2 et lequel est
f3**. Sans importance pour le codec (les deux se décodent pareil), à savoir pour qui lira le dump.

---

## 4. Écarts dump ↔ Jondo (le dump gagne, et on le note)

| # | Jondo dit | Le dump dit | Conséquence |
|---|---|---|---|
| 1 | id de requête `i64` (§3.1) | **`int32`** — `hdw.ebfc` / `hdy.ebfp` sont des `int` (`il2cpp.cs:839054`, `:839234`) | Compatible sur le fil (varint, signe étendu sur 64 bits) : `-1` sort sur 10 octets `ff×9 01`, ce que Jondo mesure aussi. **Mais un serveur qui déclarerait `int64` accepterait des ids que le client tronquera.** Notre codec lit le varint brut et le rend en `long?`, sans le tronquer. |
| 2 | `1:Any (push S2C)` — un seul champ | `hdx` a **deux** champs : `Any f1` + **`repeated int32 f2`** (`il2cpp.cs:839138-839140`) | Champ **déclaré mais jamais observé** : mesuré sur les **354 trames push** des fixtures, la forme du wrapper est `[f1:wt2]` — 0 occurrence de f2. Déclaré ≠ exercé. Notre codec le préserve génériquement, donc une trame qui le porterait survivrait au round-trip. |
| 3 | framing « varint(len) » sans plus | Deux modes coexistent (`headerSizeIncludesItself`, cf. §2) | Le mode Spin ne s'applique pas au jeu. Implémenté et éprouvé quand même. |
| 4 | protocole de connexion nu : racine `mhh` à 3 champs, le 3ᵉ (`mhn`) non implémenté par Jondo (§(b).4) | hors périmètre de ce codec | **Limite assumée, cf. §7.** |
| 5 | fixture 2 = « rafale de bienvenue » (prémisse de ma mission) | — | **RÉFUTÉ par la mesure, cf. §5.** |
| 6 | les fixtures « contiennent SPÉCIFIQUEMENT les opcodes de `WorldEntry.NotReplayed` » (fragment §(c)) | — | **RÉFUTÉ par la mesure, cf. §5.** |

---

## 5. Hypothèses REÇUES et réfutées par la mesure

Deux affirmations m'ont été transmises comme acquises. Les deux sont fausses, et les consigner coûte
moins cher que de les laisser voyager.

**(a) « La fixture 2 porte la rafale de bienvenue »** — mon brief me demandait de comparer la liste
d'opcodes de `world_etapa2_tras_confirmar.bin` à la séquence `kra lqu hoy kqu mgq mgt hpd krs mgz
kqp kqp kqp kvi kvd jtg` du fragment Jondo §3.6. **Mesuré : la fixture 2 contient exactement deux
trames, `jby` (39 o) puis `jtg` (2 306 o).** Sur les 13 opcodes distincts de la rafale, **un seul**
(`jtg`) est présent, et il l'est aussi bien par coïncidence de rôle que de séquence.

La confusion est explicable et vaut d'être nommée : la rafale de bienvenue est **construite en
code** (`ConnectionProtocol.BuildWelcomeBurst`, cité §3.6 du fragment), tandis que les trois `.bin`
sont les blocs d'**entrée monde** rejoués (`WorldEntry.SendAfterCharacterAsync` / `SendAfterConfirmAsync`
/ `SendMapAsync`, fragment §(c)). Deux moments différents de la séquence, deux mécanismes différents.
**Aucune capture de la rafale de bienvenue n'existe sur ce VPS** — la valider demandera un sniffer
sur le client vivant (étage 5) ou une capture Jondo non rapatriée.

Contrôle : la recherche fonctionne bien (témoin positif — `jtg` trouvé dans la fixture 2, `kqp` dans
la fixture 1, `lqu` dans la fixture 3). Les 10 autres opcodes de la rafale sont absents des **trois**.

**(b) « Les fixtures contiennent les opcodes de `WorldEntry.NotReplayed` »** (fragment §(c), dernier
paragraphe : `kqg`, `jhe`, `jhh`, `jhk`, `hol`, `jgu`, `ihb`, `koj`, `ife`, `jjs`, `jaa`).
**Mesuré : 0 occurrence des 11, dans les 3 fixtures.** Soit le filtre est appliqué avant l'écriture
des `.bin`, soit l'affirmation est erronée. Dans les deux cas, **les fichiers sur disque n'en portent
aucun** — la précaution qu'annonce le fragment n'a pas d'objet ici.

---

## 6. Ce qui reste DÉDUIT — et ce que le dump permet d'en dire

**Y a-t-il une compression ?** Sur le lien de jeu : **aucune trace**, et c'est mesuré — les 355
trames sont du protobuf en clair, `ivi` fait 87 878 o non compressés. La machinerie de compression
que porte le dump appartient à la pile **Spin** : `MessageType.ApplicationCompressed = 4`
(`il2cpp.cs:579722`), `Capabilities.Compression = 0` (`:579729`), `SpinTransportLayer.
ProcessCompressedApplicationMessage` (`:579923`), `MinGainForCompression = 50` (`:579846`),
`SpinConnection.DefaultCompressionThreshold = 1024` (`:579472`). **Et `allowCompression` vaut
`false` par défaut** dans le constructeur `SpinConnection` (`il2cpp.cs:579586`).
→ DÉDUIT : pas de compression sur le socket de jeu. **Comment vérifier** : sniffer le client vivant ;
si une trame de jeu arrive compressée, notre `Envelope.Decode` refusera nommément (`AnyMalformed`
ou `RootCaseMissing`) au lieu de rendre du faux.

**Y a-t-il un chiffrement ?** Le paramètre existe côté Spin : `SpinTransportLayer.ConnectAsync(host,
port, bool useSsl)` (`il2cpp.cs:579907`). Sur le jeu, les fixtures sont en **clair** — mais ce sont
des captures Jondo en 127.0.0.1, ce qui ne dit **rien** du vrai serveur Ankama. DÉDUIT.
**Comment vérifier** : observer si le client négocie TLS sur le port de jeu réel.

**Y a-t-il un heartbeat ?** Deux, à deux étages différents, et il ne faut pas les confondre :
- **transport Spin** : `SpinProtocol.HeartbeatMessage` (`il2cpp.cs:579811`), `DefaultHeartbeatDelay
  = 2000` ms (`:579470`), `PingsDelay = 3f` s (`:579478`) — **pas sur le lien de jeu** ;
- **application (jeu)** : les opcodes `kqo` (ping C2S) / `kqy` (pong S2C), toutes les 5 s selon Jondo
  (2 890 occurrences sur 235 captures). **Mesuré ici** : `kqy` est la 1ʳᵉ trame de `world_etapa3`,
  avec `f1: varint 1` — exactement ce que le fragment annonce (`ConnectionProtocol.cs:626`), et sur
  le **cas racine 1 (push)**, pas 3, comme le fragment le souligne. Corroboration indépendante.

**Autres constantes du dump utiles à l'étage 3, non exploitées ici** :
`SpinProtocol.ConnectionErrors` (`il2cpp.cs:579685-579704`) — 17 causes de refus nommées
(`BadCredentials`, `AccountKnownButBanned`, `BadClientVersion`, `ServerNotYetReady`…) ;
`SpinProtocol.CheckAuthentication(byte[] jsonPayload, …)` (`:579835`) dit que la charge
d'authentification **Spin** est du **JSON**, pas du protobuf.

**Corroborations mesurées au passage** (le codec sert déjà de sonde) :
`lqu` → `f1: 120` (le `SyncRate` que Jondo donne pour 120) et `f2: 1786294591020` (unix-ms →
2026-08-11, cohérent avec la chaîne `"2026-08-11"` lue dans la trame `jez` de la même capture) ;
`jru` → `f2: 179306497` (un `mapId`, champ 2, comme annoncé) ; l'unique trame de cas f3 porte
`reqId = -1`, cohérent avec les 98,9 % mesurés par Jondo.

---

## 7. Périmètre — ce que ce codec NE fait PAS

1. **Le protocole de connexion NU (phase 1, port 5555 avant l'enveloppe)** n'est pas couvert. Sa
   racine est `mhh` (`datos/protocolo_conexion_3.6.10.10.proto:163-178`), sans `Any` ni `typeUrl` :
   `Envelope.Decode` le refuse nommément (`AnyMissing`). C'est **volontaire** — mais l'étage 3 en
   aura besoin, et le `FrameReader`/`ProtoReader`/`Varint` d'ici s'y appliquent tels quels : seul un
   second parseur d'enveloppe est à écrire. Le champ 3 (`mhn`) que Jondo n'implémente pas
   (§(b).4 du fragment) tombera dans les champs génériques, donc **ne sera pas perdu**.
2. **Aucune sémantique d'opcode.** Le codec rend `opcode + sens + charge brute + arbre générique`.
   Nommer les champs est le travail de l'étage 1 (le graphe), pas du codec.
3. **Le sens C2S n'est prouvé par aucune frame réelle** (cf. §3) — la table est celle de Jondo.
4. **Pas de socket.** Le codec est pur : entrée octets, sortie octets. Le branchement TCP est
   `Codec3GameClient` (étage 3, §8).

---

## 8. L'API pour l'étage 3

```csharp
var codec = new Codec3();                       // pas d'horloge, pas d'aléa, pur

// Décoder un fichier ou un socket. Les segments TCP arbitraires sont gérés.
DecodeResult result = codec.Decode(bytes);
DecodeResult result = codec.DecodeSegments(segments);   // IEnumerable<ReadOnlyMemory<byte>>

foreach (RawMessage m in result.Messages)
{
    m.Opcode.Name       // "jru"          — 3 lettres, m.Opcode.IsCanonical dit si la forme tient
    m.Direction         // Direction.S2C  — dérivé du cas racine
    m.Case              // RootCase.Push | Request | Answer
    m.RequestId         // long? — présent sur Request/Answer
    m.Payload           // byte[] — la charge de l'opcode, BRUTE (pas de schéma)
    m.Fields            // arbre générique {numéro, wireType, valeur|sous-arbre}
    m.Offset            // offset absolu dans le flux
}

byte[] wire = codec.Encode(result.Messages);    // ré-encodage byte-exact
```

**Pour un flux vivant**, la boucle est celle-ci (c'est exactement ce que
`Codec3GameClient.Pump()` doit faire, cf. `bot-testeur/SPEC.md` §8.1) :

```csharp
var reader = new FrameReader();                 // plafond 131 072 par défaut
reader.Append(bytesReadFromSocket);
while (reader.TryReadFrame(out byte[] frame, out long offset))
    queue.Enqueue(codec.DecodeFrame(frame, offset, stats));   // METTRE EN FILE, ne pas appliquer
```

`TryReadFrame` rend `false` tant qu'il manque des octets : **c'est la seule condition d'arrêt**, et
elle ne lève jamais. Toute autre anomalie est un `CodecException` avec un `CodecErrorCode` et un
offset — jamais une exception nue (14 codes, tous levés par le cœur ET assertés par un test — une garde structurelle le vérifie).

**Pour émettre**, construire l'enveloppe puis encadrer :

```csharp
var writer = new FrameWriter();
socket.Write(writer.Frame(envelope.Encode()));
```

---

## 9. Ce que la gate mesure vraiment (et ses angles morts)

`./gate-codec.sh` — rejouable, déterministe, 0 jeton. `rc=0` seulement si **tout** passe.

| Étage | Ce qui est vérifié |
|---|---|
| 0 | les 3 fixtures existent et leur **sha256** est celui du 04/09 (une fixture qui change sans qu'on le sache rendrait ce vert celui d'autre chose) |
| 1 | `dotnet build` |
| 2 | `dotnet test` — **71 tests** |
| 3 | round-trip byte-exact fixture par fixture, avec trames / opcodes distincts / sha avant-après |
| 4 (`--epreuve`) | une fixture sabotée doit rendre la gate **ROUGE**, et la même copie intacte doit rester **VERTE** (témoin positif : sans lui, le rouge pourrait venir de la copie et non du sabotage) |

**Le round-trip seul ne suffirait pas**, et c'est le piège que ce projet évite explicitement : un
codec qui recopierait ses octets d'entrée rendrait le même vert. Trois garde-fous :

1. **Le ré-encodage est structurel, pas une recopie.** Le varint de longueur est réécrit depuis la
   longueur décodée ; le `typeUrl` repasse par la **chaîne UTF-8** décodée ; l'enveloppe est
   reconstruite depuis le cas racine, l'`Any` et l'id. Seule la charge utile d'opcode est opaque —
   c'est assumé (« décoder sans schéma ») et déclaré.
2. **Les sous-arbres sont comptés.** `ProtoReader` ne garde un sous-arbre que s'il se **ré-encode
   octet pour octet** en sa charge d'origine ; sinon la charge reste opaque et le compteur le dit.
   Mesuré : 20 990 / 135 / 29 852 champs décodés, **18 317 sous-arbres exacts**, 444 feuilles
   opaques (chaînes et blobs). Un parseur cassé ferait chuter le premier nombre sans casser le
   round-trip — c'est pour ça que les deux sont imprimés.
3. **Le sabotage.** 2 348 essais, **un octet retourné (XOR 0xFF) à chaque position**, sur la petite
   fixture : **59 refus nommés** (`TypeUrlInvalid` ×38, `InvalidWireType` ×8, `AnyMalformed` ×8,
   `LengthExceedsBuffer` ×4, `FrameTooLarge` ×1), **2 289 sha différents**, **0 absorbé en silence**.
   Le test exige les **deux** natures de réaction : n'en avoir qu'une signifierait qu'un mécanisme
   est éprouvé et l'autre seulement affirmé.

**Angles morts, nommés** :
- Le sens **C2S n'est éprouvé sur aucune frame réelle** (§3). Les tests C2S sont synthétiques.
- Le second champ de `hdx` (§4 ligne 2) est **préservé par construction**, jamais vu en vrai.
- Les 42 + 2 + 17 opcodes rencontrés viennent de **3 captures d'entrée monde**. La phase de
  connexion, la rafale de bienvenue et la sélection de perso **ne sont pas dans cette matière**.
- Le décodage ne prouve pas qu'un **client vivant accepte** ce que nous ré-encodons : le round-trip
  prouve la fidélité au fil, pas l'acceptabilité. C'est la gate G2, pas celle-ci.

### Segmentation TCP — la preuve la plus dense

`SmallFixture_EverySplitPoint_YieldsIdenticalResult` coupe la fixture de 2 348 octets en deux
segments à **chacune des 2 347 positions possibles** et exige, à chaque fois, le même nombre de
trames et le même sha ré-encodé : **2 347 découpes, 0 échec**. S'y ajoutent la livraison **octet par
octet** (2 348 segments d'un octet), une découpe irrégulière sur la fixture de 90 935 o, et un flux
tronqué qui doit **refuser** à la fermeture (`TrailingBytes`) plutôt que rendre une trame partielle.

---

## 10. Arborescence

```
codec/
├── Namaste3.Codec.sln · gate-codec.sh · CODEC.md
├── src/Namaste3.Codec/             (net8.0 lib, 0 dépendance, fichier max 241 lignes)
│   ├── Varint.cs           base-128, bornes, « incomplet » ≠ « invalide »
│   ├── CodecException.cs   14 codes d'erreur NOMMÉS + offset
│   ├── ProtoField.cs       un champ décodé sans schéma (+ rendu texte)
│   ├── ProtoReader.cs      lecture stricte, sous-arbres prouvés exacts, profondeur bornée
│   ├── ProtoWriter.cs      ré-écriture, ordre des champs préservé
│   ├── FrameReader.cs      délimitation sur flux TCP (partiel, multiple, à cheval)
│   ├── FrameWriter.cs      préfixe varint, 2 modes
│   ├── Direction.cs        RootCase 1/2/3 ↔ C2S/S2C
│   ├── Opcode.cs           typeUrl ↔ 3 lettres
│   ├── Envelope.cs         racine + wrapper + Any, champs inconnus préservés en place
│   ├── RawMessage.cs       ce que l'étage 3 consomme
│   └── Codec3.cs           façade : Decode / DecodeSegments / Encode
├── src/Namaste3.Codec.Sniff/       `namaste3-sniff <fichier|-> [--summary] [--hex] [--depth N]`
└── tests/Namaste3.Codec.Tests/     71 tests — RoundTrip · Segmentation · Negative · Sabotage · Varint
```

**Le sniffer est la base de l'outil communautaire de l'étage 5** : il lit un fichier ou stdin, imprime
offset / longueur / sens / opcode / id de requête puis l'arbre des champs, et sort `rc=0` seulement
si le round-trip est byte-exact. `--summary` en fait une sonde silencieuse utilisable en script.
