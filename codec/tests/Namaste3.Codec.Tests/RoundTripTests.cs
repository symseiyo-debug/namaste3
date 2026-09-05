// QUOI : RoundTripTests.cs -- décode puis ré-encode chaque fixture réelle, exige un sha
//   identique avant/après, et croise 4 autres mesures publiées par Jondo (comptes, tailles, cas).
// POURQUOI : « pas de vert sans frame réelle » -- c'est LA preuve que le codec restitue chaque
//   octet du fil, pas seulement qu'il "compile" ou passe sur des fixtures synthétiques.
// COMMENT LANCER : dotnet test --filter RoundTripTests (depuis codec/).
// GATE : rejouée par gate-codec.sh (via `dotnet test` + son propre calcul indépendant du sha).
using Xunit;
using Xunit.Abstractions;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : LA gate de l'étage 2 — round-trip BYTE-EXACT contre des frames réelles.
/// EN : THE stage-2 gate — BYTE-EXACT round-trip against real frames.
/// </summary>
public sealed class RoundTripTests
{
    private readonly ITestOutputHelper _output;

    public RoundTripTests(ITestOutputHelper output) => _output = output;

    // LE test : décoder puis ré-encoder chaque fixture réelle doit rendre EXACTEMENT les mêmes octets.
    // / THE test: decoding then re-encoding each real fixture must yield EXACTLY the same bytes.
    [Theory]
    [MemberData(nameof(Fixtures.All), MemberType = typeof(Fixtures))]
    public void Fixture_DecodeReencode_IsByteExact(string name)
    {
        byte[] original = Fixtures.Read(name);
        Assert.Equal(Fixtures.ExpectedByteCount[name], original.Length);

        var codec = new Codec3();
        DecodeResult result = codec.Decode(original);
        byte[] reencoded = codec.Encode(result.Messages);

        string before = Fixtures.Sha256Hex(original);
        string after = Fixtures.Sha256Hex(reencoded);

        _output.WriteLine($"{name}: trames/frames={result.Messages.Count} "
            + $"opcodes={result.DistinctOpcodes.Count} [{string.Join(' ', result.DistinctOpcodes)}]");
        _output.WriteLine($"{name}: arbre/tree {result.Stats}");
        _output.WriteLine($"{name}: sha avant/before={before} après/after={after}");

        Assert.Equal(original.Length, reencoded.Length);
        Assert.Equal(before, after);
    }

    /// <summary>
    /// FR : le compte de trames doit tomber sur celui publié par Jondo, mesuré par un autre chemin
    ///      (leur dépouillement de 242 pcapng). Deux natures de source qui concordent.
    /// EN : the frame count must land on the one published by Jondo, measured through another path.
    /// </summary>
    [Theory]
    [MemberData(nameof(Fixtures.All), MemberType = typeof(Fixtures))]
    public void Fixture_FrameCount_MatchesJondoPublishedCount(string name)
    {
        DecodeResult result = new Codec3().Decode(Fixtures.Read(name));
        Assert.Equal(Fixtures.ExpectedFrameCount[name], result.Messages.Count);
    }

    /// <summary>
    /// FR : toute trame doit rendre un opcode de forme canonique (3 lettres minuscules). Si un jour
    ///      une trame réelle n'en rend pas, ce test le dit AVANT qu'un handler l'apprenne mal.
    /// EN : every frame must yield a canonical opcode (3 lowercase letters). If a real frame ever
    ///      fails this, the test says so BEFORE a handler learns it wrong.
    /// </summary>
    [Theory]
    [MemberData(nameof(Fixtures.All), MemberType = typeof(Fixtures))]
    public void Fixture_EveryOpcode_IsCanonicalThreeLetters(string name)
    {
        DecodeResult result = new Codec3().Decode(Fixtures.Read(name));

        var offenders = result.Messages
            .Where(m => !m.Opcode.IsCanonical)
            .Select(m => $"@{m.Offset} {m.Opcode}")
            .ToList();

        Assert.Empty(offenders);
    }

    /// <summary>
    /// FR : les 3 fixtures sont des captures SERVEUR→CLIENT. Aucune ne doit donc porter le cas
    ///      racine f2 (requête client). C'est la seule corroboration MESURÉE dont nous disposions
    ///      pour la table sens↔cas racine, que le dump ne donne pas.
    /// EN : the 3 fixtures are SERVER→CLIENT captures. None should therefore carry root case f2
    ///      (client request). This is the only MEASURED corroboration we have for the
    ///      direction↔root-case table, which the dump does not give.
    /// </summary>
    [Theory]
    [MemberData(nameof(Fixtures.All), MemberType = typeof(Fixtures))]
    public void Fixture_ServerToClientCapture_CarriesNoClientRequestCase(string name)
    {
        DecodeResult result = new Codec3().Decode(Fixtures.Read(name));
        IReadOnlyDictionary<RootCase, int> histogram = result.CasesHistogram();

        _output.WriteLine($"{name}: push={histogram.GetValueOrDefault(RootCase.Push)} "
            + $"request={histogram.GetValueOrDefault(RootCase.Request)} "
            + $"answer={histogram.GetValueOrDefault(RootCase.Answer)}");

        Assert.Equal(0, histogram.GetValueOrDefault(RootCase.Request));
        Assert.All(result.Messages, m => Assert.Equal(Direction.S2C, m.Direction));
    }

    /// <summary>
    /// FR : le décodage doit être STABLE — deux passes sur la même entrée rendent la même sortie.
    ///      Aucune horloge, aucun aléa dans le cœur : c'est ce qui rend la gate rejouable.
    /// EN : decoding must be STABLE — two passes over the same input yield the same output.
    /// </summary>
    [Fact]
    public void Decode_IsDeterministic_AcrossTwoPasses()
    {
        byte[] data = Fixtures.Read(Fixtures.Etape3);
        var codec = new Codec3();

        byte[] first = codec.Encode(codec.Decode(data).Messages);
        byte[] second = codec.Encode(codec.Decode(data).Messages);

        Assert.Equal(Fixtures.Sha256Hex(first), Fixtures.Sha256Hex(second));
    }

    /// <summary>
    /// FR : la plus grosse trame de chaque fixture, mesurée. Jondo publie `ivx` 16 821 o (étape 1),
    ///      `jtg` 2 306 o (étape 2), `ivi` 87 878 o (étape 3) — troisième recoupement indépendant.
    /// EN : the largest frame of each fixture, measured. Jondo publishes those three — a third
    ///      independent cross-check.
    /// </summary>
    [Theory]
    [InlineData(Fixtures.Etape1, "ivx", 16821)]
    [InlineData(Fixtures.Etape2, "jtg", 2306)]
    [InlineData(Fixtures.Etape3, "ivi", 87878)]
    public void Fixture_LargestFrame_MatchesJondoPublishedSize(string name, string opcode, int size)
    {
        DecodeResult result = new Codec3().Decode(Fixtures.Read(name));
        RawMessage largest = result.Messages.OrderByDescending(m => m.FrameLength).First();

        _output.WriteLine($"{name}: plus grosse/largest = {largest.Opcode} {largest.FrameLength} o/bytes");

        Assert.Equal(opcode, largest.Opcode.Name);
        Assert.Equal(size, largest.FrameLength);
    }

    /// <summary>
    /// FR : le dump déclare un SECOND champ sur chaque wrapper : `hdx.f2` = repeated int32
    ///      (`il2cpp.cs:839140-839141`), `hdy.f2`/`hdw.f2` = int32 (`il2cpp.cs:839231`, `839051`).
    ///      Jondo ne documente ce second champ QUE pour f2/f3 (l'id de requête) et pas du tout pour
    ///      f1. Ce test MESURE ce que les captures réelles portent, au lieu de le supposer.
    /// EN : the dump declares a SECOND field on every wrapper. Jondo documents it only for f2/f3.
    ///      This test MEASURES what the real captures carry, instead of assuming it.
    /// </summary>
    [Theory]
    [MemberData(nameof(Fixtures.All), MemberType = typeof(Fixtures))]
    public void Fixture_WrapperSecondField_IsMeasuredNotAssumed(string name)
    {
        DecodeResult result = new Codec3().Decode(Fixtures.Read(name));

        var shapes = new Dictionary<string, int>();
        foreach (RawMessage message in result.Messages)
        {
            var numbers = message.Envelope.WrapperFields
                .Select(f => $"f{f.Number}:wt{(int)f.WireType}")
                .ToList();
            string shape = $"cas/case f{(int)message.Case} → [{string.Join(' ', numbers)}]";
            shapes[shape] = shapes.GetValueOrDefault(shape) + 1;
        }

        foreach ((string shape, int count) in shapes.OrderByDescending(p => p.Value))
        {
            _output.WriteLine($"{name}: {shape} × {count}");
        }

        Assert.NotEmpty(shapes);
    }
}
