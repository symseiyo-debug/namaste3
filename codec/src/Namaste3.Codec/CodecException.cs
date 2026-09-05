// QUOI : CodecException.cs -- l'exception unique du codec (CodecErrorCode + offset + message),
//   jamais une exception nue.
// POURQUOI : un refus qui ne dit ni QUOI ni À QUEL OFFSET n'apprend rien au débogueur -- doctrine du
//   projet : "un verdict ne dit jamais sa cause" appliquée au codec.
// COMMENT LANCER : jamais seul -- levée par FrameReader/ProtoReader/Varint, capturée par les tests.
// GATE : couvert par tests/Namaste3.Codec.Tests/NegativeTests.cs (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : code d'erreur NOMMÉ. Doctrine : le codec ne lève jamais d'exception nue — un refus dit
///      toujours QUOI a échoué et À QUEL OFFSET, sinon un rouge n'apprend rien.
/// EN : NAMED error code. Doctrine: the codec never throws a bare exception — a refusal always
///      says WHAT failed and AT WHICH OFFSET, otherwise a red result teaches nothing.
/// </summary>
public enum CodecErrorCode
{
    /// <summary>FR/EN : varint > 10 octets / varint longer than 10 bytes.</summary>
    VarintTooLong,

    /// <summary>FR/EN : varint tronqué (fin de tampon) / varint truncated (end of buffer).</summary>
    VarintTruncated,

    /// <summary>FR/EN : varint qui déborde 64 bits / varint overflowing 64 bits.</summary>
    VarintOverflow,

    /// <summary>FR : longueur annoncée > tampon. EN : declared length larger than the buffer.</summary>
    LengthExceedsBuffer,

    /// <summary>FR : longueur de trame &gt; plafond client (131 072). EN : frame length above the client cap.</summary>
    FrameTooLarge,

    /// <summary>FR : octets restants après la dernière trame. EN : trailing bytes after the last frame.</summary>
    TrailingBytes,

    /// <summary>FR : numéro de champ protobuf invalide (0). EN : invalid protobuf field number (0).</summary>
    InvalidFieldNumber,

    /// <summary>
    /// FR : wire type inconnu (6/7) ou groupe non supporté (3/4). Les groupes sont refusés par CE
    ///      code, et non par un code « groupe déséquilibré » : un tel code serait DÉCLARÉ sans
    ///      jamais pouvoir être levé, puisqu'on refuse dès l'ouverture du groupe.
    /// EN : unknown wire type (6/7) or unsupported group (3/4). Groups are refused by THIS code, not
    ///      by an "unbalanced group" code: such a code would be DECLARED without ever being
    ///      throwable, since we refuse at the group's opening.
    /// </summary>
    InvalidWireType,

    /// <summary>FR : la racine ne porte aucun des champs 1/2/3. EN : root carries none of fields 1/2/3.</summary>
    RootCaseMissing,

    /// <summary>FR : la racine porte plusieurs cas (oneof violé). EN : root carries several cases (oneof broken).</summary>
    RootCaseAmbiguous,

    /// <summary>FR : l'enveloppe ne porte pas de champ Any (f1). EN : envelope has no Any field (f1).</summary>
    AnyMissing,

    /// <summary>FR : typeUrl sans le préfixe "type.ankama.com/". EN : typeUrl without the expected prefix.</summary>
    TypeUrlPrefixMissing,

    /// <summary>FR : typeUrl vide ou non décodable en UTF-8. EN : empty or non-UTF-8 typeUrl.</summary>
    TypeUrlInvalid,

    /// <summary>FR : le champ Any n'est pas un sous-message lisible. EN : the Any field is not a readable submessage.</summary>
    AnyMalformed,
}

/// <summary>
/// FR : toute erreur du codec. Porte le code, l'offset absolu dans la source, et un message court.
/// EN : any codec error. Carries the code, the absolute offset in the source, and a short message.
/// </summary>
public sealed class CodecException : Exception
{
    public CodecErrorCode Code { get; }

    /// <summary>FR : offset absolu, -1 si non situable. EN : absolute offset, -1 when not locatable.</summary>
    public long Offset { get; }

    // Construit le message complet "{code} @ offset {offset}: {detail}" une seule fois, à la création.
    // / Builds the full "{code} @ offset {offset}: {detail}" message once, at construction time.
    public CodecException(CodecErrorCode code, long offset, string detail)
        : base($"{code} @ offset {offset}: {detail}")
    {
        Code = code;
        Offset = offset;
    }

    /// <summary>FR : fabrique courte. EN : short factory.</summary>
    public static CodecException At(CodecErrorCode code, long offset, string detail)
        => new(code, offset, detail);
}
