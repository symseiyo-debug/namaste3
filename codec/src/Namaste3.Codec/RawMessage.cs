// QUOI : RawMessage.cs -- une trame décodée (opcode, sens, payload brut, arbre de champs
//   générique), le type de sortie public du codec.
// POURQUOI : la forme que les étages 3 (handlers) et 5 (sniffer) consomment, SANS schéma requis
//   -- un message inconnu d'un futur patch reste exploitable.
// COMMENT LANCER : jamais seul -- produit par Codec3, consommé par les handlers et le sniffer.
// GATE : couvert par tests/Namaste3.Codec.Tests (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>
/// FR : une trame décodée, telle que l'étage 3 (handlers) et l'étage 5 (sniffer) la consomment :
///      opcode, sens, charge utile BRUTE, et l'arbre générique de ses champs. Aucune connaissance
///      de schéma n'est requise pour la produire — c'est ce qui la rend utilisable sur un message
///      qu'aucune version du protocole ne nous a encore appris.
/// EN : a decoded frame, as stage 3 (handlers) and stage 5 (sniffer) consume it: opcode, direction,
///      RAW payload, and the generic tree of its fields. No schema knowledge is required to produce
///      it — which is what makes it usable on a message no protocol version has taught us yet.
/// </summary>
public sealed class RawMessage
{
    /// <summary>FR : offset absolu du préfixe de longueur dans le flux. EN : absolute stream offset of the length prefix.</summary>
    public required long Offset { get; init; }

    /// <summary>FR : taille de la charge encadrée, préfixe exclu. EN : framed payload size, prefix excluded.</summary>
    public required int FrameLength { get; init; }

    public required Opcode Opcode { get; init; }

    public required Direction Direction { get; init; }

    public required RootCase Case { get; init; }

    /// <summary>FR : id de requête si le cas racine en porte un. EN : request id when the root case carries one.</summary>
    public long? RequestId { get; init; }

    /// <summary>FR : charge utile de l'opcode, octets bruts. EN : opcode payload, raw bytes.</summary>
    public required byte[] Payload { get; init; }

    /// <summary>
    /// FR : champs de la charge utile en arbre générique `{num: wiretype: valeur|sous-arbre}`.
    ///      Vide si la charge est absente ou non structurée.
    /// EN : payload fields as a generic tree. Empty when the payload is absent or unstructured.
    /// </summary>
    public required IReadOnlyList<ProtoField> Fields { get; init; }

    /// <summary>FR : l'enveloppe complète, pour le ré-encodage byte-exact. EN : the full envelope, for byte-exact re-encoding.</summary>
    public required Envelope Envelope { get; init; }

    /// <summary>FR : ligne d'en-tête pour le sniffer. EN : header line for the sniffer.</summary>
    public string Describe()
    {
        string id = RequestId is null ? string.Empty : $" reqId={RequestId}";
        string canonical = Opcode.IsCanonical ? string.Empty : " [opcode NON canonique/non-canonical]";
        return $"@{Offset,-7} len={FrameLength,-6} {Direction} f{(int)Case}/{Case,-7} {Opcode}{id}{canonical}";
    }
}
