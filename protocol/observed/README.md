# Protocole observé — capture d'une session de jeu réelle (build 3.6.10.10)

> **Ce que ce dossier apporte, et que l'analyse statique ne peut pas donner.**
> Le binaire du client livre la *forme* du protocole : 2206 messages, 6278 champs,
> types et cardinalités. Il ne livre **aucun nom** : mesuré, 0 message sur 2206
> porte un nom clair récupérable statiquement.
> Ces tables viennent d'une **session de jeu réelle**, jouée action par action,
> chaque geste annoncé avant d'être fait et le trafic relu entre chacun.
> Le sens vient de l'observation, pas d'une hypothèse.

## Mesures de la session
| | |
|---|---|
| trames capturées | **4 435** |
| opcodes distincts observés | **238** |
| dont nommés par recoupement | **76** |
| familles complètes reconstituées | 7 |

## Méthode
Une action à la fois. Le battement de cœur `kqo`/`kqy` (toutes les 5 s) sert de
repère temporel pour attribuer chaque trame au geste qui l'a produite.
**Provenance** : ce qui est observé est marqué VÉRIFIÉ ; ce qui est inféré d'une
position ou d'un voisinage est marqué DÉDUIT — et ne devient jamais un fait sans
confrontation.

## Fichiers
- `sequences.md` — les enchaînements canoniques, par famille
- `manquants.md` — **ce que le client demande et qu'un serveur doit fournir**
- `opcodes.md` — les 238 opcodes observés, avec sens, fréquence, taille et nom connu

## Portée — ce que ces tables NE disent pas
Un opcode **observé** n'est pas un message **compris** : la sémantique fine des
champs reste à décoder. Et une capture vaut **pour sa build** : les noms obfusqués
sont entièrement réassignés entre versions majeures (mesuré : 0 accord et 51
contradictions sur 596 opcodes comparables entre builds éloignées).

*Le client de jeu et ses données ne sont pas distribués ici.*
