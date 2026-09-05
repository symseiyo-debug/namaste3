# Accord avec JondoEmu — mesuré, pas simulé

Source Jondo : `refs/JondoEmu/datos/anclas_3.6.10.10.tsv` — 99/293 opcodes portent un nom proposé.

## 1. Validation du terrain : même build, même obfuscation
- **291/293 (99.3%)** des opcodes Jondo existent comme nom de classe/nœud QUELQUE PART dans notre propre dump (extrait indépendamment, sans lire Jondo). Ça valide l'hypothèse de départ (même build 3.6.10.10 → même espace de noms obfusqués des DEUX côtés) — condition nécessaire pour que le reste de cette page ait un sens.

## 2. Recoupement DIRECT avec nos propositions réelles
- Nos 4 lignes `DÉDUIT` (matcher.py) ∩ les 99 opcodes nommés par Jondo : **0**.
- Mesuré, pas un bug : nos 2 correspondances de tête (`kfp`→GuildMission, `knk`→TreasureHuntEvent) sont des messages référencés en PROFONDEUR par un autre message (champs), jamais envoyés seuls sur le fil — donc jamais des « opcodes » au sens de Jondo (`type.ankama.com/<opcode>`, toujours de tête). Un taux d'accord sur cette population précise vaut 0/0 (non défini) ; la section 3 mesure une comparaison plus large.

## 3. Comparaison élargie : rapprochement textuel + compatibilité structurelle
Pour chacun des opcodes nommés par Jondo, on cherche le nom clair (parmi nos 513 noms de tête) dont les MOTS se recoupent le plus (Jaccard sur tokens camelCase, seuil 0,34, indépendant de notre matcher structurel) — puis on teste si CET opcode, tel que NOUS l'avons mesuré dans notre dump, a bien la même forme imbriquée et le même bucket d'assembly que ce nom clair l'exigerait.

- rapprochement textuel trouvé : **38/99**
- sans rapprochement textuel plausible (score < 0,34) : **61**
- compatibles structurellement : **23**
- **INCOMPATIBLES : 15**
- sans donnée (opcode absent de notre dump) : **0**
- taux de compatibilité BRUT = **60.5%**

### Plancher de hasard — CORRECTION mesurée (revue indépendante, 04/09)
« L'accord doit s'effondrer sous mélange » n'est pas une mesure : 71%→62% ne permet de trancher ni dans un sens ni dans l'autre. Le vrai témoin : mélanger les noms clairs 20 fois (seeds fixes 1..20), mesurer ce même taux de compatibilité à chaque tirage, comparer le RÉEL à la moyenne et au MAXIMUM des 20.

- les 20 tirages : `[0.5263, 0.5789, 0.5263, 0.5789, 0.6053, 0.6316, 0.5, 0.5526, 0.5789, 0.6316, 0.5789, 0.6316, 0.5526, 0.6316, 0.6316, 0.5526, 0.5526, 0.6316, 0.6053, 0.6316]`
- moyenne du hasard : **58.6%**
- maximum du hasard : **63.2%**
- réel : **60.5%**

**Verdict : cette comparaison élargie NE MESURE RIEN.** Le réel (60.5%) tombe DANS la plage des 20 tirages mélangés [50.0%, 63.2%] — il n'est même pas le maximum des 20. Ce n'est pas un échec de la mesure : c'est le résultat. La cause la plus probable, déjà mesurée ailleurs (`RAPPORT-MATCHER.md` §4) : 87% des noms de tête ont une forme d'imbrication TRIVIALE (aucun enfant), donc « compatible en forme » coïncide presque aussi souvent par hasard que par vraie correspondance — le taux brut de 60,5% ne doit PAS être lu comme un accord avec Jondo, quel que soit son chiffre. Ce que ce même mécanisme arrive à faire sur le sous-ensemble à forme NON triviale (le matcher réel, `correspondance-noms-classes.tsv`) reste, lui, mesuré séparément et différent : voir `RAPPORT-MATCHER.md` §4 (3,1% de résolution UNIQUE sur les 65 noms à forme non triviale, 0% sur les 448 triviaux) — un mécanisme plus strict (candidat UNIQUE, pas juste « compatible ») que celui mesuré ici.

### Tous les désaccords (incompatibilité structurelle)
| opcode | nom Jondo | nom clair rapproché | notre forme | forme attendue | assembly OK |
|---|---|---|---|---|---|
| `kvz` | CharacterCreationRequestMessage | Com.Ankama.Dofus.Server.Game.Protocol.Common.Character | `()` | `(((((),),), (((), ()),)),)` | oui |
| `jru` | CurrentMapMessage | Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapCurrentEvent | `((),)` | `()` | oui |
| `ivx` | InventoryContentMessage | Com.Ankama.Dofus.Server.Game.Protocol.Inventory.InventoryContentEvent | `((),)` | `()` | oui |
| `jsj` | GameMapMovementMessage | Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapMovementEvent | `((),)` | `()` | oui |
| `jqi` | MapMovementConfirmRequest | Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapMovementConfirmRequest | `((),)` | `()` | oui |
| `jsq` | MapMovementConfirmResponse | Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapMovementConfirmRequest | `((),)` | `()` | oui |
| `khd` | ExchangeLeaveMessage | Com.Ankama.Dofus.Server.Game.Protocol.Exchange.ExchangeLeaveEvent | `((),)` | `()` | oui |
| `iuq` | ShortcutBarReplacedMessage | Com.Ankama.Dofus.Server.Game.Protocol.Inventory.ShortcutBarReplacedEvent | `((),)` | `()` | oui |
| `hng` | SpellVariantActivationSuccessMessage | Com.Ankama.Dofus.Server.Game.Protocol.Spell.SpellVariantActivationEvent | `((),)` | `()` | oui |
| `itz` | ShortcutBarAddRequestMessage | Com.Ankama.Dofus.Server.Game.Protocol.Inventory.ShortcutBarAddRequest | `((),)` | `()` | oui |
| `hjj` | TeleportDestinationsMessage | Com.Ankama.Dofus.Server.Game.Protocol.Teleportation.TeleportDestinationsEvent | `((),)` | `()` | oui |
| `kld` | LeaveDialogMessage | Com.Ankama.Dofus.Server.Game.Protocol.Dialog.DialogLeaveEvent | `((),)` | `()` | oui |
| `jsn` | GameContextRefreshEntityLookMessage | Com.Ankama.Dofus.Server.Game.Protocol.Common.EntityLook | `((),)` | `()` | oui |
| `kti` | ChatServerMessage | Com.Ankama.Dofus.Server.Connection.Protocol.Server | `()` | `()` | NON |
| `kqy` | BasicPongMessage | Com.Ankama.Dofus.Server.Game.Protocol.Connection.PongEvent | `((),)` | `()` | oui |

### 5 désaccords analysés — la question n'est pas qui a tort
Correction de la revue indépendante : le bon angle n'est pas « qui a raison » mais « les deux instruments regardent-ils la MÊME CHOSE ». Un désaccord localisé sur ce même build est soit une erreur (rapprochement textuel qui a pris le mauvais candidat — le cas le plus probable ici, l'heuristique est un simple Jaccard de mots sans connaissance du protocole), soit une AMBIGUÏTÉ STRUCTURELLE RÉELLE — et ce second cas est une trouvaille à rapporter comme telle, pas un bug à corriger.


**`kvz` (Jondo: CharacterCreationRequestMessage) ↔ Com.Ankama.Dofus.Server.Game.Protocol.Common.Character**
- Jondo dit (mesuré sur 242 captures) : Crear un personaje.
- notre forme mesurée : `()` — forme attendue par le nom clair : `(((((),),), (((), ()),)),)`
- notre forme est TRIVIALE alors que le nom clair en attend une : deux lectures possibles, ni tranchée ni à trancher ici — (a) les deux instruments regardent des objets DIFFÉRENTS (rapprochement textuel fautif, cas fréquent vu que 87% des noms de tête ont une forme triviale et ne discriminent rien) ; (b) les deux regardent le MÊME message mais son schéma a changé entre la mesure du littéral et cette build — dans ce cas précis (b) serait la trouvaille, pas l'erreur.

**`jru` (Jondo: CurrentMapMessage) ↔ Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapCurrentEvent**
- Jondo dit (mesuré sur 242 captures) : Carga este mapa; enviarlo dos veces hace que el cliente recargue el mundo en bucle.
- notre forme mesurée : `((),)` — forme attendue par le nom clair : `()`
- l'inverse : notre classe a des enfants, le nom clair n'en attend aucun — même double lecture que ci-dessus, pas tranchée.

**`ivx` (Jondo: InventoryContentMessage) ↔ Com.Ankama.Dofus.Server.Game.Protocol.Inventory.InventoryContentEvent**
- Jondo dit (mesuré sur 242 captures) : El inventario, construido desde la base de datos; el hueco se omite cuando es cero porque cero es el amuleto.
- notre forme mesurée : `((),)` — forme attendue par le nom clair : `()`
- l'inverse : notre classe a des enfants, le nom clair n'en attend aucun — même double lecture que ci-dessus, pas tranchée.

**`jsj` (Jondo: GameMapMovementMessage) ↔ Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapMovementEvent**
- Jondo dit (mesuré sur 242 captures) : El movimiento confirmado; saltarselo deja al actor con orientacion cero.
- notre forme mesurée : `((),)` — forme attendue par le nom clair : `()`
- l'inverse : notre classe a des enfants, le nom clair n'en attend aucun — même double lecture que ci-dessus, pas tranchée.

**`jqi` (Jondo: MapMovementConfirmRequest) ↔ Com.Ankama.Dofus.Server.Game.Protocol.Gamemap.MapMovementConfirmRequest**
- Jondo dit (mesuré sur 242 captures) : Estoy en el borde, puedo salir.
- notre forme mesurée : `((),)` — forme attendue par le nom clair : `()`
- l'inverse : notre classe a des enfants, le nom clair n'en attend aucun — même double lecture que ci-dessus, pas tranchée.

