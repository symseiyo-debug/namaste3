// ============================================================================================
// QUOI : la configuration du serveur — port d'écoute, hôte et ports ANNONCÉS au client, chemin
//     de la table de liaison, verbosité du journal — plus la source d'injection qui alimente
//     les formes de la table (horloge, ticket, hôte, ports).
// POURQUOI (05/09/2026) : deux choses se ressemblent et ne sont PAS la même — le port sur
//     lequel on ÉCOUTE, et le port qu'on ANNONCE au client dans le message « serveur
//     sélectionné ». La conception de l'étage 3 (D-03) veut deux ports (connexion / jeu) ; le
//     le brief de ce soir en veut un seul, 18420, celui que le stub Zaap sert déjà comme
//     `connectionPort`. Les DEUX tiennent ici sans réécriture : on écoute sur `ListenPort`, on
//     annonce `AnnouncedPorts`, et par défaut les deux valent 18420 — le client revient donc au
//     même endroit et la bascule de phase se fait par le CONTENU de la première trame, comme la
//     source le décrit. Mettre 5556 dans `AnnouncedPorts` suffit à éprouver D-03.
// EN : server configuration. The port we LISTEN on and the port we ANNOUNCE are two different
//     things; both the one-port requirement and the two-port design fit without a rewrite.
// COMMENT LANCER / USAGE :
//     namaste3-connect [--port N] [--annonce-hote H] [--annonce-ports N,N] [--table CHEMIN]
// GATE : `gate-serveur.sh` démarre le serveur avec ces défauts et rejoue un faux client dessus.
// ============================================================================================

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : la configuration, figée après construction. Aucun défaut qui tue : chaque valeur a un
///      défaut EXPLICITE et documenté, jamais un zéro implicite.
/// EN : the configuration, frozen after construction. Every value has an EXPLICIT default.
/// </summary>
public sealed class ServerOptions
{
    /// <summary>
    /// FR : le port d'ÉCOUTE. 18420 par défaut — la valeur que le stub Zaap sert déjà au client
    ///      comme `connectionPort`.
    /// EN : the LISTEN port. 18420 by default — what the Zaap stub already serves the client.
    /// </summary>
    public int ListenPort { get; init; } = DefaultPort;

    /// <summary>
    /// FR : l'hôte ANNONCÉ dans « serveur sélectionné ». Le client rouvre sa connexion là.
    /// EN : the host ANNOUNCED in "server selected". The client reopens its connection there.
    /// </summary>
    public string AnnouncedHost { get; init; } = DefaultHost;

    /// <summary>
    /// FR : les ports ANNONCÉS. Le client prend le premier. Par défaut le même que l'écoute :
    ///      une seule socket, bascule de phase par contenu.
    /// EN : the ANNOUNCED ports. The client takes the first. Same as the listen port by default.
    /// </summary>
    public IReadOnlyList<int> AnnouncedPorts { get; init; } = new[] { DefaultPort };

    /// <summary>FR : le chemin de la table de liaison. / EN : the binding table path.</summary>
    public string BindingPath { get; init; } = string.Empty;

    /// <summary>FR : le journal imprime-t-il l'arbre des champs ? / EN : print the field tree?</summary>
    public bool Verbose { get; init; } = true;

    /// <summary>
    /// FR : durée de vie d'un ticket. Cinq minutes — la même borne que l'émulateur de référence,
    ///      reprise parce qu'elle est mesurée, pas parce qu'elle est jolie.
    /// EN : a ticket's lifetime. Five minutes, the reference emulator's measured bound.
    /// </summary>
    public TimeSpan TicketLifetime { get; init; } = TimeSpan.FromMinutes(5);

    /// <summary>
    /// FR : accepter un ticket que NOUS n'avons pas émis. FERMÉ par défaut, et c'est voulu.
    ///      ⚠️ Fait MESURÉ le 05/09 qui rend ce drapeau nécessaire : le stub HAAPI/Zaap de
    ///      l'étage 2 n'émet aucun jeton de jeu à lui — il retient le jeton d'entrée accepté par
    ///      `SignOnWithToken` et le réutilise tel quel (`haapi-stub/haapi_stub_v2.py`, commentaire
    ///      lignes 105-115). Le ticket que le vrai client présentera vient donc probablement de
    ///      cette chaîne-là, PAS de notre phase nue — et notre registre le refuserait, à juste
    ///      titre, puisqu'il ne l'a jamais émis.
    ///      Ouvrir ce drapeau accepte tout ticket NON VIDE et le journalise. C'est un
    ///      affaiblissement RÉEL du garde : il existe pour la première mise en route face au
    ///      client vivant, pas pour tourner ainsi. Le refermer est la première chose à faire
    ///      une fois la chaîne de jetons branchée bout en bout.
    /// EN : accept a ticket WE did not issue. CLOSED by default, on purpose. MEASURED on 05/09:
    ///      the stage-2 HAAPI/Zaap stub mints no game token of its own — it remembers the input
    ///      token `SignOnWithToken` accepted and reuses it as is. The real client's ticket will
    ///      therefore likely come from that chain, not from our naked phase, and our registry
    ///      would rightly refuse it. Opening this flag accepts any NON-EMPTY ticket and logs it.
    ///      A REAL weakening of the guard: it exists for first bring-up, not to stay on.
    /// </summary>
    public bool AcceptExternalTicket { get; init; }

    /// <summary>Le port par défaut. / The default port.</summary>
    public const int DefaultPort = 18420;

    /// <summary>L'hôte par défaut. / The default host.</summary>
    public const string DefaultHost = "127.0.0.1";

    /// <summary>
    /// FR : lit la ligne de commande. Un argument inconnu est un REFUS NOMMÉ, pas un silence :
    ///      une faute de frappe sur `--port` ne doit pas faire écouter le défaut sans le dire.
    /// EN : parses the command line. An unknown argument is a NAMED refusal, not silence.
    /// </summary>
    public static ServerOptions Parse(string[] args, string defaultBindingPath)
    {
        ArgumentNullException.ThrowIfNull(args);

        int port = DefaultPort;
        string host = DefaultHost;
        IReadOnlyList<int> announced = new[] { DefaultPort };
        string binding = defaultBindingPath;
        bool verbose = true;
        bool portGiven = false;
        bool externalTicket = false;

        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--port":
                    port = int.Parse(Next(args, ref i), System.Globalization.CultureInfo.InvariantCulture);
                    portGiven = true;
                    break;
                case "--annonce-hote":
                    host = Next(args, ref i);
                    break;
                case "--annonce-ports":
                    announced = Next(args, ref i)
                        .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                        .Select(p => int.Parse(p, System.Globalization.CultureInfo.InvariantCulture))
                        .ToList();
                    break;
                case "--table":
                    binding = Next(args, ref i);
                    break;
                case "--silencieux":
                    verbose = false;
                    break;
                case "--ticket-externe":
                    externalTicket = true;
                    break;
                default:
                    throw new ArgumentException($"argument inconnu / unknown argument: {args[i]}");
            }
        }

        // FR : si le port d'écoute a été changé mais pas l'annonce, on annonce le port d'écoute —
        //      annoncer 18420 alors qu'on écoute ailleurs enverrait le client dans le vide.
        // EN : if the listen port changed but not the announcement, we announce the listen port.
        if (portGiven && announced.Count == 1 && announced[0] == DefaultPort)
        {
            announced = new[] { port };
        }

        return new ServerOptions
        {
            ListenPort = port,
            AnnouncedHost = host,
            AnnouncedPorts = announced,
            BindingPath = binding,
            Verbose = verbose,
            AcceptExternalTicket = externalTicket,
        };
    }

    /// <summary>FR : la valeur qui suit un drapeau. / EN : the value following a flag.</summary>
    private static string Next(string[] args, ref int i)
    {
        if (i + 1 >= args.Length)
        {
            throw new ArgumentException($"valeur manquante après / missing value after: {args[i]}");
        }

        return args[++i];
    }
}

/// <summary>
/// FR : ce que le serveur injecte dans les formes de la table. Une classe, pas un dictionnaire
///      global : chaque session a la sienne, avec SON ticket.
/// EN : what the server injects into the table's shapes. One per session, with ITS ticket.
/// </summary>
public sealed class ServerInjections : IInjectionSource
{
    private readonly Func<DateTimeOffset> _clock;
    private readonly ServerOptions _options;

    /// <summary>FR : construit la source. / EN : builds the source.</summary>
    public ServerInjections(ServerOptions options, Func<DateTimeOffset> clock)
    {
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
    }

    /// <summary>
    /// FR : le ticket courant de la session, posé juste avant d'encoder « serveur sélectionné ».
    /// EN : the session's current ticket, set right before encoding "server selected".
    /// </summary>
    public string Ticket { get; set; } = string.Empty;

    // Les clés que la table de liaison peut demander. Elles vivent ICI et nulle part ailleurs.
    // / The keys the binding table may ask for. They live HERE and nowhere else.
    private const string KeyClock = "horloge_ms";
    private const string KeyTicket = "ticket";
    private const string KeyHost = "hote";
    private const string KeyPorts = "ports_jeu";

    /// <inheritdoc/>
    public bool TryVarint(string key, out ulong value)
    {
        if (key == KeyClock)
        {
            value = (ulong)_clock().ToUnixTimeMilliseconds();
            return true;
        }

        value = 0;
        return false;
    }

    /// <inheritdoc/>
    public bool TryText(string key, out string value)
    {
        switch (key)
        {
            case KeyTicket:
                value = Ticket;
                return true;
            case KeyHost:
                value = _options.AnnouncedHost;
                return true;
            default:
                value = string.Empty;
                return false;
        }
    }

    /// <inheritdoc/>
    public bool TryPacked(string key, out IReadOnlyList<ulong> values)
    {
        if (key == KeyPorts)
        {
            values = _options.AnnouncedPorts.Select(p => (ulong)p).ToList();
            return true;
        }

        values = Array.Empty<ulong>();
        return false;
    }
}
