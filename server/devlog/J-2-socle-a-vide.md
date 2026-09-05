# Journal — J-2 : le socle qui tourne à vide

> Étage 3, jour 2. Les six projets, le chargeur de table, l'import des cartes. **Zéro handler métier.**
> Source : `server/SOCLE-JOUR-2.md` §B et §C.2 · `server/ARCHITECTURE.md` §2, §4, §7 ·
> `server/INTERFACES.md` §1, §3, §4, §5, §6 · `protocol/extract/proto-sync/PROTO-SYNC.md` ·
> `tools/community/cartes/RAPPORT-CARTES.md`. Reprend `DAG.md` J3.C, plus le chargeur de J3.A et
> l'import de J3.B, qui ne sont plus bloqués.

## Decided

- **L'arborescence est arrêtée** : `SOCLE-JOUR-2.md` §B.1. Six projets, plus un dossier `protocol/`
  qui porte une **donnée**, pas du code.
- ⚠️ **Le projet de connexion EXISTE DÉJÀ et a son écrivain.** Mesuré à 22:50 UTC : 10 fichiers dans
  `server/src/Namaste3.Server.Connection/`, plus un générateur et sa table dans
  `server/protocol/`. Ce jalon **s'aligne sur lui**, ne le renomme pas, n'écrit pas dans sa
  zone. Le premier geste est de convenir avec lui du partage, pas de poser une arborescence par-dessus
  la sienne — c'est exactement ce que l'anti-drift du cahier §6 interdit.
- **Deux tables nomment des opcodes, et il faut trancher leur composition** avant que le socle en
  charge une. Le détail est dans `server/devlog/J-0-dettes.md`. Le socle ne charge pas deux
  tables « au cas où » : il en charge une, et sait laquelle.
- **Le codec est référencé, jamais recopié.** `codec/` a son écrivain ; son API pour
  l'étage 3 est fixée à `codec/CODEC.md:212-255`.
- **La table de dispatch est produite, le format est celui de l'outil.** 2 206 entrées, chacune avec
  sa source dans le dump, sa direction et son statut de nom — `protocol/extract/proto-sync/PROTO-SYNC.md:106-119`.
  Le chargeur **s'aligne sur la table**, jamais l'inverse. L'indexation est le travail du chargeur : le
  fichier généré est une classe de données sans logique, et sa gate le vérifie.
- **Le chargeur est petit et son absence est nommée** : « ~50 lignes, et c'est le seul chaînon manquant
  côté code » — `protocol/extract/proto-sync/PROTO-SYNC.md:222-224`.
- **L'import des cartes se fait depuis nos propres fichiers extraits**, pas depuis un fichier dérivé
  d'un tiers : 17 353 cartes, 560 cellules, 17 champs — `tools/community/cartes/RAPPORT-CARTES.md:315-322`.
- **Les six frontières du §B.2 sont des gates, pas des intentions.** Chacune est un compte qui doit
  valoir 0 ou une liste qui doit être vide.
- **Le garde d'Area est un TYPE, pas un contrôle à l'exécution** — `DECISIONS.md` D-04. Sa gate compile
  du code fautif et **exige l'échec**, puis compile le même code conforme et exige le succès.
- **Une sous-zone est NON NULLE en base.** Un zéro fait planter le client —
  `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:641-643`. La contrainte est dans le schéma, pas dans
  un contrôle applicatif.

## Rejected

- **Reprendre un canal applicatif entre les deux processus.** Quatre défauts mesurés y sont attachés
  chez les références ; une consommation atomique en base porte les trois propriétés du ticket en une
  instruction — `DECISIONS.md` D-02, `ARCHITECTURE.md:120-141`.
- **Un cache mémoire de ticket** comme chez Jiva : il interdit toute instance multiple et ne survit pas
  à un redémarrage, et son propre fragment le signale.
- **Une table normalisée de cellules.** Un bloc par carte, les voisins calculés géométriquement —
  patron mesuré, `ARCHITECTURE.md:304-306`.
- **Réécrire le lecteur de bundles.** Il est prouvé et réutilisé tel quel par l'extracteur des cartes.
- **Activer les politiques de sécurité de ligne dès la première migration.** Hors cadrage du brief ;
  mais la colonne de portée est présente **dès la première migration**, non contrainte, pour que les
  activer plus tard soit une migration de politique et pas de schéma — `ARCHITECTURE.md:320-323`.

## Risks

- **Le socle déclaré vert sur une compilation réussie.** Le compilateur ne ferme aucun nœud (cahier §6).
  Signal : un rapport qui dit « ça compile » sans nommer une gate. Remède : les six mesures du §B.2,
  chacune avec son chiffre.
- **La gate du garde d'Area écrite en assertant son NOM.** Un garde asserté par son nom est toujours
  vert. Signal : la gate ne compile rien. Remède : contrôle positif ET négatif dans la même exécution.
- **Le chargeur qui invente un index.** La table est une donnée plate ; un chargeur qui la « corrige »
  au passage fabrique une table qui n'est celle d'aucune build. Signal : le chargeur écrit dans
  `protocol/`.
- **Un import de cartes vert sur zéro carte.** Signal : la gate ne compte pas les lignes écrites.
  Remède : la carte d'Astrub est vérifiée nommément, avec ses 4 voisins et ses 360 marchables.
- **Deux chantiers dans le même projet.** Signal : un fichier modifié depuis deux fronts différents. Remède : les
  périmètres ci-dessous sont disjoints par projet.

## Files

- **Lot 1 — architecture du socle** : `server/Namaste3.sln`,
  `server/src/Namaste3.Protocol/`, `server/src/Namaste3.Net/`,
  `server/tools/`
- **Lot 2 — domaine et persistance** : `server/src/Namaste3.World/`,
  `server/src/Namaste3.Store/`
- **Lot 3 — hôtes et import** : `server/src/Namaste3.Connect/`,
  `server/src/Namaste3.World.Host/`, l'import des cartes
- **Lire, jamais écrire** : `codec/`, `protocol/extract/proto-sync/out/`,
  `tools/community/cartes/sortie/`, `internal/`
- **Copier une fois, ne jamais éditer** : la table de dispatch vers `server/protocol/`

## Remaining

- Le schéma de la trace causale doit être **le même** que celui de l'index causal existant du projet, sinon la trace du bot, celle du
  serveur et celle du graphe ne se joignent pas — `ARCHITECTURE.md:450-453`. Question 4 de
  `server/OPEN-QUESTIONS.md`. Défaut si pas de réponse : on écrit le schéma que le bot produit
  déjà (`internal/bot-testeur/SPEC.md:55-57`), qui est le seul point d'accord existant.
- Les 1 463 messages sans nom sémantique restent sans nom. Le socle n'en a pas besoin : il route par
  adresse et n'expose de nom que là où il en existe un.
- Critère de fermeture : les six comptes du §B.2 valent ce qu'ils doivent valoir, l'import a écrit
  17 353 cartes, et le processus démarre en journalisant les messages déclarés qui manquent à cette
  build plutôt qu'en devinant.
