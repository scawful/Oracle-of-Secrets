;===============================================================================

DrawMenuItem:
	STA.b $08
	STY.b $00

	LDA.b [$08]
	AND.w #$00FF

	BNE .not_zero

	LDY.w #NothingGFX
	BRA .draw

.not_zero
	DEC

	ASL
	ASL
    ASL
	ADC.b $00
	TAY

.draw
	LDA.w $0000,Y : STA.w $1108,X 
	LDA.w $0002,Y : STA.w $110A,X 
	LDA.w $0004,Y : STA.w $1148,X 
	LDA.w $0006,Y : STA.w $114A,X 

	RTS

;===============================================================================

DrawQuestIcons:
  LDX.w #$10

.loop
  LDA.w Menu_QuestIcons, X 
  STA.w $1364, X 
  LDA.w Menu_QuestIcons+$10, X 
  STA.w $13A4, X 
  LDA.w Menu_QuestIcons+$20, X 
  STA.w $13E4, X 
  LDA.w Menu_QuestIcons+$30, X 
  STA.w $1424, X 
  LDA.w Menu_QuestIcons+$40, X 
  STA.w $1464, X 
  LDA.w Menu_QuestIcons+$50, X 
  STA.w $14A4, X 
  LDA.w Menu_QuestIcons+$60, X 
  STA.w $14E4, X 
  DEX : DEX : BPL .loop

  LDA.w #$20F5 : STA.w $13B4 : STA.w $13F4 : STA.w $1474 : STA.w $14B4 

  RTS

;===============================================================================

DrawTriforceIcon:
  LDA.l $7EF37A 
  LDX.w #$3534                    
  LDY.w #$3544

  LSR : BCC +                     
  STX.w $1366 : INX : STX.w $1368 : DEX
  STY.w $13A6 : INY : STY.w $13A8 : DEY

+ LSR : BCC +
  STX.w $136A : INX : STX.w $136C : DEX
  STY.w $13AA : INY : STY.w $13AC : DEY

+ LSR : BCC +
  STX.w $136E : INX : STX.w $1370 : DEX
  STY.w $13AE : INY : STY.w $13B0 : DEY

+ LSR : BCC +
  STX.w $13E4 : INX : STX.w $13E6 : DEX
  STY.w $1424 : INY : STY.w $1426 : DEY

+ LSR : BCC +
  STX.w $13E8 : INX : STX.w $13EA : DEX
  STY.w $1428 : INY : STY.w $142A : DEY

+ LSR : BCC +
  STX.w $13EC : INX : STX.w $13EE : DEX
  STY.w $142C : INY : STY.w $142E : DEY

+ LSR : BCC +
  STX.w $13F0 : INX : STX.w $13F2 : DEX
  STY.w $1430 : INY : STY.w $1432 : DEY

+
  RTS

;===============================================================================

DrawPendantIcons:
    LDA.l $7EF374
    LSR : BCC +
    LDX.w #$2502 : STX.w $14A4 : INX : STX.w $14A6
    LDX.w #$2512 : STX.w $14E4 : INX : STX.w $14E6

+   LSR : BCC +
    LDX.w #$3D00 : STX.w $14AA : INX : STX.w $14AC
    LDX.w #$3D10 : STX.w $14EA : INX : STX.w $14EC

+   LSR : BCC +
    LDX.w #$2D06 : STX.w $14B0 : INX : STX.w $14B2
    LDX.w #$2D16 : STX.w $14F0 : INX : STX.w $14F2

+   RTS

;===============================================================================

; V H O P P P T T    T T T T T T T T <- tile format
; V = Vertical Flip
; H = Horizontal Flip
; O = Priority
; P = Palette 0 to 7
; T = Tile (which is normally called C for Character) 0 to 1023
; E000 is T = 0
; E100 would be T = 16

DrawHeartPieces:
    LDA.l $7EF36B
    AND.w #$00FF
    CMP.w #3 : BEQ .top_right
    CMP.w #1 : BEQ .top_left
    BCS .bottom_left
    RTS

.top_right
    LDX.w #$64AD : STX.w $14A0
.bottom_left
    LDX.w #$24AE : STX.w $14DE 
.top_left
    LDX.w #$24AD : STX.w $149E 
    RTS

;===============================================================================

DrawMusicNotes:
  LDA.w #$01
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,8)
	LDY.w #QuarterNoteGFX
	JSR DrawMenuItem

  LDA.w #$02
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,11)
	LDY.w #QuarterNoteGFX
	JSR DrawMenuItem

  LDA.w #$03
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,14)
	LDY.w #QuarterNoteGFX
	JSR DrawMenuItem

  LDA.w #$04
  STA.w MusicNoteValue
  LDA.w #MusicNoteValue
  LDX.w #menu_offset(17,17)
	LDY.w #QuarterNoteGFX
	JSR DrawMenuItem

  RTS

;===============================================================================

DrawYItems:
	; Set up the bank of our indirect address
	SEP #$30
	LDA.b #$7E : STA.b $0A

	REP #$30

	LDA.w #$7EF340
	LDX.w #menu_offset(7,2)
	LDY.w #BowsGFX
	JSR DrawMenuItem

	LDA.w #$7EF341
	LDX.w #menu_offset(7,5)
	LDY.w #BoomsGFX
	JSR DrawMenuItem

	LDA.w #$7EF342
	LDX.w #menu_offset(7,8)
	LDY.w #HookGFX
	JSR DrawMenuItem

  LDA.l $7EF343
  CMP.w #$00 : BEQ .no_bomb
  LDA.w #$0001
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(7,11)
  LDY.w #BombsGFX
	JSR DrawMenuItem
.no_bomb

	LDA.w #$7EF348
	LDX.w #menu_offset(7,14)
	LDY.w #DekuMaskGFX
	JSR DrawMenuItem

	LDA.w #$7EF35C
	LDX.w #menu_offset(7,17)
	LDY.w #BottlesGFX
	JSR DrawMenuItem

  LDA.w #$7EF354
  LDX.w #menu_offset(10,20)
  LDY.w #PowerGloveGFX
  JSR DrawMenuItem

	LDA.w #$7EF345
	LDX.w #menu_offset(10,2)
	LDY.w #Fire_rodGFX
	JSR DrawMenuItem

	LDA.w #$7EF346
	LDX.w #menu_offset(10,5)
	LDY.w #Ice_rodGFX
	JSR DrawMenuItem

  LDA.l $7EF34A
  CMP.w #$00 : BEQ .no_lamp
  DEC
  .no_lamp
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
	LDX.w #menu_offset(10,8)
	LDY.w #LampGFX
	JSR DrawMenuItem

  LDA.w #$7EF34B
	LDX.w #menu_offset(10,11)
	LDY.w #HammerGFX
	JSR DrawMenuItem

	LDA.w #$7EF347
	LDX.w #menu_offset(10,14)
	LDY.w #GoronMaskGFX
	JSR DrawMenuItem

	LDA.w #$7EF35D
	LDX.w #menu_offset(10,17)
	LDY.w #BottlesGFX
	JSR DrawMenuItem

  LDA.w #$7EF355
  LDX.w #menu_offset(12,20)
  LDY.w #PegasusBootsGFX
  JSR DrawMenuItem

	LDA.w #$7EF350
	LDX.w #menu_offset(13,2)
	LDY.w #SomariaGFX
	JSR DrawMenuItem

	LDA.w #$7EF351
	LDX.w #menu_offset(13,5)
	LDY.w #ByrnaGFX
	JSR DrawMenuItem

	; LDA.w #$7EF34C
	; LDX.w #menu_offset(13,8)
	; LDY.w #ShovelGFX
	; JSR DrawMenuItem

	LDA.w #$7EF34E
	LDX.w #menu_offset(13,8)
	LDY.w #BookGFX
	JSR DrawMenuItem

  LDA.w #$7EF34D
	LDX.w #menu_offset(13,11)
	LDY.w #JumpFeatherGFX
	JSR DrawMenuItem

	LDA.w #$7EF349
	LDX.w #menu_offset(13,14)
	LDY.w #BunnyHoodGFX
	JSR DrawMenuItem

	LDA.w #$7EF35E
	LDX.w #menu_offset(13,17)
	LDY.w #BottlesGFX
	JSR DrawMenuItem

  LDA.w #$7EF356
  LDX.w #menu_offset(14,20)
  LDY.w #FlippersGFX
  JSR DrawMenuItem

  LDA.w #$7EF34C ; ocarina
	LDX.w #menu_offset(16,2)
	LDY.w #ShovelGFX
	JSR DrawMenuItem

	LDA.w #$7EF353
	LDX.w #menu_offset(16,5)
	LDY.w #MirrorGFX
	JSR DrawMenuItem

  LDA.w #$7EF34F
	LDX.w #menu_offset(16,8)
	LDY.w #ShovelGFX
	JSR DrawMenuItem

  LDA.w #$7EF344
	LDX.w #menu_offset(16,11)
	LDY.w #PowderGFX
	JSR DrawMenuItem

	LDA.w #$7EF352
	LDX.w #menu_offset(16,14)
	LDY.w #StoneMaskGFX
	JSR DrawMenuItem

	LDA.w #$7EF35F
	LDX.w #menu_offset(16,17)
	LDY.w #BottlesGFX
	JSR DrawMenuItem

  LDA.w #$7EF357
  LDX.w #menu_offset(16,20)
  LDY.w #MoonPearlGFX
  JSR DrawMenuItem

	RTS

Menu_DrawQuestItems:
	SEP #$30
	LDA.b #$7E : STA.b $0A
	REP #$30

  LDA.w #$7EF359
  LDX.w #menu_offset(14,2)
  LDY.w #SwordGFX
  JSR DrawMenuItem 

  LDA.w #$7EF35A
  LDX.w #menu_offset(14,5)
  LDY.w #ShieldGFX
  JSR DrawMenuItem

  LDA.l $7EF35B
  INC
  STA.w MenuItemValueSpoof
  LDA.w #MenuItemValueSpoof
  LDX.w #menu_offset(14,8)
  LDY.w #TunicGFX
  JSR DrawMenuItem

  RTS