# CROISEMENT-OPCODES.md — jointure par nom, deterministe 0-LLM

> Jointure par NOM (les protocolId sont renumerotes entre versions -- 868/872 classes renumerotees 2.42->2.73 mesure par ProtoDiff273, cf. ARCHI-REFERENCE-JIVA.md §F.1). Le nom est une arete DEDUITE (deux classes de meme nom dans deux depots distincts sont supposees designer le meme message protocolaire -- pas verifie champ par champ ici, c'est le travail de lecture qui reste, cf. RAPPORT-INDEX.md).

## Lignee 2.x — 5 emus croises : jiva, giny, ginycore, oneair, symbioz

- Noms de message distincts (union) : **1807**
- INVARIANT : **1073**
- PARTIEL : **573**
- DIVERGENT : **161**

### Top 20 INVARIANTS (presents dans les 5 emus 2.x, tries par couverture handler)

- `AdminQuietCommandMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `AuthenticationTicketMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `BasicPingMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ChangeMapMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `CharacterCreationRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `CharacterDeletionRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `CharacterNameSuggestionRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `CharacterSelectionMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `CharactersListRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ChatClientMultiMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ChatClientMultiWithObjectMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ChatClientPrivateMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ChatSmileyRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `EmotePlayRequestMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeAcceptMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeBidHouseBuyMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeBidHouseListMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeBidHouseSearchMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeBidHouseTypeMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz
- `ExchangeBuyMessage` — handler cote : jiva;giny;ginycore;oneair;symbioz

### Top 20 DIVERGENTS (presents dans 1 seul emu, avec handler en premier)

- `BanRequestMessage` — seul symbioz (avec handler)
- `ClearIdentificationMessage` — seul jiva (avec handler)
- `ExchangeHandleMountsStableMessage` — seul symbioz (avec handler)
- `GuildInvitationByNameMessage` — seul symbioz (avec handler)
- `InventoryPresetItemUpdateRequestMessage` — seul symbioz (avec handler)
- `InventoryPresetSaveCustomMessage` — seul symbioz (avec handler)
- `InventoryPresetSaveMessage` — seul symbioz (avec handler)
- `OnCharacterCreationMessage` — seul symbioz (avec handler)
- `OnCharacterDeletionMessage` — seul symbioz (avec handler)
- `ResetDatabaseMessage` — seul symbioz (avec handler)
- `SetServerStatusMessage` — seul symbioz (avec handler)
- `SpellModifyRequestMessage` — seul symbioz (avec handler)
- `SurrenderInfoRequestMessage` — seul jiva (avec handler)
- `WorldRegistrationRequestMessage` — seul symbioz (avec handler)
- `AbstractCharacterToRefurbishInformation` — seul symbioz
- `AchievementPioneerRank` — seul jiva
- `AchievementRewardable` — seul symbioz
- `AchievementsPioneerRanksMessage` — seul jiva
- `AchievementsPioneerRanksRequestMessage` — seul jiva
- `AggregateStatMessage` — seul symbioz

## JondoEmu 3.0 — lien DEDUIT par similarite de nom semantique

- Candidats Jondo avec nom propose : **87** liens trouves (seuil difflib >= 0.55, stdlib, deterministe).

- `kra` (AuthenticationTicketAcceptedMessage) ~ `AuthenticationTicketAcceptedMessage` — score 1.00 — **DEDUIT**
- `kqz` (AuthenticationTicketMessage) ~ `AuthenticationTicketMessage` — score 1.00 — **DEDUIT**
- `kqo` (BasicPingMessage) ~ `BasicPingMessage` — score 1.00 — **DEDUIT**
- `kqy` (BasicPongMessage) ~ `BasicPongMessage` — score 1.00 — **DEDUIT**
- `lqu` (BasicTimeMessage) ~ `BasicTimeMessage` — score 1.00 — **DEDUIT**
- `jqk` (ChangeMapMessage) ~ `ChangeMapMessage` — score 1.00 — **DEDUIT**
- `kvz` (CharacterCreationRequestMessage) ~ `CharacterCreationRequestMessage` — score 1.00 — **DEDUIT**
- `kvb` (CharacterCreationResultMessage) ~ `CharacterCreationResultMessage` — score 1.00 — **DEDUIT**
- `kvl` (CharacterFirstSelectionMessage) ~ `CharacterFirstSelectionMessage` — score 1.00 — **DEDUIT**
- `kvk` (CharacterNameSuggestionSuccessMessage) ~ `CharacterNameSuggestionSuccessMessage` — score 1.00 — **DEDUIT**
- `kva` (CharacterSelectedSuccessMessage) ~ `CharacterSelectedSuccessMessage` — score 1.00 — **DEDUIT**
- `kvw` (CharacterSelectionMessage) ~ `CharacterSelectionMessage` — score 1.00 — **DEDUIT**
- `kub` (CharacterStatsListMessage) ~ `CharacterStatsListMessage` — score 1.00 — **DEDUIT**
- `kvi` (CharactersListMessage) ~ `CharactersListRequestMessage` — score 1.00 — **DEDUIT**
- `kpa` (CharactersListRequestMessage) ~ `CharactersListRequestMessage` — score 1.00 — **DEDUIT**
- `ktm` (ChatClientMultiMessage) ~ `ChatClientMultiMessage` — score 1.00 — **DEDUIT**
- `kti` (ChatServerMessage) ~ `ChatServerMessage` — score 1.00 — **DEDUIT**
- `jru` (CurrentMapMessage) ~ `CurrentMapMessage` — score 1.00 — **DEDUIT**
- `jbn` (EnterHavenBagRequestMessage) ~ `EnterHavenBagRequestMessage` — score 1.00 — **DEDUIT**
- `khd` (ExchangeLeaveMessage) ~ `ExchangeLeaveMessage` — score 1.00 — **DEDUIT**

## Handlers presents/absents par emu (sur les messages INVARIANTS)

- jiva : 184/1073 messages invariants ont un handler cote jiva
- giny : 114/1073 messages invariants ont un handler cote giny
- ginycore : 107/1073 messages invariants ont un handler cote ginycore
- oneair : 140/1073 messages invariants ont un handler cote oneair
- symbioz : 111/1073 messages invariants ont un handler cote symbioz
