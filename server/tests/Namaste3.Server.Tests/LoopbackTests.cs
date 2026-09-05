// ============================================================================================
// QUOI : l'unique épreuve qui passe par un VRAI socket — le serveur écoute sur un port éphémère,
//     un client de test se connecte en TCP et joue tout le scénario, de la phase nue à la carte.
// POURQUOI (05/09/2026) : tous les autres tests pilotent la machine à états directement, exprès,
//     pour rester déterministes. Mais ce faisant, aucun ne traverse `TcpServer` — et la couche
//     qu'on ne parcourt jamais est précisément celle où une panne passerait inaperçue jusqu'au
//     moment où le vrai client se présente. Ce test est le seul qui la parcourt.
//     Le port est 0 : le système en choisit un, donc deux exécutions simultanées ne se marchent
//     pas dessus et aucun test ne devine un numéro de port.
// EN : the ONE check that goes through a REAL socket. Every other test drives the state machine
//     directly to stay deterministic, so none of them traverses `TcpServer` — the very layer
//     where a failure would hide until the real client shows up. Port 0: the system picks one.
// COMMENT LANCER / USAGE : dotnet test --filter LoopbackTests
// GATE : rc != 0 si le serveur n'écoute pas, ou si la rafale n'arrive pas entière sur le socket.
// ============================================================================================

using System.Net.Sockets;
using Namaste3.Codec;
using Namaste3.Server.Connection;
using Xunit;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : l'épreuve réseau, de bout en bout.
/// EN : the end-to-end network check.
/// </summary>
public sealed class LoopbackTests
{
    /// <summary>
    /// FR : le scénario complet sur un vrai socket : la phase nue rend la liste des serveurs puis
    ///      un ticket, la phase de jeu rend la rafale entière. Le ticket est LU dans la réponse,
    ///      pas deviné — c'est ce qui fait de ce test un client et non un complice.
    /// EN : the full scenario on a real socket. The ticket is READ from the answer, not guessed —
    ///      which is what makes this a client rather than an accomplice.
    /// </summary>
    [Fact]
    public async Task UnVraiSocket_JoueLaPhaseNuePuisLaRafale()
    {
        OpcodeTable table = TestSupport.Table();
        var options = new ServerOptions { ListenPort = 0, Verbose = false };
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), options.TicketLifetime);
        var server = new TcpServer(table, options, tickets, TestSupport.FrozenClock(), TextWriter.Null);

        using var stopping = new CancellationTokenSource();
        Task serving = server.RunAsync(stopping.Token);
        int port = await WaitForPortAsync(server).ConfigureAwait(false);

        try
        {
            // --- Phase NUE : ouvrir, recevoir la liste des serveurs, choisir, recevoir le ticket.
            string ticket;
            using (var naked = new TcpClient())
            {
                await naked.ConnectAsync("127.0.0.1", port).ConfigureAwait(false);
                NetworkStream stream = naked.GetStream();

                await stream.WriteAsync(TestSupport.NakedAuthFrame("fr", null)).ConfigureAwait(false);
                Assert.NotNull(await ReadFrameAsync(stream).ConfigureAwait(false));

                await stream.WriteAsync(TestSupport.NakedAuthFrame("fr", 290)).ConfigureAwait(false);
                byte[]? selected = await ReadFrameAsync(stream).ConfigureAwait(false);
                Assert.NotNull(selected);
                ticket = ReadTicket(selected!);
                Assert.NotEmpty(ticket);
            }

            // --- Phase JEU : rouvrir, présenter le ticket, recevoir les 15 messages de la rafale.
            using (var game = new TcpClient())
            {
                await game.ConnectAsync("127.0.0.1", port).ConfigureAwait(false);
                NetworkStream stream = game.GetStream();

                await stream.WriteAsync(SequenceTests.TicketFrame(table, ticket)).ConfigureAwait(false);

                var frames = new List<byte[]>();
                while (frames.Count < ExpectedBurstFrames)
                {
                    byte[]? frame = await ReadFrameAsync(stream).ConfigureAwait(false);
                    if (frame is null)
                    {
                        break;
                    }

                    frames.Add(frame);
                }

                Assert.Equal(ExpectedBurstFrames, frames.Count);
                IReadOnlyList<RawMessage> decoded = TestSupport.DecodeGame(frames);
                Assert.Equal(ExpectedBurstFrames, decoded.Count);
                Assert.Equal(13, decoded.Select(m => m.Opcode.Name).Distinct().Count());
                Assert.Equal(table.OpcodeOf(SemanticOp.CharactersList), decoded[^3].Opcode.Name);
                Assert.Equal(table.OpcodeOf(SemanticOp.CharactersListEnd), decoded[^2].Opcode.Name);
            }
        }
        finally
        {
            stopping.Cancel();
            await Task.WhenAny(serving, Task.Delay(StopTimeoutMs)).ConfigureAwait(false);
        }
    }

    /// <summary>
    /// FR : attend que l'écoute soit réellement ouverte. On interroge le port RÉEL du serveur
    ///      plutôt que de dormir un délai fixe : un délai fixe est trop court sur une machine
    ///      chargée et trop long sur une machine libre.
    /// EN : waits until the listener is actually open, by polling the server's REAL port rather
    ///      than sleeping a fixed delay.
    /// </summary>
    private static async Task<int> WaitForPortAsync(TcpServer server)
    {
        for (int attempt = 0; attempt < PortAttempts; attempt++)
        {
            if (server.BoundPort != 0)
            {
                return server.BoundPort;
            }

            await Task.Delay(PortPollMs).ConfigureAwait(false);
        }

        throw new TimeoutException("le serveur n'a pas ouvert de port / server never bound a port");
    }

    /// <summary>
    /// FR : lit UNE trame complète : le varint de longueur, puis exactement autant d'octets. Rend
    ///      `null` si le pair ferme — c'est une fin, pas une panne.
    /// EN : reads ONE complete frame: the length varint, then exactly that many bytes. Returns
    ///      null when the peer closes — an ending, not a failure.
    /// </summary>
    private static async Task<byte[]?> ReadFrameAsync(NetworkStream stream)
    {
        var header = new List<byte>(Varint.MaxBytes);
        var one = new byte[1];
        ulong length;
        while (true)
        {
            int read = await ReadWithTimeoutAsync(stream, one).ConfigureAwait(false);
            if (read == 0)
            {
                return null;
            }

            header.Add(one[0]);
            if (Varint.TryRead(header.ToArray(), start: 0, out length, out _))
            {
                break;
            }
        }

        var body = new byte[length];
        int filled = 0;
        while (filled < body.Length)
        {
            int read = await ReadWithTimeoutAsync(stream, body.AsMemory(filled)).ConfigureAwait(false);
            if (read == 0)
            {
                return null;
            }

            filled += read;
        }

        // On rend la trame ENTIÈRE, préfixe compris, pour pouvoir la redonner au codec telle
        // quelle. / We return the WHOLE frame, prefix included, so the codec can take it as is.
        var whole = new List<byte>(header);
        whole.AddRange(body);
        return whole.ToArray();
    }

    /// <summary>
    /// FR : une lecture bornée dans le temps. Sans borne, un test qui attend une trame qui ne
    ///      viendra jamais pend indéfiniment au lieu d'échouer en nommant ce qui manque.
    /// EN : a time-bounded read. Without a bound, a test waiting for a frame that never comes
    ///      hangs forever instead of failing by name.
    /// </summary>
    private static async Task<int> ReadWithTimeoutAsync(NetworkStream stream, Memory<byte> buffer)
    {
        using var timeout = new CancellationTokenSource(ReadTimeoutMs);
        try
        {
            return await stream.ReadAsync(buffer, timeout.Token).ConfigureAwait(false);
        }
        catch (OperationCanceledException)
        {
            throw new TimeoutException("aucune trame reçue à temps / no frame received in time");
        }
    }

    /// <summary>
    /// FR : extrait le ticket de la réponse « serveur sélectionné » : racine f2 → f4 → f1 → f1.
    ///      Chaque numéro est VÉRIFIÉ (`mhl`, `mim`, `mik`), pas deviné.
    /// EN : extracts the ticket from the "server selected" answer: root f2 → f4 → f1 → f1.
    /// </summary>
    private static string ReadTicket(byte[] frame)
    {
        var reader = new FrameReader();
        reader.Append(frame);
        Assert.True(reader.TryReadFrame(out byte[] body, out _));

        ConnectMessage message = ConnectEnvelope.Decode(body);
        ProtoField selected = Assert.Single(message.Fields, f => f.Number == 4);
        ProtoField inner = Assert.Single(selected.Message!);
        ProtoField ticket = inner.Message!.First(f => f.Number == 1);
        return System.Text.Encoding.UTF8.GetString(ticket.Bytes);
    }

    // 15 émissions dans la rafale : le fait mesuré, répété ici parce que ce test compte des
    // trames sur un socket, pas des étapes dans une table.
    // / 15 emissions in the burst: the measured fact, restated because this test counts frames.
    private const int ExpectedBurstFrames = 15;

    private const int ReadTimeoutMs = 5000;   // une trame de loopback qui tarde 5 s est perdue
    private const int StopTimeoutMs = 2000;   // au-delà, l'arrêt ne viendra pas, on n'attend plus
    private const int PortAttempts = 100;     // 100 x 20 ms = 2 s pour ouvrir un port loopback
    private const int PortPollMs = 20;
}
