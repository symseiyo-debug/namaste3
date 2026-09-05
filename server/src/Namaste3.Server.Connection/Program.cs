// ============================================================================================
// QUOI : le point d'entrée du serveur de connexion 3.0 — charge la table de liaison, imprime ce
//     qu'elle contient, ouvre l'écoute, sert jusqu'à Ctrl-C.
// POURQUOI (05/09/2026) : le démarrage IMPRIME l'état de la table (build, opcodes liés,
//     recroisements, longueur de la rafale) avant d'ouvrir le port. Un serveur qui démarre en
//     silence sur une table périmée fait chercher la panne dans le client ; ici, tout ce qui
//     pourrait faire échouer la connexion est visible AVANT qu'un client se présente.
//     Aucune horloge n'est lue dans le cœur : elle est injectée depuis ici, une seule fois.
// EN : the 3.0 connection server's entry point. Start-up PRINTS the table's state before opening
//     the port, so a stale table is visible before any client shows up.
// COMMENT LANCER / USAGE :
//     dotnet run --project src/Namaste3.Server.Connection
//     dotnet run --project src/Namaste3.Server.Connection -- --port 18420 --silencieux
// GATE : `gate-serveur.sh` (build + tests + 0 opcode littéral dans src/).
// ============================================================================================

using System.Security.Cryptography;
using Namaste3.Server.Connection;

// FR : le chemin par défaut de la table, relatif au binaire — le serveur se lance depuis
//      n'importe quel répertoire sans qu'on lui explique où il habite.
// EN : the table's default path, relative to the binary, so the server runs from anywhere.
string DefaultBindingPath()
{
    string here = AppContext.BaseDirectory;
    for (DirectoryInfo? dir = new(here); dir is not null; dir = dir.Parent)
    {
        string candidate = Path.Combine(dir.FullName, "protocol");
        if (Directory.Exists(candidate))
        {
            string[] found = Directory.GetFiles(candidate, "binding-*.json");
            if (found.Length > 0)
            {
                Array.Sort(found, StringComparer.Ordinal);
                return found[^1];
            }
        }
    }

    return string.Empty;
}

ServerOptions options;
try
{
    options = ServerOptions.Parse(args, DefaultBindingPath());
}
catch (ArgumentException ex)
{
    Console.Error.WriteLine($"REFUS/REFUSED : {ex.Message}");
    return 2;
}

if (string.IsNullOrEmpty(options.BindingPath))
{
    Console.Error.WriteLine(
        "REFUS/REFUSED : aucune table de liaison trouvée / no binding table found. " +
        "Générer avec / generate with: python3 protocol/generer-binding.py, ou passer --table.");
    return 2;
}

OpcodeTable table;
try
{
    table = OpcodeTable.Load(options.BindingPath);
}
catch (BindingException ex)
{
    Console.Error.WriteLine($"REFUS/REFUSED : {ex.Message}");
    return 2;
}

// FR : l'état de la table, imprimé AVANT d'ouvrir le port. Le compte des recroisements dit
//      combien de lignes un instrument indépendant confirme — un nombre qui baisse est un signal.
// EN : the table's state, printed BEFORE opening the port.
Console.WriteLine($"table de liaison / binding table : {options.BindingPath}");
Console.WriteLine($"  build                : {table.Build}");
Console.WriteLine($"  opcodes liés / bound : {table.Bindings.Count}");
Console.WriteLine(
    "  recroisés étage 1    : " +
    table.Bindings.Count(b => b.CrossCheck.StartsWith("confirme", StringComparison.Ordinal)));
Console.WriteLine(
    $"  rafale / burst       : {table.WelcomeBurst.Count} messages, " +
    $"{table.WelcomeBurst.Select(s => s.Op).Distinct().Count()} opcodes distincts");

// FR : l'état du garde de ticket est imprimé au démarrage, dans les deux cas. Un garde desserré
//      qui ne le dit pas se retrouve desserré pour toujours, parce que personne ne s'en souvient.
// EN : the ticket guard's state is printed at start-up, both ways. A loosened guard that stays
//      quiet stays loosened forever, because nobody remembers.
Console.WriteLine(options.AcceptExternalTicket
    ? "  garde de ticket      : DESSERRÉ (--ticket-externe) — accepte un ticket non émis par nous"
    : "  garde de ticket      : FERMÉ — seul un ticket émis par la phase nue est accepté");

// FR : les deux sources non déterministes du serveur, injectées ICI et nulle part ailleurs :
//      l'horloge et la fabrique de tickets. Le cœur ne les crée jamais lui-même, ce qui rend
//      chaque test rejouable à l'identique.
// EN : the server's two non-deterministic sources, injected HERE and nowhere else.
// Longueur d'un ticket, en octets tirés au sort : 24, la même que la source, assez pour n'être
// pas devinable et assez court pour tenir dans un journal lisible.
// / A ticket's random length in bytes: 24, the source's own value.
const int TicketBytes = 24;

Func<DateTimeOffset> clock = () => DateTimeOffset.UtcNow;
Func<string> mint = () => Convert.ToHexString(RandomNumberGenerator.GetBytes(TicketBytes)).ToLowerInvariant();
var tickets = new TicketRegistry(clock, mint, options.TicketLifetime);

using var stopping = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    stopping.Cancel();
};

var server = new TcpServer(table, options, tickets, clock, Console.Out);
await server.RunAsync(stopping.Token).ConfigureAwait(false);
return 0;
