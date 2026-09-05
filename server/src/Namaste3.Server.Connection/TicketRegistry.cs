// ============================================================================================
// QUOI : les tickets de session — émis en phase NUE quand le client choisit un serveur, puis
//     présentés en phase JEU sur la connexion suivante. Usage UNIQUE, expiration bornée.
// POURQUOI (05/09/2026) : le ticket est le SEUL lien entre les deux connexions du client. Deux
//     propriétés le rendent sûr par construction, et aucune n'est un `if` posé sur le chemin :
//     · l'échange est ATOMIQUE (`Redeem` retire avant de rendre) — un ticket rejoué trouve une
//       table vide, il n'y a pas de fenêtre entre « vérifier » et « consommer » ;
//     · l'horloge est INJECTÉE — le cœur ne lit jamais `DateTime.Now`, donc l'expiration est
//       rejouable à la seconde près dans un test, et un témoin négatif la prouve.
//     Un refus est NOMMÉ (`TicketVerdict`) : « ticket vide », « inconnu ou déjà consommé »,
//     « expiré » ne se confondent pas — sinon on ne saurait pas lequel des trois s'est produit
//     devant un client qui reste bloqué.
// EN : session tickets — issued in the NAKED phase, presented in the GAME phase on the next
//     connection. SINGLE use, bounded expiry, ATOMIC redemption, INJECTED clock, NAMED verdicts.
// COMMENT LANCER / USAGE : `new TicketRegistry(horloge, duree)` ; `Issue()` / `Redeem(ticket)`.
// GATE : `NegativeTests` — ticket vide, ticket rejoué et ticket expiré doivent rendre TROIS
//     verdicts DIFFÉRENTS, et un ticket frais doit être accepté (témoin positif).
// ============================================================================================

namespace Namaste3.Server.Connection;

/// <summary>
/// FR : le verdict d'un échange de ticket. Quatre valeurs distinctes : un refus qui ne dit pas
///      lequel des trois motifs l'a causé ne vaut pas mieux qu'un silence.
/// EN : a ticket redemption verdict. Four distinct values: a refusal that does not say which of
///      the three reasons caused it is no better than silence.
/// </summary>
public enum TicketVerdict
{
    /// <summary>Accepté ; la session est liée. / Accepted; the session is bound.</summary>
    Accepted,
    /// <summary>Le client n'a présenté aucun ticket. / The client presented no ticket.</summary>
    Empty,
    /// <summary>Inconnu, ou déjà consommé. / Unknown, or already consumed.</summary>
    UnknownOrConsumed,
    /// <summary>Connu mais périmé. / Known but expired.</summary>
    Expired,
}

/// <summary>
/// FR : ce qu'un ticket porte : le compte et le serveur choisis, plus sa date d'émission.
/// EN : what a ticket carries: the chosen account and server, plus its issue time.
/// </summary>
public sealed record TicketGrant(long AccountId, long ServerId, DateTimeOffset IssuedAt);

/// <summary>
/// FR : le registre. Les noms de tickets viennent d'une source INJECTÉE, pas de `Random` : deux
///      exécutions du même test produisent la même suite, et la production branche une vraie
///      source cryptographique.
/// EN : the registry. Ticket names come from an INJECTED source, not `Random`.
/// </summary>
public sealed class TicketRegistry
{
    private readonly Func<DateTimeOffset> _clock;
    private readonly Func<string> _mint;
    private readonly TimeSpan _lifetime;
    private readonly Dictionary<string, TicketGrant> _live = new(StringComparer.Ordinal);
    private readonly object _gate = new();

    /// <summary>
    /// FR : construit le registre. Aucun défaut caché : l'horloge, la fabrique de noms et la
    ///      durée de vie sont TOUTES des paramètres.
    /// EN : builds the registry. No hidden default: clock, name factory and lifetime are ALL
    ///      parameters.
    /// </summary>
    public TicketRegistry(Func<DateTimeOffset> clock, Func<string> mint, TimeSpan lifetime)
    {
        _clock = clock ?? throw new ArgumentNullException(nameof(clock));
        _mint = mint ?? throw new ArgumentNullException(nameof(mint));
        _lifetime = lifetime;
    }

    /// <summary>FR : combien de tickets vivent. / EN : how many tickets are live.</summary>
    public int LiveCount
    {
        get { lock (_gate) { return _live.Count; } }
    }

    /// <summary>
    /// FR : émet un ticket pour un compte et un serveur. Le nom vient de la fabrique injectée.
    /// EN : issues a ticket for an account and a server; the name comes from the injected mint.
    /// </summary>
    public string Issue(long accountId, long serverId)
    {
        string name = _mint();
        lock (_gate)
        {
            _live[name] = new TicketGrant(accountId, serverId, _clock());
        }

        return name;
    }

    /// <summary>
    /// FR : échange un ticket. ATOMIQUE : le retrait précède le verdict, donc un rejeu ne trouve
    ///      plus rien même si deux connexions arrivent en même temps. Un ticket expiré est
    ///      retiré aussi — le garder ferait grandir la table sans fin.
    /// EN : redeems a ticket. ATOMIC: removal precedes the verdict, so a replay finds nothing
    ///      even under concurrency. An expired ticket is removed too.
    /// </summary>
    public TicketVerdict Redeem(string? ticket, out TicketGrant? grant)
    {
        grant = null;
        if (string.IsNullOrEmpty(ticket))
        {
            return TicketVerdict.Empty;
        }

        lock (_gate)
        {
            if (!_live.Remove(ticket, out TicketGrant? found))
            {
                return TicketVerdict.UnknownOrConsumed;
            }

            if (_clock() - found.IssuedAt > _lifetime)
            {
                return TicketVerdict.Expired;
            }

            grant = found;
            return TicketVerdict.Accepted;
        }
    }
}
