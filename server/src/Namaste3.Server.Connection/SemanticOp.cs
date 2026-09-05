// ============================================================================================
// QUOI : les noms SÉMANTIQUES stables du protocole 3.0. C'est le SEUL vocabulaire que le code
//     connaît ; l'opcode 3 lettres du fil n'apparaît jamais ici, il arrive par la table de
//     liaison (`protocol/binding-<build>.json`).
// POURQUOI (05/09/2026) : l'opcode 3 lettres EST le nom de classe obfusqué du client, re-brassé
//     à chaque build — mesuré, le matcher structurel ne réapparie que 245 messages sur 2169
//     (11,3 %) entre 3.6.4.3 et 3.6.10.10. Un opcode écrit dans du C# ferait d'un patch client
//     une réécriture du serveur (DECISIONS.md D-08).
// EN : the STABLE semantic names of the 3.0 protocol. The only vocabulary the code knows; the
//     3-letter wire opcode never appears here, it comes from the binding table.
// COMMENT LANCER / USAGE : type de données pur, aucun point d'entrée.
// GATE : `gate-serveur.sh` refuse tout littéral de 3 lettres minuscules dans src/.
// ============================================================================================

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : un nom sémantique. Il est stable à travers les builds du client ; c'est la table de
///      liaison qui dit quel opcode le porte dans CETTE build, et `Unbound` dit lesquels
///      manquent — un manque est un état normal, nommé, jamais une devinette.
/// EN : a semantic name. Stable across client builds; the binding table says which opcode
///      carries it in THIS build, and `Unbound` names the missing ones.
/// </summary>
public enum SemanticOp
{
    /// <summary>Inconnu — jamais émis, sert de valeur de refus. / Unknown, never emitted.</summary>
    None = 0,

    // ---- Phase 2, entrée : présentation du ticket -------------------------------------------
    /// <summary>C2S — le client présente le ticket obtenu en phase 1. / Ticket presentation.</summary>
    AuthTicket,
    /// <summary>C2S — accompagne le ticket ; SENS INCONNU de nos sources. / Unknown companion.</summary>
    AuthTicketCompanion,

    // ---- Phase 2, la rafale de bienvenue (ordre exact) ---------------------------------------
    /// <summary>S2C — ticket accepté, vide. / Ticket accepted, empty.</summary>
    AuthTicketAccepted,
    /// <summary>S2C — cadence de synchro + horloge serveur. / Sync rate + server clock.</summary>
    BasicTime,
    /// <summary>S2C — salutation de partie. / Game hello.</summary>
    HelloGame,
    /// <summary>S2C — liste empaquetée des fonctionnalités optionnelles. / Optional features.</summary>
    ServerOptionalFeatures,
    /// <summary>S2C — trois drapeaux, SENS INCONNU. / Three flags, unknown meaning.</summary>
    BurstFlagsTriple,
    /// <summary>S2C — paire de sous-messages, un seul émis vide. / Pair, one emitted empty.</summary>
    BurstPairEmpty,
    /// <summary>S2C — un drapeau, SENS INCONNU. / One flag, unknown meaning.</summary>
    BurstFlagSingle,
    /// <summary>S2C — marqueur vide, SENS INCONNU. / Empty marker, unknown meaning.</summary>
    BurstEmptyMarker,
    /// <summary>S2C — marque du catalogue de contenu, valeur opaque. / Content catalogue mark.</summary>
    ContentCatalogVersion,
    /// <summary>S2C — émis TROIS fois avec trois charges différentes. / Emitted THREE times.</summary>
    BurstCounterPair,
    /// <summary>S2C — la liste des personnages. / The character list.</summary>
    CharactersList,
    /// <summary>S2C — fin de la liste ; son absence bloquait le client. / End of list.</summary>
    CharactersListEnd,
    /// <summary>S2C — liste des cadeaux, émise vide. / Gift list, emitted empty.</summary>
    GiftsList,

    // ---- Phase 2, sélection de personnage -----------------------------------------------------
    /// <summary>C2S — clic sur un personnage ; l'id est en champ 1. / Selection, id in field 1.</summary>
    CharacterSelection,
    /// <summary>C2S — après création ; l'id est en champ 2, PAS 1. / First selection, id in field 2.</summary>
    CharacterFirstSelection,
    /// <summary>S2C — personnage sélectionné avec succès. / Character selected successfully.</summary>
    CharacterSelectedSuccess,

    // ---- Phase 2, entrée monde -----------------------------------------------------------------
    /// <summary>C2S — le client a digéré le bloc d'identité. / Client digested the identity block.</summary>
    GameContextCreateRequest,
    /// <summary>C2S — battement de cœur applicatif. / Application heartbeat.</summary>
    BasicPing,
    /// <summary>S2C — réponse au battement, sur le cas racine 1. / Heartbeat answer, root case 1.</summary>
    BasicPong,
    /// <summary>S2C — la carte courante. / The current map.</summary>
    CurrentMap,
    /// <summary>S2C — cartes découvertes ; voyage avec la carte courante. / Discovered maps.</summary>
    MapDiscovered,
    /// <summary>C2S — le client demande qui est sur la carte. / Client asks who is on the map.</summary>
    WorldEntryRequests,
    /// <summary>S2C — la carte est chargée ; sans lui le client attend. / Map loaded.</summary>
    MapLoaded,
}
