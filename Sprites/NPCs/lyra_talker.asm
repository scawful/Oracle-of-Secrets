; =========================================================
; Lyra talkers (!ENABLE_LYRA_TALKERS, default off)
;
; Talk-only NPCs on the Lyra crescent island (parent area $B3: screens
; $B3/$B4/$BB/$BC) and the fishing village (parent $A0: screens $A0/$A1). They are vanilla ShopMan ($BB) sprites placed in the
; overworld day list (phase 1). Lyra day sprite set $1B loads sheet $4B, so
; the ShopMan body draws without a sheet swap (scawful picked "ShopMan look",
; 2026-11-15).
;
; Overworld sprites have no subtype byte, so SpritePrep_Shopkeeper is hooked:
; on these screens it sets type !LyraTalkerType in $0E80 instead of scanning
; the shop room table with a stale $A0. The talker index (SprMiscA, $0DA0)
; comes from the sprite's spawn position; an unknown position uses entry 0.
; Sprite_BB_Shopkeeper's Oracle dispatch (Core/early_game_balance.asm) sends
; types >= $0E here; type $0E stays the Banana shop item.
;
; Messages are PLACEHOLDERS (vanilla shop/thief lines) until scawful approves
; the wording. Progression gates and the gear take/return are not built.
; =========================================================

assert !ENABLE_EARLY_GAME_BALANCE == 1, "Lyra talkers use the Oracle $BB dispatch in Core/early_game_balance.asm"

!LyraTalkerType = $0F

; SpritePrep_Shopkeeper: LDA.b $A0 : LDY.b #$00 (4 bytes), before the room scan.
pushpc
org $068C0C ; @hook module=Sprites name=LyraTalker_Prep kind=jml target=LyraTalker_Prep
  JML LyraTalker_Prep
assert pc() == $068C10
pullpc

; In: X = slot, 8-bit A/X/Y. Out: returns through SpritePrep_Shopkeeper's RTS.
LyraTalker_Prep:
{
  LDA.b $1B : BNE .vanilla                 ; overworld only
  LDA.b $8A
  CMP.b #$A0 : BEQ .ours                   ; fishing village (wide $A0/$A1)
  CMP.b #$A1 : BEQ .ours
  CMP.b #$B3 : BEQ .ours
  CMP.b #$B4 : BEQ .ours
  CMP.b #$BB : BEQ .ours
  CMP.b #$BC : BNE .vanilla
  .ours
  LDA.b #!LyraTalkerType : STA.w $0E80,X
  PHB : PHK : PLB
  JSR LyraTalker_FindIndex                 ; Y = index
  TYA : STA.w SprMiscA,X
  LDA.w LyraTalker_Frames,Y : STA.w $0DC0,X
  PLB
  JML $068C71                              ; RTS (SpritePrep_Shopkeeper_SetType)
  .vanilla
  LDA.b $A0 : LDY.b #$00                   ; replaced code
  JML $068C10                              ; .next_room
}

; In: X = slot, DBR = this bank. Out: Y = talker index (0 if no match).
LyraTalker_FindIndex:
{
  REP #$20
  LDA.w SprX,X : AND.w #$00FF : STA.b $00
  LDA.w SprXH,X : AND.w #$00FF : XBA : ORA.b $00 : AND.w #$FFF0 : STA.b $00
  LDA.w SprY,X : AND.w #$00FF : STA.b $02
  LDA.w SprYH,X : AND.w #$00FF : XBA : ORA.b $02 : AND.w #$FFF0 : STA.b $02
  LDY.b #$00
  .next
    LDA.w LyraTalker_PosX,Y : BMI .none    ; $FFFF ends the table
    CMP.b $00 : BNE .skip
    LDA.w LyraTalker_PosY,Y : CMP.b $02 : BEQ .found
    .skip
    INY #2
    BRA .next
  .found
  SEP #$20
  TYA : LSR A : TAY
  RTS
  .none
  SEP #$20
  LDY.b #$00
  RTS
}

; Called from ShopBalance_Dispatch1E for $0E80 >= $0E. DBR = $1E, X = slot.
ShopBalance_OracleType:
{
  LDA.w $0E80,X : CMP.b #!LyraTalkerType : BEQ LyraTalker_Main
  JML ShopBalance_Banana
}

LyraTalker_Main:
{
  JSL $06F864                              ; SpriteDraw_AllocateOAMDeferToPlayer_long
  JSL $06DBF0                              ; SpriteDraw_SingleLarge_long

  ; Sprite_CheckIfActive_Bank1E ($1EFE78), inline.
  LDA.w $0DD0,X : CMP.b #$09 : BNE .exit
  LDA.w $0FC1 : BNE .exit
  LDA.b $11 : BNE .exit
  LDA.w $0CAA,X : BMI .active
  LDA.w $0F00,X : BNE .exit
  .active
  JSL $1EF4F3                              ; Sprite_BehaveAsBarrier

  ; Same idle flip as the vanilla clerk.
  LDA.w $0F50,X : AND.b #$3F : STA.b $00
  LDA.b $1A : ASL #3 : AND.b #$40 : ORA.b $00 : STA.w $0F50,X

  PHB : PHK : PLB
  LDA.w SprMiscA,X : ASL A : TAY
  LDA.w LyraTalker_Messages,Y : PHA
  LDA.w LyraTalker_Messages+1,Y : TAY
  PLA
  PLB
  JSL $05E1A7                              ; Sprite_ShowSolicitedMessage
  .exit
  RTL
}

; One row per talker. Position = spawn X/Y (low nibble ignored). Parent $B3
; is the 2x2 area at X $0600-$09FF, Y $0C00-$0FFF; tile (tx,ty) in the
; 64x64 area -> X = $0600 + tx*16, Y = $0C00 + ty*16. asar has no
; operator precedence (left to right), so keep the parentheses. Tiles from the roster
; board (ROSTER.md, AFS scratch); provisional until the crescent terrain pass.
LyraTalker_PosX:
  dw $0600+(49*16)                           ; 0 T1 wreck robber leader (49,44)
  dw $0600+(40*16)                           ; 1 T2 camp trader (40,46)
  dw $0600+(15*16)                           ; 2 T3 shell-game thief (15,38)
  dw $0600+(30*16)                           ; 3 T4 brawler (30,16)
  ; Fishing village: parent $A0 (2x1) at X $0000, Y $0800. Tiles from the
  ; north roster board (AFS scratch lyra-npcs-north).
  dw $0000+(26*16)                           ; 4 V1 ferry boatman, pier end (26,29)
  dw $0000+(22*16)                           ; 5 V2 cartographer, house porch (22,19)
  dw $0000+(27*16)                           ; 6 V3 net-mender, pier (27,24)
  dw $0000+(35*16)                           ; 7 V4 storyteller, east grass (35,16)
  dw $0000+(6*16)                            ; 8 V5 kid, southwest shore (6,29)
  dw $FFFF
LyraTalker_PosY:
  dw $0C00+(44*16)
  dw $0C00+(46*16)
  dw $0C00+(38*16)
  dw $0C00+(16*16)
  dw $0800+(29*16)                           ; 4 V1
  dw $0800+(19*16)                           ; 5 V2
  dw $0800+(24*16)                           ; 6 V3
  dw $0800+(16*16)                           ; 7 V4
  dw $0800+(29*16)                           ; 8 V5
  dw $FFFF

; $0DC0 frame: 0 = clerk body, 1 = chest-game man body (both sheet $4B).
LyraTalker_Frames:
  db $01, $00, $01, $00
  db $01, $00, $01, $00, $00                ; V1-V5

; PLACEHOLDER messages (vanilla) until approved Oracle text gets IDs.
LyraTalker_Messages:
  dw $0176                                 ; T1 (vanilla nice-thief line)
  dw $0165                                 ; T2 (vanilla shop clerk line)
  dw $0160                                 ; T3 (vanilla chest-game offer)
  dw $017E                                 ; T4 (vanilla thief line)
  ; V1-V5: vanilla placeholders; drafts await review (IDs $241-$246 claimed
  ; in AFS handoffs IDS.md).
  dw $0165                                 ; V1 ferry boatman
  dw $0165                                 ; V2 cartographer
  dw $0165                                 ; V3 net-mender
  dw $0165                                 ; V4 storyteller
  dw $0165                                 ; V5 kid
