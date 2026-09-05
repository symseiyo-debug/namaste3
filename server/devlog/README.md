# Journal de bord — ce qu'il est, et ce qu'il n'est pas

Ces entrées sont le **journal de conception** du serveur : ce qui a été décidé, ce qui a été
rejeté, et **pourquoi**. Elles sont publiées parce que le raisonnement vaut souvent plus que le
code qui en sort — un choix rejeté avec sa raison évite à quelqu'un d'autre de refaire le
détour.

## ⚠️ Le journal va plus loin que le code publié ici

À lire avant de chercher un fichier cité dans une entrée : **le journal documente des travaux
dont tout le code n'est pas dans ce dépôt.** Deux cas, tous deux volontaires :

- **Des projets nommés qui n'existent pas ici.** Les entrées J-3 à J-7 discutent des choix
  d'implémentation pour `Namaste3.World`, `Namaste3.Net`, `Namaste3.Store`, `Namaste3.Connect`
  et `Namaste3.World.Host`. Ce dépôt ne publie aujourd'hui que `Namaste3.Codec` et
  `Namaste3.Server.Connection` — le serveur de **connexion**. Les décisions consignées (atomicité
  des tickets, types de chemin validés par construction, contrôles serveur-side du déplacement)
  restent lisibles et réutilisables telles quelles ; simplement, **le code correspondant n'est
  pas dans ce dépôt**, et une entrée qui cite un fichier de ces projets cite quelque chose que
  vous ne trouverez pas en clonant.

- **Des outils décrits mais non publiés.** L'entrée J-8 décrit un explorateur de boutons côté
  client (parcours de l'arbre UI Toolkit, invocation par réflexion, politique de refus,
  « 40 témoins unitaires verts ») : **son code source et ses tests ne sont pas ici.** C'est un
  outil de mod client, hors du périmètre de ce dépôt (qui ne publie que le serveur et le codec).
  Les faits **mesurés** que l'entrée rapporte sur le client — notamment que Dofus 3 est bâti sur
  UI Toolkit et non sur uGUI — restent vérifiables par quiconque possède le client.

Autrement dit : **les mesures publiées ici sont reproductibles, les chiffres de tests d'outils
non publiés ne le sont pas depuis ce dépôt.** On préfère le dire plutôt que de laisser un
lecteur chercher un dossier qui n'existe pas.

## Ordre de lecture

| Entrée | Sujet |
|---|---|
| `J-0-dettes.md` | l'état de départ et les dettes assumées |
| `J-1-ou-aller.md` | le choix de l'objectif mesurable |
| `J-2-socle-a-vide.md` | le socle, sans protocole |
| `J-3` → `J-6` | sélection de serveur, personnages, entrée en jeu |
| `J-7-deplacement.md` | validation du déplacement, serveur-side |
| `J-8-explorateur-boutons-et-boucle.md` | l'explorateur de boutons et la boucle d'exploration |
