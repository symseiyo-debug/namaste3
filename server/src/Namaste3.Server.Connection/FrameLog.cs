// ============================================================================================
// QUOI : le journal de chaque trame reçue et émise — sens, phase, opcode, nom sémantique,
//     taille, et l'arbre des champs décodés. C'est à la fois la trace d'exploitation et NOTRE
//     INSTRUMENT D'OBSERVATION du client réel : sans lui, un client qui reste sur un écran noir
//     ne nous apprend rien.
// POURQUOI (05/09/2026) : le brief le demande explicitement, et la discipline du projet l'exige — « un
//     échec qui ne laisse aucune trace » et « un garde muet » sont les deux pannes qu'on paie le
//     plus cher. Un opcode que la table ne lie pas est JOURNALISÉ puis ignoré : ni crash, ni
//     silence. Le journal écrit sur un `TextWriter` injecté, donc les tests le capturent au lieu
//     de polluer la console.
// EN : the journal of every frame received and emitted — direction, phase, opcode, semantic
//     name, size, decoded field tree. Both the operational trace and OUR OBSERVATION INSTRUMENT
//     on the real client. An unbound opcode is LOGGED then ignored: no crash, no silence.
// COMMENT LANCER / USAGE : injecté dans `ConnectionSession` ; `--silencieux` le réduit au strict.
// GATE : `SequenceTests` lit le journal pour prouver l'ORDRE des messages émis.
// ============================================================================================

using System.Globalization;
using System.Text;
using Namaste3.Codec;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : le sens d'une trame, du point de vue du serveur.
/// EN : a frame's direction, from the server's point of view.
/// </summary>
public enum FrameFlow
{
    /// <summary>Reçue du client. / Received from the client.</summary>
    In,
    /// <summary>Émise vers le client. / Emitted towards the client.</summary>
    Out,
}

/// <summary>
/// FR : une ligne de journal, gardée en mémoire pour que les tests l'interrogent au lieu de
///      relire du texte. Un test qui grep une chaîne mesure le formateur, pas le serveur.
/// EN : a journal row, kept in memory so tests query it rather than grepping text. A test that
///      greps a string measures the formatter, not the server.
/// </summary>
public sealed record FrameRecord(
    FrameFlow Flow,
    string Phase,
    string Opcode,
    SemanticOp Op,
    int Bytes);

/// <summary>
/// FR : le journal. Il n'interprète rien : il rapporte ce qui est passé sur le fil.
/// EN : the journal. It interprets nothing; it reports what crossed the wire.
/// </summary>
public sealed class FrameLog
{
    private readonly TextWriter _writer;
    private readonly bool _verbose;
    private readonly List<FrameRecord> _records = new();

    /// <summary>
    /// FR : construit le journal. `verbose` ajoute l'arbre des champs sous chaque ligne.
    /// EN : builds the journal. `verbose` adds the field tree under each row.
    /// </summary>
    public FrameLog(TextWriter writer, bool verbose = true)
    {
        _writer = writer ?? throw new ArgumentNullException(nameof(writer));
        _verbose = verbose;
    }

    /// <summary>FR : tout ce qui est passé, dans l'ordre. / EN : everything, in order.</summary>
    public IReadOnlyList<FrameRecord> Records => _records;

    /// <summary>
    /// FR : les noms sémantiques ÉMIS, dans l'ordre — la preuve directe qu'une séquence est
    ///      celle qu'on attend, sans relire du texte formaté.
    /// EN : the EMITTED semantic names, in order — direct proof of a sequence.
    /// </summary>
    public IReadOnlyList<SemanticOp> Emitted
        => _records.Where(r => r.Flow == FrameFlow.Out && r.Op != SemanticOp.None)
                   .Select(r => r.Op)
                   .ToList();

    /// <summary>
    /// FR : journalise une trame de JEU, avec son arbre de champs quand il est demandé.
    /// EN : logs a GAME frame, with its field tree when asked for.
    /// </summary>
    public void Game(FrameFlow flow, string opcode, SemanticOp op, int bytes,
                     IReadOnlyList<ProtoField>? fields = null, long? requestId = null)
    {
        _records.Add(new FrameRecord(flow, PhaseGame, opcode, op, bytes));

        var line = new StringBuilder();
        line.Append(Arrow(flow)).Append(' ').Append(PhaseGame).Append("  ");
        line.Append(opcode.PadRight(4)).Append(' ');
        line.Append((op == SemanticOp.None ? UnboundLabel : op.ToString()).PadRight(26));
        line.Append(bytes.ToString(CultureInfo.InvariantCulture).PadLeft(7)).Append(" o/bytes");
        if (requestId.HasValue)
        {
            line.Append("  reqId=").Append(requestId.Value.ToString(CultureInfo.InvariantCulture));
        }

        _writer.WriteLine(line.ToString());
        if (_verbose && fields is { Count: > 0 })
        {
            WriteTree(fields, 2);
        }
    }

    /// <summary>
    /// FR : journalise une trame de la phase NUE (pas d'opcode : le protocole n'en a pas).
    /// EN : logs a NAKED-phase frame (no opcode: that protocol has none).
    /// </summary>
    public void Connect(FrameFlow flow, ConnectBranch branch, int bytes,
                        IReadOnlyList<ProtoField>? fields = null)
    {
        _records.Add(new FrameRecord(flow, PhaseConnect, branch.ToString(), SemanticOp.None, bytes));
        _writer.WriteLine(
            $"{Arrow(flow)} {PhaseConnect}  {branch,-26}      " +
            $"{bytes.ToString(CultureInfo.InvariantCulture).PadLeft(7)} o/bytes");
        if (_verbose && fields is { Count: > 0 })
        {
            WriteTree(fields, 2);
        }
    }

    /// <summary>
    /// FR : une note d'exploitation — bascule de phase, refus nommé, connexion fermée. Jamais un
    ///      silence : c'est ce qui distingue « rien ne s'est passé » de « on n'a rien regardé ».
    /// EN : an operational note — phase switch, named refusal, closed connection. Never silence.
    /// </summary>
    public void Note(string message) => _writer.WriteLine($"   .  {message}");

    /// <summary>FR : un refus, toujours NOMMÉ. / EN : a refusal, always NAMED.</summary>
    public void Refusal(string reason)
    {
        _refusals.Add(reason);
        _writer.WriteLine($"   ! REFUS/REFUSED : {reason}");
    }

    /// <summary>FR : les refus prononcés, pour les tests. / EN : the refusals, for tests.</summary>
    public IReadOnlyList<string> Refusals => _refusals;

    private readonly List<string> _refusals = new();

    // Étiquettes de phase. Quatre lettres chacune : la gate refuse les littéraux de TROIS lettres
    // minuscules (ce sont des opcodes), pas ceux-ci.
    // / Phase labels. Four letters each: the gate refuses THREE-lowercase-letter literals.
    private const string PhaseGame = "JEUX";
    private const string PhaseConnect = "NUEE";
    private const string UnboundLabel = "(non lié / unbound)";

    /// <summary>FR : la flèche du sens. / EN : the direction arrow.</summary>
    private static string Arrow(FrameFlow flow) => flow == FrameFlow.In ? "<==" : "==>";

    /// <summary>
    /// FR : écrit l'arbre des champs, indenté. Profondeur bornée par le décodeur lui-même.
    /// EN : writes the field tree, indented. Depth is bounded by the decoder itself.
    /// </summary>
    private void WriteTree(IReadOnlyList<ProtoField> fields, int indent)
    {
        foreach (ProtoField field in fields)
        {
            _writer.WriteLine(new string(' ', indent * 2) + field.Describe());
            if (field.Message is { Count: > 0 })
            {
                WriteTree(field.Message, indent + 1);
            }
        }
    }
}
