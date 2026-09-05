# ACCORD-INSTRUMENTS — otomai vs sniffer vs dump vs JondoEmu

> Étage 1 (Namaste 3), croisement de 4 instruments protocole 3.0 indépendants.
> Sources : `protocole-otomai.tsv`, `opcodes-sniffer.tsv` (ce dossier), `internal/noms-protocole-en-clair.v2.txt`, `refs/JondoEmu/datos/anclas_3.6.10.10.tsv`, `refs/JondoEmu/datos/protocolo_3.6.10.10.proto`.

## 0. Ce que chaque instrument porte réellement (mesuré, pas supposé)
- **otomai** : 1285 opcodes 3 lettres top-level, 1285 noms clairs uniques (classes C# de BubbleBot, réimplémentation communautaire du protocole 3.0).
- **sniffer** : 8 lignes au total, **0 table opcode↔nom réelle embarquée** — voir §4 et `RAPPORT-EXTRACTION-TIERS.md`. Toutes les lignes sont des exemples de doc ou des fixtures de test (`--epreuve` de `extraire_opcodes_sniffer.py` le prouve par sabotage).
- **dump (LA VÉRITÉ)** : 1003 noms de types au total, 513 top-level (mesure seconde voie : `[l for l in lignes if '+' not in l]`, conforme au 513 du cahier §ETAGE0), 512 noms feuille UNIQUES (doublon mesuré : `['CharacterInformation']` — deux namespaces différents partagent un même nom court, sans conséquence).
- **JondoEmu** : `anclas_3.6.10.10.tsv` a 293 opcodes documentés dont **99 nommés** (les autres 194 sont vus/décrits sans nom proposé). `protocolo_3.6.10.10.proto` a 2169 blocs `message` (numéro+type de champ dits VRAIS par son en-tête, noms de champ encore obfusqués). **Les noms de Jondo sont des PROPOSITIONS stylées, pas des extractions** — son propre en-tête le dit : « Ankama ne publie pas les noms... le nom de cette colonne est celui qui correspond à ce qu'il fait ». Ne pas les traiter comme une 3ᵉ mesure indépendante du nom réel, seulement de l'OPCODE et du COMPORTEMENT observé.

## 1. Intersections de NOMS CLAIRS, par paire d'instruments

### otomai ∩ dump (vérité)
- otomai : 1285 noms | dump (vérité) : 512 noms | intersection : **335** (65.4% du plus petit)
- top 10 : AccountCapabilitiesEvent, AccountInformationUpdateEvent, Achievement, AchievementRewardRequest, AchievementRewardResultEvent, AchievementsPioneerRanksResponse, AcquaintanceInformation, ActorPositionInformation, AddContactFailureEvent, AddTagStorageResponse
- présents seulement chez otomai : 950 (ex. AVAStateUpdateRequest, AccessoryPreviewErrorEvent, AccessoryPreviewEvent, AccessoryPreviewRequest, AccountAdditionalFacesEvent)
- présents seulement chez dump (vérité) : 177 (ex. AccountRightsEvent, AcquaintanceServersResponse, ActivatePaddockGaugeResponse, AddRidesFromItemRequest, AddRidesFromItemResponse)

### otomai ∩ JondoEmu (nommés)
- otomai : 1285 noms | JondoEmu (nommés) : 99 noms | intersection : **2** (2.0% du plus petit)
- top 10 : MapMovementConfirmRequest, MapMovementConfirmResponse
- présents seulement chez otomai : 1283 (ex. AVAStateUpdateRequest, AccessoryPreviewErrorEvent, AccessoryPreviewEvent, AccessoryPreviewRequest, AccountAdditionalFacesEvent)
- présents seulement chez JondoEmu (nommés) : 97 (ex. AppearanceAuraRequestMessage, AppearanceAuraResultMessage, AppearanceItemWearRequestMessage, AppearanceItemWornMessage, AppearanceOpenRequestMessage)

### dump (vérité) ∩ JondoEmu (nommés)
- dump (vérité) : 512 noms | JondoEmu (nommés) : 99 noms | intersection : **2** (2.0% du plus petit)
- top 10 : MapMovementConfirmRequest, MapMovementConfirmResponse
- présents seulement chez dump (vérité) : 510 (ex. AccountCapabilitiesEvent, AccountInformationUpdateEvent, AccountRightsEvent, Achievement, AchievementRewardRequest)
- présents seulement chez JondoEmu (nommés) : 97 (ex. AppearanceAuraRequestMessage, AppearanceAuraResultMessage, AppearanceItemWearRequestMessage, AppearanceItemWornMessage, AppearanceOpenRequestMessage)

### sniffer ∩ otomai
- sniffer : 7 noms | otomai : 1285 noms | intersection : **2** (28.6% du plus petit)
- top 10 : MapMovementEvent, MapMovementRequest
- présents seulement chez sniffer : 5 (ex. Alpha, Charlie, FriendlyInner, Goodbye, Hello)
- présents seulement chez otomai : 1283 (ex. AVAStateUpdateRequest, AccessoryPreviewErrorEvent, AccessoryPreviewEvent, AccessoryPreviewRequest, AccountAdditionalFacesEvent)

### sniffer ∩ dump (vérité)
- sniffer : 7 noms | dump (vérité) : 512 noms | intersection : **1** (14.3% du plus petit)
- top 10 : MapMovementEvent
- présents seulement chez sniffer : 6 (ex. Alpha, Charlie, FriendlyInner, Goodbye, Hello)
- présents seulement chez dump (vérité) : 511 (ex. AccountCapabilitiesEvent, AccountInformationUpdateEvent, AccountRightsEvent, Achievement, AchievementRewardRequest)

### otomai ∩ dump ∩ JondoEmu (triple accord) : **2** — ['MapMovementConfirmRequest', 'MapMovementConfirmResponse']

## 2. Accord OPCODE↔NOM entre otomai et JondoEmu — LA TROUVAILLE

**Jointure par OPCODE (chaîne 3 lettres identique)** : 27 opcodes existent dans les deux tables. Accord sur le nom : **0/27**. Désaccord : **27/27**.

**➡ 0 accord sur les 27 collisions d'opcode.** La jointure par identifiant opcode entre deux extractions indépendantes du même build nominal (3.6.10.10) est **entièrement fallacieuse** — exactement le piège que le cahier §ETAGE1 anticipait pour 2.42→2.73 (« une jointure par id rendrait TOUTES les paires fausses avec l'apparence d'un succès »), ici mesuré ENTRE DEUX OUTILS visant le MÊME build. Un opcode 3 lettres identique dans deux extractions ne prouve RIEN sur l'identité du message ; c'est une collision dans un espace de ~17 576 codes.

Désaccords (10 premiers sur 27, liste complète en annexe §5) :

| opcode | nom otomai | nom JondoEmu (proposé) |
|---|---|---|
| `hif` | ForgettableSpellsEvent | OrnamentSelectedMessage |
| `hjc` | SpouseInformationEvent | TeleportRequestMessage |
| `hjj` | AccessoryPreviewRequest | TeleportDestinationsMessage |
| `hng` | PresetUseResponse | SpellVariantActivationSuccessMessage |
| `irq` | ExchangeSellRequest | JobExperienceMultiUpdateMessage |
| `itc` | DebugClearHighlightCellsEvent | StorageObjectRemoveMessage |
| `itd` | DumpedEntityStatsEvent | StorageObjectUpdateMessage |
| `itz` | ContextReadyRequest | ShortcutBarAddRequestMessage |
| `iua` | EntitiesDispositionEvent | ObjectAddedMessage |
| `iun` | UnBlockEvent | InventoryWeightMessage |

**Jointure par NOM CLAIR (la voie correcte)** : 2 noms communs (['MapMovementConfirmRequest', 'MapMovementConfirmResponse']). Sur CES messages authentifiés par le nom, l'opcode concorde-t-il ?
- `MapMovementConfirmResponse` : otomai=`ifs` vs JondoEmu=`jsq` — **DIFFÉRENT**
- `MapMovementConfirmRequest` : otomai=`igg` vs JondoEmu=`jqi` — **DIFFÉRENT**
- Accord opcode sur nom commun : 0/2.

## 3. Champs (numéro+type) otomai vs Jondo `.proto`, sur les messages COMMUNS (par nom)

Échantillon disponible : **2** messages (limité par les 99 noms proposés de JondoEmu — ce n'est pas un défaut du script, c'est la taille réelle du recoupement possible ; voir §0).

### `MapMovementConfirmRequest` — otomai `igg` (0 champs) vs Jondo `jqi` (1 champs)
- réf. JondoEmu anclas : refs/JondoEmu/datos/anclas_3.6.10.10.tsv, opcode `jqi` — forme observée sur le fil : « empty »
  - f1: otomai=`—` jondo=`jqg` → seulement chez jondo (`jqg`)

### `MapMovementConfirmResponse` — otomai `ifs` (0 champs) vs Jondo `jsq` (1 champs)
- réf. JondoEmu anclas : refs/JondoEmu/datos/anclas_3.6.10.10.tsv, opcode `jsq` — forme observée sur le fil : « empty, id echoed »
  - f1: otomai=`—` jondo=`jso` → seulement chez jondo (`jso`)

**Taux de champs en accord de catégorie sur l'échantillon : 0/2 (0%).** Échantillon minuscule (2 messages) — un pourcentage sur si peu de cas n'est PAS une mesure de fiabilité générale du croisement, seulement le résultat exact sur les seuls cas mesurables aujourd'hui.

## 4. Ce que porte réellement le sniffer (rappel, détail dans RAPPORT-EXTRACTION-TIERS.md)

- `docstring_exemple_fictif` : 2 ligne(s)
- `fixture_test_synthetique` : 4 ligne(s)
- `readme_exemple` : 2 ligne(s)
- **0 fichier `.proto` embarqué, 0 `go:embed`** (mesuré : `grep -rn embed` + recherche de `*.proto`/`*.pb`/`*.bin` sur tout l'arbre → 0 partout). Le sniffer charge ses descripteurs et sa table de renommage **au runtime**, fournis par l'opérateur — ce n'est pas un défaut du dépôt, c'est sa conception (README §Usage : `i`/`s` pour pointer les .proto extraits ailleurs).
- Le SEUL exemple non purement synthétique (README, build cité `3.5.11.14`) donne `iri`→`MapMovementRequest`. Chez otomai (opcode probablement pour un autre build), `iri`→`ObjectAveragePricesRequest` — **désaccord**, cohérent avec §2 : l'opcode seul ne survit pas d'un build/outil à l'autre, même quand le NOM, lui, est correct des deux côtés (`MapMovementRequest`/`MapMovementEvent` existent bien chez otomai ET dans le dump).

## 5. Annexes — listes complètes

### 5.1 Les 27 désaccords opcode↔nom otomai vs JondoEmu (complet)

| opcode | nom otomai | nom JondoEmu (proposé) |
|---|---|---|
| `hif` | ForgettableSpellsEvent | OrnamentSelectedMessage |
| `hjc` | SpouseInformationEvent | TeleportRequestMessage |
| `hjj` | AccessoryPreviewRequest | TeleportDestinationsMessage |
| `hng` | PresetUseResponse | SpellVariantActivationSuccessMessage |
| `irq` | ExchangeSellRequest | JobExperienceMultiUpdateMessage |
| `itc` | DebugClearHighlightCellsEvent | StorageObjectRemoveMessage |
| `itd` | DumpedEntityStatsEvent | StorageObjectUpdateMessage |
| `itz` | ContextReadyRequest | ShortcutBarAddRequestMessage |
| `iua` | EntitiesDispositionEvent | ObjectAddedMessage |
| `iun` | UnBlockEvent | InventoryWeightMessage |
| `iuw` | FriendSetStatusShareRequest | ObjectDeleteMessage |
| `ivf` | FriendSetWarnOnLevelGainRequest | KamasUpdateMessage |
| `ivq` | FriendListEvent | ObjectMovementMessage |
| `ivx` | FriendSetWarnOnConnectionRequest | InventoryContentMessage |
| `iwn` | UnIgnoreEvent | InteractiveUsedMessage |
| `iwo` | BlockListEvent | InteractiveUseRequestMessage |
| `jba` | ChallengeReadyRequest | HavenBagEditionStoppedMessage |
| `jbl` | BreachRoomLockedEvent | HavenBagThemeChangeRequestMessage |
| `jbm` | BreachBonusEvent | HavenBagEditionStartedMessage |
| `jbn` | BreachRoomUnlockRequest | EnterHavenBagRequestMessage |
| `jbs` | BreachInvitationOfferEvent | LotteryResultMessage |
| `jbu` | BreachBranchesEvent | HavenBagFurnituresMessage |
| `jbv` | BreachCharactersEvent | HavenBagEditionStartRequestMessage |
| `jqi` | BakBufferListRequest | MapMovementConfirmRequest |
| `jru` | ReadyToLeaveArenaResponse | CurrentMapMessage |
| `jsd` | SurrenderVoteEndEvent | GameContextRemoveElementMessage |
| `jsj` | ArenaFightAnswerResponse | GameMapMovementMessage |

### 5.2 otomai ∩ dump — les 335 noms communs (complet)
AccountCapabilitiesEvent, AccountInformationUpdateEvent, Achievement, AchievementRewardRequest, AchievementRewardResultEvent, AchievementsPioneerRanksResponse, AcquaintanceInformation, ActorPositionInformation, AddContactFailureEvent, AddTagStorageResponse, AlignmentInformation, AllianceApplicationListEvent, AllianceApplicationListenRequest, AllianceApplicationPresenceEvent, AllianceApplicationResponseEvent, AllianceBulletinEvent, AllianceFactsRequest, AllianceInformation, AllianceMemberLeavingEvent, AllianceMemberStartWarningOnConnectionRequest, AllianceRankCreationRequest, AllianceRanksRequest, AllianceSummaryEvent, AllianceSummaryRequest, Alteration, AlterationAddedEvent, AnomalySubareaInformationEvent, ArenaFighterStatusEvent, ArenaLeagueRewardsEvent, ArenaRegistrationStatusEvent, ArenaUpdatePlayerInformationEvent, AutoFollowActivationResponse, AutoFollowDeactivationResponse, BakCancelBidRequest, BakConsumeBufferRequest, BakTransactionValidationEvent, BidActivity, BlockEvent, BlockListRequest, Challenge, ChallengeListEvent, ChallengeNumberEvent, ChallengeReadyRequest, ChallengeSelectedEvent, ChallengeTarget, ChangeAppearanceDialogLeave, ChangeAppearanceDialogStart, Character, CharacterAppearancesRequest, CharacterAppearancesResponse, CharacterCharacteristicUpgradeResultEvent, CharacterCharacteristicValue, CharacterDeletionErrorEvent, CharacterExperienceGainEvent, CharacterFillSlotColorsResponse, CharacterInformation, CharacterLifeStatusEvent, CharacterNameGenerationFailedEvent, CharacterOnConnectionEvent, CharacterPresetCreateResponse, CharacterPresetInfoResponse, CharacterPresetSetResponse, CharacterRemodelingInformation, CharacterSelectionEvent, CharacterStatus, CharacterUpdateColorsRequest, CharacterUpdatedGenderEvent, CharacteristicsInfo, ChatErrorEvent, ChatPrivateCopyMessageEvent, ClientChallengeProofRequest, ClientUIOpenedEvent, CompassUpdateEvent, ConsoleMessage, ContactInformation, ContactWarnOnPermanentDeathSetRequest, ContextCreationEvent, ContextQuitRequest, ContextRemoveElementEvent, CosmeticInventoryPopObjectsResponse, DateEvent, DebtsDeleteEvent, DebtsUpdateEvent, DebugHighlightCellsEvent, DebugInClientEvent, DecraftResultEvent, DetailedStatistics, DialogLeaveEvent, EmotePlayEvent, EntityLook, EntitySpawnInformation, ExchangeBidHouseBuyResultEvent, ExchangeBidHouseInListUpdatedEvent, ExchangeBidHouseListRequest, ExchangeBidHouseTypeRequest, ExchangeBidPriceEvent, ExchangeBidSellerStartedEvent, ExchangeBoughtEvent, ExchangeCraftResultEvent, ExchangeErrorEvent, ExchangeItemAutoCraftStoppedEvent, ExchangeLeaveEvent, ExchangeMoneyMovementLimitEvent, ExchangeObjectPutInBagEvent, ExchangeObjectRemovedEvent, ExchangeObjectTransferListWithQuantityToInventoryRequest, ExchangeObjectUseInWorkshopRequest, ExchangeObjectsSellRequest, ExchangeReadyEvent, ExchangeRequestedTradeEvent, ExchangeStartedWithPodsEvent, ExchangeTypesItemsExchangerDescriptionForUserEvent, ExchangeWeightEvent, FightAutoJoinActivationRequest, FightAutoJoinActivationResponse, FightAutoJoinDeactivatedResponse, FightAutoJoinDeactivationRequest, FightAutoReadyActivationRequest, FightAutoReadyActivationResponse, FightAutoReadyDeactivationResponse, FightChallengeJoinRefuseEvent, FightChoiceSelectionEvent, FightHumanReadyStateEvent, FightJoinRequest, FightMark, FightOptionUpdateEvent, FightPhaseInfo, FightPlacementSwapPositionsAcceptRequest, FightRemovableEffect, FightResultListEntry, FightResume, FightScenarioEvent, FightSpectatePlayerRequest, FightTeamLightInformation, FightTeamMemberCharacter, FightTeamMemberEntity, FightTurnReadyRequest, FightTurnStartPlayingEvent, FighterEntityLightInformation, FighterIdentity, ForgettableSpellActionRequest, ForgettableSpellDeletionEvent, ForgettableSpellPresetCreateResponse, ForgettableSpellPresetResetRequest, ForgettableSpellPresetResetResponse, ForgettableSpellPresetSetRequest, ForgettableSpellsEvent, FriendAddRequest, FriendInformation, FriendListEvent, FriendSetStatusShareRequest, GameActionFightCastRequest, GameActionFightEvent, GameActionItemConsumeRequest, GameActionItemListEvent, GameActionUpdateEffectTriggerCountEvent, GameRolePlayShowActorsEvent, GuestLimitationEvent, GuestModeEvent, GuildApplicationDeletedEvent, GuildApplicationListenRequest, GuildApplicationPlayerEvent, GuildApplicationUpdateRequest, GuildCardErrorEvent, GuildChestCurrentListenersEvent, GuildChestStructureStartListeningRequest, GuildCreationStartedEvent, GuildHousesEvent, GuildInformation, GuildInformationRequest, GuildInvitedEvent, GuildJoinAutomaticallyRequest, GuildLogbookEntry, GuildMemberUpdateEvent, GuildModificationResultEvent, GuildModificationValidRequest, GuildMotdEvent, GuildNoteUpdateRequest, GuildRankRemoveRequest, GuildRanksRequest, GuildRecruitmentEvent, GuildRecruitmentInvalidateEvent, GuildSummaryEvent, GuildSummaryRequest, HavenBagDailyLotteryEvent, HavenBagFurnitureOpenRequest, HavenBagRoomUpdateEvent, House, HouseGuildRightsViewRequest, HouseSellingUpdateEvent, HousesToSellEvent, IgnoreEvent, IgnoreRequest, InteractiveElement, InteractiveElementUpdatedEvent, InteractiveUseEndedEvent, InventoryContentEvent, ItemMinimalInformation, JobBookSubscriptionEvent, JobCrafterDirectoryJobInformation, JobCrafterDirectoryRemoveEvent, JobCrafterDirectorySettingsEvent, JobDescription, JobLevelUpEvent, JobMultiCraftStateEvent, KOTHUpdateEvent, LockableCodeResultEvent, LockableShowCodeDialogEvent, MapComplementaryHavenBagInformation, MapCurrentEvent, MapCurrentInstanceEvent, MapErrorNotFoundRequest, MapExtendedCoordinates, MapMovementConfirmRequest, MapMovementConfirmResponse, MapMovementEvent, MapObstacle, MapRunningFightStopListeningRequest, MonsterAngryAtPlayerEvent, MoodUpdateEvent, NpcDialogCreationEvent, NpcDialogQuestionEvent, NpcDialogReplyRequest, NpcGenericActionFailureEvent, NpcsMapQuestStatusUpdateEvent, NuggetsBeneficiary, ObjectAveragePricesEvent, ObjectEffect, ObjectFavoriteRequest, ObjectGidWithQuantity, ObjectInRolePlay, ObjectModifiedEvent, ObjectUidWithQuantity, ObjectUseRequest, ObjectsQuantityEvent, OrnamentLostEvent, Outfit, OutfitEquipAuraRequest, OutfitEquipFaceResponse, OutfitEquipObjectResponse, OutfitEquipRequest, OutfitEquipResponse, OutfitRemoveRequest, OutfitUpdateResponse, PartyAbdicateThroneRequest, PartyDeletedEvent, PartyEntity, PartyInvitationDetailsRequest, PartyInvitationRefuseRequest, PartyJoinErrorEvent, PartyJoinEvent, PartyNameSetErrorEvent, PartyNewMemberEvent, PartyPledgeLoyaltyRequest, PlayerSearch, PlayersMapAttackableStatusUpdateEvent, PongEvent, PopupWarningCloseRequest, PresetEquipmentUpdateRequest, PresetEquipmentUpdateResponse, PresetLook, PresetOrigin, PresetRenameRequest, PresetRenameResponse, PresetSetFavoriteResponse, PresetSpellUpdateRequest, PresetStatUpdateResponse, PresetSymbolUpdateResponse, PresetUseResponse, PrismAttackResultEvent, PrismCristal, PrismInformation, PrismTeleportationRequest, PurchasableDialogEvent, QuestActive, QuestStepInformationRequest, QuestStepValidatedEvent, QuestsEvent, RankInformation, RecycleResultEvent, RefreshMonsterBoostsEvent, RemoveSpellModifierEvent, RemoveTagObjectResponse, ReportRequest, ReportResponse, Ride, ServerSessionReadyEvent, SetMoodEvent, SetMoodRequest, ShortcutBarAddRequest, ShortcutBarReplacedEvent, ShortcutSpell, ShowCellRequest, ShowChallengeEvent, SocialApplicationInformation, SocialFightInformation, SpellItem, SpellVariantActivationEvent, SpouseInformationEvent, StorageKamasUpdateEvent, StorageObjectsRemovedEvent, SubEntityInformation, SubscriptionLimitationEvent, SubscriptionZoneEvent, SurrenderInfoResponse, SurrenderVoteCastRequest, TagStoragesRefreshEvent, TaxCollectorAttackResultEvent, TaxCollectorComplementaryInformation, TaxCollectorEquipmentUpdateEvent, TaxCollectorErrorEvent, TaxCollectorHarvestedEvent, TaxCollectorMovement, TaxCollectorPresetSpellAddRequest, TaxCollectorPresetSpellMoveRequest, TaxCollectorPresetSpellUpdatedEvent, TaxCollectorPresetsUpdatesListenStopRequest, TaxCollectorTopListEvent, TaxCollectorUpdatesListeningConfirmationEvent, TeleportBuddiesAnswerRequest, TeleportDestination, TeleportDestinationsEvent, TextInformationEvent, TimelineRefreshEvent, TreasureHuntAnswerEvent, TreasureHuntDigAnswerEvent, TreasureHuntEvent, TreasureHuntFinishedEvent, TreasureHuntFlagAnswerEvent, TreasureHuntLegendaryRequest, UnBlockEvent, UnIgnoreEvent, UnIgnoreRequest, WarnOnPermanentDeathStateEvent, WhoIsNumericEvent

