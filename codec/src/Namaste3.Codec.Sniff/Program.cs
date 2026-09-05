// QUOI : Program.cs -- décodeur de trames 3.0 en ligne de commande (namaste3-sniff), base du
//   sniffer communautaire (étage 5).
// POURQUOI : c'est l'outil de démonstration/preuve du codec -- gate-codec.sh l'appelle sur les
//   3 fixtures réelles pour mesurer le round-trip byte-exact, hors de tout test unitaire.
// COMMENT LANCER : dotnet run --project src/Namaste3.Codec.Sniff -- <fichier.bin|-> [--summary]
//   [--hex] [--depth N] (ou --help).
// GATE : rc=0 round-trip byte-exact ; rc=1 divergence ou refus nommé ; rc=2 usage -- rejoué par
//   gate-codec.sh sur les 3 fixtures réelles.
using System.Security.Cryptography;
using Namaste3.Codec;

namespace Namaste3.Codec.Sniff;

/// <summary>
/// FR : décodeur de trames 3.0 en ligne de commande — la base du sniffer communautaire (étage 5).
///      Lit un fichier de capture (charge utile TCP nue) ou stdin, et imprime chaque trame :
///      offset, longueur, sens, opcode, id de requête, puis ses champs en arbre générique.
/// EN : command-line 3.0 frame decoder — the base of the community sniffer (stage 5). Reads a
///      capture file (bare TCP payload) or stdin, and prints each frame: offset, length, direction,
///      opcode, request id, then its fields as a generic tree.
/// </summary>
public static class Program
{
    // Parse les arguments CLI, décode le fichier/stdin, imprime chaque trame puis le bilan
    // round-trip byte-exact (avant/après) -- le rc reflète ce bilan.
    // / Parses CLI args, decodes the file/stdin, prints each frame then the byte-exact
    // round-trip summary (before/after) -- the rc reflects that summary.
    public static int Main(string[] args)
    {
        if (args.Length == 1 && (args[0] is "-h" or "--help"))
        {
            PrintUsage();
            return 0;
        }

        string? path = null;
        bool quiet = false;
        bool hexPayload = false;
        int maxDepth = 6;

        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i])
            {
                case "--summary":
                    quiet = true;
                    break;
                case "--hex":
                    hexPayload = true;
                    break;
                case "--depth" when i + 1 < args.Length:
                    if (!int.TryParse(args[++i], out maxDepth) || maxDepth < 0)
                    {
                        Console.Error.WriteLine("--depth attend un entier >= 0 / expects an integer >= 0");
                        return 2;
                    }

                    break;
                default:
                    if (args[i].StartsWith('-'))
                    {
                        Console.Error.WriteLine($"option inconnue / unknown option: {args[i]}");
                        PrintUsage();
                        return 2;
                    }

                    path = args[i];
                    break;
            }
        }

        byte[] data;
        try
        {
            data = path is null ? ReadAllStdin() : File.ReadAllBytes(path);
        }
        catch (IOException ex)
        {
            Console.Error.WriteLine($"lecture impossible / cannot read: {ex.Message}");
            return 2;
        }

        string source = path ?? "<stdin>";
        Console.WriteLine($"source: {source}  octets/bytes={data.Length}  sha256={Sha256(data)}");

        var codec = new Codec3();
        DecodeResult result;
        try
        {
            result = codec.Decode(data);
        }
        catch (CodecException ex)
        {
            // FR : un refus NOMMÉ, avec son offset — jamais une trace de pile nue.
            // EN : a NAMED refusal, with its offset — never a bare stack trace.
            Console.Error.WriteLine($"REFUS/REFUSED {ex.Code} @ {ex.Offset}: {ex.Message}");
            return 1;
        }

        if (!quiet)
        {
            foreach (RawMessage message in result.Messages)
            {
                Console.WriteLine(message.Describe());
                PrintFields(message.Fields, 1, maxDepth);
                if (hexPayload && message.Fields.Count == 0 && message.Payload.Length > 0)
                {
                    Console.WriteLine($"    payload {Convert.ToHexString(message.Payload).ToLowerInvariant()}");
                }
            }
        }

        byte[] reencoded = codec.Encode(result.Messages);
        string before = Sha256(data);
        string after = Sha256(reencoded);

        Console.WriteLine();
        Console.WriteLine($"trames/frames        : {result.Messages.Count}");
        Console.WriteLine($"opcodes distincts    : {result.DistinctOpcodes.Count}  [{string.Join(' ', result.DistinctOpcodes)}]");
        Console.WriteLine($"cas racine/root cases: {FormatCases(result)}");
        Console.WriteLine($"arbre/tree           : {result.Stats}");
        Console.WriteLine($"round-trip           : {(before == after ? "BYTE-EXACT" : "DIVERGENT")}  avant/before={before}  après/after={after}");

        return before == after ? 0 : 1;
    }

    // Rend le décompte des 3 cas racine (Push/Request/Answer) sur une ligne, dans un ordre fixe.
    // / Renders the 3 root cases' counts (Push/Request/Answer) on one line, in a fixed order.
    private static string FormatCases(DecodeResult result)
    {
        IReadOnlyDictionary<RootCase, int> histogram = result.CasesHistogram();
        var parts = new List<string>();
        foreach (RootCase rootCase in new[] { RootCase.Push, RootCase.Request, RootCase.Answer })
        {
            parts.Add($"f{(int)rootCase}/{rootCase}={histogram.GetValueOrDefault(rootCase)}");
        }

        return string.Join("  ", parts);
    }

    // Imprime l'arbre de champs, récursif, indenté, borné par --depth (jamais tout un blob illisible).
    // / Prints the field tree, recursive, indented, bounded by --depth (never one unreadable blob).
    private static void PrintFields(IReadOnlyList<ProtoField> fields, int indent, int maxDepth)
    {
        if (indent > maxDepth)
        {
            return;
        }

        string pad = new(' ', indent * 4);
        foreach (ProtoField field in fields)
        {
            Console.WriteLine(pad + field.Describe());
            if (field.Message is not null)
            {
                PrintFields(field.Message, indent + 1, maxDepth);
            }
        }
    }

    // Lit stdin entier en mémoire (mode "-" / pas de chemin donné).
    // / Reads all of stdin into memory ("-" mode / no path given).
    private static byte[] ReadAllStdin()
    {
        using var stdin = Console.OpenStandardInput();
        using var memory = new MemoryStream();
        stdin.CopyTo(memory);
        return memory.ToArray();
    }

    // sha256 hex minuscule -- la preuve avant/après du round-trip byte-exact.
    // / lowercase hex sha256 -- the before/after proof of the byte-exact round-trip.
    private static string Sha256(byte[] data)
        => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();

    // Imprime l'usage CLI (déclenché par -h/--help ou une option inconnue).
    // / Prints the CLI usage (triggered by -h/--help or an unknown option).
    private static void PrintUsage()
    {
        Console.WriteLine("namaste3-sniff <fichier.bin|-> [--summary] [--hex] [--depth N]");
        Console.WriteLine("  FR : décode une capture de charge utile TCP 3.0 (framing varint + Any/typeUrl).");
        Console.WriteLine("  EN : decodes a 3.0 TCP payload capture (varint framing + Any/typeUrl).");
        Console.WriteLine("  rc=0 round-trip byte-exact · rc=1 divergence ou refus nommé · rc=2 usage");
    }
}
