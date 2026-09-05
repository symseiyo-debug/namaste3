# INTERFACES — contrats entre couches (étage 3)

<!-- gate-forme: contrat-interne -->

> # 🟡 v0 — ESQUISSES, À RÉVISER APRÈS LA CARTE
>
> Signatures **esquissées en markdown**, pas d'implémentation. Étage 3, écrit le 2026-09-04.
> **Sources lues** : les mêmes que `ARCHITECTURE.md` (liste en tête de ce fichier-là).
>
> **Aucun fichier `.cs` n'est écrit** (décision du 04/09) — mesuré, `find server -name
> "*.cs"` rend **0**. Ce qui suit vit dans des blocs markdown et n'est compilé par rien.
>
> **Ce que la carte peut déplacer, section par section.** §1 codec : le format de trame est mesuré sur
> 103 808 frames, il ne devrait pas bouger ; ce qui peut bouger, c'est la liste des refus nommés.
> §2 protocole : l'énumération `SemanticOp` est **volontairement squelettique** — elle se remplit
> depuis le graphe `graphe-protocole` et la table de correspondance du matcher, aujourd'hui à
> **511 lignes sur 515 en `À_CLASSER`**. §3 dispatch, §4 domaine, §5 persistance, §6 trace : ces
> contrats ne nomment aucun opcode, ils devraient survivre à la carte. §7 port du bot : à négocier
> avec l'auteur du bot, pas à imposer.
>
> ⚠️ **Faux positif connu de `tools/protocol-mapping/tools/gate-forme.py` sur CE fichier.** Sa règle
> `R4-code-csharp-recopie` lève dès qu'un bloc clôturé contient deux signatures de méthode
> (`gate-forme.py:238-246`). Elle est conçue pour les fragments d'**étage 1**, qui lisent du code
> tiers : elle garde contre la recopie sous licence. Ici les signatures sont **les nôtres**, écrites
> pour être implémentées — la règle mesure une FORME et ne peut pas distinguer l'acte. Remède proposé :
> borner R4 aux étages 0-1, ou exempter les blocs marqués comme conception propre.
> **Ne pas mutiler ce contrat pour faire verdir la gate** : ce serait rendre l'instrument vert par
> l'instrument, pas par le terrain.
> Ce document est le contrat de référence pour tout travail sur l'étage 3. Une signature qui
> change ici est un **événement de revue** (fichier-contrat : tout diff sur un fichier-contrat =
> revue obligatoire).
> Commentaires bilingues FR/EN sur le code de frontière, règle du projet.

---

## 1. `Namaste3.Codec` — ce que l'étage 3 attend du codec

> ✅ **Le codec est arrivé pendant cette rédaction** : `codec/` porte `CODEC.md`,
> `gate-codec.sh`, `src/`, `tests/`. Ce paragraphe reste le contrat **attendu** par l'étage 3 ; il se
> confronte au livré à J3.0, en rejouant la gate nous-mêmes plutôt qu'en lisant son rapport.

### 1.0 🔴 DEUX PILES — ne pas confondre le jeu et le launcher

**Correction mesurée par le codec contre 355 trames réelles**
(`internal/LITTERAUX-RESEAU-EN-CLAIR.md`, 04/09 23 h) : le socket de jeu **n'est pas** sur la pile
`SpinConnection`.

| | Pile | Framing | Préfixe |
|---|---|---|---|
| **Launcher, chat** | `SpinConnection` | `FrameDelimiter` | **un octet de type** (Application=0, Ping=1, Pong=2, Heartbeat=3, `il2cpp.cs:579716`) |
| **JEU** | **DotNetty** | `ProtobufVarint32FrameDecoder` (`il2cpp.cs:487219`) | **aucun** — la longueur varint couvre exactement le protobuf |

Le codec de jeu passe par `gjv : MessageToMessageCodec<hea, object>`, qui porte le littéral
`type.ankama.com` (`il2cpp.cs:825181`), et `gjx : gjw<kqy>` pour l'opcode. **Un codec écrit sur la
section Spin chercherait un octet qui n'existe pas sur le fil de jeu.** Le contrat §1.1 ci-dessous
décrit la pile de JEU, et elle seule.

### 1.1 Le format, tel que mesuré

```
frame := varint(len) ++ bytes[len]                     # len ≤ 131072 (plafond client mesuré)
root  := { 1: Any            (push   S2C)
         | 2: Any + i64 reqId (request C2S)
         | 3: Any + i64 reqId (answer  S2C) }
Any   := { 1: string "type.ankama.com/xxx" , 2: bytes payload }   # xxx = EXACTEMENT 3 lettres
```

Source : `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:254-279` (mesuré par Jondo sur 103 808 frames
/ 242 captures) ; plafond 131 072 octets `:260-262` ; contrôle des 3 lettres `NetworkEnvelope.cs:11-20`.

### 1.2 Signatures attendues

```csharp
// FR : Découpe un flux TCP en frames. Ne connaît AUCUN opcode.
// EN : Splits a TCP stream into frames. Knows NO opcode.
public interface IFrameDelimiter {
    // Rend false s'il manque des octets ; ne consomme rien dans ce cas.
    bool TryReadFrame(ref ReadOnlySequence<byte> input, out ReadOnlySequence<byte> frame);
    void WriteFrame(IBufferWriter<byte> output, ReadOnlySpan<byte> body);
    int MaxFrameBytes { get; }   // 131072 — refus AVANT allocation
}

public enum RootKind { Push = 1, Request = 2, Answer = 3 }

public readonly record struct Envelope(
    RootKind Kind,
    string   Opcode,      // 3 lettres, SANS le préfixe "type.ankama.com/"
    long     RequestId,   // -1 dans 98,9 % des cas mesurés — LU, jamais supposé
    ReadOnlyMemory<byte> Payload);

public interface IEnvelopeCodec {
    // FR : Échoue par un motif NOMMÉ, jamais par une exception nue ni un silence.
    // EN : Fails with a NAMED reason, never a bare exception nor silence.
    bool TryDecode(ReadOnlySequence<byte> frame, out Envelope env, out CodecRefusal refusal);
    void Encode(IBufferWriter<byte> output, in Envelope env);
}

public enum CodecRefusal {
    None, FrameTooLarge, RootFieldUnknown, OpcodeLengthNot3,
    TypeUrlPrefixMismatch, PayloadTruncated, RequestIdMissing }
```

### 1.3 Trois exigences non négociables

1. **Le champ racine 3 du protocole de CONNEXION doit être parsé.** Le `.proto` reconstruit déclare
   trois champs sur `mhh` (`gfcd=1`, `gfce=2`, `gfcf=3` de type `mhn`) ; Jondo n'en implémente que
   deux (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:906-913`). Ne pas copier cette omission : parser sans
   planter, même si le champ reste vide.
2. **`RequestId` est lu et réinjecté, jamais codé en dur.** 15 416 requêtes sur 15 583 portent `-1`
   (98,9 %, `:771`) — les 167 restantes casseraient en silence.
3. **Gate d'acceptation** : round-trip **byte-exact** sur les trois fixtures réelles,
   **322 + 2 + 31 = 355 frames**, 0 écart (`:930-947`). Un `rc=0` sur 0 frame décodée est un échec :
   la gate compte les frames.

---

## 2. `Namaste3.Protocol` — la table de dispatch est une DONNÉE, pas du code (L6)

**La loi L6 change la nature de cette couche.** L'opcode 3 lettres **est** le nom de classe obfusqué,
donc il est re-brassé à chaque build. La table n'est donc **ni compilée, ni écrite à la main** : elle
est **générée par build** et **chargée au démarrage**.

```csharp
// FR : Chargée au démarrage depuis protocol/binding-<build>.tsv. Aucun opcode littéral dans src/.
// EN : Loaded at startup from protocol/binding-<build>.tsv. No literal opcode in src/.
public interface IOpcodeTable {
    static IOpcodeTable LoadForBuild(string build, Stream bindingTsv);   // ex. "3.6.10.10"
    string Build { get; }                                    // la build est portée par la table
    bool TryResolve(string opcode, out MessageDescriptor d);            // fil -> type
    string OpcodeOf(SemanticOp op);                                     // sémantique -> fil
    IReadOnlyList<SemanticOp> Unbound { get; }   // sémantiques SANS opcode dans cette build
}

// Noms SÉMANTIQUES stables : ce sont eux que les handlers connaissent, pour toujours.
public enum SemanticOp {
    AuthTicket, AuthTicketCompanion /* sens INCONNU, cf. DAG J3.2 */,
    CharactersList, CharacterSelection, MapCurrentEvent, MapMovementRequest, /* … */ }
```

**Trois conséquences dures.**
1. **`Unbound` n'est pas une erreur, c'est un état normal.** Une build peut ne pas porter un opcode
   qu'une autre portait. Le serveur démarre, dit lesquels manquent, et **refuse** les handlers
   concernés avec un motif nommé — il ne devine pas.
2. **La build est une clé partout** : nom du fichier de liaison, colonne des tables de protocole,
   nom des fixtures, clé des `.tsv`. Deux artefacts de builds différentes ne se joignent jamais.
3. **Une table tierce ne se consomme jamais sans épreuve.** Mesure fondatrice : entre Jondo et otomai,
   tous deux étiquetés « 3.6.10.10 », **84 % des opcodes collisionnent mais 0 accord de sens sur 27
   examinés**, pour un bruit de fond de 30 % — `jru` charge la carte chez l'un, répond d'arène chez
   l'autre. **Un opcode venu d'une autre build est plausible et faux**, la pire des deux propriétés.

**Pourquoi l'indirection, chiffré** : sur 3.6.4.3 → 3.6.10.10 le matcher structurel ne réapparie que
**245/2169 (11,3 %)** des messages (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:830-833`) ; en 2.x, **868
classes sur 872** changent d'identifiant (99,5 %, `ARCHI-REFERENCE-JIVA.md` §F.1). Un patch doit
toucher **une donnée régénérée**, pas une ligne de code.

**Gate** : `grep -rnoE '"[a-z]{3}"' src/ --include=*.cs` doit rendre **0**.

---

## 3. `Namaste3.Net` — dispatch et handlers

```csharp
// FR : Le handler déclare un nom SÉMANTIQUE, jamais un opcode. L'opcode arrive par la table (L6).
// EN : The handler declares a SEMANTIC name, never an opcode. The opcode comes from the table (L6).
[AttributeUsage(AttributeTargets.Method)]
public sealed class HandlerAttribute : Attribute {
    public HandlerAttribute(SemanticOp op) => Op = op;   // SemanticOp.MapMovementRequest
    public SemanticOp Op { get; }                        // JAMAIS une chaîne de 3 lettres
    public bool RequiresSession { get; init; } = true;   // garde login-requis, défaut fermé
    public bool RequiresCharacter { get; init; } = false;
}

public sealed class HandlerRegistry {
    // FR : L'indirection est DANS la signature — le registre ne se construit pas sans la table
    //      de CETTE build. Il n'existe aucune surcharge qui accepte des opcodes littéraux.
    // EN : The indirection is IN the signature — no overload accepts literal opcodes.
    public static HandlerRegistry BuildFor(Assembly handlers, IOpcodeTable table);

    public bool TryGet(string wireOpcode, out HandlerEntry entry);  // fil -> handler, O(1)

    // FR : Les sémantiques déclarées par un handler mais ABSENTES de la table de cette build.
    //      Le démarrage les nomme et refuse les messages concernés ; il ne devine jamais.
    public IReadOnlyList<SemanticOp> Unbound { get; }
}
```

**Ce que la signature garantit** : `BuildFor` exige une `IOpcodeTable` **portant sa build**. Un
registre construit avec la table d'une autre build est donc un objet différent, pas une valeur par
défaut silencieuse. C'est la réponse structurelle à la mesure Jondo/otomai — **84 % de collisions
d'opcodes, 0 accord de sens sur 27** : deux tables « 3.6.10.10 » qui ne sont pas la même build.

**Deux patrons repris, une erreur évitée.** Réflexion + attribut + table : Jiva
(`ARCHI-REFERENCE-JIVA.md` §D, `HandlerManager<...>`) et Giny (`ARCHI-REFERENCE-GINY.md` §C.2) le font
tous les deux — invariant. Dériver l'opcode du **type du paramètre** plutôt que de l'écrire dans
l'attribut vient de Giny seul : le handler ne peut pas mentir sur l'opcode qu'il traite. On évite
explicitement le défaut mesuré au même endroit chez lui : `Handlers.FirstOrDefault(x => x.Key == id)`,
un parcours **O(n)** sur un dictionnaire, par paquet reçu, sur ~1182 types de message (§C.2).

### 3.1 La règle qui protège la frontière

Un handler **traduit**. Il n'appelle jamais le domaine avec un type du protocole :

```csharp
[Handler(RequiresCharacter = true)]
public static ValueTask OnMoveRequest(ISessionContext s, jrw msg)   // type GÉNÉRÉ, ici seulement
{
    var cmd = new MoveCommand(                       // record du DOMAINE, 0 dépendance protocole
        MapId: msg.MapId, Keys: msg.Path);
    return s.Area.Post(cmd);
}
```

`Namaste3.World` ne contient **aucun** `using Namaste3.Protocol` — gate mesurée, `DAG.md` J3.C.

---

## 4. `Namaste3.World` — le domaine

### 4.1 L'Area et le jeton qui rend le garde obligatoire

```csharp
// FR : Preuve d'exécution DANS la boucle de l'Area. Aucun constructeur public ; ref struct donc
//      non capturable dans une lambda, un champ ou une méthode async.
// EN : Proof of execution INSIDE the Area loop. No public ctor; ref struct hence non-capturable.
public readonly ref struct AreaTick { }

public sealed class Area {
    public AreaId Id { get; }
    // Seul point d'entrée depuis l'extérieur. Ne mute rien : met en file.
    public ValueTask Post(IAreaCommand command);
    // Démarre à l'entrée du premier personnage, s'arrête à la sortie du dernier (patron Jiva §B.1).
    internal Task RunAsync(CancellationToken ct);
}

public interface IAreaCommand { }
public readonly record struct MoveCommand(long MapId, ReadOnlyMemory<int> Keys) : IAreaCommand;
public readonly record struct EnterMapCommand(CharacterId Id, long MapId) : IAreaCommand;
```

Toute mutation de domaine prend un `AreaTick` en premier paramètre :

```csharp
public sealed class Character {
    public Cell Cell { get; private set; }
    public void ApplyMove(AreaTick _, Path validated);       // ne compile pas hors de la boucle
}
```

### 4.2 Le chemin, et pourquoi il n'a pas de constructeur

```csharp
public enum MoveRefusal {
    None, MapMismatch, StartCellMismatch, CellOutOfRange,
    CellNotWalkable, PathNotContiguous, MovementBudget }

public readonly struct Path {
    private Path(/* … */);                                    // PRIVÉ, aucun autre chemin
    // FR : Les QUATRE contrôles. Aucune référence ne les a tous (Jiva §B.4/§E.1, Giny §C.3).
    // EN : The FOUR checks. No reference emulator has all of them.
    public static bool TryBuildValidated(
        Map map, Cell from, int budget, ReadOnlySpan<int> keys,
        out Path path, out MoveRefusal refusal);

    public static (int Cell, int Facing) DecodeKey(int key)    // (facing << 12) | cell
        => (key & 0xFFF, key >> 12);                          // invariant 2.42 / 2.68 / 3.0
}
```

`DecodeKey` est l'invariant mesuré sur trois émulateurs : Jiva `Path.cs:185-200`, Giny
`PathReader.cs:14-21` (`cell & 4095`, `>> 12`), 3.0 `jrw f2` (`SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:677`).

### 4.3 La carte

```csharp
public sealed class Map {
    public long MapId { get; }
    public int  SubAreaId { get; }        // JAMAIS 0 : un zéro fait planter le client (jss f6)
    public const int CellCount = 560;     // 14 × 40, mesuré (refs/JondoEmu/docs/world.md:18)
    public bool IsWalkable(int cellId);   // 230 vraies sur 560 pour 191105026 (mesuré)
    public bool AreAdjacent(int a, int b);// géométrie, pas de table stockée (patron Jiva §B.2)
}
```

**Piège nommé** : 230 est le compte des cellules MARCHABLES de 191105026, pas la taille de la grille.
Les identifiants montent jusqu'à 559. Un tableau de 230 plante au premier identifiant (91).

---

## 5. `Namaste3.Store` — persistance

```csharp
public interface ITicketStore {
    // FR : Émission — 24 octets CSPRNG, TTL 5 min, usage unique.
    Task<string> IssueAsync(AccountId a, int serverId, string lang, CancellationToken ct);
    // FR : Consommation ATOMIQUE. Remplace tout l'IPC du chemin critique (ARCHITECTURE §1.1).
    //      0 ligne rendue = refus ; il n'existe pas d'état intermédiaire.
    Task<TicketRedemption?> RedeemAsync(string ticket, CancellationToken ct);
}

public interface ICharacterStore {
    Task<IReadOnlyList<CharacterSummary>> ListForAccountAsync(AccountId a, CancellationToken ct);
    // FR : L'appartenance est vérifiée EN BASE, jamais sur ce que le client annonce.
    Task<Character?> LoadOwnedAsync(AccountId a, CharacterId c, CancellationToken ct);
}

public interface IWorldServerRegistry {              // remplace le heartbeat IPC (10 s, patron Jiva)
    Task HeartbeatAsync(int serverId, int charsCount, WorldState st, CancellationToken ct);
    Task<IReadOnlyList<WorldServerRow>> ListAsync(CancellationToken ct);
}
```

Identifiants : **UUIDv7** (convention du projet). Secrets : jamais en clair, jamais dans une chaîne formatée
en dur — contre-exemple mesuré, Giny `DatabaseManager.cs:18,39` (`ARCHI-REFERENCE-GINY.md` §E.2).

---

## 6. Observabilité — le contrat de la trace causale

```csharp
public interface IExecutionTrace {
    // FR : Cause -> conséquence. Le motif est NOMMÉ ; un refus sans motif est un défaut.
    // EN : Cause -> consequence. The reason is NAMED; an unnamed refusal is a defect.
    void Record(in TraceEntry e);
}

public readonly record struct TraceEntry(
    Guid   SessionId,
    string Op,            // constante sémantique, jamais l'opcode littéral
    string Kind,          // "request" | "decision" | "emit" | "refusal"
    string Name,
    string? Why,          // la CAUSE     (= push.why du bot)
    string? Result,       // la CONSÉQUENCE (= action.result du bot)
    long   VirtualOrWallMs);
```

Le schéma reprend celui que le bot-testeur produit déjà
(`internal/bot-testeur/SPEC.md:55-57`, `TraceEntry{tick,timeMs,kind,name,relevance,result,why}`) :
trace du bot et trace du serveur deviennent **jointes sur le même axe**, ce qui rend un écart
diagnosticable au lieu d'être deux récits séparés.

---

## 7. `IGameClient` — le port du bot-testeur vers notre serveur

Le bot existe et son port est déjà défini (`internal/bot-testeur/SPEC.md:194-223`). L'étage 3
livre l'adaptateur `Codec3GameClient : IGameClient`. Le contrat côté bot, **inchangé** :

```csharp
public interface IGameClient {
    ClientResult Connect(); ClientResult Login(string user, string pass);
    ClientResult SelectCharacter(long id); ClientResult EnterMap(long mapId);
    ClientResult MoveToCell(int cellId);
    void Pump();                 // SEUL endroit qui mute l'état — garde le moteur déterministe
    void Disconnect();
}
```

**Extensions à négocier avec l'auteur du bot, pas à imposer** : `Actors` (nécessaire à J3.4/J3.7) et
un `SendRaw(string opcode, ReadOnlyMemory<byte>)` de secours pour les scénarios adversariaux de J3.5
(envoyer un chemin volontairement invalide). Le SPEC anticipe déjà ces deux besoins (§10, « le port
`IGameClient` est une hypothèse de forme »).

**Horloge** : contre notre serveur, `VirtualClock` est remplacée par une `LiveClock` échantillonnée une
fois par tick (SPEC §8.2). Le rapport reste structuré et comparable ; il n'est **plus** byte-identique.
C'est attendu : le rejeu byte-identique est une propriété du **banc de test**, la mesure du serveur est une
**mesure**. Une gate qui exigerait l'identité d'octets contre un vrai serveur serait un faux rouge.

---

## 8. Ce qui ferme un jalon

Un jalon ne se ferme pas sur un rapport « Done. » nu : le statut attendu est `DONE` /
`DONE_WITH_CONCERNS` / `BLOCKED` / `NEEDS_CONTEXT`, avec ce qui est tranché, ce qui reste ouvert, et
sous quel critère de fermeture. Un handler « vert » sans scénario bot passé est **REFUTED** — le
compilateur ne ferme aucun nœud, seule la mesure le fait.
