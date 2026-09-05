// QUOI : FrameWriter.cs -- écrit le préfixe de longueur varint devant une charge utile, symétrique
//   exact de FrameReader.
// POURQUOI : le round-trip byte-exact (RoundTripTests) exige un encodeur qui reconstruit
//   canoniquement, jamais qui recopie les octets d'entrée.
// COMMENT LANCER : jamais seul -- consommé par les tests et Namaste3.Codec.Sniff.
// GATE : tests/Namaste3.Codec.Tests/RoundTripTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : préfixe de longueur en varint devant une charge utile. Symétrique exact de
///      <see cref="FrameReader"/> ; côté client c'est `ProtobufVarint32LengthFieldPrepender`
///      (`il2cpp.cs:487229`).
/// EN : varint length prefix in front of a payload. Exact mirror of <see cref="FrameReader"/>;
///      on the client side this is `ProtobufVarint32LengthFieldPrepender` (`il2cpp.cs:487229`).
/// </summary>
public sealed class FrameWriter
{
    private readonly int _maxFrameLength;
    private readonly bool _headerSizeIncludesItself;

    public FrameWriter(
        int maxFrameLength = FrameReader.DefaultMaxFrameLength,
        bool headerSizeIncludesItself = false)
    {
        _maxFrameLength = maxFrameLength;
        _headerSizeIncludesItself = headerSizeIncludesItself;
    }

    /// <summary>FR : encadre une charge utile. EN : frames a payload.</summary>
    public byte[] Frame(ReadOnlySpan<byte> payload)
    {
        var buffer = new List<byte>(payload.Length + Varint.MaxBytes);
        WriteTo(buffer, payload);
        return buffer.ToArray();
    }

    /// <summary>FR : encadre en écrivant dans un tampon existant. EN : frames into an existing buffer.</summary>
    public void WriteTo(List<byte> destination, ReadOnlySpan<byte> payload)
    {
        if (payload.Length > _maxFrameLength)
        {
            throw CodecException.At(
                CodecErrorCode.FrameTooLarge, -1,
                $"charge de {payload.Length} octets > plafond {_maxFrameLength} / payload above the cap");
        }

        ulong declared = (ulong)payload.Length;

        if (_headerSizeIncludesItself)
        {
            // FR : la longueur se compte elle-même — point fixe, le passage de 127 à 128 ajoute un octet.
            // EN : the length counts itself — fixed point, crossing 127→128 adds one byte.
            int headerBytes = Varint.Size(declared);
            while (Varint.Size(declared + (ulong)headerBytes) != headerBytes)
            {
                headerBytes = Varint.Size(declared + (ulong)headerBytes);
            }

            declared += (ulong)headerBytes;
        }

        Varint.Write(destination, declared);
        foreach (byte b in payload)
        {
            destination.Add(b);
        }
    }
}
