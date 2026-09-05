// ============================================================================================
// QUOI : le lecteur JSON → `FieldSpec`. Il traduit la petite langue déclarative de la table de
//     liaison ({"n":2,"t":"varint","v":120}) en arbre de champs typés.
// POURQUOI (05/09/2026) : séparer LIRE et ENCODER. Le lecteur refuse NOMMÉMENT tout type de
//     champ qu'il ne connaît pas : une faute de frappe dans la table doit arrêter le démarrage,
//     pas produire un message auquel il manque un champ que personne ne remarquera à l'écran
//     (leçon retenue : « un état vide ment quand l'absence n'est pas une réponse »).
// EN : the JSON → `FieldSpec` reader. Reading and encoding are separate; an unknown field type
//     stops start-up by name rather than silently dropping a field.
// COMMENT LANCER / USAGE : appelé par `OpcodeTable.Load`, jamais directement.
// GATE : `NegativeTests` — une table qui porte un type inconnu doit REFUSER, pas passer.
// ============================================================================================

using System.Text.Json;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : traduit la table en arbre de champs. Aucun état, aucune horloge, aucun aléa.
/// EN : translates the table into a field tree. No state, no clock, no randomness.
/// </summary>
public static class FieldSpecReader
{
    // Les étiquettes de la petite langue déclarative. Elles vivent ICI et nulle part ailleurs.
    // / The declarative mini-language's tags. They live HERE and nowhere else.
    private const string KindVarint = "varint";
    private const string KindText = "chaine";
    private const string KindPacked = "varint_packed";
    private const string KindMessage = "message";
    private const string KindInjectedVarint = "varint_injecte";
    private const string KindInjectedText = "chaine_injectee";
    private const string KindInjectedPacked = "varint_packed_injecte";

    /// <summary>
    /// FR : lit un TABLEAU de champs. Un tableau vide est une charge VIDE valide (plusieurs
    ///      messages de la rafale n'ont aucun champ — c'est mesuré, pas une omission).
    /// EN : reads an ARRAY of fields. An empty array is a valid EMPTY payload — several burst
    ///      messages have no field at all, which is measured, not an omission.
    /// </summary>
    public static IReadOnlyList<FieldSpec> ReadList(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.Array)
        {
            throw new BindingException(
                $"charge attendue en tableau / payload expected as array, got {element.ValueKind}");
        }

        var specs = new List<FieldSpec>();
        foreach (JsonElement item in element.EnumerateArray())
        {
            specs.Add(ReadOne(item));
        }

        return specs;
    }

    /// <summary>
    /// FR : lit UN champ. Le `switch` n'a pas de branche par défaut permissive : un type inconnu
    ///      est un refus nommé, pas un champ ignoré.
    /// EN : reads ONE field. No permissive default branch: an unknown type is a named refusal.
    /// </summary>
    private static FieldSpec ReadOne(JsonElement item)
    {
        if (item.ValueKind != JsonValueKind.Object)
        {
            throw new BindingException($"champ attendu en objet / field expected as object, got {item.ValueKind}");
        }

        int number = item.GetProperty("n").GetInt32();
        string kind = item.GetProperty("t").GetString() ?? string.Empty;

        return kind switch
        {
            KindVarint => new FieldSpec
            {
                Number = number,
                Kind = FieldKind.Varint,
                Varint = item.GetProperty("v").GetUInt64(),
            },
            KindText => new FieldSpec
            {
                Number = number,
                Kind = FieldKind.Text,
                Text = item.GetProperty("v").GetString() ?? string.Empty,
            },
            KindPacked => new FieldSpec
            {
                Number = number,
                Kind = FieldKind.PackedVarint,
                Packed = ReadPacked(item.GetProperty("v")),
            },
            KindMessage => new FieldSpec
            {
                Number = number,
                Kind = FieldKind.Message,
                Message = ReadList(item.GetProperty("v")),
            },
            KindInjectedVarint => Injected(number, FieldKind.InjectedVarint, item),
            KindInjectedText => Injected(number, FieldKind.InjectedText, item),
            KindInjectedPacked => Injected(number, FieldKind.InjectedPackedVarint, item),
            _ => throw new BindingException(
                $"type de champ inconnu / unknown field type: '{kind}' (f{number})"),
        };
    }

    /// <summary>FR : un champ à valeur injectée. / EN : a field whose value is injected.</summary>
    private static FieldSpec Injected(int number, FieldKind kind, JsonElement item) => new()
    {
        Number = number,
        Kind = kind,
        InjectionKey = item.GetProperty("v").GetString() ?? string.Empty,
    };

    /// <summary>FR : la liste d'une valeur empaquetée. / EN : a packed value's list.</summary>
    private static IReadOnlyList<ulong> ReadPacked(JsonElement element)
    {
        var values = new List<ulong>();
        foreach (JsonElement value in element.EnumerateArray())
        {
            values.Add(value.GetUInt64());
        }

        return values;
    }
}
