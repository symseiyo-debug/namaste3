// QUOI : FrameReader.cs -- délimite les trames (varint32 longueur + payload) sur un flux TCP,
//   gère le recollage d'une trame coupée entre deux lectures.
// POURQUOI : un segment TCP ne respecte jamais les frontières applicatives -- sans ce
//   composant, un handler recevrait des trames tronquées ou fusionnées.
// COMMENT LANCER : jamais seul -- consommé par Codec3 et Namaste3.Codec.Sniff.
// GATE : tests/Namaste3.Codec.Tests/SegmentationTests.cs (coupures de trame) + RoundTripTests.cs.
namespace Namaste3.Codec;

/// <summary>
/// FR : délimitation des trames sur un flux TCP. Un segment TCP peut porter zéro, une ou plusieurs
///      trames, et une trame peut être coupée en deux — c'est la seule raison d'être de cette classe.
///
///      DOCTRINE, source client (le dump fait foi) : le pipeline de jeu est DotNetty, pas Spin.
///      · `ProtobufVarint32FrameDecoder` / `ProtobufVarint32LengthFieldPrepender`
///        (`il2cpp.cs:487219`, `il2cpp.cs:487229`) → longueur = varint32, EXCLUANT ses propres octets.
///      · Le plafond 131 072 est une constante du client : `SpinConnection.DefaultMaximumMessageSize`
///        (`il2cpp.cs:579468`) ; Jondo mesure la MÊME valeur dans le message d'erreur du client.
///      · La couche `Ankama.SpinConnection.Network.Layers.FrameDelimiter` (`il2cpp.cs:261570-261600`)
///        et son tampon interne `FrameDataBuffer` (`il2cpp.cs:261577-261591`, `TryGetPayload`,
///        `CompactIfNeeded`) décrivent la MÊME mécanique de recollage, avec un drapeau
///        `headerSizeIncludesItself` que `SpinConnection` fixe à `true` (`il2cpp.cs:579474`).
///        Sur nos 3 fixtures la longueur EXCLUT l'en-tête : les deux modes existent donc dans le
///        client, sur deux piles différentes. Le drapeau est exposé ici, par défaut « exclut ».
///
/// EN : frame delimitation over a TCP stream. A TCP segment may carry zero, one or several frames,
///      and a frame may be cut in two — that is the only reason this class exists. See the French
///      block above for the dump citations; the game pipeline is DotNetty (length excludes the
///      header), the Spin pipeline sets `headerSizeIncludesItself = true`. Both modes are exposed.
/// </summary>
public sealed class FrameReader
{
    /// <summary>FR : plafond client mesuré. EN : measured client cap.</summary>
    public const int DefaultMaxFrameLength = 131072;

    /// <summary>FR : capacité initiale du client (`FrameDataBuffer`, capacity=8092). EN : client initial capacity.</summary>
    public const int DefaultInitialCapacity = 8092;

    private readonly int _maxFrameLength;
    private readonly bool _headerSizeIncludesItself;
    private byte[] _buffer;
    private int _start;
    private int _end;

    /// <summary>FR : offset absolu, depuis le début du flux, du premier octet non consommé. EN : absolute stream offset of the first unconsumed byte.</summary>
    public long ConsumedOffset { get; private set; }

    public FrameReader(
        int maxFrameLength = DefaultMaxFrameLength,
        bool headerSizeIncludesItself = false,
        int initialCapacity = DefaultInitialCapacity)
    {
        if (maxFrameLength <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxFrameLength));
        }

        _maxFrameLength = maxFrameLength;
        _headerSizeIncludesItself = headerSizeIncludesItself;
        _buffer = new byte[Math.Max(16, initialCapacity)];
    }

    /// <summary>FR : octets reçus mais pas encore rendus en trame. EN : bytes received but not yet yielded as a frame.</summary>
    public int PendingBytes => _end - _start;

    /// <summary>FR : ajoute un segment TCP. EN : appends a TCP segment.</summary>
    public void Append(ReadOnlySpan<byte> segment)
    {
        if (segment.Length == 0)
        {
            return;
        }

        EnsureRoom(segment.Length);
        segment.CopyTo(_buffer.AsSpan(_end));
        _end += segment.Length;
    }

    /// <summary>
    /// FR : rend la prochaine trame COMPLÈTE (charge utile sans le préfixe de longueur), ou false
    ///      s'il faut plus d'octets. Un refus NOMMÉ n'arrive que si les octets sont invalides —
    ///      « incomplet » et « invalide » ne se confondent jamais.
    /// EN : yields the next COMPLETE frame (payload without the length prefix), or false when more
    ///      bytes are needed. A NAMED refusal only happens on invalid bytes — "incomplete" and
    ///      "invalid" are never conflated.
    /// </summary>
    public bool TryReadFrame(out byte[] frame, out long frameOffset)
    {
        frame = Array.Empty<byte>();
        frameOffset = ConsumedOffset;

        var window = _buffer.AsSpan(_start, _end - _start);
        if (window.Length == 0)
        {
            return false;
        }

        if (!Varint.TryRead(window, 0, out ulong declared, out int headerBytes, ConsumedOffset))
        {
            return false;
        }

        long payloadLength = _headerSizeIncludesItself ? (long)declared - headerBytes : (long)declared;

        if (payloadLength < 0)
        {
            throw CodecException.At(
                CodecErrorCode.LengthExceedsBuffer, ConsumedOffset,
                $"longueur annoncée {declared} < taille de l'en-tête {headerBytes} / declared length below header size");
        }

        if (payloadLength > _maxFrameLength)
        {
            throw CodecException.At(
                CodecErrorCode.FrameTooLarge, ConsumedOffset,
                $"trame de {payloadLength} octets > plafond {_maxFrameLength} / frame above the cap");
        }

        if (window.Length < headerBytes + payloadLength)
        {
            // FR : trame à cheval sur deux segments — on attend la suite, sans rien consommer.
            // EN : frame split across two segments — we wait for more, consuming nothing.
            return false;
        }

        frame = window.Slice(headerBytes, (int)payloadLength).ToArray();
        frameOffset = ConsumedOffset;
        _start += headerBytes + (int)payloadLength;
        ConsumedOffset += headerBytes + (int)payloadLength;
        return true;
    }

    /// <summary>
    /// FR : à la fermeture du flux, refuse s'il reste des octets pendants — un reliquat silencieux
    ///      est exactement la panne qu'un round-trip byte-exact doit attraper.
    /// EN : at stream close, refuses if bytes are still pending — a silent leftover is exactly the
    ///      failure a byte-exact round-trip must catch.
    /// </summary>
    public void AssertDrained()
    {
        if (PendingBytes > 0)
        {
            throw CodecException.At(
                CodecErrorCode.TrailingBytes, ConsumedOffset,
                $"{PendingBytes} octets pendants en fin de flux / {PendingBytes} bytes pending at stream end");
        }
    }

    /// <summary>FR : compacte puis agrandit si besoin (cf. `CompactIfNeeded`). EN : compacts then grows if needed.</summary>
    private void EnsureRoom(int extra)
    {
        if (_end + extra <= _buffer.Length)
        {
            return;
        }

        int pending = _end - _start;
        if (_start > 0)
        {
            Array.Copy(_buffer, _start, _buffer, 0, pending);
            _start = 0;
            _end = pending;
        }

        if (_end + extra <= _buffer.Length)
        {
            return;
        }

        int capacity = _buffer.Length;
        while (capacity < _end + extra)
        {
            capacity *= 2;
        }

        Array.Resize(ref _buffer, capacity);
    }
}
