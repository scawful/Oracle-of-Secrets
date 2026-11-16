; Park-anywhere helpers. Included from Sprites/NPCs/horse.asm after HorseNpc_End
; so horse_form.asm stays under $53D000. Assembled only when park flag is on.
; Local mirrors of horse_form.asm constants (sprites assemble before masks).
!HorsePark_SpriteId    = $2D
!HorsePark_DefaultNpcX = $01C0
!HorsePark_DefaultNpcY = $0294

; Write Link outdoor XY + $8A into the park anchor. M=8,X=8,DBR=$00.
HorseForm_SaveOutdoorAnchor_Long:
{
  PHP
  REP #$20
  LDA.b $22 : STA.l Horse_AnchorX
  LDA.b $20 : STA.l Horse_AnchorY
  SEP #$20
  LDA.b $8A : STA.l Horse_AnchorArea
  LDA.b #$01 : STA.l Horse_HasAnchor
  PLP
  RTL
}

; Spawn parked Epona on Horse_AnchorArea, or Ranch-default when no park.
; Same call site as HorseForm_MaintainRanchNpc (unmounted FrameTick).
HorseForm_MaintainParkedNpc_Long:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB

  LDA.b $1B : BEQ + : BRL .leave_keep_or_clear : +
  LDA.b $10 : CMP.b #$09 : BEQ + : PLB : PLP : RTL : +
  LDA.b $11 : BEQ + : PLB : PLP : RTL : +
  LDA.w $0FFC : BEQ + : PLB : PLP : RTL : +

  LDA.l Horse_HasAnchor : BEQ .ranch_default
  LDA.b $8A : CMP.l Horse_AnchorArea : BEQ + : BRL .leave_keep_park : +
  ; On parked map: Ranch uses sheet/actor gates; off-Ranch uses SlotsBusy only.
  LDA.b $8A : BNE .off_ranch_gates
  JSL Horse_RanchProfileReady : BCS + : PLB : PLP : RTL : +
  JSL Horse_RanchActorsSafe : BCS + : PLB : PLP : RTL : +
  BRA .spawn_scan
  .off_ranch_gates
  JSL Horse_SlotsBusy : BCC + : PLB : PLP : RTL : +
  BRA .spawn_scan

  .ranch_default
  LDA.b $8A : BEQ + : BRL .leave_clear : +
  JSL Horse_RanchProfileReady : BCS + : PLB : PLP : RTL : +
  JSL Horse_RanchActorsSafe : BCS + : PLB : PLP : RTL : +

  .spawn_scan
  PHX : PHY
  %m8()
  LDX.b #$0F
  .scan
    LDA.w $0DD0, X : BEQ .next_slot
    LDA.w $0E20, X : CMP.b #!HorsePark_SpriteId : BEQ .found
  .next_slot
    DEX : BPL .scan

  LDX.b #$00
  LDA.b #!HorsePark_SpriteId : JSL Sprite_SpawnDynamically : BMI .spawn_failed
  LDA.l Horse_HasAnchor : BEQ .use_default_pos
    REP #$20
    LDA.l Horse_AnchorX : STA.b $00
    LDA.l Horse_AnchorY : STA.b $02
    SEP #$20
    BRA .set_coords
  .use_default_pos
    REP #$20
    LDA.w #!HorsePark_DefaultNpcX : STA.b $00
    LDA.w #!HorsePark_DefaultNpcY : STA.b $02
    SEP #$20
  .set_coords
  LDA.b $00 : STA.w SprX, Y
  LDA.b $01 : STA.w SprXH, Y
  LDA.b $02 : STA.w SprY, Y
  LDA.b $03 : STA.w SprYH, Y
  LDA.b #$00
  STA.w $0F20, Y : STA.w $0F70, Y : STA.w $0DE0, Y
  STA.w $0E30, Y : STA.w $0E80, Y
  STA.w SprAction, Y : STA.w SprFrame, Y
  LDA.b #$01 : STA.l Horse_NpcActive : STA.w SprBulletproof, Y
  LDA.b #14  : STA.l Horse_NpcFrame
  LDA.b #$FF : STA.l Horse_NpcUploadedFrame
  JSL Horse_LoadNpcPalette
  BRA .done_scan

  .found
  LDA.b #$01 : STA.l Horse_NpcActive
  BRA .done_scan

  .spawn_failed
  LDA.b #$00 : STA.l Horse_NpcActive

  .done_scan
  PLY : PLX
  PLB : PLP
  RTL

  ; Left parked map: despawn NPC, keep WRAM park for return.
  .leave_keep_park
  LDA.l Horse_NpcActive : BEQ +
    JSL Horse_RestoreSp3Palette
  +
  LDA.b #$00 : STA.l Horse_NpcActive
  PLB : PLP
  RTL

  ; Indoor or no-park leave: clear park when indoors / leaving Ranch default.
  .leave_keep_or_clear
  LDA.l Horse_HasAnchor : BNE .leave_keep_park
  .leave_clear
  LDA.l Horse_NpcActive : BEQ +
    JSL Horse_RestoreSp3Palette
  +
  LDA.b #$00 : STA.l Horse_HasAnchor : STA.l Horse_NpcActive : STA.l Horse_AnchorArea
  PLB : PLP
  RTL
}
