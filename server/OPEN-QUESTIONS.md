# QUESTIONS — ce qui attend ta main, 05/09

> Étage 3. Cinq questions, une ligne chacune. **Chacune a un défaut choisi** : si tu ne réponds pas,
> on avance dessus plutôt que d'attendre. Source : `server/SOCLE-JOUR-2.md` §D, mesures du §A.

1. **Peux-tu jouer les trois essais « où va le client » sur ton PC ?** Deux ne touchent à rien (regarder
   l'écran de login ; relancer avec d'autres arguments). Le troisième, le banc du serveur de référence,
   **modifie ton client officiel** et se défait en une commande — c'est celui qui rapporte le plus,
   parce qu'il donne en prime la capture complète qui nous manque partout.
   *Défaut sans réponse* : on bâtit tout contre le bot-testeur seul ; le client vivant reste non prouvé,
   donc la gate finale reste hors d'atteinte, et la journée s'arrête sur du vert de laboratoire.

2. **`krt` : on capture sa charge aujourd'hui, ou on le laisse ouvert ?** C'est le dernier écart entre
   G1 et le vert (mesuré ce soir : 32/32 couverts, 31/32 conformes).
   *Défaut sans réponse* : on le tolère sans le jeter en silence, on capture pendant la rafale, et G1
   reste rouge jusqu'à la capture. **On ne le retire pas de la liste pour faire verdir la gate.**

3. **Le portage multi-build reste-t-il arrêté ?** La seconde build est téléchargée (149 Mo) mais non
   dumpée, et tu as dit le 05/09 « osef du portage de version pour l'instant ».
   *Défaut sans réponse* : oui, arrêté. Rien ne le relance de sa propre initiative.

4. **La trace causale : on aligne son schéma avec l'index causal existant du projet avant d'écrire, ou on écrit d'abord ?**
   *Défaut sans réponse* : on écrit le schéma que le bot-testeur produit déjà, seul point d'accord
   existant entre les deux côtés — sinon la trace du bot, celle du serveur et celle du graphe ne se
   joignent pas.

5. **Le code de l'étage 2 doit-il passer la gate commentaires avant qu'on construise dessus ?** Elle est
   rouge sur 16 fichiers, dont 10 du bot-testeur, alors que tu as demandé le 04/09 que tout le code soit
   commenté.
   *Défaut sans réponse* : non bloquant. On compte, on affiche, on ne rouvre pas la zone d'un autre
   écrivain pendant qu'il y travaille.
