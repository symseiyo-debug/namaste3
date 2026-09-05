// ============================================================================================
// QUOI : le branchement réseau — écoute TCP, une session par connexion, boucle de pompage
//     octets → `ConnectionSession` → octets. C'est la SEULE couche qui touche un socket.
// POURQUOI (05/09/2026) : garder le réseau hors de la machine à états est ce qui permet aux
//     tests de jouer tout le scénario sans ouvrir un port — un test qui a besoin du réseau
//     mesure le réseau autant que le serveur. Ici, la boucle ne fait que trois choses : lire,
//     passer, écrire. Toute anomalie est un refus NOMMÉ, jamais une exception nue qui tuerait
//     l'écoute entière pour une connexion qui a mal tourné.
// EN : the network binding — TCP listen, one session per connection, byte pump. The ONLY layer
//     touching a socket; keeping it out of the state machine is what lets tests run networkless.
// COMMENT LANCER / USAGE : `await new TcpServer(...).RunAsync(token)`.
// GATE : `gate-serveur.sh` lance le binaire et vérifie qu'il écoute et journalise.
// ============================================================================================

using System.Net;
using System.Net.Sockets;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : l'écoute. Une connexion = une tâche = une session ; rien n'est partagé entre elles sauf
///      la table (immuable) et le registre de tickets (verrouillé).
/// EN : the listener. One connection = one task = one session; nothing shared but the immutable
///      table and the locked ticket registry.
/// </summary>
public sealed class TcpServer
{
    private readonly OpcodeTable _table;
    private readonly ServerOptions _options;
    private readonly TicketRegistry _tickets;
    private readonly Func<DateTimeOffset> _clock;
    private readonly TextWriter _out;

    /// <summary>FR : construit le serveur. / EN : builds the server.</summary>
    public TcpServer(OpcodeTable table, ServerOptions options, TicketRegistry tickets,
                     Func<DateTimeOffset> clock, TextWriter output)
    {
        _table = table ?? throw new ArgumentNullException(nameof(table));
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _tickets = tickets ?? throw new ArgumentNullException(nameof(tickets));
        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
        _out = output ?? throw new ArgumentNullException(nameof(output));
    }

    /// <summary>
    /// FR : le port réellement ouvert. Utile quand on demande le port 0 (le système en choisit
    ///      un) : un test ne doit jamais deviner un numéro de port.
    /// EN : the port actually opened. Useful with port 0 (system-chosen): a test must never
    ///      guess a port number.
    /// </summary>
    public int BoundPort { get; private set; }

    /// <summary>
    /// FR : ouvre l'écoute et sert jusqu'à l'annulation. Chaque connexion tourne sur sa propre
    ///      tâche ; l'échec de l'une n'arrête jamais l'écoute.
    /// EN : opens the listener and serves until cancellation. One task per connection; one
    ///      failing connection never stops the listener.
    /// </summary>
    public async Task RunAsync(CancellationToken token)
    {
        var listener = new TcpListener(IPAddress.Any, _options.ListenPort);
        listener.Start();
        BoundPort = ((IPEndPoint)listener.LocalEndpoint).Port;
        _out.WriteLine($"écoute / listening on 0.0.0.0:{BoundPort}  (build {_table.Build})");
        _out.WriteLine(
            $"annoncé au client / announced to the client: {_options.AnnouncedHost}:" +
            $"{string.Join(',', _options.AnnouncedPorts)}");

        try
        {
            while (!token.IsCancellationRequested)
            {
                TcpClient client = await listener.AcceptTcpClientAsync(token).ConfigureAwait(false);
                _ = Task.Run(() => ServeAsync(client, token), token);
            }
        }
        catch (OperationCanceledException)
        {
            // Arrêt demandé : ce n'est pas une panne, on ne le journalise pas comme telle.
            // / Requested stop: not a failure, so not logged as one.
        }
        finally
        {
            listener.Stop();
            _out.WriteLine("écoute fermée / listener closed");
        }
    }

    /// <summary>
    /// FR : sert UNE connexion. La session décide ce qui sort ; ici on ne fait que transporter.
    ///      Une exception est journalisée et referme CETTE connexion, jamais l'écoute.
    /// EN : serves ONE connection. The session decides what goes out; here we only carry it.
    /// </summary>
    private async Task ServeAsync(TcpClient client, CancellationToken token)
    {
        var log = new FrameLog(_out, _options.Verbose);
        var session = new ConnectionSession(_table, _options, log, _tickets, _clock);
        EndPoint? peer = client.Client.RemoteEndPoint;
        log.Note($"connexion acceptée / connection accepted: {peer}");

        try
        {
            using (client)
            {
                NetworkStream stream = client.GetStream();
                byte[] buffer = new byte[ReadBufferBytes];
                while (!token.IsCancellationRequested)
                {
                    int read = await stream.ReadAsync(buffer, token).ConfigureAwait(false);
                    if (read == 0)
                    {
                        log.Note("le client a fermé / client closed");
                        break;
                    }

                    foreach (byte[] frame in session.Receive(buffer.AsSpan(0, read)))
                    {
                        await stream.WriteAsync(frame, token).ConfigureAwait(false);
                    }

                    await stream.FlushAsync(token).ConfigureAwait(false);
                    if (session.ShouldClose)
                    {
                        log.Note("fermeture décidée par la session / close decided by the session");
                        break;
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
            // Arrêt demandé pendant une lecture. / Requested stop during a read.
        }
        catch (IOException ex)
        {
            log.Refusal($"entrée-sortie / io: {ex.Message}");
        }
        catch (SocketException ex)
        {
            log.Refusal($"socket: {ex.SocketErrorCode}");
        }
        finally
        {
            log.Note($"connexion terminée / connection ended: {peer}");
        }
    }

    // Taille du tampon de lecture. Les segments TCP arbitraires sont gérés par le délimiteur du
    // codec, donc cette valeur ne change AUCUN comportement — seulement le nombre d'appels.
    // / Read buffer size. Arbitrary TCP segmentation is handled by the codec's frame reader, so
    // this value changes NO behaviour, only the number of calls.
    private const int ReadBufferBytes = 16384;
}
