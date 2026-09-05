# Séquences canoniques observées

Chaque séquence a été **vue en situation**, l'action déclenchante étant annoncée
avant d'être faite. Les tailles sont mesurées, les délais aussi.

---

## Battement de cœur — VÉRIFIÉ
| sens | opcode | taille | nom |
|---|---|---|---|
| C→S | `kqo` | 40 o | BasicPingMessage |
| S→C | `kqy` | 29 o | BasicPongMessage |

Toutes les ~5 secondes, sans interruption. Sert de repère temporel pour dater
toutes les autres séquences.

---

## Rafale de bienvenue — VÉRIFIÉ, observée 3 fois à l'identique
Envoyée d'un bloc, **en moins d'une milliseconde**, après acceptation du ticket.

| ordre | opcode | taille | nom |
|---|---|---|---|
| 1 | `kra` | 25 o | AuthenticationTicketAcceptedMessage |
| 2 | `lqu` | 36 o | BasicTimeMessage |
| 3 | `hoy` | 40 o | HelloGameMessage |
| 4 | `kqu` | 46 o | ServerOptionalFeaturesMessage |
| 5 | `mgq` | 33 o | — |
| 6 | `mgt` | 29 o | — |
| 7 | `hpd` | 29 o | — |
| 8 | `krs` | 25 o | — |
| 9 | `mgz` | 33 o | ContentCatalogVersionMessage |
| 10 | `kqp` ×3 | 31/29/25 o | — |
| 11 | `kvi` | 92-112 o | CharactersListMessage |
| 12 | `kvd` | 25 o | CharactersListEndMessage |
| 13 | `jtg` | 25 o | GiftsListMessage |

Puis le client répond : `krt`, `kvc`, `krv` (266 o), `kwb`.

**Lecture DÉDUITE** : les cinq opcodes sans nom tombent entre « fonctionnalités du
serveur » et « version du catalogue », puis juste avant la liste des personnages.
Leur position les désigne comme **négociation de session**, pas comme du jeu.
À confronter au décodage des champs avant d'en faire un fait.

⚠️ *Les trois occurrences proviennent d'une même capture continue, pas de trois
sessions indépendantes : c'est une répétition, pas une triple corroboration.*

---

## Déplacement — VÉRIFIÉ
| ordre | sens | opcode | nom |
|---|---|---|---|
| 1 | C→S | `jrw` | GameMapMovementRequestMessage |
| 2 | S→C | `jsj` | GameMapMovementMessage |
| 3 | C→S | `jqi` | MapMovementConfirmRequest |
| 4 | S→C | `jsq` | MapMovementConfirmResponse |

---

## Dialogue avec un PNJ — VÉRIFIÉ
| ordre | sens | opcode | taille | rôle observé |
|---|---|---|---|---|
| 1 | C→S | `iov` | 56 o | clic sur le PNJ |
| 2 | S→C | `ioc` | 43 o | ouverture du dialogue |
| 3 | S→C | `ios` | 109 o | texte et choix proposés |
| 4 | C→S | `ioy` | 42 o | choix d'une réponse |
| 5 | S→C | `kld` | 29 o | fermeture (LeaveDialogMessage) |

**Famille `io*`** : les messages de dialogue partagent un préfixe.

---

## Changement d'équipement — VÉRIFIÉ, répété 3 fois à l'identique
Un seul clic déclenche **neuf messages**.

| ordre | sens | opcode | nom |
|---|---|---|---|
| 1 | C→S | `iuk` | ObjectSetPositionMessage |
| 2 | S→C | `ivq` | ObjectMovementMessage |
| 3-5 | S→C | `lym` `hie` `hii` | — |
| 6 | S→C | `iun` | InventoryWeightMessage |
| 7 | S→C | `jsn` | GameContextRefreshEntityLookMessage (117 o) |
| 8 | S→C | `lxc` | AppearancePreviewLookMessage (109 o) |
| 9 | S→C | `kub` | CharacterStatsListMessage (869 o) |

---

## Apparence / cosmétiques — VÉRIFIÉ, famille complète
Motif : `ly*` = requêtes du client, `lx*` = réponses du serveur.

| sens | opcode | nom |
|---|---|---|
| C→S | `lyk` | AppearanceOpenRequestMessage |
| C→S | `lyy` | AppearanceStateRequestMessage |
| C→S | `lyf` | AppearanceSlotSetRequestMessage |
| C→S | `lys` | AppearanceItemWearRequestMessage |
| S→C | `lxc` | AppearancePreviewLookMessage |
| S→C | `lxo` | AppearanceStateMessage |
| S→C | `lyj` | AppearanceSlotSetResultMessage |
| S→C | `lwz` | AppearanceItemWornMessage |

**Mesure parlante** : `lxc` grossit à mesure qu'on s'habille — 109 → 110 → 112 →
126 o. Le message porte l'apparence complète ; son poids le confirme sans décodage.

---

## Récolte / métiers — VÉRIFIÉ (famille `iw*` = interaction avec le décor)
| ordre | sens | opcode | nom |
|---|---|---|---|
| 1 | C→S | `iwo` | InteractiveUseRequestMessage |
| 2-3 | S→C | `iwf` `iwm` | — |
| 4 | S→C | `iwn` | InteractiveUsedMessage |
| — | | | *≈ 3,03 s de récolte* |
| 5 | S→C | `iwi` | — |
| 6 | S→C | `iua` | ObjectAddedMessage |
| 7 | S→C | `iun` | InventoryWeightMessage |
| 8 | S→C | `itn` | — |
| 9 | S→C | `irq` | JobExperienceMultiUpdateMessage |

**Délai mesuré : ~3 secondes** entre l'usage confirmé et l'objet obtenu. Un serveur
qui donne l'objet instantanément se trahit.

---

## Combat — VÉRIFIÉ
**Démarrage** (400 ms) : `hqa` (C→S) puis le serveur monte la scène d'un bloc —
`jsd` `kmu` `kml` `kmp` `jru` `lqu` `hjk`, puis **`kmk` répété une fois par
combattant** (×5 pour 5 combattants), puis `kam`.

**Pendant** : `jwe` (GameActionFightEvent) — une action, un message.

**Sortie** — identique en victoire et en défaite :
| ordre | sens | opcode | nom |
|---|---|---|---|
| 1 | C→S | `jti` | — |
| 2 | S→C | `kua` | — |
| 3 | S→C | `jyg` | GuildGeneralInformationEvent |
| 4 | S→C | `iua` ×2 | ObjectAddedMessage — le butin |
| 5 | S→C | `kub` | CharacterStatsListMessage (878 o) |
| 6 | S→C | `jru` | CurrentMapMessage |
| 7 | C→S | `jrh` | WorldEntryRequests |
| 8 | S→C | `jss` | MapComplementaryInformationsDataMessage (899 o) |
| 9 | S→C | `lva` | MapLoadedMessage |

Le retour au monde **recharge intégralement la carte**.

---

## Chat — VÉRIFIÉ
| sens | opcode | nom |
|---|---|---|
| C→S | `ktm` | ChatClientMultiMessage |
| S→C | `kti` | ChatServerMessage |

Une commande rend parfois **plusieurs** `kti` (mesuré : 216 o + 79 o pour `/help`).

---

## Caractéristiques — VÉRIFIÉ
| sens | opcode | nom |
|---|---|---|
| C→S | `kum` | StatsUpgradeRequestMessage |
| S→C | `kub` | CharacterStatsListMessage (878 o) |

---

## Ce qui ne parle PAS au serveur — mesuré à 0 trafic
Grimoire de sorts, filtres de sorts, guide d'aventure, fermeture de fenêtre.
**Conséquence de conception** : tout doit être envoyé à la connexion, le client
ne redemande rien pour afficher.

---

## Trames les plus volumineuses (les plus riches à décoder)
| opcode | taille | contexte |
|---|---|---|
| `ivi` | **87 881 o** | la plus grosse de la session |
| `mft` | 9 575 o | chargement en jeu |
| `lwt` | 4 068 o | — |
| `jxb` | 2 322 o | combat |
| `jss` | 899 o | informations complémentaires de carte |
| `kub` | 878 o | fiche de personnage |
