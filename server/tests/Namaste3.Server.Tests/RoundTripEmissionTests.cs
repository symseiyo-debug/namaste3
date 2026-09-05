// ============================================================================================
// QUOI : le round-trip de CE QUE NOUS ÉMETTONS — chaque message produit par le serveur est
//     re-décodé par le codec de l'étage 2, puis ré-encodé, et doit rendre EXACTEMENT les mêmes
//     octets.
// POURQUOI (05/09/2026) : l'étage 2 prouve qu'on sait LIRE le client ; rien ne prouvait encore
//     qu'on sache ÉCRIRE quelque chose qu'il saurait lire. Ce test ferme cet écart. Il porte
//     aussi son propre garde-fou : un round-trip qui recopierait ses octets d'entrée rendrait le
//     même vert, donc on n'affirme pas seulement l'égalité — on vérifie que l'opcode, le sens et
//     l'arbre des champs RESSORTENT, c'est-à-dire que la trame a bien été COMPRISE et non
//     seulement recopiée.
//     ⚠️ Ce qu'il ne prouve PAS, et qui doit rester dit : la fidélité au format ne dit rien de
//     l'ACCEPTABILITÉ par un client vivant. Cette preuve-là est une gate d'écran, pas une gate
//     de test.
// EN : the round-trip of WHAT WE EMIT. Stage 2 proved we can READ the client; nothing yet proved
//     we can WRITE something it could read. A byte-copy would yield the same green, so we also
//     check the opcode, direction and field tree come back out — i.e. the frame was UNDERSTOOD.
//     It does NOT prove a live client ACCEPTS it; that is a screen gate, not a test gate.
// COMMENT LANCER / USAGE : dotnet test --filter RoundTripEmissionTests
// GATE : rc != 0 si une seule trame émise ne se re-décode pas en elle-même.
// ============================================================================================

using Namaste3.Codec;
using Namaste3.Server.Connection;
using Xunit;

namespace Namaste3.Server.Tests;

/// <summary>
/// FR : les épreuves d'émission.
/// EN : the emission checks.
/// </summary>
public sealed class RoundTripEmissionTests
{
    /// <summary>
    /// FR : chaque étape de la rafale s'émet, se décode et se ré-encode à l'identique — et son
    ///      opcode décodé est bien celui que la table annonce pour ce nom sémantique.
    /// EN : every burst step emits, decodes and re-encodes identically — and its decoded opcode
    ///      is the one the table announces for that semantic name.
    /// </summary>
    [Fact]
    public void ChaqueEtapeDeLaRafale_SeRedecodeEnElleMeme()
    {
        OpcodeTable table = TestSupport.Table();
        var injections = new ServerInjections(new ServerOptions(), TestSupport.FrozenClock());
        var codec = new Codec3();

        foreach (BurstStep step in table.WelcomeBurst)
        {
            string opcode = table.OpcodeOf(step.Op);
            byte[] payload = PayloadBuilder.Build(step.Payload, injections);
            byte[] frame = GameEnvelope.Frame(opcode, payload, RootCase.Push);

            DecodeResult decoded = codec.Decode(frame);
            RawMessage message = Assert.Single(decoded.Messages);

            Assert.Equal(opcode, message.Opcode.Name);
            Assert.True(message.Opcode.IsCanonical, $"opcode non canonique / non-canonical: {opcode}");
            Assert.Equal(Direction.S2C, message.Direction);
            Assert.Equal(RootCase.Push, message.Case);
            Assert.Equal(payload, message.Payload);
            Assert.Equal(frame, codec.Encode(decoded.Messages));
        }
    }

    /// <summary>
    /// FR : une charge VIDE ne produit PAS un champ 2 présent-et-vide dans l'`Any`. C'est la
    ///      règle mesurée sur la plus petite trame serveur connue (26 octets), et un serveur qui
    ///      l'ignorerait émettrait des octets qu'aucune capture réelle ne montre.
    /// EN : an EMPTY payload does NOT produce a present-but-empty field 2 in the Any — the rule
    ///      measured on the smallest known server frame (26 bytes).
    /// </summary>
    [Fact]
    public void UneChargeVide_NEmetPasDeChampDeCharge()
    {
        OpcodeTable table = TestSupport.Table();
        BurstStep empty = table.WelcomeBurst.First(s => s.Payload.Count == 0);
        string opcode = table.OpcodeOf(empty.Op);

        byte[] frame = GameEnvelope.Frame(opcode, ReadOnlySpan<byte>.Empty, RootCase.Push);

        // 26 octets = 1 (longueur) + 25. C'est le compte de la trame minimale mesurée.
        // / 26 bytes = 1 (length) + 25, the measured minimal frame's count.
        Assert.Equal(26, frame.Length);

        RawMessage message = Assert.Single(new Codec3().Decode(frame).Messages);
        Assert.Empty(message.Payload);
        // Le champ 2 de l'`Any` est ABSENT, pas vide : l'`Any` ne porte qu'un seul champ.
        // / The Any's field 2 is ABSENT, not empty: the Any carries a single field.
        ProtoField only = Assert.Single(message.Envelope.AnyFields);
        Assert.Equal(Envelope.AnyTypeUrlField, only.Number);
    }

    /// <summary>
    /// FR : une réponse voyage sur le cas racine 3 et RÉINJECTE l'identifiant de requête tel
    ///      quel, y compris une valeur négative. Le codé en dur à -1 serait faux pour 1,1 % des
    ///      requêtes mesurées — assez pour bloquer un joueur sur un bord de carte.
    /// EN : an answer travels on root case 3 and echoes the request id AS IS, negatives included.
    /// </summary>
    [Theory]
    [InlineData(-1L)]
    [InlineData(0L)]
    [InlineData(7L)]
    [InlineData(2147483647L)]
    public void UneReponse_ReinjecteLIdentifiantDeRequete(long requestId)
    {
        OpcodeTable table = TestSupport.Table();
        string opcode = table.OpcodeOf(SemanticOp.MapLoaded);

        byte[] frame = GameEnvelope.Frame(
            opcode, ReadOnlySpan<byte>.Empty, RootCase.Answer, requestId);

        RawMessage message = Assert.Single(new Codec3().Decode(frame).Messages);
        Assert.Equal(RootCase.Answer, message.Case);
        Assert.Equal(Direction.S2C, message.Direction);
        Assert.Equal(requestId, message.RequestId);
    }

    /// <summary>
    /// FR : toutes les charges NOMMÉES de la table s'encodent et se re-décodent. Elles ne passent
    ///      pas toutes par la rafale (la carte, le pong, le personnage sélectionné arrivent plus
    ///      tard) — les laisser hors de l'épreuve laisserait un angle mort exactement là où le
    ///      client s'arrête aujourd'hui.
    /// EN : every NAMED table payload encodes and decodes. Not all go through the burst, and
    ///      leaving them out would blind us exactly where the client stops today.
    /// </summary>
    [Theory]
    [InlineData("carte_courante", SemanticOp.CurrentMap)]
    [InlineData("carte_decouverte", SemanticOp.MapDiscovered)]
    [InlineData("carte_prete", SemanticOp.MapLoaded)]
    [InlineData("pong", SemanticOp.BasicPong)]
    [InlineData("personnage_selectionne", SemanticOp.CharacterSelectedSuccess)]
    public void ChaqueChargeNommee_SeRedecodeEnElleMeme(string payloadName, SemanticOp op)
    {
        OpcodeTable table = TestSupport.Table();
        var injections = new ServerInjections(new ServerOptions(), TestSupport.FrozenClock());
        var codec = new Codec3();

        string opcode = table.OpcodeOf(op);
        byte[] payload = PayloadBuilder.Build(table.Payload(payloadName), injections);
        byte[] frame = GameEnvelope.Frame(opcode, payload, RootCase.Push);

        DecodeResult decoded = codec.Decode(frame);
        RawMessage message = Assert.Single(decoded.Messages);
        Assert.Equal(opcode, message.Opcode.Name);
        Assert.Equal(payload, message.Payload);
        Assert.Equal(frame, codec.Encode(decoded.Messages));
    }

    /// <summary>
    /// FR : la carte servie est bien celle qu'on annonce — le zaap d'Astrub, 191105026. Un
    ///      identifiant de carte faux passerait toutes les gates de forme et ne se verrait qu'à
    ///      l'écran, sur une carte vide.
    /// EN : the served map really is the announced one, 191105026. A wrong map id would pass
    ///      every shape gate and only show up on screen, as an empty map.
    /// </summary>
    [Fact]
    public void LaCarteServie_EstCelleDuZaapDAstrub()
    {
        OpcodeTable table = TestSupport.Table();
        var injections = new ServerInjections(new ServerOptions(), TestSupport.FrozenClock());
        byte[] payload = PayloadBuilder.Build(table.Payload("carte_courante"), injections);

        var stats = new ProtoStats();
        IReadOnlyList<ProtoField> fields = ProtoReader.ReadMessage(payload, 0, stats);
        ProtoField mapId = Assert.Single(fields, f => f.Number == 2);
        Assert.Equal(ProtoWireType.Varint, mapId.WireType);
        Assert.Equal(191105026UL, mapId.VarintValue);
    }

    /// <summary>
    /// FR : la réponse « serveur sélectionné » de la phase NUE porte le ticket, l'hôte et les
    ///      ports que la configuration ANNONCE — et non le port sur lequel on écoute, qui peut
    ///      être différent. Confondre les deux enverrait le client dans le vide.
    /// EN : the NAKED phase's "server selected" carries the ANNOUNCED host and ports, not the
    ///      listen port, which may differ. Confusing the two would send the client nowhere.
    /// </summary>
    [Fact]
    public void ServeurSelectionne_PorteLeTicketEtLesPortsAnnonces()
    {
        OpcodeTable table = TestSupport.Table();
        var options = new ServerOptions
        {
            ListenPort = 1,                                  // volontairement différent
            AnnouncedHost = "10.0.0.7",
            AnnouncedPorts = new[] { 5556, 5557 },
        };
        var injections = new ServerInjections(options, TestSupport.FrozenClock())
        {
            Ticket = "ticket-de-test-0001",
        };

        byte[] frame = ConnectEnvelope.Frame(table.Payload("serveur_selectionne"), injections);
        // On retire le préfixe de longueur pour relire la racine. / Strip the length prefix.
        var reader = new FrameReader();
        reader.Append(frame);
        Assert.True(reader.TryReadFrame(out byte[] body, out _));

        ConnectMessage message = ConnectEnvelope.Decode(body);
        Assert.Equal(ConnectBranch.AuthResult, message.Branch);

        // f4 { f1 { f1 ticket, f2 hôte, f3 ports } } — numéros VÉRIFIÉS (mik, proto:259-263).
        ProtoField selected = Assert.Single(message.Fields, f => f.Number == 4);
        ProtoField inner = Assert.Single(selected.Message!);
        IReadOnlyList<ProtoField> parts = inner.Message!;

        Assert.Equal("ticket-de-test-0001",
            System.Text.Encoding.UTF8.GetString(parts.First(f => f.Number == 1).Bytes));
        Assert.Equal("10.0.0.7",
            System.Text.Encoding.UTF8.GetString(parts.First(f => f.Number == 2).Bytes));

        // Les ports sont EMPAQUETÉS : deux varints à la suite dans un seul champ.
        // / The ports are PACKED: two consecutive varints in a single field.
        byte[] ports = parts.First(f => f.Number == 3).Bytes;
        int position = 0;
        Assert.Equal(5556UL, Varint.Read(ports, ref position));
        Assert.Equal(5557UL, Varint.Read(ports, ref position));
        Assert.Equal(ports.Length, position);
    }
}
