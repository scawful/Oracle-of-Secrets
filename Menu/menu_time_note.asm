; One-color OBJ mask for Time's purple note. All existing BG3 palette entries
; remain unchanged: the BG3 holes glyph retains the original white and black.
; Called after the final menu/world OAM pass, before NMI_PrepareSprites packs
; $0A20. No native allocator is used: it can wrap into occupied OAM regions.
;
; WRAM $7F5700..5715 is owned by menu_time_note_tracking.asm. This module owns
; $7F5720..57FF only; $5780..57FF backs up the borrowed 16x16 OBJ pixels.
; Prepare and both NMI entry points preserve P/A/X/Y/DBR and do not use DP.
;
; NMI order is mandatory:
;   MenuTimeNote_NmiRestore -> native NMI_DoUpdates -> MenuTimeNote_Nmi
;   -> MenuTimeNote_PatchVramNmiLong.
; Restore happens BEFORE native DMA, so a dialogue transfer skipping sprite
; DMA cannot strand the mask, and new animation data is never overwritten by
; a previous frame's backup. The final upload happens AFTER native CGRAM DMA.

!MTN_MAGIC       = $5720
!MTN_USED        = $5722
!MTN_BLOCKED     = $5724
!MTN_WANTED      = $5726
!MTN_HIDDEN      = $5728
!MTN_OAM         = $572A
!MTN_TILE        = $572C
!MTN_PROP_BIT    = $572E
!MTN_CHOSEN_TILE = $5730
!MTN_CHOSEN_PAL  = $5732
!MTN_POSITION    = $5734
!MTN_EXT         = $5736
!MTN_ACTIVE      = $5738
!MTN_LEASE      = $573A
!MTN_LEASE_TILE = $573C
!MTN_LEASE_PAL  = $573E
; NMI-only workspace; Prepare never alters it.
!MTN_VRAM       = $5740
!MTN_SOURCE     = $5742
!MTN_BANK       = $5744
!MTN_LENGTH     = $5746
!MTN_NMI_TEMP   = $5748
!MTN_BACKUP     = $5780
MenuTimeNote_LeaseBackup = $7F5780
assert MenuTimeNote_LeaseBackup+$80 == $7F5800, "Time note lease exceeds reserved WRAM"

MenuTimeNote_Prepare:
{
  PHP
  REP #$30
  PHA : PHX : PHY : PHB
  SEP #$20
  LDA.b #$7F : PHA : PLB
  REP #$30
  LDA.w #$0000
  STA.l MenuTimeNote_Active : STA.l MenuTimeNote_Active+2
  STA.w !MTN_ACTIVE
  LDA.w !MTN_MAGIC : CMP.w #$4E54 : BEQ .initialized
  LDA.w #$4E54 : STA.w !MTN_MAGIC
  STZ.w !MTN_LEASE
.initialized
  ; A skipped native sprite upload cannot establish a fresh dynamic lease.
  LDA.l $7E0710 : AND.w #$00FF : BEQ .sprite_dma
  JMP .done
.sprite_dma
  LDA.l MenuTimeNote_Initialized : CMP.w #$0001 : BEQ .tracking
  JMP .done
.tracking
  LDA.l MenuTimeNote_Visible : CLC : ADC.l MenuTimeNote_Visible+2
  STA.w !MTN_WANTED : BNE .wanted
  JMP .done
.wanted
  CMP.w #$0003 : BCC .scan_start
  JMP .done
.scan_start
  STZ.w !MTN_USED : STZ.w !MTN_BLOCKED : STZ.w !MTN_HIDDEN
  STZ.w !MTN_OAM
.scan
  LDX.w !MTN_OAM
  LDA.l $7E0801,X : AND.w #$00FF : CMP.w #$00F0 : BNE .visible
  INC.w !MTN_HIDDEN
  JMP .next
.visible
  ; Name-table page 1 cannot reference the dynamic page-0 tile pool.
  LDA.l $7E0803,X : AND.w #$0001 : BEQ .page_zero
  JMP .next
.page_zero
  LDA.l $7E0803,X : AND.w #$000E : TAX
  LDA.l MenuTimeNote_Bits,X : STA.w !MTN_PROP_BIT
  LDX.w !MTN_OAM
  LDA.l $7E0802,X : AND.w #$00FF : STA.w !MTN_TILE
  JSR MenuTimeNote_MarkTile
  LDA.w !MTN_OAM : LSR #2 : TAX
  LDA.l $7E0A20,X : AND.w #$0002 : BEQ .next
  ; A 16x16 object names four 8x8 tiles. Conservatively include the ordinary
  ; +1 spelling as well as the hardware horizontal nibble wrap at column F.
  LDA.w !MTN_TILE : INC A : AND.w #$00FF
  JSR MenuTimeNote_MarkTile
  LDA.w !MTN_TILE : AND.w #$00F0 : STA.w !MTN_EXT
  LDA.w !MTN_TILE : INC A : AND.w #$000F : ORA.w !MTN_EXT
  JSR MenuTimeNote_MarkTile
  LDA.w !MTN_TILE : CLC : ADC.w #$0010 : AND.w #$00FF
  JSR MenuTimeNote_MarkTile
  LDA.w !MTN_TILE : CLC : ADC.w #$0011 : AND.w #$00FF
  JSR MenuTimeNote_MarkTile
  LDA.w !MTN_TILE : CLC : ADC.w #$0010 : AND.w #$00F0
  STA.w !MTN_EXT
  LDA.w !MTN_TILE : INC A : AND.w #$000F : ORA.w !MTN_EXT
  JSR MenuTimeNote_MarkTile
.next
  LDA.w !MTN_OAM : CLC : ADC.w #$0004 : STA.w !MTN_OAM
  CMP.w #$0200 : BCS .resources
  JMP .scan
.resources
  LDA.w !MTN_HIDDEN : CMP.w !MTN_WANTED : BCS .find_tile
  JMP .done
.find_tile
  LDX.w #$0000
.tile_loop
  LDA.l MenuTimeNote_Bits,X : AND.w !MTN_USED : BEQ .tile_found
  INX #2 : CPX.w #$0010 : BCC .tile_loop
  JMP .done
.tile_found
  LDA.l MenuTimeNote_Tiles,X : STA.w !MTN_CHOSEN_TILE
  LDX.w #$0000
.palette_loop
  LDA.l MenuTimeNote_Palettes,X : PHA : PHX
  ASL : TAX
  LDA.l MenuTimeNote_Bits,X : AND.w !MTN_BLOCKED
  PLX : TAY : PLA
  CPY.w #$0000 : BNE .next_palette
  CMP.w #$0004 : BCC .palette_found
  ; OBJ palettes 4..7 participate in color math, unlike palettes 0..3.
  ; Do not let a dark room or translucent layer change the requested purple.
  PHA
  LDA.l $7E009A : AND.w #$0010
  TAY : PLA
  CPY.w #$0000 : BEQ .palette_found
.next_palette
  INX #2 : CPX.w #$000A : BCC .palette_loop
  JMP .done
.palette_found
  STA.w !MTN_CHOSEN_PAL
  STZ.w !MTN_POSITION
.draw_instance
  LDX.w !MTN_POSITION
  LDA.l MenuTimeNote_Visible,X : CMP.w #$0001 : BNE .next_instance
  JSR MenuTimeNote_InsertOam
  LDX.w !MTN_POSITION
  LDA.w #$0001 : STA.l MenuTimeNote_Active,X
  INC.w !MTN_ACTIVE
.next_instance
  INC.w !MTN_POSITION : INC.w !MTN_POSITION
  LDA.w !MTN_POSITION : CMP.w #$0004 : BCC .draw_instance
.done
  REP #$30
  PLB : PLY : PLX : PLA : PLP
  RTL
}

; A=page-0 8x8 tile; M/X16, DB7F. Marks each of the eight possible 2x2 leases.
; Native 3bpp conversion uses indices 0..7 or 0,9..15, never color8. Link/P2
; use palettes0/7, which are excluded. Bombchu's raw 4bpp uses color8 in tiles
; 2E/2F/3E/3F and may flash through any palette; all such footprints block
; that palette. This includes native sword tips sharing the same tile IDs.
MenuTimeNote_MarkTile:
{
  PHA
  AND.w #$00EE : CMP.w #$002E : BNE .ordinary
  LDA.w !MTN_BLOCKED : ORA.w !MTN_PROP_BIT : STA.w !MTN_BLOCKED
.ordinary
  PLA : PHA
  AND.w #$00E0 : BEQ .link_row
  CMP.w #$0020 : BEQ .follower_row
  PLA : RTS
.link_row
  PLA : AND.w #$000F : CMP.w #$0004 : BCC .done
  CMP.w #$000E : BCS .done
  SEC : SBC.w #$0004 : AND.w #$FFFE : TAX
  BRA .mark
.follower_row
  PLA : AND.w #$000F : CMP.w #$0006 : BCS .done
  AND.w #$FFFE : CLC : ADC.w #$000A : TAX
.mark
  LDA.l MenuTimeNote_Bits,X : ORA.w !MTN_USED : STA.w !MTN_USED
.done
  RTS
}

; Capacity was checked before any mutation. Find one hidden entry, then shift
; preceding entries upward. Insertion at index0 preserves ALL world OBJ order
; while giving the mask precedence over any object visible through BG3 holes.
MenuTimeNote_InsertOam:
{
  LDX.w #$0000
.find
  LDA.l $7E0801,X : AND.w #$00FF : CMP.w #$00F0 : BEQ .found
  INX #4 : BRA .find
.found
  CPX.w #$0000 : BEQ .write
.shift
  LDA.l $7E07FC,X : STA.l $7E0800,X
  LDA.l $7E07FE,X : STA.l $7E0802,X
  PHX : TXA : LSR #2 : TAX
  SEP #$20
  LDA.l $7E0A1F,X : STA.l $7E0A20,X
  REP #$30
  PLX : DEX #4 : BNE .shift
.write
  LDX.w !MTN_POSITION
  LDA.l MenuTimeNote_ScreenX,X
  XBA : AND.w #$0001 : ORA.w #$0002 : STA.w !MTN_EXT
  SEP #$20
  LDA.l MenuTimeNote_ScreenX,X : STA.l $7E0800
  LDA.l MenuTimeNote_ScreenY,X : STA.l $7E0801
  LDA.w !MTN_CHOSEN_TILE : STA.l $7E0802
  LDA.w !MTN_CHOSEN_PAL : ASL : ORA.b #$30 : STA.l $7E0803
  LDA.w !MTN_EXT : STA.l $7E0A20
  REP #$30
  RTS
}

MenuTimeNote_Bits:
  dw $0001,$0002,$0004,$0008,$0010,$0020,$0040,$0080
MenuTimeNote_Tiles:
  dw $0004,$0006,$0008,$000A,$000C,$0020,$0022,$0024
MenuTimeNote_Palettes:
  dw $0001,$0003,$0004,$0005,$0006

; Restore the preceding frame's lease before ALL native NMI updates. The
; backup is exact VRAM data, not a guessed Link/follower source pointer.
MenuTimeNote_NmiRestore:
{
  PHP
  REP #$30
  PHA : PHX : PHY : PHB
  SEP #$20
  LDA.b #$7F : PHA : PLB
  REP #$30
  LDA.w !MTN_MAGIC : CMP.w #$4E54 : BEQ .magic_ok
  JMP .done
.magic_ok
  LDA.w !MTN_LEASE : CMP.w #$D17A : BEQ .leased
  JMP .done
.leased
  ; Save all DMA0 registers touched by this module, including the adjacent
  ; indirect-bank byte, so the native routine sees its original context.
  LDA.l $004300 : PHA
  LDA.l $004302 : PHA
  LDA.l $004304 : PHA
  LDA.l $004306 : PHA
  LDA.w !MTN_LEASE_TILE : ASL #4 : CLC : ADC.w #$4000
  STA.w !MTN_VRAM
  LDA.w #!MTN_BACKUP : STA.w !MTN_SOURCE
  LDA.w #$007F : STA.w !MTN_BANK
  LDA.w #$0040 : STA.w !MTN_LENGTH
  JSR MenuTimeNote_DmaWrite
  LDA.w !MTN_VRAM : CLC : ADC.w #$0100 : STA.w !MTN_VRAM
  LDA.w !MTN_SOURCE : CLC : ADC.w #$0040 : STA.w !MTN_SOURCE
  JSR MenuTimeNote_DmaWrite
  ; $C500 is the native palette mirror. It is never modified by this lease.
  LDA.w !MTN_LEASE_PAL : ASL #4 : CLC : ADC.w #$0088
  PHA
  SEP #$20
  STA.l $002121
  REP #$20
  ASL : TAX
  LDA.l $7EC500,X
  SEP #$20
  STA.l $002122 : XBA : STA.l $002122
  REP #$20
  PLA
  STZ.w !MTN_LEASE
  PLA : STA.l $004306
  PLA : STA.l $004304
  PLA : STA.l $004302
  PLA : STA.l $004300
.done
  ; Native NMI_UploadTilemap writes VMADDH only and assumes VMADDL is zero.
  SEP #$20
  LDA.b #$00 : STA.l $002116
  REP #$30
  PLB : PLY : PLX : PLA : PLP
  RTL
}

; Runs after native sprite, HUD, and full-palette DMA. The caller then patches
; the two tracked BG3 notes to holes/fallback according to Active[].
MenuTimeNote_Nmi:
{
  PHP
  REP #$30
  PHA : PHX : PHY : PHB
  SEP #$20
  LDA.b #$7F : PHA : PLB
  REP #$30
  LDA.w !MTN_MAGIC : CMP.w #$4E54 : BEQ .magic_ok
  JMP .done
.magic_ok
  LDA.l $7E0010 : AND.w #$00FF : CMP.w #$000E : BEQ .interface
  JMP .done
.interface
  LDA.l $7E0011 : AND.w #$00FF : CMP.w #$0001 : BEQ .menu
  JMP .done
.menu
  LDA.l MenuTimeNote_Initialized : CMP.w #$0001 : BEQ .initialized
  JMP .done
.initialized
  LDA.w !MTN_ACTIVE : BNE .active
  JMP .done
.active
  LDA.l $004300 : PHA
  LDA.l $004302 : PHA
  LDA.l $004304 : PHA
  LDA.l $004306 : PHA
  LDA.w !MTN_CHOSEN_TILE : STA.w !MTN_LEASE_TILE
  ASL #4 : CLC : ADC.w #$4000 : STA.w !MTN_VRAM
  LDA.w #!MTN_BACKUP : STA.w !MTN_SOURCE
  LDA.w #$007F : STA.w !MTN_BANK
  LDA.w #$0040 : STA.w !MTN_LENGTH
  JSR MenuTimeNote_DmaRead
  LDA.w !MTN_VRAM : CLC : ADC.w #$0100 : STA.w !MTN_VRAM
  LDA.w !MTN_SOURCE : CLC : ADC.w #$0040 : STA.w !MTN_SOURCE
  JSR MenuTimeNote_DmaRead
  ; Top two 8x8 tiles, then bottom two one tile row ($100 words) below.
  LDA.w !MTN_LEASE_TILE : ASL #4 : CLC : ADC.w #$4000
  STA.w !MTN_VRAM
  LDA.w #MenuTimeNote_MaskGfx : STA.w !MTN_SOURCE
  LDA.w #MenuTimeNote_MaskGfx>>16 : STA.w !MTN_BANK
  JSR MenuTimeNote_DmaWrite
  LDA.w !MTN_VRAM : CLC : ADC.w #$0100 : STA.w !MTN_VRAM
  LDA.w #MenuTimeNote_MaskGfx+$40 : STA.w !MTN_SOURCE
  JSR MenuTimeNote_DmaWrite
  ; BG3 $180..$183 are unused by all menu maps/font. Native dialogue entry
  ; replaces this region from its own cleared VWF buffer after menu closure.
  LDA.w #$7C00 : STA.w !MTN_VRAM
  LDA.w #MenuTimeNote_HolesGfx : STA.w !MTN_SOURCE
  LDA.w #MenuTimeNote_HolesGfx>>16 : STA.w !MTN_BANK
  JSR MenuTimeNote_DmaWrite
  LDA.w !MTN_CHOSEN_PAL : STA.w !MTN_LEASE_PAL
  ASL #4 : CLC : ADC.w #$0088
  SEP #$20
  STA.l $002121
  LDA.b #$D5 : STA.l $002122
  LDA.b #$6D : STA.l $002122
  REP #$20
  LDA.w #$D17A : STA.w !MTN_LEASE
  PLA : STA.l $004306
  PLA : STA.l $004304
  PLA : STA.l $004302
  PLA : STA.l $004300
.done
  REP #$30
  PLB : PLY : PLX : PLA : PLP
  RTL
}

; M/X16, DB7F. Both helpers preserve these widths; A is scratch. VMAIN stays
; at the native NMI default $80. Caller saves/restores DMA0's registers.
MenuTimeNote_DmaWrite:
{
  SEP #$20
  LDA.b #$80 : STA.l $002115
  REP #$20
  LDA.w !MTN_VRAM : STA.l $002116
  LDA.w #$1801 : STA.l $004300
  LDA.w !MTN_SOURCE : STA.l $004302
  LDA.w !MTN_LENGTH : STA.l $004305
  SEP #$20
  LDA.w !MTN_BANK : STA.l $004304
  LDA.b #$01 : STA.l $00420B
  REP #$20
  RTS
}

MenuTimeNote_DmaRead:
{
  SEP #$20
  LDA.b #$80 : STA.l $002115
  REP #$20
  LDA.w !MTN_VRAM : STA.l $002116
  ; VRAM reads are buffered. Dummy low+high advances the address once while
  ; retaining the requested first word in the read buffer for reverse DMA.
  LDA.l $002139
  LDA.w #$3981 : STA.l $004300
  LDA.w !MTN_SOURCE : STA.l $004302
  LDA.w !MTN_LENGTH : STA.l $004305
  SEP #$20
  LDA.w !MTN_BANK : STA.l $004304
  LDA.b #$01 : STA.l $00420B
  REP #$20
  RTS
}

MenuTimeNote_MaskGfx:
  incbin "../Data/graphics/items/time_note_mask.4bpp"
MenuTimeNote_MaskGfxEnd:
assert MenuTimeNote_MaskGfxEnd-MenuTimeNote_MaskGfx == $0080, "Time note OBJ mask must be 128 bytes"
assert (MenuTimeNote_MaskGfx&$FFFF)+$0080 <= $10000, "Time note OBJ DMA crosses a bank"
MenuTimeNote_HolesGfx:
  incbin "../Data/graphics/items/time_note_holes.2bpp"
MenuTimeNote_HolesGfxEnd:
assert MenuTimeNote_HolesGfxEnd-MenuTimeNote_HolesGfx == $0040, "Time note BG3 holes must be 64 bytes"
assert (MenuTimeNote_HolesGfx&$FFFF)+$0040 <= $10000, "Time note BG3 DMA crosses a bank"
