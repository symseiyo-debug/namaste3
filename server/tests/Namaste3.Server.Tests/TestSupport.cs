// ============================================================================================
// QUOI : l'outillage commun des tests — localisation de la table de liaison, horloge FIGÉE,
//     fabrique de tickets déterministe, et un « faux client » qui joue le scénario complet sans
//     jamais ouvrir un socket.
// POURQUOI (05/09/2026) : deux exigences du chantier se rejoignent ici. Le déterminisme
//     d'abord : aucune horloge réelle, aucun aléa, donc deux exécutions du même test rendent la
//     même suite d'octets et un échec est reproductible. L'absence de réseau ensuite : un test
//     qui ouvre un port mesure le réseau autant que le serveur, et devient « flaky » — la
//     machine à états ne touchant aucun socket, on la pilote directement.
// EN : the tests' shared tooling — binding-table lookup, FROZEN clock, deterministic ticket
//     mint, and a "fake client" that plays the whole scenario without ever opening a socket.
// COMMENT LANCER / USAGE : dotnet test (voir gate-serveur.sh).
// GATE : aucun test ne passe si `TableDeTest()` ne trouve pas la table — un test qui s'auto-
//     désactive faute de matière est un faux vert.
// ============================================================================================

using Namaste3.Codec;
using Namaste3.Server.Connection;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : les fixtures et le montage commun. Statique et sans état partagé mutable.
/// EN : fixtures and shared setup. Static, with no mutable shared state.
/// </summary>
public static class TestSupport
{
    /// <summary>
    /// FR : l'instant FIGÉ de tous les tests. Une date fixe, pas `UtcNow` : l'horloge du serveur
    ///      part dans une trame émise, donc une horloge vivante rendrait les octets différents à
    ///      chaque exécution et le round-trip byte-exact serait invérifiable.
    /// EN : the FROZEN instant. The server clock ends up inside an emitted frame, so a live
    ///      clock would change the bytes on every run.
    /// </summary>
    public static readonly DateTimeOffset Instant =
        new(2026, 9, 5, 0, 0, 0, TimeSpan.Zero);

    /// <summary>FR : l'horloge figée. / EN : the frozen clock.</summary>
    public static Func<DateTimeOffset> FrozenClock() => () => Instant;

    /// <summary>
    /// FR : une fabrique de tickets DÉTERMINISTE : elle compte, elle ne tire pas au sort. Un
    ///      ticket prévisible est inacceptable en production et indispensable en test.
    /// EN : a DETERMINISTIC ticket mint: it counts, it does not draw at random.
    /// </summary>
    public static Func<string> CountingMint()
    {
        int next = 0;
        return () => $"ticket-de-test-{++next:D4}";
    }

    /// <summary>
    /// FR : trouve la table de liaison en remontant depuis le binaire de test. Si elle manque,
    ///      on ÉCHOUE — jamais un `Skip` : un test qui s'éteint faute de matière rend un vert
    ///      qui ne mesure rien.
    /// EN : finds the binding table by walking up from the test binary. Missing table = FAILURE,
    ///      never a skip: a self-disabling test yields a green that measures nothing.
    /// </summary>
    public static OpcodeTable Table()
    {
        for (DirectoryInfo? dir = new(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            string candidate = Path.Combine(dir.FullName, "protocol");
            if (!Directory.Exists(candidate))
            {
                continue;
            }

            string[] found = Directory.GetFiles(candidate, "binding-*.json");
            if (found.Length > 0)
            {
                Array.Sort(found, StringComparer.Ordinal);
                return OpcodeTable.Load(found[^1]);
            }
        }

        throw new FileNotFoundException(
            "table de liaison introuvable / binding table not found — " +
            "lancer / run: python3 protocol/generer-binding.py");
    }

    /// <summary>
    /// FR : le répertoire des captures réelles. Surchargeable par la variable d'environnement
    ///      utilisée par la gate de l'étage 2, pour qu'une seule variable serve les deux étages.
    /// EN : the real captures' directory, overridable by the same environment variable stage 2
    ///      already uses, so one variable serves both stages.
    /// </summary>
    public static string FixturesDirectory()
        => Environment.GetEnvironmentVariable("NAMASTE3_FIXTURES") ?? "refs/JondoEmu/datos";

    /// <summary>Les trois captures réelles, par nom. / The three real captures, by name.</summary>
    public static readonly string[] FixtureNames =
    {
        "world_etapa1_tras_elegir_personaje.bin",
        "world_etapa2_tras_confirmar.bin",
        "world_etapa3_mapa.bin",
    };

    /// <summary>
    /// FR : monte une session neuve et son journal, tous deux déterministes.
    /// EN : builds a fresh session and its journal, both deterministic.
    /// </summary>
    public static (ConnectionSession Session, FrameLog Log, TicketRegistry Tickets, StringWriter Out)
        NewSession(OpcodeTable? table = null)
    {
        table ??= Table();
        var options = new ServerOptions { Verbose = false };
        var output = new StringWriter();
        var log = new FrameLog(output, verbose: false);
        var tickets = new TicketRegistry(FrozenClock(), CountingMint(), options.TicketLifetime);
        var session = new ConnectionSession(table, options, log, tickets, FrozenClock());
        return (session, log, tickets, output);
    }

    /// <summary>
    /// FR : décode toutes les trames de JEU d'un flux d'octets, à travers le codec de l'étage 2 —
    ///      exactement le chemin qu'un vrai client emprunterait pour lire ce que nous émettons.
    /// EN : decodes every GAME frame in a byte stream through the stage-2 codec — exactly the
    ///      path a real client would take to read what we emit.
    /// </summary>
    public static IReadOnlyList<RawMessage> DecodeGame(IEnumerable<byte[]> frames)
    {
        var joined = new List<byte>();
        foreach (byte[] frame in frames)
        {
            joined.AddRange(frame);
        }

        return new Codec3().Decode(joined.ToArray()).Messages;
    }

    /// <summary>
    /// FR : encode une trame de connexion NUE pour le faux client — branche 1 (auth), avec la
    ///      langue et, si demandé, l'identifiant de serveur choisi (`f4 { f1 }`).
    /// EN : encodes a NAKED frame for the fake client — branch 1 (auth), with the language and,
    ///      optionally, the chosen server id (f4 { f1 }).
    /// </summary>
    public static byte[] NakedAuthFrame(string language, long? serverId)
    {
        var auth = new List<byte>();
        ProtoWriter.WriteLengthDelimited(auth, 1, System.Text.Encoding.UTF8.GetBytes(language));
        if (serverId.HasValue)
        {
            var selected = new List<byte>();
            ProtoWriter.WriteVarint(selected, 1, (ulong)serverId.Value);
            ProtoWriter.WriteLengthDelimited(auth, 4, selected.ToArray());
        }

        var root = new List<byte>();
        ProtoWriter.WriteLengthDelimited(root, 1, auth.ToArray());
        return new FrameWriter().Frame(root.ToArray());
    }

    /// <summary>
    /// FR : encode une trame de JEU côté client. Le sens C2S n'est prouvé par aucune frame réelle
    ///      (le codec le déclare comme angle mort) : ces trames sont donc SYNTHÉTIQUES, et on
    ///      l'écrit ici plutôt que de laisser croire le contraire.
    /// EN : encodes a client-side GAME frame. The C2S direction is proven by no real frame, so
    ///      these are SYNTHETIC — stated here rather than left to look otherwise.
    /// </summary>
    public static byte[] ClientGameFrame(string opcode, IReadOnlyList<FieldSpec> payload)
    {
        byte[] body = PayloadBuilder.Build(payload, new NoInjections());
        return GameEnvelope.Frame(opcode, body, RootCase.Request, requestId: -1);
    }

    /// <summary>
    /// FR : une source d'injection VIDE — elle refuse tout. Elle prouve au passage qu'une forme
    ///      qui réclamerait une injection ne peut pas être encodée par accident.
    /// EN : an EMPTY injection source; it refuses everything.
    /// </summary>
    public sealed class NoInjections : IInjectionSource
    {
        /// <inheritdoc/>
        public bool TryVarint(string key, out ulong value) { value = 0; return false; }

        /// <inheritdoc/>
        public bool TryText(string key, out string value) { value = string.Empty; return false; }

        /// <inheritdoc/>
        public bool TryPacked(string key, out IReadOnlyList<ulong> values)
        {
            values = Array.Empty<ulong>();
            return false;
        }
    }

    /// <summary>FR : un champ varint pour les trames du faux client. / EN : a varint field.</summary>
    public static FieldSpec Varint(int number, ulong value)
        => new() { Number = number, Kind = FieldKind.Varint, Varint = value };

    /// <summary>FR : un champ texte pour les trames du faux client. / EN : a text field.</summary>
    public static FieldSpec Text(int number, string value)
        => new() { Number = number, Kind = FieldKind.Text, Text = value };
}
