; =========================================================
; Abyss $56 Twin Brothers — Hookshot/Goldstar <-> Switch Hook
; Trade-Back & Swap-Diamond Trial
; =========================================================
; Hooks vanilla Sprite_32_ArguingBros ($05:E026) in Eon Abyss rooms
; $00F4 (West Brother) and $00F5 (East Brother). Every other room,
; world, or pre-Hookshot/Goldstar state runs exact vanilla logic.
;
; Progression bit:
;   SideQuestProgress ($7EF3D7) bit 6 (!SideQuest_SwapDiamond = $40).
;   (SideQuestProgress2 $7EF3D8 bit 7 is already used by
;    Masks/horse_minigame.asm !SideQuest2_RanchArchery = $80.)
;
; Volatile WRAM (4 bytes in vanilla-unused $7EC13A-$7EC13D, cleared by
; Intro_Clear1kbBlocksOfWRAM; $7EC132-$7EC138 belong to SpecialOverworld):
;   $7EC13A SwapTrial_Active (1B): 0=idle, 1=trial active
;   $7EC13B SwapTrial_Timer  (2B): countdown in frames (1800 = 30s)
;   $7EC13D SwapTrial_Step   (1B): 0=idle, 1=started (East), 2=cleared (West)
; =========================================================

; Named message constants (existing vanilla Arguing Bros IDs; replace
; with approved custom message IDs later without altering logic).
!SwapBrosMsg_WestEquip   = $0131
!SwapBrosMsg_TrialStart  = $012F
!SwapBrosMsg_TrialClear  = $0130
!SwapBrosMsg_EastEquip   = $0130

!SwapBros_WorldAbyss     = $40
!SwapBros_RoomWest       = $00F4
!SwapBros_RoomEast       = $00F5

!SwapTrial_Duration      = 1800  ; 30 seconds at 60 fps ($0708)
!SwapTrial_MaxMagic      = $80   ; Full magic bar ($7EF36E)

!SwapBros_SFX2_WestEquip = $05   ; SFX2.$05 metallic clink (Hookshot/Goldstar)
!SwapBros_SFX2_EastEquip = $21   ; SFX2.$21 swap/warp thud (Switch Hook)
!SwapBros_SFX2_Timeout   = $3C   ; SFX2.$3C error buzz (trial timeout)
!SwapBros_SFX3_Fanfare   = $1B   ; SFX3.$1B puzzle/secret chime (start & clear)

SwapTrial_Active         = $7EC13A
SwapTrial_Timer          = $7EC13B
SwapTrial_Step           = $7EC13D

pushpc
; Vanilla Sprite_32_ArguingBros.main ($05E026-$05E02B):
;   $05E026: A5 A0       LDA.b $A0
;   $05E028: 29 01       AND.b #$01
;   $05E02A: D0 0A       BNE .east_side ($05E036)
;   ...
;   $05E04D: 22 F3 F4 1E JSL Sprite_BehaveAsBarrier
;   $05E051: 60          RTS
assert read3($05E026) == $29A0A5, "Vanilla Sprite_32_ArguingBros hook site moved"
assert read3($05E029) == $0AD001, "Vanilla Sprite_32_ArguingBros branch moved"
assert read1($05E02C) == $A9, "Vanilla Sprite_32_ArguingBros west-side entry moved"
assert read4($05E04D) == $1EF4F322, "Vanilla Sprite_32_ArguingBros barrier tail moved"
assert read1($05E051) == $60, "Vanilla Sprite_32_ArguingBros RTS moved"
org $05E026 ; @hook module=Sprites name=HookSwapBrothers_Interact kind=jsl target=HookSwapBrothers_Interact expected_m=8 expected_x=8
  JSL HookSwapBrothers_Interact
  JMP.w $E04D
assert pc() == $05E02D, "HookSwapBrothers gateway must be exactly 7 bytes"
pullpc

; Entry: M=8, X=8, DBR=$05, X=sprite slot.
; Exit:  M=8, X=8, DBR=$05, X preserved. Returns to $05E02A -> JMP.w $E04D.
HookSwapBrothers_Interact:
{
  PHB : PHK : PLB

  ; 1. Strict gate: Indoors ($1B != 0), SavedWorld ($7EF3CA == $40),
  ;    Room ($A0 == $00F4 or $00F5).
  LDA.b $1B : BEQ .not_abyss_bros
  LDA.l SavedWorld : CMP.b #!SwapBros_WorldAbyss : BNE .not_abyss_bros

  REP #$20
  LDA.b $A0
  CMP.w #!SwapBros_RoomWest : BEQ .in_abyss_bros
  CMP.w #!SwapBros_RoomEast : BEQ .in_abyss_bros
  SEP #$20

  .not_abyss_bros
  ; Cancel any active trial cleanly if an ArguingBros tick runs outside
  ; Abyss $00F4/$00F5 (no timeout buzz; restore Hookshot so player isn't stuck).
  LDA.l SwapTrial_Active : BEQ .vanilla_fallback
    JSR HookSwapBrothers_CancelExit
  .vanilla_fallback
  JSR HookSwapBrothers_VanillaInteract
  JMP .done

  .in_abyss_bros
  SEP #$20

  ; 2. Require Hookshot ($7EF342 != 0) OR GoldstarOwned ($7EF3A9 != 0).
  ;    Without either item, run exact vanilla dialogue without mutating SRAM.
  LDA.l $7EF342 : ORA.l GoldstarOwned : BNE .owns_hook
    LDA.b #$00
    STA.l SwapTrial_Active
    STA.l SwapTrial_Step
    BRA .vanilla_fallback

  .owns_hook
  ; 3. Tick active Swap-Diamond Trial countdown.
  LDA.l SwapTrial_Active : BEQ .after_tick
    LDA.l SideQuestProgress : AND.b #!SideQuest_SwapDiamond : BEQ .tick_timer
      ; Already cleared: sweep any stale active flag without reverting gear.
      LDA.b #$00
      STA.l SwapTrial_Active
      STA.l SwapTrial_Timer
      STA.l SwapTrial_Timer+1
      BRA .after_tick

    .tick_timer
    REP #$20
    LDA.l SwapTrial_Timer
    BEQ .trial_timeout
    DEC A
    STA.l SwapTrial_Timer
    BEQ .trial_timeout
    SEP #$20
    BRA .after_tick

    .trial_timeout
    SEP #$20
    JSR HookSwapBrothers_TimeoutReset

  .after_tick
  ; 4. Dispatch West Brother ($00F4, even) vs East Brother ($00F5, odd).
  LDA.b $A0 : AND.b #$01 : BNE .east_brother

  ; --- West Brother ($00F4) ---
  LDA.l SwapTrial_Active : BEQ .west_equip
  LDA.l SideQuestProgress : AND.b #!SideQuest_SwapDiamond : BNE .west_equip

    ; Active Swap-Diamond Trial: talking to West Brother clears the trial!
    LDA.b #!SwapBrosMsg_TrialClear&$FF
    LDY.b #!SwapBrosMsg_TrialClear>>8
    JSL Sprite_ShowSolicitedMessage : BCC .west_done

    LDA.b #$00
    STA.l SwapTrial_Active
    STA.l SwapTrial_Timer
    STA.l SwapTrial_Timer+1
    LDA.b #$02 : STA.l SwapTrial_Step

    LDA.l SideQuestProgress : ORA.b #!SideQuest_SwapDiamond : STA.l SideQuestProgress
    LDA.b #!SwapTrial_MaxMagic : STA.l MagicPower
    LDA.b #$01 : STA.l GoldstarOwned
    LDA.b #$A5 : STA.l GoldstarInventoryVersion
    LDA.b #$02 : STA.l $7EF342 ; Leave Switch Hook equipped on clear
    LDA.b #!SwapBros_SFX3_Fanfare : STA.w $012F
    JSL HUD_RefreshLong
    BRA .west_done

  .west_equip
  ; Trial idle or already cleared: instant switch to Hookshot/Goldstar ($7EF342=1).
  LDA.b #!SwapBrosMsg_WestEquip&$FF
  LDY.b #!SwapBrosMsg_WestEquip>>8
  JSL Sprite_ShowSolicitedMessage : BCC .west_done

  LDA.b #$01
  STA.l $7EF342
  STA.l GoldstarOwned
  LDA.b #$A5 : STA.l GoldstarInventoryVersion
  LDA.b #!SwapBros_SFX2_WestEquip : STA.w $012E
  JSL HUD_RefreshLong

  .west_done
  JMP .done

  ; --- East Brother ($00F5) ---
  .east_brother
  LDA.l SideQuestProgress : AND.b #!SideQuest_SwapDiamond : BNE .east_equip

    ; Trial not yet cleared: start 30-second Swap-Diamond Trial on talk.
    LDA.b #!SwapBrosMsg_TrialStart&$FF
    LDY.b #!SwapBrosMsg_TrialStart>>8
    JSL Sprite_ShowSolicitedMessage : BCC .done

    LDA.l SwapTrial_Active : BNE .east_keep_trial

    LDA.b #$01
    STA.l SwapTrial_Active
    STA.l SwapTrial_Step
    REP #$20
    LDA.w #!SwapTrial_Duration : STA.l SwapTrial_Timer
    SEP #$20

    LDA.b #$02 : STA.l $7EF342
    LDA.b #$01 : STA.l GoldstarOwned
    LDA.b #$A5 : STA.l GoldstarInventoryVersion
    LDA.b #!SwapBros_SFX3_Fanfare : STA.w $012F
    JSL HUD_RefreshLong
    BRA .done

    .east_keep_trial
    ; Trial already running: keep Switch Hook active without resetting timer.
    LDA.b #$02 : STA.l $7EF342
    LDA.b #$01 : STA.l GoldstarOwned
    LDA.b #$A5 : STA.l GoldstarInventoryVersion
    BRA .done

  .east_equip
  ; Trial cleared: permanent instant toggle to Switch Hook ($7EF342=2).
  LDA.b #!SwapBrosMsg_EastEquip&$FF
  LDY.b #!SwapBrosMsg_EastEquip>>8
  JSL Sprite_ShowSolicitedMessage : BCC .done

  LDA.b #$02 : STA.l $7EF342
  LDA.b #$01 : STA.l GoldstarOwned
  LDA.b #$A5 : STA.l GoldstarInventoryVersion
  LDA.b #!SwapBros_SFX2_EastEquip : STA.w $012E
  JSL HUD_RefreshLong

  .done
  PLB
  RTL
}

; Timeout reset: clear trial state, buzz SFX2.$3C, restore Hookshot ($7EF342=1),
; preserve GoldstarOwned=1, refresh HUD. M=8, X=8, X preserved.
HookSwapBrothers_TimeoutReset:
{
  LDA.b #!SwapBros_SFX2_Timeout : STA.w $012E
  JMP HookSwapBrothers_CancelExit
}

; Room/world exit cancel: same restore without timeout error buzz.
HookSwapBrothers_CancelExit:
{
  LDA.b #$00
  STA.l SwapTrial_Active
  STA.l SwapTrial_Timer
  STA.l SwapTrial_Timer+1
  STA.l SwapTrial_Step
  LDA.b #$01
  STA.l $7EF342
  STA.l GoldstarOwned
  LDA.b #$A5 : STA.l GoldstarInventoryVersion
  JSL HUD_RefreshLong
  RTS
}

; Exact vanilla Sprite_32_ArguingBros interaction ($05E026-$05E04C).
HookSwapBrothers_VanillaInteract:
{
  LDA.b $A0 : AND.b #$01 : BNE .east_side
    LDA.b #$31 : LDY.b #$01 ; MESSAGE 0131
    JSL Sprite_ShowSolicitedMessage
    RTS
  .east_side
  LDA.w $0401 : BNE .door_opened
    LDA.b #$2F : LDY.b #$01 ; MESSAGE 012F
    JSL Sprite_ShowSolicitedMessage
    RTS
  .door_opened
  LDA.b #$30 : LDY.b #$01 ; MESSAGE 0130
  JSL Sprite_ShowSolicitedMessage
  RTS
}
