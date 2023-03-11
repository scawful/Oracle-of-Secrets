; =============================================================================
; Zora Mask
; Fairy Flippers RAM Position $7EF33C - 01

; Normal Flippers RAM Position $7ef356 - 01

; =============================================================================

org $07A569
LinkItem_ZoraMask:
{
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A        ; clear the Y button state 

  LDA $6C : BNE .return                 ; in a doorway
  LDA $0FFC : BNE .return               ; can't open menu

  LDY.b #$04 : LDA.b #$23
  JSL AddTransformationCloud
  LDA.b #$14 : JSR Player_DoSfx2

  LDA $02B2 : CMP #$02 : BEQ .unequip   ; is the zora mask on?
  JSL UpdateZoraPalette
  LDA #$36 : STA $BC
  LDA #$02 : STA $02B2
  BRA .return
.unequip
  JSL Palette_ArmorAndGloves
  LDA #$10 : STA $BC : STZ $02B2        ; take the mask off

.return
  CLC
  RTS
}

; =============================================================================

org $368000
incbin gfx/zora_link.4bpp

; =============================================================================

UpdateZoraPalette:
{
  REP #$30  ; change 16 bit mode
  LDX #$001E

  .loop
  LDA.l zora_palette, X : STA $7EC6E0, X
  DEX : DEX : BPL .loop

  SEP #$30  ; go back to 8 bit mode
  INC $15   ; update the palette
  RTL       
}

; TODO: Change from "bunny palette" to blue zora palette colors 
zora_palette:
  dw #$7BDE, #$7FFF, #$2F7D, #$19B5, #$3A9C, #$14A5, #$19FD, #$14B6
  dw #$55BB, #$362A, #$3F4E, #$162B, #$22D0, #$2E5A, #$1970, #$7616
  dw #$6565, #$7271, #$2AB7, #$477E, #$1997, #$14B5, #$459B, #$69F2
  dw #$7AB8, #$2609, #$19D8, #$3D95, #$567C, #$1890, #$52F6, #$2357, #$0000

; =============================================================================

LinkItem_UsingZoraMask:
{

}

; =============================================================================
; Disassembled/Debugged Code of Conn's Zora Flippers 
; May God Give Me Strength 

; =============================================================================
; 22E100

  LDA $2F
  STA $0323
  JMP $E5F0
  NOP 
  NOP 
  NOP 
  NOP 
  LDA $0345
  CMP #$01
  BEQ $22E120
  LDA $7F500E
  CMP #$01
  BEQ $22E11C
  RTL 

; =============================================================================
; 22E120 

  LDA $F0
  CMP #$40
  BEQ $22E12D
  LDA #$00
  STA $7F500F
  RTL 
;-------
  LDA $7F500F
  CMP #$01
  BNE $22E136
  RTL 
;-------
  LDA #$01
  STA $7F500F
  JSR $E340
  NOP 
  NOP 
  LDA $1B
  BEQ $22E17D
  LDA $7F500E
  CMP #$00
  BNE $22E163
  JMP $E320

; =============================================================================
; 22E17D

  LDA $7F500E
  CMP #$00
  BNE $22E1A3
  LDA $5D
  CMP #$04
  BEQ $22E18C
  RTL 
;-------
  LDA #$01
  STA $7F500E
  STZ $5D
  LDA #$01
  STA $55
  STA $037B
  LDA #$08
  STA $5E
  NOP 
  NOP 
  NOP 
  RTL 
;-------
  LDA #$00
  JSL $22EF80
  LDA #$04
  STA $5D
  STZ $55
  STZ $5E
  LDA #$01
  STA $0345
  STZ $037B
  RTL 

; =============================================================================
; 22E1E0

  LDA $1B
  BNE $22E1F7
  LDA $7F500E
  CMP #$01
  BNE $22E1F7
  LDA #$01
  STA $55
  STZ $5D
  LDA #$08
  STA $5E
  RTL 
;-------
  LDA #$06
  STA $5D
  RTL 

; =============================================================================
; 22E260

  LDA $7EF33C
  AND #$00FF
  CMP #$0001
  BEQ $22E271
  LDA $7EF357
  RTL 

; -------
; 22E271
  SEP #$30
  LDA #$3C
  STA $1613
  STA $1615
  STA $1653
  STA $1655
  REP #$30
  LDA $7EF357
  RTL 

; =============================================================================
; 22E2A0
; 
; Description: routine is hooked at $07:8106, right before the 
;              Link_ControlHandlerTable jump loop. 
;
; Observed behavior of preserving the direction link was facing when diving
; E.g. face left, dive, turn right underwater, and resurface facing left

FairyFlipper_Prepare:
{
  JSR FairyFlippers_Main        ; $E530
  JSL FairyFlippers_HandleMagic ; $22E670
  LDA $7F500E : CMP #$01        ; are we currently underwater? 
  BEQ .underwater
  JMP FairyFlippers_RestoreControlHandler ; $E2F0

.underwater
  LDA $F0 ; Joypad 1 Register (preserves previous press)
  SEC : SBC #$0B ; ??? Not sure 
  BCS .beta
  JMP FairyFlippers_RestoreControlHandler ; $E2F0

.beta
  LDA $F0 ; Joypad 1 Register (preserves previous press)
  SEC : SBC #$4B ; probably Y 
  BCS .gamma

  LDA #$40
  STA $F0
  JMP $079657 ; Apart of LinkState_Swimming 

.gamma
  LDA $F0 ; Joypad 1 Register (preserves previous press)
  SEC : SBC #$BB
  BCS $22E2D5 ; Unknown?? Possibly dead branch 

  JMP FairyFlippers_RestoreControlHandler ; $E2F0
}


; =============================================================================
; 22E2F0

FairyFlippers_RestoreControlHandler:
{
  LDA $5D     ; Player Handler or "State"
  ASL 
  TAX 
  JMP $078106 ; Link_ControlHandler Jump Table Statement 
}

; =============================================================================
; 22E300

  LDA #$00
  STA $5D
  STA $7F500E
  STA $7F500F
  STA $5E
  STA $0345
  JSL $00E3FA
  RTL 

; =============================================================================
; 22E340 

  LDA $1B
  BEQ $22E34E
  LDA $0114
  BEQ $22E34E
  CMP #$08
  BEQ $22E34E
  RTS 
;-------
  LDA #$24
  STA $012E
  RTS 

; =============================================================================
; 22E460

  LDA $02E4
  AND #$00FF
  BNE $22E46E
  LDA #$0009
  LDX $8C
  RTL 
;-------
  LDA $0202
  AND #$00FF
  CMP #$000F
  BNE $22E481
  LDA $02F0
  AND #$00FF
  BEQ $22E487
  LDA #$0009
  LDX $8C
  RTL 

; =============================================================================
; 22E500

  CMP #$5A
  BEQ $22E507
  JMP $D00B

; =============================================================================
; 22E530
; Seems to always run when you are in the water 

FairyFlippers_Main:
{
  LDA $7F500E ; are we currently underwater? 
  CMP #$01
  BEQ $22E539
  RTS 
;-------------
; underwater 
  LDA $7F500F 
  CMP #$01
  BNE .alpha

  LDA $F0 : CMP #$40 ; controller again you shouldn't have 
  BNE .alpha

  LDA $67 : CMP #$00 ; is player facing up ? 
  BEQ .alpha
  STZ $67

.alpha
  LDA $1B ; Dungeon/Overworld flag 
  BNE $22E558

  ; Set underwater walking speed 
  LDA #$08
  STA $5E ; Link Speed Setting 

  RTS 
}

; =============================================================================
; 22E5F0

  LDA $7EF33C
  BNE $22E5F7
  RTL 
;-------
  LDA $4D
  BEQ $22E5FC
  RTL 
;-------
  JMP $E108

; =============================================================================
; 22E600
; Possibly relevant, unconfirmed 

  LDA $7EF34A
  AND #$00FF
  CMP #$0001
  BEQ $22E611
  LDA $7EF35C,X
  RTL 
;-------
  LDA $7EF33B
  AND #$00FF
  CMP #$0001
  BNE $22E622
  LDA $7EF35C,X
  RTL 
;-------
  SEP #$30
  LDA #$3C
  STA $139F
  STA $13A1
  STA $13DF
  STA $13E1
  REP #$30
  LDA $7EF35C,X
  RTL 


; =============================================================================
; 22E670

FairyFlippers_HandleMagic:
{
  LDA $7F500E ; probably free ram 
  CMP #$01
  BEQ $22E679
  RTL 
;-------
; Magic draining loop 
  LDA $7EF36E ; Load magic 
  BNE $22E688 ; branch if != 0 
  LDA #$3C
  STA $012E
  JMP $22E141
  LDA $7F500D ; load timer 
  BNE $22E69E ; branch if != 0 
  LDA #$18
  STA $7F500D ; set timer to 18
  LDA $7EF36E ; load magic 
  DEC         ; decrease magic by 1 
  STA $7EF36E ; store new magic 
  RTL 
;-------
  DEC 
  STA $7F500D ; decrease timer 
  RTL 
}

; =============================================================================
; 22E700

  STA $F6
  STY $FA
  REP #$30
  LDA $7EE000
  DEC 
  BNE $22E721
  LDA $7EF339
  INC 
  CMP #$1770
  BCC $22E71A
  LDA #$0000
  STA $7EF339
  LDA #$0E10
  STA $7EE000
  SEP #$30
  RTL 

; =============================================================================
; 22E760

  LDA #$0E10
  STA $7EE000
  LDY #$0000
  LDX $00
  RTL 

; =============================================================================
; 22E780
; Jesucristo...

    REP #$30
  LDY #$0000
  LDA $7EF339
  CMP #$000A
  BCC $22E796
  SEC 
  SBC #$000A
  INY 
  INY 
  BRA $22E789
  STA $00
  TYA 
  ASL 
  ASL 
  ASL 
  ORA $00
  LDY #$0000
  CMP #$0060
  BCC $22E7AD
  SEC 
  SBC #$0060
  INY 
  BRA $22E7A1
  LDX #$0000
  STA $00
  AND #$000F
  ASL 
  TAX 
  LDA $22E860,X
  STA $1376
  LDA $00
  AND #$00F0
  LSR 
  LSR 
  LSR 
  TAX 
  LDA $22E860,X
  STA $1374
  TYA 
  LDY #$0000
  CMP #$000A
  BCC $22E7DF
  SEC 
  SBC #$000A
  INY 
  INY 
  BRA $22E7D2
  STA $00
  TYA 
  ASL 
  ASL 
  ASL 
  ORA $00
  STA $00
  AND #$000F
  ASL 
  TAX 
  LDA $22E860,X
  STA $1370
  LDA $00
  AND #$00F0
  LSR 
  LSR 
  LSR 
  TAX 
  LDA $22E860,X
  STA $136E
  LDA $7E0AE0
  AND #$00FF
  CMP #$00C0
  BNE $22E816
  LDA #$2CF5
  BRA $22E819
  LDA #$241D
  STA $1372
  SEP #$30
  INC $0207
  LDA $F0
  RTL 

; =============================================================================
; 22E830

  ADC #$0020
  STA $1CD0
  LDA $10
  AND #$00FF
  CMP #$0012
  BEQ $22E841
  RTL 
;-------
  STZ $0223
  STZ $1CD8
  LDA $7F502E
  AND #$00FF
  CMP #$0000
  BNE $22E854
  RTL 

; =============================================================================
; 22EF50

  LDA $7EF3CC
  CMP #$0D
  BEQ $22EF59
  RTL 

; =============================================================================
; 22EF80

  STA $7F500E ; reset underwater variable 
  STZ $0372   ; link bounce flag 
  RTL 

; =============================================================================
; 22EFA0

  LDA $5D
  CMP #$05
  BNE $22EFAA
  STZ $0351
  RTS 
;-------
  LDA $4D
  CMP #$01
  BNE $22EFB4
  LDA #$04
  STA $5D
  RTS 