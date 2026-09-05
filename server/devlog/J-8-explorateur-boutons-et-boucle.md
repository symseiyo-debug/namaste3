# Journal — J-8 : l'explorateur de boutons, et pourquoi il ne cherchait pas le bon type

> Étage 4. La question du jour : sur quel système d'UI le client 3.0 est-il bâti,
> et qu'est-ce qu'un explorateur automatique doit savoir pour trouver un bouton
> plutôt qu'un décor ?

## Decided

- **Le client 3.0 est bâti sur UI Toolkit, pas sur uGUI — mesuré, pas supposé.**
  Comptage direct dans les métadonnées de types du client : exactement **8 classes**
  dérivent de `Selectable` (la base uGUI/`UnityEngine.UI`), et les 8 sont des
  widgets du **moteur lui-même** (`Button`, `Dropdown`, `InputField`, `Scrollbar`,
  `Slider`, `TMP_Dropdown`, `TMP_InputField`, `Toggle`). **Zéro classe Ankama**
  parmi elles. Un explorateur parti de `Selectable` — le réflexe naturel, c'est le
  nom qu'on connaît — aurait trouvé les classes, confirmé qu'elles existent, et
  cliqué sur rien.
- **L'explorateur construit** parcourt donc `UIDocument.rootVisualElement`
  récursivement (API publique : `childCount` / `ElementAt(int)`), détecte un
  « bouton » par une propriété publique `clickable` assignable à `Clickable` —
  motif identique sur `Button`, `DofusButton`, `RadioButton`, `PlayButton` — et
  clique : API publique (`onClick.Invoke()`) côté uGUI, réflexion sur le délégué
  privé `Clickable.clicked` côté UI Toolkit.
- **La politique de refus est posée avant le clic, jamais après.** Liste noire
  FR+EN sur chemin+libellé (Supprimer/Delete, Vendre/Sell, Acheter/Buy,
  Quitter/Quit, Déconnexion/Logout, Payer/Pay), un bouton sans libellé est refusé
  par défaut, l'explorateur est désarmé et en simulation par défaut, et chaque
  écran est traité **séquentiellement** — jamais en concurrence, pour ne pas
  mélanger l'attribution des messages réseau.
- **40 témoins unitaires verts, build propre (0 avertissement, 0 erreur).**
  Le témoin qui comptait : `"Supprimer"` refusé, `"Inventaire"` accepté.

## Rejected

- **Le premier chiffre de comptage (324 classes dérivées d'UI Toolkit), jamais
  regravé.** Remesuré ensuite par trois méthodes indépendantes : 229, 133, 239 —
  aucune ne retombe sur 324. La **conclusion** qualitative, elle, a été confirmée
  exactement (les 8 `Selectable` sont bien celles du moteur). Un chiffre qui ne se
  reproduit pas ne se publie pas, même quand la conclusion qu'il portait est
  juste — on garde la conclusion, on jette le chiffre.
- **Énumérer l'arbre d'UI par l'énumérateur natif du client.** La couche d'interop
  du client expose un objet miroir qui ne porte que `Current`, pas une vraie
  énumération .NET — un `foreach` direct échoue à la compilation. Marcher par
  index (`childCount`/`ElementAt(int)`) est ce qui fonctionne réellement.

## Encore ouvert

Le chemin de clic **côté UI Toolkit** (la branche par réflexion) n'a jamais été
exercé contre un client réellement en vol — construit et prouvé par témoins
unitaires seulement, jamais mesuré en conditions réelles.

## La boucle, et où elle s'arrête aujourd'hui

Explorer → mesurer → cartographier → implémenter → **vérifier** ne se referme
que si la dernière étape existe : rejouer le **même** parcours contre **notre**
serveur, et voir si les silences de la carte reculent. Cette dernière jambe
n'existe pas encore — tout ce qui précède mesure le serveur de référence, pas
le nôtre. Tant qu'elle manque, on a une mesure, pas encore une preuve de
progrès.
