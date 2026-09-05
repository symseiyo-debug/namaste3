// QUOI : ProtoField.cs -- wire types protobuf (ProtoWireType) et un champ décodé (tag + valeur brute).
// POURQUOI : la base commune que ProtoReader/ProtoWriter manipulent -- un seul modèle de champ,
//   jamais une paire de structures qui pourrait diverger entre lecture et écriture.
// COMMENT LANCER : jamais seul -- consommé par ProtoReader/ProtoWriter/RawMessage.
// GATE : couvert par tests/Namaste3.Codec.Tests (`dotnet test`).
using System.Text;

namespace Namaste3.Codec;

/// <summary>FR : wire types protobuf. EN : protobuf wire types.</summary>
public enum ProtoWireType : byte
{
    Varint = 0,
    Fixed64 = 1,
    LengthDelimited = 2,
    StartGroup = 3,
    EndGroup = 4,
    Fixed32 = 5,
}

/// <summary>
/// FR : UN champ protobuf décodé SANS schéma — c'est l'exigence de l'étage 5 (sniffer
///      communautaire) : on doit pouvoir lire une trame dont on n'a pas le `.proto`.
///      Un champ de type 2 porte TOUJOURS ses octets bruts ; il porte EN PLUS un sous-arbre
///      quand ce sous-arbre se ré-encode exactement en ces mêmes octets (voir ProtoReader).
/// EN : ONE protobuf field decoded WITHOUT a schema — the stage-5 requirement (community
///      sniffer): we must be able to read a frame whose `.proto` we do not have.
///      A type-2 field ALWAYS carries its raw bytes; it ALSO carries a subtree when that subtree
///      re-encodes exactly into those same bytes (see ProtoReader).
/// </summary>
public sealed class ProtoField
{
    public required int Number { get; init; }

    public required ProtoWireType WireType { get; init; }

    /// <summary>FR : wire type 0. EN : wire type 0.</summary>
    public ulong VarintValue { get; init; }

    /// <summary>FR : wire type 1. EN : wire type 1.</summary>
    public ulong Fixed64Value { get; init; }

    /// <summary>FR : wire type 5. EN : wire type 5.</summary>
    public uint Fixed32Value { get; init; }

    /// <summary>FR : wire type 2, octets exacts. EN : wire type 2, exact bytes.</summary>
    public byte[] Bytes { get; init; } = Array.Empty<byte>();

    /// <summary>
    /// FR : sous-arbre, non nul UNIQUEMENT s'il se ré-encode octet pour octet en <see cref="Bytes"/>.
    ///      Null = charge utile opaque (chaîne, blob, ou sous-message que nous n'avons pas su rendre).
    /// EN : subtree, non-null ONLY if it re-encodes byte for byte into <see cref="Bytes"/>.
    ///      Null = opaque payload (string, blob, or submessage we failed to reproduce).
    /// </summary>
    public IReadOnlyList<ProtoField>? Message { get; init; }

    /// <summary>FR : offset absolu du tag dans la source. EN : absolute offset of the tag in the source.</summary>
    public long Offset { get; init; }

    /// <summary>
    /// FR : rendu texte pour le sniffer — `f2:varint 154010882` / `f1:len(19) "type.ankama.com/jru"`.
    /// EN : text rendering for the sniffer.
    /// </summary>
    public string Describe()
    {
        return WireType switch
        {
            ProtoWireType.Varint => $"f{Number}:varint {VarintValue}{SignedHint()}",
            ProtoWireType.Fixed64 => $"f{Number}:fixed64 0x{Fixed64Value:x16}",
            ProtoWireType.Fixed32 => $"f{Number}:fixed32 0x{Fixed32Value:x8}",
            ProtoWireType.LengthDelimited when Message is not null => $"f{Number}:msg({Bytes.Length})",
            ProtoWireType.LengthDelimited => $"f{Number}:len({Bytes.Length}) {Preview()}",
            _ => $"f{Number}:wt{(int)WireType}",
        };
    }

    /// <summary>
    /// FR : un varint dont le bit 64 est mis vient presque toujours d'un int32/int64 NÉGATIF
    ///      (protobuf étend le signe sur 64 bits). Le cas mesuré : l'id de requête -1 sur 10 octets.
    /// EN : a varint with bit 64 set almost always comes from a NEGATIVE int32/int64 (protobuf
    ///      sign-extends to 64 bits). Measured case: request id -1 on 10 bytes.
    /// </summary>
    private string SignedHint()
        => VarintValue > long.MaxValue ? $" (signé/signed {unchecked((long)VarintValue)})" : string.Empty;

    /// <summary>FR : aperçu ASCII sûr, tronqué. EN : safe truncated ASCII preview.</summary>
    private string Preview()
    {
        const int Limit = 48;
        int take = Math.Min(Bytes.Length, Limit);
        var sb = new StringBuilder(take + 8);
        bool printable = true;

        for (int i = 0; i < take; i++)
        {
            byte b = Bytes[i];
            if (b is < 0x20 or > 0x7E)
            {
                printable = false;
                break;
            }
        }

        if (printable && take > 0)
        {
            sb.Append('"');
            for (int i = 0; i < take; i++)
            {
                sb.Append((char)Bytes[i]);
            }

            sb.Append('"');
        }
        else
        {
            for (int i = 0; i < take; i++)
            {
                sb.Append(Bytes[i].ToString("x2"));
            }
        }

        if (Bytes.Length > take)
        {
            sb.Append('…');
        }

        return sb.ToString();
    }
}
