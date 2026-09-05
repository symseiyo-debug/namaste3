// ============================================================================================
// QUOI : le protocole de connexion NU (phase 1) — celui qui parle AVANT que l'enveloppe
//     `type.ankama.com` n'apparaisse. Racine `mhh`, un `oneof` à trois branches :
//     f1 = authentification (client → serveur), f2 = résultat (serveur → client), f3 = une
//     troisième branche que l'émulateur de référence n'implémente pas.
// POURQUOI (05/09/2026) : le codec de l'étage 2 REFUSE nommément cette phase (`AnyMissing`) —
//     c'est volontaire et déclaré dans son §7.1, qui prévoit qu'un second parseur d'enveloppe
//     reste à écrire. Le voici. Deux sources indépendantes le décrivent et concordent champ par
//     champ : le dump de NOTRE client (il2cpp.cs:1063673 `mhh`, :1063780 `mhj`, :1063912 `mhl`,
//     :1065253 `mih`) et le `.proto` reconstruit (protocolo_conexion_3.6.10.10.proto:163-178,
//     232-242 `mia`, 259-263 `mik`).
//     ⚠️ On PARSE le champ 3 au lieu de l'ignorer : l'émulateur de référence l'omet, et cette
//     omission est explicitement listée comme un décalage à NE PAS copier.
// EN : the NAKED connection protocol (phase 1), spoken BEFORE the `type.ankama.com` envelope.
//     Root `mhh`, a three-branch oneof. Stage 2's codec refuses this phase by design; this is
//     the second envelope parser its §7.1 announced.
// COMMENT LANCER / USAGE : `ConnectEnvelope.Decode(frame)` puis `.Frame(champs)` pour répondre.
// GATE : `NegativeTests` (racine vide, branche inconnue) + `SequenceTests` (sélection serveur).
// ============================================================================================

using Namaste3.Codec;

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : les trois branches du `oneof` racine. Le NUMÉRO du champ EST la branche.
/// EN : the root oneof's three branches. The field NUMBER IS the branch.
/// </summary>
public enum ConnectBranch
{
    /// <summary>Aucune branche lisible. / No readable branch.</summary>
    None = 0,
    /// <summary>f1 — authentification / sélection de serveur, C2S. / Auth, C2S.</summary>
    Auth = 1,
    /// <summary>f2 — résultat d'authentification, S2C. / Auth result, S2C.</summary>
    AuthResult = 2,
    /// <summary>f3 — branche non implémentée par l'émulateur de référence. / Third branch.</summary>
    Third = 3,
}

/// <summary>
/// FR : une trame de connexion nue décodée : sa branche et ses champs. Les champs sont l'arbre
///      GÉNÉRIQUE du codec — on ne modélise pas le schéma, on lit les numéros qu'on connaît.
/// EN : a decoded naked frame: its branch and its fields, as the codec's GENERIC tree.
/// </summary>
public sealed class ConnectMessage
{
    /// <summary>La branche racine lue. / The root branch read.</summary>
    public required ConnectBranch Branch { get; init; }

    /// <summary>Les champs de la branche. / The branch's fields.</summary>
    public required IReadOnlyList<ProtoField> Fields { get; init; }

    /// <summary>
    /// FR : l'identifiant de serveur choisi, quand la trame est une sélection.
    ///      Chemin : `mhj.f4` (`mih`) → `mih.f1` (int32). VÉRIFIÉ il2cpp.cs:1065253 et recoupé
    ///      octet à octet avec l'exemple `0a 0a 08 0a 01 31 22 03 08 a2 02` → serverId 290.
    /// EN : the chosen server id, when the frame is a selection. Path: mhj.f4 → mih.f1 (int32).
    /// </summary>
    public long? SelectedServerId
    {
        get
        {
            ProtoField? selected = Find(Fields, SelectedServerField);
            if (selected?.Message is null)
            {
                return null;
            }

            ProtoField? id = Find(selected.Message, ServerIdField);
            return id is { WireType: ProtoWireType.Varint } ? (long)id.VarintValue : null;
        }
    }

    /// <summary>
    /// FR : la langue annoncée par le client (`mhj.f1`, string). Utile à journaliser : c'est le
    ///      premier renseignement que le client donne sur lui-même.
    /// EN : the client's announced language (mhj.f1, string).
    /// </summary>
    public string? Language
    {
        get
        {
            ProtoField? lang = Find(Fields, LanguageField);
            return lang is { WireType: ProtoWireType.LengthDelimited }
                ? System.Text.Encoding.UTF8.GetString(lang.Bytes)
                : null;
        }
    }

    // Numéros VÉRIFIÉS dans le dump du client, jamais devinés.
    // / Field numbers VERIFIED in the client dump, never guessed.
    private const int LanguageField = 1;          // mhj.f1 string, il2cpp.cs:1063780
    private const int SelectedServerField = 4;    // mhj.f4 mih,    il2cpp.cs:1063780
    private const int ServerIdField = 1;          // mih.f1 int32,  il2cpp.cs:1065253

    /// <summary>FR : premier champ portant ce numéro. / EN : first field with that number.</summary>
    private static ProtoField? Find(IReadOnlyList<ProtoField> fields, int number)
    {
        foreach (ProtoField field in fields)
        {
            if (field.Number == number)
            {
                return field;
            }
        }

        return null;
    }
}

/// <summary>
/// FR : décodage et encodage de la phase nue.
/// EN : naked-phase decoding and encoding.
/// </summary>
public static class ConnectEnvelope
{
    /// <summary>
    /// FR : décode une trame nue. Un refus est NOMMÉ (`CodecException`) : une racine vide, une
    ///      branche hors 1/2/3 ou un sous-message illisible ne rendent jamais un message muet.
    /// EN : decodes a naked frame. A refusal is NAMED; an empty root, an out-of-range branch or
    ///      an unreadable sub-message never yield a silent message.
    /// </summary>
    public static ConnectMessage Decode(ReadOnlySpan<byte> frame, long offset = 0)
    {
        var stats = new ProtoStats();
        IReadOnlyList<ProtoField> root = ProtoReader.ReadMessage(frame, offset, stats);
        if (root.Count == 0)
        {
            throw CodecException.At(
                CodecErrorCode.RootCaseMissing, offset, "racine de connexion vide / empty connect root");
        }

        ProtoField first = root[0];
        if (first.Number is < (int)ConnectBranch.Auth or > (int)ConnectBranch.Third)
        {
            throw CodecException.At(
                CodecErrorCode.RootCaseMissing, offset,
                $"branche de connexion hors 1..3 / connect branch out of 1..3: f{first.Number}");
        }

        if (first.WireType != ProtoWireType.LengthDelimited)
        {
            throw CodecException.At(
                CodecErrorCode.InvalidWireType, offset,
                $"branche de connexion f{first.Number} n'est pas un sous-message / not a sub-message");
        }

        return new ConnectMessage
        {
            Branch = (ConnectBranch)first.Number,
            Fields = first.Message ?? ProtoReader.ReadMessage(first.Bytes, offset, stats),
        };
    }

    /// <summary>
    /// FR : encode une réponse de phase nue, préfixe de longueur compris. Les champs donnés sont
    ///      déjà ceux de la RACINE (le générateur écrit `{"n":2,...}` pour la branche résultat) —
    ///      on n'ajoute donc pas d'enveloppe supplémentaire par-dessus.
    /// EN : encodes a naked-phase answer, length prefix included. The given fields are already
    ///      the ROOT's; no extra envelope is wrapped on top.
    /// </summary>
    public static byte[] Frame(IReadOnlyList<FieldSpec> rootFields, IInjectionSource injections)
    {
        byte[] body = PayloadBuilder.Build(rootFields, injections);
        return new FrameWriter().Frame(body);
    }
}
