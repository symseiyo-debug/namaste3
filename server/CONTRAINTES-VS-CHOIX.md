# CONTRAINTES HÉRITÉES vs CHOIX — table comparative (étage 3)

> # 🟡 v0 — À REMPLACER PAR LA SORTIE DU GRAPHE
>
> Extrait de `ARCHITECTURE.md` §8 le 04/09 pour tenir la règle du projet des fichiers < 500 lignes,
> après l'ajout de la section §0 (lois L4/L5/L6). **Ce n'est pas un retrait de périmètre** : la
> section reste due, elle vit dans son propre fichier et `ARCHITECTURE.md` §8 y renvoie.
> **Sources lues** : les mêmes que `ARCHITECTURE.md`.
>
> Cette table est celle que le **graphe comparatif** calcule mécaniquement (arêtes
> `ÉQUIVALENT`/`INVARIANT`/`DIVERGENT`/`ÉVOLUTION`, cahier §2). Quand il répondra, elle se
> **remplace** par sa sortie — elle ne se complète pas.


> **v0 — la section la PLUS dépendante de la carte, et de loin.** Un « invariant » se calcule sur le
> corpus **complet** : l'affirmer sur trois fragments d'archi quand d'autres passes en produiront des dizaines,
> c'est généraliser depuis un échantillon. Ferme sur **tous** les fragments de `internal/reference-fragments/` et
> `internal/third-party-review/` (7 livrés, corpus final inconnu) et sur le **graphe comparatif**, dont c'est
> exactement le rôle : ses quatre arêtes `ÉQUIVALENT`/`INVARIANT`/`DIVERGENT`/`ÉVOLUTION` (cahier §2)
> calculent cette table **mécaniquement**, là où je l'ai écrite à la main. Chaque ligne « INVARIANT »
> ci-dessous est donc une hypothèse à la mesure du corpus lu, pas un verdict. Quand le graphe
> répondra, cette table se **remplace** par sa sortie — elle ne se complète pas, deux tables qui
> divergeraient seraient pires qu'une seule.

**Règle du cahier** (§2 étage 1, graphe comparatif) : ce que TOUS les émulateurs font est une
contrainte du protocole, obligatoire. Ce qu'un seul fait est un choix d'auteur, libre. *On hérite des
contraintes, pas des solutions.*

### 8.1 INVARIANTS — présents partout, donc obligatoires

| Invariant | Où c'est mesuré |
|---|---|
| Phase de connexion séparée de la phase de jeu, jointes par un **ticket éphémère à usage unique** | Jiva §A.4 (3→5, ticket CSPRNG 24 o, retiré du cache à la consommation) · Jondo `:344-357, 369-382` · Giny (Auth/World) |
| **Dispatch par table**, construite au démarrage par réflexion sur un attribut | Jiva §D (`HandlerManager<...>`, `Dictionary<uint,…>`) · Giny §C.2 (`ProtocolMessageManager`) |
| Clé de déplacement = **12 bits cellule + direction** | Jiva §B.4 · Giny §C.3/§F.1 · Jondo 3.0 `:677` |
| Diffusion à **la map entière**, jamais un rayon de vision | Jiva §B.5 (`CanBeSee` = même map) · Jondo (`BroadcastToMapAsync`) |
| **Le serveur fait foi** sur la position ; le client n'est pas fiable | Jiva §B.4 · Giny §C.3 · Jondo `:679-682` et `:731-733` (le client demande une carte voisine qui n'existe pas) |
| Le protocole se **régénère** depuis le client à chaque version | Symbioz 2018 §A.4 · Giny 2026 §A.3 |

### 8.2 CHOIX — un seul le fait, on prend et on dit pourquoi

| Choix (chez qui) | Pourquoi on le prend |
|---|---|
| **Area mono-thread** (Jiva §B.1) | l'alternative mesurée (Giny §B.1-B.2) porte une course documentée et un commentaire qui affirme une garantie fausse |
| **Le handler dérive son opcode du type de son paramètre** (Giny §C.2) | supprime une classe d'erreur entière : le handler ne peut pas mentir sur l'opcode qu'il traite |
| **Dette interrogeable par attribut** (Giny §G.2) | énumérable par un outil, contrairement aux 4 tags en commentaire de Jiva |
| **Modules chargés à part** (Giny §G.4) | garde le cœur séparé de ce qu'on ajoute — reporté étage 5 |
| **Synchronisateur de fin de tour tolérant au lag** (Giny §D.2) | les deux issues sont deux chemins nommés — reporté au combat |
| **5 natures de dette de portage** (Jiva §F.1) | vocabulaire éprouvé sur un cycle de version réel — sert l'étage 4 |
| **Conception ouverte**, pas de `sealed` sur le domaine (Giny §G.5 : 1 sur 2881 fichiers, contre 131 chez Jiva) | le livrable est repris par d'autres (cahier étage 5) |

### 8.3 PERSONNE ne le fait — c'est à nous de le concevoir

**Anti-triche déplacement complet** (§6.1) · **des tests** — Giny a 0 fichier de test et 0 `.csproj`
référençant xUnit/NUnit/MSTest (§G.1), notre preuve est le bot déterministe déjà livré
(`internal/bot-testeur/SPEC.md:172-192`) · **fichiers < 500 lignes** — mesuré `Character.cs` 4637
et `Map.cs` 2095 chez Jiva (§E.5), `Fighter.cs` 2721 chez Giny (§F.3) · **isolation cœur/protocole**
— 72,5 % chez Giny (§G.3), notre cible est 0 % dans le domaine (§0.2, §2).

---

