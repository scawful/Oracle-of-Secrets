; =========================================================
; King of Red Lions Water Mount (Bank $60)
;
; Inherits Epona's zero-overrun VBlank & Menu-safe runtime:
;   - Compact sparse 4BPP tiles (<= 960 B worst-case NMI DMA, hardware $43x2
;     auto-increment, per-group Hull/Rider/Sail pointer deduplication, skips
;     1 KB animated-tile DMA on upload/restore/crowded steady NMIs -> 0 NTSC
;     VBlank overruns, 0 black top scanlines).
;   - Dropable-safe Page 0 VRAM slots ($4000/$4100 Hull 512 B, $4080/$4180
;     Seated Link Rider 128 B in SP-7, $42A0/$42C0/$40A0/$41A0 Wind Waker
;     Sail 320 B in SP-3[9..15]). Preserves Rupee ($0B/$1B), Receipt/Bird
;     ($0E/$0F), Follower/P2 ($20-$25), Boomerang ($26), Shadow/Heart ($28-$29),
;     and Bombchu ($2E-$2F).
;   - Boat-only controls (no Y-item use aboard, avoiding item-VRAM contention).
;   - Wind Waker Sail Boost on A/B hold (~2.91 px/f cardinal, fastest ocean
;     travel, faster than Zora Link and Epona) vs 2.00 px/f normal cruise.
;   - Clean shore docking & manual R mount/dismount with parked anchor.
;   - Menu-safe $0E overlay hold/restore via shared Horse_IsSafeOverlay.
;   - Day/night-aware SP-3[9..15] refresh across Light/Dark/Special/Lyra Sea.
;   - Single-byte KORL_Mounted ($7FF3D4) exported for Lyra Sea current bypass.
; =========================================================

; ---------------------------------------------------------
; Transient WRAM Block ($7FF3D4-$7FF3F3, 32 bytes in vanilla-free UNUSED_7FF180)
; Immediately after HeavySword ($7FF3D0-$7FF3D2), strictly < $7FF400 (2P PoC).
; ---------------------------------------------------------
KORL_Mounted        = $7FF3D4 ; byte: 0=off boat, 1=sailing King of Red Lions (Lyra current bypass!)
KORL_SailActive     = $7FF3D5 ; byte: 0=cruise (2.00 px/f), 1=Wind Waker sail boost (2.91 px/f)
KORL_Frame          = $7FF3D6 ; byte: desired mounted frame ID (0..11)
KORL_UploadedFrame  = $7FF3D7 ; byte: resident mounted Page 0 VRAM frame ($FF = none / restore needed)
KORL_PalLoaded      = $7FF3D8 ; byte: bit7=same-NMI mounted DMA grant, bit0=SP-3 palette active
KORL_AnimTimer      = $7FF3D9 ; byte: mounted wave bob & sail billow counter
KORL_Cooldown       = $7FF3DA ; byte: mount/dismount debounce timer
KORL_HasAnchor      = $7FF3DB ; byte: 0=none, 1=docked boat anchor valid (visibly moored!)
KORL_AnchorArea     = $7FF3DC ; byte: $8A area of docked boat
KORL_AnchorDir      = $7FF3DD ; byte: facing ($00/$02/$04/$06) when docked
KORL_AnchorX        = $7FF3DE ; word: 16-bit world X of docked water edge
KORL_AnchorY        = $7FF3E0 ; word: 16-bit world Y of docked water edge
KORL_Marker         = $7FF3E2 ; word: $4B4C ('KL') cold-init sentinel
KORL_LastWaterX     = $7FF3E4 ; word: last deep-water world X while sailing
KORL_LastWaterY     = $7FF3E6 ; word: last deep-water world Y while sailing
KORL_VelY           = $7FF3E8 ; word: signed 1/256 px/f Y boat velocity
KORL_VelX           = $7FF3EA ; word: signed 1/256 px/f X boat velocity
KORL_DockState      = $7FF3EC ; byte: $00=clean, $A1=Page1 $5C00/$5D00 saved, $A2=docked hull resident
KORL_DockSheet      = $7FF3ED ; byte: saved $7EC2FF sheet ID for safe VRAM restore
KORL_DockFrame      = $7FF3EE ; byte: desired docked empty-hull frame (0..5)
KORL_DockUploaded   = $7FF3EF ; byte: resident docked hull frame in $5C00/$5D00 ($FF = none)
KORL_DockClear      = $7FF3F0 ; byte: consecutive OAM-conflict-free frames (requires >= 2)
KORL_DockBobTimer   = $7FF3F1 ; byte: calm moored bob timer
KORL_DockOam        = $7FF3F2 ; word: OAM offset ($0800..$09F0) of 4 docked hull slots, or 0
assert KORL_DockOam+2 <= $7FF400, "KORL transient WRAM block reached 2P PoC ($7FF400)"

; Docked-boat Page 1 VRAM backup ($5C00-$5C7F + $5D00-$5D7F = 512 B) in UNUSED_7F5000
; cleanly after Horse_Off* ($7F5000-$7F5406) AND HorseGame_* ($7F5410-$7F545F), strictly < $7F5800.
KORL_DockDma0       = $7F5460 ; 2B VRAM read prefetch + 256B copy of VRAM $5C00-$5C7F
KORL_DockBuf0       = $7F5462 ; 256B payload ($7F5462..$7F5561)
KORL_DockDma1       = $7F5562 ; 2B VRAM read prefetch + 256B copy of VRAM $5D00-$5D7F
KORL_DockBuf1       = $7F5564 ; 256B payload ($7F5564..$7F5663)
assert KORL_DockDma0 >= $7F5460, "KORL docked VRAM backup overlapped Horse_Off*/HorseGame_*"
assert KORL_DockBuf1+$0100 <= $7F5800, "KORL docked VRAM backup exceeded UNUSED_7F5000 ($7F5800)"

; Persistent SRAM unlock flag ($7EF439, first free byte of FreeBlock_Dreams after
; SpecialTravelSpotsVisited $7EF438; inside native 5-page checksummed SRAM $7EF000-$7EF4FF).
KORL_Unlocked       = $7EF439 ; bit 0 (!KORL_Flag_Unlocked = $01): King of Red Lions acquired
!KORL_Flag_Unlocked = $01

!KORL_MagicMarker   = $4B4C   ; 'KL'

; Sailing physics constants (16-bit fixed-point 1/256 px/frame)
!KORL_CruiseCard    = $0200   ; 2.000 px/f (120.0 px/60f) normal cruise
!KORL_CruiseDiag    = $016A   ; 1.414 px/f per axis -> 2.000 px/f vector
!KORL_SailCard      = $02E8   ; 2.906 px/f (174.4 px/60f) Wind Waker Sail Boost!
!KORL_SailDiag      = $020E   ; 2.055 px/f per axis -> 2.906 px/f vector
!KORL_AccelStep     = $00A0   ; snappy wind-catch acceleration (top speed in ~5f)
!KORL_DecelStep     = $0050   ; gentle sailboat water glide when D-pad released

; Vanilla routines referenced long
KORL_GetTileAttr          = $00882E ; (DP $00=Ypx, $02=Xpx>>3) -> A=8x8 tiletype
KORL_ResetSwimmingState   = $07983A ; resets vanilla swim accumulators cleanly

; ---------------------------------------------------------
; Bank $07 Swimming Hooks (4-byte surgical replacements, zero overlap with zora_mask.asm!)
; ---------------------------------------------------------
pushpc
; LinkState_Swimming Flippers check ($079665): allow sailing KORL even without Flippers.
org $079665 ; @hook module=Masks name=KORL_CheckFlippersOrBoat kind=jsl target=KORL_CheckFlippersOrBoat expected_m=8 expected_x=8
  assert read4($079665) == $7EF356AF, "Expected LDA.l $7EF356 at $079665"
  JSL KORL_CheckFlippersOrBoat
assert pc() == $079669

; HandleSwimStrokeAndSubpixels entry ($07E42A): drive KORL 2.00 / 2.91 px/f sailing physics.
org $07E42A ; @hook module=Masks name=KORL_SwimVelocityHook kind=jsl target=KORL_SwimVelocityHook expected_m=8 expected_x=8
  assert read4($07E42A) == $28642764, "Expected STZ $27 : STZ $28 at $07E42A"
  JSL KORL_SwimVelocityHook
assert pc() == $07E42E
pullpc

; ---------------------------------------------------------
; Tiletype Walkable Shore Table ($00..$57)
; 1 = safe walkable dry shore OR shallow water ($09) for manual R shore dismount.
; Deep water ($08, $4B), solids ($01-$04), pits ($20), ledges ($28-$2F) = 0.
; ---------------------------------------------------------
KORL_ShoreWalkableAttr:
  db 1,0,0,0,0,1,1,1, 0,1,0,0,0,0,0,0 ; $00-$0F ($00 ground, $05-$07 normal, $08 DEEP water=0, $09 shallow=1!)
  db 0,0,0,0,1,1,1,1, 0,0,0,0,0,0,0,0 ; $10-$1F ($14-$17 normal)
  db 0,1,0,1,1,1,0,0, 0,0,0,0,0,0,0,0 ; $20-$2F ($21,$23-$25 normal; $20 pit, $28-$2F ledges)
  db 0,0,0,0,0,0,0,0, 1,1,1,1,1,0,0,0 ; $30-$3F ($38-$3C normal)
  db 1,1,1,0,0,1,0,1, 1,1,0,0,1,1,1,1 ; $40-$4F ($40 grass, $48 dirt, $4B deep water=0)
  db 0,0,0,0,0,0,0,0                  ; $50-$57 (liftable rocks/bushes)

; ---------------------------------------------------------
; Slot-Busy Guard (mirrors Horse_SlotsBusy; C=1 if cutscene, live ancilla, or receipt)
; Preserves all registers, widths, DBR.
; ---------------------------------------------------------
KORL_SlotsBusy:
{
  PHP : PHB : REP #$30 : PHA : PHX
  SEP #$20 : LDA.b #$00 : PHA : PLB
  LDA.l InCutScene : BNE .busy
  LDX.w #9
  .scan_anc
    LDA.w $0C4A, X : BEQ .next_anc
    CMP.b #$15 : BEQ .next_anc       ; jump splash (page 0 $C0+ static tiles, disjoint)
    CMP.b #$1D : BEQ .next_anc       ; dash tremor: BG offset only
    CMP.b #$22 : BEQ .next_anc       ; item receipt uses $40E0/$41E0 (disjoint)
    CMP.b #$3D : BEQ .next_anc       ; object water splash (static tiles, disjoint)
    CMP.b #$41 : BEQ .next_anc       ; waterfall splash (static tiles, disjoint)
    BRA .busy
    .next_anc
    DEX : BPL .scan_anc
  LDX.w #15
  .scan_spr
    LDA.w $0DD0, X : BEQ .next_spr
    LDA.w $0E20, X : CMP.b #$EA : BEQ .busy
    CMP.b #$E7 : BEQ .busy
    .next_spr
    DEX : BPL .scan_spr
  REP #$30 : PLX : PLA : PLB : PLP : CLC : RTL
  .busy
  REP #$30 : PLX : PLA : PLB : PLP : SEC : RTL
}

; ---------------------------------------------------------
; Palette Helpers (SP-3[9..15] = $7EC472..$7EC47E / $7EC672..$7EC67E)
; Applies TimeSystem Day/Night tinting identically to Epona.
; ---------------------------------------------------------
KORL_LoadPalette:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  REP #$30
  PHX : PHY
  LDY.w #$000C                        ; 7 colors = 14 bytes (offsets 12,10,...,0)
  .loop
    PHY
    TYX : LDA.l KORL_Palette, X : PHA
    TYA : CLC : ADC.w #$0172 : TAX
    PLA
    JSL LoadDayNightPaletteEffect
    REP #$30
    PLX
    STA.l $7EC672, X
    TXY
    DEY : DEY : BPL .loop
  PLY : PLX
  SEP #$20
  INC.b $15
  PLB : PLP
  RTL
}

KORL_RestoreSp3Palette:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  ; If Epona NPC is active on this map, restore her SP-3 brown instead of neutral fill.
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BEQ .neutral
    JSL UpdateHorsePalette
    PLB : PLP
    RTL
  .neutral
endif
  REP #$30
  PHX : PHY
  LDY.w #$000C
  .loop
    PHY
    TYA : CLC : ADC.w #$0172 : TAX
    LDA.w #$14A5                      ; MainSpr SP-3[9..15] uniform fill
    JSL LoadDayNightPaletteEffect
    REP #$30
    PLX
    STA.l $7EC672, X
    TXY
    DEY : DEY : BPL .loop
  PLY : PLX
  SEP #$20
  INC.b $15
  PLB : PLP
  RTL
}

; Called from Palette_ArmorAndGloves (.original_palette) — preserves P (M16/C=0) & A/X/Y.
; Refreshes KORL SP-3[9..15] whenever KORL is mounted OR visibly docked on the current area!
KORL_RefreshPaletteIfMounted:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$20
  LDA.l KORL_Marker : CMP.b #(!KORL_MagicMarker&$FF) : BNE .done
  LDA.l KORL_Marker+1 : CMP.b #(!KORL_MagicMarker>>8) : BNE .done
  LDA.l KORL_Mounted : BNE .reload
  ; Also keep SP-3 active while King of Red Lions is visibly moored on this outdoor map!
  LDA.l KORL_HasAnchor : BEQ .done
  LDA.l $7E001B : BNE .done
  LDA.l $7E008A : CMP.l KORL_AnchorArea : BNE .done
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BNE .done
endif
  .reload
    JSL KORL_LoadPalette
  .done
  REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; ---------------------------------------------------------
; Cold-Init & Lifecycle (Mount / Dock / Dismount / Clear)
; ---------------------------------------------------------
KORL_EnsureInit:
{
  PHP : REP #$30
  LDA.l KORL_Marker : CMP.w #!KORL_MagicMarker : BEQ .ok
    SEP #$20
    PHX
    LDX.w #$001F
    LDA.b #$00
    .clr
      STA.l KORL_Mounted, X
      DEX : BPL .clr
    LDA.b #$FF
    STA.l KORL_UploadedFrame
    STA.l KORL_DockUploaded
    REP #$20
    LDA.w #!KORL_MagicMarker : STA.l KORL_Marker
    PLX
  .ok
  PLP
  RTL
}

; Clears mounted state & velocities cleanly (safe from ResetToLinkGraphics / GameOver / SaveQuit).
; Preserves moored anchor coords/dir so docked King of Red Lions stays waiting outdoors.
; Preserves A/X/Y/DBR/P.
KORL_ClearState:
{
  PHP : REP #$30 : PHA
  SEP #$20
  LDA.l KORL_Marker : CMP.b #(!KORL_MagicMarker&$FF) : BNE .exit
  LDA.l KORL_Marker+1 : CMP.b #(!KORL_MagicMarker>>8) : BNE .exit
  LDA.b #$00
  STA.l KORL_Mounted
  STA.l KORL_SailActive
  STA.l KORL_AnimTimer
  STA.l KORL_PalLoaded
  STA.l KORL_VelY
  STA.l KORL_VelY+1
  STA.l KORL_VelX
  STA.l KORL_VelX+1
  .exit
  REP #$30 : PLA : PLP
  RTL
}

; Initializes calm moored docked-boat frame from KORL_AnchorDir & keeps SP-3 warm.
; Entry: M=8, X=8, DBR=$00.
KORL_InitDockedMoored:
{
  LDA.l KORL_AnchorDir : AND.b #$06 : LSR A : TAX
  LDA.l KORL_DirBase, X
  STA.l KORL_DockFrame
  LDA.b #$00
  STA.l KORL_DockBobTimer
  STA.l KORL_DockClear
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BEQ .keep_pal
    JSL KORL_RestoreSp3Palette
    RTS
  .keep_pal
endif
  LDA.b #$01 : STA.l KORL_PalLoaded
  JSL KORL_LoadPalette
  RTS
}

; Board King of Red Lions on deep water. Preserves A/X/Y/DBR/P.
KORL_Mount:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB
  JSL KORL_EnsureInit
  JSL KORL_SlotsBusy : BCC +
    BRL .abort
  +

  ; Ensure swimming state ($5D=$04, $0345=1) and reset stale swim accel.
  LDA.b #$04 : STA.b $5D
  LDA.b #$01 : STA.w $0345
  STZ.b $3C : STZ.b $3A : STZ.b $55
  JSL KORL_ResetSwimmingState

  LDA.b #$01 : STA.l KORL_Mounted
  LDA.b #$00
  STA.l KORL_SailActive
  STA.l KORL_AnimTimer
  STA.l KORL_VelY : STA.l KORL_VelY+1
  STA.l KORL_VelX : STA.l KORL_VelX+1
  STA.l KORL_DockClear
  LDA.b #$FF : STA.l KORL_UploadedFrame
  LDA.b #$14 : STA.l KORL_Cooldown

  ; Save initial deep-water anchor coords & pick initial directional frame.
  REP #$20
  LDA.b $22 : STA.l KORL_LastWaterX : STA.l KORL_AnchorX
  LDA.b $20 : STA.l KORL_LastWaterY : STA.l KORL_AnchorY
  SEP #$20
  LDA.b $8A : STA.l KORL_AnchorArea
  LDA.b $2F : STA.l KORL_AnchorDir
  JSR KORL_SelectFrame

  ; Load KORL SP-3[9..15] palette + Link SP-7 worn tunic.
  LDA.b #$01 : STA.l KORL_PalLoaded
  JSL KORL_LoadPalette
  JSL Palette_ArmorAndGloves

  ; Crisp splash/boarding SFX2.25
  LDA.b #$25 : STA.w $0CF8
  JSL $0DBB67
  ORA.w $0CF8 : STA.w $012E

  .abort
  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; Clean shore dock when Link hops out of deep water onto beach/pier/shallow shore.
; Keeps King of Red Lions visibly moored & bobbing right at the water's edge!
KORL_DockAtShore:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB

  REP #$20
  LDA.l KORL_LastWaterX : STA.l KORL_AnchorX
  LDA.l KORL_LastWaterY : STA.l KORL_AnchorY
  SEP #$20
  LDA.b $8A : STA.l KORL_AnchorArea
  LDA.b #$01 : STA.l KORL_HasAnchor

  JSL KORL_ClearState
  JSR KORL_InitDockedMoored
  LDA.b #$18 : STA.l KORL_Cooldown

  ; Gentle dock splash cue
  LDA.b #$21 : STA.w $0CF8
  JSL $0DBB67
  ORA.w $0CF8 : STA.w $012E

  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; Quiet dismount for doorways / indoors / cutscenes / busy slots. Preserves A/X/Y/DBR/P.
KORL_SilentDismount:
{
  PHP : REP #$30 : PHA : PHX : PHY
  SEP #$30 : PHB
  LDA.b #$00 : PHA : PLB

  LDA.b $1B : BNE .skip_pal
    JSL KORL_RestoreSp3Palette
  .skip_pal
  JSL KORL_ClearState
  LDA.b #$10 : STA.l KORL_Cooldown

  PLB : REP #$30 : PLY : PLX : PLA : PLP
  RTL
}

; ---------------------------------------------------------
; Per-Frame Hook from LinkMain_FrameHook (M=8, DBR=$07/any)
; ---------------------------------------------------------
KORL_FrameTick:
{
  PHP : PHB
  SEP #$30
  LDA.b #$00 : PHA : PLB
  JSL KORL_EnsureInit

  LDA.l KORL_Cooldown : BEQ +
    DEC : STA.l KORL_Cooldown
  +

  LDA.l KORL_Mounted : BEQ +
    BRL .mounted
  +

  ; --- UNMOUNTED: maintain visibly moored boat + deliberate A/R re-board (NO auto-remount!) ---
  ; If indoors or on a different area than the docked boat, restore SP-3 once while keeping anchor!
  LDA.b $1B : BEQ + : BRL .off_dock_area : +
  LDA.b $10 : CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BEQ .mod_ok
    BRL .exit_near
  .mod_ok
  LDA.l KORL_HasAnchor : BNE + : BRL .chk_open_water_summon : +
  LDA.b $8A : CMP.l KORL_AnchorArea : BEQ + : BRL .off_dock_area : +

  ; On the docked boat's outdoor map!
  LDA.b $11 : BEQ + : BRL .exit_near_tramp : +

  ; Advance calm moored wave-bob animation (toggles frame A/B every 16 frames).
  LDA.l KORL_DockBobTimer : INC : STA.l KORL_DockBobTimer
  LDA.l KORL_AnchorDir : AND.b #$06 : LSR A : TAX
  LDA.l KORL_DirBase, X : STA.b $00
  LDA.l KORL_DockBobTimer : LSR #4 : AND.b #$01
  CLC : ADC.b $00
  STA.l KORL_DockFrame

  ; Keep KORL SP-3[9..15] palette Day/Night-refreshed while boat is moored (yield if Epona NPC active).
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BNE .skip_dock_pal
endif
  LDA.b $13 : CMP.b #$0F : BNE .skip_dock_pal
  REP #$30
  LDA.l KORL_Palette+12 : LDX.w #$017E
  JSL LoadDayNightPaletteEffect
  REP #$30
  CMP.l $7EC67E : BEQ .dock_pal_ok
    SEP #$30
    LDA.b #$01 : STA.l KORL_PalLoaded
    JSL KORL_LoadPalette
  .dock_pal_ok
  SEP #$30
  .skip_dock_pal

  ; Deliberate re-board check when Link stands on pier/shore OR swims within +/-28 px of moored boat!
  LDA.w $0FFC : ORA.w $02E4 : BNE .exit_near_tramp
  LDA.w !ZoraDiving : BNE .exit_near_tramp
  LDA.l KORL_Cooldown : BNE .exit_near_tramp
  LDA.l InCutScene : BNE .exit_near_tramp
  LDA.w !CurrentMask : BEQ .dock_form_ok
  CMP.b #$06 : BNE .exit_near_tramp
  .dock_form_ok
  REP #$20
  LDA.b $22 : SEC : SBC.l KORL_AnchorX : CLC : ADC.w #28 : CMP.w #57 : BCS .not_beside_boat
  LDA.b $20 : SEC : SBC.l KORL_AnchorY : CLC : ADC.w #28 : CMP.w #57 : BCS .not_beside_boat
  SEP #$20
  ; Beside the visibly moored boat! Re-board deliberately on fresh R OR fresh A (when not carrying)!
  LDA.b $F6 : AND.b #$10 : BNE .reboard_r
  LDA.b $F6 : AND.b #$80 : BEQ .exit_near_tramp
  LDA.w $0308 : ORA.b $3C : BNE .exit_near_tramp ; carrying liftable or mid-swing -> don't hijack A
    LDA.b #$80 : TRB.b $F6
    BRA .do_reboard
  .reboard_r
    LDA.b #$10 : TRB.b $F6
  .do_reboard
    ; Snap Link cleanly into the visibly docked boat at exact anchor coordinates & facing!
    REP #$20
    LDA.l KORL_AnchorX : STA.b $22
    LDA.l KORL_AnchorY : STA.b $20
    SEP #$20
    LDA.l KORL_AnchorDir : STA.b $2F
    JSL KORL_Mount
  .exit_near_tramp
    PLB : PLP
    RTL

  .not_beside_boat
  SEP #$20
  BRA .chk_open_water_summon

  .off_dock_area
  ; Left the moored map or went indoors: restore SP-3 once while preserving KORL_HasAnchor!
  LDA.l KORL_PalLoaded : AND.b #$01 : BEQ .chk_open_water_summon_guard
    LDA.b #$00 : STA.l KORL_PalLoaded
    LDA.b $1B : BNE .chk_open_water_summon_guard
      JSL KORL_RestoreSp3Palette
  .chk_open_water_summon_guard
  LDA.b $1B : BNE .exit_near

  ; --- Open-water deliberate R summon/board (only when swimming in deep water $5D==$04) ---
  .chk_open_water_summon
  LDA.b $11 : BNE .exit_near
  LDA.b $5D : CMP.b #$04 : BNE .exit_near      ; deep-water swimming only
  LDA.w $0FFC : ORA.w $02E4 : BNE .exit_near
  LDA.w !ZoraDiving : BNE .exit_near
  LDA.l KORL_Cooldown : BNE .exit_near
  LDA.l KORL_Unlocked : AND.b #!KORL_Flag_Unlocked : BEQ .exit_near
  ; Human Link ($00) or GBC Link ($06) only — never hijack Zora Mask ($02) or Epona ($09)!
  LDA.w !CurrentMask : BEQ .form_ok
  CMP.b #$06 : BNE .exit_near
  .form_ok
  ; Deliberate fresh R press while swimming in deep water -> summon & board King of Red Lions!
  LDA.b $F6 : AND.b #$10 : BEQ .exit_near
    LDA.b #$10 : TRB.b $F6
    JSL KORL_Mount
  .exit_near
    PLB : PLP
    RTL

  ; --- MOUNTED: sailing King of Red Lions ---
  .mounted
  ; Overlay ($0E) leaves mounted state untouched; Horse_IsSafeOverlay gates VRAM/OAM.
  LDA.b $10 : CMP.b #$0E : BEQ .exit_mounted
  ; Must stay outdoors in OW play ($09/$0B) without busy slots/cutscene.
  LDA.b $1B : BNE .force_silent_near
  LDA.b $10 : CMP.b #$09 : BEQ .outdoor_ok
  CMP.b #$0B : BEQ .outdoor_ok
  .force_silent_near
    BRL .force_silent
  .outdoor_ok
  JSL KORL_SlotsBusy : BCS .force_silent_near

  ; During OW / Lyra Sea border scroll transitions ($11 != 0): hold pose & suppress items.
  LDA.b $11 : BEQ .settled
    JSR KORL_SuppressBoatButtons
    .exit_mounted
    PLB : PLP
    RTL

  .settled
  ; If vanilla transitioned Link out of deep water (e.g. $5D=$06 hop onto shore or $5D=$00),
  ; cleanly dock King of Red Lions at the water's edge!
  LDA.b $5D : CMP.b #$04 : BNE .shore_dock_near
  LDA.b $4D : BEQ .on_water
  .shore_dock_near
    BRL .shore_dock
  .on_water

  ; Record current deep-water position for clean shore docking.
  REP #$20
  LDA.b $22 : STA.l KORL_LastWaterX
  LDA.b $20 : STA.l KORL_LastWaterY
  SEP #$20
  LDA.b $2F : STA.l KORL_AnchorDir

  ; Check manual R dismount / shore dock (when debounce clear).
  LDA.l KORL_Cooldown : BNE .after_r
  LDA.b $F6 : AND.b #$10 : BEQ .after_r
    LDA.b #$10 : TRB.b $F6
    JSR KORL_TryManualDismount
    LDA.l KORL_Mounted : BEQ .exit_mounted
  .after_r

  ; Read Wind Waker Sail Boost hold: A ($F2 bit 7) OR B ($F0 bit 7)!
  LDA.b $F2 : ORA.b $F0 : AND.b #$80 : BEQ .sail_off
    LDA.l KORL_SailActive : BNE .sail_on
      LDA.b #$01 : STA.l KORL_SailActive
      ; Crisp wind-catch sail-snap SFX if channel 2 is quiet
      LDA.w $012E : BNE .sail_on
        LDA.b #$20 : STA.w $012E
    .sail_on
    BRA .after_sail
  .sail_off
    LDA.b #$00 : STA.l KORL_SailActive
  .after_sail

  ; Enforce boat-only controls (no Y-item, X-item, or vanilla swim-stroke spam).
  JSR KORL_SuppressBoatButtons

  ; Cross-world Day/Night-aware SP-3[9..15] palette guard (mirrors Epona's $7EC67E check):
  ; Catches LW uniform $14A5 fills AND non-uniform SW/DW/Lyra Sea palettes ($B0, $A2, etc.)!
  LDA.b $13 : CMP.b #$0F : BNE .pal_ok
  REP #$30
  LDA.l KORL_Palette+12 : LDX.w #$017E
  JSL LoadDayNightPaletteEffect
  REP #$30
  CMP.l $7EC67E : BEQ .pal_ok
    SEP #$30
    JSL KORL_LoadPalette
  .pal_ok
  SEP #$30

  ; Advance wave-bob / sail-billow animation timer and select KORL_Frame (0..11).
  LDA.l KORL_AnimTimer : INC : STA.l KORL_AnimTimer
  JSR KORL_SelectFrame

  PLB : PLP
  RTL

  .force_silent
  JSL KORL_SilentDismount
  PLB : PLP
  RTL

  .shore_dock
  JSL KORL_DockAtShore
  PLB : PLP
  RTL
}

; Suppresses A/B/Y/X new-presses so no Y-item or vanilla swim-stroke fires aboard KORL.
; Preserves D-pad ($F0&$0F) and Start/Select ($F4&$30) for Pause/Save menus!
KORL_SuppressBoatButtons:
{
  LDA.b #$C0 : TRB.b $F4              ; clear B ($80) and Y ($40) new presses
  LDA.b #$C0 : TRB.b $F6              ; clear A ($80) and X ($40) new presses
  RTS
}

; Computes KORL_Frame (0..11) from LinkFaceDir ($2F), KORL_SailActive, and KORL_AnimTimer.
; Preserves X/Y; M=8, X=8, DBR=$00.
KORL_SelectFrame:
{
  ; Base dir offset: Down ($02)->0, Up ($00)->2, Left ($04)/Right ($06)->4
  LDA.b $2F : AND.b #$06 : LSR A : TAX
  LDA.l KORL_DirBase, X
  STA.b $00
  ; Bob / billow bit: 8f cadence when sail raised, 16f cadence when cruising
  LDA.l KORL_SailActive : BEQ .cruise_bob
    LDA.b $00 : CLC : ADC.b #$06 : STA.b $00
    LDA.l KORL_AnimTimer : LSR #3 : AND.b #$01
    BRA .apply_bob
  .cruise_bob
  LDA.l KORL_AnimTimer : LSR #4 : AND.b #$01
  .apply_bob
  CLC : ADC.b $00
  STA.l KORL_Frame
  RTS
}
KORL_DirBase:
  db $02, $00, $04, $04               ; $2F=0(Up)->2, 2(Down)->0, 4(Left)->4, 6(Right)->4

; Manual R dismount: tries adjacent walkable shore/shallow tile first (facing dir then N/S/W/E);
; if out in open deep water with Flippers, dismounts into swimming leaving boat anchored.
; Entry: M=8, X=8, DBR=$00.
KORL_TryManualDismount:
{
  PHX : PHY
  ; Probe order: start with current facing dir (0=U, 1=D, 2=L, 3=R), then remaining 3 cardinals.
  LDA.b $2F : AND.b #$06 : LSR A : STA.b $0E ; $0E = starting dir index
  LDY.b #$04
  .probe_loop
    PHY
    LDA.b $0E : ASL : TAX
    REP #$20
    LDA.b $22 : CLC : ADC.l .shore_dx, X : STA.b $08 ; candX
    LDA.b $20 : CLC : ADC.l .shore_dy, X : STA.b $06 ; candY
    ; Stay inside the same $400 overworld quadrant and non-border margins
    LDA.b $08 : CMP.w #$0010 : BCC .fail16
    EOR.b $22 : AND.w #$FC00 : BNE .fail16
    LDA.b $06 : CMP.w #$0010 : BCC .fail16
    EOR.b $20 : AND.w #$FC00 : BNE .fail16
    ; Check foot center (candX+8, candY+14) is walkable shore or shallow water!
    LDA.b $08 : CLC : ADC.w #$0008 : STA.b $0C
    LDA.b $06 : CLC : ADC.w #$000E : STA.b $0A
    SEP #$20
    JSR KORL_QueryTileAt              ; A = tiletype
    CMP.b #$58 : BCS .fail8
    TAX
    LDA.l KORL_ShoreWalkableAttr, X : BEQ .fail8
    ; Also verify foot left (candX+3, candY+14) and right (candX+12, candY+14) aren't solid/water
    REP #$20
    LDA.b $08 : CLC : ADC.w #$0003 : STA.b $0C
    SEP #$20
    JSR KORL_QueryTileAt
    CMP.b #$58 : BCS .fail8
    TAX
    LDA.l KORL_ShoreWalkableAttr, X : BEQ .fail8
    REP #$20
    LDA.b $08 : CLC : ADC.w #$000C : STA.b $0C
    SEP #$20
    JSR KORL_QueryTileAt
    CMP.b #$58 : BCS .fail8
    TAX
    LDA.l KORL_ShoreWalkableAttr, X : BNE .found_shore
    .fail8
    BRL .next_cand
    .fail16
    BRL .next_cand16

    .found_shore
    ; Valid walkable shore found! Leave King of Red Lions visibly moored & hop Link onto shore!
    PLY
    REP #$20
    LDA.b $22 : STA.l KORL_AnchorX
    LDA.b $20 : STA.l KORL_AnchorY
    LDA.b $08 : STA.b $22
    LDA.b $06 : STA.b $20
    SEP #$20
    LDA.b $8A : STA.l KORL_AnchorArea
    LDA.b #$01 : STA.l KORL_HasAnchor
    STZ.b $5D
    STZ.w $0345
    JSL KORL_ResetSwimmingState
    JSL KORL_ClearState
    JSR KORL_InitDockedMoored
    LDA.b #$18 : STA.l KORL_Cooldown
    LDA.b #$21 : STA.w $012E          ; crisp land/dock thud
    PLY : PLX
    RTS

    .next_cand16
    SEP #$20
    .next_cand
    PLY
    LDA.b $0E : INC : AND.b #$03 : STA.b $0E
    DEY : BEQ +
      BRL .probe_loop
    +

  ; No adjacent walkable shore: if Link has Flippers, dismount into swimming leaving boat visibly moored!
  LDA.l $7EF356 : BEQ .refuse_dismount
    REP #$20
    LDA.b $22 : STA.l KORL_AnchorX
    LDA.b $20 : STA.l KORL_AnchorY
    SEP #$20
    LDA.b $8A : STA.l KORL_AnchorArea
    LDA.b #$01 : STA.l KORL_HasAnchor
    JSL KORL_ResetSwimmingState
    JSL KORL_ClearState
    JSR KORL_InitDockedMoored
    LDA.b #$18 : STA.l KORL_Cooldown
    LDA.b #$25 : STA.w $012E          ; water splash SFX
    PLY : PLX
    RTS

  .refuse_dismount
  LDA.b #$3C : STA.w $012E            ; gentle error beep (no Flippers & no shore)
  PLY : PLX
  RTS

  ;            Up      Down    Left    Right
  .shore_dx: dw $0000, $0000, $FFEC, $0014
  .shore_dy: dw $FFEC, $0014, $0000, $0000
}

; Queries Overworld_GetTileAttrAtLocation ($00882E) safely from any DBR.
; In:  DP $0A = 16-bit world Y px, DP $0C = 16-bit world X px (M/X=8).
; Out: A = 8-bit TileType (M=8, X=8); preserves DP $00-$09, X, Y, DBR.
KORL_QueryTileAt:
{
  PHB : PHX : PHY
  REP #$20
  LDA.b $00 : PHA : LDA.b $02 : PHA
  LDA.b $04 : PHA : LDA.b $06 : PHA : LDA.b $08 : PHA
  LDA.b $0A : STA.b $00               ; $00 = world Y pixels
  LDA.b $0C : LSR #3 : STA.b $02      ; $02 = world X / 8
  SEP #$20
  LDA.b #$00 : PHA : PLB              ; $00882E reads $0708..$070E with w-addr
  JSL KORL_GetTileAttr                ; returns SEP #$30, A = TileType (clobbers DP $00-$07!)
  TAX
  REP #$20
  PLA : STA.b $08 : PLA : STA.b $06 : PLA : STA.b $04
  PLA : STA.b $02 : PLA : STA.b $00
  SEP #$30
  TXA
  PLY : PLX : PLB
  RTS
}

; ---------------------------------------------------------
; Bank $07 Swimming Hooks
; ---------------------------------------------------------

; Hook at $079665 (replaces LDA.l $7EF356). Returns A != 0 when mounted on KORL!
KORL_CheckFlippersOrBoat:
{
  LDA.l KORL_Mounted : BNE .allow
    LDA.l $7EF356
  .allow
  RTL
}

; Hook at $07E42A (replaces STZ.b $27 : STZ.b $28 at entry of HandleSwimStrokeAndSubpixels).
; Entry: M=8, X=8, DBR=$07 (Link_HandleVelocity pushed caller DBR on stack).
; When KORL_Mounted == 0 or $5D != #$04: replays STZ $27 : STZ $28 : RTL (0 impact on vanilla/Zora!).
; When KORL_Mounted != 0 and $5D == #$04: computes crisp 8-way boat velocity (2.00 px/f cruise,
; 2.91 px/f Wind Waker Sail Boost) with smooth glide into $08..$0B and $67, updates $2F facing,
; pops JSL return, and JMLs cleanly to HandleSwimStrokeAndSubpixels.continue ($07E4D3)!
KORL_SwimVelocityHook:
{
  LDA.l KORL_Mounted : BEQ .native
  LDA.b $5D : CMP.b #$04 : BEQ .boat_physics
  .native
  STZ.b $27
  STZ.b $28
  RTL

  .boat_physics
  STZ.b $27
  STZ.b $28

  ; Read live D-pad ($F0 & $0F) -> DP $00
  LDA.b $F0 : AND.b #$0F : STA.b $00

  ; Update Link facing $2F (0=U, 2=D, 4=L, 6=R) smoothly from D-pad without diagonal flicker
  BEQ .skip_face
    ; Pure cardinal check
    CMP.b #$08 : BEQ .face_u
    CMP.b #$04 : BEQ .face_d
    CMP.b #$02 : BEQ .face_l
    CMP.b #$01 : BEQ .face_r
    ; Diagonal: keep current $2F if it matches a held bit, else prefer horizontal
    LDA.b $2F : AND.b #$06 : LSR A : TAX
    LDA.b $00 : AND.l .dir_bits, X : BNE .skip_face
    LDA.b $00 : BIT.b #$02 : BNE .face_l
    BIT.b #$01 : BNE .face_r
    BIT.b #$08 : BNE .face_u
    .face_d : LDA.b #$02 : BRA .set_face
    .face_u : LDA.b #$00 : BRA .set_face
    .face_l : LDA.b #$04 : BRA .set_face
    .face_r : LDA.b #$06
    .set_face : STA.b $2F
  .skip_face

  ; Choose target speed magnitude (16-bit 1/256 px/f) -> DP $04:
  ;   Check diagonal (both V=$0C and H=$03 held) AND KORL_SailActive!
  LDX.b #$00
  LDA.b $00 : AND.b #$0C : BEQ .not_diag
  LDA.b $00 : AND.b #$03 : BEQ .not_diag
    LDX.b #$02                        ; diagonal offset +2
  .not_diag
  LDA.l KORL_SailActive : BEQ .not_sail
    INX #4                            ; sail boost table +4
  .not_sail
  REP #$20
  LDA.l .speed_table, X : STA.b $04   ; $04 = positive target magnitude

  ; --- Y axis target ($06): Up ($08) -> -mag, Down ($04) -> +mag, neither -> 0 ---
  LDA.w #$0000 : STA.b $06
  SEP #$20
  LDA.b $00 : BIT.b #$08 : BNE .y_neg
  BIT.b #$04 : BEQ .y_step
    REP #$20
    LDA.b $04 : STA.b $06
    BRA .y_step
  .y_neg
    REP #$20
    LDA.w #$0000 : SEC : SBC.b $04 : STA.b $06
  .y_step
  REP #$20
  LDA.l KORL_VelY : JSR KORL_StepAxis
  STA.l KORL_VelY
  STA.b $08                           ; DP $08/$09 = signed Y velocity (1/256 px/f)

  ; --- X axis target ($06): Left ($02) -> -mag, Right ($01) -> +mag, neither -> 0 ---
  LDA.w #$0000 : STA.b $06
  SEP #$20
  LDA.b $00 : BIT.b #$02 : BNE .x_neg
  BIT.b #$01 : BEQ .x_step
    REP #$20
    LDA.b $04 : STA.b $06
    BRA .x_step
  .x_neg
    REP #$20
    LDA.w #$0000 : SEC : SBC.b $04 : STA.b $06
  .x_step
  REP #$20
  LDA.l KORL_VelX : JSR KORL_StepAxis
  STA.l KORL_VelX
  STA.b $0A                           ; DP $0A/$0B = signed X velocity (1/256 px/f)

  ; Build collision direction mask $67 & $0340 from signed signs of $08 (Y) and $0A (X).
  LDY.b #$00
  LDA.b $08 : BEQ .chk_x_dir
    BMI .dir_up
      INY #4                          ; Down ($04)
      BRA .chk_x_dir
    .dir_up
      LDY.b #$08                      ; Up ($08)
  .chk_x_dir
  LDA.b $0A : BEQ .store_dir
    BMI .dir_left
      TYA : ORA.w #$0001 : TAY        ; Right ($01)
      BRA .store_dir
    .dir_left
      TYA : ORA.w #$0002 : TAY        ; Left ($02)
  .store_dir
  SEP #$30
  STY.b $67
  STY.w $0340
  ; Pop our 3-byte JSL return and continue straight into vanilla subpixel application!
  PLA : PLA : PLA
  JML $07E4D3

  .dir_bits
  db $08, $04, $02, $01
  .speed_table
  dw !KORL_CruiseCard, !KORL_CruiseDiag
  dw !KORL_SailCard,   !KORL_SailDiag
}

; Smoothly steps signed 16-bit velocity A toward signed 16-bit target DP $06.
; Uses !KORL_AccelStep when target != 0, !KORL_DecelStep when coasting to 0.
; Entry/Exit: M=16, X=8. Clobbers DP $02, $0C.
KORL_StepAxis:
{
  CMP.b $06 : BEQ .done
  STA.b $02                           ; $02 = current vel
  LDA.b $06 : BEQ .use_decel
    LDA.w #!KORL_AccelStep : BRA .have_step
  .use_decel
    LDA.w #!KORL_DecelStep
  .have_step
  STA.b $0C                           ; $0C = positive step magnitude
  ; Signed delta = target - current (both strictly in [-$0400..+$0400], no overflow)
  LDA.b $06 : SEC : SBC.b $02
  BMI .step_down
    CMP.b $0C : BCC .snap : BEQ .snap
    LDA.b $02 : CLC : ADC.b $0C
    RTS
  .step_down
    EOR.w #$FFFF : INC A              ; |delta|
    CMP.b $0C : BCC .snap : BEQ .snap
    LDA.b $02 : SEC : SBC.b $0C
    RTS
  .snap
  LDA.b $06
  .done
  RTS
}

; ---------------------------------------------------------
; NMI Prefix & Sparse DMA Uploader (VBlank-safe <= 960 B!)
; ---------------------------------------------------------

; Entry via JML from Horse_LinkDmaPrefix (.native): M=8, X=16, DBR=$00.
; Skips Link's 896 B $4000-$40DF/$4100-$41DF DMA while refreshing animated Rupee $40B0/$41B0.
KORL_LinkDmaPrefix:
{
  ; Clear same-NMI grant bit 7; preserve palette bit 0.
  LDA.l KORL_PalLoaded : AND.b #$7F : STA.l KORL_PalLoaded
  REP #$20 : LDA.l KORL_Marker : CMP.w #!KORL_MagicMarker : SEP #$20
  BNE .native
  LDA.l KORL_Mounted : BEQ .native
  LDA.b $1B : BNE .native
  LDA.b $10 : CMP.b #$09 : BEQ .eligible
  CMP.b #$0B : BEQ .eligible
  CMP.b #$0E : BNE .native
  JSL Horse_IsSafeOverlay : BCS .eligible
  .native
  LDY.w #$4100 : STY.w $2116
  JML $008A12

  .eligible
  ; Single-pass DBR=$00 busy check (matches Horse_LinkDmaPrefix fast path).
  LDA.l InCutScene : BNE .native
  LDX.w #9
  .anc_scan
    LDA.w $0C4A, X : BEQ .next_anc
    CMP.b #$15 : BEQ .next_anc
    CMP.b #$1D : BEQ .next_anc
    CMP.b #$22 : BEQ .next_anc
    CMP.b #$3D : BEQ .next_anc
    CMP.b #$41 : BEQ .next_anc
    BRA .native
    .next_anc
    DEX : BPL .anc_scan
  LDX.w #15
  .spr_scan
    LDA.w $0DD0, X : BEQ .next_spr
    LDA.w $0E20, X : CMP.b #$EA : BEQ .native
    CMP.b #$E7 : BEQ .native
    .next_spr
    DEX : BPL .spr_scan

  ; Grant same-NMI KORL upload!
  LDA.l KORL_PalLoaded : ORA.b #$80 : STA.l KORL_PalLoaded
  ; Required post-prefix DMA channel banks ($7E) for vanilla $008ADB body.
  LDA.b #$7E
  STA.w $4304 : STA.w $4314 : STA.w $4324 : STA.w $4334 : STA.w $4344
  ; Keep animated Rupee dropable ($0B/$1B = VRAM $40B0/$41B0) live every frame!
  LDX.w #$0020
  LDA.b #$01
  LDY.w #$40B0 : STY.w $2116
  LDY.w $0AE0  : STY.w $4302 : STX.w $4305
  STA.w $420B
  LDY.w #$41B0 : STY.w $2116
  LDY.w $0AE2  : STY.w $4302 : STX.w $4305
  STA.w $420B
  LDX.w #$0040
  JML $008ADB
}

; Entry via JSL from Horse_NmiUpload (.replay): M=8, X=16, DBR=$00.
; DP $04/$06 are already saved by Horse_NmiUpload; preserves Y, DBR=$00, $4314=#$7E, M8/X16.
; Out: C=1 -> skip 1 KB animated-tile DMA this NMI; C=0 -> allow animated tiles normally.
KORL_NmiUpload:
{
  ; Fast-exit when KORL is inactive, Page 0 clean, and no docked boat active (~24 cycles!).
  LDA.l KORL_PalLoaded : BMI .mounted
  LDA.l KORL_UploadedFrame : CMP.b #$FF : BNE .restore_cells
  ; Unmounted + Page 0 clean -> maintain visibly docked boat on Page 1 $5C00/$5D00 (<= 516 B!)
  JML KORL_NmiDockedBoat

  .restore_cells
  ; Dismount or unsafe $0E overlay: restore 256 B native arrow cells ($42A0/$43A0).
  ; Native Link DMA ($008A12) already restored $4000-$41DF (including $40A0/$41A0).
  PHY
  LDA.b #HorseItemRestore>>16 : STA.w $4304
  LDY.w #$0080 : LDA.b #$01
  LDX.w #HorseItemRestore+64  : STX.w $4302
  LDX.w #$42A0 : STX.w $2116 : STY.w $4305 : STA.w $420B
  LDX.w #HorseItemRestore+256 : STX.w $4302
  LDX.w #$43A0 : STX.w $2116 : STY.w $4305 : STA.w $420B
  LDA.b #$FF : STA.l KORL_UploadedFrame
  PLY
  SEC : RTL

  .mounted
  ; Consume same-NMI grant bit 7; preserve palette bit 0.
  AND.b #$7F : STA.l KORL_PalLoaded
  ; Clamp desired frame -> A (0..11, fallback 4 = Side Cruise A).
  LDA.l KORL_Frame : CMP.b #!KORL_FrameCount : BCC + : LDA.b #4 : +
  CMP.l KORL_UploadedFrame : BNE .upload

  ; Steady mounted frame (0 B mounted DMA!): if docked Page 1 backup is still live from
  ; re-boarding 1 frame ago, restore $5C00/$5D00 (512 B <= 960 B!) cleanly now!
  LDA.l KORL_DockState : BEQ .steady_check
    CMP.b #$A2 : BNE .clear_dock_only
      JML KORL_DockRestoreVram        ; restores 512B if sheet matches, returns SEC : RTL
    .clear_dock_only
    LDA.b #$00 : STA.l KORL_DockState
    LDA.b #$FF : STA.l KORL_DockUploaded
  .steady_check
  ; Guard crowded steady frames (scroll+palette/stripes) identically to Epona.
  LDA.b $17 : BNE .steady_heavy
  LDA.b $14 : BEQ .steady_ok
  LDA.b $15 : BNE .steady_skip
  .steady_ok
  CLC : RTL
  .steady_heavy
  LDA.b $14 : ORA.b $15 : BEQ .steady_ok
  .steady_skip
  SEC : RTL

  .upload
  PHY
  ; DP $06 = new_frame (16-bit, hi=0); DP $04 = new_frame * 10 (GroupPointers offset).
  REP #$20
  AND.w #$00FF : STA.b $06
  ASL : STA.b $04                     ; *2
  ASL #2 : CLC : ADC.b $04 : STA.b $04 ; *8 + *2 = *10
  SEP #$20

  ; Compute old_frame * 10 on stack (or $FFFF if no resident frame) for per-group dedup!
  LDA.l KORL_UploadedFrame : CMP.b #!KORL_FrameCount : BCC .have_old
    REP #$20 : LDA.w #$FFFF : PHA : SEP #$20
    BRA .set_bank
  .have_old
  REP #$20
  AND.w #$00FF : PHA
  ASL : STA 1, S                      ; *2
  ASL #2 : CLC : ADC 1, S : STA 1, S  ; *10 -> 1,S = old_off!
  SEP #$20

  .set_bank
  LDA.b #KORL_Graphics>>16 : STA.w $4304 : STA.w $4314

  ; --- Group 0: Hull 4x16x16 -> $4000/$4100 (512 B in 2 hardware auto-inc bursts) ---
  REP #$20
  LDA 1, S : BMI .dma_hull            ; old_off == $FFFF -> must upload
  TAX
  LDA.l KORL_Frame_GroupPointers+0, X : PHA
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+0, X
  CMP 1, S : BEQ .skip_hull_pop
  STA.w $4302
  PLA
  SEP #$20
  BRA .dma_hull_go
  .skip_hull_pop
  PLA
  SEP #$20
  BRA .after_hull
  .dma_hull
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+0, X : STA.w $4302
  SEP #$20
  .dma_hull_go
  LDX.w #$0100 : LDA.b #$01
  LDY.w #$4000 : STY.w $2116 : STX.w $4305 : STA.w $420B
  LDY.w #$4100 : STY.w $2116 : STX.w $4305 : STA.w $420B
  .after_hull

  ; --- Group 1: Seated Link Rider 1x16x16 -> $4080/$4180 (128 B in 2 auto-inc bursts) ---
  REP #$20
  LDA 1, S : BMI .dma_rider
  TAX
  LDA.l KORL_Frame_GroupPointers+2, X : PHA
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+2, X
  CMP 1, S : BEQ .skip_rider_pop
  STA.w $4302
  PLA
  SEP #$20
  BRA .dma_rider_go
  .skip_rider_pop
  PLA
  SEP #$20
  BRA .after_rider
  .dma_rider
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+2, X : STA.w $4302
  SEP #$20
  .dma_rider_go
  LDX.w #$0040 : LDA.b #$01
  LDY.w #$4080 : STY.w $2116 : STX.w $4305 : STA.w $420B
  LDY.w #$4180 : STY.w $2116 : STX.w $4305 : STA.w $420B
  .after_rider

  ; --- Group 2: Wind Waker Sail (320 B: CH0+CH1 $42A0/$42C0 256B + narrow $40A0/$41A0 64B) ---
  LDX.b $06
  LDA.l KORL_Frame_HasSail, X : BNE +
    BRL .after_sail
  +
  ; Check if old resident frame ALREADY had this exact Sail0 pointer!
  REP #$20
  LDA 1, S : BMI .dma_sail
  SEP #$20
  LDA.l KORL_UploadedFrame : REP #$20 : AND.w #$00FF : TAX : SEP #$20
  LDA.l KORL_Frame_HasSail, X : BEQ .dma_sail16
  REP #$20
  LDA 1, S : TAX
  LDA.l KORL_Frame_GroupPointers+4, X : PHA
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+4, X
  CMP 1, S : BEQ .skip_sail_pop
  PLA
  BRA .dma_sail
  .skip_sail_pop
  PLA
  SEP #$20
  BRA .after_sail
  .dma_sail16
  REP #$20
  .dma_sail
  LDX.b $04
  LDA.l KORL_Frame_GroupPointers+4, X : STA.w $4302 ; Sail0 (128B -> $42A0/$43A0)
  LDA.l KORL_Frame_GroupPointers+6, X : STA.w $4312 ; Sail1 (128B -> $42C0/$43C0)
  SEP #$20
  LDX.w #$0040 : LDA.b #$03
  LDY.w #$42A0 : STY.w $2116 : STX.w $4305 : STX.w $4315 : STA.w $420B
  LDY.w #$43A0 : STY.w $2116 : STX.w $4305 : STX.w $4315 : STA.w $420B
  ; Narrow 8x16 Sail tip (64B -> $40A0 TL 32B, $41A0 BL 32B via hardware auto-inc; Rupee $40B0 untouched!)
  LDX.b $04
  REP #$20
  LDA.l KORL_Frame_GroupPointers+8, X : STA.w $4302
  SEP #$20
  LDX.w #$0020 : LDA.b #$01
  LDY.w #$40A0 : STY.w $2116 : STX.w $4305 : STA.w $420B
  LDY.w #$41A0 : STY.w $2116 : STX.w $4305 : STA.w $420B

  .after_sail
  REP #$20 : PLA : SEP #$20           ; pop old_off word
  LDA.b #$7E : STA.w $4314            ; restore native DMA1 bank invariant
  LDA.b $06  : STA.l KORL_UploadedFrame
  PLY
  SEC : RTL                           ; skip 1 KB animated tiles on KORL upload frame!
}

; ---------------------------------------------------------
; Player OAM Renderer (called via JML from Horse_PlayerOamHook)
; Entry: M=8, X=8, DBR=$0D, caller DBR stacked above PlayerOam_Main JSL return.
; ---------------------------------------------------------
KORL_PlayerOamHook:
{
  LDA.l KORL_Marker : CMP.b #(!KORL_MagicMarker&$FF) : BNE .native_oam
  LDA.l KORL_Marker+1 : CMP.b #(!KORL_MagicMarker>>8) : BNE .native_oam
  LDA.l KORL_Mounted : BEQ .native_oam
  ; Exact same eligibility check as KORL_LinkDmaPrefix -> ZERO CHR mismatch glitch frames!
  LDA.b $1B : BNE .native_oam
  LDA.b $10 : CMP.b #$09 : BEQ .chk_busy
  CMP.b #$0B : BEQ .chk_busy
  CMP.b #$0E : BNE .native_oam
  JSL Horse_IsSafeOverlay : BCC .native_oam
  .chk_busy
  JSL KORL_SlotsBusy : BCS .native_oam
  JSL KORL_DrawPlayerOam_Long
  PLA : PLA : PLA                     ; drop JSL return inside PlayerOam_Main
  PLB                                 ; pop PlayerOam_Main entry PHB
  RTL
  .native_oam
  LDY.b #$00 : LDA.b $11
  RTL
}

KORL_HullChr:
  db $00, $02, $04, $06

KORL_DrawPlayerOam_Long:
{
  PHB : PHP
  SEP #$20 : LDA.b #$00 : PHA : PLB   ; DBR=$00 mirrors WRAM $0000..$1FFF

  ; Setup $64 priority and $0352 OAM offset matching PlayerOam_Main ($0DA120/$0DA126).
  REP #$30
  LDA.b $EE : AND.w #$0003 : ASL : TAX
  LDA.l $0DA126, X : STA.b $64
  LDA.w $0FB3 : AND.w #$00FF : CMP.w #$0003 : BCC +
    LDA.w #$0002
  +
  ASL : TAX
  LDA.l $0DA120, X : STA.w $0352

  ; Base screen origin: SX16 = $22 - $E2, SY16 = $20 - $E8
  LDA.b $22 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $20 : SEC : SBC.b $E8 : STA.b $02

  SEP #$20
  LDA.b $65 : STA.b $64               ; unified water-surface OBJ priority

  ; Handle invincibility blink ($031F) & invisible state ($4B == $0C / $55 != 0).
  LDA.b $11 : BNE .chk_vis
  LDA.w $031F : BEQ .chk_vis
    DEC : STA.w $031F
    CMP.b #$04 : BCC .chk_vis
    AND.b #$01 : BEQ .hide_all
  .chk_vis
  LDA.b $4B : CMP.b #$0C : BEQ .hide_all
  LDA.b $55 : BNE .hide_all
  BRA .draw_visible

  .hide_all
  REP #$30
  JSR KORL_OamHideAll
  BRL .exit

  .draw_visible
  ; Hold resident frame on scroll-row frames ($17 == $03) to preserve VBlank headroom!
  LDA.b $17 : CMP.b #$03 : BNE .frame_ok
  LDA.b $11 : BNE .frame_ok
  LDA.l KORL_UploadedFrame : CMP.b #!KORL_FrameCount : BCS .frame_ok
  STA.l KORL_Frame
  .frame_ok
  LDA.l KORL_Frame : CMP.b #!KORL_FrameCount : BCC + : LDA.b #4 : +
  STA.b $0D                           ; DP $0D = validated frame ID (0..11)

  REP #$30
  AND.w #$00FF : TAX
  ; BaseX ($04) = SX16 + 8 - (Width >> 1)
  LDA.l KORL_Frame_Width, X : AND.w #$00FF : LSR : STA.b $08
  LDA.b $00 : CLC : ADC.w #8 : SEC : SBC.b $08 : STA.b $04
  ; BaseY ($06) = SY16 + 24 - Height
  LDA.l KORL_Frame_Height, X : AND.w #$00FF : STA.b $08
  LDA.b $02 : CLC : ADC.w #24 : SEC : SBC.b $08 : STA.b $06
  LDY.w $0352

  ; 1. Frontmost: Wind Waker Sail (if HasSail != 0 -> 4 OAM slots: $2A, $2C, $0A, $1A)
  SEP #$20
  LDA.l KORL_Frame_HasSail, X : BEQ .no_sail
    JSR KORL_EmitSail
  .no_sail

  ; 2. Hull + Seated Link Rider ordering (lower OAM slot draws IN FRONT!):
  ;    - Side ($2F == $04/$06): Hull FIRST (white gunwale overlaps Link's waist!), then Rider.
  ;    - Up/Down ($2F == $00/$02): Rider FIRST (Link sits atop open interior deck), then Hull.
  SEP #$20
  LDA.b $2F : AND.b #$04 : BEQ .vertical_order
    JSR KORL_EmitHull
    JSR KORL_EmitRider
    BRA .clear_unused
  .vertical_order
    JSR KORL_EmitRider
    JSR KORL_EmitHull

  .clear_unused
  ; Clear remaining player OAM slots up to 12 entries (48 bytes).
  REP #$30
  TYA : SEC : SBC.w $0352 : CMP.w #48 : BCS .exit
  .clear_loop
    LDA.w #$F000 : STA.w $0800, Y
    TYA : LSR #2 : TAX
    SEP #$20 : LDA.b #$01 : STA.w $0A20, X : REP #$20
    INY #4
    TYA : SEC : SBC.w $0352 : CMP.w #48 : BCC .clear_loop

  .exit
  PLP : PLB
  RTL
}

; Emits 16x16 Seated Link Rider ($08, SP-7 $0E / H-flip $4E on Left $2F==4).
KORL_EmitRider:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : TAX
  SEP #$20
  LDA.l KORL_Rider_X, X : STA.b $08
  LDA.l KORL_Rider_Y, X : STA.b $09
  LDA.b #$08 : STA.b $0B              ; CHR $08
  LDA.b $2F : CMP.b #$04 : BNE .no_flip
    LDA.l KORL_Frame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
    LDA.b #$4E : BRA .attr_ok         ; H-flip + SP-7
  .no_flip
  LDA.b #$0E                          ; SP-7, no flip
  .attr_ok
  ORA.b $64 : STA.b $0A
  LDA.b #$02 : STA.b $0C              ; 16x16 size
  JMP KORL_EmitSignedPiece
}

; Emits 4 x 16x16 Boat Hull pieces ($00,$02,$04,$06, SP-3 $06 / H-flip $46 on Left $2F==4).
KORL_EmitHull:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : ASL #2 : TAX
  .loop
    PHX
    SEP #$20
    LDA.l KORL_Piece_X, X : STA.b $08
    LDA.l KORL_Piece_Y, X : STA.b $09
    TXA : AND.b #$03 : REP #$20 : AND.w #$00FF : TAX : SEP #$20
    LDA.l KORL_HullChr, X : STA.b $0B
    LDA.b #$06 : STA.b $0A            ; SP-3, no flip
    LDA.b $2F : CMP.b #$04 : BNE .no_flip
      REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
      LDA.l KORL_Frame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
      LDA.b #$46 : STA.b $0A          ; H-flip + SP-3
    .no_flip
    LDA.b $0A : ORA.b $64 : STA.b $0A
    LDA.b #$02 : STA.b $0C            ; 16x16 size
    JSR KORL_EmitSignedPiece
    PLX : INX
    REP #$20 : TXA : AND.w #$0003 : BNE .loop
  RTS
}

; Emits Wind Waker Sail: 2 x 16x16 ($2A, $2C) + narrow 8x16 ($0A top, $1A bot), SP-3.
KORL_EmitSail:
{
  REP #$30
  LDA.b $0D : AND.w #$00FF : ASL #2 : TAX
  ; Sail 0 (16x16 CHR $2A)
  PHX
  SEP #$20
  LDA.l KORL_Sail_X+0, X : STA.b $08
  LDA.l KORL_Sail_Y+0, X : STA.b $09
  LDA.b #$2A : STA.b $0B
  JSR .emit_16
  PLX
  ; Sail 1 (16x16 CHR $2C)
  PHX
  SEP #$20
  LDA.l KORL_Sail_X+1, X : STA.b $08
  LDA.l KORL_Sail_Y+1, X : STA.b $09
  LDA.b #$2C : STA.b $0B
  JSR .emit_16
  PLX
  ; Sail Narrow (8x16 -> two 8x8 OAM entries: $0A top, $1A bot)
  SEP #$20
  LDA.l KORL_Sail_X+2, X : STA.b $08
  LDA.l KORL_Sail_Y+2, X : STA.b $09
  LDA.b #$06 : STA.b $0A
  LDA.b $2F : CMP.b #$04 : BNE .narrow_no_flip
    REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
    LDA.l KORL_Frame_Width, X : SEC : SBC.b #8 : SEC : SBC.b $08 : STA.b $08
    LDA.b #$46 : STA.b $0A
  .narrow_no_flip
  LDA.b $0A : ORA.b $64 : STA.b $0A
  STZ.b $0C                           ; 8x8 size
  LDA.b #$0A : STA.b $0B              ; top 8x8 CHR $0A
  LDA.b $09 : PHA
  REP #$20
  LDA.b $08 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $04 : STA.b $08
  SEP #$20 : PLA : REP #$20 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $06 : STA.b $0E
  JSR KORL_OamWriteSlot
  INY #4
  SEP #$20
  LDA.b #$1A : STA.b $0B              ; bot 8x8 CHR $1A
  REP #$20
  LDA.b $0E : CLC : ADC.w #$0008 : STA.b $0E
  JSR KORL_OamWriteSlot
  INY #4
  RTS

  .emit_16
  LDA.b #$06 : STA.b $0A
  LDA.b $2F : CMP.b #$04 : BNE .s16_no_flip
    REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
    LDA.l KORL_Frame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
    LDA.b #$46 : STA.b $0A
  .s16_no_flip
  LDA.b $0A : ORA.b $64 : STA.b $0A
  LDA.b #$02 : STA.b $0C
  JMP KORL_EmitSignedPiece
}

; Sign-extends 8-bit $08/$09, adds BaseX ($04) / BaseY ($06), writes OAM slot, advances Y += 4.
; In: M=8, X=16, DBR=$00. Out: M=16, X=16.
KORL_EmitSignedPiece:
{
  LDA.b $09 : PHA
  REP #$20
  LDA.b $08 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $04 : STA.b $08
  SEP #$20 : PLA : REP #$20 : AND.w #$00FF
  BIT.w #$0080 : BEQ + : ORA.w #$FF00 : +
  CLC : ADC.b $06 : STA.b $0E
  JSR KORL_OamWriteSlot
  INY #4
  RTS
}

; Writes one OAM slot at Y ($0800+Y) and hi-table $0A20+(Y>>2). M=16, X=16, DBR=$00.
KORL_OamWriteSlot:
{
  LDA.b $0E : CLC : ADC.w #$0010 : CMP.w #$0100 : BCS .offscreen
  LDA.b $08 : CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .offscreen

  SEP #$20
  LDA.b $08 : STA.w $0800, Y
  LDA.b $0E : STA.w $0801, Y
  LDA.b $0B : STA.w $0802, Y
  LDA.b $0A : STA.w $0803, Y
  LDA.b $09 : AND.b #$01 : ORA.b $0C : PHA
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
  PLA : STA.w $0A20, X
  REP #$20
  RTS

  .offscreen
  SEP #$20
  LDA.b #$F0 : STA.w $0801, Y
  REP #$20
  TYA : LSR #2 : TAX
  SEP #$20
  LDA.b #$01 : STA.w $0A20, X
  REP #$20
  RTS
}

KORL_OamHideAll:
{
  LDA.w $0352 : LSR #2 : TAX
  LDA.w #$0101
  LDY.w #$0005
  .loop
    STA.w $0A20, X
    INX : INX
    DEY : BPL .loop
  RTS
}

; =========================================================
; Visibly Docked King of Red Lions (Page 1 $5C00/$5D00, <= 516 B NMI!)
; Mirrors Epona's parked off-Ranch VRAM save/restore & OAM conflict safety.
; =========================================================

; NMI handler entered via JML from KORL_NmiUpload when unmounted & Page 0 is clean.
; Entry: M=8, X=16, DBR=$00; DP $04/$06 already saved by Horse_NmiUpload; preserves Y & $4314=#$7E.
; Out: C=1 -> skip 1 KB animated-tile DMA this NMI; C=0 -> allow animated tiles normally.
KORL_NmiDockedBoat:
{
  ; Ultra-fast exit when uninitialized or no anchor and Page 1 is clean!
  REP #$20 : LDA.l KORL_Marker : CMP.w #!KORL_MagicMarker : SEP #$20 : BEQ .init_ok
    CLC : RTL
  .init_ok
  LDA.l KORL_HasAnchor : ORA.l KORL_DockState : BNE .active
    CLC : RTL
  .active

  ; Safe Overworld-overlay $0E (Pause Menu / Dialogue / Save Menu): hold $5C00/$5D00 untouched!
  LDA.b $10 : CMP.b #$0E : BNE .not_overlay
    JSL Horse_IsSafeOverlay : BCC .unwant
    CLC : RTL
  .not_overlay
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .unwant
  .mod_ok
  LDA.b $1B : ORA.b $11 : BNE .unwant
  LDA.l KORL_HasAnchor : BEQ .unwant
  LDA.b $8A : CMP.l KORL_AnchorArea : BNE .unwant
  LDA.l InCutScene : BNE .unwant
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BNE .unwant
endif
  LDA.l KORL_DockClear : CMP.b #$02 : BCC .unwant

  ; Eligible! Check whether Page 1 Slot 3 ($7EC2FF) still matches our backup.
  LDA.l $7EC2FF : CMP.l KORL_DockSheet : BNE .save_vram
  LDA.l KORL_DockState : CMP.b #$A2 : BEQ .check_upload
  CMP.b #$A1 : BNE .save_vram
  ; Promote $A1 (saved last NMI) -> $A2 and fall through to upload empty hull (512 B)!
  LDA.b #$A2 : STA.l KORL_DockState
  LDA.b #$FF : STA.l KORL_DockUploaded

  .check_upload
  ; Clamp desired empty-hull frame (0..5: Down/Up/Side A/B)
  LDA.l KORL_DockFrame : CMP.b #$06 : BCC + : LDA.b #$04 : +
  CMP.l KORL_DockUploaded : BEQ +
    BRL .upload_hull
  +

  ; Steady docked frame (0 B DMA!) — guard crowded scroll+palette frames identically to Epona.
  LDA.b $17 : BNE .steady_heavy
  LDA.b $14 : BEQ .steady_ok
  LDA.b $15 : BNE .steady_skip
  .steady_ok
  CLC : RTL
  .steady_heavy
  LDA.b $14 : ORA.b $15 : BEQ .steady_ok
  .steady_skip
  SEC : RTL

  .unwant
  LDA.l KORL_DockState : CMP.b #$A2 : BNE .clear_only
    JML KORL_DockRestoreVram
  .clear_only
  LDA.b #$00 : STA.l KORL_DockState
  LDA.b #$FF : STA.l KORL_DockUploaded
  CLC : RTL

  ; Save Page 1 $5C00-$5C7F (256B+2B prefetch) + $5D00-$5D7F (256B+2B prefetch) = 516 B!
  .save_vram
  PHY
  LDA.b #$81 : STA.w $4300            ; B->A VRAM read ($2139/$213A)
  LDA.b #$39 : STA.w $4301
  LDA.b #KORL_DockDma0>>16 : STA.w $4304
  LDY.w #$0102 : LDA.b #$01
  LDX.w #KORL_DockDma0 : STX.w $4302 : STY.w $4305
  LDX.w #$5C00 : STX.w $2116 : STA.w $420B
  LDX.w #KORL_DockDma1 : STX.w $4302 : STY.w $4305
  LDX.w #$5D00 : STX.w $2116 : STA.w $420B
  ; Restore native DMA0 mode (A->B $2118/9, bank $7E)
  LDA.b #$01 : STA.w $4300
  LDA.b #$18 : STA.w $4301
  LDA.b #$7E : STA.w $4304
  LDA.l $7EC2FF : STA.l KORL_DockSheet
  LDA.b #$A1 : STA.l KORL_DockState
  LDA.b #$FF : STA.l KORL_DockUploaded
  PLY
  SEC : RTL                           ; skip 1 KB animated tiles on 516 B VRAM read NMI!

  ; Upload 4 x 16x16 empty hull -> Page 1 $5C00/$5D00 (512 B in 2 hardware auto-inc bursts!)
  .upload_hull
  PHY
  REP #$20
  AND.w #$00FF : STA.b $06
  ASL : STA.b $04
  ASL #2 : CLC : ADC.b $04 : TAX      ; X = frame * 10 (GroupPointers offset)
  LDA.l KORL_Frame_GroupPointers+0, X : STA.w $4302
  SEP #$20
  LDA.b #KORL_Graphics>>16 : STA.w $4304
  LDX.w #$0100 : LDA.b #$01
  LDY.w #$5C00 : STY.w $2116 : STX.w $4305 : STA.w $420B
  LDY.w #$5D00 : STY.w $2116 : STX.w $4305 : STA.w $420B
  LDA.b #$7E : STA.w $4304            ; restore native DMA0 bank
  LDA.b $06 : STA.l KORL_DockUploaded
  PLY
  SEC : RTL                           ; skip 1 KB animated tiles on 512 B upload NMI!
}

; Restores saved 512 B back into Page 1 $5C00/$5D00 if $7EC2FF still holds the copied sheet.
; Entry: M=8, X=16, DBR=$00; preserves Y. Out: C=1 if 512 B DMA ran, C=0 if no DMA needed.
KORL_DockRestoreVram:
{
  LDA.l KORL_DockState : CMP.b #$A2 : BNE .done_no_dma
  LDA.l $7EC2FF : CMP.l KORL_DockSheet : BNE .done_no_dma
  PHY
  LDA.b #KORL_DockBuf0>>16 : STA.w $4304
  LDY.w #$0100 : LDA.b #$01
  LDX.w #KORL_DockBuf0 : STX.w $4302 : STY.w $4305
  LDX.w #$5C00 : STX.w $2116 : STA.w $420B
  LDX.w #KORL_DockBuf1 : STX.w $4302 : STY.w $4305
  LDX.w #$5D00 : STX.w $2116 : STA.w $420B
  LDA.b #$7E : STA.w $4304
  LDA.b #$00 : STA.l KORL_DockState
  LDA.b #$FF : STA.l KORL_DockUploaded
  PLY
  SEC : RTL
  .done_no_dma
  LDA.b #$00 : STA.l KORL_DockState
  LDA.b #$FF : STA.l KORL_DockUploaded
  CLC : RTL
}

KORL_DockHullChr:
  db $C0, $C2, $C4, $C6

; Frame-end OAM scanner & docked-boat emitter (called from Horse_FrameEndScan .done).
; Preserves all registers, widths, DBR, and DP $00-$0F.
KORL_FrameEndDockedOam:
{
  PHP : PHB
  REP #$30 : PHA : PHX : PHY
  ; Preserve DP $00-$0F cleanly across any module
  LDA.b $00 : PHA : LDA.b $02 : PHA : LDA.b $04 : PHA : LDA.b $06 : PHA
  LDA.b $08 : PHA : LDA.b $0A : PHA : LDA.b $0C : PHA : LDA.b $0E : PHA
  SEP #$20
  LDA.b #$00 : PHA : PLB

  ; Cold-init guard
  REP #$20 : LDA.l KORL_Marker : CMP.w #!KORL_MagicMarker : SEP #$20 : BEQ .marker_ok
    BRL .exit
  .marker_ok

  ; Module $0E overlay: safe overlays keep docked boat OAM frozen behind menu;
  ; unsafe overlays hide docked OAM immediately BEFORE NMI restores $5C00/$5D00 (0 glitch frames!).
  LDA.b $10 : CMP.b #$0E : BNE .not_overlay
    JSL Horse_IsSafeOverlay : BCS .exit_near
    BRL .hide_reset
  .exit_near
    BRL .exit
  .not_overlay

  ; On non-$0E frames, Oam_Clear wiped $0800-$09FF at frame start -> clear old OAM pointer first.
  CMP.b #$09 : BEQ .mod_ok
  CMP.b #$0B : BNE .hide_tramp
  .mod_ok
  LDA.b $1B : ORA.b $11 : BNE .hide_tramp
  LDA.l KORL_Mounted : BNE .hide_tramp
  LDA.l KORL_HasAnchor : BEQ .hide_tramp
  LDA.b $8A : CMP.l KORL_AnchorArea : BNE .hide_tramp
  LDA.l InCutScene : BNE .hide_tramp
if !ENABLE_HORSE_FORM == 1
  LDA.l Horse_NpcActive : BNE .hide_tramp
endif

  ; Reset previous-frame OAM record before scanning finished OAM buffer for Page 1 $C0-$C7/$D0-$D7 conflicts!
  LDA.b #$00 : STA.l KORL_DockOam : STA.l KORL_DockOam+1
  REP #$10
  LDX.w #$01FC
  .scan_oam
    LDA.w $0801, X : CMP.b #$F0 : BEQ .scan_next
    LDA.w $0803, X : LSR : BCC .scan_next          ; page 0 -> safe
    LDA.w $0802, X : AND.b #$E8 : CMP.b #$C0 : BEQ .hide_tramp ; Page 1 $C0-$C7 or $D0-$D7 -> yield!
    .scan_next
    DEX #4
    BPL .scan_oam
  BRA .scan_clean
  .hide_tramp
    BRL .hide_reset
  .scan_clean

  ; Clean OAM scan! Increment consecutive clear counter (saturating at $FF).
  LDA.l KORL_DockClear : INC : BEQ + : STA.l KORL_DockClear : +

  ; Only draw docked OAM once Page 1 $5C00/$5D00 tiles are resident (KORL_DockState == $A2 & Uploaded < 6)!
  LDA.l KORL_DockState : CMP.b #$A2 : BNE .exit_near
  LDA.l KORL_DockUploaded : CMP.b #$06 : BCS .exit_near
  STA.b $0D                           ; DP $0D = resident docked empty-hull frame (0..5)

  ; Find 4 contiguous free OAM slots (Y == #$F0), scanning backwards from $09F0 down to $0900
  ; (tail of OAM -> Link & HUD always render cleanly IN FRONT of the moored boat!).
  REP #$10
  LDY.w #$01F0                        ; $0800 + $01F0 = $09F0 (slots 124..127)
  .find_slots
    LDA.w $0801, Y : CMP.b #$F0 : BNE .next_block
    LDA.w $0805, Y : CMP.b #$F0 : BNE .next_block
    LDA.w $0809, Y : CMP.b #$F0 : BNE .next_block
    LDA.w $080D, Y : CMP.b #$F0 : BEQ .got_slots
    .next_block
    REP #$20
    TYA : SEC : SBC.w #$0010 : CMP.w #$0100 : BCC .no_slots
    TAY
    SEP #$20
    BRA .find_slots
  .no_slots
  SEP #$20
  BRL .exit

  .got_slots
  ; Record absolute OAM address ($0800 + Y) for unsafe-$0E hide guard.
  REP #$20
  TYA : CLC : ADC.w #$0800 : STA.l KORL_DockOam
  ; Base screen origin: SX16 = AnchorX - $E2, SY16 = AnchorY - $E8 (matches mounted KORL pixel-for-pixel!)
  LDA.l KORL_AnchorX : SEC : SBC.b $E2 : STA.b $00
  LDA.l KORL_AnchorY : SEC : SBC.b $E8 : STA.b $02
  ; BaseX ($04) = SX16 + 8 - (Width >> 1); BaseY ($06) = SY16 + 24 - Height
  LDA.b $0D : AND.w #$00FF : TAX
  LDA.l KORL_Frame_Width, X : AND.w #$00FF : LSR : STA.b $08
  LDA.b $00 : CLC : ADC.w #8 : SEC : SBC.b $08 : STA.b $04
  LDA.l KORL_Frame_Height, X : AND.w #$00FF : STA.b $08
  LDA.b $02 : CLC : ADC.w #24 : SEC : SBC.b $08 : STA.b $06

  ; Emit 4 x 16x16 empty hull pieces ($C0, $C2, $C4, $C6, Page 1 + SP-3 + priority 2 = $27 / H-flip $67)!
  LDA.b $0D : AND.w #$00FF : ASL #2 : TAX
  .emit_loop
    PHX
    SEP #$20
    LDA.l KORL_Piece_X, X : STA.b $08
    LDA.l KORL_Piece_Y, X : STA.b $09
    TXA : AND.b #$03 : REP #$20 : AND.w #$00FF : TAX : SEP #$20
    LDA.l KORL_DockHullChr, X : STA.b $0B
    LDA.b #$27 : STA.b $0A            ; Priority 2 ($20) + SP-3 ($06) + Page 1 ($01)
    LDA.l KORL_AnchorDir : CMP.b #$04 : BNE .no_flip
      REP #$20 : LDA.b $0D : AND.w #$00FF : TAX : SEP #$20
      LDA.l KORL_Frame_Width, X : SEC : SBC.b #16 : SEC : SBC.b $08 : STA.b $08
      LDA.b #$67 : STA.b $0A          ; H-flip ($40) + Priority 2 ($20) + SP-3 ($06) + Page 1 ($01)
    .no_flip
    LDA.b #$02 : STA.b $0C            ; 16x16 size
    JSR KORL_EmitSignedPiece
    PLX : INX
    REP #$20 : TXA : AND.w #$0003 : BNE .emit_loop
  SEP #$20
  BRA .exit

  .conflict
  .hide_reset
  JSR KORL_HideDockedOam
  LDA.b #$00 : STA.l KORL_DockClear

  .exit
  REP #$30
  PLA : STA.b $0E : PLA : STA.b $0C : PLA : STA.b $0A : PLA : STA.b $08
  PLA : STA.b $06 : PLA : STA.b $04 : PLA : STA.b $02 : PLA : STA.b $00
  PLY : PLX : PLA
  PLB : PLP
  RTL
}

; Hides the 4 docked boat OAM slots immediately (called on unsafe $0E / map exit / conflict).
; Entry: M=8, DBR=$00. Preserves nothing except DBR.
KORL_HideDockedOam:
{
  REP #$30
  LDA.l KORL_DockOam : CMP.w #$0800 : BCC .done
  CMP.w #$09F1 : BCS .done
  TAX
  SEP #$20
  LDA.b #$F0
  STA.w $0001, X
  STA.w $0005, X
  STA.w $0009, X
  STA.w $000D, X
  .done
  SEP #$20
  LDA.b #$00 : STA.l KORL_DockOam : STA.l KORL_DockOam+1
  RTS
}
KORL_CodeEnd:
