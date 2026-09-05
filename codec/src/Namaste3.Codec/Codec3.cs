// QUOI : Codec3.cs -- point d'entrée haut niveau du codec 3.0 : décode un flux d'octets en
//   RawMessage, agrège les statistiques (DecodeResult, ProtoStats).
// POURQUOI : les composants bas niveau (FrameReader/ProtoReader) parsent trame par trame ; ce
//   fichier assemble le résultat complet d'un flux/fichier de capture pour l'appelant (tests,
//   sniffer CLI).
// COMMENT LANCER : jamais seul -- consommé par Namaste3.Codec.Sniff/Program.cs et les tests.
// GATE : couvert par tests/Namaste3.Codec.Tests/RoundTripTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>FR : résultat d'un décodage de flux. EN : result of a stream decode.</summary>
public sealed class DecodeResult
{
    public required IReadOnlyList<RawMessage> Messages { get; init; }

    public required ProtoStats Stats { get; init; }

    /// <summary>FR : opcodes distincts rencontrés, dans l'ordre de PREMIÈRE apparition. EN : distinct opcodes, in first-seen order.</summary>
    public IReadOnlyList<string> DistinctOpcodes
    {
        get
        {
            var seen = new HashSet<string>(StringComparer.Ordinal);
            var order = new List<string>();
            foreach (RawMessage message in Messages)
            {
                if (seen.Add(message.Opcode.Name))
                {
                    order.Add(message.Opcode.Name);
                }
            }

            return order;
        }
    }

    /// <summary>FR : compte des trames par cas racine. EN : frame count per root case.</summary>
    public IReadOnlyDictionary<RootCase, int> CasesHistogram()
    {
        var histogram = new Dictionary<RootCase, int>();
        foreach (RawMessage message in Messages)
        {
            histogram[message.Case] = histogram.GetValueOrDefault(message.Case) + 1;
        }

        return histogram;
    }
}

/// <summary>
/// FR : façade du codec 3.0. Décode un flux (fichier de capture ou socket) en messages, et les
///      ré-encode. Aucune horloge, aucun aléa : à entrée égale, sortie égale, toujours.
/// EN : the 3.0 codec facade. Decodes a stream (capture file or socket) into messages, and
///      re-encodes them. No clock, no randomness: equal input, equal output, always.
/// </summary>
public sealed class Codec3
{
    private readonly int _maxFrameLength;
    private readonly bool _headerSizeIncludesItself;

    public Codec3(
        int maxFrameLength = FrameReader.DefaultMaxFrameLength,
        bool headerSizeIncludesItself = false)
    {
        _maxFrameLength = maxFrameLength;
        _headerSizeIncludesItself = headerSizeIncludesItself;
    }

    /// <summary>
    /// FR : décode un flux livré en SEGMENTS arbitraires — c'est la forme réelle du TCP. Passer un
    ///      seul segment décode un fichier ; passer 2 347 découpes prouve le recollage.
    /// EN : decodes a stream delivered as arbitrary SEGMENTS — the real shape of TCP. Passing a
    ///      single segment decodes a file; passing 2,347 cuts proves the reassembly.
    /// </summary>
    public DecodeResult DecodeSegments(IEnumerable<ReadOnlyMemory<byte>> segments)
    {
        var reader = new FrameReader(_maxFrameLength, _headerSizeIncludesItself);
        var messages = new List<RawMessage>();
        var stats = new ProtoStats();

        foreach (ReadOnlyMemory<byte> segment in segments)
        {
            reader.Append(segment.Span);
            while (reader.TryReadFrame(out byte[] frame, out long offset))
            {
                messages.Add(DecodeFrame(frame, offset, stats));
            }
        }

        reader.AssertDrained();

        return new DecodeResult { Messages = messages, Stats = stats };
    }

    /// <summary>FR : décode un tampon complet en un seul segment. EN : decodes a whole buffer as one segment.</summary>
    public DecodeResult Decode(ReadOnlyMemory<byte> data)
        => DecodeSegments(new[] { data });

    /// <summary>
    /// FR : décode UNE trame délimitée. Le corps de l'opcode est lu en arbre générique quand il est
    ///      structuré ; sinon il reste opaque, ce qui est dit, pas caché.
    /// EN : decodes ONE delimited frame. The opcode body is read as a generic tree when structured;
    ///      otherwise it stays opaque, which is stated, not hidden.
    /// </summary>
    public RawMessage DecodeFrame(ReadOnlySpan<byte> frame, long frameOffset, ProtoStats stats)
    {
        Envelope envelope = Envelope.Decode(frame, frameOffset, stats);

        IReadOnlyList<ProtoField> payloadFields = Array.Empty<ProtoField>();
        if (envelope.Payload.Length > 0)
        {
            try
            {
                payloadFields = ProtoReader.ReadMessage(envelope.Payload, frameOffset, new ProtoStats());
            }
            catch (CodecException)
            {
                // FR : charge non structurée — le sniffer l'affichera en hexadécimal.
                // EN : unstructured payload — the sniffer will print it as hex.
                payloadFields = Array.Empty<ProtoField>();
            }
        }

        return new RawMessage
        {
            Offset = frameOffset,
            FrameLength = frame.Length,
            Opcode = envelope.Opcode,
            Direction = envelope.Direction,
            Case = envelope.Case,
            RequestId = envelope.RequestId,
            Payload = envelope.Payload,
            Fields = payloadFields,
            Envelope = envelope,
        };
    }

    /// <summary>FR : ré-encode une suite de messages en flux encadré. EN : re-encodes a message list into a framed stream.</summary>
    public byte[] Encode(IEnumerable<RawMessage> messages)
    {
        var writer = new FrameWriter(_maxFrameLength, _headerSizeIncludesItself);
        var buffer = new List<byte>(4096);

        foreach (RawMessage message in messages)
        {
            writer.WriteTo(buffer, message.Envelope.Encode());
        }

        return buffer.ToArray();
    }
}
