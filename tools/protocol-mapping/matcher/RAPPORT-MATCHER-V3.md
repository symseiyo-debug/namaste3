# RAPPORT-MATCHER-V3 — graines Jondo directes + propagation sur voisinage obfusqué

> Suite de v1/v2. v1/v2 restent intactes. Pipeline complet :
> `extraire_signatures.py && extraire_contexte.py && charger_proto_clair.py &&
> matcher_v2.py && matcher_v3.py`.

## 1. Chiffres v1 → v2 → v3

| Mesure | v1 | v2 | v3 |
|---|---:|---:|---:|
| Correspondances `DÉDUIT` | 4 | 36 | **158** (×4,4 vs v2, ×39,5 vs v1) |
| Graines de départ | 2 (forme) | 6 (forme+champs) | **133** (99 anclas Jondo + 36 v2, 2 conflits internes résolus) |
| Arrastre/propagation | 2 | 3 | **25** |
| Arrosage | 0 | 19 | 5 (+ bonus voisinage disponible, jamais décisif ce run — §4) |
| Rétrogradés pour conflit inter-sources | — | — | **5** (jondo-anclas vs v2 sur le même nom, cf. §3) |
| À CLASSER | 1793 | 1793 | 1239 |
| … dont sans candidat | — | — | 83 |
| … dont à égalité | — | — | 1156 |

## 2. Part des messages avec porteur en clair — mesure clé demandée, résultat net

`extraire_contexte.py` (nouveau) scanne TOUT `cs/il2cpp.cs` (pas seulement nos 2
assemblies) pour chaque signature de méthode citant un de nos 2206 tokens (paramètre,
retour, générique). Résultat FINAL, après 2 bugs trouvés et corrigés en chemin :

**0/2206 (0,0%) classes obfusquées ont un porteur EN CLAIR.**

- 2206/2206 (100%) sont citées au moins une fois quelque part dans le dump.
- 651 arêtes de co-occurrence obfusqué↔obfusqué (méthode citant 2 tokens à la fois).

Deux bugs trouvés et corrigés AVANT de rendre ce chiffre :
1. Le texte `namespace X` de ce décompilateur ne délimite RIEN — une fois émis, il
   « colle » à tout ce qui suit jusqu'à la prochaine directive, y compris des classes du
   protocole obfusqué qui n'ont EN VRAI aucun namespace (mesuré : `namespace
   Unity.Mathematics` attribué à tort à `hdw` et consorts — donnait un faux 86,9% de
   porteurs « clairs »). Corrigé : classification par TypeDefIndex/assembly (même
   méthode que v1/gate-g0.py), jamais par le texte.
2. Même après correction, `Core.dll` (hors de nos 2 assemblies protocolaires) s'est
   révélé LUI AUSSI obfusqué — mêmes tokens tout-minuscule que le protocole
   (`ebu`,`eqq`…). Ajout d'un test de lisibilité du nom (une classe C# réelle est en
   PascalCase, jamais tout-minuscule) : le chiffre est tombé à 0,04% puis, après un 3e
   bug (le token `int`, une VRAIE classe obfusquée nommée littéralement `int` par
   collision avec le mot-clé C#, polluait 11278 citations fausses), à **0,0% net**.

**Conclusion, mesurée pas supposée : l'obfuscation d'Ankama couvre TOUT le code de
première partie visible statiquement, pas seulement le protocole.** Aucune ancre
sémantique en clair n'existe dans le dump statique pour nommer un message. Ça valide
directement la règle L7 du projet (« l'analyse dynamique du client est la
voie du debug complet ») avec un chiffre : le statique donne la FORME et le VOISINAGE,
jamais le SENS — le sens ne peut venir que d'une capture réelle ou d'un nom déjà connu
par ailleurs (Jondo, otomai/gatherer/luaxy).

## 3. Graines Jondo directes — et un cas où elles se trompaient probablement

99 opcodes nommés (`anclas_3.6.10.10.tsv`, « code + 242 captures » selon son propre
en-tête) + 36 de v2 = 135 graines, 2 conflits internes (même opcode, nom différent entre
anclas et v2) — non tranchés en silence, listés. Après propagation, **7 noms clairs
étaient revendiqués par plus d'un token** :
- **5 conflits RÉELS entre jondo-anclas et v2** (même nom clair, tokens différents) —
  résolus en gardant la version STRUCTURELLE (v2, données de champs réelles), jondo-anclas
  rétrogradé en `À_CLASSER` avec la raison explicite.
- **2 réutilisations légitimes** (`ObjectItemInventory`×3, `MountData`×2) — un même type
  clair référencé par PLUSIEURS messages parents différents ; le protobuf réutilise le
  type, mais le C# généré compile une copie imbriquée DISTINCTE par parent — chaque
  copie est une classe obfusquée à part entière. Gardées `DÉDUIT`, notées.

**Un des 5 conflits mérite d'être signalé nommément** : `jtg` → `GiftsListMessage`
(jondo-anclas) a été rétrogradé au profit de `kmz` → `GiftsListMessage` (v2). Or `jtg`
EST le vrai `GiftsListMessage` — VÉRIFIÉ dans `SEQUENCE-CHEMIN-CRITIQUE-JONDO.md` §3.6
(rafale de bienvenue, sourcé `ConnectionProtocol.cs:218`, 242 captures), un document que
j'ai lu et confirmé indépendamment AVANT ce chantier. La règle « v2 structurel > jondo
proposition » n'est donc PAS toujours correcte — ici c'est probablement `kmz` qui se
trompe (un faux positif d'arrosage structurel), pas `jtg`. **Je n'ai pas eu le temps de
construire une 3e priorité (opcodes VÉRIFIÉS par capture, au-dessus de jondo-anclas ET
de v2)** — ce cas précis est corrigible à la main (`jtg`→`GiftsListMessage`,
`kmz`→À_CLASSER) mais je ne l'ai PAS fait automatiquement pour ne pas fabriquer une
règle ad hoc sur un seul cas observé. Signalé, pas caché.

## 4. Épreuve v3 — 3 témoins, un résultat honnête et un négatif franc

- **Témoin 1 (déterminisme)** : sha256 identique sur 2 rejeux. ✅
- **Témoin 2 (sabotage voisinage, 10% des 651 arêtes cassées)** : **0 correspondance
  dépendait du bonus de voisinage** sur ce run — le mécanisme est implémenté, éprouvé
  (rejoué, sabotable), mais **n'a eu AUCUN impact mesurable sur le résultat final** :
  soit les paires qu'il aurait pu débloquer étaient déjà résolues par le round-0 seul,
  soit le bonus (+0,05) n'a jamais suffi à faire basculer un candidat sous les seuils
  0,55/0,08. Négatif franc, rapporté tel quel — pas un échec de l'épreuve, un résultat.
- **Témoin 3 (plancher de hasard, CORRIGÉ en cours de route)** : mon premier passage
  mesurait seulement le COMPTE de `DÉDUIT` sous graines mélangées (réel=158, hasard
  moyenne=153,2, max=165) — **réel DANS la plage du hasard, comme en v1/v2**. Mais un
  comptage seul ne prouve rien (même piège déjà trouvé et corrigé en v1 le même jour) :
  la structure de propagation est IDENTIQUE quelles que soient les étiquettes, donc le
  COMPTE de correspondances produites ne peut PAS varier avec le mélange, seule leur
  IDENTITÉ le peut. Mesuré directement : sur les tokens communs entre le run réel et
  chaque tirage mélangé, l'**accord d'identité tombe à 4,6% en moyenne (max 8,1%)** —
  effondrement net. **Le mécanisme est bien identité-dépendant** ; c'est le compte seul
  qui ne mesure rien, pas la méthode.

## 5. Ce qui reste inatteignable par le statique — à passer à la chaîne L7

- **Tout nom de message sans opcode dans anclas.tsv ET sans nom otomai/gatherer/luaxy
  cohérent** : 1239 lignes `À_CLASSER`, dont 83 sans le moindre candidat structurel. Le
  statique a épuisé sa contribution ; ces noms ne peuvent venir que d'une capture réelle
  (§2, 0% de porteur en clair) ou d'un nommage humain sur trace.
- **Les 194 opcodes Jondo « sans nom mais avec séquence connue »** — non exploités
  comme graines nommées ici (aucun nom à propager), mais leur POSITION dans la rafale de
  bienvenue est déjà câblée comme arête de voisinage (`RAFALE_BIENVENUE`, 13 opcodes
  VÉRIFIÉS du chemin critique). Les 181 restants (194-13) demandent soit de relire
  `docs/opcodes.md`/`world.md` de Jondo plus large que ce que j'ai eu le temps de
  cartographier, soit une capture réelle.
- **Le cas `jtg`/`kmz` (§3)** — la preuve qu'un opcode déjà VÉRIFIÉ par 242 captures
  peut être écrasé à tort par une règle automatique trop simple ; une hiérarchie de
  priorité à 3 niveaux (capture vérifiée > structure v2 > proposition Jondo seule)
  reste à construire.
- **`decoder_filedescriptor.py`** (RAPPORT-MATCHER-V2.md §5) — piste ouverte, pas fermée.

## 6. Fichiers produits (v3)
`extraire_contexte.py`, `matcher_v3.py`, `contexte-appels.jsonl`, `aretes-voisinage.jsonl`,
`correspondance-v3.tsv`, ce fichier. `signatures-obfusquees.jsonl`/`signatures-claires.jsonl`
partagés avec v1/v2 (régénérés avec le correctif `OTOMAI_SCALARS`, cf. §historique commits).
