// ============================================================================================
// QUOI : les TÉMOINS NÉGATIFS — ce qui doit être REFUSÉ, et refusé par un motif NOMMÉ : ticket
//     vide, ticket rejoué, ticket expiré, sélection avant ticket, mauvais personnage, trame
//     tronquée, opcode inconnu, table incohérente.
// POURQUOI (05/09/2026) : une suite qui ne contient que des cas qui passent ne mesure pas un
//     garde, elle mesure un chemin heureux. Deux règles gouvernent ce fichier :
//     · chaque refus doit être DISTINCT des autres — un garde qui refuse tout de la même façon
//       ne dit pas lequel des trois motifs s'est produit devant un client qui reste bloqué ;
//     · chaque témoin négatif est accompagné de son TÉMOIN POSITIF — sans lui, un rouge pourrait
//       venir du montage du test et non de la chose testée.
// EN : the NEGATIVE CONTROLS — what must be REFUSED, and refused by a NAMED reason. Each refusal
//     must be DISTINCT from the others, and each negative control comes with its POSITIVE one,
//     without which a red might come from the test's own plumbing.
// COMMENT LANCER / USAGE : dotnet test --filter NegativeTests
// GATE : rc != 0 si un refus disparaît, ou si deux motifs se confondent.
// ============================================================================================

using Namaste3.Codec;
using Namaste3.Server.Connection;
using Xunit;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : les épreuves de refus.
/// EN : the refusal checks.
/// </summary>
public sealed class NegativeTests
{
    /// <summary>
    /// FR : les quatre verdicts de ticket sont DISTINCTS, et le cas accepté est présent — c'est
    ///      le témoin positif : sans lui, quatre refus identiques passeraient pour quatre gardes.
    /// EN : the four ticket verdicts are DISTINCT, and the accepted case is present — the
    ///      positive control, without which four identical refusals would look like four guards.
    /// </summary>
    [Fact]
    public void LesVerdictsDeTicket_SontQuatreEtDistincts()
    {
        DateTimeOffset now = TestSupport.Instant;
        var tickets = new TicketRegistry(() => now, TestSupport.CountingMint(), TimeSpan.FromMinutes(5));

        // Témoin POSITIF : un ticket frais est accepté.
        string fresh = tickets.Issue(accountId: 1, serverId: 290);
        Assert.Equal(TicketVerdict.Accepted, tickets.Redeem(fresh, out TicketGrant? grant));
        Assert.NotNull(grant);
        Assert.Equal(290, grant!.ServerId);

        // Rejeu du MÊME ticket : l'échange est atomique, il ne reste rien à trouver.
        Assert.Equal(TicketVerdict.UnknownOrConsumed, tickets.Redeem(fresh, out _));

        // Ticket vide et ticket inconnu ne se confondent pas.
        Assert.Equal(TicketVerdict.Empty, tickets.Redeem(string.Empty, out _));
        Assert.Equal(TicketVerdict.Empty, tickets.Redeem(null, out _));
        Assert.Equal(TicketVerdict.UnknownOrConsumed, tickets.Redeem("jamais-emis", out _));

        // Expiration : l'horloge INJECTÉE avance, rien d'autre ne change.
        string aging = tickets.Issue(accountId: 1, serverId: 290);
        now = TestSupport.Instant.AddMinutes(6);
        Assert.Equal(TicketVerdict.Expired, tickets.Redeem(aging, out _));

        // Et un ticket frais sous la MÊME horloge avancée reste accepté : le refus vient de
        // l'âge du ticket, pas de l'heure qu'il est. / The refusal comes from the ticket's age.
        string afterMove = tickets.Issue(accountId: 1, serverId: 290);
        Assert.Equal(TicketVerdict.Accepted, tickets.Redeem(afterMove, out _));
    }

    /// <summary>
    /// FR : un ticket vide présenté au serveur ferme la session avec un refus NOMMÉ, et n'émet
    ///      AUCUNE rafale. Une rafale servie sans ticket serait une porte ouverte.
    /// EN : an empty ticket closes the session with a NAMED refusal and emits NO burst.
    /// </summary>
    [Fact]
    public void UnTicketVide_FermeLaSessionSansRafale()
    {
        OpcodeTable table = TestSupport.Table();
        (ConnectionSession session, FrameLog log, _, _) = TestSupport.NewSession(table);

        IReadOnlyList<byte[]> outgoing =
            session.Receive(SequenceTests.TicketFrame(table, string.Empty));

        Assert.Empty(outgoing);
        Assert.True(session.ShouldClose);
        Assert.Contains(log.Refusals, r => r.Contains("Empty", StringComparison.Ordinal));
    }

    /// <summary>
    /// FR : un ticket rejoué est refusé avec un motif DIFFÉRENT de celui du ticket vide. Deux
    ///      refus qui se ressemblent ne se distinguent plus dans un journal.
    /// EN : a replayed ticket is refused with a reason DIFFERENT from the empty one.
    /// </summary>
    [Fact]
    public void UnTicketRejoue_EstRefusePourUnMotifDifferent()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);

        // Première présentation : acceptée (témoin POSITIF).
        (ConnectionSession first, FrameLog firstLog, _, _) = NewSession(table, tickets);
        Assert.NotEmpty(first.Receive(SequenceTests.TicketFrame(table, ticket)));
        Assert.Empty(firstLog.Refusals);

        // Seconde présentation du MÊME ticket : refusée, et nommément.
        (ConnectionSession second, FrameLog secondLog, _, _) = NewSession(table, tickets);
        Assert.Empty(second.Receive(SequenceTests.TicketFrame(table, ticket)));
        Assert.True(second.ShouldClose);
        Assert.Contains(secondLog.Refusals, r => r.Contains("UnknownOrConsumed", StringComparison.Ordinal));
    }

    /// <summary>
    /// FR : une sélection de personnage AVANT tout ticket est refusée. Sans ce garde, la liste
    ///      n'aurait servi à rien : n'importe qui devinant un identifiant entrerait en jeu.
    /// EN : a character selection BEFORE any ticket is refused.
    /// </summary>
    [Fact]
    public void UneSelectionAvantTicket_EstRefusee()
    {
        OpcodeTable table = TestSupport.Table();
        (ConnectionSession session, FrameLog log, _, _) = TestSupport.NewSession(table);

        IReadOnlyList<byte[]> outgoing = session.Receive(SequenceTests.SelectionFrame(table, 1));

        Assert.Empty(outgoing);
        Assert.True(session.ShouldClose);
        Assert.Contains(log.Refusals, r => r.Contains("ticket", StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>
    /// FR : un identifiant de personnage qui n'est pas celui servi est refusé — et la session
    ///      RESTE ouverte, parce qu'un client peut se tromper sans être un attaquant. Le témoin
    ///      positif est dans `SequenceTests` : le bon identifiant, lui, passe.
    /// EN : a character id that is not the served one is refused, and the session STAYS open.
    /// </summary>
    [Fact]
    public void UnMauvaisPersonnage_EstRefuseSansFermerLaSession()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);
        (ConnectionSession session, FrameLog log, _, _) = NewSession(table, tickets);

        session.Receive(SequenceTests.TicketFrame(table, ticket));
        ulong served = SequenceTests.ServedCharacterId(table);
        IReadOnlyList<byte[]> outgoing = session.Receive(SequenceTests.SelectionFrame(table, served + 1));

        Assert.Empty(outgoing);
        Assert.False(session.ShouldClose);
        Assert.Contains(log.Refusals, r => r.Contains("personnage", StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>
    /// FR : une trame TRONQUÉE n'est pas une erreur — c'est un segment TCP qui n'est pas fini. La
    ///      session doit rendre une liste VIDE et ATTENDRE, jamais lever, jamais refuser. Puis
    ///      les octets manquants doivent débloquer exactement la même réponse (témoin positif).
    /// EN : a TRUNCATED frame is not an error, it is an unfinished TCP segment. The session must
    ///      return an EMPTY list and WAIT; the missing bytes then unblock the same answer.
    /// </summary>
    [Fact]
    public void UneTrameTronquee_FaitAttendreSansLeverNiRefuser()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);
        (ConnectionSession session, FrameLog log, _, _) = NewSession(table, tickets);

        byte[] frame = SequenceTests.TicketFrame(table, ticket);
        int cut = frame.Length / 2;

        Assert.Empty(session.Receive(frame.AsSpan(0, cut)));
        Assert.Empty(log.Refusals);
        Assert.False(session.ShouldClose);

        // Le reste arrive : la rafale part, entière. / The rest arrives: the full burst goes out.
        Assert.Equal(15, TestSupport.DecodeGame(session.Receive(frame.AsSpan(cut))).Count);
    }

    /// <summary>
    /// FR : un opcode que la table ne lie pas est JOURNALISÉ puis IGNORÉ — pas de réponse, pas de
    ///      refus, pas de fermeture, pas d'exception. Le client en envoie que nous ne traitons
    ///      pas encore ; planter dessus perdrait la session pour un message décoratif.
    /// EN : an unbound opcode is LOGGED then IGNORED — no answer, no refusal, no close, no throw.
    /// </summary>
    [Fact]
    public void UnOpcodeInconnu_EstJournaliseEtIgnore()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);
        (ConnectionSession session, FrameLog log, _, _) = NewSession(table, tickets);
        session.Receive(SequenceTests.TicketFrame(table, ticket));

        // "zzz" n'est lié par aucune build : le forme est valide, le sens n'existe pas.
        // / "zzz" is bound by no build: the shape is valid, the meaning does not exist.
        IReadOnlyList<byte[]> outgoing =
            session.Receive(TestSupport.ClientGameFrame("zzz", new[] { TestSupport.Varint(1, 1) }));

        Assert.Empty(outgoing);
        Assert.False(session.ShouldClose);
        Assert.Empty(log.Refusals);
        Assert.Contains(log.Records, r => r.Opcode == "zzz" && r.Op == SemanticOp.None);
    }

    /// <summary>
    /// FR : dans une session DÉJÀ en phase de jeu, une trame dont les octets sont SABOTÉS est
    ///      refusée par un code NOMMÉ du codec, sans tuer la session ni répondre. Le témoin
    ///      positif est la trame intacte qui l'a précédée, et qui a déclenché la rafale.
    /// EN : inside a session ALREADY in the game phase, a SABOTAGED frame is refused with a
    ///      NAMED codec code, without killing the session or answering.
    /// </summary>
    [Fact]
    public void UneTrameSabotee_EstRefuseeNommementSansTuerLaSession()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);
        (ConnectionSession session, FrameLog log, _, _) = NewSession(table, tickets);

        // Témoin POSITIF : la trame intacte passe et déclenche la rafale ; la phase est décidée.
        // / Positive control: the intact frame passes and starts the burst; the phase is decided.
        Assert.NotEmpty(session.Receive(SequenceTests.TicketFrame(table, ticket)));
        Assert.Equal(SessionPhase.Game, session.Phase);
        Assert.Empty(log.Refusals);

        // Puis le sabotage, sur une trame de la MÊME session : un octet du typeUrl retourné.
        // / Then the sabotage, on a frame of the SAME session: one typeUrl byte flipped.
        byte[] sabotaged = SequenceTests.SelectionFrame(table, SequenceTests.ServedCharacterId(table));
        sabotaged[SabotageOffset] ^= 0xFF;

        Assert.Empty(session.Receive(sabotaged));
        Assert.NotEmpty(log.Refusals);
        Assert.False(session.ShouldClose);
    }

    /// <summary>
    /// FR : LIMITE MESURÉE, écrite comme un test pour qu'elle ne se perde pas. La phase est
    ///      décidée par le CONTENU de la première trame — la présence du préfixe de typeUrl. Une
    ///      PREMIÈRE trame de jeu dont le typeUrl est abîmé est donc INDISCERNABLE d'une trame de
    ///      connexion nue, et part dans la phase nue au lieu d'être refusée.
    ///      Ce n'est pas un défaut d'implémentation : c'est la propriété d'un critère de contenu,
    ///      et c'est précisément ce qu'écarterait la variante à deux ports (écouter la connexion
    ///      et le jeu ailleurs), qu'un seul paramètre d'annonce suffit à activer.
    ///      Conséquence pratique : si le vrai client se retrouve un jour à recevoir une liste de
    ///      serveurs alors qu'il présentait un ticket, c'est ICI qu'il faut regarder.
    /// EN : MEASURED LIMIT, written as a test so it is not lost. The phase is decided by the
    ///      FIRST frame's CONTENT, so a first game frame with a damaged typeUrl is
    ///      INDISTINGUISHABLE from a naked frame and is routed to the naked phase rather than
    ///      refused. Not an implementation defect: the property of a content criterion, and
    ///      exactly what the two-port variant would remove.
    /// </summary>
    [Fact]
    public void LimiteConnue_UnePremiereTrameAbimeeEstPriseePourUneTrameNue()
    {
        OpcodeTable table = TestSupport.Table();
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        string ticket = tickets.Issue(accountId: 1, serverId: 290);
        (ConnectionSession session, FrameLog log, _, _) = NewSession(table, tickets);

        byte[] sabotaged = SequenceTests.TicketFrame(table, ticket);
        sabotaged[SabotageOffset] ^= 0xFF;

        IReadOnlyList<byte[]> outgoing = session.Receive(sabotaged);

        // La phase part en NUE, et la réponse est celle de la phase nue — le comportement
        // documenté, pas celui qu'on aurait souhaité. / The documented behaviour, not the wished one.
        Assert.Equal(SessionPhase.Naked, session.Phase);
        Assert.Single(outgoing);
        Assert.Empty(log.Refusals);

        // Le ticket n'a PAS été consommé : le garde du ticket, lui, tient.
        // / The ticket was NOT consumed: the ticket guard itself holds.
        Assert.Equal(1, tickets.LiveCount);
    }

    /// <summary>
    /// FR : une table qui porte un type de champ inconnu REFUSE au chargement. Une faute de
    ///      frappe dans la table doit arrêter le démarrage, pas produire un message auquel il
    ///      manque un champ que personne ne remarquera à l'écran.
    /// EN : a table carrying an unknown field type REFUSES at load. A typo must stop start-up.
    /// </summary>
    [Fact]
    public void UneTableAvecUnTypeInconnu_RefuseAuChargement()
    {
        string path = Path.Combine(Path.GetTempPath(), $"binding-{Guid.NewGuid():N}.json");
        File.WriteAllText(path, """
        {
          "build": "0.0.0",
          "messages": [],
          "rafale_bienvenue": [],
          "charges": { "essai": [ { "n": 1, "t": "type_qui_nexiste_pas", "v": 1 } ] }
        }
        """);

        try
        {
            BindingException ex = Assert.Throws<BindingException>(() => OpcodeTable.Load(path));
            Assert.Contains("type_qui_nexiste_pas", ex.Message, StringComparison.Ordinal);
        }
        finally
        {
            File.Delete(path);
        }
    }

    /// <summary>
    /// FR : une forme qui réclame une injection que le serveur ne sait pas fournir REFUSE
    ///      nommément, au lieu d'émettre un message auquel il manque un champ.
    /// EN : a shape asking for an injection the server cannot provide REFUSES by name.
    /// </summary>
    [Fact]
    public void UneInjectionInconnue_RefuseNommement()
    {
        var spec = new FieldSpec
        {
            Number = 1,
            Kind = FieldKind.InjectedText,
            InjectionKey = "cle_qui_nexiste_pas",
        };

        PayloadException ex = Assert.Throws<PayloadException>(
            () => PayloadBuilder.Build(new[] { spec }, new TestSupport.NoInjections()));
        Assert.Contains("cle_qui_nexiste_pas", ex.Message, StringComparison.Ordinal);

        // Témoin POSITIF : la même forme, avec une clé que le serveur connaît, s'encode.
        // / Positive control: the same shape with a known key encodes.
        var known = new FieldSpec { Number = 1, Kind = FieldKind.InjectedText, InjectionKey = "hote" };
        var injections = new ServerInjections(new ServerOptions(), TestSupport.FrozenClock());
        Assert.NotEmpty(PayloadBuilder.Build(new[] { known }, injections));
    }

    /// <summary>
    /// FR : une trame nue dont la branche racine sort de 1..3 est refusée par un code nommé. Le
    ///      témoin positif est la branche 1, qui passe.
    /// EN : a naked frame whose root branch is outside 1..3 is refused with a named code.
    /// </summary>
    [Fact]
    public void UneBrancheNueHorsPlage_EstRefusee()
    {
        // Témoin POSITIF : la branche 1 se décode.
        var body = new List<byte>();
        ProtoWriter.WriteLengthDelimited(body, 1, new byte[] { 0x08, 0x01 });
        Assert.Equal(ConnectBranch.Auth, ConnectEnvelope.Decode(body.ToArray()).Branch);

        // Puis la branche 9, qui n'existe pas dans le `oneof` racine.
        var wrong = new List<byte>();
        ProtoWriter.WriteLengthDelimited(wrong, 9, new byte[] { 0x08, 0x01 });
        CodecException ex = Assert.Throws<CodecException>(() => ConnectEnvelope.Decode(wrong.ToArray()));
        Assert.Equal(CodecErrorCode.RootCaseMissing, ex.Code);
    }

    /// <summary>
    /// FR : le drapeau « ticket externe », éprouvé DANS LES DEUX SENS sur la même trame. Fermé
    ///      (le défaut), un ticket que nous n'avons pas émis est refusé et la session se ferme.
    ///      Ouvert, le même ticket passe et la rafale part. Sans les deux sens, on ne saurait pas
    ///      si le drapeau agit ou si le garde était déjà ouvert.
    ///      Un ticket VIDE reste refusé dans les DEUX cas : le drapeau desserre le garde, il ne
    ///      le supprime pas.
    /// EN : the "external ticket" flag, tested BOTH WAYS on the same frame. Closed (the default),
    ///      a ticket we did not issue is refused; open, the same ticket passes. An EMPTY ticket
    ///      stays refused in BOTH cases: the flag loosens the guard, it does not remove it.
    /// </summary>
    [Fact]
    public void LeDrapeauTicketExterne_EprouveDansLesDeuxSens()
    {
        OpcodeTable table = TestSupport.Table();
        byte[] frame = SequenceTests.TicketFrame(table, "jeton-venu-de-haapi");

        // FERMÉ (défaut) : refusé, session fermée.
        (ConnectionSession closed, FrameLog closedLog) = Session(table, accept: false);
        Assert.Empty(closed.Receive(frame));
        Assert.True(closed.ShouldClose);
        Assert.Contains(closedLog.Refusals, r => r.Contains("UnknownOrConsumed", StringComparison.Ordinal));

        // OUVERT : le MÊME ticket passe, et la rafale entière part.
        (ConnectionSession open, FrameLog openLog) = Session(table, accept: true);
        Assert.Equal(15, TestSupport.DecodeGame(open.Receive(frame)).Count);
        Assert.False(open.ShouldClose);
        Assert.Empty(openLog.Refusals);
        Assert.Contains(openLog.Records, _ => true);

        // OUVERT mais ticket VIDE : toujours refusé — le desserrage a une borne.
        (ConnectionSession empty, FrameLog emptyLog) = Session(table, accept: true);
        Assert.Empty(empty.Receive(SequenceTests.TicketFrame(table, string.Empty)));
        Assert.True(empty.ShouldClose);
        Assert.Contains(emptyLog.Refusals, r => r.Contains("Empty", StringComparison.Ordinal));
    }

    /// <summary>FR : une session avec ou sans le desserrage. / EN : a session with or without it.</summary>
    private static (ConnectionSession, FrameLog) Session(OpcodeTable table, bool accept)
    {
        var options = new ServerOptions { Verbose = false, AcceptExternalTicket = accept };
        var log = new FrameLog(new StringWriter(), verbose: false);
        var tickets = new TicketRegistry(
            TestSupport.FrozenClock(), TestSupport.CountingMint(), TimeSpan.FromMinutes(5));
        return (new ConnectionSession(table, options, log, tickets, TestSupport.FrozenClock()), log);
    }

    // L'octet saboté : le 8e, dans le typeUrl de la trame. Même position que l'épreuve de la
    // gate du codec, pour que les deux étages sabotent la même chose au même endroit.
    // / The sabotaged byte: the 8th, inside the frame's typeUrl — same spot as stage 2's gate.
    private const int SabotageOffset = 8;

    /// <summary>FR : une session sur un registre donné. / EN : a session on a given registry.</summary>
    private static (ConnectionSession, FrameLog, TicketRegistry, StringWriter)
        NewSession(OpcodeTable table, TicketRegistry tickets)
    {
        var output = new StringWriter();
        var log = new FrameLog(output, verbose: false);
        var session = new ConnectionSession(
            table, new ServerOptions { Verbose = false }, log, tickets, TestSupport.FrozenClock());
        return (session, log, tickets, output);
    }
}
