// QUOI : SegmentationTests.cs -- coupe une capture réelle à CHAQUE offset possible, vérifie que
//   FrameReader recolle sans trou.
// POURQUOI : un TCP réel ne respecte jamais les frontières de trame -- un test qui ne coupe
//   qu'à quelques offsets choisis à la main pourrait manquer exactement celui qui casse.
// COMMENT LANCER : dotnet test --filter SegmentationTests (depuis codec/).
// GATE : rejouée par gate-codec.sh --epreuve.
using Xunit;
using Xunit.Abstractions;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : le TCP ne livre pas des trames, il livre des octets. Une trame peut arriver en deux
///      morceaux, et deux trames peuvent arriver dans le même segment. Ces tests coupent une
///      capture réelle à CHAQUE offset possible : si le recollage a un trou, un offset le trouve.
/// EN : TCP does not deliver frames, it delivers bytes. A frame may arrive in two pieces, and two
///      frames may arrive in the same segment. These tests cut a real capture at EVERY possible
///      offset: if the reassembly has a hole, one offset finds it.
/// </summary>
public sealed class SegmentationTests
{
    private readonly ITestOutputHelper _output;

    public SegmentationTests(ITestOutputHelper output) => _output = output;

    /// <summary>
    /// FR : 2 348 octets → 2 347 découpes en deux segments. Chacune doit rendre EXACTEMENT le même
    ///      résultat qu'une livraison en un bloc.
    /// EN : 2,348 bytes → 2,347 two-segment cuts. Each must yield EXACTLY the same result as a
    ///      single-block delivery.
    /// </summary>
    [Fact]
    public void SmallFixture_EverySplitPoint_YieldsIdenticalResult()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape2);
        var codec = new Codec3();

        DecodeResult reference = codec.Decode(data);
        string referenceSha = Fixtures.Sha256Hex(codec.Encode(reference.Messages));
        int expectedFrames = reference.Messages.Count;

        int cuts = 0;
        var failures = new List<string>();

        for (int cut = 1; cut < data.Length; cut++)
        {
            cuts++;
            var segments = new[]
            {
                new ReadOnlyMemory<byte>(data, 0, cut),
                new ReadOnlyMemory<byte>(data, cut, data.Length - cut),
            };

            try
            {
                DecodeResult split = codec.DecodeSegments(segments);
                if (split.Messages.Count != expectedFrames)
                {
                    failures.Add($"cut={cut} trames/frames={split.Messages.Count} attendu/expected={expectedFrames}");
                    continue;
                }

                string sha = Fixtures.Sha256Hex(codec.Encode(split.Messages));
                if (sha != referenceSha)
                {
                    failures.Add($"cut={cut} sha={sha}");
                }
            }
            catch (CodecException ex)
            {
                failures.Add($"cut={cut} refus/refusal {ex.Code} @ {ex.Offset}");
            }
        }

        _output.WriteLine($"découpes/cuts={cuts} échecs/failures={failures.Count} sha={referenceSha}");
        foreach (string failure in failures.Take(10))
        {
            _output.WriteLine("  " + failure);
        }

        Assert.Equal(data.Length - 1, cuts);
        Assert.Empty(failures);
    }

    /// <summary>
    /// FR : livraison octet par octet — 2 348 segments d'un octet. Le cas le plus hostile pour un
    ///      délimiteur : chaque varint de longueur arrive en morceaux.
    /// EN : byte-by-byte delivery — 2,348 one-byte segments. The most hostile case for a delimiter:
    ///      every length varint arrives in pieces.
    /// </summary>
    [Fact]
    public void SmallFixture_ByteByByteDelivery_YieldsIdenticalResult()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape2);
        var codec = new Codec3();

        string referenceSha = Fixtures.Sha256Hex(codec.Encode(codec.Decode(data).Messages));

        var segments = new List<ReadOnlyMemory<byte>>(data.Length);
        for (int i = 0; i < data.Length; i++)
        {
            segments.Add(new ReadOnlyMemory<byte>(data, i, 1));
        }

        DecodeResult result = codec.DecodeSegments(segments);
        Assert.Equal(Fixtures.ExpectedFrameCount[Fixtures.Etape2], result.Messages.Count);
        Assert.Equal(referenceSha, Fixtures.Sha256Hex(codec.Encode(result.Messages)));
    }

    /// <summary>
    /// FR : plusieurs trames dans le MÊME segment — le cas inverse. La grosse fixture arrive en un
    ///      bloc de 90 935 octets qui porte 31 trames.
    /// EN : several frames in the SAME segment — the reverse case.
    /// </summary>
    [Fact]
    public void LargeFixture_SingleSegment_CarriesManyFrames()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape3);
        DecodeResult result = new Codec3().DecodeSegments(new[] { new ReadOnlyMemory<byte>(data) });

        Assert.Equal(Fixtures.ExpectedFrameCount[Fixtures.Etape3], result.Messages.Count);
    }

    /// <summary>
    /// FR : découpe en tranches irrégulières (7, 1, 13, 1024…) sur la GRANDE fixture — un segment
    ///      peut couper une trame de 87 878 octets en une dizaine de morceaux.
    /// EN : irregular slicing over the LARGE fixture — a segment may cut an 87,878-byte frame into
    ///      a dozen pieces.
    /// </summary>
    [Fact]
    public void LargeFixture_IrregularSegments_YieldIdenticalResult()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape3);
        var codec = new Codec3();
        string referenceSha = Fixtures.Sha256Hex(codec.Encode(codec.Decode(data).Messages));

        int[] pattern = { 7, 1, 13, 1024, 3, 65536, 2, 511 };
        var segments = new List<ReadOnlyMemory<byte>>();
        int position = 0;
        int index = 0;
        while (position < data.Length)
        {
            int size = Math.Min(pattern[index++ % pattern.Length], data.Length - position);
            segments.Add(new ReadOnlyMemory<byte>(data, position, size));
            position += size;
        }

        DecodeResult result = codec.DecodeSegments(segments);

        _output.WriteLine($"segments={segments.Count} trames/frames={result.Messages.Count}");
        Assert.Equal(Fixtures.ExpectedFrameCount[Fixtures.Etape3], result.Messages.Count);
        Assert.Equal(referenceSha, Fixtures.Sha256Hex(codec.Encode(result.Messages)));
    }

    /// <summary>
    /// FR : un flux tronqué au milieu d'une trame NE DOIT PAS rendre cette trame, et doit refuser
    ///      à la fermeture. « Incomplet » ne doit jamais se lire « fini ».
    /// EN : a stream truncated mid-frame MUST NOT yield that frame, and must refuse at close.
    ///      "Incomplete" must never read as "finished".
    /// </summary>
    [Fact]
    public void TruncatedStream_RefusesAtClose_WithNamedError()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape2);
        byte[] truncated = data[..(data.Length - 5)];

        var exception = Assert.Throws<CodecException>(
            () => new Codec3().Decode(truncated));

        Assert.Equal(CodecErrorCode.TrailingBytes, exception.Code);
        _output.WriteLine(exception.Message);
    }
}
