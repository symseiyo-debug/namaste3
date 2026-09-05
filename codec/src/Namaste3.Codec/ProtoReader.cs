// QUOI : ProtoReader.cs -- lecture protobuf minimale sans schéma (ReadMessage/ReadValue), avec
//   ProtoStats pour mesurer ce qui a été RÉELLEMENT reconstruit vs laissé opaque.
// POURQUOI : un sous-message n'est gardé QUE s'il se ré-encode octet pour octet (règle dure de
//   TryParseSubtree ci-dessous) -- sinon un texte qui "parse par accident" ferait perdre des octets.
// COMMENT LANCER : jamais seul -- consommé par Envelope/Codec3 et les tests.
// GATE : tests/Namaste3.Codec.Tests/RoundTripTests.cs + NegativeTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : compteurs de lecture — ce qu'on a VRAIMENT su reconstruire, par opposition à ce qu'on a
///      laissé passer en opaque. Un round-trip vert avec 0 sous-arbre exact serait un vert vide :
///      c'est ce couple de nombres qui empêche la gate de se mentir.
/// EN : reading counters — what we ACTUALLY managed to rebuild, as opposed to what we let through
///      opaque. A green round-trip with 0 exact subtrees would be an empty green: this pair of
///      numbers is what stops the gate from lying to itself.
/// </summary>
public sealed class ProtoStats
{
    /// <summary>FR : champs décodés, tous niveaux. EN : decoded fields, all levels.</summary>
    public int Fields;

    /// <summary>FR : champs len-préfixés rendus en sous-arbre ré-encodé exact. EN : len fields rebuilt as an exact subtree.</summary>
    public int ExactSubtrees;

    /// <summary>FR : champs len-préfixés laissés opaques. EN : len fields left opaque.</summary>
    public int OpaqueLeaves;

    // Cumule les compteurs d'un sous-appel (récursion sur un sous-message) dans ce total.
    // / Adds a sub-call's counters (recursion into a submessage) into this total.
    public void Add(ProtoStats other)
    {
        Fields += other.Fields;
        ExactSubtrees += other.ExactSubtrees;
        OpaqueLeaves += other.OpaqueLeaves;
    }

    // Rend les 3 compteurs sur une ligne, pour les logs/rapports du sniffer.
    // / Renders the 3 counters on one line, for the sniffer's logs/reports.
    public override string ToString()
        => $"champs/fields={Fields} sous-arbres-exacts/exact-subtrees={ExactSubtrees} opaques/opaque={OpaqueLeaves}";
}

/// <summary>
/// FR : lecture protobuf minimale, écrite à la main, SANS schéma et sans Google.Protobuf.
/// EN : minimal hand-written protobuf reading, WITHOUT a schema and without Google.Protobuf.
/// </summary>
public static class ProtoReader
{
    /// <summary>
    /// FR : profondeur maximale d'exploration. Borne dure : une charge utile hostile ne doit pas
    ///      pouvoir faire récurser le sniffer jusqu'au débordement de pile.
    /// EN : maximum exploration depth. Hard bound: a hostile payload must not be able to recurse
    ///      the sniffer into a stack overflow.
    /// </summary>
    public const int MaxDepth = 24;

    /// <summary>
    /// FR : décode une suite de champs, STRICTEMENT (tout le tampon doit être consommé).
    /// EN : decodes a field list, STRICTLY (the whole buffer must be consumed).
    /// </summary>
    public static List<ProtoField> ReadMessage(
        ReadOnlySpan<byte> data, long baseOffset, ProtoStats stats, int depth = 0)
    {
        var fields = new List<ProtoField>();
        int position = 0;

        while (position < data.Length)
        {
            long tagOffset = baseOffset + position;
            ulong tag = Varint.Read(data, ref position, tagOffset);

            int number = (int)(tag >> 3);
            var wireType = (ProtoWireType)(byte)(tag & 0x07);

            if (number == 0)
            {
                throw CodecException.At(
                    CodecErrorCode.InvalidFieldNumber, tagOffset,
                    "numéro de champ 0 interdit / field number 0 is forbidden");
            }

            fields.Add(ReadValue(data, ref position, baseOffset, tagOffset, number, wireType, stats, depth));
            stats.Fields++;
        }

        return fields;
    }

    // Lit UNE valeur de champ selon son wire type (varint/fixed64/fixed32/length-delimited) ;
    // tente de voir un length-delimited comme sous-message via TryParseSubtree.
    // / Reads ONE field value per its wire type (varint/fixed64/fixed32/length-delimited); tries
    // to see a length-delimited value as a submessage via TryParseSubtree.
    private static ProtoField ReadValue(
        ReadOnlySpan<byte> data, ref int position, long baseOffset, long tagOffset,
        int number, ProtoWireType wireType, ProtoStats stats, int depth)
    {
        switch (wireType)
        {
            case ProtoWireType.Varint:
            {
                ulong value = Varint.Read(data, ref position, baseOffset + position);
                return new ProtoField
                {
                    Number = number, WireType = wireType, VarintValue = value, Offset = tagOffset,
                };
            }

            case ProtoWireType.Fixed64:
            {
                Require(data, position, 8, baseOffset + position, "fixed64");
                ulong value = 0;
                for (int i = 0; i < 8; i++)
                {
                    value |= (ulong)data[position + i] << (8 * i);
                }

                position += 8;
                return new ProtoField
                {
                    Number = number, WireType = wireType, Fixed64Value = value, Offset = tagOffset,
                };
            }

            case ProtoWireType.Fixed32:
            {
                Require(data, position, 4, baseOffset + position, "fixed32");
                uint value = 0;
                for (int i = 0; i < 4; i++)
                {
                    value |= (uint)data[position + i] << (8 * i);
                }

                position += 4;
                return new ProtoField
                {
                    Number = number, WireType = wireType, Fixed32Value = value, Offset = tagOffset,
                };
            }

            case ProtoWireType.LengthDelimited:
            {
                long lengthOffset = baseOffset + position;
                ulong length = Varint.Read(data, ref position, lengthOffset);
                if (length > int.MaxValue)
                {
                    throw CodecException.At(
                        CodecErrorCode.LengthExceedsBuffer, lengthOffset,
                        $"longueur {length} hors bornes / length {length} out of bounds");
                }

                Require(data, position, (int)length, lengthOffset, "len");
                byte[] payload = data.Slice(position, (int)length).ToArray();
                long payloadOffset = baseOffset + position;
                position += (int)length;

                IReadOnlyList<ProtoField>? subtree = TryParseSubtree(payload, payloadOffset, stats, depth);
                if (subtree is null)
                {
                    stats.OpaqueLeaves++;
                }
                else
                {
                    stats.ExactSubtrees++;
                }

                return new ProtoField
                {
                    Number = number, WireType = wireType, Bytes = payload,
                    Message = subtree, Offset = tagOffset,
                };
            }

            default:
                throw CodecException.At(
                    CodecErrorCode.InvalidWireType, tagOffset,
                    $"wire type {(int)wireType} non supporté (groupes 3/4 absents du protocole 3.0 mesuré) / "
                    + $"wire type {(int)wireType} unsupported (groups 3/4 absent from the measured 3.0 protocol)");
        }
    }

    /// <summary>
    /// FR : tente de voir une charge utile comme un sous-message. RÈGLE DURE : on ne garde le
    ///      sous-arbre que s'il se RÉ-ENCODE octet pour octet en la charge d'origine. Sans cette
    ///      règle, une chaîne UTF-8 qui « parse par accident » ferait perdre des octets au
    ///      round-trip — un faux vert structurel.
    /// EN : tries to see a payload as a submessage. HARD RULE: we keep the subtree only if it
    ///      RE-ENCODES byte for byte into the original payload. Without this rule, a UTF-8 string
    ///      that "parses by accident" would lose bytes on round-trip — a structural false green.
    /// </summary>
    private static IReadOnlyList<ProtoField>? TryParseSubtree(
        byte[] payload, long payloadOffset, ProtoStats stats, int depth)
    {
        if (payload.Length == 0 || depth >= MaxDepth)
        {
            return null;
        }

        var childStats = new ProtoStats();
        List<ProtoField> children;
        try
        {
            children = ReadMessage(payload, payloadOffset, childStats, depth + 1);
        }
        catch (CodecException)
        {
            // FR : charge utile non structurée (chaîne, blob) — c'est le cas normal, pas une panne.
            // EN : unstructured payload (string, blob) — this is the normal case, not a failure.
            return null;
        }

        byte[] rebuilt = ProtoWriter.WriteMessage(children);
        if (!rebuilt.AsSpan().SequenceEqual(payload))
        {
            return null;
        }

        stats.Add(childStats);
        return children;
    }

    // Refuse (nommé, avec offset) si moins de `need` octets restent dans `data` à `position`.
    // / Refuses (named, with offset) if fewer than `need` bytes remain in `data` at `position`.
    private static void Require(ReadOnlySpan<byte> data, int position, int need, long offset, string what)
    {
        if (position + need > data.Length)
        {
            throw CodecException.At(
                CodecErrorCode.LengthExceedsBuffer, offset,
                $"{what} demande {need} octets, il en reste {data.Length - position} / "
                + $"{what} needs {need} bytes, {data.Length - position} left");
        }
    }
}
