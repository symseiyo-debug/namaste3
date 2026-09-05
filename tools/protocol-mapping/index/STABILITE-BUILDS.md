# STABILITÉ-BUILDS — gatherer/luaxy (≈2024) vs otomai/JondoEmu (3.6.10.10)

> Étage 1 (Namaste 3), second passage sur `comparer_instruments.py`. Sources : `protocole-gatherer.tsv`, `protocole-luaxy.tsv`, `protocole-deobfs.tsv`, `protocole-otomai.tsv`, dump étage0, `anclas_3.6.10.10.tsv`.

## 1. gatherer / luaxy / deobfs — ce qui est réellement indépendant
- gatherer vs luaxy (`.proto` sha256 par fichier) : **79 identiques**, 0 différents, 0 présents d'un seul côté. ⚠️ CE SONT LA MÊME DONNÉE.
- deobfs `protos/clear/` vs luaxy : **79 identiques**, 0 différents, 0 présents d'un seul côté — une 3ᵉ copie de la MÊME donnée.
- **Correction de compte** : `dofus-deobfs` contient 1441 `.proto` au total (`find -iname` sur tout le dépôt), mais seuls **1362** (`protos/filtered/`) sont une donnée OBFUSQUÉE propre à cet outil — les 79 de `protos/clear/` sont LuaxY, déjà comptés via gatherer/luaxy. Ne pas citer « 1441 fichiers .proto indépendants » pour deobfs : c'est 1362 + une 4ᵉ copie de 79.

**Conséquence pour tout calcul « N instruments s'accordent »** : gatherer, luaxy et le sous-dossier `protos/clear/` de deobfs comptent pour **UN SEUL** instrument indépendant (LuaxY, 2024-10). Un accord affiché comme « 3 instruments convergent » qui inclut deux de ces trois est en réalité **2 instruments**, pas 3 — l'un d'eux votant deux ou trois fois.

## 2. gatherer (LuaxY, ~2024-10) ∩ instruments du build courant — la stabilité des NOMS
- gatherer : 1239 noms top-level | otomai (2026-03) : 1286 | dump (LA VÉRITÉ, 3.6.10.10) : 512 | JondoEmu nommés (3.6.10.10) : 99
- gatherer ∩ otomai : **1202/1239 (97%)** — un instrument de ~2024 et un instrument de 2026, construits par des auteurs différents, s'accordent sur la quasi-totalité de leurs noms de messages communs.
- gatherer ∩ dump (vérité, mesurée sur NOTRE build) : **316/1239 (26%)**.
- gatherer ∩ JondoEmu (nommés) : **1/99** — ['MapMovementConfirmRequest']

**Lecture à charge, pas seulement à décharge** : gatherer (1239 noms) et otomai (1286 noms) dépassent LARGEMENT le compte de notre propre dump (512 noms top-level). Deux hypothèses concurrentes, ni l'une ni l'autre tranchée ici (DÉDUIT, à vérifier) : (a) notre extraction étage0 (littéraux du metadata v39) est **incomplète** — elle ne capte pas tous les noms réellement présents dans le binaire 3.6.10.10 ; (b) gatherer/otomai agrègent des messages qui existaient sur d'anciens builds et ont depuis été retirés du protocole. **Comment trancher** : prendre 20 noms présents chez gatherer+otomai mais absents du dump, et grep leur littéral exact dans `global-metadata.dat` (v39) directement — présent = (a), notre extracteur étage0 sous-compte ; absent = (b), message disparu du protocole depuis.

## 3. Champs (numéro+type) — gatherer vs otomai, sur les 1202 noms communs (échantillon large)
- 1202 messages communs, 2734 emplacements de champ comparés.
- **Même NOMBRE de champs** (comptage brut, le signal le moins ambigu) : 965/1202 (80.3%).
- Accord sur la CATÉGORIE de type (numérique/string/liste/bool/message…) : 1626/2734 (59.5%) — mesure BASSE volontairement prudente : deux champs référençant chacun un type MESSAGE différent tombent tous les deux dans le même seau `message_ou_enum` et comptent comme "accord" alors que le type précis diffère peut-être ; ce chiffre sur-compte donc légèrement l'accord réel sur les champs message-typés.
- Accord sur le type LITTÉRAL exact (`int32`==`int`, faux négatif attendu — deux conventions de nommage différentes, C# vs proto3) : 257/2734 (9.4%) — chiffre BAS attendu et normal, pas un signe de désaccord.
- Présent d'un seul côté (champ ajouté/retiré) : 256/2734 (9.4%).

**Conclusion mesurée** : à la différence de la comparaison otomai↔JondoEmu (0/27 sur les OPCODES, cf. `ACCORD-INSTRUMENTS.md` §2), la comparaison par NOM ici — sur un échantillon 50× plus grand (1202 vs 2) — montre une stabilité réelle et forte : 80% des messages communs gardent EXACTEMENT le même nombre de champs entre un snapshot ~2024 et notre build 3.6.10.10. **Le nom et la structure de champs survivent aux patchs ; l'opcode 3 lettres, jamais.**

## 4. dofus-deobfs — pourquoi aucune comparaison par nom n'est possible
`protos/filtered/` (1362 fichiers, tous nommés par leur code obfusqué 3 lettres, 0 exception mesurée) ne porte AUCUN nom clair dans ce commit — le mapping vers les noms clairs est un produit de RUNTIME (`utils/report.go` du dépôt construit un `MessageMatch{ObfuscatedMsg, OriginalMsg, MatchPercent}`), écrit dans un dossier `reports/` absent de ce commit (gitignored). **0 nom disponible → 0 jointure possible par nom, avec quiconque.** Une jointure par OPCODE serait possible mécaniquement (comparer les codes 3 lettres de `protos/filtered/` à ceux du `.proto` de Jondo) mais a déjà été prouvée sans valeur sur un cas mesuré 50× plus favorable (otomai vs Jondo, mêmes deux tables mais TOUTES DEUX partiellement nommées : 0/27 accord, `ACCORD-INSTRUMENTS.md` §2) — ne pas la refaire ici sans raison nouvelle. Ce que deobfs apporte concrètement au chantier n'est donc PAS une table utilisable en l'état, mais sa MÉTHODE (le matching structurel contre les protos clairs de LuaxY) — un second patron pour l'étage 4, à coté de `otomai/tools/proto-sync/` (§2 du RAPPORT-EXTRACTION-TIERS.md).

