# Journal — J-0 : solder les rouges bon marché

> Étage 3, jour 2. Aucune IA payée : trois gestes scriptés.
> Source : `server/SOCLE-JOUR-2.md` §C.0 et §A.2 (gates relancées le 04/09 à 22:xx UTC).

## Decided

- **Trois refus mesurés, trois corrections, aucune discussion.**
  1. Trois adresses d'opcode figées en dur dans les tests du codec —
     `codec/tests/Namaste3.Codec.Tests/NegativeTests.cs:164`, `:181`, `:335`. Sortie
     prescrite par l'outil lui-même : lire l'adresse dans la table générée
     (`protocol/extract/proto-sync/out/`) au lieu du littéral.
  2. Neuf fragments rouges à `gate-forme.py` : 3 en-têtes de document incomplets (titre, mention
     d'étage, mention de source dans les 15 premières lignes), 5 sources manquantes sur une entrée
     taguée, 1 dossier cité sans barre oblique finale.
  3. La valeur « 230 cellules marchables » périmée dans trois fichiers : `ARCHITECTURE.md:271-284`,
     `DAG.md:208-210`, `INTERFACES.md:279`. Mesure de remplacement : 560 cellules dont **360**
     marchables sur Astrub, plus les deux égalités d'ensemble exactes (357 et 85) contre
     `refs/JondoEmu/datos/map_fight_cells.json` — `tools/community/cartes/RAPPORT-CARTES.md:50-66`.
- **Un seul écrivain par zone.** La correction du codec appartient à l'auteur du codec ; celle des
  fragments à leurs auteurs ; celle des trois documents d'architecture à l'architecte de l'étage 3.
  Quiconque bute sur une forme refusée **rapporte, il n'édite pas** `gate-forme.py` (cahier §4).

- **Un quatrième geste, apparu à 22:50 : réconcilier les DEUX tables qui nomment des opcodes.**
  `protocol/extract/proto-sync/out/dispatch-3.6.10.10.json` porte 2 206 messages générés depuis le dump ;
  `server/protocol/binding-3.6.10.11.json` porte 25 messages du chemin critique **plus la
  charge exacte à émettre**, que la première n'a pas. Les deux se déclarent « le seul fichier qui nomme
  des opcodes ». Elles sont complémentaires, pas contradictoires — mais deux producteurs de la même
  chose divergent tôt ou tard. **Ce geste se fait AVEC l'écrivain du serveur de connexion**, qui
  travaille dans cette zone en ce moment, jamais à sa place.
- **Et déclarer le statut des cinq noms de commodité de la seconde table.** Les messages de la rafale
  que personne n'a nommés y reçoivent des étiquettes de place. Un nom de commodité qui a la forme d'un
  nom sémantique se cite ensuite comme s'il était mesuré. La table de proto-sync marque ses 1 463
  entrées sans nom ; celle-ci doit marquer ses cinq. Croiser avec
  `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv`, qui les liste précisément comme sans nom.

## Rejected

- **Retirer `krt` de `internal/chemin-critique.txt` pour faire verdir G1.** Ce serait rendre
  l'instrument vert par l'instrument. `DAG.md:95-97` le nomme déjà comme piège. Le sens de `krt` se
  mesure par une capture, il ne se supprime pas.
- **Supprimer les entrées taguées pour faire verdir `gate-forme.py`.** Même faute, un cran plus bas :
  une entrée sans source se corrige en lui ajoutant sa source, jamais en la retirant.
- **Ajouter une exception « fichier connu » à une gate.** Un écart reste un écart : il se nomme et se
  compte. C'est ce que fait déjà la gate des cartes sur ses 15 écarts.

## Risks

- **Le codec est une zone vivante.** Modifier ses tests pendant qu'un autre chantier y travaille produit
  une collision silencieuse. Signal : la gate du codec passe de rc=0 à rc≠0 sans qu'on ait touché au
  cœur. Remède : signaler à l'auteur, ne pas éditer si sa zone est active.
- **Les fragments bougent sous la mesure.** Deux passes à 20 minutes d'écart n'ont pas rendu le même
  ensemble de rouges le 04/09 au soir. Signal : un fichier rouge dans la liste est déjà vert quand on
  l'ouvre. Remède : remesurer juste avant de corriger, et remesurer après.
- **Corriger la valeur 230 dans un seul des trois fichiers.** Une leçon appliquée localement ressemble
  à une leçon apprise. Signal : une recherche de « 230 » dans `server/` rend encore quelque
  chose après la passe.

## Files

- Zone codec, écrivain = l'auteur du codec : `codec/tests/Namaste3.Codec.Tests/NegativeTests.cs`
- Zone étage 1, écrivain = l'auteur de chaque fragment : les 9 fichiers nommés par
  `gate-forme.py` à la relance du matin
- Zone étage 3, écrivain = l'architecte : `server/ARCHITECTURE.md`, `server/DAG.md`,
  `server/INTERFACES.md`
- **Interdit d'écrire** : `tools/protocol-mapping/tools/gate-forme.py`, `protocol/extract/proto-sync/out/`,
  `internal/GATE-G0-RAPPORT.md`

## Remaining

- La gate des commentaires reste rouge sur 16 fichiers, dont 10 du bot-testeur. **Hors de cette
  passe** : c'est la zone de l'auteur du bot, et la question est ouverte
  (`server/OPEN-QUESTIONS.md`, question 5). Défaut retenu : non bloquant, compté et affiché.
- Critère de fermeture de J-0 : `gate-proto-sync.py --epreuve` rend rc=0, `gate-forme.py` sur les 64
  fragments rend 0 rouge, et une recherche de « 230 » dans `server/` ne trouve plus de
  cellule marchable.
