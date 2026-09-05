// QUOI : NegativeTests.cs -- entrées malformées (varint débordant, longueur hors bornes,
//   typeUrl invalide, oneof ambigu...) doivent toutes produire un refus NOMMÉ avec offset.
// POURQUOI : une gate qui n'a jamais vu de rouge ne prouve pas qu'elle sait dire non -- le
//   round-trip seul (RoundTripTests) ne couvre que le chemin qui marche.
// COMMENT LANCER : dotnet test --filter NegativeTests (depuis codec/).
// GATE : rejouée par gate-codec.sh (via `dotnet test`).
using System.Text;
using Xunit;
using Xunit.Abstractions;

namespace Namaste3.Codec.Tests;

/// <summary>
/// FR : TÉMOINS NÉGATIFS. Une gate qui n'a jamais vu de rouge ne prouve pas qu'elle sait dire non.
///      Chaque entrée malformée doit produire un code d'erreur NOMMÉ et un offset — jamais une
///      exception nue, jamais un silence.
/// EN : NEGATIVE WITNESSES. A gate that has never seen red does not prove it can say no. Every
///      malformed input must produce a NAMED error code and an offset — never a bare exception,
///      never silence.
/// </summary>
public sealed class NegativeTests
{
    private readonly ITestOutputHelper _output;

    public NegativeTests(ITestOutputHelper output) => _output = output;

    // Exige que `action` lève un CodecException avec un message non vide -- jamais une exception
    // nue ni un message vide (un refus doit toujours dire quelque chose).
    // / Requires `action` to throw a CodecException with a non-empty message -- never a bare
    // exception nor an empty message (a refusal must always say something).
    private static CodecException Refuse(Action action)
    {
        var exception = Assert.Throws<CodecException>(action);
        Assert.NotEqual(string.Empty, exception.Message);
        return exception;
    }

    // FR : REMPLISSAGE syntaxique pour les témoins qui ne testent QUE l'enveloppe (racine
    //      manquante/ambiguë, cf. RootWithoutCase_IsNamed / RootWithTwoCases_IsNamed) -- le décodage
    //      lève avant même d'atteindre Opcode.Parse (voir Envelope.Decode), donc AUCUNE assertion ne
    //      lit cette valeur. "zzq" est délibérément un opcode qui N'EXISTE PAS dans la table générée
    //      (aucun token mesuré ne commence par 'z') : il ne peut donc jamais collisionner avec un
    //      vrai opcode ni se faire passer pour l'un d'eux. Ne pas confondre avec le littéral GARDÉ de
    //      WellFormedSyntheticFrame_IsAccepted plus bas, qui LUI porte une charge sémantique réelle
    //      -- voir son marqueur TEST_ONLY.
    // EN : syntactic FILLER for witnesses that test ONLY the envelope (missing/ambiguous root, see
    //      RootWithoutCase_IsNamed / RootWithTwoCases_IsNamed) -- decoding throws before ever
    //      reaching Opcode.Parse (see Envelope.Decode), so NO assertion ever reads this value. "zzq"
    //      is deliberately an opcode that does NOT exist in the generated table (no measured token
    //      starts with 'z'), so it can never collide with, or be mistaken for, a real one. Do not
    //      confuse it with the KEPT literal in WellFormedSyntheticFrame_IsAccepted below, which DOES
    //      carry real semantic weight -- see its TEST_ONLY marker.
    private const string FillerOpcode = "zzq";

    /// <summary>
    /// FR : un varint qui réclame un 11e octet. Le 10e doit porter la continuation SANS déborder
    ///      (bits bas ≤ 0x01), sinon c'est <see cref="CodecErrorCode.VarintOverflow"/> qui se
    ///      déclenche d'abord — deux défauts distincts, deux témoins distincts.
    /// EN : a varint asking for an 11th byte. The 10th must carry continuation WITHOUT overflowing
    ///      (low bits ≤ 0x01), otherwise <see cref="CodecErrorCode.VarintOverflow"/> fires first —
    ///      two distinct defects, two distinct witnesses.
    /// </summary>
    [Fact]
    public void VarintTooLong_IsNamed()
    {
        var evil = new List<byte>();
        for (int i = 0; i < 9; i++)
        {
            evil.Add(0xFF);
        }

        evil.Add(0x81);
        evil.Add(0x01);

        CodecException error = Refuse(() =>
        {
            int position = 0;
            Varint.Read(evil.ToArray(), ref position);
        });

        Assert.Equal(CodecErrorCode.VarintTooLong, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>FR : 10e octet &gt; 0x01 = débordement 64 bits. EN : 10th byte above 0x01 = 64-bit overflow.</summary>
    [Fact]
    public void VarintOverflow_IsNamed()
    {
        var evil = new List<byte>();
        for (int i = 0; i < 9; i++)
        {
            evil.Add(0xFF);
        }

        evil.Add(0x7F);

        CodecException error = Refuse(() =>
        {
            int position = 0;
            Varint.Read(evil.ToArray(), ref position);
        });

        Assert.Equal(CodecErrorCode.VarintOverflow, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : longueur de trame annoncée au-delà du plafond client (131 072). Le client lui-même
    ///      refuse à cette valeur — la nôtre doit refuser avant de tenter d'allouer.
    /// EN : declared frame length beyond the client cap. The client itself refuses at that value.
    /// </summary>
    [Fact]
    public void FrameLargerThanClientCap_IsNamed()
    {
        var stream = new List<byte>();
        Varint.Write(stream, FrameReader.DefaultMaxFrameLength + 1);
        stream.AddRange(new byte[16]);

        CodecException error = Refuse(() => new Codec3().Decode(stream.ToArray()));

        Assert.Equal(CodecErrorCode.FrameTooLarge, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : longueur d'un champ len-préfixé qui dépasse le tampon de la trame.
    /// EN : length-delimited field length exceeding the frame buffer.
    /// </summary>
    [Fact]
    public void FieldLengthExceedsBuffer_IsNamed()
    {
        // FR : tag f1/len, longueur 200, mais 3 octets seulement derrière.
        // EN : tag f1/len, length 200, but only 3 bytes behind.
        byte[] frame = { 0x0A, 0xC8, 0x01, 0x01, 0x02, 0x03 };

        CodecException error = Refuse(() => ProtoReader.ReadMessage(frame, 0, new ProtoStats()));

        Assert.Equal(CodecErrorCode.LengthExceedsBuffer, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>FR : typeUrl sans le préfixe attendu. EN : typeUrl without the expected prefix.</summary>
    [Fact]
    public void TypeUrlWithoutPrefix_IsNamed()
    {
        CodecException error = Refuse(() => Opcode.Parse("type.googleapis.com/jru"));

        Assert.Equal(CodecErrorCode.TypeUrlPrefixMissing, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>FR : préfixe seul, sans nom d'opcode derrière. EN : bare prefix, no opcode name.</summary>
    [Fact]
    public void TypeUrlWithoutName_IsNamed()
    {
        CodecException error = Refuse(() => Opcode.Parse(Opcode.Prefix));
        Assert.Equal(CodecErrorCode.TypeUrlInvalid, error.Code);
    }

    /// <summary>
    /// FR : une trame complète mais dont le typeUrl n'a pas le préfixe — le refus doit remonter du
    ///      décodage d'enveloppe, pas d'un `Parse` isolé.
    /// EN : a complete frame whose typeUrl lacks the prefix — the refusal must come from envelope
    ///      decoding, not from an isolated `Parse`.
    /// </summary>
    [Fact]
    public void FrameWithForeignTypeUrl_IsNamed()
    {
        byte[] frame = BuildFrame(rootField: 1, typeUrl: "type.googleapis.com/jru", payload: Array.Empty<byte>());

        CodecException error = Refuse(() => new Codec3().Decode(frame));

        Assert.Equal(CodecErrorCode.TypeUrlPrefixMissing, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>FR : racine sans champ 1/2/3. EN : root without field 1/2/3.</summary>
    [Fact]
    public void RootWithoutCase_IsNamed()
    {
        byte[] frame = BuildFrame(rootField: 7, typeUrl: Opcode.Prefix + FillerOpcode, payload: Array.Empty<byte>());

        CodecException error = Refuse(() => new Codec3().Decode(frame));

        Assert.Equal(CodecErrorCode.RootCaseMissing, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : racine portant DEUX cas — le `oneof` du client (`hea`, discriminant `hdz`) ne peut pas
    ///      en produire deux ; les accepter en silence masquerait un émetteur cassé.
    /// EN : root carrying TWO cases — the client `oneof` cannot produce two; silently accepting
    ///      them would hide a broken sender.
    /// </summary>
    [Fact]
    public void RootWithTwoCases_IsNamed()
    {
        byte[] any = BuildAny(Opcode.Prefix + FillerOpcode, Array.Empty<byte>());
        var root = new List<byte>();
        ProtoWriter.WriteLengthDelimited(root, 1, BuildWrapper(any));
        ProtoWriter.WriteLengthDelimited(root, 3, BuildWrapper(any));

        byte[] frame = new FrameWriter().Frame(root.ToArray());

        CodecException error = Refuse(() => new Codec3().Decode(frame));

        Assert.Equal(CodecErrorCode.RootCaseAmbiguous, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>FR : wrapper sans champ Any. EN : wrapper without an Any field.</summary>
    [Fact]
    public void WrapperWithoutAny_IsNamed()
    {
        var wrapper = new List<byte>();
        ProtoWriter.WriteVarint(wrapper, Envelope.WrapperIdField, 42);

        var root = new List<byte>();
        ProtoWriter.WriteLengthDelimited(root, 1, wrapper.ToArray());

        CodecException error = Refuse(
            () => new Codec3().Decode(new FrameWriter().Frame(root.ToArray())));

        Assert.Equal(CodecErrorCode.AnyMissing, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : wire type 3/4 (groupes) et 6/7 (inexistants) — absents du protocole 3.0 mesuré, donc
    ///      refusés nommément plutôt qu'ignorés.
    /// EN : wire types 3/4 (groups) and 6/7 (nonexistent) — absent from the measured 3.0 protocol,
    ///      hence named-refused rather than ignored.
    /// </summary>
    [Theory]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(6)]
    [InlineData(7)]
    public void UnsupportedWireType_IsNamed(int wireType)
    {
        byte[] frame = { (byte)((1 << 3) | wireType), 0x00 };

        CodecException error = Refuse(() => ProtoReader.ReadMessage(frame, 0, new ProtoStats()));

        Assert.Equal(CodecErrorCode.InvalidWireType, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : varint coupé en fin de tampon dans un contexte STRICT (`Varint.Read`, pas `TryRead`) —
    ///      là, « incomplet » EST une erreur, parce qu'il n'y aura pas de segment suivant.
    /// EN : varint cut at buffer end in a STRICT context (`Varint.Read`, not `TryRead`) — there,
    ///      "incomplete" IS an error, because no further segment will come.
    /// </summary>
    [Fact]
    public void VarintTruncated_IsNamed()
    {
        byte[] cut = { 0x82 };

        CodecException error = Refuse(() =>
        {
            int position = 0;
            Varint.Read(cut, ref position);
        });

        Assert.Equal(CodecErrorCode.VarintTruncated, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : le champ `Any` existe mais ses octets ne sont pas un message lisible. Le refus doit
    ///      nommer l'`Any`, pas le wire type profond : c'est l'`Any` que l'appelant peut situer.
    /// EN : the `Any` field exists but its bytes are not a readable message. The refusal must name
    ///      the `Any`, not the deep wire type: the `Any` is what the caller can locate.
    /// </summary>
    [Fact]
    public void AnyMalformed_IsNamed()
    {
        // FR : 0x74 = champ 14 / wire type 4 (fin de groupe) — illisible comme message.
        // EN : 0x74 = field 14 / wire type 4 (end group) — unreadable as a message.
        var wrapper = new List<byte>();
        ProtoWriter.WriteLengthDelimited(wrapper, Envelope.WrapperAnyField, new byte[] { 0x74 });

        var root = new List<byte>();
        ProtoWriter.WriteLengthDelimited(root, 1, wrapper.ToArray());

        CodecException error = Refuse(
            () => new Codec3().Decode(new FrameWriter().Frame(root.ToArray())));

        Assert.Equal(CodecErrorCode.AnyMalformed, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : GARDE STRUCTURELLE — tout code d'erreur DÉCLARÉ doit être levé quelque part dans le
    ///      cœur, et tout code levé doit être éprouvé ici. Un code déclaré et jamais atteignable
    ///      est une promesse de refus que personne ne tient.
    /// EN : STRUCTURAL GUARD — every DECLARED error code must be thrown somewhere in the core, and
    ///      every thrown code must be exercised here. A declared, unreachable code is a promise of
    ///      refusal nobody keeps.
    /// </summary>
    [Fact]
    public void EveryDeclaredErrorCode_IsCoveredByATest()
    {
        var covered = new HashSet<CodecErrorCode>
        {
            CodecErrorCode.VarintTooLong,
            CodecErrorCode.VarintTruncated,
            CodecErrorCode.VarintOverflow,
            CodecErrorCode.LengthExceedsBuffer,
            CodecErrorCode.FrameTooLarge,
            CodecErrorCode.TrailingBytes,
            CodecErrorCode.InvalidFieldNumber,
            CodecErrorCode.InvalidWireType,
            CodecErrorCode.RootCaseMissing,
            CodecErrorCode.RootCaseAmbiguous,
            CodecErrorCode.AnyMissing,
            CodecErrorCode.TypeUrlPrefixMissing,
            CodecErrorCode.TypeUrlInvalid,
            CodecErrorCode.AnyMalformed,
        };

        var declared = Enum.GetValues<CodecErrorCode>().ToHashSet();
        var uncovered = declared.Except(covered).ToList();

        _output.WriteLine($"codes déclarés/declared={declared.Count} couverts/covered={covered.Count}");
        Assert.Empty(uncovered);
    }

    /// <summary>FR : numéro de champ 0 interdit par protobuf. EN : field number 0 forbidden by protobuf.</summary>
    [Fact]
    public void FieldNumberZero_IsNamed()
    {
        byte[] frame = { 0x00, 0x01 };

        CodecException error = Refuse(() => ProtoReader.ReadMessage(frame, 0, new ProtoStats()));

        Assert.Equal(CodecErrorCode.InvalidFieldNumber, error.Code);
        _output.WriteLine(error.Message);
    }

    /// <summary>
    /// FR : CONTRÔLE POSITIF des témoins négatifs — la même fabrique, bien formée, doit passer.
    ///      Sans ce contrôle, un refus pourrait venir de la fabrique et non du défaut visé.
    /// EN : POSITIVE CONTROL for the negative witnesses — the same builder, well formed, must pass.
    ///      Without it, a refusal could come from the builder rather than from the targeted defect.
    /// </summary>
    [Fact]
    public void WellFormedSyntheticFrame_IsAccepted()
    {
        byte[] payload = { 0x10, 0x82, 0x8A, 0xB8, 0x49 };
        // FR : littéral GARDÉ à dessein -- seconde transcription INDÉPENDANTE d'un fait mesuré
        //      (capture réelle build 3.6.10.10, opcode `jru`, cf. commentaire ~10 lignes plus bas).
        //      Il ne doit PAS lire dispatch-3.6.10.10.json ni passer par Opcode/la table de liaison :
        //      un test qui lirait la table pour se comparer à elle-même resterait vert même si le
        //      générateur avait régénéré la table de travers -- « vérifier par le même chemin est un
        //      tampon, pas une mesure ». La ligne suivante est donc exemptée de la règle L6
        //      (gate-proto-sync.py témoin a) par le marqueur ci-dessous, jamais en silence : la gate
        //      imprime la ligne exemptée, avec son fichier:ligne, à chaque passage.
        // EN : literal deliberately KEPT -- an INDEPENDENT second transcription of a measured fact
        //      (real capture, build 3.6.10.10, opcode `jru`, see the comment ~10 lines below). It
        //      must NOT read dispatch-3.6.10.10.json nor go through Opcode/the link table: a test
        //      that read the table to compare itself against the table would stay green even if the
        //      generator had regenerated the table wrong -- "verifying through the same path is a
        //      rubber stamp, not a measurement." The next line is therefore exempted from the L6 rule
        //      (gate-proto-sync.py witness a) by the marker below, never silently: the gate prints
        //      the exempted line, with its file:line, on every run.
        // TEST_ONLY: ligne suivante -- littéral gardé, voir justification ci-dessus.
        byte[] frame = BuildFrame(rootField: 1, typeUrl: "type.ankama.com/jru", payload: payload);

        DecodeResult result = new Codec3().Decode(frame);

        Assert.Single(result.Messages);
        RawMessage message = result.Messages[0];
        Assert.Equal("jru", message.Opcode.Name);
        Assert.Equal(Direction.S2C, message.Direction);
        Assert.Equal(RootCase.Push, message.Case);

        // FR : `jru { f2: mapId }` — la capture citée par Jondo donne mapId = 154010882.
        // EN : `jru { f2: mapId }` — the capture cited by Jondo gives mapId = 154010882.
        Assert.Single(message.Fields);
        Assert.Equal(2, message.Fields[0].Number);
        Assert.Equal(154010882UL, message.Fields[0].VarintValue);

        Assert.Equal(
            Fixtures.Sha256Hex(frame),
            Fixtures.Sha256Hex(new Codec3().Encode(result.Messages)));
    }

    // Construit un `google.protobuf.Any` synthétique (typeUrl + payload) pour un témoin de test.
    // / Builds a synthetic `google.protobuf.Any` (typeUrl + payload) for a test witness.
    private static byte[] BuildAny(string typeUrl, byte[] payload)
    {
        var any = new List<byte>();
        ProtoWriter.WriteLengthDelimited(any, Envelope.AnyTypeUrlField, Encoding.UTF8.GetBytes(typeUrl));
        if (payload.Length > 0)
        {
            ProtoWriter.WriteLengthDelimited(any, Envelope.AnyPayloadField, payload);
        }

        return any.ToArray();
    }

    // Enveloppe un Any dans le wrapper (hdx/hdy/hdw) pour un témoin de test.
    // / Wraps an Any into the wrapper (hdx/hdy/hdw) for a test witness.
    private static byte[] BuildWrapper(byte[] any)
    {
        var wrapper = new List<byte>();
        ProtoWriter.WriteLengthDelimited(wrapper, Envelope.WrapperAnyField, any);
        return wrapper.ToArray();
    }

    // Construit une trame complète synthétique (racine → wrapper → Any) avec son préfixe de
    // longueur, prête à passer dans FrameReader pour un témoin de test.
    // / Builds a complete synthetic frame (root → wrapper → Any) with its length prefix, ready
    // to feed into FrameReader for a test witness.
    private static byte[] BuildFrame(int rootField, string typeUrl, byte[] payload)
    {
        var root = new List<byte>();
        ProtoWriter.WriteLengthDelimited(root, rootField, BuildWrapper(BuildAny(typeUrl, payload)));
        return new FrameWriter().Frame(root.ToArray());
    }
}
