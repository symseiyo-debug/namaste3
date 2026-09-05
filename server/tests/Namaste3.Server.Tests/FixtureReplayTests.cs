// ============================================================================================
// QUOI : rejeu des TROIS captures réelles à travers l'intégration étage 3 → codec étage 2.
// POURQUOI (05/09/2026) : l'étage 2 a déjà prouvé le décodage byte-exact de ces 355 trames ; ce
//     que CES tests mesurent est différent et vaut d'être dit — que NOTRE projet référence bien
//     ce codec-là, que les captures sont là où on croit, et que rien dans notre montage ne les
//     transforme au passage. C'est une épreuve d'INTÉGRATION, pas une re-preuve du codec, et la
//     confondre avec la seconde ferait croire qu'on a vérifié deux fois la même chose.
//     Les sha256 sont vérifiés : une fixture qui change sans qu'on le sache transformerait ce
//     vert en vert d'autre chose.
// EN : replays the THREE real captures through the stage-3 → stage-2 integration. This is an
//     INTEGRATION check, not a re-proof of the codec; sha256 are checked so a silently changed
//     fixture cannot turn this green into someone else's green.
// COMMENT LANCER / USAGE : dotnet test --filter FixtureReplayTests
// GATE : rc != 0 si une capture manque, a changé, ou ne rend pas son compte de trames.
// ============================================================================================

using System.Security.Cryptography;
using Namaste3.Codec;
using Xunit;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : l'épreuve d'intégration sur matière réelle.
/// EN : the integration check on real material.
/// </summary>
public sealed class FixtureReplayTests
{
    // Comptes et empreintes MESURÉS le 04/09 par la gate de l'étage 2. Les répéter ici est
    // volontaire : si l'étage 2 change ses attentes, la divergence doit se voir, pas se propager.
    // / Frame counts and digests MEASURED on 04/09 by the stage-2 gate, repeated here on purpose.
    private static readonly (string Name, int Frames, string Sha)[] Expected =
    {
        ("world_etapa1_tras_elegir_personaje.bin", 322,
         "4b08e983067d1455529a48f5a5a654e82b42087a7b1896ac283fc369efdf0432"),
        ("world_etapa2_tras_confirmar.bin", 2,
         "1bd7d1bbd5f65abc28e36f031469b2f0c8c43d64a883fda12495b6e1563e9f31"),
        ("world_etapa3_mapa.bin", 31,
         "602843eb75456f323f66aab58f87da528a72da0145e8b7fdc90aa483bd91c1ec"),
    };

    /// <summary>
    /// FR : chaque capture se décode par notre référence du codec, rend son compte de trames
    ///      attendu, et se ré-encode byte-exact. Le sha de la capture est vérifié D'ABORD.
    /// EN : each capture decodes through our codec reference, yields its expected frame count and
    ///      re-encodes byte-exact. The capture's sha is checked FIRST.
    /// </summary>
    [Fact]
    public void LesTroisCaptures_SeDecodentEtSeReencodentByteExact()
    {
        string dir = TestSupport.FixturesDirectory();
        foreach ((string name, int frames, string sha) in Expected)
        {
            string path = Path.Combine(dir, name);
            Assert.True(File.Exists(path), $"capture absente / missing capture: {path}");

            byte[] bytes = File.ReadAllBytes(path);
            Assert.Equal(sha, Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant());

            DecodeResult result = new Codec3().Decode(bytes);
            Assert.Equal(frames, result.Messages.Count);
            Assert.Equal(bytes, new Codec3().Encode(result.Messages));
        }
    }

    /// <summary>
    /// FR : la première capture porte bien la trame de personnage sélectionné dont nous avons
    ///      TIRÉ la forme de notre liste de personnages. C'est le témoin positif de la mesure du
    ///      05/09 : si cette trame disparaissait, notre forme n'aurait plus de source.
    /// EN : capture 1 carries the character-selected frame from which we DERIVED our character
    ///      list's shape — the positive control for the 05/09 measurement.
    /// </summary>
    [Fact]
    public void LaCapture1_PorteLaTrameDontLaFormeDuPersonnageEstTiree()
    {
        string path = Path.Combine(TestSupport.FixturesDirectory(), Expected[0].Name);
        Assert.True(File.Exists(path), $"capture absente / missing capture: {path}");

        DecodeResult result = new Codec3().Decode(File.ReadAllBytes(path));
        RawMessage? selected = result.Messages.FirstOrDefault(m => m.Opcode.Name == "kva");
        Assert.NotNull(selected);

        // La forme : f1 { f1 { f1 = détails, f2 = characterId } }. Trois niveaux, mesurés.
        // / The shape: f1 { f1 { f1 = details, f2 = characterId } }. Three levels, measured.
        ProtoField outer = Assert.Single(selected!.Fields);
        Assert.Equal(1, outer.Number);
        ProtoField wrapper = Assert.Single(outer.Message!);
        Assert.Equal(1, wrapper.Number);

        IReadOnlyList<ProtoField> entry = wrapper.Message!;
        Assert.Contains(entry, f => f.Number == 1 && f.Message is { Count: > 0 });   // détails
        Assert.Contains(entry, f => f.Number == 2 && f.WireType == ProtoWireType.Varint);  // id

        // Dans les détails : f2 = nom (chaîne), f3 = niveau (varint), f4 = bloc étendu.
        // / Inside the details: f2 = name (string), f3 = level (varint), f4 = extended block.
        IReadOnlyList<ProtoField> details = entry.First(f => f.Number == 1).Message!;
        Assert.Contains(details, f => f.Number == 2 && f.WireType == ProtoWireType.LengthDelimited);
        Assert.Contains(details, f => f.Number == 3 && f.WireType == ProtoWireType.Varint);
        Assert.Contains(details, f => f.Number == 4 && f.Message is { Count: > 0 });
    }
}
