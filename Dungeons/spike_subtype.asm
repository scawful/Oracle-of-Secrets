;#PATCH_NAME=Spike Subtype
;#PATCH_AUTHOR=Zarby89
;#PATCH_VERSION=1.0
;#PATCH_DESCRIPTION
;Allow the spikes to go in multiple direction at different speed
;Default Values : (00) = normal, (08) = normal vertical
;01,02,03,04,05,06 = Horizontal with speed incrementing
;09,0A,0B,0C,0D,0E = Vertical with speed incrementing
;you can edit the ASM to make diagonal spikes too
;#ENDPATCH_DESCRIPTION

org $0691D7 ; SpritePrep_SpikeBlock:
JSL NewSpikePrep
RTS

org $1EBD0E
JSL NewSpikeCollision
RTS

pullpc
speedValuesH:
db $20, $10, $18, $28, $30, $38, $40, $FF
db $00, $00, $00, $00, $00, $00, $00, $FF

speedValuesV:
db $00, $00, $00, $00, $00, $00, $00, $FF
db $20, $18, $20, $28, $30, $38, $40, $FF

NewSpikePrep:
{
  PHB : PHK : PLB
  LDA $0E30, X : TAY
  LDA.w speedValuesH, Y : STA.w SprXSpeed, X
  LDA.w speedValuesV, Y : STA.w SprYSpeed, X
  PLB
  RTL
}

NewSpikeCollision:
{
  LDA.b #$04 : STA.w SprTimerA, X
  LDA.w SprXSpeed, X : EOR.b #$FF : INC A : STA.w SprXSpeed, X
  LDA.w SprYSpeed, X : EOR.b #$FF : INC A : STA.w SprYSpeed, X
  LDA.b #$05 : JSL $0DBB7C ; Sound_SetSfx2PanLong
  RTL
}

print  "End of spike_subtype.asm          ", pc
pushpc
