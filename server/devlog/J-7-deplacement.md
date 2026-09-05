# Journal — J-7 : déplacement validé serveur-side

> Étage 3, jour 2. Reprend `DAG.md` J3.5. Le nœud qui n'a **aucune** référence complète.
> Source : `server/SOCLE-JOUR-2.md` §C.7 · `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:672-698`
> · `server/ARCHITECTURE.md` §6.1 · `internal/ARCHI-REFERENCE-JIVA.md` §B.4 ·
> `internal/ARCHI-REFERENCE-GINY.md` §C.3 · J-6.

## Decided

- **Quatre contrôles, tous serveur-side, dès l'écriture initiale.** Carte annoncée, cellule de départ,
  marchabilité de chaque cellule du chemin, contiguïté et budget de pas —
  `server/ARCHITECTURE.md:404-410`.
- **Aucune référence ne les a tous, et c'est mesuré.** Jiva valide la marchabilité mais a **commenté**
  le contrôle de la cellule de départ ; Giny fait l'inverse exact ; le serveur de référence 3.0 vérifie
  la carte et **ignore silencieusement** en cas d'écart —
  `server/ARCHITECTURE.md:396-402`. Les deux derniers contrôles, personne ne les a.
- **« Par construction » veut dire une chose précise** : le type qui porte un chemin n'a **aucun
  constructeur accessible**, et le seul point d'obtention est la validation. Un handler ne peut pas
  appliquer un chemin non validé : il n'en existe pas dans le programme — `DECISIONS.md` D-06.
- **Un refus répond et trace.** Jamais un silence : un joueur figé sans savoir pourquoi est le
  symptôme mesuré chez la référence — `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:679-682`.
- **L'encodage des pas est l'unique invariant que L4 laisse traverser** : il est mesuré des deux côtés,
  sur deux générations et trois émulateurs — `server/ARCHITECTURE.md:424-427`. Il est
  transposé parce qu'il est **mesuré**, pas parce qu'il est pratique.
- **La marchabilité vient de NOTRE extraction**, 560 cellules par carte, pas du fichier dérivé rogné
  (cf. J-6).

## Rejected

- **Le budget de pas repris d'une référence.** Personne ne l'a ; sa valeur n'est sourcée nulle part —
  `server/ARCHITECTURE.md:391-393`. Il est donc posé, nommé, et sa valeur est déclarée
  DÉDUITE tant qu'une capture ne la donne pas. On ne le **retire pas** pour autant : un contrôle
  absent est pire qu'un contrôle dont le seuil est provisoire.
- **Ignorer silencieusement un déplacement à la mauvaise carte**, comme la référence.
- **Un contrôle de sécurité laissé en commentaire.** Soit implémenté, soit supprimé —
  `server/ARCHITECTURE.md:440-444`. Un commentaire de sécurité inactif se lit comme une
  protection.

## Risks

- **Les cinq refus produits par la MÊME barrière.** C'est le risque central de ce jalon. Un test
  adversarial vert peut l'être par une autre barrière que celle qu'on croit mesurer. Signal : les cinq
  scénarios sont refusés mais la trace ne porte qu'un ou deux motifs distincts. Remède : la gate exige
  **cinq motifs NOMMÉS DIFFÉRENTS** et échoue même si tout est refusé.
- **Un chemin fabriqué hors du point de validation.** Signal : une construction directe du type de
  chemin ailleurs que dans le fichier qui le définit. Remède : la gate la compte, et le compte doit
  être 0.
- **Le contrôle de contiguïté vert par accident**, parce que les cellules du scénario sont voisines de
  toute façon. Signal : le scénario de saut n'a jamais de saut réel. Remède : le scénario adversarial
  saute par-dessus au moins une cellule.
- **Le budget de pas jamais exercé.** Signal : aucun scénario ne dépasse le seuil. Jamais essayé
  ressemble à jamais réussi.

## Files

- **Écrire** : `server/src/Namaste3.World/` (le type de chemin et sa validation),
  `server/src/Namaste3.Net/` (le handler et la diffusion),
  `server/tests/` (les cinq scénarios adversariaux)
- **Lire, jamais écrire** : `internal/`, `tools/community/cartes/sortie/`
- **Négocier, ne pas imposer** : l'extension du port du bot pour envoyer un chemin volontairement
  invalide appartient à l'auteur du bot — `server/INTERFACES.md:358-361`

## Remaining

- La valeur du budget de pas reste DÉDUITE. **Comment la lever** : capturer une session réelle et
  mesurer le nombre maximal de cellules d'un déplacement, contre le fichier
  `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` qui donne la forme du message mais pas ce seuil.
- Critère de fermeture : le contrôle positif rend OK et la position serveur est mise à jour ; les cinq
  scénarios adversariaux sont refusés avec **cinq motifs distincts** dans la trace ; aucun chemin ne se
  fabrique hors du point de validation.
