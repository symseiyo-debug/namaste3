// QUOI : SabotageTests.cs -- flip d'un octet sur chaque fixture réelle, exige que la gate BOUGE
//   (refus nommé ou sha différent).
// POURQUOI : c'est la contre-épreuve du round-trip -- sans sabotage, un round-trip vert pourrait
//   masquer un codec qui ignore une partie du flux au lieu de le vérifier.
// COMMENT LANCER : dotnet test --filter SabotageTests (depuis codec/).
// GATE : rejouée par gate-codec.sh --epreuve.
using Xunit;
using Xunit.Abstractions;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : SABOTAGE. Une gate qui reste verte quand on corrompt son entrée ne mesure rien — elle
///      mesure sa propre complaisance. On modifie UN octet, partout, et on exige que la gate BOUGE :
///      soit un refus NOMMÉ, soit un sha différent de l'original. Le seul verdict interdit est
///      « sha identique à l'original » : il signifierait qu'un octet du fil ne survit pas au codec.
/// EN : SABOTAGE. A gate that stays green when its input is corrupted measures nothing — it
///      measures its own complacency. We flip ONE byte, everywhere, and demand the gate MOVES:
///      either a NAMED refusal, or a sha different from the original. The only forbidden verdict is
///      "sha identical to the original": it would mean a byte of the wire does not survive the codec.
/// </summary>
public sealed class SabotageTests
{
    private readonly ITestOutputHelper _output;

    public SabotageTests(ITestOutputHelper output) => _output = output;

    /// <summary>
    /// FR : chaque octet de la petite fixture, un par un, XOR 0xFF.
    /// EN : every byte of the small fixture, one at a time, XOR 0xFF.
    /// </summary>
    [Fact]
    public void SmallFixture_EverySingleByteFlipped_MovesTheGate()
    {
        byte[] original = Fixtures.Read(Fixtures.Etape2);
        var codec = new Codec3();
        string originalSha = Fixtures.Sha256Hex(codec.Encode(codec.Decode(original).Messages));

        int refused = 0;
        int different = 0;
        var silentPasses = new List<int>();
        var refusalCodes = new Dictionary<CodecErrorCode, int>();

        for (int position = 0; position < original.Length; position++)
        {
            byte[] sabotaged = (byte[])original.Clone();
            sabotaged[position] ^= 0xFF;

            try
            {
                DecodeResult result = codec.Decode(sabotaged);
                string sha = Fixtures.Sha256Hex(codec.Encode(result.Messages));

                if (sha == originalSha)
                {
                    // FR : la gate n'a PAS bougé — un octet corrompu a été absorbé en silence.
                    // EN : the gate did NOT move — a corrupted byte was silently absorbed.
                    silentPasses.Add(position);
                }
                else
                {
                    different++;
                }
            }
            catch (CodecException ex)
            {
                refused++;
                refusalCodes[ex.Code] = refusalCodes.GetValueOrDefault(ex.Code) + 1;
            }
        }

        _output.WriteLine($"octets sabotés/bytes sabotaged = {original.Length}");
        _output.WriteLine($"  refus nommés/named refusals  = {refused}");
        _output.WriteLine($"  sha différent/different sha  = {different}");
        _output.WriteLine($"  absorbés en silence/silent   = {silentPasses.Count}");
        foreach ((CodecErrorCode code, int count) in refusalCodes.OrderByDescending(p => p.Value))
        {
            _output.WriteLine($"    {code} × {count}");
        }

        if (silentPasses.Count > 0)
        {
            _output.WriteLine($"  offsets absorbés/silent offsets: {string.Join(", ", silentPasses.Take(20))}");
        }

        Assert.Equal(original.Length, refused + different + silentPasses.Count);
        Assert.Empty(silentPasses);

        // FR : CONTRÔLE — le sabotage doit produire les DEUX natures de réaction, sinon un seul
        //      mécanisme est éprouvé et l'autre reste une affirmation.
        // EN : CONTROL — sabotage must produce BOTH kinds of reaction, otherwise only one mechanism
        //      is exercised and the other stays a claim.
        Assert.True(refused > 0, "aucun refus nommé / no named refusal");
        Assert.True(different > 0, "aucun sha différent / no different sha");
    }

    /// <summary>
    /// FR : sabotage CIBLÉ sur des zones qui portent un sens : l'octet de longueur de trame, un
    ///      octet du typeUrl, un octet du tag racine. Le sabotage aveugle prouve la robustesse ;
    ///      celui-ci prouve qu'on touche bien les pièces qu'on prétend décoder.
    /// EN : TARGETED sabotage on meaningful areas: the frame length byte, a typeUrl byte, a root tag
    ///      byte. Blind sabotage proves robustness; this one proves we really touch the parts we
    ///      claim to decode.
    /// </summary>
    [Theory]
    [InlineData(0, "octet de longueur de la 1re trame / 1st frame length byte")]
    [InlineData(1, "tag racine / root tag")]
    [InlineData(8, "typeUrl / typeUrl")]
    public void SmallFixture_TargetedByteFlipped_MovesTheGate(int position, string what)
    {
        byte[] original = Fixtures.Read(Fixtures.Etape2);
        var codec = new Codec3();
        string originalSha = Fixtures.Sha256Hex(codec.Encode(codec.Decode(original).Messages));

        byte[] sabotaged = (byte[])original.Clone();
        sabotaged[position] ^= 0xFF;

        string verdict;
        try
        {
            DecodeResult result = codec.Decode(sabotaged);
            string sha = Fixtures.Sha256Hex(codec.Encode(result.Messages));
            Assert.NotEqual(originalSha, sha);
            verdict = $"sha différent/different {sha[..16]}…";
        }
        catch (CodecException ex)
        {
            verdict = $"refus nommé/named refusal {ex.Code} @ {ex.Offset}";
        }

        _output.WriteLine($"offset {position} ({what}) → {verdict}");
    }

    /// <summary>
    /// FR : TÉMOIN DE NON-DESTRUCTION — la même boucle, sans sabotage, doit rendre 0 mouvement.
    ///      Sinon le test précédent pourrait « bouger » à cause de sa propre mécanique de clonage.
    /// EN : NON-DESTRUCTION WITNESS — the same loop, without sabotage, must yield 0 movement.
    ///      Otherwise the previous test could "move" because of its own cloning mechanics.
    /// </summary>
    [Fact]
    public void SmallFixture_ClonedWithoutSabotage_DoesNotMove()
    {
        byte[] original = Fixtures.Read(Fixtures.Etape2);
        var codec = new Codec3();
        string originalSha = Fixtures.Sha256Hex(codec.Encode(codec.Decode(original).Messages));

        for (int position = 0; position < original.Length; position += 97)
        {
            byte[] clone = (byte[])original.Clone();
            clone[position] ^= 0x00;
            Assert.Equal(originalSha, Fixtures.Sha256Hex(codec.Encode(codec.Decode(clone).Messages)));
        }
    }
}
