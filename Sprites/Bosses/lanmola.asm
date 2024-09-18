; ==============================================================================\
; RAM used

;$35-$37 as some temp draw ram
;$70 lanmola kill count
;$7EEA00-$7EEAB8 draw table storage
;$7EEAB8-$7EEAC9 room cleared flags

; ==============================================================================
; Hooks

org $05AB93
    Sprite2_CheckDamage:

org $05F955
    Sprite2_CheckIfActivePermissive:

org $05FA2E
    Sprite2_MoveAltitude:

org $05F9ED
    Sprite2_Move:

org $068F95 ; skip SpritePrep_Bosses
    NOP : NOP : NOP
    ;JSR $8F1C ; original JSR
    JSL Lanmola_FinishInitialization

org $05B60E
    dw Sprite_Lanmola

org $1AF9D6
    JSL SetShrapnelTimer

org $1AF981
    Lanmola_SpawnShrapnel:

org $1DF614
    Sprite_ConvertVelocityToAngle:

org $05A377 ;replace vanilla sprite_lanmola.asm

; ==============================================================================

Lanmola_FinishInitialization:
{
    PHB : PHK : PLB

    LDA.l .starting_delay, X : STA $0DF0, X
        
    LDA.b #$FF : STA $0F70, X
        
    PHX
        
    LDY.b #$3F
        
    LDA $7EEA00, X : TAX ;.sprite_regions
        
    LDA.b #$FF

    .reset_extended_sprites
        STA $7FFE00, X
            
        INX
        
    DEY : BPL .reset_extended_sprites
        
    PLX
        
    LDA.b #$07 : STA $7FF81E, X

    JSL Sprite_Lanmola_Init_DataLONG

    PLB
        
    RTL

    .starting_delay
    db $80, $CF, $FF, $60
}

; ==============================================================================

Sprite_Lanmola:
{
    ;JSR Sprite2_CheckIfActivePermissive
        
    LDA $0D80, X
        
    JSL UseImplicitRegIndexedLocalJumpTable
        
    dw Lanmola_Wait  ;0x00
    dw Lanmola_Mound ;0x01
    dw Lanmola_Fly   ;0x02
    dw Lanmola_Dive  ;0x03
    dw Lanmola_Reset ;0x04
    dw Lanmola_Death ;0x05
}

; ==============================================================================

Lanmola_Wait: ;0x00
{
    JSR Lanmola_Draw

    LDA $0DF0, X : BNE .delay ; ORA $0F00, X :
        LDA.b #$7F : STA $0DF0, X
            
        INC $0D80, X
        
        ;Play rumbling sound
        LDA.b #$35 : JSL Sound_SetSfx2PanLong
    
    .delay
    
    RTS
}

; ==============================================================================

Lanmola_Mound: ;0x01
{
    JSL Lanmola_MoveSegment
    JSR Lanmola_DrawMound
    JSL CheckIfActive : BCS Lanmola_Wait_delay

    LDA $0DF0, X : BNE .return
        JSL Lanmola_SpawnShrapnel
            
        LDA.b #$13 : STA $012D

        TXY
        JSL GetRandomInt : AND.b #$07 : TAX
        LDA $7EEAA8, X : STA $0DA0, Y ; Get random X pos to have the lanmola fly to. ;.randXPos
            
        JSL GetRandomInt : AND.b #$07 : TAX
        LDA $7EEAB0, X : STA $0DB0, Y ; Get random Y pos to have the lanmola fly to. ;.randYPos
        TYX
            
        INC $0D80, X
            
        LDA.b #$18 : STA $0F80, X
            
        STZ $0EC0, X
        STZ $0ED0, X
        
        ; ALTERNATE ENTRY POINT
        .Lanmola_SetScatterSandPosition

        LDA SprXH, X : STA $0DC0, X
        LDA SprYH, X : STA $0EB0, X
        
        LDA SprX, X : STA $0DE0, X
        LDA SprY, X : STA $0E70, X
            
        LDA.b #$4A : STA $0E00, X
    
    .return
    
    RTS
}

; ==============================================================================

Lanmola_Fly: ;0x02
{
    JSR Lanmola_Draw
    JSL Lanmola_DrawDirtLONG
    JSL CheckIfActive : BCS Lanmola_Mound_return

    JSR Sprite2_CheckDamage
    JSR Sprite2_MoveAltitude
        
    ; Slowly decrease the Y speed when first coming out of the ground
    LDA $0EC0, X : BNE .notRising
        LDA $0F80, X : SEC : SBC.b #$01 : STA $0F80, X : BNE .beta 
            INC $0EC0, X
        
        .beta
        
        BRA .dontSwitchDirections
    
    .notRising
    
    ; Use the Y speed to bob up and down
    LDA $1A : AND.b #$01 : BNE .dontSwitchDirections ; Every other frame.
        TXY
        LDA $0ED0, X : AND.b #$01 : TAX
            
        LDA $0F80, Y : CLC : ADC $7EEA9C, X : STA $0F80, Y : CMP $7EEA9E, X : BNE .dontSwitchDirections2 ;.y_speed_slope ;.y_speeds
            TYX : INC $0ED0, X ; Switch direction

        .dontSwitchDirections2
        TYX
    
    .dontSwitchDirections
    
    LDA $0DA0, X : STA $04
    LDA SprXH, X : STA $05
    LDA $0DB0, X : STA $06
    LDA SprYH, X : STA $07
    LDA SprX, X : STA $00
    LDA SprXH, X : STA $01
    LDA SprY, X : STA $02
    LDA SprYH, X : STA $03
        
    REP #$20
        
    ; If our position is 0x0002 away from the random X and Y pos we chose earlier go to the next stage.
    LDA $00 : SEC : SBC $04 : CLC : ADC.w #$0002 : CMP.w #$0004 : BCS .notCloseEnough
        LDA $02 : SEC : SBC $06 : CLC : ADC.w #$0002 : CMP.w #$0004 : SEP #$20 : BCS .notCloseEnough
            INC $0D80, X
    
    .notCloseEnough
    
    SEP #$20
        
    LDA.b #$0A
    
    JSL Sprite_ProjectSpeedTowardsEntityLong
        
    LDA $00 : STA $0D40, X
    LDA $01 : STA $0D50, X
        
    JSR Sprite2_Move

    .return
        
    RTS
}

; ==============================================================================

Lanmola_Dive: ;0x03
{
    JSR Lanmola_Draw
    JSL Lanmola_DrawDirtLONG
    JSL CheckIfActive : BCS Lanmola_Fly_return

    JSR Sprite2_CheckDamage
    JSR Sprite2_Move
    JSR Sprite2_MoveAltitude
        
    LDA $0F80, X : CMP.b #$EC : BMI .alpha
        SEC : SBC.b #$01 : STA $0F80, X
    
    .alpha
    
    ; If we are under the ground go to the reset stage
    LDA $0F70, X : BPL .notUnderGroundYet
        INC $0D80, X
        
        LDA.b #$80 : STA $0DF0, X
        
        JSR Lanmola_Mound_Lanmola_SetScatterSandPosition
    
    .notUnderGroundYet
    
    RTS
}

; ==============================================================================

Lanmola_Reset: ;0x04
{
    JSR Lanmola_Draw
    JSL Lanmola_DrawDirtLONG
    JSL CheckIfActive : BCS Lanmola_Dive_notUnderGroundYet
    
    LDA $0DF0, X : BNE .wait
        STZ $0D80, X ; Go back to wait phase
        
        TXY
        JSL GetRandomInt : AND.b #$07 : TAX
        LDA $7EEAA8, X : STA.w SprX, Y ; Get random X pos to have the lanmola fly to. ;.randXPos
            
        JSL GetRandomInt : AND.b #$07 : TAX
        LDA $7EEAB0, X : STA.w SprY, Y ; Get random Y pos to have the lanmola fly to. ;.randYPos
        TYX
    
    .wait
    
    RTS
}

; ==============================================================================

Lanmola_Death: ;0x05
{
    JSR Lanmola_Draw

    LDA $0DF0, X : BNE .timerNotDone
        STZ $0DD0, X

        ; Y is the index where we write in RAM
        PHX ; keep X
        TYX ; Since we'll need X for long we move Y in X
        LDA $7EEAB8, X : ORA $00 : STA $7EEAB8, X
        PLX ; pull back x because sprite will crash otherwise even if it's dying...

        ; There can only be 4 so we only need to check for 4
        PHX : LDX.b #$03

        .next_sprite
            LDA $0E20, X : CMP.b #$54 : BNE .notLanmola
                LDA $0DD0, X : BNE .oneIsntDead

            .notLanmola

        DEX : BPL .next_sprite
            TYX : LDA.b #$0F : STA $7EEAB8, X
            LDA.b #$1A : STA $012F

        .oneIsntDead
        PLX

    .timerNotDone
    
    LDA $0DF0, X : CMP.b #$20 : BCC Lanmola_Reset_wait
                   CMP.b #$A0 : BCS Lanmola_Reset_wait
                   AND.b #$0F : BNE Lanmola_Reset_wait
        TXY
        LDA $7FF81E, X : TAX
        
        LDA $0E80, Y : SEC : SBC $7EEAA0, X ;.dataDeath

        PHY : TXY : PLX
        AND.b #$3F : CLC : ADC $7EEA00, X : PHX : TAX ;.sprite_regions

        LDA $7FFC00, X : STA $0A
        LDA $7EE800, X : STA $0B

        LDA $7FFD00, X : SEC : SBC $7FFE00, X : STA $0C
        LDA $7EE900, X : STA $0D

        REP #$20
        LDA $0A : SEC : SBC $E2 : STA $0A
        LDA $0C : SEC : SBC $E8 : STA $0C
        SEP #$20
        
        PLX
        
        ; Spawn a sprite that instantly dies as a boss explosion.
        LDA.b #$00 : JSL Sprite_SpawnDynamically : BMI .spawn_failed
            LDA.b #$0B : STA $0AAA
            
            LDA.b #$04 : STA $0DD0, Y
            
            LDA.b #$1F : STA $0DF0, Y : STA $0D90, Y
        
            LDA $0A : STA.w SprX, Y
            LDA $0B : STA.w SprXH, Y
            LDA $0C : STA.w SprY, Y
            LDA $0D : STA.w SprYH, Y
            
            LDA.b #$03 : STA $0E40, Y
            
            LDA.b #$0C : STA $0F50, Y
            
            LDA.b #$0C : JSL Sound_SetSfx2PanLong
            
            LDA $7FF81E, X : BMI .beta
                DEC A : STA $7FF81E, X

            .beta
        .spawn_failed
    .return
    
    RTS
}

; ==============================================================================

Lanmola_Draw:
{
    JSL Lanmola_MoveSegment
    
    LDA $0B89, X : STA $03
        
    LDA $7FF81E, X : BPL .beta
        RTS
    
    .beta
    
    PHX
        
    STA $0F
        
    LDA $0D40, X : ASL A : ROL A : AND.b #$01 : TAX
        
    LDA $7EEA06, X : STA $0C ;.data2
        
    LDA $7EEA04, X : TAY ;.data1
        
    LDX $0F
    
    .loopBody
        PHX : STX $0D
        
        LDA $02 : CLC : ADC $04 : TAX
        
        LDA $02 : SEC : SBC.b #$08 : AND.b #$3F : STA $02

        LDA $7FFC00, X : STA $0A
        LDA $7EE800, X : STA $0B
        LDA $7FFD00, X : STA $08
        LDA $7EE900, X : STA $09
        LDA $7FFE00, X : STA $05

        PHX

        TYA : CLC : ADC.b #$20 : TAX

        REP #$20
        LDA $0A : SEC : SBC $E2 : STA ($90), Y ;Body X byte

        STZ $37
        BPL .notNegative
            INC $37

        .notNegative

        PHY : TXY : PLX
        STA ($90), Y ;Shadow X byte
        PHY : TXY : PLX

        INY : INX

        CLC : ADC.w #$0040 : CMP.w #$0140 : SEP #$20 : BCS .out_of_boundsX
            LDA $05 : BMI .out_of_boundsX
                STA $06 : STZ $07

                REP #$20
                LDA $08 : SEC : SBC $06 : SEC : SBC $E8 : STA ($90), Y ;Body Y byte
                CLC : ADC.w #$0010 : CMP.w #$0100

                BCC .on_screen_y1
                    SEP #$20
                    LDA.b #$F0 : STA ($90), Y ;Body offscreen Y Byte
                    REP #$20

                .on_screen_y1

                PHY : TXY : PLX
                
                LDA $08 : CLC : ADC.w #$000A : SEC : SBC $E8 : STA ($90), Y ;Shadow Y byte
                CLC : ADC.w #$0010 : CMP.w #$0100
                SEP #$20
                PHY : TXY : PLX

                BCC .on_screen_y2
                    PHY : TXY : PLX
                    LDA.b #$F0 : STA ($90), Y ;Shadow offscreen Y Byte
                    PHY : TXY : PLX

                .on_screen_y2

                BRA .skip

                .out_of_boundsX
                    LDA.b #$F0 : STA ($90), Y ;Body offscreen Y Byte
                    PHY : TXY : PLX
                    LDA.b #$F0 : STA ($90), Y ;Shadow offscreen Y Byte
                    PHY : TXY : PLX

        .skip

        PLX

        PHY
        
        LDA $7FFF00, X : TAX
        
        LDY $0D
        
        LDA $0F : CMP.b #$07 : BNE .dontDrawTail
            CPY.b #$00 : BNE .dontDrawTail
                LDA $7EEA18, X ;.chrTail
                BRA .notHead
    
        .dontDrawTail
    
        LDA.b #$C6
        
        CPY $0F : BNE .notHead
            LDA $7EEA08, X ;.chrHead

        .notHead
    
        PLY : INY : STA ($90), Y ;Body chr

        PHY

        TYA : CLC : ADC.b #$20 : TAY

        LDA.b #$6C       : STA ($90), Y ;Shadow chr
        LDA.b #$36 : INY : STA ($90), Y ;Shadow properties

        PLY

        INY

        LDA $7EEA28, X : ORA $03 : STA ($90), Y ;Body properties ;.propertiesBody
        
        TYA : PHY : LSR #2 : TAY
        CLC : ADC.b #$08 : TAX
        
        LDA.b #$02 : ORA $37 : STA ($92), Y ;Body size and extra X bit
        PHY : TXY : PLX      : STA ($92), Y ;Shadow size and extra X bit
        
        PLA : CLC : ADC $0C : TAY
        
    PLX : DEX : BMI .bodyDone
        JMP .loopBody

    .bodyDone
        
    PLX

    RTS
}

; ==============================================================================

Lanmola_DrawMound:
{
    LDA.b #$04 : JSL OAM_AllocateFromRegionB

    PHX

    LDA $0DF0, X : LSR #3 : TAX
        
    LDA $7EEA54, X : TAX ;.frameMound
        
    LDY.b #$00
        
    REP #$20
    LDA $0FDA : SEC : SBC $E8 : STA $02
    LDA $0FD8 : SEC : SBC $E2 : STA ($90), Y
    
    STZ $37
    BPL .notNegative
        INC $37

    .notNegative

    INY

    CLC : ADC.w #$0040 : CMP.w #$0140 : BCS .out_of_boundsx

    LDA $02 : STA ($90), Y

    CLC : ADC.w #$0010 : CMP.w #$0100
    BCC .on_screen_y
        .out_of_boundsx
        LDA.w #$00F0 : STA ($90), Y 

    .on_screen_y
    SEP #$20

    LDA $7EEA48, X : INY : STA ($90), Y ;.chrMound
    LDA $7EEA4E, X : INY : STA ($90), Y ;.propertiesMound
        
    TYA : LSR #2 : TAY
        
    LDA.b #$02 : ORA $37 : STA ($92), Y ;.sizesMound
        
    PLX
        
    RTS
}

; ==============================================================================

assert pc() <= $05A880

; ==============================================================================
org $1DCFCB

Sprite_Shrapnel:
{
    ; This sprite manifests as a boulder outdoors, and as shrapnel indoors.
    LDA $1B : BEQ $5B ;Boulder_Main
        
    ; Check if we can draw.
    LDA $0FC6 : CMP.b #$03 : BCS .invalid_gfx_loaded
        JSL $06DBF8 ;Sprite_PrepAndDrawSingleSmallLong
    
    .invalid_gfx_loaded
    
    ;JSR $E8A2 ;Sprite4_CheckIfActive
    JSL CheckIfActive : BCC .active
        RTS

    .active
        
    LDA $1A : ASL #2 : AND.b #$C0 : STA $0F50, X ; : ORA.b #$00
        
    JSR $E948 ;Sprite4_MoveXyz
        
    TXA : EOR $1A : AND.b #$03 : BNE .noTileCollision
        REP #$20
            
        LDA $0FD8 : SEC : SBC $22 : CLC : ADC.w #$0004
            
        CMP.w #$0010 : BCS .player_not_close
            
        LDA $0FDA : SEC : SBC $20 : CLC : ADC.w #$FFFC
            
        CMP.w #$000C : BCS .player_not_close
            
        SEP #$20
        
        JSL $06F41F ;Sprite_AttemptDamageToPlayerPlusRecoilLong
        
    .player_not_close
        
    SEP #$20

    ;JSR $8094 : BEQ .noTileCollision ;Sprite4_CheckTileCollision
        ;STZ $0DD0, X

    .noTileCollision

    LDA $0DF0, X : BNE .timerNotDone
        STZ $0DD0, X

    .timerNotDone
    
    RTS
}
    
; ==============================================================================

assert pc() <= $1DD02A