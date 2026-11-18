; ============================================================================
; Intro Scene 0 Storybook Art Engine (QUEUE269 Option 1)
; ============================================================================
; Replaces vanilla Scene 0 polka-dot BG1 with four 224x96 15-color 4bpp panels
; streamed cleanly across the four pages of Message_1C0 without modifying
; Message_1C0 text/canon (parsed $7F1200 offsets are -4 from raw ROM):
;   Panel 0 (Page 1): Link riding toward Hyrule Castle  ($67 fade-in at $0004)
;   Panel 1 (Page 2): Shipwreck & Maku Tree cliff        (hook at $0060)
;   Panel 2 (Page 3): Abyssal Shrine & Twin Emblems      ($67/$67 at $00A9)
;   Panel 3 (Page 4): Three Essence crests over Kalyxo   (hook at $00FB)
;
; Memory layout:
;   ROM:  Bank $56 ($568000-$56FFFF) + 5-byte NMI stub in $00E852
;   WRAM: $7F8100-$7FABFF (up to 11 KB CHR decompress buffer, in UNUSED_7F74D8)
;         $7FB100-$7FB8FF (2 KB map decompress buffer, above ThinIce $7FB035)
;         $7FF3A0-$7FF3AF (16 B state block in UNUSED_7FF180)
;   VRAM: $0000-$1BFF (BG1 4bpp CHR, <=448 tiles), $1C00-$1FFF (BG1 32x32 map)
;         $2000-$3FFF (BG2 4bpp CHR untouched), $6000-$63FF (BG3 VWF tilemap)
;         $6800-$6BFF (BG2 32x32 weave tilemap), CGRAM row 6 ($7EC3C0/$7EC5C0)
; ============================================================================

pushpc

!Storybook_ActiveMarker = $5A
!Storybook_ChunkBytes   = $0A00       ; 2560 B/VBlank -> all 4 panels fit in 5 VBlanks
!Storybook_ChrBuf       = $7F8100     ; up to $2B00 B decompressed 4bpp CHR (<$7FB000)
!Storybook_MapBuf       = $7FB100     ; $0800 B decompressed 32x32 map (>$7FB035, <$7FDD80)

; Transient state block in UNUSED_7FF180 (Core/ram.asm), after BossDirector ($7FF39D).
!Storybook_Active       = $7FF3A0     ; byte: $5A while Scene 0 owns BG1/PPU
!Storybook_State        = $7FF3A1     ; byte: 0=idle/fade, 2=NMI streaming, 3=stream done
!Storybook_Panel        = $7FF3A2     ; byte: current/next panel index (0..3)
!Storybook_Pending      = $7FF3A3     ; byte: 0=normal, 1=virtual fade-out+stream, 2=fade-in
!Storybook_HooksDone    = $7FF3A4     ; byte: bit0=Page1->2 ($0060), bit1=Page3->4 ($00FB)
!Storybook_ChunkOff     = $7FF3A6     ; word: byte offset streamed in current State=2
!Storybook_ChrTotal     = $7FF3A8     ; word: uncompressed CHR byte size of active panel

; ----------------------------------------------------------------------------
; Preimage guards and vanilla hooks
; ----------------------------------------------------------------------------
assert read4($0CEE90) == $9A85A3A9, "Attract_Initialize CGADSUB moved"
org $0CEE91 : db $A2                  ; @hook module=Cutscene name=Storybook_AttractCGADSUB kind=data

assert read4($0CF7E6) == $948509A9, "Attract_BuildBackgrounds signature moved"
org $0CF7E6
  JSL Storybook_Init                  ; @hook module=Cutscene name=Storybook_Init kind=jsl target=Storybook_Init expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8
  RTS

assert read4($0CEEDA) == $00893D22, "Attract_FadeOutSequence.advance EnableForceBlank moved"
org $0CEEDA
  JSL Storybook_CleanupAndBlank       ; @hook module=Cutscene name=Storybook_CleanupFadeOut kind=jsl target=Storybook_CleanupAndBlank expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8

assert read4($0CF704) == $00893D22, "Attract_SkipToFileSelect EnableForceBlank moved"
org $0CF704
  JSL Storybook_CleanupAndBlank       ; @hook module=Cutscene name=Storybook_CleanupStartSkip kind=jsl target=Storybook_CleanupAndBlank expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8

assert read4($0CF12C) == $EE0124EE && read2($0CF130) == $0120, "AttractDramatize_PolkaDots BG1 scroll moved"
org $0CF12C
  NOP #6                              ; @hook module=Cutscene name=Storybook_DisableBG1Scroll kind=patch

assert read3($0CF13C) == $F73E20, "AttractDramatize_PolkaDots BuildNextImageTilemap moved"
org $0CF13C
  NOP #3                              ; @hook module=Cutscene name=Storybook_SkipPolkaTilemap kind=patch

assert read4($0CF14B) == $0EC44022, "AttractDramatize_PolkaDots RenderText JSL moved"
org $0CF14B
  JSL Storybook_RenderText            ; @hook module=Cutscene name=Storybook_RenderText kind=jsl target=Storybook_RenderText expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8

assert read4($0ECD04) == $00EB5E22, "RenderText_NextImage PaletteFilterHistory JSL moved"
org $0ECD04
  JSL Storybook_PaletteFilter         ; @hook module=Cutscene name=Storybook_PaletteFilter kind=jsl target=Storybook_PaletteFilter expected_m=8 expected_x=8 expected_exit_m=8 expected_exit_x=8

assert read2($008C7E) == $8CE3, "NMI_DoUpdates vector 0 (NMI_NoTileUpdates) moved"
assert read4($00E852) == $FFFFFFFF && read2($00E856) == $FFFF, "NULL_00E852 free space occupied"
org $008C7E
  dw Storybook_NmiStub                ; @hook module=Cutscene name=Storybook_NmiNoTileVec kind=data
org $00E852
Storybook_NmiStub:                    ; @hook module=Cutscene name=Storybook_NmiStub kind=patch
  JSL Storybook_NmiStream
  RTS

; ----------------------------------------------------------------------------
; Bank $56 payload: compiled LZ2 panel assets + Scene 0 engine
; ----------------------------------------------------------------------------
org $568000

incsrc "Core/Cutscene/storybook/storybook_data.asm"

; ----------------------------------------------------------------------------
; Storybook_Init ($0CF7E6 -> JSL Storybook_Init : RTS)
; Entered under force blank ($80) from Attract_Initialize ($0CEE4F), M=8, X=8.
; ----------------------------------------------------------------------------
Storybook_Init:
{
  PHB : PHP
  SEP #$20 : REP #$10
  LDA.b #$00 : PHA : PLB              ; DBR = $00 for WRAM mirrors & PPU/DMA regs

  ; Initialize Scene 0 state cleanly
  LDA.b #!Storybook_ActiveMarker : STA.l !Storybook_Active
  LDA.b #$00
  STA.l !Storybook_State
  STA.l !Storybook_Panel
  STA.l !Storybook_Pending
  STA.l !Storybook_HooksDone
  REP #$20
  LDA.w #$0000
  STA.l !Storybook_ChunkOff
  STA.l !Storybook_ChrTotal

  ; Vanilla PPU setup ($94/$1C/$1D) plus Storybook Mode 1 VRAM layout
  SEP #$20
  LDA.b #$09 : STA.b $94              ; Mode 1, BG3 priority
  LDA.b #$17 : STA.b $1C              ; Main: BG1 + BG2 + BG3 + OBJ
  STZ.b $1D                           ; Sub: none

  LDA.b #$1C : STA.w $2107            ; BG1SC: $1C00..$1FFF (32x32 panel map)
  LDA.b #$68 : STA.w $2108            ; BG2SC: $6800..$6BFF (32x32 weave map)
  LDA.b #$60 : STA.w $2109            ; BG3SC: $6000..$63FF (32x32 VWF box)
  LDA.b #$20 : STA.w $210B            ; BG12NBA: BG1=$0000, BG2=$2000

  REP #$20
  STZ.w $0120                         ; BG1HOFS = 0
  LDA.w #$FFFB : STA.w $0124          ; BG1VOFS = -5 -> row 2 (bgY=16) at screen Y=20
  STZ.w $011E                         ; BG2HOFS = 0
  STZ.w $0122                         ; BG2VOFS = 0

  ; Build 32x32 BG2 2x2 weave tilemap ($09A1/$09A2 even rows, $09A3/$09A4 odd) in MapBuf
  LDX.w #$0000
.weave_loop:
  TXA : AND.w #$0040 : BNE .weave_odd
  LDA.w #$09A1 : STA.l !Storybook_MapBuf,X
  LDA.w #$09A2 : STA.l !Storybook_MapBuf+2,X
  BRA .weave_next
.weave_odd:
  LDA.w #$09A3 : STA.l !Storybook_MapBuf,X
  LDA.w #$09A4 : STA.l !Storybook_MapBuf+2,X
.weave_next:
  INX #4
  CPX.w #$0800 : BNE .weave_loop

  ; DMA weave tilemap to VRAM $6800 while still under force blank
  LDX.w #$6800
  LDY.w #!Storybook_MapBuf&$FFFF
  LDA.w #$0800
  JSR Storybook_DmaVram7F

  ; Decompress Panel 0 CHR + Map to WRAM and DMA both to VRAM $0000 / $1C00
  SEP #$20
  LDA.b #$00
  JSR Storybook_LoadWram

  REP #$20
  LDX.w #$0000
  LDY.w #!Storybook_ChrBuf&$FFFF
  LDA.l !Storybook_ChrTotal
  JSR Storybook_DmaVram7F

  LDX.w #$1C00
  LDY.w #!Storybook_MapBuf&$FFFF
  LDA.w #$0800
  JSR Storybook_DmaVram7F

  ; Install Panel 0 Row-6 target colors and black live palette for off=8 fade-in
  SEP #$20
  LDA.b #$00
  JSR Storybook_InstallPanelPal_BlackLive

  REP #$20
  LDA.w #$0000 : STA.l $7EC007
  LDA.w #$0002 : STA.l $7EC009        ; fade-in direction
  SEP #$20
  INC.b $15                           ; upload palettes next NMI

  PLP : PLB
  RTL
}

; ----------------------------------------------------------------------------
; Storybook_CleanupAndBlank
; Hooked at $0CEEDA (fade out -> Scene 1) and $0CF704 (Start-skip -> File Select).
; Restores vanilla BG12NBA/BG1SC/BG2SC/BG3SC and clears Storybook state cleanly.
; ----------------------------------------------------------------------------
Storybook_CleanupAndBlank:
{
  PHP
  SEP #$20
  LDA.b #$00
  STA.l !Storybook_Active
  STA.l !Storybook_State
  STA.l !Storybook_Pending
  PLP

  JSL $00893D                         ; EnableForceBlank (returns SEP #$30)

  PHB : PHP
  SEP #$20
  LDA.b #$00 : PHA : PLB
  LDA.b #$22 : STA.w $210B            ; Restore BG12NBA = $22 (required by FileSelect)
  LDA.b #$13 : STA.w $2107            ; Restore BG1SC = $13
  LDA.b #$03 : STA.w $2108            ; Restore BG2SC = $03
  LDA.b #$63 : STA.w $2109            ; Restore BG3SC = $63
  REP #$20
  STZ.w $0120 : STZ.w $0124
  STZ.w $011E : STZ.w $0122
  PLP : PLB
  RTL
}

; ----------------------------------------------------------------------------
; Storybook_RenderText ($0CF14B -> JSL Storybook_RenderText)
; Drives virtual [IMG][IMG] swaps at Page 1->2 ($0060) and Page 3->4 ($00FB),
; otherwise runs vanilla RenderText ($0EC440). Enters/exits M=8, X=8.
; ----------------------------------------------------------------------------
Storybook_RenderText:
{
  LDA.l !Storybook_Active
  CMP.b #!Storybook_ActiveMarker
  BEQ .active
  JML $0EC440                         ; RenderText

.active:
  LDA.l !Storybook_State
  BEQ .not_streaming
  CMP.b #$02
  BEQ .wait_nmi_stream

  ; State == 3: NMI stream completed while RenderText was held (keeps $17==0).
  JSL Storybook_PaletteFilter         ; clears State=0, $7EC007=0, $7EC009=2
  LDA.l !Storybook_Pending
  BNE .promote_pending
  ; Came from $67 fade-out ($00A9): step past first $67 onto second $67 ($00AA).
  REP #$20
  INC.w $1CD9
  SEP #$30
  RTL

.promote_pending:
  LDA.b #$02 : STA.l !Storybook_Pending
  JSL Storybook_PaletteFilter         ; begin fade-in step 0 immediately
.wait_nmi_stream:
  SEP #$30
  RTL

.not_streaming:
  LDA.l !Storybook_Pending
  BEQ .check_hooks

  ; Virtual transition in progress: step fade and stall RenderText.
  CMP.b #$01
  BNE .pending_fadein
  JSL Storybook_PaletteFilter
  SEP #$30
  RTL

.pending_fadein:
  JSL Storybook_PaletteFilter
  LDA.l $7EC007
  BNE .wait_nmi_stream
  LDA.b #$00 : STA.l !Storybook_Pending
  SEP #$30
  RTL

.check_hooks:
  ; Only fire when text renderer is mid-stream drawing Message_1C0 characters.
  LDA.w $1CD8 : CMP.b #$01 : BNE .run_vanilla
  LDA.w $1CD4 : CMP.b #$03 : BNE .run_vanilla

  REP #$20
  LDA.w $1CD9
  CMP.w #$0060 : BEQ .try_hook0
  CMP.w #$00FB : BEQ .try_hook1
  SEP #$20
.run_vanilla:
  JML $0EC440                         ; RenderText

.try_hook0:
  SEP #$20
  LDA.l !Storybook_HooksDone
  BIT.b #$01 : BNE .run_vanilla
  ORA.b #$01 : STA.l !Storybook_HooksDone
  BRA .start_virtual_swap

.try_hook1:
  SEP #$20
  LDA.l !Storybook_HooksDone
  BIT.b #$02 : BNE .run_vanilla
  ORA.b #$02 : STA.l !Storybook_HooksDone

.start_virtual_swap:
  LDA.b #$01 : STA.l !Storybook_Pending
  REP #$20
  LDA.w #$0000
  STA.l $7EC007
  STA.l $7EC009                       ; fade-out direction
  SEP #$20
  JSL Storybook_PaletteFilter         ; step 0 of fade-out
  SEP #$30
  RTL
}

; ----------------------------------------------------------------------------
; Storybook_PaletteFilter ($0ECD04 -> JSL Storybook_PaletteFilter)
; Replaces PaletteFilterHistory during Scene 0: drives 31-step Row-6 fade and
; triggers next-panel WRAM decompression + 5-VBlank DMA stream.
; ----------------------------------------------------------------------------
Storybook_PaletteFilter:
{
  LDA.l !Storybook_Active
  CMP.b #!Storybook_ActiveMarker
  BEQ .active
  JML $00EB5E                         ; PaletteFilterHistory

.active:
  PHB : PHP
  SEP #$20 : REP #$10
  LDA.b #$00 : PHA : PLB

  LDA.l !Storybook_State
  BEQ .do_fade
  CMP.b #$02
  BEQ .wait_stream

  ; State == 3: NMI stream completed; release $7EC007 so caller moves to fade-in.
  LDA.b #$00 : STA.l !Storybook_State
  REP #$20
  LDA.w #$0000 : STA.l $7EC007
  LDA.w #$0002 : STA.l $7EC009
  BRA .exit

.wait_stream:
  LDA.b #$01 : STA.l $7EC007          ; keep RenderText_NextImage paused
  BRA .exit

.do_fade:
  ; Determine brightness level (0..31) from $7EC007 (0..30) & $7EC009 (0=out, 2=in)
  REP #$30
  LDA.l $7EC009
  BNE .calc_in_lvl
  LDA.w #30
  SEC : SBC.l $7EC007                 ; fade-out: 30 down to 0
  BRA .apply_lvl
.calc_in_lvl:
  LDA.l $7EC007
  INC A                               ; fade-in: 1 up to 31

.apply_lvl:
  JSR Storybook_ApplyRow6Level

  LDA.l $7EC007
  INC A
  STA.l $7EC007
  CMP.w #$001F
  BCC .more_steps

  ; Completed 31st fade step ($7EC007 reached 31)
  LDA.l $7EC009
  BNE .fadein_done

  ; Fade-out reached pure black ($0000): advance panel, decompress, start NMI stream
  SEP #$20
  LDA.l !Storybook_Panel
  INC A
  AND.b #$03
  STA.l !Storybook_Panel
  JSR Storybook_LoadWram
  REP #$20
  LDA.w #$0000 : STA.l !Storybook_ChunkOff
  LDA.w #$0002 : STA.l $7EC009        ; next phase is fade-in
  LDA.w #$0001 : STA.l $7EC007        ; hold RenderText while State=2 streams
  SEP #$20
  LDA.b #$02 : STA.l !Storybook_State
  BRA .exit

.fadein_done:
  LDA.w #$0000
  STA.l $7EC007
  STA.l $7EC009                       ; next phase is fade-out

.more_steps:
  SEP #$20
.exit:
  INC.b $15                           ; upload Row-6 CGRAM on next NMI
  PLP : PLB
  RTL
}

; ----------------------------------------------------------------------------
; Storybook_NmiStream ($008C7E -> $00E852 -> JSL Storybook_NmiStream)
; Runs inside NMI_DoUpdates when $17==0 (M=8, X=8). Streams <=$0A00 B/VBlank.
; ----------------------------------------------------------------------------
Storybook_NmiStream:
{
  LDA.l !Storybook_Active
  CMP.b #!Storybook_ActiveMarker
  BNE .fast_exit
  LDA.l !Storybook_State
  CMP.b #$02
  BNE .fast_exit

  PHB : PHP
  SEP #$20 : REP #$10
  LDA.b #$00 : PHA : PLB

  REP #$20
  LDA.l !Storybook_ChunkOff
  CMP.l !Storybook_ChrTotal
  BCS .final_map

  ; size = min($0A00, ChrTotal - ChunkOff)
  LDA.l !Storybook_ChrTotal
  SEC : SBC.l !Storybook_ChunkOff
  CMP.w #!Storybook_ChunkBytes : BCC +
  LDA.w #!Storybook_ChunkBytes
+ PHA                                 ; save bytes transferred this VBlank

  LDA.l !Storybook_ChunkOff
  LSR A                               ; VRAM word addr = byte offset / 2
  TAX
  LDA.l !Storybook_ChunkOff
  CLC : ADC.w #!Storybook_ChrBuf&$FFFF
  TAY
  LDA 1,S                             ; peek size without popping yet
  JSR Storybook_DmaVram7F

  PLA
  CLC : ADC.l !Storybook_ChunkOff
  STA.l !Storybook_ChunkOff
  BRA .done

.final_map:
  LDX.w #$1C00
  LDY.w #!Storybook_MapBuf&$FFFF
  LDA.w #$0800
  JSR Storybook_DmaVram7F

  SEP #$20
  LDA.l !Storybook_Panel
  JSR Storybook_InstallPanelPal_BlackLive
  LDA.b #$03 : STA.l !Storybook_State

.done:
  PLP : PLB
.fast_exit:
  RTL
}

; ----------------------------------------------------------------------------
; Helpers (all internal JSR in Bank $56; DBR assumed $00 where indicated)
; ----------------------------------------------------------------------------

; Storybook_DmaVram7F: M=16, X=16, DBR=$00.
; In: A=size_bytes, X=vram_word, Y=wram_addr16 (bank $7F). Preserves P width=16/16.
Storybook_DmaVram7F:
{
  STX.w $2116                         ; VMADDR
  STY.w $4302                         ; DMA0ADDRL
  STA.w $4305                         ; DMA0SIZE
  LDA.w #$1801 : STA.w $4300          ; DMA0MODE ($01) + DMA0PORT ($18 -> $2118)
  SEP #$20
  LDA.b #$80 : STA.w $2115            ; VMAIN word increment
  LDA.b #$7F : STA.w $4304            ; DMA0ADDRB ($7F)
  LDA.b #$01 : STA.w $420B            ; MDMAEN ch0
  REP #$20
  RTS
}

; Storybook_InstallPanelPal_BlackLive: M=8 on entry; writes 16 target colors
; for panel in A (0..3) to $7EC3C0..$7EC3DE and zeroes $7EC5C0..$7EC5DE.
Storybook_InstallPanelPal_BlackLive:
{
  PHB : PHP
  REP #$30
  AND.w #$0003
  ASL #5                              ; panel * 32
  TAX
  SEP #$20
  LDA.b #$7E : PHA : PLB              ; DBR = $7E so $C3C0,Y / $C5C0,Y hit WRAM palettes
  REP #$20
  LDY.w #$0000
.loop:
  LDA.l Storybook_Palettes,X
  STA.w $C3C0,Y
  LDA.w #$0000
  STA.w $C5C0,Y
  INX #2
  INY #2
  CPY.w #$0020 : BNE .loop
  PLP : PLB
  RTS
}

; Storybook_ApplyRow6Level: M=16, X=16; A = brightness level 0..31.
; Scales all 15 non-transparent colors from $7EC3C2..$7EC3DE into $7EC5C2..$7EC5DE.
; Uses DP $00..$09 saved/restored cleanly on stack.
Storybook_ApplyRow6Level:
{
  PHA                                 ; push level
  LDA.b $00 : PHA : LDA.b $02 : PHA
  LDA.b $04 : PHA : LDA.b $06 : PHA
  LDA.b $08 : PHA

  LDA 11,S                            ; level (0..31)
  STA.b $00
  LDA.w #$0000
  STA.l $7EC5C0                       ; color 0 stays transparent $0000

  LDX.w #$0002
.color_loop:
  LDA.l $7EC3C0,X
  STA.b $06                           ; target BGR555 word

  ; Red (bits 0..4)
  AND.w #$001F
  JSR Storybook_ScaleChan5
  STA.b $08

  ; Green (bits 5..9)
  LDA.b $06
  AND.w #$03E0
  LSR #5
  JSR Storybook_ScaleChan5
  ASL #5
  ORA.b $08
  STA.b $08

  ; Blue (bits 10..14)
  LDA.b $06
  AND.w #$7C00
  XBA
  LSR #2
  JSR Storybook_ScaleChan5
  ASL #2
  XBA
  ORA.b $08
  STA.l $7EC5C0,X

  INX #2
  CPX.w #$0020 : BNE .color_loop

  PLA : STA.b $08
  PLA : STA.b $06 : PLA : STA.b $04
  PLA : STA.b $02 : PLA : STA.b $00
  PLA                                 ; pop level
  RTS
}

; Storybook_ScaleChan5: M=16, X=16. In: A = 5-bit val (0..31), $00 = level (0..31).
; Out: A = (val*level + (val*level >> 5) + 15) >> 5, preserving X.
Storybook_ScaleChan5:
{
  STZ.b $02                           ; product accumulator
  STA.b $04                           ; shifted multiplicand
  LDA.b $00                           ; 5-bit multiplier
  LDY.w #$0005
.mul_loop:
  LSR A
  BCC .no_add
  PHA
  LDA.b $02 : CLC : ADC.b $04 : STA.b $02
  PLA
.no_add:
  ASL.b $04
  DEY
  BNE .mul_loop

  LDA.b $02
  LSR #5
  CLC : ADC.b $02
  ADC.w #15
  LSR #5
  RTS
}

; Storybook_LoadWram: M=8 on entry; A = panel index (0..3).
; Decompresses CHR -> !Storybook_ChrBuf, Map -> !Storybook_MapBuf, sets ChrTotal.
; Saves/restores DP $00..$0B cleanly on stack.
Storybook_LoadWram:
{
  PHP
  AND.b #$03
  REP #$30
  AND.w #$0003
  PHA                                 ; push panel (0..3)

  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $04 : PHA
  LDA.b $06 : PHA : LDA.b $08 : PHA : LDA.b $0A : PHA

  LDA 13,S                            ; panel (0..3)
  ASL A : TAX
  LDA.l Storybook_ChrSizes,X
  STA.l !Storybook_ChrTotal

  TXA : CLC : ADC 13,S : TAX          ; X = panel * 3

  ; Decompress CHR -> !Storybook_ChrBuf
  LDA.l Storybook_ChrPointers+0,X : STA.b $00
  SEP #$20
  LDA.l Storybook_ChrPointers+2,X : STA.b $02
  LDA.b #!Storybook_ChrBuf>>16 : STA.b $05
  REP #$20
  LDA.w #!Storybook_ChrBuf&$FFFF : STA.b $03
  PHX
  JSR Storybook_Decompress
  PLX

  ; Decompress Map -> !Storybook_MapBuf (M=16 on entry here? force REP #$20)
  REP #$20
  LDA.l Storybook_MapPointers+0,X : STA.b $00
  SEP #$20
  LDA.l Storybook_MapPointers+2,X : STA.b $02
  LDA.b #!Storybook_MapBuf>>16 : STA.b $05
  REP #$20
  LDA.w #!Storybook_MapBuf&$FFFF : STA.b $03
  JSR Storybook_Decompress

  REP #$20
  PLA : STA.b $0A : PLA : STA.b $08 : PLA : STA.b $06
  PLA : STA.b $04 : PLA : STA.b $02 : PLA : STA.b $00
  PLA                                 ; pop panel
  PLP
  RTS
}

; Storybook_Decompress: ALTTP LC-LZ2 codec matching Scripts/Generate/lz2.py.
; In: DP $00..$02 = source ROM pointer, DP $03..$05 = dest WRAM pointer ($7F).
Storybook_Decompress:
{
  SEP #$20 : REP #$10
  LDA.b $05 : STA.b $08               ; copy-backref bank ($7F)
  LDY.w #$0000                        ; output byte offset

.next_cmd:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  CMP.b #$FF : BNE +
  JMP .done
+ CMP.b #$E0 : BCS .extended_hdr

  PHA
  AND.b #$1F
  INC A
  REP #$20
  AND.w #$00FF
  TAX
  SEP #$20
  PLA
  LSR #5
  BRA .dispatch

.extended_hdr:
  PHA
  AND.b #$03
  STA.b $0A
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b $09
  REP #$20
  LDA.b $09
  AND.w #$03FF
  INC A
  TAX
  SEP #$20
  PLA
  LSR #2
  AND.b #$07

.dispatch:
  BEQ .cmd0_direct
  DEC A : BEQ .cmd1_bytefill
  DEC A : BEQ .cmd2_wordfill
  DEC A : BEQ .cmd3_incfill
  DEC A : BEQ .cmd4_copy
  JMP .done

.cmd0_direct:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b [$03],Y
  INY
  DEX
  BNE .cmd0_direct
  JMP .next_cmd

.cmd1_bytefill:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
- STA.b [$03],Y
  INY
  DEX
  BNE -
  JMP .next_cmd

.cmd2_wordfill:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b $0A
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b $0B
- LDA.b $0A
  STA.b [$03],Y
  INY
  DEX
  BNE +
  JMP .next_cmd
+ LDA.b $0B
  STA.b [$03],Y
  INY
  DEX
  BNE -
  JMP .next_cmd

.cmd3_incfill:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
- STA.b [$03],Y
  INY
  INC A
  DEX
  BNE -
  JMP .next_cmd

.cmd4_copy:
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b $09
  LDA.b [$00]
  INC.b $00 : BNE + : INC.b $01 : +
  STA.b $0A
  REP #$20
  LDA.b $09
  CLC : ADC.b $03
  STA.b $06
  SEP #$20
- LDA.b [$06]
  STA.b [$03],Y
  INY
  INC.b $06 : BNE + : INC.b $07 : +
  DEX
  BNE -
  JMP .next_cmd

.done:
  RTS
}

assert pc() <= $570000

pullpc
