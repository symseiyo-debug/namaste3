# Journal — J-6 : entrée sur la carte d'Astrub

> Étage 3, jour 2. Reprend `DAG.md` J3.4. Le jalon qui consomme la géométrie extraite cette nuit.
> Source : `server/SOCLE-JOUR-2.md` §C.6 · `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:545-670`
> · `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:239-312` · `tools/community/cartes/RAPPORT-CARTES.md`
> · J-5.

## Decided

- **La géométrie est là, et elle est à nous.** 17 353 cartes × 560 cellules × 17 champs, extraites de
  nos propres bundles et corroborées par égalité d'ensemble contre une source produite hors de notre
  chaîne — `tools/community/cartes/RAPPORT-CARTES.md:10-16` et `:204-216`. Ce jalon **n'est plus bloqué**.
- **Astrub porte 560 cellules dont 360 marchables**, une sous-zone non nulle, et ses 4 voisins mesurés
  dans le bundle — `tools/community/cartes/RAPPORT-CARTES.md:78-96` et `:116-120`.
- **Le nombre 560 est sourcé dans le dump**, pas seulement mesuré : une constante déclarée deux fois de
  façon indépendante — `tools/community/cartes/RAPPORT-CARTES.md:68-71`.
- **Le bloc carte s'envoie UNE fois par entrée, par construction.** L'envoyer deux fois fait boucler le
  client sur un rechargement du monde — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:610-611`.
- **Une sous-zone nulle fait REFUSER l'émission**, avec trace, plutôt qu'émettre un message qui plante
  le client — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:641-643`.
- **Sept sites appellent le message de découverte, toujours dans le même ordre** —
  `internal/COMPLEMENT-CHEMIN-CRITIQUE-G1.md:239-312`. Sans lui, la fenêtre de voyage du client
  reste vide.

## Rejected

- **La valeur « 230 cellules marchables ».** C'est un compte **rogné**, produit par un masque de spawn
  de monstres qui coupe les bords exprès — `refs/JondoEmu/docs/world.md:48`. Le serveur de référence
  refuse lui-même de s'en servir pour la marchabilité —
  `refs/JondoEmu/Jondo.Unity.Server/Handlers/WorldMoveHandler.cs:442-445`. Une gate bâtie dessus
  refuserait un extracteur correct.
- **Recopier les drapeaux de cellule du format 2.x.** Deux builds, deux mondes : rien ne s'y porte
  structurellement (cahier L4).
- **Rejouer les captures du serveur de référence comme contenu à émettre.** Elles portent des données
  de compte tiers et servent de preuve de round-trip au codec —
  `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:957-961`. Un message construit depuis une trame
  rejouée serait un faux vert : le client entre en jeu, et rien de notre serveur n'a été prouvé.
- **Une table de voisinage de cellules.** Les voisins se calculent géométriquement —
  `ARCHITECTURE.md:304-306`.

## Risks

- **Allouer un tableau de 230 cellules.** Les identifiants montent jusqu'à 559 ; le tableau plante au
  premier identifiant réel. Signal : une constante 230 dans le code. C'est le piège que J-0 corrige
  dans trois documents.
- **La minimap vide.** Signal : la fenêtre de voyage du client affiche l'absence de destination.
  Cause connue : le message de découverte n'a pas été envoyé.
- **Un import vert sur zéro carte.** Signal : la gate ne compte pas les lignes. Remède : Astrub est
  vérifiée nommément, avec ses 4 voisins et ses 360 marchables.
- **27 cartes portent un schéma de cellule plus ancien**, à 16 champs au lieu de 17 — mesuré,
  `tools/community/cartes/RAPPORT-CARTES.md:169`. Le champ absent est écrit vide, **jamais faux**, ce qui
  fabriquerait une valeur. Le socle doit tolérer le vide sans le confondre avec un non.

## Files

- **Écrire** : `server/src/Namaste3.Net/` (le bloc carte, la structure d'acteurs),
  `server/src/Namaste3.World/` (l'entrée dans l'Area)
- **Lire, jamais écrire** : `tools/community/cartes/sortie/`, `internal/`, `refs/JondoEmu/`

## Remaining

- Le sens de deux champs de cellule reste inconnu : les méthodes qui les lisent existent, leur corps
  n'est pas décompilé — `tools/community/cartes/RAPPORT-CARTES.md:282-284`. Sans conséquence pour ce
  jalon ; à lever quand le changement de carte arrivera.
- 15 cartes divergent de la source de corroboration, **toutes dans un bundle hors catalogue**, et
  l'écart est un défaut de l'autre instrument, mesuré — `tools/community/cartes/RAPPORT-CARTES.md:218-233`.
  Astrub n'en fait pas partie.
- Critère de fermeture : l'introspection du bot rend la bonne carte, la bonne cellule et la bonne
  phase ; le double envoi est refusé avec trace et 0 boucle côté client ; une sous-zone nulle fait
  refuser l'émission ; le personnage apparaît à Astrub avec sa minimap peuplée.
