; Early Mirror: real-dungeon return, and an entry-bound Abyss return until
; all three pendants unlock the existing two-way Mirror. The saved entry is
; the native $32-byte overworld exit-cache image, not a Portal Rod target.
!EarlyMirror_Magic = $4D01
!EarlyMirror_CacheRoom = $0152

pushpc

; LinkItem_Mirror: LDA $6C : BNE LinkGoBeep. Item-only: pads and sprite $6C
; enter Mirror_TryToWarp below this hook. M8/X8, DB=$07, DP=$0000.
assert read4($07A942) == $0FD06CA5, "Early Mirror item hook moved"
org $07A942 ; @hook module=Overworld name=EarlyMirror_ItemGate kind=jsl target=EarlyMirror_ItemGate expected_m=8 expected_x=8
  JSL EarlyMirror_ItemGate
assert pc() == $07A946

; MirrorWarp_Initialize: capture before the original saved-world toggle.
; InitializeMirrorHDMA does not clear the native warp-tile flag $0357.
assert read4($02B236) == $7EF3CAAF, "Early Mirror capture hook moved"
assert read2($02B23A) == $4049, "Early Mirror world toggle moved"
assert read4($02B23C) == $7EF3CA8F, "Early Mirror world store moved"
org $02B236 ; @hook module=Overworld name=EarlyMirror_CaptureEntry kind=jsl target=EarlyMirror_CaptureEntry expected_m=8 expected_x=8
  JSL EarlyMirror_CaptureEntry
  NOP #6
assert pc() == $02B240

; Sprite_6C_MirrorPortal: LDA #$23 : STA $11. Validate its independent
; activation path too; it does not call the item or fixed-pad gate.
assert read4($05AFC6) == $118523A9, "Early Mirror portal hook moved"
org $05AFC6 ; @hook module=Overworld name=EarlyMirror_PortalGate kind=jsl target=EarlyMirror_PortalGate expected_m=8 expected_x=8
  JSL EarlyMirror_PortalGate
assert pc() == $05AFCA

; Cached exits normally walk Link down before returning control. This
; synthetic cache room skips only that walk, retaining the exact entry XY.
assert read4($02AC8F) == $07E69D22, "Early Mirror cached-exit hook moved"
org $02AC8F ; @hook module=Overworld name=EarlyMirror_FinishReturn kind=jml target=EarlyMirror_FinishReturn expected_m=8 expected_x=8
  JML EarlyMirror_FinishReturn
assert pc() == $02AC93

; Current edit-base chest index 91: room $113, receipt $1A. Its old Mirror
; becomes the existing $41 fifty-rupee receipt; this patches output only.
assert read2($01EA7F) == $0113, "Grave Mirror chest room moved"
assert read1($01EA81) == $1A, "Grave Mirror chest receipt changed"
org $01EA81 ; @hook module=Overworld name=EarlyMirror_GraveRupees kind=data
  db $41
assert pc() == $01EA82

pullpc

; The actual intro escape is SwordWarp_Go's SavedWorld=$00 transition.
; Encounter + sword + Pearl qualify the old-save fallback, not GameState=2.
; Any M/X; preserve X/Y/DB and P except returned carry. A is scratch.
EarlyMirror_HasEscapedItems:
{
  PHP
  SEP #$20
  LDA.l StoryProgress2 : AND.b #!Story2_KydrogEncounter : BEQ .no
  LDA.l Sword : BEQ .no
  LDA.l MoonPearl : BEQ .no
  PLP
  SEC
  RTL
  .no
  PLP
  CLC
  RTL
}

; M8/X8. Original continuation overwrites A; keep X/Y/DB/DP unchanged.
; Nonreturning paths discard only this hook's three-byte JSL return, then
; resume a bank-$07 RTS with the original LinkItem_Mirror caller intact.
EarlyMirror_ItemGate:
{
  LDA.b $6C : BNE .deny
if !ENABLE_D3_PRISON_SEQUENCE == 1
  LDA.l CastleAmbushFlags : AND.b #$03 : CMP.b #$01 : BEQ .deny
endif
  LDA.b $1B : BNE .allow             ; native dungeon / FF-cave behavior
  LDA.b $8A : CMP.b #$80 : BCS .deny ; unpaired special / sea areas
  LDA.l Pendants : CMP.b #$07 : BEQ .allow
  LDA.b $8A : AND.b #$40 : BEQ .deny
  JSL EarlyMirror_HasEscapedItems : BCC .deny
  JSL EarlyMirror_StartReturn
  PLA : PLA : PLA
  JML $07A9B0                       ; LinkItem_Mirror.exit (RTS)
  .deny
  PLA : PLA : PLA
  JML $07A955                       ; original LinkGoBeep
  .allow
  RTL
}

; Preserve widths, X/Y/DB and P except carry. A is scratch. Validate the
; complete saved image before publishing it to the live exit cache.
EarlyMirror_CheckAnchor:
{
  PHP
  REP #$30
  PHX
  LDA.l EarlyMirrorAnchorMagic : CMP.w #!EarlyMirror_Magic : BEQ +
    JMP .invalid
  +
  LDA.l EarlyMirrorAnchorCache : AND.w #$FFC0 : BEQ +
    JMP .invalid
  +
  LDA.l EarlyMirrorAnchorCache : CMP.l EarlyMirrorAnchorCache+$0C : BEQ +
    JMP .invalid
  +
  LDA.l EarlyMirrorAnchorCache+$08 : CMP.w #$1000 : BCC +
    JMP .invalid
  +
  LDA.l EarlyMirrorAnchorCache+$0A : CMP.w #$1000 : BCC +
    JMP .invalid
  +
  LDA.w #$0000
  LDX.w #$0030
  .sum
    CLC : ADC.l EarlyMirrorAnchorCache, X
  DEX #2 : BPL .sum
  CMP.l EarlyMirrorAnchorChecksum : BNE .invalid
  PLX
  PLP
  SEC
  RTL
  .invalid
  PLX
  PLP
  CLC
  RTL
}

; M8/X8 on entry/exit, DB/DP unchanged. X/Y and original carry are kept;
; A/N/Z reproduce LDA SavedWorld : EOR #$40 : STA SavedWorld exactly.
EarlyMirror_CaptureEntry:
{
  PHP
  REP #$30
  PHA : PHX : PHY
  LDA.b $10 : CMP.w #$2309 : BEQ +
    JMP .done
  +
  LDA.b $1B : AND.w #$00FF : BEQ +
    JMP .done
  +
  LDA.b $8A : AND.w #$00FF : CMP.w #$0040 : BCC +
    JMP .done
  +
  LDA.l SavedWorld : AND.w #$00FF : BEQ +
    JMP .done
  +
  LDA.w $0357 : AND.w #$0010 : BNE + ; accepted native tile-$4B entry
    JMP .done
  +
  LDA.l Pendants : AND.w #$00FF : CMP.w #$0007 : BNE +
    JMP .done
  +
  JSL EarlyMirror_HasEscapedItems : BCS +
    JMP .done
  +
  ; A valid $6C return at the existing entry must not drift the anchor.
  ; A new pad at a different point/area replaces it normally.
  JSL EarlyMirror_CheckAnchor : BCC .capture
  LDA.b $8A : AND.w #$00FF : CMP.l EarlyMirrorAnchorCache : BNE .capture
  LDA.b $22 : SEC : SBC.l EarlyMirrorAnchorCache+$0A
  CLC : ADC.w #$0010 : CMP.w #$0021 : BCS .capture
  LDA.b $20 : SEC : SBC.l EarlyMirrorAnchorCache+$08
  CLC : ADC.w #$0018 : CMP.w #$0031 : BCS .capture
  JMP .done

  .capture
  LDA.w #$0000 : STA.l EarlyMirrorAnchorMagic
  ; Same live-field mapping as $02D8C5 and Exp_CacheScreen. Do not call
  ; Underworld_LoadEntrance: that routine also changes live world state.
  LDA.w $040A : STA.l EarlyMirrorAnchorCache+$00
  LDA.b $1C   : STA.l EarlyMirrorAnchorCache+$02
  LDA.b $E8   : STA.l EarlyMirrorAnchorCache+$04
  LDA.b $E2   : STA.l EarlyMirrorAnchorCache+$06
  LDA.b $20   : STA.l EarlyMirrorAnchorCache+$08
  LDA.b $22   : STA.l EarlyMirrorAnchorCache+$0A
  LDA.b $8A   : AND.w #$00FF : STA.l EarlyMirrorAnchorCache+$0C
  LDA.b $84   : STA.l EarlyMirrorAnchorCache+$0E
  LDA.w $0618 : STA.l EarlyMirrorAnchorCache+$10
  LDA.w $061C : STA.l EarlyMirrorAnchorCache+$12
  LDA.w $0600 : STA.l EarlyMirrorAnchorCache+$14
  LDA.w $0602 : STA.l EarlyMirrorAnchorCache+$16
  LDA.w $0604 : STA.l EarlyMirrorAnchorCache+$18
  LDA.w $0606 : STA.l EarlyMirrorAnchorCache+$1A
  LDA.w $0610 : STA.l EarlyMirrorAnchorCache+$1C
  LDA.w $0612 : STA.l EarlyMirrorAnchorCache+$1E
  LDA.w $0614 : STA.l EarlyMirrorAnchorCache+$20
  LDA.w $0616 : STA.l EarlyMirrorAnchorCache+$22
  LDA.w $0AA0 : STA.l EarlyMirrorAnchorCache+$24
  LDA.w $0AA2 : STA.l EarlyMirrorAnchorCache+$26
  LDA.w #$0000 : STA.l EarlyMirrorAnchorCache+$28
  LDA.w $0624 : STA.l EarlyMirrorAnchorCache+$2A
  LDA.w $0626 : STA.l EarlyMirrorAnchorCache+$2C
  LDA.w $0628 : STA.l EarlyMirrorAnchorCache+$2E
  LDA.w $062A : STA.l EarlyMirrorAnchorCache+$30
  LDA.w #$0000
  LDX.w #$0030
  .sum
    CLC : ADC.l EarlyMirrorAnchorCache, X
  DEX #2 : BPL .sum
  STA.l EarlyMirrorAnchorChecksum
  LDA.w #!EarlyMirror_Magic : STA.l EarlyMirrorAnchorMagic ; publish last
  .done
  PLY : PLX : PLA
  PLP
  LDA.l SavedWorld : EOR.b #$40 : STA.l SavedWorld
  RTL
}

; Any M/X; preserve X/Y/DB and P. Called only after the item gate's
; escaped-inventory check. Both returns reuse the native Module08 loader.
EarlyMirror_StartReturn:
{
  PHP
  REP #$30
  PHX : PHY
  JSL EarlyMirror_CheckAnchor : BCC .fallback
  LDX.w #$0030
  .copy_entry
    LDA.l EarlyMirrorAnchorCache, X : STA.l $7EC140, X
  DEX #2 : BPL .copy_entry
  ; Reconstruct only the entry's native LW return portal. Sprite $6C adds
  ; eight to Y itself; its activation is separately checked below.
  LDA.l EarlyMirrorAnchorCache+$0A
  SEP #$20
  STA.w $1ABF : XBA : STA.w $1ACF
  REP #$20
  LDA.l EarlyMirrorAnchorCache+$08
  SEP #$20
  STA.w $1ADF : XBA : STA.w $1AEF
  REP #$20
  BRA .load
  .fallback
  ; Old Abyss saves have no anchor. Escaped-stage inventory permits the
  ; existing safe Maku arrival, without a fabricated return portal.
  LDX.w #$0030
  .copy_home
    LDA.l SwordWarp_Cache, X : STA.l $7EC140, X
  DEX #2 : BPL .copy_home
  SEP #$20
  LDA.b #$FF
  STA.w $1ABF : STA.w $1ACF : STA.w $1ADF : STA.w $1AEF
  REP #$20
  .load
  STZ.w $0696 : STZ.w $0698
  LDA.w #!EarlyMirror_CacheRoom : STA.b $A0
  SEP #$20
  LDA.b #$00 : STA.l SavedWorld
  STZ.w $0FFF
  LDA.w $02B2 : CMP.b #$06 : BNE .not_gbc
    LDA.b #$10 : STA.b $BC
    STZ.w $02B2
  .not_gbc
  STZ.w $03EF : STZ.w $02E4 : STZ.w $037B : STZ.w $0FFC
  STZ.w $010A : STZ.w $04AA
  LDA.b #$80 : STA.b $13
  STZ.b $9B : STZ.b $11 : STZ.b $B0
  LDA.b #$08 : STA.b $10
  REP #$30
  PLY : PLX
  PLP
  RTL
}

; JML entry from bank-$02's local JSR caller, M8/X8, DB=$02. The synthetic
; room is the pending flag: consume it without claiming another WRAM byte.
EarlyMirror_FinishReturn:
{
  PHP
  REP #$20
  LDA.b $A0 : CMP.w #!EarlyMirror_CacheRoom : BNE .ordinary
  STZ.b $A0
  STZ.w $069A
  STZ.b $30
  SEP #$20
  LDA.b #$01 : STA.w $02DB          ; step off the entry pad before rearming
  STZ.b $11 : STZ.b $B0
  PLP
  JML $02ACC1                       ; original RTS, no door walk
  .ordinary
  PLP
  JSL $07E69D                       ; replaced moving-animation call
  JML $02AC93
}

; M8/X8, DB=$05. X is the active sprite slot. Preserve X/Y/DB and widths.
; Invalid early portals take vanilla's kill/skip-warp path, never sub-$23.
EarlyMirror_PortalGate:
{
  LDA.l Pendants : CMP.b #$07 : BEQ .allow
  LDA.l NOWARP : BNE .latched
  PHP
  REP #$30
  PHA : PHX
  JSL EarlyMirror_CheckAnchor : BCC .deny
  LDA.b $8A : AND.w #$00FF : CMP.l EarlyMirrorAnchorCache : BNE .deny
  LDA.l EarlyMirrorAnchorCache+$0A
  SEP #$20
  CMP.w SprX, X : BNE .deny
  XBA : CMP.w SprXH, X : BNE .deny
  REP #$20
  LDA.l EarlyMirrorAnchorCache+$08 : CLC : ADC.w #$0008
  SEP #$20
  CMP.w SprY, X : BNE .deny
  XBA : CMP.w SprYH, X : BNE .deny
  REP #$30
  PLX : PLA
  PLP
  .allow
  LDA.b #$23 : STA.b $11             ; replaced native instructions
  RTL
  .deny
  REP #$30
  PLX : PLA
  PLP
  PLA : PLA : PLA                   ; discard this hook's JSL return only
  JML $05AFDF                       ; native kill sprite / skip warp
  .latched
  PLA : PLA : PLA
  JML $05AFF1                       ; native skip warp; keep the entry portal
}

; Maku's first briefing and Heart Container remain in their existing order.
; The new action then uses the normal Mirror receipt. Met-Maku old saves
; missing the item can take the same action on a later eligible visit.
EarlyMirror_SelectMakuAction:
{
  LDA.l MakuTreeQuest : AND.b #$01 : BEQ .first
  JSL EarlyMirror_CanGrant : BCC .revisit
  LDA.b #$04
  RTL
  .first
  LDA.b #$01
  RTL
  .revisit
  LDA.b #$03
  RTL
}

EarlyMirror_CanGrant:
{
  JSL EarlyMirror_HasEscapedItems : BCC .no
  LDA.b $1B : BNE .no
  LDA.b $8A : CMP.b #$80 : BNE .no  ; Maku interior, normal entry from LW $2A
  LDA.l SavedWorld : BNE .no
  LDA.l Mirror : CMP.b #$02 : BCS .no
  SEC
  RTL
  .no
  CLC
  RTL
}

EarlyMirror_GrantMakuMirror:
{
  JSL EarlyMirror_CanGrant : BCC .done
  PHX : PHY
  LDY.b #$1A
  STZ.w $02E9
  JSL Link_ReceiveItem
  PLY : PLX
  .done
  RTL
}

assert bank(EarlyMirror_ItemGate) == $34
assert pc() <= $350000, "Early Mirror overflowed bank $34"
