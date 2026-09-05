// ============================================================================================
// QUOI : la FORME d'une charge utile, décrite en donnée et non en code — un arbre de champs
//     {numéro, type, valeur} chargé depuis `protocol/binding-<build>.json`, plus l'encodeur qui
//     le transforme en octets protobuf.
// POURQUOI (05/09/2026) : le brief exige que chaque message émis soit construit depuis les
//     champs VÉRIFIÉS (numéro + type) du dump du client. Mettre ces numéros dans du C# les
//     rendrait invisibles à la relecture et périmés au prochain patch ; les mettre en donnée les
//     rend diffables, régénérables et vérifiables sans compiler. Les nombres magiques quittent
//     aussi le code, ce que la gate de commentaires compte.
// EN : the SHAPE of a payload, expressed as data rather than code — a tree of {number, type,
//     value} fields loaded from the binding table, plus the encoder that turns it into protobuf.
// COMMENT LANCER / USAGE : `PayloadBuilder.Build(specs, injections)` rend les octets.
// GATE : `RoundTripEmissionTests` re-décode chaque charge émise et exige l'égalité byte-exacte.
// ============================================================================================

using Namaste3.Codec;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : les natures de champ que la table de liaison sait décrire. Toute autre valeur du JSON
///      est un REFUS NOMMÉ au chargement, jamais un champ silencieusement ignoré.
/// EN : the field kinds the binding table can describe. Anything else is a NAMED refusal at
///      load time, never a silently dropped field.
/// </summary>
public enum FieldKind
{
    /// <summary>Entier base-128, wire type 0. / Base-128 integer, wire type 0.</summary>
    Varint,
    /// <summary>Chaîne UTF-8, wire type 2. / UTF-8 string, wire type 2.</summary>
    Text,
    /// <summary>Suite de varints EMPAQUETÉS dans un champ length-delimited. / Packed varints.</summary>
    PackedVarint,
    /// <summary>Sous-message. Une liste vide = sous-message VIDE. / Sub-message; empty list = empty.</summary>
    Message,
    /// <summary>Varint dont la valeur est injectée à l'exécution. / Run-time injected varint.</summary>
    InjectedVarint,
    /// <summary>Chaîne dont la valeur est injectée à l'exécution. / Run-time injected string.</summary>
    InjectedText,
    /// <summary>Liste empaquetée injectée à l'exécution. / Run-time injected packed list.</summary>
    InjectedPackedVarint,
}

/// <summary>
/// FR : un champ. `Number` est le numéro protobuf VÉRIFIÉ dans le dump du client ; `Kind` est le
///      type VÉRIFIÉ ; la valeur, elle, peut être inventée — la table le dit dans sa source.
/// EN : one field. `Number` and `Kind` come VERIFIED from the client dump; the value may be
///      invented, and the table says so in its source column.
/// </summary>
public sealed class FieldSpec
{
    /// <summary>Numéro de champ protobuf. / Protobuf field number.</summary>
    public required int Number { get; init; }

    /// <summary>Nature du champ. / Field kind.</summary>
    public required FieldKind Kind { get; init; }

    /// <summary>Valeur entière, pour <see cref="FieldKind.Varint"/>. / Integer value.</summary>
    public ulong Varint { get; init; }

    /// <summary>Valeur texte, pour <see cref="FieldKind.Text"/>. / Text value.</summary>
    public string Text { get; init; } = string.Empty;

    /// <summary>Valeurs empaquetées. / Packed values.</summary>
    public IReadOnlyList<ulong> Packed { get; init; } = Array.Empty<ulong>();

    /// <summary>Champs du sous-message. / Sub-message fields.</summary>
    public IReadOnlyList<FieldSpec> Message { get; init; } = Array.Empty<FieldSpec>();

    /// <summary>Clé d'injection, pour les natures `Injected*`. / Injection key.</summary>
    public string InjectionKey { get; init; } = string.Empty;
}

/// <summary>
/// FR : ce que le serveur injecte à l'exécution dans une forme figée — l'horloge, le ticket,
///      l'hôte annoncé, les ports annoncés. Une INTERFACE, pas un accès direct à `DateTime.Now` :
///      le cœur reste déterministe et les tests rejouent la même seconde (DECISIONS.md, D-12).
/// EN : what the server injects at run time into a frozen shape — clock, ticket, announced host
///      and ports. An INTERFACE, not a direct `DateTime.Now`: the core stays deterministic.
/// </summary>
public interface IInjectionSource
{
    /// <summary>
    /// FR : rend la valeur entière d'une clé, ou refuse nommément si la clé est inconnue.
    /// EN : returns a key's integer value, or refuses by name if the key is unknown.
    /// </summary>
    bool TryVarint(string key, out ulong value);

    /// <summary>FR : idem pour une chaîne. / EN : same, for a string.</summary>
    bool TryText(string key, out string value);

    /// <summary>FR : idem pour une liste empaquetée. / EN : same, for a packed list.</summary>
    bool TryPacked(string key, out IReadOnlyList<ulong> values);
}

/// <summary>
/// FR : levée quand une forme ne peut pas être encodée — clé d'injection inconnue, nature de
///      champ non gérée. Un refus NOMMÉ vaut mieux qu'un champ manquant à l'écran.
/// EN : thrown when a shape cannot be encoded. A NAMED refusal beats a field missing on screen.
/// </summary>
public sealed class PayloadException : Exception
{
    /// <summary>FR : construit le refus. / EN : builds the refusal.</summary>
    public PayloadException(string message) : base(message) { }
}

/// <summary>
/// FR : l'encodeur. Il ne connaît AUCUN opcode et AUCUN message : il applique une forme.
/// EN : the encoder. It knows NO opcode and NO message: it just applies a shape.
/// </summary>
public static class PayloadBuilder
{
    /// <summary>
    /// FR : encode un arbre de champs en octets protobuf, dans l'ORDRE de la table — l'ordre des
    ///      champs sur le fil est celui que la capture réelle montre, on ne le trie pas.
    /// EN : encodes a field tree into protobuf bytes, in the table's ORDER — the wire order is
    ///      the one the real capture shows; we never sort it.
    /// </summary>
    public static byte[] Build(IReadOnlyList<FieldSpec> specs, IInjectionSource injections)
    {
        ArgumentNullException.ThrowIfNull(specs);
        ArgumentNullException.ThrowIfNull(injections);

        var buffer = new List<byte>(64);
        foreach (FieldSpec spec in specs)
        {
            Write(buffer, spec, injections);
        }

        return buffer.ToArray();
    }

    /// <summary>
    /// FR : écrit UN champ. Chaque nature a sa branche ; il n'existe aucune branche par défaut
    ///      qui laisserait passer un champ non écrit (DECISIONS.md D-12, « aucun défaut qui tue »).
    /// EN : writes ONE field. Every kind has its branch; there is no default branch that would
    ///      let a field go unwritten.
    /// </summary>
    private static void Write(List<byte> buffer, FieldSpec spec, IInjectionSource injections)
    {
        switch (spec.Kind)
        {
            case FieldKind.Varint:
                ProtoWriter.WriteVarint(buffer, spec.Number, spec.Varint);
                break;

            case FieldKind.Text:
                ProtoWriter.WriteLengthDelimited(
                    buffer, spec.Number, System.Text.Encoding.UTF8.GetBytes(spec.Text));
                break;

            case FieldKind.PackedVarint:
                ProtoWriter.WriteLengthDelimited(buffer, spec.Number, PackBody(spec.Packed));
                break;

            case FieldKind.Message:
                ProtoWriter.WriteLengthDelimited(buffer, spec.Number, Build(spec.Message, injections));
                break;

            case FieldKind.InjectedVarint:
                if (!injections.TryVarint(spec.InjectionKey, out ulong number))
                {
                    throw new PayloadException(Missing(spec));
                }

                ProtoWriter.WriteVarint(buffer, spec.Number, number);
                break;

            case FieldKind.InjectedText:
                if (!injections.TryText(spec.InjectionKey, out string? text))
                {
                    throw new PayloadException(Missing(spec));
                }

                ProtoWriter.WriteLengthDelimited(
                    buffer, spec.Number, System.Text.Encoding.UTF8.GetBytes(text));
                break;

            case FieldKind.InjectedPackedVarint:
                if (!injections.TryPacked(spec.InjectionKey, out IReadOnlyList<ulong>? packed))
                {
                    throw new PayloadException(Missing(spec));
                }

                ProtoWriter.WriteLengthDelimited(buffer, spec.Number, PackBody(packed));
                break;

            default:
                throw new PayloadException(
                    $"nature de champ non gérée / unhandled field kind: {spec.Kind} (f{spec.Number})");
        }
    }

    /// <summary>
    /// FR : le corps d'un champ empaqueté — des varints à la suite, SANS étiquette chacun.
    /// EN : a packed field's body — consecutive varints, each WITHOUT its own tag.
    /// </summary>
    private static byte[] PackBody(IReadOnlyList<ulong> values)
    {
        var body = new List<byte>(values.Count * 2);
        foreach (ulong value in values)
        {
            Varint.Write(body, value);
        }

        return body.ToArray();
    }

    /// <summary>FR : le texte d'un refus d'injection. / EN : the injection refusal text.</summary>
    private static string Missing(FieldSpec spec)
        => $"clé d'injection inconnue / unknown injection key: '{spec.InjectionKey}' (f{spec.Number})";
}
