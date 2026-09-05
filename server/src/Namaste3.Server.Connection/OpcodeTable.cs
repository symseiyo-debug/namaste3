// ============================================================================================
// QUOI : la table de liaison — chargée au démarrage depuis `protocol/binding-<build>.json`,
//     elle traduit dans les deux sens « nom sémantique stable » ⇄ « opcode 3 lettres du fil »,
//     et porte les FORMES des charges utiles que le serveur émet.
// POURQUOI (05/09/2026) : DECISIONS.md D-08 — un seul fichier nomme les opcodes littéraux, et
//     ce n'est pas du C#. Mesure fondatrice (INTERFACES.md §2) : entre deux tables tierces
//     toutes deux étiquetées « 3.6.10.10 », 84 % des opcodes collisionnent pour 0 accord de
//     sens sur 27 examinés — un opcode venu d'une autre build est « plausible et faux », la
//     pire des deux propriétés. La build est donc une CLÉ portée par la table elle-même.
// EN : the binding table, loaded at start-up; translates stable semantic names ⇄ 3-letter wire
//     opcodes both ways, and carries the shapes of the payloads the server emits.
// COMMENT LANCER / USAGE : `OpcodeTable.Load(chemin)` ; `--table <chemin>` côté Program.
// GATE : `gate-serveur.sh` étage « 0 opcode littéral dans src/ » + tests de chargement.
// ============================================================================================

using System.Text.Json;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : une ligne de la table — ce que le fil porte pour un nom sémantique, et la source qui
///      le prouve. `Source` n'est pas décoratif : il rend la table auditable sans relire le code.
/// EN : one table row — what the wire carries for a semantic name, plus the proving source.
/// </summary>
public sealed class OpcodeBinding
{
    /// <summary>Nom sémantique stable. / Stable semantic name.</summary>
    public required SemanticOp Op { get; init; }

    /// <summary>Opcode 3 lettres de CETTE build. / THIS build's 3-letter opcode.</summary>
    public required string Opcode { get; init; }

    /// <summary>Sens déclaré, tel qu'écrit par la table. / Declared direction.</summary>
    public required string Direction { get; init; }

    /// <summary>Nom clair, vide si aucun n'est établi. / Clear name, empty if none established.</summary>
    public required string ClearName { get; init; }

    /// <summary>La source qui prouve la ligne. / The source proving the row.</summary>
    public required string Source { get; init; }

    /// <summary>Verdict du recroisement étage 1. / Stage-1 cross-check verdict.</summary>
    public required string CrossCheck { get; init; }
}

/// <summary>
/// FR : une étape de la rafale de bienvenue : un nom sémantique + la forme de sa charge. La
///      rafale est une LISTE, pas un ensemble : le même opcode y paraît trois fois avec trois
///      charges différentes, et l'ordre est le fait mesuré.
/// EN : one welcome-burst step. The burst is a LIST, not a set: one opcode appears three times
///      with three different payloads, and the ORDER is the measured fact.
/// </summary>
public sealed class BurstStep
{
    /// <summary>Nom sémantique de l'étape. / The step's semantic name.</summary>
    public required SemanticOp Op { get; init; }

    /// <summary>Forme de la charge utile. / The payload shape.</summary>
    public required IReadOnlyList<FieldSpec> Payload { get; init; }
}

/// <summary>
/// FR : levée quand la table est absente, illisible ou incohérente. Le serveur ne démarre pas
///      sur une table douteuse : mieux vaut un refus au démarrage qu'un écran vide sans motif.
/// EN : thrown when the table is missing, unreadable or inconsistent. The server refuses to
///      start on a doubtful table.
/// </summary>
public sealed class BindingException : Exception
{
    /// <summary>FR : construit le refus. / EN : builds the refusal.</summary>
    public BindingException(string message) : base(message) { }
}

/// <summary>
/// FR : la table chargée. Immuable après construction (DECISIONS.md, immutabilité).
/// EN : the loaded table. Immutable once built.
/// </summary>
public sealed class OpcodeTable
{
    private readonly Dictionary<string, SemanticOp> _byOpcode;
    private readonly Dictionary<SemanticOp, OpcodeBinding> _bySemantic;
    private readonly Dictionary<string, IReadOnlyList<FieldSpec>> _payloads;

    private OpcodeTable(
        string build,
        IReadOnlyList<OpcodeBinding> bindings,
        IReadOnlyList<BurstStep> burst,
        Dictionary<string, IReadOnlyList<FieldSpec>> payloads)
    {
        Build = build;
        Bindings = bindings;
        WelcomeBurst = burst;
        _payloads = payloads;
        _byOpcode = bindings.ToDictionary(b => b.Opcode, b => b.Op, StringComparer.Ordinal);
        _bySemantic = bindings.ToDictionary(b => b.Op, b => b);
    }

    /// <summary>FR : la build que CETTE table décrit. / EN : the build THIS table describes.</summary>
    public string Build { get; }

    /// <summary>FR : toutes les liaisons. / EN : every binding.</summary>
    public IReadOnlyList<OpcodeBinding> Bindings { get; }

    /// <summary>FR : la rafale, dans l'ordre. / EN : the burst, in order.</summary>
    public IReadOnlyList<BurstStep> WelcomeBurst { get; }

    /// <summary>
    /// FR : fil → sémantique. Rend `false` pour un opcode que cette build ne lie pas ; l'appelant
    ///      le journalise et l'IGNORE, il ne devine jamais et ne plante jamais.
    /// EN : wire → semantic. Returns false for an opcode this build does not bind; the caller
    ///      logs and IGNORES it, never guesses and never crashes.
    /// </summary>
    public bool TryResolve(string wireOpcode, out SemanticOp op)
        => _byOpcode.TryGetValue(wireOpcode, out op);

    /// <summary>
    /// FR : sémantique → fil. Refuse NOMMÉMENT si cette build ne porte pas ce sémantique — un
    ///      sémantique non lié est un état normal, pas une erreur muette.
    /// EN : semantic → wire. Refuses BY NAME if this build does not carry that semantic.
    /// </summary>
    public string OpcodeOf(SemanticOp op)
    {
        if (!_bySemantic.TryGetValue(op, out OpcodeBinding? binding))
        {
            throw new BindingException(
                $"sémantique non liée dans la build {Build} / unbound semantic in build {Build}: {op}");
        }

        return binding.Opcode;
    }

    /// <summary>FR : la liaison complète d'un sémantique. / EN : a semantic's full binding.</summary>
    public bool TryBinding(SemanticOp op, out OpcodeBinding? binding)
        => _bySemantic.TryGetValue(op, out binding);

    /// <summary>
    /// FR : une charge utile nommée de la table (carte courante, pong, accès accepté…).
    /// EN : a named payload from the table (current map, pong, access accepted…).
    /// </summary>
    public IReadOnlyList<FieldSpec> Payload(string name)
    {
        if (!_payloads.TryGetValue(name, out IReadOnlyList<FieldSpec>? spec))
        {
            throw new BindingException($"charge inconnue / unknown payload: {name}");
        }

        return spec;
    }

    /// <summary>
    /// FR : charge la table depuis un fichier JSON généré. Toute incohérence est un refus NOMMÉ
    ///      au démarrage — jamais une valeur par défaut silencieuse.
    /// EN : loads the table from a generated JSON file. Any inconsistency is a NAMED refusal at
    ///      start-up — never a silent default.
    /// </summary>
    public static OpcodeTable Load(string path)
    {
        ArgumentException.ThrowIfNullOrEmpty(path);
        if (!File.Exists(path))
        {
            throw new BindingException($"table de liaison absente / missing binding table: {path}");
        }

        using JsonDocument doc = JsonDocument.Parse(File.ReadAllText(path));
        JsonElement root = doc.RootElement;
        string build = Str(root, "build");

        var bindings = new List<OpcodeBinding>();
        foreach (JsonElement row in Array(root, "messages"))
        {
            string semantic = Str(row, "semantique");
            if (!Enum.TryParse(semantic, ignoreCase: false, out SemanticOp op) || op == SemanticOp.None)
            {
                throw new BindingException(
                    $"nom sémantique inconnu du code / semantic unknown to the code: {semantic}");
            }

            bindings.Add(new OpcodeBinding
            {
                Op = op,
                Opcode = Str(row, "opcode"),
                Direction = Str(row, "sens"),
                ClearName = Str(row, "nom_clair"),
                Source = Str(row, "source"),
                CrossCheck = Str(row, "recroisement"),
            });
        }

        var burst = new List<BurstStep>();
        foreach (JsonElement step in Array(root, "rafale_bienvenue"))
        {
            string semantic = Str(step, "semantique");
            if (!Enum.TryParse(semantic, ignoreCase: false, out SemanticOp op) || op == SemanticOp.None)
            {
                throw new BindingException(
                    $"étape de rafale inconnue / unknown burst step: {semantic}");
            }

            burst.Add(new BurstStep { Op = op, Payload = FieldSpecReader.ReadList(step.GetProperty("charge")) });
        }

        var payloads = new Dictionary<string, IReadOnlyList<FieldSpec>>(StringComparer.Ordinal);
        foreach (JsonProperty prop in root.GetProperty("charges").EnumerateObject())
        {
            payloads[prop.Name] = FieldSpecReader.ReadList(prop.Value);
        }

        return new OpcodeTable(build, bindings, burst, payloads);
    }

    /// <summary>FR : lit une propriété texte obligatoire. / EN : reads a required text property.</summary>
    private static string Str(JsonElement element, string name)
        => element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : throw new BindingException($"propriété texte absente / missing text property: {name}");

    /// <summary>FR : lit une propriété tableau obligatoire. / EN : reads a required array.</summary>
    private static JsonElement.ArrayEnumerator Array(JsonElement element, string name)
        => element.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Array
            ? value.EnumerateArray()
            : throw new BindingException($"tableau absent / missing array: {name}");
}
