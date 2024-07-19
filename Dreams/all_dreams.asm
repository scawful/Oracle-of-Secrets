; Contains all the dreams in the game
; Each dream is a separate subroutine

; To enter a dream, Link will see the Maku tree
; after getting an essence from a dungeon.
; We will put the player into LinkState_Sleeping

Link_EnterDream:
{
  PHB : PHK : PLB

  JSR Link_HandleDreams

  PLB 

  RTL
}

Link_HandleDreams:
{
  LDA.b #$16 : STA.b $5D
  LDA.w CurrentDream
  JSL JumpTableLocal

  dw Dream_MushroomGrotto
  dw Dream_TailPalace
  dw Dream_KalyxoCastle
  dw Dream_ZoraTemple
  dw Dream_GlaciaEstate
  dw Dream_GoronMines
  dw Dream_DragonShip

  Dream_MushroomGrotto:
  {
    LDA.l DREAMS : ORA.b #%00000001 : STA.l DREAMS
    LDX.b #$00
    JSR Link_FallIntoDungeon
    RTS
  }

  Dream_TailPalace:
  {
    LDA.l DREAMS : ORA.b #%00000010 : STA.l DREAMS
    RTS
  }

  Dream_KalyxoCastle:
  {
    LDA.l DREAMS : ORA.b #%00000100 : STA.l DREAMS
    RTS
  }

  Dream_ZoraTemple:
  {
    LDA.l DREAMS : ORA.b #%00001000 : STA.l DREAMS
    RTS
  }

  Dream_GlaciaEstate:
  {
    LDA.l DREAMS : ORA.b #%00010000 : STA.l DREAMS
    RTS
  }

  Dream_GoronMines:
  {
    LDA.l DREAMS : ORA.b #%00100000 : STA.l DREAMS
    RTS
  }

  Dream_DragonShip:
  {
    LDA.l DREAMS : ORA.b #%01000000 : STA.l DREAMS
    RTS
  }
}

; Takes X as argument for the entrance ID 
Link_FallIntoDungeon:
{
  LDA.w .entrance, X
  STA.w $010E
  STZ.w $010F

  LDA.b #$11 : STA.b $10
  STZ.b $11 : STZ.b $B0

  RTS
.entrance
  db $7B, $01
}

print "End of all_dreams.asm             ", pc