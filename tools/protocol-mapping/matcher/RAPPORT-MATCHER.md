# RAPPORT-MATCHER — Étage 1, chaînon manquant : noms clairs ↔ classes obfusquées

> Chantier « Namaste 3 ». Outil déterministe, 0 LLM, stdlib Python seule. Entrées lues
> en lecture seule ; seule zone d'écriture : `tools/protocol-mapping/matcher/`. Rejouable de bout
> en bout : `extraire_signatures.py && attendus_depuis_noms.py && matcher.py && comparer_jondo.py`
> (`verifier_motif.py` est appelé automatiquement par `extraire_signatures.py`, et
> rejouable seul).

## 1. Chiffres mesurés (rejoués le 2026-09-04, `extraction-stats.json` fait foi)

| Mesure | Valeur |
|---|---|
| Classes `IBufferMessage` extraites (Game.dll + Connection.dll) | **2206** (2169+37 — recoupe EXACTEMENT le compte indépendant de `GATE-G0-RAPPORT.md`) |
| … dont messages de tête (profondeur 0, C#) | 1629 (1602 Game.dll, 27 Connection.dll) |
| Nœuds totaux (messages + enums + conteneurs `Types`) | 5740 |
| Champs protobuf (`const int`) | 6277 — **6277 résolus (100%), 0 non résolu** après correction du bug oneof (voir §5) |
| Groupes `oneof` détectés (plusieurs `const` → 1 seul champ `object` partagé) | 117 |
| Registre de noms (dernier segment) | 3533 noms uniques, **0 collision** |
| Noms clairs de tête (référence G0, `noms-protocole-en-clair.v2.txt`) | 513 (9 Connection.Protocol, 504 Game.Protocol) |
| … alternance `Types`/libellé dans les 1003 noms complets | **1003/1003 (100%), 0 exception** — mesuré, pas supposé |
| … dont forme d'imbrication TRIVIALE (aucun enfant) | 448/513 (87%) |
| Correspondances proposées (`DÉDUIT`) | **4** — 2 de tête + 2 par arrastre parent-enfant |
| À CLASSER | **511** |
| Accord Jondo — recoupement direct (nos propositions ∩ opcodes nommés par Jondo) | **0/0** (non défini — populations disjointes, cf. §4) |
| Accord Jondo — comparaison élargie, taux BRUT (rapprochement textuel + forme) | 60,5% sur N=38 — **mesuré comme NE MESURANT RIEN**, voir plancher de hasard ci-dessous |
| … plancher de hasard, 20 tirages (seeds 1..20) | moyenne **58,6%**, max **63,2%**, réel **60,5%** — réel DANS la plage du hasard → aucun signal démontré à ce niveau (cf. §4bis) |
| Validation du terrain (opcodes Jondo trouvés dans NOTRE dump, extrait indépendamment) | **291/293 (99,3%)** |
| Motif numéro↔type vérifié sur 3 témoins en clair (Any/Api/Duration) | **3/3 PASS** (`verifier_motif.py`) — a débusqué un vrai piège, voir §5 |
| Rejets À_CLASSER par cause | 0 candidat de même forme : 6 · candidats à égalité : 505 (dont 442 à cause de la forme triviale, 88% des égalités) · autre : 0 |

## 2. L'algorithme, en 10 lignes

1. Parser `cs/il2cpp.cs` (PAS `il2cpp.json` — mesuré : son unique clé est `addressMap`,
   une table d'adresses/RVA, aucun type résolu) en ARBRE (tabulation = profondeur).
2. Ne garder que les sous-arbres dont le `TypeDefIndex` de tête tombe dans
   `Ankama.Dofus.Protocol.{Game,Connection}.dll`.
3. Pour chaque classe, apparier chaque `const int` de champ à son `backing field`
   (le type juste après, en sautant `FieldCodec<T>`/`MessageParser<T>`) ; un groupe de
   `const` consécutifs sans champ entre eux = un `oneof` partageant un seul `object`.
4. Construire un registre global nom→nature (message/enum/autre) pour résoudre les
   références croisées (`hef.hee`).
5. Pour chaque nom clair, replier le conteneur `Types` (100% des 1003 noms alternent
   strictement `Types`/libellé — mesuré) → un arbre SÉMANTIQUE sans le bruit du wrapper.
6. Faire la même chose côté obfusqué : chaque nœud message n'a que des profondeurs
   PAIRES de vrais enfants messages/enums (mesuré sur les 2206 fiches) — le conteneur
   `Types` existe, mais est LUI AUSSI obfusqué (0 occurrence du littéral `class Types`
   dans nos 2 assemblies cibles).
7. Signature de forme = tuple récursif trié des formes des enfants (canonique, ordre-
   indépendant) — comparable directement des deux côtés.
8. Bucket = assembly (Connection vs Game, déterministe via le TypeDefIndex ET le
   namespace du nom clair).
9. Candidat retenu SEULEMENT si (bucket + forme exacte) désigne UN SEUL candidat.
10. Arrastre un niveau : une fois un nom de tête résolu, apparier ses enfants directs
    UNIQUEMENT quand la forme les distingue un-à-un des deux côtés (jamais deviné sur
    une égalité).

## 3. Pourquoi ce n'est PAS l'algorithme de Jondo, et pourquoi le dire est le résultat

`Matcher.cs` (a.1 de la spec) apparie **deux graphes de même nature** (obfusqué-ancien ↔
obfusqué-nouveau), chacun avec ses numéros de champ, ses types résolus, son graphe
complet de références — le round-0 (`Signatures`) et les rondes suivantes marchent
PARCE QUE les deux côtés portent la même richesse d'information.

Notre problème est **asymétrique** : un côté (nos 2206 classes obfusquées) a un graphe
complet ; l'autre (les 1003 littéraux clairs) n'a **ni numéro de champ ni type** —
mesuré par Jondo lui-même dans son propre fichier `nombres_reales_3.6.10.10.tsv` :
*« NADIE las referencia »* (orphelins, 3 coïncidences sur 2687 anciennes candidates,
du bruit). Le round-0 de Jondo (numéros+types de champ) **n'a donc pas de pendant côté
noms clairs** — ce n'est pas « pas encore fait », c'est structurellement absent des
données disponibles. Le seul axe commun mesuré aux deux côtés est la **forme
d'imbrication** (§2, étapes 5-7) : c'est l'adaptation réimplémentée ici, un round-0 de
Weisfeiler-Lehman restreint à cette seule dimension. Un score très en dessous du
11,3% de Jondo (§a.1 de la spec) est donc **attendu**, pas un signe d'échec de
l'implémentation : son signal (champs) est strictement plus riche que le nôtre.

## 4. Ce que la forme imbriquée apporte — mesuré avec/sans

| Sous-ensemble | N | Résolus (`DÉDUIT`) | Taux |
|---|---:|---:|---:|
| Noms de tête à forme **non triviale** (ont au moins un enfant) | 65 | 2 | **3,1%** |
| Noms de tête à forme **triviale** (aucun enfant, 87% des noms) | 448 | 0 | **0%** |

La forme imbriquée est le SEUL signal qui discrimine quoi que ce soit : sans elle
(bucket d'assembly seul), aucun nom — même parmi les 9 de Connection.Protocol — n'a de
candidat unique (27 candidats obfusqués pour 9 noms clairs). Avec elle, 100% des
résolutions viennent du sous-ensemble à forme non triviale (2/65), et 0% du sous-
ensemble trivial (2206 candidats environ pour chaque nom vide) — c'est cohérent et
mesuré, pas un artefact.

## 4bis. Plancher de hasard sur l'accord Jondo — CORRECTION issue d'une révision indépendante (04/09)

Ma première épreuve testait « l'accord doit s'effondrer sous mélange » — la révision indépendante a corrigé,
à raison : à 71%→62% on ne peut RIEN trancher, ce n'est pas une mesure. Le vrai témoin,
maintenant dans `matcher.py --epreuve` et `comparer_jondo.py` : mélanger les noms clairs
20 fois (seeds fixes 1..20), mesurer le taux de compatibilité Jondo (§3 de
`ACCORD-JONDO.md`) à chaque tirage, comparer le réel à la moyenne et au MAXIMUM.

```
20 tirages : [0.5263, 0.5789, 0.5263, 0.5789, 0.6053, 0.6316, 0.5, 0.5526, 0.5789,
              0.6316, 0.5789, 0.6316, 0.5526, 0.6316, 0.6316, 0.5526, 0.5526, 0.6316,
              0.6053, 0.6316]
moyenne_hasard = 58,6%   max_hasard = 63,2%   min_hasard = 50,0%   réel = 60,5%
```

**Verdict, chiffré, pas un seuil arbitraire : le réel n'est même pas le maximum des 20
tirages mélangés.** La comparaison élargie de `ACCORD-JONDO.md` §3 (rapprochement
textuel + compatibilité de forme) **ne mesure rien** au-delà de la ressemblance
structurelle de base — cohérent avec la cause déjà mesurée en §4 : 87% des noms de tête
ont une forme triviale, donc « compatible en forme » coïncide presque aussi souvent par
hasard que par vraie correspondance. **Le taux de 60,5% ne doit PAS être lu comme un
accord avec Jondo**, quel que soit son chiffre — résultat honnête, pas un échec de
l'épreuve.

Ceci ne remet PAS en cause le mécanisme du matcher réel (§4, `correspondance-noms-classes.tsv`) :
celui-ci exige un candidat UNIQUE (pas juste « compatible »), un critère strictement plus
sévère, et son propre témoin (identité des paires sous mélange, `matcher.py --epreuve`
témoin 2) reste vert : les 2 paires réelles disparaissent totalement sous mélange (0
recoupement), preuve que CE mécanisme-là est bien identité-dépendant. Les deux mesures
répondent à des questions différentes et ne se contredisent pas.

**Piste mesurée mais non exploitée en matching** : 103 classes-marqueurs `Reflection`
(`private static FileDescriptor X; public static FileDescriptor Y {get;}`, sans autre
membre) délimitent les 102 fichiers `.proto` d'origine dans Game.dll (1 seul dans
Connection.dll). C'est un signal RÉEL de regroupement par domaine, mais la taille de
ces blocs (jusqu'à 108 messages) ne colle pas proprement aux tailles de domaine
mesurées côté noms clairs (max 44, `Guild`) — pas de bijection simple taille↔domaine.
Utilisable en théorie pour une prochaine passe (ex. décoder les octets du
`FileDescriptorProto` sérialisé dans le champ statique de chaque marqueur, hors budget
ici), documenté pour ne pas être re-découvert à zéro.

## 5. Mes propres erreurs (corrigées, mesurées avant/après)

1. **`il2cpp.json` n'est pas ce que le brief supposait** — mesuré via `jq`, pas
   deviné : sa seule clé de haut niveau est `addressMap` (adresses/RVA, `fields` =
   2410 blobs d'octets statiques bruts). La vraie source (`cs/il2cpp.cs`) était déjà
   prouvée lisible par `gate-g0.py` — j'ai basculé dessus avant d'écrire une ligne de
   parseur JSON inutile.
2. **`object` (champ `oneof` partagé) classé `unresolu`** — corrigé en catégorie dédiée
   `oneof_object` (373 champs concernés).
3. **`MapField<K, V>` classé `unresolu`** — bug de découpage (traitait `"K, V"` comme un
   seul type) — corrigé en séparant clé/valeur avant classification.
4. **Consts `oneof` consécutifs perdus** — 3 `const int` suivis d'un SEUL champ `object`
   partagé (mesuré sur `hea`/TypeDefIndex 9451) faisaient marquer les 2 premiers
   `non_resolu` à tort — corrigé en regroupant les `const` en attente jusqu'au premier
   champ porteur trouvé. Résultat avant/après : 259 champs non résolus → **0**.
5. **Témoin `--epreuve` mal conçu au premier jet** — je testais la CHUTE du nombre de
   correspondances uniques sous mélange ; mesuré : le nombre restait identique (2→2)
   alors que les PAIRES elles-mêmes étaient toutes fausses (0 recoupement) — un
   comptage peut coïncider par hasard à petit N, pas l'identité des paires. Corrigé :
   le témoin compare maintenant l'ENSEMBLE des paires précises, pas leur nombre.
6. **Tentative initiale de faire coller le témoin sur « l'accord Jondo s'effondre »**
   — mesuré et ABANDONNÉ comme témoin (pas comme mesure) : le recoupement direct
   propositions/opcodes nommés est 0/0 des deux côtés (réel et mélangé, même
   population disjointe), et le sous-ensemble « nom Jondo proche d'un nom clair à forme
   non triviale » ne contient qu'1 cas — l'utiliser comme critère pass/fail aurait
   fabriqué une preuve sur un N insuffisant. **Corrigé une 2e fois par la révision indépendante**
   (§4bis) : même la comparaison élargie (N=38) n'est PAS un témoin valide sans plancher
   de hasard chiffré — mesuré, corrigé, gardé maintenant dans `matcher.py --epreuve` ET
   `comparer_jondo.py`.
7. **`n` réassigné par erreur dans `parse_tree`** — le compteur de progression
   (`n = len(lines)`) et le numéro de champ extrait (`n = int(cst.group(2))`) portaient
   le MÊME nom dans la même fonction ; le second écrasait le premier, rendant le
   logging de progression faux après le 1er champ rencontré (`"1000000/2 lignes…"` au
   lieu de `"…/1081734"`). Purement cosmétique (n'affectait aucune sortie), corrigé en
   renommant la variable locale (`champ_num`).
8. **Motif const→champ vérifié sur 3 témoins EN CLAIR (`verifier_motif.py`, demandé par
   team-lead)** — `Any`/`Api` passent 3/3 du premier coup ; `Duration` FAIL au premier
   essai : il porte des `public const int` qui ne sont PAS des numéros de champ
   (`NanosecondsPerSecond = 1000000000`, `NanosecondsPerTick = 100` — du code Google
   écrit à la main, pas généré par `protoc`). **Mesuré : ce piège ne touchait AUCUNE de
   nos 2206 classes cibles** (0 non-résolu avant et après le correctif), mais je l'ai
   durci quand même : `MAX_FIELD_NUMBER=100000` écarte toute valeur de const
   invraisemblable comme numéro de champ, et le témoin le rejoue pour le prouver plutôt
   que de l'affirmer. 3/3 après correctif.

## 6. Trous connus, non résolus ici

- **Aucun ancrage déterministe trouvé** pour un statut `VÉRIFIÉ` — cohérent avec
  l'hypothèse déjà réfutée (aucun descripteur protobuf en clair) citée par la mission.
  Tout le fichier `correspondance-noms-classes.tsv` est `DÉDUIT` ou `À_CLASSER`.
- **511/515 lignes en `À_CLASSER`** — la majorité écrasante. Le matcher REFUSE de
  deviner sur une égalité plutôt que de produire un faux vert.
- **Ordre de déclaration perdu côté noms clairs** — `noms-protocole-en-clair.v2.txt`
  est trié ALPHABÉTIQUEMENT par `gate-g0.py` (`sorted(ref)`), pas dans l'ordre de
  déclaration d'origine. L'arrastre parent-enfant ne peut donc apparier des frères de
  MÊME forme (ambigus par construction), seulement ceux dont la forme est unique parmi
  leurs frères.
- **`Reflection`/domaine** (§4) mesuré mais pas exploité — piste ouverte, pas fausse piste.
- **Byte-size réel non extrait** — « taille » dans les fiches JSONL = `field_count`
  (nombre de champs), pas un calcul d'agencement mémoire ; noté explicitement pour ne
  pas être lu comme une taille en octets.
- **Stabilité (déterminisme) auditée, pas seulement affirmée** — les seuls `set()` du
  code (`comparer_jondo.py`) ne servent qu'à des tests d'appartenance (`in`, `&`, `|`),
  jamais à produire un ordre de sortie ; le témoin 3 de `matcher.py --epreuve` le PROUVE
  en rejouant en 2 sous-processus séparés avec `PYTHONHASHSEED` différents (0 et 42) —
  un même processus réutilisé n'aurait pas pu détecter ce genre de bug (le seed de
  hachage est fixé une fois par processus).
