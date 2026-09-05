// QUOI : Direction.cs -- direction sur le fil (C2S/S2C), le cas racine du oneof `hea` (Push/
//   Request/Answer) et leur correspondance VÉRIFIÉE sur le dump + Jondo.
// POURQUOI : le sens n'est pas décoratif -- envoyer sur le mauvais champ racine bloque le
//   personnage DÉFINITIVEMENT côté client (cf. commentaire de DirectionMap.Of ci-dessous).
// COMMENT LANCER : jamais seul -- consommé par Codec3/ProtoReader pour étiqueter chaque trame.
// GATE : couvert par tests/Namaste3.Codec.Tests (`dotnet test`).
namespace Namaste3.Codec;

/// <summary>FR : sens sur le fil. EN : direction on the wire.</summary>
public enum Direction
{
    /// <summary>FR : client → serveur. EN : client → server.</summary>
    C2S,

    /// <summary>FR : serveur → client. EN : server → client.</summary>
    S2C,
}

/// <summary>
/// FR : le cas du `oneof` racine. VÉRIFIÉ sur le dump : la racine `hea`
///      (`il2cpp.cs:839326-839367`) est un oneof à 3 branches (constantes de champ 1/2/3,
///      `il2cpp.cs:839331-839333`, discriminant `hdz` à 4 valeurs dont None=0) :
///        · f1 → `hdx` = { f1: Any, f2: repeated int32 }  (`il2cpp.cs:839134-839144`)
///        · f2 → `hdy` = { f1: Any, f2: int32 }           (`il2cpp.cs:839224-839234`)
///        · f3 → `hdw` = { f1: Any, f2: int32 }           (`il2cpp.cs:839045-839054`)
///      Le SENS attaché à chaque cas (push/requête/réponse) vient de Jondo (§3.1 du fragment,
///      mesuré sur 103 808 frames) — DÉDUIT côté dump, corroboré par les fixtures (cf. CODEC.md §4).
/// EN : the root `oneof` case. VERIFIED on the dump: root `hea` (`il2cpp.cs:839326-839367`) is a
///      3-branch oneof (field constants 1/2/3, `il2cpp.cs:839331-839333`, `hdz` discriminator with
///      4 values including None=0). The MEANING attached to each case (push/request/answer) comes
///      from Jondo (fragment §3.1, measured on 103,808 frames) — DEDUCED on the dump side,
///      corroborated by the fixtures (see CODEC.md §4).
/// </summary>
public enum RootCase
{
    /// <summary>FR : f1 — poussée serveur, PAS d'id de requête, mais une liste d'int32. EN : f1 — server push.</summary>
    Push = 1,

    /// <summary>FR : f2 — requête client, porte l'id de requête. EN : f2 — client request, carries the request id.</summary>
    Request = 2,

    /// <summary>FR : f3 — réponse serveur, réinjecte l'id de requête. EN : f3 — server answer, echoes the request id.</summary>
    Answer = 3,
}

/// <summary>FR : correspondance cas racine → sens. EN : root case → direction mapping.</summary>
public static class DirectionMap
{
    /// <summary>
    /// FR : `jsq` envoyé sur le champ racine 1 au lieu de 3 laisse le personnage bloqué au bord de
    ///      la carte DÉFINITIVEMENT (Jondo §5.3). Le cas racine n'est donc pas décoratif.
    /// EN : `jsq` sent on root field 1 instead of 3 leaves the character stuck at the map edge
    ///      FOREVER (Jondo §5.3). The root case is therefore not decorative.
    /// </summary>
    public static Direction Of(RootCase rootCase) => rootCase switch
    {
        RootCase.Push => Direction.S2C,
        RootCase.Request => Direction.C2S,
        RootCase.Answer => Direction.S2C,
        _ => throw CodecException.At(
            CodecErrorCode.RootCaseMissing, -1, $"cas racine inconnu / unknown root case {(int)rootCase}"),
    };
}
