; =========================================================
; File: checkpoint_state.asm
; Purpose: Central last-activated checkpoint codec and activation API.
; Inert source: no include/hook/org until a code range and registry are bound.
; @source: Core/sram.asm; root CURRENT_RESOURCE_GRANTS 2026-10-28
; @verified: source/host only; assembly and CPU execution pending
; =========================================================
; All public entries require M16/X16, native mode. DBR/DP unchanged.
; No volatile scratch and no writes outside the granted B4..B8 state.
; Caller supplies source-validated registry tables in this code bank. Domains,
; maps and explicit region membership are table data, not physical-map masks.
assert !CHECKPOINT_STATE_CODE_BOUND == 1
assert pc() == !CHECKPOINT_STATE_CODE_BASE
assert !CHECKPOINT_STATE_SCHEMA == $01
assert !CHECKPOINT_REGISTRY_EPOCH > 0 && !CHECKPOINT_REGISTRY_EPOCH < $FF
assert !CHECKPOINT_REGISTRY_COUNT >= 0 && !CHECKPOINT_REGISTRY_COUNT <= $0100
assert RegionalCheckpointEpoch == RegionalCheckpointSchema+1
assert RegionalCheckpointKey == RegionalCheckpointSchema+2

; A=key. Preserve full A/X/Y/P except C; C=set only for a registered key.
Checkpoint_FindKey:
{
  PHP : PHX
  CMP.w #$0000 : BEQ .missing
if !CHECKPOINT_REGISTRY_COUNT > 0
  LDX.w #$0000
  .next
    CMP.l CheckpointRegistry_Keys,X : BEQ .found
    INX #2
    CPX.w #!CHECKPOINT_REGISTRY_COUNT*2 : BCC .next
endif
  .missing
  PLX : PLP : CLC : RTL
if !CHECKPOINT_REGISTRY_COUNT > 0
  .found
  PLX : PLP : SEC : RTL
endif
}

; Validate/migrate the last key only. No current-region or resume inference.
; Preserve A/X/Y/P except C. C=set if old/invalid state was initialized empty.
Checkpoint_StateMigrate:
{
  PHP : PHA
  LDA.l RegionalCheckpointSchema : AND.w #$00FF
  CMP.w #!CHECKPOINT_STATE_SCHEMA : BNE .initialize
  LDA.l RegionalCheckpointEpoch : AND.w #$00FF
  CMP.w #!CHECKPOINT_REGISTRY_EPOCH : BNE .initialize
  LDA.l RegionalCheckpointKey : BEQ .current
  JSL Checkpoint_FindKey : BCS .current
  .initialize
    LDA.w #$0000 : STA.l RegionalCheckpointKey
    SEP #$20
    LDA.b #!CHECKPOINT_REGISTRY_EPOCH : STA.l RegionalCheckpointEpoch
    LDA.b #!CHECKPOINT_STATE_SCHEMA : STA.l RegionalCheckpointSchema
    REP #$20
    PLA : PLP : SEC : RTL
  .current
  PLA : PLP : CLC : RTL
}

; Explicit activation: A=key, X=logical domain, Y=current physical map.
; Caller pushes current region:u16 BEFORE JSL and removes it after return.
; At entry it is04,S; after the seven saved bytes below it is0B,S.
; Check key/domain/region/map here. Preserve A/X/Y/P except C success.
; It does NOT write resume intent; that separate field is not granted.
Checkpoint_ActivateKey:
{
  PHP : PHA : PHX : PHY
if !CHECKPOINT_REGISTRY_COUNT > 0
  LDX.w #$0000
  .next
    LDA $05,S : CMP.l CheckpointRegistry_Keys,X : BEQ .matched
    INX #2
    CPX.w #!CHECKPOINT_REGISTRY_COUNT*2 : BCC .next
endif
  .refuse
  PLY : PLX : PLA : PLP : CLC : RTL
if !CHECKPOINT_REGISTRY_COUNT > 0
  .matched
    LDA $03,S : CMP.l CheckpointRegistry_Domains,X : BNE .refuse
    LDA $01,S : CMP.l CheckpointRegistry_Maps,X : BNE .refuse
    LDA $0B,S : CMP.l CheckpointRegistry_Regions,X : BNE .refuse
    LDA $05,S : STA.l RegionalCheckpointKey
    SEP #$20
    LDA.b #!CHECKPOINT_REGISTRY_EPOCH : STA.l RegionalCheckpointEpoch
    LDA.b #!CHECKPOINT_STATE_SCHEMA : STA.l RegionalCheckpointSchema
    REP #$20
    PLY : PLX : PLA : PLP : SEC : RTL
endif
}

; Read-only codec: A=last valid key/C=set; A=0/C=clear for none or stale state.
; Preserve X/Y/DBR/DP and P except A-result N/Z and C. Never clear a retained key
; just because the current region chooses Home or a script/dungeon takes priority.
Checkpoint_ReadLastKey:
{
  LDA.l RegionalCheckpointSchema : AND.w #$00FF
  CMP.w #!CHECKPOINT_STATE_SCHEMA : BNE .missing
  LDA.l RegionalCheckpointEpoch : AND.w #$00FF
  CMP.w #!CHECKPOINT_REGISTRY_EPOCH : BNE .missing
  LDA.l RegionalCheckpointKey
  JSL Checkpoint_FindKey : BCC .missing
  ORA.w #$0000 : SEC : RTL
  .missing
  LDA.w #$0000 : CLC : RTL
}

Checkpoint_StateCodeEnd:
assert pc() <= !CHECKPOINT_STATE_CODE_LIMIT
