# Panneaux d'UI observés en jeu

> Complète `sequences.md` et `opcodes.md` côté réseau : ici, la **structure**
> des panneaux vus à l'écran pendant une session de jeu réelle (Bonta,
> Faubourgs des artisans), utile pour reconstruire les mêmes écrans côté
> émulateur.

## Panneau Zaapi (téléportation)

Ouvert en cliquant un point de téléportation en ville. Structure observée :

- Titre : `Zaapi — <nom du quartier>`
- Trois onglets : **Ateliers**, **Hôtels de vente**, **Divers**
- Barre de recherche (« Rechercher une destination »)
- Liste de destinations (vide tant qu'aucun zaap n'est découvert/favori —
  affiche alors « Aucune destination »)
- Case à cocher : « Afficher uniquement mes zaapis favoris »
- Solde de kamas affiché en bas à droite
- Bouton d'action : « SE TÉLÉPORTER »

## Panneau « Quêtes suivies » — menu contextuel

Le petit menu (icône « ⋮ ») du module de suivi de quêtes ouvre :

**Section QUÊTES SUIVIES**
- Masquer le module
- Réduire le titre du module
- Suivre 3 / 5 / 10 quêtes maximum (choix exclusif)
- Suivre automatiquement les quêtes acceptées (case à cocher)
- Masquer / Afficher tous les points de repère

**Section AFFICHAGE**
- Redimensionnement automatique
- Taille de la police (sous-menu)
- Niveau d'opacité du fond (sous-menu)

Ce module suit jusqu'à 2 quêtes affichées simultanément par défaut, chacune
avec ses étapes ordonnées listées en clair (texte de quête complet, pas
d'identifiant).
