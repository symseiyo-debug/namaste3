// ============================================================================================
// QUOI : la fabrication d'une trame de JEU à émettre — enveloppe racine + `google.protobuf.Any`
//     + préfixe de longueur varint. C'est le pendant ÉMISSION du décodeur de l'étage 2.
// POURQUOI (05/09/2026) : le codec de l'étage 2 décode et ré-encode ce qu'il a LU ; pour émettre
//     un message que personne n'a capturé, il faut construire l'enveloppe. Deux faits mesurés
//     la gouvernent, et aucun ne se devine :
//     · le socket de JEU est du varint(len) ++ protobuf, SANS octet de type (la pile Spin et son
//       octet de type sont celles du launcher/chat) — mesuré sur les 3 captures, 355 trames ;
//     · quand la charge utile est VIDE, le champ 2 de l'`Any` est ABSENT, pas présent-et-vide.
//       Mesure : la plus petite trame serveur connue fait 26 octets,
//       `19 0a 17 0a 15 0a 13 <typeUrl>` — aucun `12 00`.
// EN : builds a GAME frame for EMISSION: root envelope + Any + varint length prefix. Two
//     measured facts govern it: no Spin type byte on the game socket, and an EMPTY payload means
//     the Any's field 2 is ABSENT rather than present-and-empty.
// COMMENT LANCER / USAGE : `GameEnvelope.Frame(opcode, payload, rootCase)`.
// GATE : `RoundTripEmissionTests` re-décode chaque trame émise par le codec de l'étage 2 et
//     exige que l'opcode, le sens et la charge en ressortent identiques.
// ============================================================================================

using System.Text;
using Namaste3.Codec;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : fabrique les trames de jeu. Pure : ni horloge, ni aléa, ni socket.
/// EN : builds game frames. Pure: no clock, no randomness, no socket.
/// </summary>
public static class GameEnvelope
{
    // Le préfixe des typeUrl du jeu. Littéral du client (`dxji`, il2cpp.cs:825181), pas un choix.
    // / The game's typeUrl prefix. A client literal, not a choice of ours.
    private const string TypeUrlPrefix = "type.ankama.com/";

    /// <summary>
    /// FR : encode l'enveloppe SANS le préfixe de longueur — utile pour tester la forme seule.
    /// EN : encodes the envelope WITHOUT the length prefix — useful to test the shape alone.
    /// </summary>
    /// <param name="opcode">L'opcode 3 lettres du fil. / The 3-letter wire opcode.</param>
    /// <param name="payload">La charge de l'opcode, éventuellement vide. / The payload.</param>
    /// <param name="rootCase">Le cas racine : push, requête ou réponse. / The root case.</param>
    /// <param name="requestId">
    /// FR : l'id de requête, à réinjecter TEL QUEL sur une réponse. Jamais codé en dur : 98,9 %
    ///      des requêtes mesurées portent -1, mais 1,1 % ne le portent pas.
    /// EN : the request id, echoed AS IS on an answer. Never hard-coded.
    /// </param>
    public static byte[] Encode(
        string opcode, ReadOnlySpan<byte> payload, RootCase rootCase, long? requestId = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(opcode);

        // 1. L'`Any` : champ 1 = typeUrl UTF-8, champ 2 = charge — ABSENT si la charge est vide.
        // / The Any: field 1 = UTF-8 typeUrl, field 2 = payload — ABSENT when the payload is empty.
        var any = new List<byte>(32 + payload.Length);
        ProtoWriter.WriteLengthDelimited(
            any, Envelope.AnyTypeUrlField, Encoding.UTF8.GetBytes(TypeUrlPrefix + opcode));
        if (!payload.IsEmpty)
        {
            ProtoWriter.WriteLengthDelimited(any, Envelope.AnyPayloadField, payload);
        }

        // 2. Le wrapper : champ 1 = l'`Any` ; champ 2 = l'id de requête quand il y en a un.
        // / The wrapper: field 1 = the Any; field 2 = the request id when there is one.
        var wrapper = new List<byte>(any.Count + 16);
        ProtoWriter.WriteLengthDelimited(wrapper, Envelope.WrapperAnyField, any.ToArray());
        if (requestId.HasValue)
        {
            ProtoWriter.WriteVarint(wrapper, Envelope.WrapperIdField, unchecked((ulong)requestId.Value));
        }

        // 3. La racine : le NUMÉRO du champ EST le cas (1 push, 2 requête, 3 réponse).
        // / The root: the field NUMBER IS the case (1 push, 2 request, 3 answer).
        var root = new List<byte>(wrapper.Count + 8);
        ProtoWriter.WriteLengthDelimited(root, (int)rootCase, wrapper.ToArray());
        return root.ToArray();
    }

    /// <summary>
    /// FR : encode l'enveloppe ET son préfixe de longueur varint — la trame prête pour le socket.
    ///      La longueur EXCLUT ses propres octets (mode mesuré sur les 3 captures de jeu).
    /// EN : encodes the envelope AND its varint length prefix — the socket-ready frame. The
    ///      length EXCLUDES its own bytes (the mode measured on the 3 game captures).
    /// </summary>
    public static byte[] Frame(
        string opcode, ReadOnlySpan<byte> payload, RootCase rootCase, long? requestId = null)
    {
        byte[] envelope = Encode(opcode, payload, rootCase, requestId);
        return new FrameWriter().Frame(envelope);
    }

    /// <summary>
    /// FR : dit si des octets ressemblent à une trame de JEU, par la présence du préfixe de
    ///      typeUrl. C'est EXACTEMENT le critère de bascule de phase que la source décrit, et
    ///      c'est un critère de CONTENU, donc faillible : on le journalise à chaque bascule.
    /// EN : tells whether bytes look like a GAME frame, by the typeUrl prefix. This is exactly
    ///      the phase-switch criterion the source describes — a CONTENT criterion, hence
    ///      fallible, so every switch is logged.
    /// </summary>
    public static bool LooksLikeGameFrame(ReadOnlySpan<byte> frame)
    {
        ReadOnlySpan<byte> needle = Encoding.UTF8.GetBytes(TypeUrlPrefix);
        return frame.IndexOf(needle) >= 0;
    }
}
