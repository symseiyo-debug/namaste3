# Journal — J-1 : dire au client où aller

> Étage 3, jour 2. Le premier obstacle réel, et le seul qui demande une main humaine.
> Source : `server/SOCLE-JOUR-2.md` §C.1 · les 4 récoltes `internal/haapi-stub/resultat-g2-*/`
> · `internal/third-party-review/client-3.0-clair/login-pregame-ecrans.md` · `internal/haapi-stub/CARTE-HAAPI.md`.

## Decided

- **Le symptôme est mesuré, pas supposé.** Sur les 4 récoltes : le client appelle le launcher **3 fois
  `connect` et 3 fois `settings_get`**, rien d'autre ; il échoue dans le chargement de sa configuration
  externe (exception levée dans la méthode de téléchargement, visible dans la pile du journal) ; et il
  n'émet que **4 requêtes HTTP**, toutes vers `launcher.cdn.ankama.com`. **Aucune vers l'hôte que
  notre stub sert.** Le stub ne répond donc pas mal : il n'est jamais appelé.
- **Deux essais, joués dans cet ordre, un seul changement à la fois.**
  - **Essai A — le sélecteur d'hôte natif.** L'écran de login porte en clair un conteneur de sélection
    de port et une liste déroulante d'hôte — `il2cpp.cs:390916-390951`, relevé par
    `internal/third-party-review/client-3.0-clair/login-pregame-ecrans.md:47-71`. Lancer le client, ouvrir
    l'écran de login, **regarder**. Coût : dix minutes, zéro ligne de code.
  - **Essai B — les arguments du serveur de référence.** Relancer avec le canal explicite, la connexion
    automatique et le port de jeu de `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md:60-63`, au lieu du
    canal générique employé jusqu'ici. Coût : trente minutes, zéro ligne de code.
  - **Essai C — le banc du serveur de référence contre le vrai client** (paquet apparu à 22:50 UTC :
    `etage2-socle/banc-jondo/RUNBOOK-BANC-JONDO.md`, six commandes, réversible en une). Il ne répond
    pas seulement à « où va le client » : il donne **la première capture complète du vrai client face
    à un serveur qui répond de bout en bout**, trame par trame —
    `etage2-socle/banc-jondo/CE-QUE-JONDO-NOUS-DONNE.md`. Cette matière n'existe nulle part sur ce
    VPS : le codec a mesuré que la rafale de bienvenue est **construite en code** et qu'aucune capture
    n'en existe (`codec/CODEC.md:132-143`). C'est donc aussi ce qui nomme les 8 opcodes
    restants et tranche `krt`. **Ligne rouge : il modifie le client officiel installé en local**, et son mode
    d'emploi le dit en première ligne avec sa commande de retour arrière.
- **L'ordre est A, puis C, puis B**, et il n'est pas arbitraire : A ferme la question sans écrire une
  ligne s'il réussit ; C rapporte le plus par minute mais touche le client ; B ne coûte rien mais ne
  rapporte qu'une réponse.
- **Un essai qui ne change rien est un résultat.** Il élimine une branche et se consigne comme tel.

## Rejected

- **Patcher le binaire du client.** Coûteux, fragile à chaque build, et rendu inutile si l'essai A
  réussit. On ne l'envisage qu'après avoir mesuré que les deux essais échouent.
- **Continuer à durcir le stub HAAPI.** Il est déjà à quatre chemins candidats plus un attrape-tout
  journalisé (`internal/haapi-stub/CARTE-HAAPI.md:225-236`). Ajouter un cinquième chemin à un
  service que le client n'appelle pas ne mesure rien.
- **Conclure depuis la piste `connectionHosts`.** C'est l'hypothèse la mieux motivée du dossier
  (`CARTE-HAAPI.md:352-365`) et elle reste DÉDUITE : elle suppose que le document de configuration soit
  servi, ce qui est précisément ce qui échoue.

## Risks

- **Conclure « le sélecteur n'existe pas » sur une capture d'écran.** Sa condition d'affichage n'est
  pas décompilée (`internal/third-party-review/client-3.0-clair/login-pregame-ecrans.md:70`) : il peut être
  réservé à un build interne. Signal : absent à l'écran mais présent dans le binaire. Remède : le
  noter DÉDUIT-négatif, pas VÉRIFIÉ-absent, et passer à l'essai B.
- **Changer deux choses à la fois.** Rejouer avec les nouveaux arguments **et** un stub modifié rendrait
  un résultat ininterprétable. Signal : le protocole d'essai touche plus d'une variable.
- **Lire un changement de comportement comme la preuve de sa cause.** Si B change quelque chose, ça dit
  que le comportement dépend des arguments, pas **lequel** des trois arguments.
- **Ce PC personnel est la seule instance.** Un essai qui casse son installation coûte la journée.
  Remède : le paquet existant ne modifie rien sans confirmation
  (`internal/haapi-stub/paquet-g2/LIRE-MOI-G2.md`), on garde cette propriété.

## Files

- **Écrire** : `internal/haapi-stub/PROTOCOLE-ESSAIS-ADRESSE.md` (le protocole des deux essais,
  ce qu'on regarde, ce qui compte comme réponse) ; une nouvelle récolte
  `internal/haapi-stub/resultat-g2-<date>/` par essai.
- **Lire, jamais écrire** : `internal/third-party-review/client-3.0-clair/`, `internal/haapi-stub/CARTE-HAAPI.md`,
  `internal/SEQUENCE-CHEMIN-CRITIQUE-JONDO.md`, les 4 récoltes existantes.
- **Interdit** : modifier `haapi_stub_v2.py` pendant les essais. Un stub qui change entre deux essais
  fait de la comparaison une illusion.

## Remaining

- Si A réussit : l'adresse est réglée, et J-3 peut viser le client vivant dès aujourd'hui.
- Si A échoue et B réussit : le chemin dépend des arguments de lancement ; il faut alors mesurer
  **lequel** avant d'en faire une consigne.
- Si les deux échouent : le point ouvert redevient « quelle route porte le document de configuration »,
  et la réponse passe par l'attrape-tout déjà en place, pas par une hypothèse.
- Critère de fermeture : une phrase VÉRIFIÉE, avec sa source, qui dit par quel chemin le client
  apprend l'adresse de notre serveur.
