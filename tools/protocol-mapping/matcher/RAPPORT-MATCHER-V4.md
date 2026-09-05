# RAPPORT-MATCHER-V4 — hiérarchie de provenance + cahier des charges de la capture

> Suite de v1/v2/v3 (toutes intactes). Pipeline complet :
> `extraire_signatures.py && charger_proto_clair.py && extraire_contexte.py &&
> matcher_v2.py && matcher_v3.py && matcher_v4.py`.

## 1. Hiérarchie de provenance à 3 niveaux — `jtg` gagne, comme prédit

`capture_verifiee` (24 opcodes, transcrits de `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6/§5
et `COMPLEMENT-CHEMIN-CRITIQUE-G1.md`, chacun avec sa citation fichier:ligne dans
`matcher_v4.py`) > `structure_v2` (57 graines) > `proposition_jondo_seule` (72, anclas
brut). **3 conflits tranchés par la hiérarchie**, dont le cas nommé par team-lead :

```
jtg → GiftsListMessage (capture_verifiee, ConnectionProtocol.cs:218) — GAGNE
kmz → rétrogradé en À_CLASSER, note explicite du conflit
```

Assertion vérifiée automatiquement dans `matcher_v4.py::main()` (pas un espoir, un test
qui imprime ❌ s'il échoue). Les 2 autres conflits résolus de la même façon, listés dans
`correspondance-v4.tsv` (colonne `chemin_de_preuve`, jamais silencieux).

**Bug trouvé en construisant v4, corrigé avant de rendre** : `gatherer`/`luaxy` écrivent
le répété en syntaxe protobuf directe (`repeated int32`), pas seulement `List<int>`
(convention otomai) — mon dépouillement ne gérait que la 2e forme. Sans le correctif,
`"repeated int32"` fuitait comme un FAUX nom clair dans `correspondance-v4.tsv` (mesuré :
1 occurrence, `len`→`repeated int32`). Corrigé dans `charger_proto_clair.py`
(`parse_otomai_champ`). Effet mesuré avant/après sur tout le pipeline (pas seulement le
cas trouvé) : v2 36→**60**, v3 158→**209**, v4 **208** — le bug bloquait bien plus de
correspondances légitimes que le seul cas visible.

| Mesure | v3 | v4 |
|---|---:|---:|
| DÉDUIT | 209 | 208 |
| par niveau | — | capture_verifiee 24, structure_v2 57, proposition_jondo_seule 72, arrastre (reste), arrosage (reste) |
| conflits tranchés | 0 (défaut arbitraire) | **3** (hiérarchie explicite) |

## 2. `A-NOMMER-PAR-CAPTURE.tsv` — le cahier des charges de la capture dynamique (L7)

23 lignes : **8/32 opcodes du chemin critique** restent sans nom après v4 —
`mgq`,`mgt`,`hpd`,`krs`,`kqp`,`ksl`,`krt`,`hjk` — VÉRIFIÉS en FORME et en SÉQUENCE par
Jondo (position exacte dans la rafale/le chemin), mais SANS nom clair proposé par aucune
source lue (ni SEQUENCE, ni COMPLEMENT, ni anclas). Chaque ligne donne le typedef_index,
ses voisins de co-occurrence mesurés (indice de famille), et sa position dans la
séquence VÉRIFIÉE — c'est littéralement l'écran/l'action à observer en capture (ex.
`mgq`/`mgt`/`hpd`/`krs` sont dans la rafale de bienvenue entre `kqu` et `mgz`, donc
juste après la connexion réussie, avant la liste de personnages).

+ 15 familles obfusquées les PLUS CITÉES par co-occurrence de méthode restant sans nom
(jusqu'à 22 arêtes pour `ljx`, TypeDefIndex 14075) — candidates fortes pour une capture
ciblée puisqu'elles sont manipulées par de nombreux points du code.

## 3. Le bonus de voisinage — verdict en une ligne

**Mesuré deux fois (avant et après le correctif §1, comptes de correspondances très
différents) : 0 correspondance n'a jamais dépendu du bonus de voisinage (+0,05) — il
peut être retiré sans perte mesurée, gardé seulement parce qu'il ne fait pas de mal et
documente une piste pour un futur graphe de voisinage plus dense.**

## 4. Trous connus (v4)
- Les mêmes « réutilisations légitimes » qu'en v3 (`HouseInstance`×4, `Teleporter`×2…) —
  un type clair référencé par plusieurs parents compile plusieurs classes obfusquées
  distinctes ; comportement structurel attendu, pas un bug, non re-détaillé ici (cf.
  RAPPORT-MATCHER-V3.md §3).
- Pas de nouvelle épreuve `--epreuve` écrite pour v4 spécifiquement (hors périmètre borné) —
  la mécanique réutilisée (`propagate`/`arrosage_avec_voisinage` de v3) reste couverte
  par l'épreuve de v3, rejouée ci-dessus après le correctif ; l'assertion `jtg` dans
  `main()` sert de garde minimale propre à v4.
