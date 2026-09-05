# Journal — J-4 : ticket, rafale de bienvenue, écran des personnages

> Étage 3, jour 2. Reprend `DAG.md` J3.2. La seconde connexion, l'enveloppe, et la séquence d'accueil.
> Source : `server/SOCLE-JOUR-2.md` §C.4 · `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:367-456`
> · `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:20-140` · `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv`
> · J-3.

## Decided

- **Quinze messages, dans un ordre exact, mesuré.** Trois d'entre eux partagent le même opcode avec des
  charges **différentes** — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:404-421`. L'ordre fait
  partie du contrat, pas la seule liste.
- **Les cinq types de champ qui manquaient sont mesurés** et disponibles —
  `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:57-140`.
- **La consommation du ticket est atomique, et son refus est NOMMÉ.** Rejouer le même ticket ferme la
  connexion avec un motif et une ligne de trace, jamais un silence.
- **`krt` est toléré sans être jeté en silence, et sa charge est CAPTURÉE ce jour-là.** C'est le seul
  refus de G1 (mesuré ce soir : 32/32 couverts, 31/32 conformes) et le serveur de référence ne
  l'implémente pas — quatre de ses tables répètent la même absence,
  `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:22-53`. Il ne se lève que par une capture.
- **Huit opcodes du chemin critique n'ont aucun nom sémantique**, dont six dans cette rafale. Le cahier
  des charges de la capture existe déjà, avec pour chacun sa position de séquence et ses voisins —
  `tools/protocol-mapping/matcher/A-NOMMER-PAR-CAPTURE.tsv`. Ce jalon est **l'occasion de les nommer**, pas
  seulement de les émettre.

## Rejected

- **Rejouer les fixtures du serveur de référence comme contenu à émettre.** Mesuré par le codec : la
  fixture qu'on croyait porter la rafale n'en porte qu'un seul opcode sur treize, parce que la rafale
  est **construite en code** et n'a jamais été capturée ici — `codec/CODEC.md:132-143`.
  **Aucune capture de la rafale n'existe sur ce VPS.**
- **Émettre un opcode nommé par une table tierce sans épreuve.** Entre deux tables étiquetées de la
  même build, 84 % des opcodes se collisionnent et **0 accord de sens sur 27 examinés** — un opcode
  venu d'ailleurs est plausible ET faux, la pire des deux propriétés.
- **Écrire un opcode littéral dans un handler.** La gate le mesure ; elle est déjà rouge sur trois cas
  ailleurs.

## Risks

- **La gate d'usage unique verte parce que le ticket n'a jamais été écrit.** Jamais essayé ressemble à
  jamais réussi. Signal : la gate n'a pas de contrôle positif. Remède : ticket frais et ticket rejoué
  dans la **même** exécution.
- **Le succès produit par une barrière voisine.** Si le décodage échoue en silence, le ticket est
  refusé pour la mauvaise raison et le test passe quand même. Signal : un refus sans motif nommé.
- **Un ordre correct obtenu par hasard sur une exécution.** Signal : la gate compare un ensemble, pas
  une liste ordonnée. Remède : comparer la liste ordonnée, 15 sur 15, 0 permutation.
- **Le bouton de création de personnage mort.** Symptôme mesuré chez la référence, imputé à l'absence
  d'un message de la rafale — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:420`. C'est un signal
  utile : s'il est mort chez nous, un message manque.

## Files

- **Écrire** : `server/src/Namaste3.World.Host/`, les constructeurs de messages dans
  `server/src/Namaste3.Net/`
- **Écrire, si la capture réussit** : un fragment de carte pour `krt` et pour les opcodes nommés, dans
  la zone de l'étage 1, **via son écrivain**
- **Lire, jamais écrire** : `internal/`, `codec/`, `protocol/extract/proto-sync/out/`

## Remaining

- Les six opcodes de la rafale sans nom sémantique restent sans nom si la capture n'a pas lieu. Le
  serveur fonctionne quand même — il route par adresse — mais un handler écrit contre un jeton
  obfusqué est faux à la build suivante. **À nommer, pas à contourner.**
- Critère de fermeture : le bot atteint la phase authentifiée avec une liste non vide ; les 15 messages
  sont dans l'ordre ; le rejeu du ticket rend un refus nommé avec contrôle positif ; et le client vivant
  affiche l'écran des personnages avec le bouton de création actif.
