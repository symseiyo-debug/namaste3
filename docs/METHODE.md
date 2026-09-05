# Méthode — retrouver le sens d'un protocole obfusqué
*Method — recovering meaning from an obfuscated protocol*

> Document public. Il explique **comment on travaille**, pour que le travail soit reproductible et
> contestable par quelqu'un d'autre que nous.
> *Public document: how we work, so the work can be reproduced and challenged by anyone.*

---

## 1. Le problème

Le client est en **Unity / IL2CPP**. Le protocole est du **protobuf**. Chaque message porte un nom
**obfusqué de trois lettres** (`jru`, `kqp`, `hpd`), et ces noms sont **redistribués à chaque
version majeure**. Les champs ne sont que des numéros.

*The client is Unity/IL2CPP, the protocol is protobuf, and every message name is an obfuscated
three-letter code, reshuffled at every major build. Fields are just numbers.*

La difficulté n'est donc pas de comprendre le jeu : c'est de **retrouver le sens** de messages qui
n'en portent aucun.

---

## 2. Deux sources, deux natures de vérité

| Source | Ce qu'elle donne | Ce qu'elle ne donne pas |
|---|---|---|
| **Analyse statique** (dump du binaire) | la **forme** : structure, types, cardinalités, numéros de champ | le **sens** |
| **Analyse dynamique** (capture de trafic) | le **sens** : ce message-ci survient quand on fait cela | difficilement l'exhaustivité |

**Mesuré chez nous : 0 message sur 2 206 ne porte de nom clair récupérable statiquement.** Le nom
n'est pas caché dans le binaire — il n'y est pas. C'est pourquoi la capture n'est pas un raccourci
mais un **passage obligé**.

*Measured: 0 of 2 206 messages carries a statically recoverable clear name. The name isn't hidden in
the binary — it isn't there. Capture is not a shortcut, it's the only road to meaning.*

---

## 3. Une signature ne vaut que pour sa version

Résultat mesuré en confrontant des tables d'opcodes tierces aux nôtres :

| Comparaison | Accord |
|---|---|
| entre **versions majeures** différentes (596 opcodes comparables) | **0 accord, 51 contradictions** |
| entre **versions voisines** (3.6.10.10 → 3.6.10.11, 2 169 identités) | **rotation nulle** |

**Conséquence pratique** : une table d'opcodes d'un autre projet, aussi sérieux soit-il, est
**fausse chez vous** si elle ne vise pas votre version exacte. Et le piège est vicieux : un mauvais
numéro de champ produit du protobuf **parfaitement valide** — compilateur muet, tests verts, panne
visible seulement à l'écran.

**La bonne nouvelle** : un correctif de version ne casse rien. C'est le saut majeur qui coûte.

*A signature is only valid for its own build. Third-party opcode tables don't transfer across major
versions — and a wrong field number yields perfectly valid protobuf, so nothing complains until the
screen breaks.*

---

## 4. DARCI — la méthode

**D**eterminist **A**ugments **R**eality through **C**ausal **I**ntelligence.
Pas un modèle, pas un chatbot : une **méthode**, parcourue dans deux sens.

- **DAR** — *Découverte par Agrégation Resserrée*, la face **montante**. On part des données brutes
  (sources décompilées, tables, captures), on agrège, on resserre, et **la bonne question émerge**.
  On ne part pas d'une hypothèse : on la laisse sortir de la matière.
- **MCI** — *Model of Causal Intelligence*, la face **descendante**. D'une question, on rend une
  réponse **avec sa chaîne de causes** : version → message → classe → champ → ligne de source.
  Chaque maillon se lit, se conteste, se corrige.

> **Une réponse sans chaîne de causes n'est pas une réponse, c'est une supposition — et elle se
> déclare comme telle.**
> *An answer without its causal chain is not an answer but a guess — and it must be labelled as one.*

---

## 5. La provenance : VÉRIFIÉ / DÉDUIT

Chaque affirmation du dépôt porte son statut :

- **VÉRIFIÉ** — confronté à la source, avec la référence exacte (`fichier:ligne`, ou la capture).
- **DÉDUIT** — plausible, pas encore confronté. **Ce n'est pas un fait.**

Une correspondance reste **DÉDUITE** jusqu'à sa confrontation. Le **traçable** prime toujours sur le
probable : ce qu'un outil déterministe peut retrouver n'est jamais deviné.

---

## 6. La discipline de preuve : éprouver dans les deux sens

**Un vérificateur qu'on n'a jamais vu échouer ne prouve rien.**

Chaque garde de ce dépôt a un mode `--epreuve` qui :
1. lui **plante volontairement un défaut** et exige qu'elle le voie — *témoin positif* ;
2. lui présente un cas **sain** et exige qu'elle le laisse passer — *témoin négatif*.

Sans le témoin positif, un « tout est vert » peut vouloir dire « l'instrument ne regarde plus ».
C'est la règle qui nous a le plus servi : elle a attrapé, chez nous, plusieurs verts qui ne
mesuraient rien.

*A checker you have never seen fail proves nothing. Every gate here can be deliberately sabotaged
and must catch it; it must also stay green on a clean case.*

**Corollaire mesuré** : un test doit **imiter l'appelant réel**. Un test qui invoque autrement que
les vrais appelants mesure son propre protocole, et rend un verdict sur un usage que personne n'a.

---

## 7. Reproductibilité

Chaque outil rend ses résultats **avec la commande qui les a produits**. Les chemins cités dans les
tables sont **relatifs** (`sources/…`) : ils désignent l'arborescence du client décompilé **chez
vous**, pas une machine en particulier.

Le but n'est pas qu'on vous croie. C'est que vous puissiez **rejouer**, et **nous contredire**.

*Every tool ships the command that produced its output, and all paths are relative. The goal isn't
to be believed — it's to be reproducible and refutable.*
