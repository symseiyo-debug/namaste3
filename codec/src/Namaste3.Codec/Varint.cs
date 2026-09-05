// QUOI : Varint.cs -- lecture/écriture du varint base-128 protobuf, la brique de bas niveau du
//   codec 3.0 (framing + numéros de champ protobuf).
// POURQUOI : réutilisé par FrameReader/FrameWriter (longueur de trame) ET ProtoReader/ProtoWriter
//   (tags de champ) -- une seule implémentation prouvée, jamais deux qui pourraient diverger.
// COMMENT LANCER : jamais seul -- classe statique consommée par le reste de Namaste3.Codec.
// GATE : couvert par tests/Namaste3.Codec.Tests/VarintTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : varint base-128 protobuf (little-endian, bit 7 = continuation). C'est la brique du framing
///      du jeu 3.0 : le client empile DotNetty `ProtobufVarint32FrameDecoder` /
///      `ProtobufVarint32LengthFieldPrepender` (dump `il2cpp.cs:487219` et `il2cpp.cs:487229`),
///      dont la longueur EXCLUT ses propres octets — mesuré sur les 3 fixtures (cf. CODEC.md §2).
/// EN : protobuf base-128 varint (little-endian, bit 7 = continuation). It is the building block of
///      the 3.0 game framing: the client stacks DotNetty `ProtobufVarint32FrameDecoder` /
///      `ProtobufVarint32LengthFieldPrepender` (dump `il2cpp.cs:487219` and `il2cpp.cs:487229`),
///      whose length EXCLUDES its own bytes — measured on the 3 fixtures (see CODEC.md §2).
/// </summary>
public static class Varint
{
    /// <summary>FR : un varint 64 bits tient au plus sur 10 octets. EN : a 64-bit varint fits in 10 bytes at most.</summary>
    public const int MaxBytes = 10;

    /// <summary>
    /// FR : lit un varint. Rend false SANS lever si le tampon est trop court (cas « trame à cheval »).
    ///      Lève un refus NOMMÉ si le varint est mal formé (trop long / débordement).
    /// EN : reads a varint. Returns false WITHOUT throwing when the buffer is too short (split-frame
    ///      case). Throws a NAMED refusal when the varint is malformed (too long / overflow).
    /// </summary>
    /// <param name="source">FR : tampon source. EN : source buffer.</param>
    /// <param name="start">FR : index de départ dans le tampon. EN : start index in the buffer.</param>
    /// <param name="value">FR : valeur lue. EN : value read.</param>
    /// <param name="bytesRead">FR : octets consommés. EN : bytes consumed.</param>
    /// <param name="absoluteOffset">FR : offset absolu pour les messages d'erreur. EN : absolute offset for error messages.</param>
    public static bool TryRead(
        ReadOnlySpan<byte> source, int start, out ulong value, out int bytesRead, long absoluteOffset = -1)
    {
        value = 0;
        bytesRead = 0;

        for (int i = 0; i < MaxBytes; i++)
        {
            int index = start + i;
            if (index >= source.Length)
            {
                // FR : incomplet, pas invalide — l'appelant redemandera plus d'octets.
                // EN : incomplete, not invalid — the caller will ask for more bytes.
                return false;
            }

            byte b = source[index];

            // FR : le 10e octet ne peut porter que le bit de poids fort 64 (0x00 ou 0x01).
            // EN : the 10th byte may only carry the 64th bit (0x00 or 0x01).
            if (i == MaxBytes - 1 && (b & 0x7F) > 0x01)
            {
                throw CodecException.At(
                    CodecErrorCode.VarintOverflow, absoluteOffset < 0 ? start : absoluteOffset,
                    $"le 10e octet vaut 0x{b:x2}, il déborde 64 bits / 10th byte 0x{b:x2} overflows 64 bits");
            }

            value |= (ulong)(b & 0x7F) << (7 * i);
            bytesRead = i + 1;

            if ((b & 0x80) == 0)
            {
                return true;
            }
        }

        // FR : 10 octets tous marqués « continuation » = varint invalide, jamais « incomplet ».
        // EN : 10 bytes all flagged "continuation" = invalid varint, never "incomplete".
        throw CodecException.At(
            CodecErrorCode.VarintTooLong, absoluteOffset < 0 ? start : absoluteOffset,
            $"plus de {MaxBytes} octets sans octet terminal / more than {MaxBytes} bytes without a terminator");
    }

    /// <summary>
    /// FR : lit un varint ou refuse (nommé) — variante stricte pour les tampons complets.
    /// EN : reads a varint or refuses (named) — strict variant for complete buffers.
    /// </summary>
    public static ulong Read(ReadOnlySpan<byte> source, ref int position, long absoluteOffset = -1)
    {
        long where = absoluteOffset < 0 ? position : absoluteOffset;
        if (!TryRead(source, position, out ulong value, out int read, where))
        {
            throw CodecException.At(
                CodecErrorCode.VarintTruncated, where,
                "fin de tampon au milieu d'un varint / end of buffer inside a varint");
        }

        position += read;
        return value;
    }

    /// <summary>FR : taille encodée en octets. EN : encoded size in bytes.</summary>
    public static int Size(ulong value)
    {
        int size = 1;
        while (value >= 0x80)
        {
            value >>= 7;
            size++;
        }

        return size;
    }

    /// <summary>
    /// FR : écrit un varint CANONIQUE (le plus court possible). Le round-trip byte-exact des
    ///      fixtures prouve que le serveur d'origine encodait déjà canoniquement — on ne recopie
    ///      pas les octets d'entrée, on les RECONSTRUIT.
    /// EN : writes a CANONICAL varint (shortest form). The byte-exact round-trip of the fixtures
    ///      proves the original server already encoded canonically — we do not copy the input
    ///      bytes back, we REBUILD them.
    /// </summary>
    public static void Write(Stream destination, ulong value)
    {
        while (value >= 0x80)
        {
            destination.WriteByte((byte)(value | 0x80));
            value >>= 7;
        }

        destination.WriteByte((byte)value);
    }

    /// <summary>FR : idem, vers une liste d'octets. EN : same, into a byte list.</summary>
    public static void Write(List<byte> destination, ulong value)
    {
        while (value >= 0x80)
        {
            destination.Add((byte)(value | 0x80));
            value >>= 7;
        }

        destination.Add((byte)value);
    }

    /// <summary>FR : encode en tableau (confort de test). EN : encodes to an array (test comfort).</summary>
    public static byte[] Encode(ulong value)
    {
        var buffer = new List<byte>(MaxBytes);
        Write(buffer, value);
        return buffer.ToArray();
    }
}
