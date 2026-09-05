# Journal — J-5 : sélection de personnage

> Étage 3, jour 2. Reprend `DAG.md` J3.3. Le premier jalon où l'anti-triche compte vraiment.
> Source : `server/SOCLE-JOUR-2.md` §C.5 · `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:144-235`
> · `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:434-541` · J-4.

## Decided

- **L'appartenance du personnage se vérifie EN BASE**, jamais sur ce que le client annonce. Le contrat
  l'inscrit dans la signature elle-même : la méthode de chargement prend le compte et le personnage
  ensemble, il n'existe pas de chargement sans compte — `server/INTERFACES.md:300-304`.
- **Trois formes de message, trois déclarations différentes, trois lectures différentes.** Les trois
  sont mesurées dans le `.proto` reconstruit, chacune avec sa ligne —
  `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:179-227`. Le handler de la deuxième forme lit son
  **second** champ, jamais le premier.
- **L'autorité de forme est notre dump, puis le `.proto` reconstruit ; jamais celui écrit à la main** —
  `DECISIONS.md` D-09, `ARCHITECTURE.md:370-379`.

## Rejected

- **La lecture générique du serveur de référence**, qui lit le même numéro de champ et le même type
  pour les trois formes. Sur l'une, cela lit un booléen comme un identifiant ; sur l'autre, une
  énumération valant 0 ou 1. Les trois sont des entiers variables : **ça compile, ça décode, et ça
  charge le personnage n°1 ou rien** — `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:179-227`.
  C'est le cas d'école « le type est bon, la source est fausse ».
- **Faire confiance à l'identifiant envoyé par le client** sans vérifier à qui il appartient.

## Risks

- **La gate adversariale verte parce que le compte de test n'a qu'un personnage.** Signal : un seul
  compte peuplé dans le jeu de données. Remède : **deux comptes peuplés**, exigé par la gate.
- **Un refus produit par une autre barrière.** Si le personnage d'un autre compte est refusé parce
  qu'il n'existe pas en base plutôt que parce qu'il n'appartient pas au compte, le test passe pour la
  mauvaise raison. Signal : le motif du refus n'est pas celui attendu. Remède : le motif est nommé et
  comparé, pas seulement le fait du refus.
- **Une des trois formes non exercée.** Signal : la gate ne teste qu'une forme. Remède : les trois,
  chacune contre sa propre déclaration.

## Files

- **Écrire** : `server/src/Namaste3.Net/` (les trois handlers),
  `server/src/Namaste3.World/` (le chargement du personnage)
- **Lire, jamais écrire** : `internal/`, `refs/JondoEmu/datos/`

## Remaining

- Une des trois formes reste sans nom sémantique (`tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv`).
  Même remarque qu'en J-4 : à nommer par capture, pas à contourner.
- Critère de fermeture : le bot passe la phase ; l'identifiant d'un autre compte rend un refus nommé
  avec 0 chargement et 1 trace, contrôle positif dans la même exécution ; les trois formes sont
  décodées chacune selon sa déclaration ; le client vivant sort de l'écran des personnages.
