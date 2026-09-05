# RAPPORT-MATCHER-V2 — appariement structurel complet, deux graphes de champs

> Suite de `RAPPORT-MATCHER.md` (v1). v1 restait intacte pour comparaison. v2 est
> déclenchée par la correction de team-lead (04/09) : « Jondo jamais en entrée » valait
> pour la validation d'un matcher à une seule source ; avec un second graphe COMPLET
> (numéros+types+imbrication), l'algorithme de Jondo s'applique enfin des deux côtés.
> Pipeline complet : `extraire_signatures.py && charger_proto_clair.py && matcher_v2.py`.

## 1. Chiffres v1 → v2

| Mesure | v1 | v2 |
|---|---:|---:|
| Correspondances proposées (`DÉDUIT`) | **4** | **31** (×7,75) |
| Mécanisme du côté clair | forme d'imbrication seule (noms orphelins, 0 champ) | numéro+catégorie+répété par champ, 4 provenances |
| Noms clairs disponibles | 513 (littéraux du dump, sans données de champ) | **1829** (union otomai/gatherer/luaxy/jondo-proto) |
| … dont écartés comme SUSPECTS (champs internes encore obfusqués) | — (signal indisponible en v1) | **451/1829 (24,7%)** — trouvaille en cours de route, cf. §3 |
| Graines (signature round-0 exacte, unique des 2 côtés) | 2 (forme seule) | 6 (numéro+catégorie+répété) |
| Arrastre/parent-drag | 2 | 2 |
| Arrosage (score ≥0,55, écart ≥0,08) | 0 (jamais tenté en v1 — pas de champs à comparer) | 23 |
| À CLASSER | 511/515 | 1798/1829 |
| Épreuve | 2 témoins ✅ | 3 témoins (déterminisme ✅, sabotage ✅, stabilité inter-provenances ℹ️) |

## 2. Ce que le deuxième graphe complet a permis de mesurer (et de corriger)

### 2.1 Validation croisée dump ↔ Jondo .proto — AVANT tout matching
Mesuré sur les 2169 tokens partagés entre `signatures-obfusquees.jsonl` (notre dump,
indépendant) et `datos/protocolo_3.6.10.10.proto` (Jondo) :
- **accord du NOMBRE de champs : 2168/2169 (100,0%)**
- **accord de la SET de numéros de champ : 2168/2169 (100,0%)**
- **accord de CATÉGORIE (scalaire/référence) par champ : 6018/6183 (97,3%)**

C'est une validation FORTE (pas une hypothèse) que Jondo et notre dump lisent le MÊME
build, avec le MÊME espace de tokens obfusqués — condition nécessaire à tout le reste.
L'écart de 2,7% s'explique presque entièrement par les `oneof` (93/2169 tokens) : Jondo
résout le type de CHAQUE variante en lisant les `Properties` générées (analyse plus
riche) ; notre extracteur ne voit que le champ `object` partagé — catégorisé
`oneof_object`, jamais faux, juste moins précis. Documenté, pas caché.

### 2.2 Une vraie erreur trouvée et corrigée dans mon PROPRE extracteur v1
En creusant le désaccord `jsj` (Jondo dit 6 champs typés distincts ; mon dump v1 disait
6 fois `oneof_object`), j'ai trouvé la cause dans le C# source (`class hex`,
TypeDefIndex 9487) : **9 `const int` consécutifs SANS aucun champ porteur entre eux**,
alors que les vrais backing fields existaient mais étaient de type `object` partagé —
ce n'était PAS un bug de pairage (déjà corrigé le même jour, voir v1 §5.4), c'est la
NATURE MÊME d'un `oneof` à 9 variantes, correctement identifiée par mon extracteur mais
avec une précision plafonnée à la catégorie « objet partagé ». Un `public const int
NanosecondsPerSecond = 1000000000;` trouvé en testant `Duration` (Google.Protobuf,
témoin en clair) a confirmé un AUTRE piège réel — des constantes qui ne sont PAS des
numéros de champ — corrigé par une borne de plausibilité (`MAX_FIELD_NUMBER`), 0 impact
mesuré sur nos 2206 classes cibles (aucune n'a ce motif).

### 2.3 La vraie richesse de noms clairs vient d'OTOMAI/GATHERER/LUAXY, pas de Jondo
Jondo ne nomme que **99/293** opcodes (des PROPOSITIONS stylées, pas des extractions —
son propre en-tête le dit). `index/protocole-otomai.tsv` (réimplémentation communautaire
BubbleBot) porte **1547** noms clairs AVEC numéros+types+imbrication complets — la vraie
matière. `protocole-gatherer.tsv` et `protocole-luaxy.tsv` (apparus pendant ce travail,
écrits ailleurs dans le projet) en portent chacun ~1455, avec un **fichier source commun**
(`proto/game/preset.proto`, même numéro de ligne dans les deux dépôts cités) — leur
accord mutuel n'est donc PAS une double corroboration indépendante, à traiter comme
UNE seule voix quand les deux sont d'accord entre eux et divergent d'un tiers.

### 2.4 Trouvaille : un nom clair peut être un vrai mot anglais PAR COÏNCIDENCE
`Ride` (mot anglais légitime) apparaissait dans `protocole-otomai.tsv` avec des champs
`ebko`,`ebkp`,`ebkq`,`ebkr` — encore OBFUSQUÉS. otomai n'a pas fini de renommer tous ses
types imbriqués ; certains gardent un nom court qui, une fois capitalisé, RESSEMBLE à un
vrai mot (`Hio`, `Jfj`, `Jio`, `Ride`...) sans en être un. **Le nom seul ment ; les
noms de CHAMPS ne mentent pas** — heuristique ajoutée (`champs_semblent_obfusques`,
`charger_proto_clair.py`) : proportion de noms de champ à la forme d'un token obfusqué
(minuscule, 3-6 lettres, sans underscore) ≥ 60%. **451/1829 noms marqués suspects et
écartés du matching** — mesuré, avant/après : le run buggé initial proposait `Ride` et
`Rights` avec la même confiance que `AllianceInformation` ; corrigé, `Ride` reste
proposé (0,889, `hor`) car **luaxy ET gatherer le confirment indépendamment** avec de
vrais noms (`model_id`,`level`,`is_current_ride`) — la règle n'exclut QUE si TOUTES les
provenances qui se prononcent sont d'accord pour dire « encore obfusqué », jamais sur
une seule voix minoritaire.

### 2.5 Un vrai bug d'affectation trouvé et corrigé AVANT le rendu final
Premier jet de l'arrosage : `AllianceApplicationSubmitRequest` assigné à **10 tokens
obfusqués différents en un seul run** (`hpn`,`imq`,`jhb`,`jlp`,`jnt`,`jwn`,`lgt`,`lrt`,
`lsh`,`lst`) — `taken_clear` n'était filtré qu'UNE FOIS avant la boucle, pas mis à jour
à chaque affectation. Corrigé par une affectation GLOUTONNE GLOBALE (tous les candidats
scorés d'abord, triés, puis assignés en respectant l'unicité des deux côtés). Mesuré
avant/après : 153 propositions bugées → 52 correctes (avant le filtre §2.4) → 31 après.

## 3. L'algorithme v2, en 10 lignes (vraie transposition de Matcher.cs a.1, cette fois)

1. Round-0 côté obfusqué : `(numéro, catégorie S/R, répété)` par champ — déjà résolu
   par `extraire_signatures.py`.
2. Round-0 côté clair : FUSION PAR VOTE entre provenances (numéro→répété/catégorie
   majoritaire ; désaccord compté, jamais tranché en silence — 1501 champs incertains
   mesurés sur ce run).
3. Bucket = assembly (Connection vs Game), déterministe des deux côtés.
4. Graine = signature round-0 EXACTE, non vide, unique des DEUX côtés du même bucket.
5. Arrastre : si A_obf↔A_clair appariés et que le champ N de chacun référence un AUTRE
   type, propage cette référence comme une nouvelle paire.
6. Arrosage : score = recoupement de Dice sur l'ensemble (numéro,catégorie,répété) —
   analogue direct de `Matcher.Similar()`, sans le terme de voisinage (round-0 seul).
7. Retenu SEULEMENT si score≥0,55 ET écart≥0,08 avec le 2e candidat (seuils identiques
   à Jondo).
8. Affectation GLOUTONNE GLOBALE (tous les candidats scorés, triés, assignés en
   respectant l'unicité) — jamais une boucle qui laisse une même cible partir deux fois.
9. Toute fiche claire dont les champs sentent encore l'obfuscation est écartée AVANT
   le matching (§2.4), jamais après, jamais silencieusement.
10. Statut TOUJOURS `DÉDUIT` — un accord de structure entre deux instruments
    indépendants (notre dump, Jondo/otomai/gatherer/luaxy) n'est jamais une preuve.

## 4. Épreuve v2

- **Témoin 1 (déterminisme)** : rejeu 2× → sha256 identique. ✅
- **Témoin 2 (sabotage)** : champs de toutes les fiches claires mélangés (seed=99) →
  0/31 paires réelles survivent. ✅ Effondrement total, pas partiel.
- **Témoin 3 (stabilité inter-provenances, INFO — pas pass/fail)** : v2 tourné sur
  `otomai` seul (1547 noms) vs `jondo-proto` seul (99 noms) → **0 nom clair couvert par
  les deux dans ce run** (otomai propose 50 paires, jondo-proto 11, aucun recouvrement).
  Cohérent avec `ACCORD-JONDO.md` v1 (2 noms communs mesurés sur l'ensemble complet,
  aucune garantie qu'ils tombent dans les DEUX sous-ensembles PROPOSÉS par v2 sur ce
  run précis) — **rapporté tel quel**, un N=0 ne prouve ni ne réfute rien, exactement
  la même leçon que le plancher de hasard de v1.

## 5. Ce que le décodeur FileDescriptorProto a apporté — mesuré, borné, PAS la piste qu'on croyait

Team-lead avait mesuré 163 stretches ≥300 octets dans le metadata brut, base64-alphabet-
compatibles, dont 15 auraient décodé en `\n\x0b`+11 octets non-ASCII. **Reproduit
partiellement, pas confirmé** : un parseur protobuf minimal complet (stdlib,
`decoder_filedescriptor.py`, wire format brut, DescriptorProto récursif) montre que
**ces 163 « runs » ne sont PAS des blobs uniques** — plusieurs littéraux de chaîne C#
sont concaténés sans séparateur dans la table de chaînes du binaire (mesuré : le run à
l'offset 379539 contient un `FieldOptions` lisible 212 caractères après son PROPRE
début, qui lui décode en bruit). Balayage de 24 142 offsets alignés-4 dans les 163 runs :
**0 FileDescriptorProto complet valide**, mais **23 noms de champ-1 isolés lisibles** —
et LES 23 sont des fichiers/identifiants STANDARD de Google.Protobuf
(`descriptor.proto`, `struct.proto`, `wrappers.proto`, `timestamp.proto`…), **aucun nom
obfusqué de fichier Dofus**. Cette région du metadata est la bibliothèque protobuf
elle-même, pas notre protocole. **Conclusion honnête : je n'ai PAS trouvé le chemin vers
les descripteurs Dofus par cette voie dans le temps imparti** — soit ils n'existent pas
sous cette forme (l'obfuscateur pourrait retirer complètement `descriptorData` pour les
classes du protocole, puisque le nom même du fichier serait un indice), soit leur
localisation exacte demande de comprendre le VRAI format de concaténation des littéraux
C# dans ce binaire — piste ouverte, pas fermée, documentée pour ne pas être re-explorée
à l'identique.

## 6. Trous connus (v2)

- **1501/6183 champs « incertains » au vote** (provenances en désaccord sur répété/
  catégorie pour un même numéro) — jamais tranchés en silence, mais pas résolus non plus.
- **Le sous-ensemble jondo-proto (99 noms) ne recoupe quasiment jamais celui d'otomai**
  (2 noms communs sur l'ensemble, 0 dans ce run précis) — le témoin de stabilité §4 reste
  donc structurellement peu informatif tant que rien n'agrandit le recoupement.
- **Gatherer et luaxy partagent probablement une origine commune** (§2.3) — leur accord
  ne doit PAS être compté comme 2 provenances indépendantes dans une future analyse de
  robustesse, seulement dans `nb_provenances` brut (déjà le cas ici, à corriger dans un
  futur passage si l'origine commune est confirmée par une lecture des deux dépôts).
- **FileDescriptorProto (§5)** : chemin exploré, pas résolu — nécessite de comprendre
  le format exact de concaténation des littéraux C# dans ce binaire spécifique.
