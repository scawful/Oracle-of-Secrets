; =========================================================
; File: checkpoint_state.asm
; Purpose: Central last-activated checkpoint codec and activation API.
; Private source-bound runtime; disabled at Oracle_main until joint admission.
; @source: Core/sram.asm; root CURRENT_RESOURCE_GRANTS 2026-10-28
; @verified: Native Home/Goron death, Continue, Save & Quit and cold reopen
; on 9d8dd38a; Lyra records/entry require separate saved-source qualification.
; =========================================================
; All public entries require M16/X16, native mode. DBR/DP unchanged.
; State APIs write only grantedB4..B9. Load adapters also use the existing
; native cache/context ABI; no new volatile scratch allocation.
; Caller supplies source-validated registry tables in this code bank. Domains,
; maps and explicit region membership are table data, not physical-map masks.
assert !REGIONAL_CHECKPOINTS_BOUND == 1
Checkpoint_StateCodeBegin = $34F900
Checkpoint_StateCodeLimit = $34FE00
assert pc() == Checkpoint_StateCodeBegin
!CHECKPOINT_STATE_SCHEMA = $01
!CHECKPOINT_REGISTRY_EPOCH = $01
!CHECKPOINT_REGISTRY_COUNT = 1 ; Existing native Goron source control only.
!CHECKPOINT_REGION_MEMBER_COUNT = 4 ; Explicit qualified native36/37/3E/3F.
assert RegionalCheckpointEpoch == RegionalCheckpointSchema+1
assert RegionalCheckpointKey == RegionalCheckpointSchema+2
assert RegionalCheckpointResumeIntent == RegionalCheckpointSchema+4

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
    LDA.b #$00 : STA.l RegionalCheckpointResumeIntent
    REP #$20
    PLA : PLP : SEC : RTL
  .current
  LDA.l RegionalCheckpointResumeIntent : AND.w #$00FF
  CMP.w #$0002 : BCC .intent_valid
    SEP #$20
    LDA.b #$00 : STA.l RegionalCheckpointResumeIntent
    REP #$20
    PLA : PLP : SEC : RTL
  .intent_valid
  PLA : PLP : CLC : RTL
}

; Explicit activation: A=key, X=logical domain, Y=current physical map.
; Caller pushes current region:u16 BEFORE JSL and removes it after return.
; At entry it is04,S; after the seven saved bytes below it is0B,S.
; Check key/domain/region/map here. Preserve A/X/Y/P except C success.
; Successful activation sets the separately granted intent to Regional.
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
    LDA.b #$01 : STA.l RegionalCheckpointResumeIntent
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

; Internal M16/X16 lookup. Returns X=word table index/C=set; clobbers X.
Checkpoint_FindKeyIndex:
  CMP.w #$0000 : BEQ .missing
  LDX.w #$0000
  .next
    CMP.l CheckpointRegistry_Keys,X : BEQ .found
    INX #2
    CPX.w #!CHECKPOINT_REGISTRY_COUNT*2 : BCC .next
  .missing
  CLC : RTS
  .found
  SEC : RTS

; Live context only: explicit source-bound map/domain/affinity rows. Native
; affinity is independent of logical domain; cold resolution never calls this.
Checkpoint_FindCurrentRegion:
  LDA.b $8A : AND.w #$00FF
  LDX.w #$0000
  .next
    CMP.l CheckpointRegions_Maps,X : BEQ .map_found
    INX #2
    CPX.w #!CHECKPOINT_REGION_MEMBER_COUNT*2 : BCC .next
  CLC : RTS
  .map_found
  LDA.l CheckpointRegions_Affinities,X : PHA
  LDA.l SavedWorld : AND.w #$00FF : CMP $01,S : BNE .wrong_world
  PLA : SEC : RTS
  .wrong_world
  PLA : CLC : RTS

; Word-table index X=2*i -> packed record offset X=60*i. Caller CLD.
Checkpoint_RecordOffset:
  TXA : ASL : PHA : ASL #4 : SEC : SBC $01,S : TAX : PLA : RTS

; M8/X8 public entry; preserve full A/X/Y/P/DBR/DP. Shared09F540 executes
; after Module17 JMP09F50F and before both09F5DE/09F60A SaveGameFile calls.
; Indoors retain the last qualified outdoor frame intent, not stale8A.
Checkpoint_PrepareResume:
{
  PHP : REP #$30 : PHA : PHX : PHY : CLD
  LDA.b $1B : AND.w #$00FF : BNE .done
  LDA.l GameState : AND.w #$00FF : CMP.w #$0002 : BCC .done
  JSL Checkpoint_StateMigrate
  JSR Checkpoint_FindCurrentRegion : BCC .home
  LDA.l CheckpointRegions_Regions,X : PHA
  LDA.l CheckpointRegions_Domains,X : PHA
  LDA.l RegionalCheckpointKey
  JSR Checkpoint_FindKeyIndex : BCC .pop_home
  LDA.l CheckpointRegistry_Regions,X : CMP $03,S : BNE .pop_home
  LDA.l CheckpointRegistry_Domains,X : CMP $01,S : BNE .pop_home
  PLA : PLA
  LDA.w #$0001 : BRA .store
  .pop_home
  PLA : PLA
  .home
  LDA.w #$0000
  .store
  SEP #$20
  STA.l RegionalCheckpointResumeIntent
  REP #$20
  .done
  PLY : PLX : PLA : PLP : RTL
}

Checkpoint_PrepareAndReset:
  JSL Checkpoint_PrepareResume
  JML $0BFFBF ; Original ResetSomeThingsAfterDeath, original A intact.

Checkpoint_FrameAndLink:
  JSL Checkpoint_OnFrame
  JML $078000 ; Original Link_Main, exact caller ABI restored.

; Actual normal-OW hook, not test injection. The activation point is the exact
; existing source control's player coordinate, not a newly invented radius.
Checkpoint_OnFrame:
{
  JSL Checkpoint_PrepareResume
  PHP : REP #$30 : PHA : PHX : PHY : CLD
  LDA.b $1B : AND.w #$00FF : BNE .done
  LDA.l GameState : AND.w #$00FF : CMP.w #$0002 : BCC .done
  LDA.w $04C6 : AND.w #$00FF : BNE .done ; $04C7 is independent dungeon-tag state.
  JSR Checkpoint_FindCurrentRegion : BCC .done
  LDA.l CheckpointRegions_Regions,X : PHA
  LDA.l CheckpointRegions_Domains,X : PHA
  LDX.w #$0000
  .next_anchor
    LDA.b $8A : AND.w #$00FF
    CMP.l CheckpointRegistry_Maps,X : BNE .advance
    TXA : TAY
    JSR Checkpoint_RecordOffset
    LDA.l CheckpointRegistry_Records+18,X : CMP.b $20 : BNE .restore_index
    LDA.l CheckpointRegistry_Records+20,X : CMP.b $22 : BNE .restore_index
    LDA.l CheckpointRegistry_Records+2,X : AND.w #$00FF : CMP $01,S : BNE .restore_index
    LDA.l CheckpointRegistry_Records+4,X : CMP $03,S : BNE .restore_index
    PLA ; Qualified current domain; record domain was compared above.
    LDA.l CheckpointRegistry_Records+6,X : TAY
    LDA.l CheckpointRegistry_Records+2,X : AND.w #$00FF : PHA
    LDA.l CheckpointRegistry_Records,X
    PLX
    JSL Checkpoint_ActivateKey
    PLA ; Caller-owned current region argument.
    BRA .done
  .restore_index
  TYX
  .advance
  INX #2
  CPX.w #!CHECKPOINT_REGISTRY_COUNT*2 : BCC .next_anchor
  PLA : PLA
  .done
  PLY : PLX : PLA : PLP : RTL
}

; Actual cold-copy boundary. Do not infer cold/continue from stale1B or8A.
; Replays BOTH replaced stores, then explicitly clears the native warm marker.
Checkpoint_ColdContext:
  STZ.w $010E : STZ.w $0710 : STZ.w $010A : RTL

; M16/X16 pure decision. A=0 legacy/1 Home/2 regional; X=regional row only.
; Script adapters preserve their existing native source instead of replacing it.
Checkpoint_ResolveLoad:
{
  PHP : PHX : PHY : CLD
  LDA.l GameState : AND.w #$00FF : CMP.w #$0002 : BCC .legacy
  LDA.w $010A : AND.w #$00FF : BEQ .cold
  LDA.b $1B : AND.w #$00FF : BEQ .cold
  LDA.w $04AA : AND.w #$00FF : BEQ .legacy ; Normal dungeon entrance.
  .cold
  LDA.l SpawnPoint : AND.w #$00FF
  CMP.w #$0007 : BEQ .legacy ; Existing one-shot Goron factory.
  CMP.w #$0005 : BEQ .legacy ; Existing old-man routing.
  CMP.w #$0008 : BCS .home ; Never send an invalid native selector to arrays.
  LDA.l FollowerId : AND.w #$00FF : BNE .legacy
  LDA.l SavedWorld : AND.w #$0040 : BNE .legacy ; Existing Abyss/DW policy.
if !ENABLE_D3_PRISON_SEQUENCE == 1
  LDA.l CastleAmbushFlags : AND.w #$0003 : CMP.w #$0001 : BEQ .legacy
endif
  JSL Checkpoint_StateMigrate
  LDA.l RegionalCheckpointResumeIntent : AND.w #$00FF : CMP.w #$0001 : BNE .home
  LDA.l RegionalCheckpointKey
  JSR Checkpoint_FindKeyIndex : BCC .home
  PLY : PLA : PLP ; Discard saved X, retain selected table index.
  LDA.w #$0002 : RTL
  .home
  PLY : PLX : PLP
  LDA.w #$0001 : RTL
  .legacy
  PLY : PLX : PLP
  LDA.w #$0000 : RTL
}

; Called by the existing Module05 owner after palette restoration/event migration.
; Return C=clear for the exact existing native adapters, C=set after a full load.
Checkpoint_Load:
{
  PHP : REP #$30 : PHA : PHX : PHY : CLD
  JSL Checkpoint_ResolveLoad
  CMP.w #$0000 : BNE .selected
    JMP .legacy
  .selected
  CMP.w #$0001 : BEQ .home
  PHX : SEP #$30
  JSL $0DE395 : JSL $0DFA6C : JSL $0DDD32
  REP #$30 : PLX
  JSR Checkpoint_RecordOffset
  LDA.l CheckpointRegistry_Records+3,X : SEP #$20 : STA.l SavedWorld : REP #$20
  TXA : CLC : ADC.w #$003A : TAX ; 10-byte header + final cache word48.
  LDY.w #$0030
  PHB : SEP #$20 : LDA.b #$7E : PHA : PLB : REP #$20
  .copy
    LDA.l CheckpointRegistry_Records,X : STA.w $C140,Y
    DEX #2 : DEY #2 : BPL .copy
  PLB
  STZ.w $0696 : STZ.w $0698
  LDA.w #$0151 : STA.b $A0 ; Existing native cached-exit room.
  PLY : PLX : PLA : PLP
  SEC : JML Checkpoint_EnterPreparedCache
  .home
  PLY : PLX : PLA : PLP
; Direct M8/X8 long entry for source-bound preaccess guards. No saved frame
; from Checkpoint_Load is required here; the caller supplies only its own JSL.
; Uses the same temporary C8/native Home path and returns C=set.
Checkpoint_EnterHome = pc()
  LDA.l SpawnPoint : PHA
  LDA.b #$00 : STA.l SpawnPoint : STA.l SavedWorld
  STZ.w $010A : STZ.w $010E
  LDA.b #$01 : STA.w $04AA
  JSL $028208 ; Real Home loader, bypass Module1B chooser.
  PLA : STA.l SpawnPoint ; Compatibility field is temporary, like native chooser.
  SEC : RTL
  .legacy
  PLY : PLX : PLA : PLP : CLC : RTL
}

; Existing native Goron source-qualified CONTROL, not a Lyra gameplay claim.
; Key1, LIGHT region1, map/parent36. No new coordinates or actor system.
CheckpointRegistry_Keys:    dw $0001
CheckpointRegistry_Domains: dw $0000
CheckpointRegistry_Maps:    dw $0036
CheckpointRegistry_Regions: dw $0001
; Explicit region membership, independent of checkpoint/activation rows.
CheckpointRegions_Maps:       dw $0036,$0037,$003E,$003F
CheckpointRegions_Domains:    dw $0000,$0000,$0000,$0000
CheckpointRegions_Affinities: dw $0000,$0000,$0000,$0000
CheckpointRegions_Regions:    dw $0001,$0001,$0001,$0001
CheckpointRegistry_Records:
  dw $0001 : db $00,$00 : dw $0001,$0036,$0036
  %RegionalCheckpoint_GoronControlCache()
assert pc()-CheckpointRegistry_Records == 60
Checkpoint_StateCodeEnd:
assert pc() <= Checkpoint_StateCodeLimit, "Checkpoint aggregate code/tables/records/adapters exceed reservation"

pushpc
org $09F540 ; @hook module=Overworld name=Checkpoint_PrepareAndReset kind=jsl target=Checkpoint_PrepareAndReset expected_m=8 expected_x=8
  assert read4($09F540) == $0BFFBF22
  JSL Checkpoint_PrepareAndReset
assert pc() == $09F544
org $02A5A2 ; @hook module=Overworld name=Checkpoint_FrameAndLink kind=jsl target=Checkpoint_FrameAndLink expected_m=8 expected_x=8
  assert read4($02A5A2) == $07800022
  JSL Checkpoint_FrameAndLink
assert pc() == $02A5A6
org $0CD049 ; @hook module=Overworld name=Checkpoint_ColdContext kind=jsl target=Checkpoint_ColdContext expected_m=8 expected_x=8
  assert read3($0CD049) == $010E9C && read3($0CD04C) == $07109C
  JSL Checkpoint_ColdContext : NOP #2
assert pc() == $0CD04F
pullpc
