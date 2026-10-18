; Time-note positions belong to uploaded BG3 halves, not the current menu page.
; Included in bank $2E. The caller owns ROM placement and the two JSL hooks.
; TrackLong runs after each Menu_Entry dispatch, before the OBJ lease/render.
; PatchVramNmiLong runs after native NMI DMA, after overlay glyphs are ready.
;
; Shared volatile WRAM. Renderer indexes each word array with X=0 (left) or2
; (right), then publishes Active=1 only after drawing with a valid OBJ lease.
; Screen coordinates are nine-bit signed/wrapped values; OAM uses X's ninth
; bit and Y's low byte. Offsets are byte offsets within a $0800-byte map.
MenuTimeNote_Initialized = $7F5700
MenuTimeNote_Offsets     = $7F5702 ; word[2], $FFFF means no Time note
MenuTimeNote_ScreenX     = $7F5706 ; word[2], -15..255 encoded in nine bits
MenuTimeNote_ScreenY     = $7F570A ; word[2], -15..223 encoded in nine bits
MenuTimeNote_Visible     = $7F570E ; word[2], intersects the 256x224 screen
MenuTimeNote_Active      = $7F5712 ; word[2], written by the OBJ renderer
assert MenuTimeNote_Active+4 <= $7F5720, "Time note tracking overlaps OBJ lease state"

MenuTimeNote_CodeStart:

; Any input widths/DBR/DP; preserves A/X/Y/P/DBR. No scratch direct-page RAM.
MenuTimeNote_TrackLong:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  SEP #$20
  LDA.l $7E0010 : CMP.b #$0E : BEQ .interface
  JMP .leave_menu
.interface
  LDA.l $7E0011 : CMP.b #$01 : BEQ .item_menu
  JMP .leave_menu
.item_menu
  ; State0 has become state1 after Menu_InitGraphics. Reset before an old
  ; upload flag or saved RAM can be mistaken for this opening's map contents.
  LDA.l $7E0200 : CMP.b #$02 : BCS .after_init
  REP #$30
  JSR .clear
  LDA.w #$0001 : STA.l MenuTimeNote_Initialized
  JMP .done
.after_init
  REP #$30
  LDA.l MenuTimeNote_Initialized : CMP.w #$0001 : BEQ .initialized
  JSR .clear
  LDA.w #$0001 : STA.l MenuTimeNote_Initialized
.initialized
  LDA.w #$0000
  STA.l MenuTimeNote_Active : STA.l MenuTimeNote_Active+2
  STA.l MenuTimeNote_Visible : STA.l MenuTimeNote_Visible+2

  ; Only actual full-map uploads replace a bottom half's metadata. Transfer24
  ; writes the closing HUD to the upper-right map and leaves both halves intact.
  LDA.l $7E0017 : AND.w #$00FF : BEQ .positions
  LDA.l $7E0116 : AND.w #$00FF
  CMP.w #$0022 : BEQ .upload_left
  CMP.w #$0023 : BEQ .upload_right
  BRA .positions
.upload_left
  LDY.w #$0000 : BRA .scan_start
.upload_right
  LDY.w #$0002
.scan_start
  LDX.w #$0000
.scan
  ; Unique marker: palette6 note art. Require the complete 2x2 pattern so a
  ; frame word or ordinary Secrets note cannot create an overlay accidentally.
  LDA.l $7E1000,X : CMP.w #$38AA : BNE .scan_next
  TXA : AND.w #$003E : CMP.w #$003E : BEQ .scan_next
  LDA.l $7E1002,X : CMP.w #$386B : BNE .scan_next
  LDA.l $7E1040,X : CMP.w #$387A : BNE .scan_next
  LDA.l $7E1042,X : CMP.w #$386A : BNE .scan_next
  TXA : BRA .store_offset
.scan_next
  INX #2
  CPX.w #$07BE : BCC .scan             ; last valid top-left is $07BC
  LDA.w #$FFFF
.store_offset
  CPY.w #$0000 : BNE .store_right
  STA.l MenuTimeNote_Offsets : BRA .positions
.store_right
  STA.l MenuTimeNote_Offsets+2

.positions
  LDX.w #$0000
.half
  LDA.l MenuTimeNote_Offsets,X : CMP.w #$FFFF : BEQ .next_half
  ; BG3 is a64x64 map. Both menu halves are the lower row of screens.
  AND.w #$003E : ASL #2                 ; column *8
  CPX.w #$0000 : BEQ .left_x
  CLC : ADC.w #$0100
.left_x
  SEC : SBC.l $7E00E4 : AND.w #$01FF
  STA.l MenuTimeNote_ScreenX,X
  CMP.w #$0100 : BCC .x_visible
  CMP.w #$01F1 : BCC .next_half        ; allow left-edge overlap down to -15
.x_visible
  LDA.l MenuTimeNote_Offsets,X : AND.w #$07C0 : LSR #3 ; row *8
  CLC : ADC.w #$0100
  SEC : SBC.l $7E00EA : DEC : AND.w #$01FF
  STA.l MenuTimeNote_ScreenY,X         ; OAM appears one scanline after its Y
  CMP.w #$00E0 : BCC .visible
  CMP.w #$01F1 : BCC .next_half        ; allow top-edge overlap down to -15
.visible
  LDA.w #$0001 : STA.l MenuTimeNote_Visible,X
.next_half
  INX #2 : CPX.w #$0004 : BCC .half
  BRA .done

.leave_menu
  REP #$30
  JSR .clear
.done
  REP #$30
  PLY : PLX : PLA
  PLP
  RTL

; Internal, M/X=16. Invalidating both halves also releases active requests.
.clear
  LDA.w #$0000
  STA.l MenuTimeNote_Initialized
  STA.l MenuTimeNote_ScreenX : STA.l MenuTimeNote_ScreenX+2
  STA.l MenuTimeNote_ScreenY : STA.l MenuTimeNote_ScreenY+2
  STA.l MenuTimeNote_Visible : STA.l MenuTimeNote_Visible+2
  STA.l MenuTimeNote_Active : STA.l MenuTimeNote_Active+2
  LDA.w #$FFFF
  STA.l MenuTimeNote_Offsets : STA.l MenuTimeNote_Offsets+2
  RTS
}

; Any input widths/DBR/DP; preserves A/X/Y/P/DBR. VBlank-only, after all native
; map DMA. Leaves VMAIN=$80 and VMADDR past the last patched pair. No DMA use.
; An unavailable OBJ lease displays ordinary blue note art, never a missing
; icon or palette6 frame colors. Glyphs$180..183 are the separately uploaded
; high-priority BG3 black/white mask with transparent foreground pixels.
MenuTimeNote_PatchVramNmiLong:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  PHB
  SEP #$20
  LDA.b #$00 : PHA : PLB               ; hardware registers in bank00
  LDA.l $7E0010 : CMP.b #$0E : BEQ .interface
  JMP .done
.interface
  LDA.l $7E0011 : CMP.b #$01 : BEQ .item_menu
  JMP .done
.item_menu
  REP #$30
  LDA.l MenuTimeNote_Initialized : CMP.w #$0001 : BEQ .initialized
  JMP .done
.initialized
  LDX.w #$0000
.half
  LDA.l MenuTimeNote_Offsets,X : CMP.w #$07BD : BCC .offset_valid
  JMP .next_half                      ; includes $FFFF/uninitialized offsets
.offset_valid
  AND.w #$0001 : BEQ .aligned
  JMP .next_half
.aligned
  LDA.l MenuTimeNote_Offsets,X : AND.w #$003E : CMP.w #$003E : BNE .column_valid
  JMP .next_half
.column_valid
  LDA.l MenuTimeNote_Offsets,X : LSR
  CPX.w #$0000 : BNE .right
  CLC : ADC.w #$6800 : BRA .address
.right
  CLC : ADC.w #$6C00
.address
  TAY
  SEP #$20
  LDA.b #$80 : STA.w $2115
  REP #$20
  LDA.l MenuTimeNote_Active,X : CMP.w #$0001 : BNE .fallback
  LDA.l MenuTimeNote_Visible,X : CMP.w #$0001 : BNE .fallback
  STY.w $2116
  LDA.w #$2D80 : STA.w $2118
  LDA.w #$2D81 : STA.w $2118
  TYA : CLC : ADC.w #$0020 : STA.w $2116
  LDA.w #$2D82 : STA.w $2118
  LDA.w #$2D83 : STA.w $2118
  BRA .next_half
.fallback
  STY.w $2116
  LDA.w #$2CAA : STA.w $2118
  LDA.w #$2C6B : STA.w $2118
  TYA : CLC : ADC.w #$0020 : STA.w $2116
  LDA.w #$2C7A : STA.w $2118
  LDA.w #$2C6A : STA.w $2118
.next_half
  INX #2 : CPX.w #$0004 : BCS .done
  JMP .half
.done
  REP #$30
  PLB
  PLY : PLX : PLA
  PLP
  RTL
}

assert (MenuTimeNote_CodeStart>>16) == ((pc()-1)>>16), "Time note tracking crossed its code bank"
assert pc()-MenuTimeNote_CodeStart <= $0800, "Time note tracking exceeded its bounded allocation"
