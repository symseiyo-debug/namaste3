// ============================================================================================
// QUOI : le scénario complet joué par un FAUX CLIENT, sans réseau — connexion nue → sélection de
//     serveur → ticket → rafale de bienvenue → sélection de personnage → carte.
// POURQUOI (05/09/2026) : c'est l'épreuve qui répond à l'objectif de la soirée. Elle vérifie
//     l'ORDRE, qui est le fait mesuré (`ConnectionProtocol.cs:191-221`) et pas une convenance :
//     la liste de personnages arrive à l'AVANT-DERNIER rang, et la marque de fin juste après —
//     son absence était le principal suspect d'un bouton « créer personnage » mort.
//     L'ordre attendu est TRANSCRIT ici en opcodes littéraux, exprès : c'est une seconde
//     transcription, indépendante de la table de liaison. Si la table était régénérée de
//     travers, comparer la table à elle-même rendrait vert — deux transcriptions du même fait
//     mesuré, non.
// EN : the full scenario played by a FAKE CLIENT, networkless. It checks the ORDER, which is the
//     measured fact. The expected order is transcribed here as literal opcodes on purpose: a
//     second, independent transcription, so the table is never compared to itself.
// COMMENT LANCER / USAGE : dotnet test --filter SequenceTests
// GATE : rc != 0 si l'ordre, le compte ou le contenu de la rafale changent.
// ============================================================================================

using Namaste3.Codec;
using Namaste3.Server.Connection;
using Xunit;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : le scénario, bout en bout.
/// EN : the end-to-end scenario.
/// </summary>
public sealed class SequenceTests
{
    // L'ordre EXACT de la rafale, transcrit de `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6 :
    // 15 émissions, 13 opcodes distincts, dont trois émissions du même opcode à la suite.
    // / The burst's EXACT order: 15 emissions, 13 distinct opcodes.
    private static readonly string[] ExpectedBurst =
    {
        "kra", "lqu", "hoy", "kqu", "mgq", "mgt", "hpd", "krs", "mgz",
        "kqp", "kqp", "kqp", "kvi", "kvd", "jtg",
    };

    /// <summary>
    /// FR : un faux client joue la phase NUE : il ouvre, reçoit l'accès accepté avec la liste des
    ///      serveurs, choisit un serveur, et reçoit son ticket.
    /// EN : a fake client plays the NAKED phase: opens, receives access + server list, picks a
    ///      server, receives its ticket.
    /// </summary>
    [Fact]
    public void PhaseNue_RendLaListeDeServeursPuisLeTicket()
    {
        (ConnectionSession session, FrameLog log, TicketRegistry tickets, _) = TestSupport.NewSession();

        IReadOnlyList<byte[]> first = session.Receive(TestSupport.NakedAuthFrame("fr", serverId: null));
        Assert.Equal(SessionPhase.Naked, session.Phase);
        Assert.Single(first);
        Assert.Equal(0, tickets.LiveCount);

        IReadOnlyList<byte[]> second = session.Receive(TestSupport.NakedAuthFrame("fr", serverId: 290));
        Assert.Single(second);
        Assert.Equal(1, tickets.LiveCount);
        Assert.Empty(log.Refusals);
    }

    /// <summary>
    /// FR : la première réponse porte bien une liste de serveurs NON VIDE. Un écran de sélection
    ///      vide et sans message est exactement ce que produit une liste bien formée mais creuse
    ///      — la forme ne suffit pas, il faut du contenu dedans.
    /// EN : the first answer carries a NON-EMPTY server list. A well-formed but hollow list is
    ///      exactly what produces an empty, message-less selection screen.
    /// </summary>
    [Fact]
    public void LAccesAccepte_PorteUnServeurEtUnPersonnage()
    {
        (ConnectionSession session, _, _, _) = TestSupport.NewSession();
        byte[] frame = Assert.Single(session.Receive(TestSupport.NakedAuthFrame("fr", null)));

        var reader = new FrameReader();
        reader.Append(frame);
        Assert.True(reader.TryReadFrame(out byte[] body, out _));
        ConnectMessage message = ConnectEnvelope.Decode(body);

        // f3 { f1 { f1 accountId, f2 nickname, f3 tag, f4 listeServeurs, f5 abonnement, f6 {} } }
        // Numéros VÉRIFIÉS : `mia`, protocolo_conexion_3.6.10.10.proto:232-242.
        ProtoField accepted = Assert.Single(message.Fields, f => f.Number == 3);
        IReadOnlyList<ProtoField> body2 = Assert.Single(accepted.Message!).Message!;

        Assert.Contains(body2, f => f.Number == 1);   // accountId
        Assert.Contains(body2, f => f.Number == 2);   // nickname
        ProtoField servers = Assert.Single(body2, f => f.Number == 4);

        // `miq` : f1 répété = les serveurs, f2 répété = les quotas. Au moins un de chaque.
        Assert.Contains(servers.Message!, f => f.Number == 1);
        Assert.Contains(servers.Message!, f => f.Number == 2);

        // Le serveur porte son résumé de personnage (`mit.f3`, `mjg`) — ce que l'écran affiche.
        ProtoField entry = servers.Message!.First(f => f.Number == 1);
        Assert.Contains(entry.Message!, f => f.Number == 1);   // miw { serverId, type }
        Assert.Contains(entry.Message!, f => f.Number == 3);   // mjg { nom, race, sexe, niveau }
    }

    /// <summary>
    /// FR : LE test de la soirée. Un faux client présente un ticket valide et doit recevoir les
    ///      15 messages de la rafale, dans l'ordre exact, avec 13 opcodes distincts.
    /// EN : THE test. A fake client presents a valid ticket and must receive the burst's 15
    ///      messages, in exact order, with 13 distinct opcodes.
    /// </summary>
    [Fact]
    public void UnTicketValide_DeclencheLaRafaleDansLOrdreExact()
    {
        OpcodeTable table = TestSupport.Table();
        string ticket = JouerPhaseNue(out ConnectionSession _, out TicketRegistry tickets);

        // Le client rouvre une connexion : phase JEU, et il présente son ticket.
        // / The client reopens a connection: GAME phase, and presents its ticket.
        (ConnectionSession game, FrameLog log, _, _) = NewGameSession(table, tickets);
        IReadOnlyList<byte[]> burst = game.Receive(TicketFrame(table, ticket));

        Assert.Equal(SessionPhase.Game, game.Phase);
        Assert.False(game.ShouldClose);
        Assert.Empty(log.Refusals);

        IReadOnlyList<RawMessage> decoded = TestSupport.DecodeGame(burst);
        Assert.Equal(ExpectedBurst, decoded.Select(m => m.Opcode.Name).ToArray());
        Assert.Equal(15, decoded.Count);
        Assert.Equal(13, decoded.Select(m => m.Opcode.Name).Distinct().Count());
        Assert.All(decoded, m => Assert.Equal(Direction.S2C, m.Direction));
        Assert.All(decoded, m => Assert.Equal(RootCase.Push, m.Case));
    }

    /// <summary>
    /// FR : les trois émissions du même opcode portent bien TROIS charges DIFFÉRENTES. Émettre
    ///      trois fois la même serait un vert de forme sur un fait faux — la source dit trois
    ///      charges distinctes, dans cet ordre.
    /// EN : the three emissions of one opcode carry THREE DIFFERENT payloads.
    /// </summary>
    [Fact]
    public void LOpcodeTripleDeLaRafale_PorteTroisChargesDifferentes()
    {
        OpcodeTable table = TestSupport.Table();
        string ticket = JouerPhaseNue(out _, out TicketRegistry tickets);
        (ConnectionSession game, _, _, _) = NewGameSession(table, tickets);

        IReadOnlyList<RawMessage> decoded =
            TestSupport.DecodeGame(game.Receive(TicketFrame(table, ticket)));

        string triple = table.OpcodeOf(SemanticOp.BurstCounterPair);
        byte[][] payloads = decoded.Where(m => m.Opcode.Name == triple)
                                   .Select(m => m.Payload)
                                   .ToArray();
        Assert.Equal(3, payloads.Length);
        Assert.Equal(3, payloads.Select(Convert.ToHexString).Distinct().Count());
        // La troisième est VIDE : c'est la forme mesurée, pas une charge oubliée.
        // / The third one is EMPTY: the measured shape, not a forgotten payload.
        Assert.Empty(payloads[2]);
    }

    /// <summary>
    /// FR : le scénario complet — ticket, rafale, sélection du personnage servi, puis entrée en
    ///      monde. Le bloc de carte ne part QU'UNE FOIS, même si les deux déclencheurs arrivent.
    /// EN : the full scenario. The map block goes out ONCE even when both triggers fire.
    /// </summary>
    [Fact]
    public void ScenarioComplet_DeLaSelectionALaCarte()
    {
        OpcodeTable table = TestSupport.Table();
        string ticket = JouerPhaseNue(out _, out TicketRegistry tickets);
        (ConnectionSession game, FrameLog log, _, _) = NewGameSession(table, tickets);

        game.Receive(TicketFrame(table, ticket));

        // La sélection : l'identifiant est celui que NOUS avons servi dans la liste.
        // / The selection: the id is the one WE served in the list.
        IReadOnlyList<RawMessage> selected = TestSupport.DecodeGame(
            game.Receive(SelectionFrame(table, ServedCharacterId(table))));
        RawMessage success = Assert.Single(selected);
        Assert.Equal(table.OpcodeOf(SemanticOp.CharacterSelectedSuccess), success.Opcode.Name);

        // Premier déclencheur du bloc de carte : la demande d'entrée en monde.
        // / First map-block trigger: the world-entry request.
        IReadOnlyList<RawMessage> mapBlock = TestSupport.DecodeGame(
            game.Receive(TestSupport.ClientGameFrame(
                table.OpcodeOf(SemanticOp.GameContextCreateRequest), Array.Empty<FieldSpec>())));
        Assert.Equal(
            new[] { table.OpcodeOf(SemanticOp.CurrentMap), table.OpcodeOf(SemanticOp.MapDiscovered) },
            mapBlock.Select(m => m.Opcode.Name).ToArray());

        // Second déclencheur (le battement) : il répond le pong, mais N'ÉMET PAS la carte une
        // seconde fois — l'envoyer deux fois fait boucler le rechargement du monde côté client.
        // / Second trigger (the heartbeat): pong yes, map NO — twice makes the client loop.
        IReadOnlyList<RawMessage> ping = TestSupport.DecodeGame(
            game.Receive(TestSupport.ClientGameFrame(
                table.OpcodeOf(SemanticOp.BasicPing), Array.Empty<FieldSpec>())));
        RawMessage pong = Assert.Single(ping);
        Assert.Equal(table.OpcodeOf(SemanticOp.BasicPong), pong.Opcode.Name);
        Assert.DoesNotContain(ping, m => m.Opcode.Name == table.OpcodeOf(SemanticOp.CurrentMap));

        Assert.Empty(log.Refusals);
    }

    /// <summary>
    /// FR : le battement SEUL suffit à libérer la carte quand la demande d'entrée n'est jamais
    ///      venue. C'est le filet documenté par la source ; il coûte de la latence, mais il évite
    ///      un client bloqué pour toujours.
    /// EN : the heartbeat ALONE releases the map when the world-entry request never came — the
    ///      documented fallback.
    /// </summary>
    [Fact]
    public void LeBattementSeul_LibereLaCarte()
    {
        OpcodeTable table = TestSupport.Table();
        string ticket = JouerPhaseNue(out _, out TicketRegistry tickets);
        (ConnectionSession game, _, _, _) = NewGameSession(table, tickets);

        game.Receive(TicketFrame(table, ticket));
        game.Receive(SelectionFrame(table, ServedCharacterId(table)));

        IReadOnlyList<RawMessage> answered = TestSupport.DecodeGame(
            game.Receive(TestSupport.ClientGameFrame(
                table.OpcodeOf(SemanticOp.BasicPing), Array.Empty<FieldSpec>())));

        Assert.Contains(answered, m => m.Opcode.Name == table.OpcodeOf(SemanticOp.BasicPong));
        Assert.Contains(answered, m => m.Opcode.Name == table.OpcodeOf(SemanticOp.CurrentMap));
    }

    /// <summary>
    /// FR : les octets arrivent en segments arbitraires — un par un. La session doit rendre
    ///      exactement la même chose : c'est le contrat du délimiteur de l'étage 2, ré-éprouvé
    ///      ici parce que c'est NOTRE boucle qui l'utilise.
    /// EN : bytes arrive one at a time; the session must yield exactly the same thing.
    /// </summary>
    [Fact]
    public void LaSessionSurvitAUneLivraisonOctetParOctet()
    {
        OpcodeTable table = TestSupport.Table();
        string ticket = JouerPhaseNue(out _, out TicketRegistry tickets);
        (ConnectionSession game, _, _, _) = NewGameSession(table, tickets);

        byte[] frame = TicketFrame(table, ticket);
        var collected = new List<byte[]>();
        foreach (byte b in frame)
        {
            collected.AddRange(game.Receive(new[] { b }));
        }

        Assert.Equal(ExpectedBurst, TestSupport.DecodeGame(collected).Select(m => m.Opcode.Name).ToArray());
    }

    // -------------------------------------------------------------------------------------
    // Montage du faux client. / The fake client's plumbing.
    // -------------------------------------------------------------------------------------

    /// <summary>
    /// FR : joue la phase nue et rend le ticket émis, en réutilisant le MÊME registre pour la
    ///      phase de jeu — c'est ce registre partagé qui fait le lien entre les deux connexions.
    /// EN : plays the naked phase and returns the issued ticket, reusing the SAME registry.
    /// </summary>
    private static string JouerPhaseNue(out ConnectionSession session, out TicketRegistry tickets)
    {
        Func<string> mint = TestSupport.CountingMint();
        tickets = new TicketRegistry(TestSupport.FrozenClock(), mint, TimeSpan.FromMinutes(5));
        var options = new ServerOptions { Verbose = false };
        var log = new FrameLog(new StringWriter(), verbose: false);
        session = new ConnectionSession(TestSupport.Table(), options, log, tickets, TestSupport.FrozenClock());

        session.Receive(TestSupport.NakedAuthFrame("fr", serverId: null));
        session.Receive(TestSupport.NakedAuthFrame("fr", serverId: 290));

        // Le premier ticket émis par la fabrique comptante. / The counting mint's first ticket.
        return "ticket-de-test-0001";
    }

    /// <summary>FR : une session de phase JEU sur le registre donné. / EN : a GAME session.</summary>
    private static (ConnectionSession, FrameLog, TicketRegistry, StringWriter)
        NewGameSession(OpcodeTable table, TicketRegistry tickets)
    {
        var output = new StringWriter();
        var log = new FrameLog(output, verbose: false);
        var session = new ConnectionSession(
            table, new ServerOptions { Verbose = false }, log, tickets, TestSupport.FrozenClock());
        return (session, log, tickets, output);
    }

    /// <summary>
    /// FR : la trame de présentation du ticket. Le ticket est en champ 2 (chaîne) — VÉRIFIÉ.
    /// EN : the ticket presentation frame. The ticket is field 2 (string) — VERIFIED.
    /// </summary>
    internal static byte[] TicketFrame(OpcodeTable table, string ticket)
        => TestSupport.ClientGameFrame(
            table.OpcodeOf(SemanticOp.AuthTicket), new[] { TestSupport.Text(2, ticket) });

    /// <summary>
    /// FR : la trame de sélection de personnage. L'identifiant est en champ 1 — VÉRIFIÉ.
    /// EN : the character selection frame. The id is field 1 — VERIFIED.
    /// </summary>
    internal static byte[] SelectionFrame(OpcodeTable table, ulong characterId)
        => TestSupport.ClientGameFrame(
            table.OpcodeOf(SemanticOp.CharacterSelection),
            new[] { TestSupport.Varint(1, characterId) });

    /// <summary>
    /// FR : l'identifiant du personnage que la table sert. Lu DANS la table, pas recopié : un
    ///      test qui réécrirait la valeur ne mesurerait plus l'accord entre les deux messages.
    /// EN : the served character's id, read FROM the table rather than restated.
    /// </summary>
    internal static ulong ServedCharacterId(OpcodeTable table)
    {
        IReadOnlyList<FieldSpec> payload = table.Payload("personnage_selectionne");
        FieldSpec entry = payload[0].Message[0];
        return entry.Message.First(f => f.Number == 2).Varint;
    }
}
