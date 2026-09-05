# Journal — J-3 : le client atteint l'écran de sélection de serveur

> Étage 3, jour 2. Reprend `DAG.md` J3.1. La phase de connexion **nue**, sans enveloppe.
> Source : `server/SOCLE-JOUR-2.md` §C.3 · `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:281-357`
> · `refs/JondoEmu/datos/protocolo_conexion_3.6.10.10.proto:163-178` ·
> `codec/CODEC.md:196-208` · le résultat de J-1 · J-2.

## Decided

- **Deux phases, deux connexions, c'est le protocole qui l'impose.** Le client ferme la connexion et en
  rouvre une entre la sélection de serveur et le jeu — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:344-357`.
  Ce n'est pas un choix d'architecture, c'est une contrainte mesurée.
- **La phase nue n'a pas d'enveloppe.** Le codec de l'étage 2 la **refuse nommément**, exprès —
  `codec/CODEC.md:196-203`. Ce qui s'y applique tel quel : la lecture des entiers
  variables, la délimitation de trames et le lecteur générique. Ce qui est à écrire : un second
  analyseur d'enveloppe, et lui seul.
- **La racine porte TROIS champs.** Le serveur de référence n'en implémente que deux ; le troisième
  doit être **parsé sans planter**, même vide — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:906-913`,
  exigence reprise dans `server/INTERFACES.md:105-108`.
- **Le ticket vit en base, avec durée de vie courte et usage unique atomique.** Une seule instruction
  porte l'atomicité, l'unicité et l'expiration — `ARCHITECTURE.md:126-135`.
- **L'identifiant de requête est LU et réinjecté, jamais codé en dur.** 98,9 % des requêtes portent la
  même valeur ; les 1,1 % restantes casseraient en silence — `INTERFACES.md:109-111`.
- **Deux ports plutôt qu'un multiplexage.** Décision tranchée, avec son repli nommé en une ligne de
  configuration si le client ignore le champ d'adresse — `DECISIONS.md` D-03, `ARCHITECTURE.md:143-149`.

## Rejected

- **Multiplexer les deux phases sur un port unique** en détectant la phase sur le contenu de la
  première trame, comme le serveur de référence : deux protocoles incompatibles dans le même chemin de
  code. Repli conservé, pas retenu par défaut.
- **Copier l'omission du troisième champ racine.** Elle est mesurée chez la référence et documentée
  comme une omission, pas comme une propriété du protocole.
- **Construire une trame depuis une capture rejouée.** Les captures servent de preuve de round-trip au
  codec, jamais de contenu à émettre.

## Risks

- **L'écran s'affiche parce que le client a repris une session en cache.** Signal : le succès n'est pas
  reproductible sur un profil neuf. Remède : la gate exige un profil neuf.
- **Le client n'arrive jamais jusqu'à nous** parce que J-1 n'est pas tranché. Signal : aucune connexion
  établie vers notre port. Remède : ce jalon a une gate à trois niveaux et les deux premiers (bot,
  décodage croisé) se jouent **sans** le client vivant. On ne bloque pas dessus.
- **Un identifiant de requête codé en dur parce que la valeur fréquente marche.** Une corroboration sur
  la plage fréquente ne valide pas la plage rare. Signal : la valeur apparaît comme littéral.
- **Le second analyseur d'enveloppe recopié depuis le premier.** Il n'a pas la même forme ; un copier
  coller qui « marche » sur les premières trames masque la différence.

## Files

- **Écrire** : `server/src/Namaste3.Connect/`, plus le second analyseur d'enveloppe dans
  `server/src/Namaste3.Protocol/`
- **Lire, jamais écrire** : `codec/`, `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md`,
  `refs/JondoEmu/datos/`
- **Toucher via son écrivain seulement** : `server/src/Namaste3.Store/` pour le ticket

## Remaining

- Le format exact de l'adresse transmise au client dépend du résultat de J-1. Tant qu'il n'est pas
  tranché, ce jalon se ferme sur ses deux premiers niveaux de gate et laisse le troisième ouvert,
  **explicitement**, plutôt que de se déclarer vert.
- Critère de fermeture complet : le client officiel non modifié affiche l'écran de sélection avec le
  nom de notre serveur, journal sans exception, et une connexion établie visible côté réseau.
