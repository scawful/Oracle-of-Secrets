; M/X=8, DBR=$30, PBR=$32, X=sprite slot. Keeps X/Y and processor widths.
; The last tile in every Darknut frame is its sword. Read its relative
; offsets from the exact tables used by Draw; do not inherit the shared
; cache from a previous sprite. $0FAB=$80 is vanilla's invalid sentinel.
Sprite_Darknut_WeaponHitbox:
{
  PHX : PHY
  LDA.w SprGfx, X : CLC : ADC.w $0D90, X : TAY
  LDA.w DarknutDrawStartIndex, Y
  CLC : ADC.w DarknutDrawTileCounts, Y
  ASL A : TAY
  LDA.w DarknutDrawXOffsets, Y : STA.w $0FAB
  LDA.w DarknutDrawYOffsets, Y : STA.w $0FAA
  PLY : PLX
  RTL
}
