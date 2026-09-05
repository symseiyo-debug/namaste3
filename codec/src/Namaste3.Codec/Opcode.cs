// QUOI : Opcode.cs -- l'opcode 3 lettres et son `typeUrl` (`type.ankama.com/<opcode>`).
// POURQUOI : c'est l'identifiant de message qui REMPLACE le protocolId numérique de Dofus 2 --
//   voir L6 du cahier des charges (re-brassé à chaque build, jamais écrit en dur dans un handler).
// COMMENT LANCER : jamais seul -- consommé par ProtoReader/RawMessage.
// GATE : couvert par tests/Namaste3.Codec.Tests (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : l'opcode 3 lettres et son `typeUrl`. Le préfixe est VÉRIFIÉ : littéral
///      `"type.ankama.com"` dans le client (`il2cpp.cs:825181`, champ `dxji` de la classe
///      `gjv : MessageToMessageCodec<hea, object>` qui fabrique les `Any` — `il2cpp.cs:825175-825205`).
///      La longueur de 3 est une RÈGLE OBSERVÉE (Jondo la contrôle explicitement), pas une
///      contrainte trouvée dans le client : on la MESURE, on ne la fait pas respecter de force.
/// EN : the 3-letter opcode and its `typeUrl`. The prefix is VERIFIED: literal
///      `"type.ankama.com"` in the client (`il2cpp.cs:825181`, field `dxji` of class
///      `gjv : MessageToMessageCodec<hea, object>` which builds the `Any` — `il2cpp.cs:825175-825205`).
///      The length of 3 is an OBSERVED RULE (Jondo checks it explicitly), not a constraint found in
///      the client: we MEASURE it, we do not enforce it.
/// </summary>
public readonly record struct Opcode
{
    /// <summary>FR : préfixe exact, slash compris. EN : exact prefix, slash included.</summary>
    public const string Prefix = "type.ankama.com/";

    /// <summary>FR : longueur observée d'un opcode de jeu. EN : observed game opcode length.</summary>
    public const int CanonicalLength = 3;

    /// <summary>FR : la partie après le slash, ex. `jru`. EN : the part after the slash, e.g. `jru`.</summary>
    public string Name { get; }

    private Opcode(string name) => Name = name;

    /// <summary>FR : `true` si l'opcode a la forme canonique 3 lettres. EN : `true` if canonical 3-letter form.</summary>
    public bool IsCanonical
    {
        get
        {
            if (Name.Length != CanonicalLength)
            {
                return false;
            }

            foreach (char c in Name)
            {
                if (c is < 'a' or > 'z')
                {
                    return false;
                }
            }

            return true;
        }
    }

    /// <summary>FR : reconstruit le typeUrl complet. EN : rebuilds the full typeUrl.</summary>
    public string ToTypeUrl() => Prefix + Name;

    public override string ToString() => Name;

    /// <summary>
    /// FR : parse un typeUrl ou REFUSE avec un code nommé. Jamais d'exception nue.
    /// EN : parses a typeUrl or REFUSES with a named code. Never a bare exception.
    /// </summary>
    public static Opcode Parse(string typeUrl, long offset = -1)
    {
        if (string.IsNullOrEmpty(typeUrl))
        {
            throw CodecException.At(
                CodecErrorCode.TypeUrlInvalid, offset, "typeUrl vide / empty typeUrl");
        }

        if (!typeUrl.StartsWith(Prefix, StringComparison.Ordinal))
        {
            throw CodecException.At(
                CodecErrorCode.TypeUrlPrefixMissing, offset,
                $"« {typeUrl} » ne commence pas par « {Prefix} » / does not start with « {Prefix} »");
        }

        string name = typeUrl[Prefix.Length..];
        if (name.Length == 0)
        {
            throw CodecException.At(
                CodecErrorCode.TypeUrlInvalid, offset, "typeUrl sans nom après le préfixe / no name after the prefix");
        }

        return new Opcode(name);
    }

    /// <summary>FR : variante non levante. EN : non-throwing variant.</summary>
    public static bool TryParse(string typeUrl, out Opcode opcode)
    {
        try
        {
            opcode = Parse(typeUrl);
            return true;
        }
        catch (CodecException)
        {
            opcode = default;
            return false;
        }
    }
}
