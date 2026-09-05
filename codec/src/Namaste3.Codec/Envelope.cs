// QUOI : Envelope.cs -- décode/ré-encode l'enveloppe complète d'une trame 3.0 : racine (oneof)
//   → wrapper (hdx/hdy/hdw) → google.protobuf.Any (typeUrl + payload).
// POURQUOI : c'est le composant byte-exact -- il conserve les listes de champs ORDONNÉES à
//   chaque étage pour qu'un champ inconnu d'un futur patch survive au round-trip, à sa place.
// COMMENT LANCER : jamais seul -- consommé par Codec3/RawMessage.
// GATE : tests/Namaste3.Codec.Tests/RoundTripTests.cs (`dotnet test`).
using System.Text;

namespace Namaste3.Codec;

/// <summary>
/// FR : l'enveloppe d'une trame de jeu 3.0 : racine `hea` (oneof f1/f2/f3) → sous-message
///      (`hdx`/`hdy`/`hdw`) → `google.protobuf.Any` { f1: typeUrl, f2: payload }.
///
///      Byte-exactitude : l'enveloppe conserve les LISTES ORDONNÉES de champs lues à chaque étage.
///      Le ré-encodage les reparcourt DANS L'ORDRE en substituant les parties qu'on prétend
///      comprendre (le typeUrl re-encodé depuis la chaîne, la charge utile, le sous-message) et en
///      ré-écrivant les autres depuis l'arbre générique. Un champ inconnu d'un futur patch survit
///      donc au round-trip à sa place exacte, au lieu d'être perdu en silence.
///
/// EN : the envelope of a 3.0 game frame: root `hea` (oneof f1/f2/f3) → submessage
///      (`hdx`/`hdy`/`hdw`) → `google.protobuf.Any` { f1: typeUrl, f2: payload }.
///      Byte-exactness: the envelope keeps the ORDERED field lists read at each level. Re-encoding
///      walks them IN ORDER, substituting the parts we claim to understand and rewriting the others
///      from the generic tree. An unknown field from a future patch therefore survives the
///      round-trip in its exact place instead of being silently dropped.
/// </summary>
public sealed class Envelope
{
    /// <summary>FR : numéro de champ du typeUrl dans `Any`. EN : typeUrl field number inside `Any`.</summary>
    public const int AnyTypeUrlField = 1;

    /// <summary>FR : numéro de champ de la charge utile dans `Any`. EN : payload field number inside `Any`.</summary>
    public const int AnyPayloadField = 2;

    /// <summary>FR : numéro du champ `Any` dans `hdx`/`hdy`/`hdw` (`il2cpp.cs:839049`, `839138`, `839229`). EN : `Any` field number.</summary>
    public const int WrapperAnyField = 1;

    /// <summary>FR : numéro du champ id/liste dans le wrapper (`il2cpp.cs:839051`, `839140`, `839231`). EN : id/list field number.</summary>
    public const int WrapperIdField = 2;

    public required RootCase Case { get; init; }

    public Direction Direction => DirectionMap.Of(Case);

    public required string TypeUrl { get; init; }

    public required Opcode Opcode { get; init; }

    /// <summary>FR : charge utile brute de l'`Any`, sans schéma. EN : raw `Any` payload, schema-free.</summary>
    public required byte[] Payload { get; init; }

    /// <summary>
    /// FR : id de requête, présent sur f2 (requête) et f3 (réponse). Déclaré `int32` dans le client
    ///      (`il2cpp.cs:839054` / `839234`) alors que Jondo le documente en `i64` — cf. CODEC.md §4.
    ///      Un -1 sort donc sur 10 octets (extension de signe protobuf), ce que Jondo mesure aussi.
    /// EN : request id, present on f2 (request) and f3 (answer). Declared `int32` in the client
    ///      while Jondo documents `i64` — see CODEC.md §4. So -1 goes out on 10 bytes (protobuf
    ///      sign extension), which Jondo measures too.
    /// </summary>
    public long? RequestId { get; init; }

    /// <summary>FR : champs de la racine, dans l'ordre lu. EN : root fields, in read order.</summary>
    public required IReadOnlyList<ProtoField> RootFields { get; init; }

    /// <summary>FR : champs du wrapper, dans l'ordre lu. EN : wrapper fields, in read order.</summary>
    public required IReadOnlyList<ProtoField> WrapperFields { get; init; }

    /// <summary>FR : champs de l'`Any`, dans l'ordre lu. EN : `Any` fields, in read order.</summary>
    public required IReadOnlyList<ProtoField> AnyFields { get; init; }

    /// <summary>
    /// FR : vrai UNIQUEMENT si le wrapper source (<see cref="WrapperFields"/>) se ré-encode octet
    ///      pour octet — le même contrat que <see cref="ProtoField.Message"/>. Faux, entre autres,
    ///      quand un champ interne (ex. l'id de requête) porte un varint non canonique valide mais
    ///      pas le plus court. <see cref="Encode"/> s'appuie dessus pour ne JAMAIS reconstruire un
    ///      niveau dont l'exactitude n'est pas prouvée.
    /// EN : true ONLY if the source wrapper re-encodes byte for byte — same contract as
    ///      <see cref="ProtoField.Message"/>. False when e.g. an inner field (request id) carries a
    ///      valid but non-shortest varint. <see cref="Encode"/> relies on this to NEVER rebuild a
    ///      level whose exactness isn't proven.
    /// </summary>
    public required bool WrapperExact { get; init; }

    /// <summary>FR : octets bruts du wrapper, pour ré-émission opaque si <see cref="WrapperExact"/>
    ///      est faux. EN : raw wrapper bytes, for opaque re-emission if not exact.</summary>
    public required byte[] WrapperBytes { get; init; }

    /// <summary>FR : même garde que <see cref="WrapperExact"/>, pour l'`Any`.
    ///      EN : same guard as <see cref="WrapperExact"/>, for the `Any`.</summary>
    public required bool AnyExact { get; init; }

    /// <summary>FR : octets bruts de l'`Any`, pour ré-émission opaque si <see cref="AnyExact"/> est
    ///      faux. EN : raw `Any` bytes, for opaque re-emission if not exact.</summary>
    public required byte[] AnyBytes { get; init; }

    /// <summary>
    /// FR : décode UNE trame déjà délimitée (sans son préfixe de longueur).
    /// EN : decodes ONE already-delimited frame (without its length prefix).
    /// </summary>
    public static Envelope Decode(ReadOnlySpan<byte> frame, long frameOffset, ProtoStats stats)
    {
        List<ProtoField> rootFields = ProtoReader.ReadMessage(frame, frameOffset, stats);

        ProtoField? caseField = null;
        foreach (ProtoField field in rootFields)
        {
            if (field.Number is 1 or 2 or 3 && field.WireType == ProtoWireType.LengthDelimited)
            {
                if (caseField is not null)
                {
                    throw CodecException.At(
                        CodecErrorCode.RootCaseAmbiguous, frameOffset,
                        $"champs racine {caseField.Number} ET {field.Number} présents / root fields both present");
                }

                caseField = field;
            }
        }

        if (caseField is null)
        {
            throw CodecException.At(
                CodecErrorCode.RootCaseMissing, frameOffset,
                "aucun champ 1/2/3 sur la racine `hea` / no field 1/2/3 on root `hea`");
        }

        var rootCase = (RootCase)caseField.Number;

        IReadOnlyList<ProtoField> wrapperFields = caseField.Message
            ?? ProtoReader.ReadMessage(caseField.Bytes, caseField.Offset, new ProtoStats());

        ProtoField? anyField = null;
        long? requestId = null;
        foreach (ProtoField field in wrapperFields)
        {
            if (field.Number == WrapperAnyField && field.WireType == ProtoWireType.LengthDelimited)
            {
                anyField = field;
            }
            else if (field.Number == WrapperIdField && field.WireType == ProtoWireType.Varint)
            {
                requestId = unchecked((long)field.VarintValue);
            }
        }

        if (anyField is null)
        {
            throw CodecException.At(
                CodecErrorCode.AnyMissing, caseField.Offset,
                $"pas de champ Any (f{WrapperAnyField}) dans le wrapper du cas {(int)rootCase} / no Any field in the wrapper");
        }

        IReadOnlyList<ProtoField> anyFields;
        try
        {
            anyFields = anyField.Message
                ?? ProtoReader.ReadMessage(anyField.Bytes, anyField.Offset, new ProtoStats());
        }
        catch (CodecException inner)
        {
            throw CodecException.At(
                CodecErrorCode.AnyMalformed, anyField.Offset,
                $"l'Any ne se lit pas comme un message / Any is not readable as a message ({inner.Code})");
        }

        string? typeUrl = null;
        byte[] payload = Array.Empty<byte>();
        foreach (ProtoField field in anyFields)
        {
            if (field.WireType != ProtoWireType.LengthDelimited)
            {
                continue;
            }

            if (field.Number == AnyTypeUrlField)
            {
                typeUrl = DecodeUtf8(field);
            }
            else if (field.Number == AnyPayloadField)
            {
                payload = field.Bytes;
            }
        }

        if (typeUrl is null)
        {
            throw CodecException.At(
                CodecErrorCode.TypeUrlInvalid, anyField.Offset,
                $"pas de typeUrl (f{AnyTypeUrlField}) dans l'Any / no typeUrl in the Any");
        }

        return new Envelope
        {
            Case = rootCase,
            TypeUrl = typeUrl,
            Opcode = Opcode.Parse(typeUrl, anyField.Offset),
            Payload = payload,
            RequestId = requestId,
            RootFields = rootFields,
            WrapperFields = wrapperFields,
            WrapperExact = caseField.Message is not null,
            WrapperBytes = caseField.Bytes,
            AnyFields = anyFields,
            AnyExact = anyField.Message is not null,
            AnyBytes = anyField.Bytes,
        };
    }

    /// <summary>
    /// FR : ré-encode l'enveloppe. Le typeUrl repasse par la CHAÎNE décodée (pas par les octets
    ///      d'origine) : si un typeUrl n'était pas de l'UTF-8 aller-retour, le round-trip le dirait.
    /// EN : re-encodes the envelope. The typeUrl goes back through the decoded STRING (not through
    ///      the original bytes): a non-round-trippable UTF-8 typeUrl would show up here.
    /// </summary>
    public byte[] Encode()
    {
        // FR : un niveau dont l'exactitude n'est PAS prouvée (varint non canonique, etc.) est
        //      ré-émis OPAQUE — ses octets d'origine, verbatim — plutôt que reconstruit depuis des
        //      champs qu'on sait déjà ne pas retomber juste (Varint.Write canonicalise toujours).
        //      C'est le même contrat que ProtoField.Message : décomposer un niveau non exact pour
        //      le reconstruire silencieusement est précisément le bug que ce garde empêche.
        // EN : a level whose exactness is NOT proven is re-emitted OPAQUE — its original bytes,
        //      verbatim — instead of rebuilt from fields already known not to round-trip.
        byte[] anyBytes = AnyExact
            ? Rebuild(AnyFields, field => field.Number switch
            {
                AnyTypeUrlField when field.WireType == ProtoWireType.LengthDelimited
                    => Encoding.UTF8.GetBytes(TypeUrl),
                AnyPayloadField when field.WireType == ProtoWireType.LengthDelimited
                    => Payload,
                _ => null,
            })
            : AnyBytes;

        byte[] wrapperBytes = WrapperExact
            ? Rebuild(WrapperFields, field =>
                field.Number == WrapperAnyField && field.WireType == ProtoWireType.LengthDelimited
                    ? anyBytes
                    : null)
            : WrapperBytes;

        return Rebuild(RootFields, field =>
            field.Number == (int)Case && field.WireType == ProtoWireType.LengthDelimited
                ? wrapperBytes
                : null);
    }

    /// <summary>
    /// FR : réécrit une liste de champs DANS L'ORDRE ; `substitute` rend les octets d'un champ
    ///      qu'on reconstruit, ou null pour laisser l'arbre générique s'en charger.
    /// EN : rewrites a field list IN ORDER; `substitute` returns the bytes of a field we rebuild,
    ///      or null to let the generic tree handle it.
    /// </summary>
    private static byte[] Rebuild(IReadOnlyList<ProtoField> fields, Func<ProtoField, byte[]?> substitute)
    {
        var buffer = new List<byte>(64);
        foreach (ProtoField field in fields)
        {
            byte[]? replacement = substitute(field);
            if (replacement is not null)
            {
                ProtoWriter.WriteLengthDelimited(buffer, field.Number, replacement);
            }
            else
            {
                ProtoWriter.WriteField(buffer, field);
            }
        }

        return buffer.ToArray();
    }

    // Decode un champ en UTF-8 STRICT (rejette les octets invalides plutôt que les remplacer)
    // -- un typeUrl mal décodé casserait Opcode.Parse en silence.
    // / Decodes a field as STRICT UTF-8 (rejects invalid bytes instead of replacing them) -- a
    // mis-decoded typeUrl would silently break Opcode.Parse.
    private static string DecodeUtf8(ProtoField field)
    {
        try
        {
            return new UTF8Encoding(false, true).GetString(field.Bytes);
        }
        catch (DecoderFallbackException)
        {
            throw CodecException.At(
                CodecErrorCode.TypeUrlInvalid, field.Offset,
                "typeUrl non décodable en UTF-8 / typeUrl is not valid UTF-8");
        }
    }
}
