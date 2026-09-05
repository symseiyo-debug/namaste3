// ============================================================================================
// QUOI : la machine à états d'UNE connexion client — bascule de phase, phase NUE (sélection de
//     serveur → ticket), phase JEU (ticket → rafale de bienvenue → liste de personnages →
//     sélection → carte). Elle ne touche AUCUN socket : on lui donne des octets, elle rend les
//     trames à émettre. C'est ce qui permet au faux client des tests de jouer tout le scénario
//     sans réseau.
// POURQUOI (05/09/2026) : décision du projet — « faisons déjà un serveur qui marche », un seul
//     objectif mesurable : le client 3.6.10.10 se connecte et affiche un écran. La séquence est
//     TRANSCRITE de `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` (§3.2 à §5.2) et de
//     `COMPLEMENT-CHEMIN-CRITIQUE-G1.md`, jamais devinée ; chaque forme émise est recroisée
//     contre le dump de notre client. Aucune ligne de code n'est reprise d'un émulateur tiers.
// EN : ONE client connection's state machine — phase switch, NAKED phase, GAME phase. It touches
//     NO socket: give it bytes, it returns frames to emit, so tests can play the whole scenario.
// COMMENT LANCER / USAGE : `new ConnectionSession(table, options, log, tickets, horloge)` puis
//     `Receive(octets)` en boucle ; voir `TcpServer` pour le branchement réseau.
// GATE : `SequenceTests` (la rafale dans l'ordre), `RoundTripEmissionTests` (byte-exact),
//     `NegativeTests` (ticket vide/rejoué, trame tronquée, opcode inconnu).
// ============================================================================================

using Namaste3.Codec;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : la phase de la connexion. Elle est décidée par le CONTENU de la première trame, comme la
///      source le décrit — donc journalisée à chaque bascule, parce qu'un critère de contenu est
///      faillible et qu'on veut le voir se tromper plutôt que le deviner.
/// EN : the connection phase, decided by the FIRST frame's CONTENT, and logged at every switch.
/// </summary>
public enum SessionPhase
{
    /// <summary>Pas encore décidée. / Not decided yet.</summary>
    Undecided,
    /// <summary>Protocole de connexion nu. / Naked connection protocol.</summary>
    Naked,
    /// <summary>Protocole de jeu, enveloppe `type.ankama.com`. / Game protocol.</summary>
    Game,
}

/// <summary>
/// FR : une connexion. Un seul fil la pilote (le pump TCP), donc aucun verrou ici.
/// EN : one connection, driven by a single thread (the TCP pump), so no lock here.
/// </summary>
public sealed class ConnectionSession
{
    private readonly OpcodeTable _table;
    private readonly ServerOptions _options;
    private readonly FrameLog _log;
    private readonly TicketRegistry _tickets;
    private readonly ServerInjections _injections;
    private readonly Codec3 _codec = new();
    private readonly FrameReader _reader = new();

    private SessionPhase _phase = SessionPhase.Undecided;
    private bool _accessAnnounced;
    private bool _ticketAccepted;
    private bool _characterSelected;
    private bool _mapBlockSent;

    /// <summary>FR : construit la session. / EN : builds the session.</summary>
    public ConnectionSession(
        OpcodeTable table, ServerOptions options, FrameLog log,
        TicketRegistry tickets, Func<DateTimeOffset> clock)
    {
        _table = table ?? throw new ArgumentNullException(nameof(table));
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _log = log ?? throw new ArgumentNullException(nameof(log));
        _tickets = tickets ?? throw new ArgumentNullException(nameof(tickets));
        _injections = new ServerInjections(options, clock);
    }

    /// <summary>FR : la phase courante. / EN : the current phase.</summary>
    public SessionPhase Phase => _phase;

    /// <summary>
    /// FR : vrai quand la session doit être fermée — ticket refusé. Le pump ferme APRÈS avoir
    ///      émis ce qu'il reste, jamais au milieu d'une trame.
    /// EN : true when the session must be closed (ticket refused). The pump closes AFTER
    ///      flushing, never mid-frame.
    /// </summary>
    public bool ShouldClose { get; private set; }

    /// <summary>
    /// FR : avale un segment TCP arbitraire et rend les trames à émettre, dans l'ordre. Un
    ///      segment qui ne complète aucune trame rend une liste VIDE — c'est la seule condition
    ///      d'arrêt normale, et elle ne lève jamais.
    /// EN : swallows an arbitrary TCP segment and returns the frames to emit, in order. A segment
    ///      completing no frame returns an EMPTY list — the only normal stop condition.
    /// </summary>
    public IReadOnlyList<byte[]> Receive(ReadOnlySpan<byte> segment)
    {
        var outgoing = new List<byte[]>();
        _reader.Append(segment);

        while (_reader.TryReadFrame(out byte[] frame, out long offset))
        {
            DecidePhase(frame);
            if (_phase == SessionPhase.Naked)
            {
                HandleNaked(frame, offset, outgoing);
            }
            else
            {
                HandleGame(frame, offset, outgoing);
            }
        }

        return outgoing;
    }

    /// <summary>
    /// FR : décide la phase à la PREMIÈRE trame, par la présence du préfixe de typeUrl. C'est le
    ///      critère de la source (§3.2) ; il est journalisé pour qu'on le voie à l'œuvre.
    /// EN : decides the phase on the FIRST frame, by the typeUrl prefix — the source's criterion.
    /// </summary>
    private void DecidePhase(ReadOnlySpan<byte> frame)
    {
        if (_phase != SessionPhase.Undecided)
        {
            return;
        }

        _phase = GameEnvelope.LooksLikeGameFrame(frame) ? SessionPhase.Game : SessionPhase.Naked;
        _log.Note($"phase décidée sur la 1re trame / phase decided on 1st frame: {_phase}");
    }

    // ---------------------------------------------------------------------------------------
    // PHASE NUE — sélection de serveur puis délivrance du ticket.
    // ---------------------------------------------------------------------------------------

    /// <summary>
    /// FR : traite une trame nue. Deux réponses possibles, dans cet ordre : d'abord « accès
    ///      accepté + liste des serveurs » (c'est ce message qui PEUPLE l'écran de sélection de
    ///      serveur), puis, dès qu'une trame porte un identifiant de serveur, « serveur
    ///      sélectionné » avec le ticket, l'hôte et les ports.
    ///      ⚠️ La place exacte du premier message dans la séquence Ankama RÉELLE est DÉDUITE :
    ///      la source l'envoie en réponse au premier frame nu et note elle-même que ce peut être
    ///      une simplification. Le journal imprime la branche et l'identifiant de chaque trame
    ///      nue reçue — c'est ainsi qu'on verra ce que le vrai client fait, au lieu de le
    ///      supposer.
    /// EN : handles a naked frame. First "access accepted + server list" (this is what POPULATES
    ///      the server-selection screen), then "server selected" with ticket/host/ports as soon
    ///      as a frame carries a server id. The first message's exact place is DEDUCED; the
    ///      journal prints every naked frame so we observe rather than assume.
    /// </summary>
    private void HandleNaked(ReadOnlySpan<byte> frame, long offset, List<byte[]> outgoing)
    {
        ConnectMessage message;
        try
        {
            message = ConnectEnvelope.Decode(frame, offset);
        }
        catch (CodecException ex)
        {
            _log.Refusal($"trame nue illisible / unreadable naked frame: {ex.Code} @{ex.Offset}");
            return;
        }

        _log.Connect(FrameFlow.In, message.Branch, frame.Length, message.Fields);
        if (message.Language is { Length: > 0 } lang)
        {
            _log.Note($"langue annoncée par le client / client language: {lang}");
        }

        if (!_accessAnnounced)
        {
            _accessAnnounced = true;
            Emit(outgoing, PayloadAccessAccepted);
            return;
        }

        long? serverId = message.SelectedServerId;
        if (serverId is null)
        {
            _log.Note("trame nue sans identifiant de serveur / naked frame without a server id");
            return;
        }

        _injections.Ticket = _tickets.Issue(AccountId, serverId.Value);
        _log.Note($"serveur choisi / server chosen: {serverId.Value} ; ticket émis / ticket issued");
        Emit(outgoing, PayloadServerSelected);
    }

    /// <summary>FR : émet une charge nommée de la table. / EN : emits a named table payload.</summary>
    private void Emit(List<byte[]> outgoing, string payloadName)
    {
        byte[] wire = ConnectEnvelope.Frame(_table.Payload(payloadName), _injections);
        outgoing.Add(wire);
        _log.Connect(FrameFlow.Out, ConnectBranch.AuthResult, wire.Length);
    }

    // ---------------------------------------------------------------------------------------
    // PHASE JEU — ticket, rafale, liste, sélection, carte.
    // ---------------------------------------------------------------------------------------

    /// <summary>
    /// FR : traite une trame de jeu. Un opcode que la table ne lie pas est JOURNALISÉ puis
    ///      IGNORÉ : le client en envoie que nous ne traitons pas encore, et planter dessus
    ///      ferait perdre la session entière pour un message décoratif.
    /// EN : handles a game frame. An unbound opcode is LOGGED then IGNORED: crashing on a
    ///      decorative message would lose the whole session.
    /// </summary>
    private void HandleGame(ReadOnlySpan<byte> frame, long offset, List<byte[]> outgoing)
    {
        RawMessage message;
        try
        {
            message = _codec.DecodeFrame(frame, offset, new ProtoStats());
        }
        catch (CodecException ex)
        {
            _log.Refusal($"trame de jeu illisible / unreadable game frame: {ex.Code} @{ex.Offset}");
            return;
        }

        bool bound = _table.TryResolve(message.Opcode.Name, out SemanticOp op);
        _log.Game(FrameFlow.In, message.Opcode.Name, bound ? op : SemanticOp.None,
                  frame.Length, message.Fields, message.RequestId);
        if (!bound)
        {
            return;
        }

        switch (op)
        {
            case SemanticOp.AuthTicket:
                OnTicket(message, outgoing);
                break;

            case SemanticOp.AuthTicketCompanion:
                // Accompagne le ticket et n'attend RIEN en retour — sens inconnu de nos sources,
                // et l'admettre coûte moins cher que d'inventer une réponse.
                // / Comes with the ticket and expects NOTHING back; the meaning is unknown.
                _log.Note("compagnon du ticket reçu, aucune réponse / ticket companion, no answer");
                break;

            case SemanticOp.CharacterSelection:
                OnCharacterSelection(message, ReadVarint(message.Fields, SelectionIdField), outgoing);
                break;

            case SemanticOp.CharacterFirstSelection:
                // L'id est en champ 2, PAS en champ 1 : le champ 1 est un booléen. Divergence
                // trouvée et écrite par l'étage 1 ; la suivre est le seul moyen de ne pas lire
                // un drapeau à la place d'un identifiant.
                // / The id is in field 2, NOT 1: field 1 is a bool.
                OnCharacterSelection(message, ReadVarint(message.Fields, FirstSelectionIdField), outgoing);
                break;

            case SemanticOp.GameContextCreateRequest:
                SendMapBlockOnce(outgoing, "bloc d'identité digéré / identity block digested");
                break;

            case SemanticOp.BasicPing:
                Push(outgoing, SemanticOp.BasicPong, _table.Payload(PayloadPong));
                // Filet de sécurité décrit par la source : si la demande d'entrée en monde n'est
                // jamais venue, le PREMIER battement déclenche quand même la carte. Coût mesuré
                // par la source : 4,8 s de latence — un filet, pas le chemin normal.
                // / Documented fallback: the FIRST heartbeat also releases the map block.
                SendMapBlockOnce(outgoing, "filet du 1er battement / first-heartbeat fallback");
                break;

            case SemanticOp.WorldEntryRequests:
                // Sans « carte chargée », le client ne considère jamais la carte comme prête.
                // / Without "map loaded", the client never considers the map ready.
                Push(outgoing, SemanticOp.MapLoaded, _table.Payload(PayloadMapReady));
                break;

            default:
                _log.Note($"opcode lié mais non traité à ce stade / bound but unhandled: {op}");
                break;
        }
    }

    /// <summary>
    /// FR : le ticket. Un refus est NOMMÉ et la connexion se ferme — un ticket rejoué ou périmé
    ///      ne doit jamais ouvrir une session, et un refus muet ferait passer un défaut de
    ///      sécurité pour un bug réseau.
    /// EN : the ticket. A refusal is NAMED and closes the connection.
    /// </summary>
    private void OnTicket(RawMessage message, List<byte[]> outgoing)
    {
        string? ticket = ReadText(message.Fields, TicketField);
        TicketVerdict verdict = _tickets.Redeem(ticket, out TicketGrant? grant);

        // Repli EXPLICITE pour la première mise en route face au client vivant : un ticket que
        // nous n'avons pas émis (il vient de la chaîne HAAPI/Zaap) est accepté SI et SEULEMENT
        // SI le drapeau est ouvert, et il est journalisé comme tel. Fermé, le garde reste entier.
        // / EXPLICIT fallback for first bring-up: a ticket we did not issue is accepted only when
        // the flag is open, and it is logged as such. Closed, the guard stays whole.
        if (verdict == TicketVerdict.UnknownOrConsumed
            && _options.AcceptExternalTicket
            && !string.IsNullOrEmpty(ticket))
        {
            _log.Note($"ticket EXTERNE accepté (garde desserré) / EXTERNAL ticket accepted: {ticket}");
            grant = new TicketGrant(AccountId, ExternalServerId, DateTimeOffset.MinValue);
            verdict = TicketVerdict.Accepted;
        }

        if (verdict != TicketVerdict.Accepted || grant is null)
        {
            ShouldClose = true;
            _log.Refusal($"ticket refusé / ticket refused: {verdict}");
            return;
        }

        _ticketAccepted = true;
        _log.Note($"ticket accepté / ticket accepted: compte {grant.AccountId}, serveur {grant.ServerId}");
        SendWelcomeBurst(outgoing);
    }

    /// <summary>
    /// FR : la rafale de bienvenue — QUINZE émissions, TREIZE opcodes distincts, dans l'ordre
    ///      EXACT de la table. L'ordre est le fait mesuré ; le code ne le reconstruit pas, il le
    ///      déroule.
    /// EN : the welcome burst — FIFTEEN emissions, THIRTEEN distinct opcodes, in the table's
    ///      EXACT order. The order is the measured fact; the code unrolls it, never rebuilds it.
    /// </summary>
    private void SendWelcomeBurst(List<byte[]> outgoing)
    {
        foreach (BurstStep step in _table.WelcomeBurst)
        {
            Push(outgoing, step.Op, step.Payload);
        }

        _log.Note($"rafale émise / burst emitted: {_table.WelcomeBurst.Count} messages");
    }

    /// <summary>
    /// FR : la sélection de personnage. L'identifiant reçu est vérifié contre celui que NOUS
    ///      avons servi : le client n'est pas une source fiable sur ce point, et accepter le
    ///      sien laisserait choisir le personnage d'un autre compte.
    /// EN : character selection. The received id is checked against the one WE served: the
    ///      client is not a trustworthy source here.
    /// </summary>
    private void OnCharacterSelection(RawMessage message, ulong? requested, List<byte[]> outgoing)
    {
        if (!_ticketAccepted)
        {
            ShouldClose = true;
            _log.Refusal("sélection avant ticket accepté / selection before an accepted ticket");
            return;
        }

        ulong served = ServedCharacterId();
        if (requested is null || requested.Value != served)
        {
            _log.Refusal(
                $"personnage refusé / character refused: demandé {requested?.ToString() ?? "aucun"}, " +
                $"servi {served}");
            return;
        }

        _characterSelected = true;
        Push(outgoing, SemanticOp.CharacterSelectedSuccess,
             _table.Payload(PayloadCharacterSelected), message.RequestId);
        _log.Note("personnage accepté / character accepted");
    }

    /// <summary>
    /// FR : le bloc de carte, UNE SEULE FOIS par entrée en monde. L'envoyer deux fois fait
    ///      boucler le rechargement du monde côté client — c'est une panne mesurée, pas une
    ///      précaution de principe, d'où le garde plutôt qu'un commentaire.
    /// EN : the map block, ONCE per world entry. Sending it twice makes the client loop reloading
    ///      the world — a measured failure, hence a guard rather than a comment.
    /// </summary>
    private void SendMapBlockOnce(List<byte[]> outgoing, string trigger)
    {
        if (!_characterSelected)
        {
            _log.Note("bloc de carte retenu : aucun personnage sélectionné / map block withheld");
            return;
        }

        if (_mapBlockSent)
        {
            _log.Note($"bloc de carte déjà émis, ignoré / map block already sent, ignored ({trigger})");
            return;
        }

        _mapBlockSent = true;
        _log.Note($"bloc de carte, déclencheur / map block, trigger: {trigger}");
        Push(outgoing, SemanticOp.CurrentMap, _table.Payload(PayloadCurrentMap));
        Push(outgoing, SemanticOp.MapDiscovered, _table.Payload(PayloadMapDiscovered));
    }

    /// <summary>
    /// FR : émet un message de jeu. Par défaut sur le cas racine 1 (push) ; si le client avait
    ///      posé une requête, on répond sur le cas 3 en RÉINJECTANT son identifiant tel quel —
    ///      jamais codé en dur, même si la source mesure -1 dans 98,9 % des cas.
    /// EN : emits a game message, root case 1 (push) by default; on case 3 with the request id
    ///      echoed AS IS when the client asked a question — never hard-coded.
    /// </summary>
    private void Push(List<byte[]> outgoing, SemanticOp op,
                      IReadOnlyList<FieldSpec> payload, long? requestId = null)
    {
        string opcode = _table.OpcodeOf(op);
        byte[] body = PayloadBuilder.Build(payload, _injections);
        RootCase rootCase = requestId.HasValue ? RootCase.Answer : RootCase.Push;
        byte[] wire = GameEnvelope.Frame(opcode, body, rootCase, requestId);
        outgoing.Add(wire);
        _log.Game(FrameFlow.Out, opcode, op, wire.Length, requestId: requestId);
    }

    /// <summary>FR : l'identifiant du personnage servi. / EN : the served character's id.</summary>
    private ulong ServedCharacterId()
    {
        // Il vit dans la table, pas dans le code : c'est la même donnée que celle envoyée dans la
        // liste, donc elle ne peut pas diverger. / It lives in the table, so it cannot diverge.
        IReadOnlyList<FieldSpec> entry = _table.Payload(PayloadCharacterSelected);
        FieldSpec? wrapper = entry.FirstOrDefault();
        FieldSpec? inner = wrapper?.Message.FirstOrDefault();
        FieldSpec? id = inner?.Message.FirstOrDefault(f => f.Number == SelectedIdField);
        return id?.Varint ?? 0;
    }

    /// <summary>FR : lit un varint à un numéro donné. / EN : reads a varint at a given number.</summary>
    private static ulong? ReadVarint(IReadOnlyList<ProtoField> fields, int number)
    {
        foreach (ProtoField field in fields)
        {
            if (field.Number == number && field.WireType == ProtoWireType.Varint)
            {
                return field.VarintValue;
            }
        }

        return null;
    }

    /// <summary>FR : lit une chaîne à un numéro donné. / EN : reads a string at a given number.</summary>
    private static string? ReadText(IReadOnlyList<ProtoField> fields, int number)
    {
        foreach (ProtoField field in fields)
        {
            if (field.Number == number && field.WireType == ProtoWireType.LengthDelimited)
            {
                return System.Text.Encoding.UTF8.GetString(field.Bytes);
            }
        }

        return null;
    }

    // Numéros de champ VÉRIFIÉS dans le dump de notre client, chacun avec sa ligne.
    // / Field numbers VERIFIED in our client's dump, each with its line.
    private const int TicketField = 2;             // kqz.f2 string,  il2cpp.cs:991823
    private const int SelectionIdField = 1;        // kvw.f1 int64,   il2cpp.cs:1000115
    private const int FirstSelectionIdField = 2;   // kvl.f2 int64,   il2cpp.cs:999385
    private const int SelectedIdField = 2;         // lpg.f2 int64,   il2cpp.cs:1029268

    // L'identifiant de compte servi. Une seule valeur ce soir : le serveur ne gère pas encore de
    // comptes, et l'inventer explicitement vaut mieux qu'un zéro qui aurait l'air d'un défaut.
    // / The served account id. One value tonight; inventing it openly beats a zero that would
    // look like a bug.
    private const long AccountId = 1;

    // Le serveur attribué à un ticket EXTERNE : celui que notre liste annonce. Il n'y en a qu'un
    // ce soir, donc il n'y a rien à choisir — mais l'écrire évite un zéro qui ressemblerait à
    // une valeur oubliée. / The server given to an EXTERNAL ticket: the only one we announce.
    private const long ExternalServerId = 290;

    // Les charges nommées de la table. Ce sont des CLÉS, pas des opcodes.
    // / The table's named payloads. These are KEYS, not opcodes.
    private const string PayloadAccessAccepted = "acces_accepte";
    private const string PayloadServerSelected = "serveur_selectionne";
    private const string PayloadCharacterSelected = "personnage_selectionne";
    private const string PayloadCurrentMap = "carte_courante";
    private const string PayloadMapDiscovered = "carte_decouverte";
    private const string PayloadMapReady = "carte_prete";
    private const string PayloadPong = "pong";
}
