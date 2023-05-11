; =============================================================================
; Zora Mask
; Fairy Flippers RAM Position $7EF33C - 01
; Normal Flippers RAM Position $7EF356 - 01
; 
; Underwater Flag RAM Position $7F500E
; =============================================================================

org $0998FC
  AddTransitionSplash:

org $07A569
LinkItem_ZoraMask:
{
  ; Check for R button held 
  LDA $F2 : CMP #$10 : BNE .return 

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

org $07F93F
LinkState_UsingZoraMask:
{
  ; Check if the mask is equipped 
  LDA $02B2 : CMP #$02 : BNE .normal

  CLC

  ; Check if we are in water or not 
  LDA $5D : CMP #$04 : BEQ .swimming
  
.normal
  ; Return to normal state 
  STZ $55
  STZ $037B
  STZ $0351
  LDA #$00 : STA $5E ; Reset speed to normal 
  STA $037B
  JMP .return
  
.swimming
  ; ---------------------------------------------------------------------------

  ; Check if we are indoors or outdoors 
  LDA $1B : BEQ .overworld ; z flag is 1 

  ; Check if already underwater
  LDA $0AAB : BEQ .dive_dungeon
  
  ; Handle dungeon swimming (hard)
.dive_dungeon

  LDA #$01 : STA $5D
  ; Else, restore to normal swimming state 
  LDA.b #$15 : LDY.b #$00
  JSL AddTransitionSplash
  LDA.b #$00 : STA $EE

  JSR $E8F0 ; HandleIndoorCameraAndDoors
  RTS

  ; ---------------------------------------------------------------------------

.overworld 
  ; Check the Y button and clear state if activated
  JSR Link_CheckNewY_ButtonPress : BCC .return
  LDA $3A : AND.b #$BF : STA $3A       

  ; Check if already underwater 
  LDA $0AAB : BEQ .dive

  STZ $55     ; Reset cape flag 
  STZ $0AAB   ; Reset underwater flag 
  STZ $0351   ; Reset ripple flag 
  LDA #$00 : STA $037B ; Reset invincibility flag
  LDA #$04 : STA $5D

  JMP .return

.dive
  ; Handle overworld underwater swimming 
  LDA #$01 : STA $55   ; Set cape flag 
  STA $037B            ; Set invincible flag 
  LDA #$08 : STA $5E   ; Set underwater speed 
  LDA #$01 : STA $0AAB ; Set underwater flag
  STA $0351 ; Water ripples around sprite 

  ; Splash visual effect 
  LDA.b #$15 : LDY.b #$00
  JSL AddTransitionSplash

  ; Stay in swimming mode 
  LDA #$04 : STA $5D
  ; Splash sound effect 
  ; LDA #$24 : STA $012E  

.return
  JSR $E8F0 ; HandleIndoorCameraAndDoors 
}

print "Next address for jump in bank07:  ", pc 

; =============================================================================

; End of LinkState_Swimming
org $079781
  JSR LinkState_UsingZoraMask
  RTS

; =============================================================================
; Disassembled/Debugged Code of Conn's Zora Flippers 
; May God Give Me Strength 

; =============================================================================
; 22E0E0

org $348000
FairyFlippers_E0E0:
{
  LDA $1B     ; 1 if the player is in indoors and 0 otherwise.
  BNE .alpha  ; we are outdoors 

  LDA $7F500E ; are we currently underwater? 
  CMP #$01
  BNE .alpha  ; we are not underwater 

  LDA #$01
  STA $55     ; activate cape flag (invisible, invincible)
  STZ $5D     ; reset player to ground state 
  LDA #$08
  STA $5E     ; set the player speed 
  RTL 
;-------
.alpha
  LDA #$01
  STA $4D
  RTL 
}

; =============================================================================
; 22E100

FairyFlippers_E100:
{
  LDA $2F     ; The direction the player is currently facing 
  STA $0323   ; Mirror of $2F 
  JMP FairyFlippers_E5F0 ; $E5F0   
  NOP 
  NOP 
  NOP 
  NOP 
  LDA $0345   ; Set to 1 when we are in deep water, 0 otherwise 
  CMP #$01    ; Are we in deep water? 
  BEQ FairyFlippers_E120
  LDA $7F500E
  CMP #$01
  BEQ $22E11C
  RTL 
}

; =============================================================================
; 22E120 

FairyFlippers_E120:
{
  LDA $F0     ; Joypad 1 Register 
  CMP #$40
  BEQ .alpha  ; $22E12D
  LDA #$00
  STA $7F500F
  RTL 
;-------
.alpha
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
}

; =============================================================================
; 22E17D

FairyFlippers_E17D:
{
  LDA $7F500E
  CMP #$00
  BNE $22E1A3
  LDA $5D     ; Player Handler or "State"
  CMP #$04
  BEQ $22E18C
  RTL 
;-------
  LDA #$01
  STA $7F500E
  STZ $5D     ; Player Handler or "State"
  LDA #$01
  STA $55     ; Cape flag 
  STA $037B
  LDA #$08
  STA $5E     ; Speed setting for link 
  NOP 
  NOP 
  NOP 
  RTL 
;-------
  LDA #$00
  JSL $22EF80
  LDA #$04
  STA $5D     ; Player Handler or "State"
  STZ $55     ; Reset cape flag (invisible invincible)
  STZ $5E     ; Reset Speed
  LDA #$01
  STA $0345   ; Set to 1 when we are in deep water. 0 otherwise 
  STZ $037B
  RTL 
}

; =============================================================================
; 22E1E0
; Observed behavior: Triggers when entering and exiting water indoors only
; Returns to 3C30B below 
; Noted changes added 

FairyFlippers_SetFlipperAbilities:
{
  LDA $1B     ; Flag set to 1 when indoors, 0 otherwise
  BNE .set_player_state

  LDA $7F500E ; 
  CMP #$01
  BNE .set_player_state

  LDA #$01
  STA $55 ; Set cape flag (invisible invincible)
  STZ $5D ; Player Handler or "State"
  LDA #$08  
  STA $5E ; Set player speed 
  RTL 
;-------
.set_player_state
  LDA #$06 ; recoil mode 2 
  STA $5D ; Player Handler or "State"
  RTL 
}

; =============================================================================
; *$3C2C3-$3C30B LOCAL

Vanilla_UntitledRoutine:
{
  LDA $1B : BNE .alpha          ; Set to 1 if indoors, 0 otherwise 
  LDX #$02
  BRA .beta

.alpha
  LDX $1D
  LDA $047A : BEQ .beta
  LDX #$00                      ; Modified from vanilla `LDY.b #$00`

.beta
  STX $00
  LDA $C2BA, X : TAX 
  LDA $66 : BNE .gamma
  TXA : EOR #$FF : INC : TAX 

.gamma
  STX $27
  STZ $28
  LDX $00
  LDA $C2BD,X

  STA $29     ; vertical resistance 
  STA $02C7   ; countdown timer 
  STZ $24     ; z coordinate for link
  STZ $25     ; ??? No idea 

  LDA $C2C0,X
  JSL $8EFCE0 ; Dungeon Code (Flippers?)
  CMP #$02 : BEQ .delta
  JSL FairyFlippers_E0E0 ; $22E0E0 
  STZ $0360

.delta
  JSL FairyFlippers_SetFlipperAbilities ; $22E1E0
  RTS 
}


; =============================================================================
; 22E260

FairyFlippers_E260:
{
  LDA $7EF33C ; fairy flippers save ram 
  AND #$00FF
  CMP #$0001
  BEQ .has_fairy_flippers ; $22E271 
  LDA $7EF357
  RTL 

; -------
; 22E271
.has_fairy_flippers
  SEP #$30
  LDA #$3C
  STA $1613
  STA $1615
  STA $1653
  STA $1655
  REP #$30
  LDA $7EF357
  RTL 
}

; =============================================================================
; 22E2A0
; 
; Description: routine is hooked at $07:8106, right before the 
;              Link_ControlHandlerTable jump loop. 
;
; Observed behavior of preserving the direction link was facing when diving
; E.g. face left, dive, turn right underwater, and resurface facing left

FairyFlippers_Prepare:
{
  JSR FairyFlippers_Main        ; $E530
  JSL FairyFlippers_HandleMagic ; $22E670
  LDA $7F500E : CMP #$01        ; are we currently underwater? 
  BEQ .underwater
  JMP FairyFlippers_RestoreControlHandler ; $E2F0

  ; if so, restore control 
.underwater
  LDA $F0 ; Joypad 1 Register (preserves previous press)
  SEC : SBC #$0B ; up left right it seems 
  BCS .beta
  JMP FairyFlippers_RestoreControlHandler ; $E2F0

.beta
  LDA $F0 ; Joypad 1 Register (preserves previous press)
  SEC : SBC #$4B ; probably Y 
  BCS .gamma

  LDA #$40
  STA $F0
  ; TODO: RESTORE ME 
  ; JMP $079657 ; Apart of LinkState_Swimming 

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
  LDA $5D ; Player Handler or "State"     
  ASL 
  TAX 
  ; TODO: RESTORE ME 
  ; JMP $078106 ; Link_ControlHandler Jump Table Statement 
}

; =============================================================================
; 22E300

FairyFlippers_E300:
{
  LDA #$00
  STA $5D ; Player Handler or "State"
  STA $7F500E
  STA $7F500F
  STA $5E
  STA $0345
  JSL $00E3FA
  RTL 
}

; =============================================================================
; 22E340 

FairyFlippers_E340:
{
  LDA $1B     ; 1 if indoors, 0 otherwise
  BEQ $22E34E
  LDA $0114   ; Value of the type of tile Link is standing on 
  BEQ $22E34E
  CMP #$08
  BEQ $22E34E
  RTS 
;-------
  LDA #$24   ; Splash sound effect 
  STA $012E  
  RTS 
}

; =============================================================================
; 22E460

FairyFlippers_E460:
{
  LDA $02E4  ; If flag nonzero, Link cannot move 
  AND #$00FF
  BNE .alpha ; $22E46E
  LDA #$0009
  LDX $8C
  RTL 
;-------
.alpha
  LDA $0202   ; currently selected item 
  AND #$00FF
  CMP #$000F  ; what item is F? 
  BNE $22E481
  LDA $02F0
  AND #$00FF
  BEQ $22E487
  LDA #$0009
  LDX $8C
  RTL 
}


; =============================================================================
; 22E500

FairyFlippers_E500:
{
  CMP #$5A
  BEQ $22E507
  JMP $D00B
}

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

FairyFlippers_E5F0:
{
  LDA $7EF33C
  BNE $22E5F7
  RTL 
;-------
  LDA $4D
  BEQ $22E5FC
  RTL 
;-------
  JMP $E108
}

; =============================================================================
; 22E600
; Possibly relevant, unconfirmed 

; Referenced at: 0D:E507

FairyFlippers_E600:
{
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
}

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
  ; TODO: RESTORE ME
  ; JMP $22E141
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

FairyFlippers_E700:
{
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
}

; =============================================================================
; 22E760

FairyFlippers_E760:
{
  LDA #$0E10
  STA $7EE000
  LDY #$0000
  LDX $00
  RTL 
}

; =============================================================================
; 22E780
; Jesucristo...

FairyFlippers_E780:
{
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
}

; =============================================================================
; 22E830

FairyFlippers_E830:
{
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
}

; =============================================================================
; 22EF50

{
  LDA $7EF3CC
  CMP #$0D
  BEQ $22EF59
  RTL 
}

; =============================================================================
; 22EF80

{
  STA $7F500E ; reset underwater variable 
  STZ $0372   ; link bounce flag 
  RTL 
}

; =============================================================================
; 22EFA0

{
  LDA $5D ; Player Handler or "State"
  CMP #$05
  BNE $22EFAA
  STZ $0351
  RTS 
;-------
  LDA $4D
  CMP #$01
  BNE $22EFB4
  LDA #$04
  STA $5D ; Player Handler or "State"
  RTS 
}