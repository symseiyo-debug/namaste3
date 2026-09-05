// QUOI : ProtoWriter.cs -- écriture protobuf minimale sans schéma (tag, varint, length-delimited).
// POURQUOI : symétrique de ProtoReader -- sans schéma imposé, un message inconnu se ré-encode
//   quand même (survie aux patchs, étage 5).
// COMMENT LANCER : jamais seul -- consommé par FrameWriter/RawMessage et les tests.
// GATE : tests/Namaste3.Codec.Tests/RoundTripTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : écriture protobuf minimale, écrite à la main. AUCUNE dépendance Google.Protobuf : le cœur
///      doit savoir ré-encoder ce qu'il a lu SANS schéma, sinon il ne peut pas servir de sniffer
///      (étage 5) ni survivre à un message inconnu d'un futur patch.
/// EN : minimal hand-written protobuf writing. NO Google.Protobuf dependency: the core must be able
///      to re-encode what it read WITHOUT a schema, otherwise it cannot serve as a sniffer
///      (stage 5) nor survive an unknown message from a future patch.
/// </summary>
public static class ProtoWriter
{
    /// <summary>FR : tag = (numéro &lt;&lt; 3) | wire type. EN : tag = (number &lt;&lt; 3) | wire type.</summary>
    public static void WriteTag(List<byte> destination, int number, ProtoWireType wireType)
        => Varint.Write(destination, ((ulong)(uint)number << 3) | (byte)wireType);

    /// <summary>FR : champ longueur-préfixé brut. EN : raw length-delimited field.</summary>
    public static void WriteLengthDelimited(List<byte> destination, int number, ReadOnlySpan<byte> payload)
    {
        WriteTag(destination, number, ProtoWireType.LengthDelimited);
        Varint.Write(destination, (ulong)payload.Length);
        foreach (byte b in payload)
        {
            destination.Add(b);
        }
    }

    /// <summary>FR : champ varint. EN : varint field.</summary>
    public static void WriteVarint(List<byte> destination, int number, ulong value)
    {
        WriteTag(destination, number, ProtoWireType.Varint);
        Varint.Write(destination, value);
    }

    /// <summary>
    /// FR : ré-écrit UN champ décodé. Un sous-arbre présent est ré-encodé RÉCURSIVEMENT (jamais
    ///      recopié) ; un champ opaque ressort par ses octets, ce qui est assumé et déclaré.
    /// EN : rewrites ONE decoded field. A present subtree is re-encoded RECURSIVELY (never copied);
    ///      an opaque field goes back out through its bytes, which is assumed and declared.
    /// </summary>
    public static void WriteField(List<byte> destination, ProtoField field)
    {
        switch (field.WireType)
        {
            case ProtoWireType.Varint:
                WriteTag(destination, field.Number, ProtoWireType.Varint);
                Varint.Write(destination, field.VarintValue);
                break;

            case ProtoWireType.Fixed64:
                WriteTag(destination, field.Number, ProtoWireType.Fixed64);
                for (int i = 0; i < 8; i++)
                {
                    destination.Add((byte)(field.Fixed64Value >> (8 * i)));
                }

                break;

            case ProtoWireType.Fixed32:
                WriteTag(destination, field.Number, ProtoWireType.Fixed32);
                for (int i = 0; i < 4; i++)
                {
                    destination.Add((byte)(field.Fixed32Value >> (8 * i)));
                }

                break;

            case ProtoWireType.LengthDelimited:
                if (field.Message is not null)
                {
                    byte[] rebuilt = WriteMessage(field.Message);
                    WriteLengthDelimited(destination, field.Number, rebuilt);
                }
                else
                {
                    WriteLengthDelimited(destination, field.Number, field.Bytes);
                }

                break;

            default:
                throw CodecException.At(
                    CodecErrorCode.InvalidWireType, field.Offset,
                    $"wire type {(int)field.WireType} non écrivable / not writable");
        }
    }

    /// <summary>FR : ré-écrit une suite de champs, DANS L'ORDRE lu. EN : rewrites a field list, IN READ ORDER.</summary>
    public static byte[] WriteMessage(IReadOnlyList<ProtoField> fields)
    {
        var buffer = new List<byte>(64);
        foreach (ProtoField field in fields)
        {
            WriteField(buffer, field);
        }

        return buffer.ToArray();
    }
}
