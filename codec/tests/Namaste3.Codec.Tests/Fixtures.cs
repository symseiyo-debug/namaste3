// QUOI : Fixtures.cs -- accès centralisé aux 3 captures réelles (chemin, sha256, comptes
//   attendus de trames/octets) partagé par tous les tests.
// POURQUOI : une seule source de vérité pour les 3 chemins/comptes -- sinon un test qui les
//   redéclare pourrait diverger silencieusement d'un autre.
// COMMENT LANCER : jamais seul -- consommé par RoundTripTests/SegmentationTests/SabotageTests.
// GATE : rejouée par gate-codec.sh (échoue si les fixtures sont absentes).
using System.Security.Cryptography;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : les 3 captures RÉELLES serveur→client du build 3.6.10.10 (rejeu Jondo). Elles sont en
///      LECTURE SEULE et hors de notre zone d'écriture. Si elles manquent, les tests ÉCHOUENT :
///      « pas de vert sans frame réelle » (cahier des charges §2, étage 2) — un test qui se
///      contente de sauter quand la matière manque fabrique un vert qui ne mesure rien.
/// EN : the 3 REAL server→client captures of build 3.6.10.10 (Jondo replay). They are READ-ONLY and
///      outside our write area. If they are missing, tests FAIL: "no green without a real frame" —
///      a test that merely skips when the material is missing manufactures a green that measures
///      nothing.
/// </summary>
public static class Fixtures
{
    /// <summary>FR : surchargeable pour rejouer ailleurs. EN : overridable to replay elsewhere.</summary>
    public static string Directory =>
        Environment.GetEnvironmentVariable("NAMASTE3_FIXTURES") ?? "refs/JondoEmu/datos";

    public const string Etape1 = "world_etapa1_tras_elegir_personaje.bin";
    public const string Etape2 = "world_etapa2_tras_confirmar.bin";
    public const string Etape3 = "world_etapa3_mapa.bin";

    /// <summary>
    /// FR : comptes de trames publiés par Jondo (`docs/world.md` §9), repris dans le fragment de
    ///      carte §(c). Ils servent de SECONDE SOURCE : notre décodeur doit tomber sur les mêmes
    ///      nombres sans les avoir jamais lus.
    /// EN : frame counts published by Jondo, used as a SECOND SOURCE: our decoder must land on the
    ///      same numbers without ever having read them.
    /// </summary>
    public static readonly IReadOnlyDictionary<string, int> ExpectedFrameCount =
        new Dictionary<string, int>
        {
            [Etape1] = 322,
            [Etape2] = 2,
            [Etape3] = 31,
        };

    /// <summary>FR : tailles mesurées sur disque (fragment §(c)). EN : sizes measured on disk.</summary>
    public static readonly IReadOnlyDictionary<string, int> ExpectedByteCount =
        new Dictionary<string, int>
        {
            [Etape1] = 64510,
            [Etape2] = 2348,
            [Etape3] = 90935,
        };

    // Chemin absolu d'une fixture par son nom (Etape1/2/3).
    // / Absolute path of a fixture by its name (Etape1/2/3).
    public static string PathOf(string name) => Path.Combine(Directory, name);

    // Lit une fixture ou refuse NOMMÉMENT (jamais un skip silencieux -- voir POURQUOI).
    // / Reads a fixture or refuses BY NAME (never a silent skip -- see POURQUOI).
    public static byte[] Read(string name)
    {
        string path = PathOf(name);
        if (!File.Exists(path))
        {
            throw new FileNotFoundException(
                $"fixture RÉELLE absente / REAL fixture missing: {path}. "
                + "Pas de vert sans frame réelle / no green without a real frame.", path);
        }

        return File.ReadAllBytes(path);
    }

    // Source de données xUnit [MemberData] pour paramétrer un test sur les 3 fixtures.
    // / xUnit [MemberData] data source to parametrize a test over the 3 fixtures.
    public static IEnumerable<object[]> All()
    {
        yield return new object[] { Etape1 };
        yield return new object[] { Etape2 };
        yield return new object[] { Etape3 };
    }

    // sha256 hex minuscule -- comparaison avant/après du round-trip.
    // / lowercase hex sha256 -- before/after round-trip comparison.
    public static string Sha256Hex(byte[] data)
        => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
}
