; =========================================================
; Ending credits: Oracle overworld scenes before the staff roll.
;
; Vanilla Module1A plays 16 scenes (subs $00-$1F) and then the staff roll
; (sub $20). Each scene loads its camera from an UnderworldExitData record,
; but Oracle reused those records, so the vanilla scan never matches and hangs.
; This file:
;   1. Hooks LoadOverworldFromUnderworld's record scan: during credits ($10 =
;      $1A) the camera comes from OracleCredits_* tables below instead.
;   2. Plays !OracleCredits_SceneCount scenes, all overworld, with centered BG3
;      location captions, animated scene NPCs (matched to each scene's loaded
;      spriteset), and Scene 7's volcanic emerald-moss grass palette fix, then
;      jumps to the staff roll.
;   3. Patches the vanilla per-scene tables (spritesets, palettes, pan, timer).
;
; Scenes (camera pans 96 px and ends on the chosen view):
;   0 Loom Ranch       area $00  pan right  (Ranch Girl, Rancher, two Cuccos, Cat)
;   1 Wayward Village  area $23  pan down   (Village Dog, Girl, Villager, Cat)
;   2 Hall of Secrets  area $0E  pan right  (Farore, Eon Owl, Cat)
;   3 Kalyxo Castle    area $0B  pan up     (Castle Guards, Maiden; clean framing)
;   4 Loom Beach       area $33  pan left   (Beach Girl, Villager, Cat)
;   5 Zora Island      area $1E  pan down   (three D4 River Zoras in the bay)
;   6 Goron Mines      area $36  pan up     (two cheering Kalyxo Gorons)
;   7 The Eon Abyss    area $46  pan down   (growing sapling + emerald-moss grass)
; Included from Overworld/overworld.asm (bank $34 free space).

!OracleCredits_SceneCount = 8

; Camera values as Oracle's ZScream exits compute them from the scroll position.
function credits_map_x(area) = (area&$07)<<9
function credits_map_y(area) = (area&$38)<<6
function credits_vram(area, sy, sx) = (((sy-credits_map_y(area))&$FFF0)<<3)|(((sx-credits_map_x(area))&$FFF0)>>3)

; Start scroll (top-left of the camera), per scene.
; Scene 3 ($0B Kalyxo Castle) starts at $0300 -> pans up to $02A0 so the grand
; entrance & flower courtyard fill the frame cleanly above the southern blocks.
OracleCredits_Area:
  db $00, $23, $0E, $0B, $33, $1E, $36, $46
OracleCredits_ScrollY:
  dw $00C0, $08E0, $0220, $0300, $0EA0, $0630, $0E00, $0030
OracleCredits_ScrollX:
  dw $01A0, $0700, $0C20, $0740, $0760, $0C30, $0C80, $0C70
OracleCredits_Vram:
  dw credits_vram($00, $00C0, $01A0)
  dw credits_vram($23, $08E0, $0700)
  dw credits_vram($0E, $0220, $0C20)
  dw credits_vram($0B, $0300, $0740)
  dw credits_vram($33, $0EA0, $0760)
  dw credits_vram($1E, $0630, $0C30)
  dw credits_vram($36, $0E00, $0C80)
  dw credits_vram($46, $0030, $0C70)

; Replaces `LDX.b #$9E : DEX : DEX` at LoadOverworldFromUnderworld_custom_exit.
; M=16, X=8, DBR=$02, A = $A0 (exit room id).
; The vanilla scan loop branches back to $02E4D6, which is inside the JML
; operand, so the whole scan runs here and returns past the BNE at $02E4DD.
OracleCredits_ExitHook:
{
  LDX.b $10 : CPX.b #$1A : BEQ .credits
    LDX.b #$9E
    .next_room_check
    DEX : DEX
    CMP.l $02DD8A, X ; UnderworldExitData room id
    BEQ .found_exit
    CPX.b #$00 : BNE .next_room_check
    ; Room has no row in UnderworldExitData: fall back to cached entrance
    ; properties ($02E4CE) instead of wrapping 8-bit X ($00 -> $FE).
    JML $02E4CE
    .found_exit
    JML $02E4DD

  .credits
  LDA.b $11 : AND.w #$00FE : TAX
  LDA.l OracleCredits_ScrollY, X
  STA.b $E6 : STA.b $E8 : STA.w $0122 : STA.w $0124
  CLC : ADC.w #$0050 : STA.b $20                    ; Link Y = scroll + 80
  CLC : ADC.w #$001F : STA.w $0618                  ; camera Y = Link Y + 31
  DEC A : DEC A : STA.w $061A
  LDA.l OracleCredits_ScrollX, X
  STA.b $E0 : STA.b $E2 : STA.w $011E : STA.w $0120
  CLC : ADC.w #$0078 : STA.b $22                    ; Link X = scroll + 120
  CLC : ADC.w #$0007 : STA.w $061C                  ; camera X = Link X + 7
  DEC A : DEC A : STA.w $061E

  LDA.l OracleCredits_Vram, X : STA.b $84
  SEC : SBC.w #$0400 : AND.w #$0F80 : ASL A : XBA : STA.b $88
  LDA.b $84 : SEC : SBC.w #$0010 : AND.w #$003E : LSR A : STA.b $86

  LDA.w #$0002 : STA.b $2F
  STZ.w $0696 : STZ.w $0698                         ; no door to redraw
  STZ.w $0624 : STZ.w $0626 : STZ.w $0628 : STZ.w $062A ; scroll aligned to 16 px

  TXA : LSR A : TAX
  SEP #$20
  LDA.l OracleCredits_Area, X : STA.b $8A : STA.w $040A
  STZ.b $8B : STZ.w $040B
  REP #$20
  JML $02E58A ; Overworld_LoadNewScreenProperties_pre (PLB, then M=16 code)
}

; Replaces Credits_LoadNextScene_Overworld. M=8, X=8.
OracleCredits_LoadNextScene:
{
  LDA.b $11 : CMP.b #!OracleCredits_SceneCount*2 : BCC .scene
    LDA.b #$20 : STA.b $11                          ; staff roll
    RTL

  .scene
  JSL $0285BA ; Credits_LoadScene_Overworld
  JSR OracleCredits_PatchScenePalette
  JSR OracleCredits_UploadCaption
  RTL
}

; Scene 7 ($46 Abyss grass patch) grass palette fix: replace the harsh neon
; chartreuse ($0965/$1E6E/$1A53/$2B4D) in BG rows 2 & 6 with a moody volcanic
; emerald-moss ramp ($1143/$1DA6/$2649/$2A8B) that harmonizes with orange lava
; and lets the bright green sprouting sapling stand out cleanly.
!CreditsAbyss_GrassShadow = $1143 ; #185020 deep forest moss
!CreditsAbyss_GrassMid    = $1DA6 ; #306838 rich volcanic emerald-olive
!CreditsAbyss_GrassLight  = $2649 ; #489048 soft healing sage highlight
!CreditsAbyss_GrassAccent = $2A8B ; #58A050 gentle sage edge

OracleCredits_PatchScenePalette:
{
  LDA.b $11 : AND.b #$FE
  CMP.b #$0A : BEQ .zora_scene
  CMP.b #$0E : BEQ .abyss_scene
  RTS

  ; Scene 5 ($1E Zora Island, spriteset $8E): bind D4 River Zora head/body
  ; palettes into OBJ rows 3 & 4 ($7EC462/$7EC662, $7EC482/$7EC682).
  ; Local copy keeps credits independent of feature-flag builds.
  .zora_scene
  PHX
  REP #$20
  LDX.b #$0C
  .zora_loop
    LDA.l OracleCredits_ZoraHeadPal, X
    STA.l $7EC462, X : STA.l $7EC662, X
    LDA.l OracleCredits_ZoraBodyPal, X
    STA.l $7EC482, X : STA.l $7EC682, X
    DEX : DEX : BPL .zora_loop
  SEP #$20
  LDA.b #$01 : STA.b $15
  PLX
  RTS

  .abyss_scene
  REP #$20
  ; BG row 2 colors 5-6 ($4A/$4C)
  LDA.w #!CreditsAbyss_GrassShadow
  STA.l $7EC34A : STA.l $7EC54A
  STA.l $7EC3CA : STA.l $7EC5CA
  LDA.w #!CreditsAbyss_GrassMid
  STA.l $7EC34C : STA.l $7EC54C
  STA.l $7EC3CC : STA.l $7EC5CC
  ; BG row 6 highlight & edge accent ($CE / $C4)
  LDA.w #!CreditsAbyss_GrassLight
  STA.l $7EC3CE : STA.l $7EC5CE
  LDA.w #!CreditsAbyss_GrassAccent
  STA.l $7EC3C4 : STA.l $7EC5C4
  SEP #$20
  LDA.b #$01 : STA.b $15
  RTS
}

OracleCredits_ZoraHeadPal:
  dw $0C63, $2525, $39E5, $46F0, $2F7D, $5B7D, $1ADF
OracleCredits_ZoraBodyPal:
  dw $0C63, $2525, $39E5, $46F0, $1970, $5B7D, $1ADF

; =========================================================
; Per-scene BG3 captions (same format & character table as vanilla $0EC303).
; Clears BG3 ($6000) to CreditsBlankFillTile ($0EB176 = $3CA9), then expands
; the current scene's caption rows (Row 19 small gold + Rows 23-24 big title)
; through Credits_CharacterToTile ($0EB038) into the NMI VRAM queue at $7E1000.
OracleCredits_UploadCaption:
{
  PHB : PHK : PLB
  REP #$30
  ; Clear entire 32x32 BG3 tilemap first.
  LDA.w #$0060 : STA.l $7E1002                      ; VRAM $C000 (word $6000 BE)
  LDA.w #$FE47 : STA.l $7E1004                      ; RLE 1024 words
  LDA.l $0EB176 : STA.l $7E1006                     ; CreditsBlankFillTile ($3CA9)

  LDA.b $11 : AND.w #$00FE : TAY
  LDA.w OracleCredits_CaptionPtrs+2, Y : STA.b $04  ; end offset
  LDA.w OracleCredits_CaptionPtrs, Y : TAY          ; start offset
  LDX.w #$0000
  .next_line
    LDA.w OracleCredits_CaptionData, Y : STA.l $7E1008, X
    INY : INY : INX : INX
    LDA.w OracleCredits_CaptionData, Y : STA.l $7E1008, X
    XBA : AND.w #$00FF : LSR A : STA.b $00          ; chars - 1
    INY : INY : INX : INX
    STY.b $02
    .next_char
      LDY.b $02
      PHX
      LDA.w OracleCredits_CaptionData, Y : AND.w #$00FF : ASL A : TAX
      LDA.l $0EB038, X                              ; Credits_CharacterToTile
      PLX
      STA.l $7E1008, X
      INC.b $02
      INX : INX
      DEC.b $00 : BPL .next_char
    LDY.b $02 : CPY.b $04 : BNE .next_line
  TXA : CLC : ADC.w #$0006 : STA.l $7E1000
  SEP #$20
  LDA.b #$FF : STA.l $7E1008, X
  SEP #$10
  LDA.b #$01 : STA.b $14
  PLB
  RTS
}

OracleCredits_CaptionPtrs:
  dw $0000, $0031, $006B, $00A6, $00DB, $010A, $013C, $016C, $01A1

OracleCredits_CaptionData:
  ; Scene 0: PEACEFUL PASTURES / LOOM RANCH
  db $62, $67, $00, $21, $29, $1E, $1A, $1C, $1E, $1F, $2E, $25, $9F, $29, $1A, $2C, $2D, $2E, $2B, $1E, $2C
  db $62, $EB, $00, $13, $68, $6B, $6B, $69, $9F, $6E, $5D, $6A, $5F, $64
  db $63, $0B, $00, $13, $8E, $91, $91, $8F, $9F, $94, $83, $90, $85, $8A
  ; Scene 1: A QUIET HOMETOWN / WAYWARD VILLAGE
  db $62, $68, $00, $1F, $1A, $9F, $2A, $2E, $22, $1E, $2D, $9F, $21, $28, $26, $1E, $2D, $28, $30, $27
  db $62, $E8, $00, $1D, $73, $5D, $75, $73, $5D, $6E, $60, $9F, $72, $65, $68, $68, $5D, $63, $61
  db $63, $08, $00, $1D, $99, $83, $9B, $99, $83, $94, $86, $9F, $98, $8B, $8E, $8E, $83, $89, $87
  ; Scene 2: ANCIENT SANCTUARY / HALL OF SECRETS
  db $62, $67, $00, $21, $1A, $27, $1C, $22, $1E, $27, $2D, $9F, $2C, $1A, $27, $1C, $2D, $2E, $1A, $2B, $32
  db $62, $E8, $00, $1D, $64, $5D, $68, $68, $9F, $6B, $62, $9F, $6F, $61, $5F, $6E, $61, $70, $6F
  db $63, $08, $00, $1D, $8A, $83, $8E, $8E, $9F, $91, $88, $9F, $95, $87, $85, $94, $87, $96, $95
  ; Scene 3: ROYAL COURTYARD / KALYXO CASTLE
  db $62, $68, $00, $1D, $2B, $28, $32, $1A, $25, $9F, $1C, $28, $2E, $2B, $2D, $32, $1A, $2B, $1D
  db $62, $E9, $00, $19, $67, $5D, $68, $75, $74, $6B, $9F, $5F, $5D, $6F, $70, $68, $61
  db $63, $09, $00, $19, $8D, $83, $8E, $9B, $9A, $91, $9F, $85, $83, $95, $96, $8E, $87
  ; Scene 4: CALM SHORELINES / LOOM BEACH
  db $62, $68, $00, $1D, $1C, $1A, $25, $26, $9F, $2C, $21, $28, $2B, $1E, $25, $22, $27, $1E, $2C
  db $62, $EB, $00, $13, $68, $6B, $6B, $69, $9F, $5E, $61, $5D, $5F, $64
  db $63, $0B, $00, $13, $8E, $91, $91, $8F, $9F, $84, $87, $83, $85, $8A
  ; Scene 5: WATERS OF KALYXO / ZORA ISLAND
  db $62, $68, $00, $1F, $30, $1A, $2D, $1E, $2B, $2C, $9F, $28, $1F, $9F, $24, $1A, $25, $32, $31, $28
  db $62, $EA, $00, $15, $76, $6B, $6E, $5D, $9F, $65, $6F, $68, $5D, $6A, $60
  db $63, $0A, $00, $15, $9C, $91, $94, $83, $9F, $8B, $95, $8E, $83, $90, $86
  ; Scene 6: MOUNTAIN FORGE / GORON MINES
  db $62, $69, $00, $1B, $26, $28, $2E, $27, $2D, $1A, $22, $27, $9F, $1F, $28, $2B, $20, $1E
  db $62, $EA, $00, $15, $63, $6B, $6E, $6B, $6A, $9F, $69, $65, $6A, $61, $6F
  db $63, $0A, $00, $15, $89, $91, $94, $91, $90, $9F, $8F, $8B, $90, $87, $95
  ; Scene 7: NEW LIFE BLOOMS / THE EON ABYSS
  db $62, $68, $00, $1D, $27, $1E, $30, $9F, $25, $22, $1F, $1E, $9F, $1B, $25, $28, $28, $26, $2C
  db $62, $E9, $00, $19, $70, $64, $61, $9F, $61, $6B, $6A, $9F, $5D, $5E, $75, $6F, $6F
  db $63, $09, $00, $19, $96, $8A, $87, $9F, $87, $91, $90, $9F, $83, $84, $9B, $95, $95

; =========================================================
; Animated per-scene credits NPC actor engine (scenes 0-7).
; Called every frame through OracleCredits_ActorVector in bank $0E.
; M=8, X=8, DBR=$0E on entry.
OracleCredits_DrawSceneActors:
{
  PHB : PHK : PLB
  LDA.b $11 : AND.b #$FE : TAX
  JSR (.scene_handlers, X)
  PLB
  RTL

  .scene_handlers
    dw CreditsActors_Scene0_Ranch
    dw CreditsActors_Scene1_Village
    dw CreditsActors_Scene2_Hall
    dw CreditsActors_Scene3_Castle
    dw CreditsActors_Scene4_Beach
    dw CreditsActors_Scene5_Zora
    dw CreditsActors_Scene6_Goron
    dw CreditsActors_Scene7_Abyss
}

; Generic table-driven OAM actor drawer with exact 16-bit screen clipping.
; In: M=8 X=8 DBR=$34, $00-$01 = world X, $02-$03 = world Y,
;     $06-$07 = pointer in bank $34 to tile frame record:
;       db tile_count (1..8)
;       per tile (5 bytes): db dx (signed), db dy (signed), db chr, db props, db size (0 or 2)
; Clobbers A, X, Y, $00-$0F.
CreditsActors_DrawFrame:
{
  ; Screen coordinates = world - scroll ($E2/$E8)
  REP #$20
  LDA.b $00 : SEC : SBC.b $E2 : STA.b $00
  LDA.b $02 : SEC : SBC.b $E8 : STA.b $02
  ; Coarse off-screen reject before allocating OAM
  LDA.b $00 : CLC : ADC.w #$0020 : CMP.w #$0140 : BCS .skip_16
  LDA.b $02 : CLC : ADC.w #$0020 : CMP.w #$0110 : BCC .in_view
  .skip_16
    SEP #$20
    RTS
  .in_view
  SEP #$20

  LDY.b #$00
  LDA.b ($06), Y : STA.b $08                        ; tile count
  REP #$20 : INC.b $06 : SEP #$20
  ASL A : ASL A : JSL OAM_AllocateFromRegionA

  STZ.b $0F                                         ; OAM byte offset (0, 4, 8, ...)
  .tile
    ; Read 5-byte tile record via ($06),Y
    LDY.b #$00
    LDA.b ($06), Y : STA.b $0A                      ; dx
    BPL .dx_pos
      LDA.b #$FF : BRA .dx_hi
    .dx_pos
      LDA.b #$00
    .dx_hi
    STA.b $0B
    INY
    LDA.b ($06), Y : STA.b $0C                      ; dy
    BPL .dy_pos
      LDA.b #$FF : BRA .dy_hi
    .dy_pos
      LDA.b #$00
    .dy_hi
    STA.b $0D
    INY : LDA.b ($06), Y : STA.b $04                ; chr
    INY : LDA.b ($06), Y : STA.b $05                ; props
    INY : LDA.b ($06), Y : STA.b $0E                ; size (0 or 2)

    REP #$20
    LDA.b $00 : CLC : ADC.b $0A : STA.b $0A
    LDA.b $02 : CLC : ADC.b $0C : STA.b $0C
    ; Clip piece if outside [-16..255] x [-16..239]
    LDA.b $0A : CLC : ADC.w #$0010 : CMP.w #$0110 : BCS .hide
    LDA.b $0C : CLC : ADC.w #$0010 : CMP.w #$0100 : BCS .hide
    SEP #$20

    LDY.b $0F
    LDA.b $0A : STA.b ($90), Y : INY
    LDA.b $0C : STA.b ($90), Y : INY
    LDA.b $04 : STA.b ($90), Y : INY                ; chr
    LDA.b $05 : STA.b ($90), Y                      ; props
    LDA.b $0F : LSR A : LSR A : TAY
    LDA.b $0B : AND.b #$01 : ORA.b $0E : STA.b ($92), Y ; x-high | size
    BRA .next

    .hide
    SEP #$20
    LDY.b $0F : INY
    LDA.b #$F0 : STA.b ($90), Y

    .next
    LDA.b $0F : CLC : ADC.b #$04 : STA.b $0F
    REP #$20
    LDA.b $06 : CLC : ADC.w #$0005 : STA.b $06
    SEP #$20
    DEC.b $08 : BEQ .done
    JMP .tile
  .done
  RTS
}

; Compute gentle ping-pong patrol delta in A (signed -16..+15) from ($C8 >> 2) & $3F.
; Returns Carry set when walking left, clear when walking right.
CreditsActors_PingPong16:
{
  REP #$20
  LDA.b $C8 : LSR A : LSR A : AND.w #$003F
  SEP #$20
  CMP.b #$20 : BCS .left
    SEC : SBC.b #$10                                ; -16..+15 (moving right)
    CLC
    RTS
  .left
  EOR.b #$3F : SEC : SBC.b #$10                     ; +15..-16 (moving left)
  SEC
  RTS
}

; Macro to place actor at static world (wx, wy) and draw frame label.
macro credits_actor(wx, wy, frame_lbl)
  REP #$20
  LDA.w #<wx> : STA.b $00
  LDA.w #<wy> : STA.b $02
  LDA.w #<frame_lbl> : STA.b $06
  SEP #$20
  JSR CreditsActors_DrawFrame
endmacro

; ---- Scene 0: Loom Ranch ($00, set $06: $4F/$49/$4A/$50, pal $01) ----
CreditsActors_Scene0_Ranch:
{
  ; 1. Patrolling Ranch Cucco ($50: $EA/$EC) strutting across the green pasture
  JSR CreditsActors_PingPong16
  PHP
  STA.b $04
  BPL .c1_pos
    LDA.b #$FF : BRA .c1_hi
  .c1_pos
    LDA.b #$00
  .c1_hi
  STA.b $05
  REP #$20
  LDA.w #$0270 : CLC : ADC.b $04 : STA.b $00
  LDA.w #$00EE : STA.b $02
  SEP #$20
  PLP : BCS .c1_left
    LDA.b $1A : AND.b #$08 : BNE .c1_r2
      REP #$20 : LDA.w #CreditsGfx_CuccoRightA : BRA .c1_draw
    .c1_r2
      REP #$20 : LDA.w #CreditsGfx_CuccoRightB : BRA .c1_draw
  .c1_left
    LDA.b $1A : AND.b #$08 : BNE .c1_l2
      REP #$20 : LDA.w #CreditsGfx_CuccoLeftA : BRA .c1_draw
    .c1_l2
      REP #$20 : LDA.w #CreditsGfx_CuccoLeftB
  .c1_draw
  STA.b $06 : SEP #$20
  JSR CreditsActors_DrawFrame

  ; 2. Second Cucco pecking happily near the pasture paddock
  LDA.b $1A : AND.b #$10 : BNE .c2_b
    %credits_actor($0286, $00E0, CreditsGfx_CuccoLeftA)
    BRA .girl
  .c2_b
    %credits_actor($0286, $00E0, CreditsGfx_CuccoLeftB)
  .girl
  ; 3. Ranch Girl ($50: $C0/$C2) standing happily beside the milk churns
  LDA.b $1A : AND.b #$10 : BNE .rg_b
    %credits_actor($0234, $0128, CreditsGfx_GirlA)
    BRA .rancher
  .rg_b
    %credits_actor($0234, $0128, CreditsGfx_GirlB)
  .rancher
  ; 4. Rancher / Villager ($50: $E0/$E8) tending the green pasture
  LDA.b $1A : AND.b #$10 : BNE .rn_b
    %credits_actor($0246, $00F2, CreditsGfx_WomanA)
    BRA .cat
  .rn_b
    %credits_actor($0246, $00F2, CreditsGfx_WomanB)
  .cat
  ; 5. Ranch Cat ($49: $4E) lounging on the grass beside the lower milk churn
  LDA.b $1A : AND.b #$20 : BNE .cat_b
    %credits_actor($0234, $0142, CreditsGfx_CatA)
    RTS
  .cat_b
    %credits_actor($0234, $0142, CreditsGfx_CatB)
  RTS
}

; ---- Scene 1: Wayward Village ($23, set $0A: $2B/$49/$4A/$50, pal $01) ----
CreditsActors_Scene1_Village:
{
  ; 1. Village Dog ($2B) trotting happily back & forth across the central square!
  JSR CreditsActors_PingPong16
  PHP
  STA.b $04
  BPL .dog_pos
    LDA.b #$FF : BRA .dog_hi
  .dog_pos
    LDA.b #$00
  .dog_hi
  STA.b $05
  REP #$20
  LDA.w #$0778 : CLC : ADC.b $04 : STA.b $00
  LDA.w #$0998 : STA.b $02
  SEP #$20
  PLP : BCS .dog_left
    LDA.b $1A : AND.b #$08 : BNE .dog_r2
      REP #$20 : LDA.w #CreditsGfx_DogRightA : BRA .dog_draw
    .dog_r2
      REP #$20 : LDA.w #CreditsGfx_DogRightB : BRA .dog_draw
  .dog_left
    LDA.b $1A : AND.b #$08 : BNE .dog_l2
      REP #$20 : LDA.w #CreditsGfx_DogLeftA : BRA .dog_draw
    .dog_l2
      REP #$20 : LDA.w #CreditsGfx_DogLeftB
  .dog_draw
  STA.b $06 : SEP #$20
  JSR CreditsActors_DrawFrame

  ; 2. Village Girl ($50: $C0/$C2) on the left side of the square
  LDA.b $1A : AND.b #$10 : BNE .vg_b
    %credits_actor($0758, $0972, CreditsGfx_GirlA)
    BRA .woman
  .vg_b
    %credits_actor($0758, $0972, CreditsGfx_GirlB)
  .woman
  ; 3. Village Woman ($50: $E0/$E8) chatting on the right side of the square
  LDA.b $1A : AND.b #$10 : BNE .vw_b
    %credits_actor($07A4, $0972, CreditsGfx_WomanB)
    BRA .cat
  .vw_b
    %credits_actor($07A4, $0972, CreditsGfx_WomanA)
  .cat
  ; 4. Village Cat ($49: $4E) curled peacefully on the open sandy square
  %credits_actor($074E, $098C, CreditsGfx_CatA)
  RTS
}

; ---- Scene 2: Hall of Secrets ($0E, set $09: $1F/$49/$55/$42, pal $01) ----
CreditsActors_Scene2_Hall:
{
  ; 1. Farore ($55: $A8/$AA <-> $A8/$88) standing before the sanctuary doors
  LDA.b $1A : AND.b #$10 : BNE .farore_b
    %credits_actor($0CF8, $028C, CreditsGfx_FaroreA)
    BRA .owl
  .farore_b
    %credits_actor($0CF8, $028C, CreditsGfx_FaroreB)
  .owl
  ; 2. Eon Owl / Kaepora Gaebora ($42: $C7/$C9) soaring above the sanctuary!
  JSR CreditsActors_PingPong16
  STA.b $04
  BPL .owl_pos
    LDA.b #$FF : BRA .owl_hi
  .owl_pos
    LDA.b #$00
  .owl_hi
  STA.b $05
  REP #$20
  LDA.w #$0D08 : CLC : ADC.b $04 : STA.b $00
  LDA.w #$024A : STA.b $02
  SEP #$20
  LDA.b $1A : AND.b #$08 : BNE .owl_b
    REP #$20 : LDA.w #CreditsGfx_OwlFlyA : BRA .owl_draw
  .owl_b
    REP #$20 : LDA.w #CreditsGfx_OwlFlyB
  .owl_draw
  STA.b $06 : SEP #$20
  JSR CreditsActors_DrawFrame

  ; 3. Sanctuary Cat ($49: $4E) resting on the bright stone courtyard
  %credits_actor($0CE2, $0298, CreditsGfx_CatA)
  RTS
}

; ---- Scene 3: Kalyxo Castle ($0B, set $28: $35/$4D/$65/$36, pal $01) ----
CreditsActors_Scene3_Castle:
{
  ; 1. Left Castle Guard ($35 slot 0: $24/$24/$26) flanking the grand avenue
  %credits_actor($079C, $031C, CreditsGfx_Guard)
  ; 2. Right Castle Guard flanking symmetrically
  %credits_actor($07E4, $031C, CreditsGfx_Guard)
  ; 3. Royal Maiden / Impa ($35 slot 0: $28/$28/$04) welcoming at the steps
  LDA.b $1A : AND.b #$20 : BNE .impa_b
    %credits_actor($07C0, $02FC, CreditsGfx_MaidenA)
    RTS
  .impa_b
    %credits_actor($07C0, $02FC, CreditsGfx_MaidenB)
  RTS
}

; ---- Scene 4: Loom Beach ($33, set $06: $4F/$49/$4A/$50, pal $01) ----
CreditsActors_Scene4_Beach:
{
  ; 1. Beach Girl ($50: $C0/$C2) strolling gently along the warm golden sand
  JSR CreditsActors_PingPong16
  STA.b $04
  BPL .bg_pos
    LDA.b #$FF : BRA .bg_hi
  .bg_pos
    LDA.b #$00
  .bg_hi
  STA.b $05
  REP #$20
  LDA.w #$0774 : CLC : ADC.b $04 : STA.b $00
  LDA.w #$0F22 : STA.b $02
  SEP #$20
  LDA.b $1A : AND.b #$08 : BNE .bg_b
    REP #$20 : LDA.w #CreditsGfx_GirlA : BRA .bg_draw
  .bg_b
    REP #$20 : LDA.w #CreditsGfx_GirlB
  .bg_draw
  STA.b $06 : SEP #$20
  JSR CreditsActors_DrawFrame

  ; 2. Beach Villager ($50: $E0/$E8) enjoying the breeze on the dry sand
  LDA.b $1A : AND.b #$10 : BNE .bw_b
    %credits_actor($0798, $0F06, CreditsGfx_WomanA)
    BRA .bcat
  .bw_b
    %credits_actor($0798, $0F06, CreditsGfx_WomanB)
  .bcat
  ; 3. Beach Cat ($49: $4E) lounging on the shoreline sand
  %credits_actor($07B0, $0F18, CreditsGfx_CatB)
  RTS
}

; ---- Scene 5: Zora Island ($1E, set $8E: $4B/$49/$4C/$74, pal $01 + D4 Zora) ----
CreditsActors_Scene5_Zora:
{
  ; 1. D4 River Zora ($74 / global $E7: $C0/$C2) bobbing in the western cove
  LDA.b $1A : AND.b #$10 : BNE .z0_b
    %credits_actor($0CAA, $06D2, CreditsGfx_D4ZoraA)
    BRA .zora1
  .z0_b
    %credits_actor($0CAA, $06D2, CreditsGfx_D4ZoraB)
  .zora1
  ; 2. Friendly D4 River Zora gliding peacefully across the central bay
  JSR CreditsActors_PingPong16
  PHP
  STA.b $04
  BPL .z1_pos
    LDA.b #$FF : BRA .z1_hi
  .z1_pos
    LDA.b #$00
  .z1_hi
  STA.b $05
  REP #$20
  LDA.w #$0CE2 : CLC : ADC.b $04 : STA.b $00
  LDA.w #$06CC : STA.b $02
  SEP #$20
  PLP : BCS .z1_left
    LDA.b $1A : AND.b #$10 : BNE .z1_r2
      REP #$20 : LDA.w #CreditsGfx_D4ZoraA : BRA .z1_draw
    .z1_r2
      REP #$20 : LDA.w #CreditsGfx_D4ZoraB : BRA .z1_draw
  .z1_left
    LDA.b $1A : AND.b #$10 : BNE .z1_l2
      REP #$20 : LDA.w #CreditsGfx_D4ZoraLeftA : BRA .z1_draw
    .z1_l2
      REP #$20 : LDA.w #CreditsGfx_D4ZoraLeftB
  .z1_draw
  STA.b $06 : SEP #$20
  JSR CreditsActors_DrawFrame

  ; 3. Third D4 River Zora bobbing happily in the upper island cove
  LDA.b $1A : AND.b #$10 : BNE .z2_b
    %credits_actor($0CC4, $06B0, CreditsGfx_D4ZoraLeftA)
    RTS
  .z2_b
    %credits_actor($0CC4, $06B0, CreditsGfx_D4ZoraLeftB)
  RTS
}

; ---- Scene 6: Goron Mines ($36, set $08: $3D/$49/$12/$38, pal $0E) ----
CreditsActors_Scene6_Goron:
{
  ; 1. Left Kalyxo Goron ($12: $8C/$AC <-> $8A/$AA) cheering by the mine gate
  LDA.b $1A : AND.b #$10 : BNE .g1_b
    %credits_actor($0CE4, $0E10, CreditsGfx_GoronA)
    BRA .g2
  .g1_b
    %credits_actor($0CE4, $0E10, CreditsGfx_GoronB)
  .g2
  ; 2. Right Kalyxo Goron alternating cheer rhythm!
  LDA.b $1A : AND.b #$10 : BNE .g2_b
    %credits_actor($0D3C, $0E10, CreditsGfx_GoronB)
    RTS
  .g2_b
    %credits_actor($0D3C, $0E10, CreditsGfx_GoronA)
  RTS
}

; ---- Scene 7: The Eon Abyss ($46, set $06, pal $01) ----
; Sapling grows from a magic bean on the newly emerald-moss grass patch.
; Reuses the bean vendor's frames (Sprites/NPCs/bean_vendor.asm), no new tiles.
!OracleCredits_SaplingX = $0CF8 ; area $46 map px (248,260)
!OracleCredits_SaplingY = $0104

CreditsActors_Scene7_Abyss:
{
  ; Growth stage by scene time ($C8): bean ($0000..$016F), then swaying green sprout!
  REP #$20
  LDA.w #!OracleCredits_SaplingX : STA.b $00
  LDA.w #!OracleCredits_SaplingY : STA.b $02
  LDA.b $C8 : CMP.w #$0170 : BCC .bean
  AND.w #$0020 : BEQ .sprout_a
    LDA.w #CreditsGfx_SproutB : BRA .draw
  .sprout_a
    LDA.w #CreditsGfx_SproutA : BRA .draw
  .bean
  LDA.w #CreditsGfx_Bean
  .draw
  STA.b $06
  SEP #$20
  JMP CreditsActors_DrawFrame
}

; =========================================================
; Verified OAM frame definitions (all tiles proven in each scene's loaded spriteset).
; Format: db tile_count; per tile: db dx, dy, chr, props, size (0=8x8, 2=16x16)

; Ranch / Village / Beach Girl (sheet $50 in slot 3, sets $06 & $0A)
CreditsGfx_GirlA:
  db 2
  db $00, $F8, $C0, $3B, $02
  db $00, $00, $C2, $3B, $02
CreditsGfx_GirlB:
  db 2
  db $00, $F9, $C0, $3B, $02
  db $00, $01, $C2, $7B, $02

; Village / Ranch / Beach Woman (sheet $50 in slot 3, sets $06 & $0A; $1AF8AC)
CreditsGfx_WomanA:
  db 2
  db $00, $F8, $E0, $39, $02
  db $00, $00, $E8, $39, $02
CreditsGfx_WomanB:
  db 2
  db $00, $F9, $E0, $39, $02
  db $00, $01, $E8, $79, $02

; Cucco / Chicken (sheet $50 in slot 3, set $06; vanilla Sprite $0B $EA/$EC pal 4)
CreditsGfx_CuccoLeftA:
  db 1
  db $00, $00, $EA, $39, $02
CreditsGfx_CuccoLeftB:
  db 1
  db $00, $FF, $EC, $39, $02
CreditsGfx_CuccoRightA:
  db 1
  db $00, $00, $EA, $79, $02
CreditsGfx_CuccoRightB:
  db 1
  db $00, $FF, $EC, $79, $02

; Curled / sitting Cat (sheet $49 in slot 1, sets $06, $09, $0A; warm coat $37)
CreditsGfx_CatA:
  db 1
  db $00, $00, $4E, $37, $02
CreditsGfx_CatB:
  db 1
  db $00, $FF, $4E, $37, $02

; Village Dog trotting (sheet $2B in slot 0, set $0A; exact frames 2/3/5/6 of village_dog.asm)
CreditsGfx_DogRightA:
  db 4
  db $FC, $F8, $13, $37, $02
  db $FC, $00, $23, $37, $02
  db $04, $00, $24, $37, $02
  db $0C, $F8, $15, $37, $00
CreditsGfx_DogRightB:
  db 4
  db $FC, $00, $26, $37, $02
  db $FC, $F8, $16, $37, $02
  db $04, $F8, $17, $37, $02
  db $04, $00, $27, $37, $02
CreditsGfx_DogLeftA:
  db 4
  db $04, $00, $23, $77, $02
  db $FC, $00, $24, $77, $02
  db $04, $F8, $13, $77, $02
  db $FC, $F8, $14, $77, $02
CreditsGfx_DogLeftB:
  db 4
  db $04, $00, $26, $77, $02
  db $FC, $00, $27, $77, $02
  db $04, $F0, $06, $77, $02
  db $FC, $F8, $18, $77, $00

; Farore (sheet $55 in slot 2, set $09)
CreditsGfx_FaroreA:
  db 2
  db $00, $F8, $A8, $3B, $02
  db $00, $04, $AA, $3B, $02
CreditsGfx_FaroreB:
  db 2
  db $00, $F8, $A8, $3B, $02
  db $00, $04, $88, $7B, $02

; Eon Owl / Kaepora Gaebora soaring (sheet $42 in slot 3, set $09)
CreditsGfx_OwlFlyA:
  db 2
  db $F8, $00, $C7, $37, $02
  db $08, $00, $C7, $77, $02
CreditsGfx_OwlFlyB:
  db 2
  db $08, $00, $C9, $37, $02
  db $F8, $00, $C9, $77, $02

; Castle Guard & Royal Maiden (sheet $35 in slot 0, set $28; chars -$80 from hyrule_dream)
CreditsGfx_Guard:
  db 3
  db $FC, $FC, $24, $39, $02
  db $04, $FC, $24, $79, $02
  db $00, $F2, $26, $39, $02
CreditsGfx_MaidenA:
  db 3
  db $F8, $FC, $28, $39, $02
  db $08, $FC, $28, $79, $02
  db $00, $F2, $04, $39, $02
CreditsGfx_MaidenB:
  db 3
  db $F8, $FD, $28, $39, $02
  db $08, $FD, $28, $79, $02
  db $00, $F3, $04, $39, $02

; D4 River Zoras (sheet $74 / global $E7 in slot 3, set $8E; pal 3/4 via PatchScenePalette)
CreditsGfx_D4ZoraA:
  db 2
  db $00, $F0, $C0, $37, $02
  db $00, $F8, $C2, $39, $02
CreditsGfx_D4ZoraB:
  db 2
  db $00, $F1, $C0, $37, $02
  db $00, $F9, $C2, $79, $02
CreditsGfx_D4ZoraLeftA:
  db 2
  db $00, $F0, $C0, $77, $02
  db $00, $F8, $C2, $79, $02
CreditsGfx_D4ZoraLeftB:
  db 2
  db $00, $F1, $C0, $77, $02
  db $00, $F9, $C2, $39, $02

; Kalyxo Goron cheering forward (sheet $12 in slot 2, set $08)
CreditsGfx_GoronA:
  db 4
  db $F8, $F8, $8C, $37, $02
  db $F8, $08, $AC, $37, $02
  db $08, $F8, $8C, $77, $02
  db $08, $08, $AC, $77, $02
CreditsGfx_GoronB:
  db 4
  db $F8, $F6, $8C, $37, $02
  db $F8, $06, $AC, $37, $02
  db $08, $F6, $8C, $77, $02
  db $08, $06, $AC, $77, $02

; Scene 7 Magic Bean & swaying green Sapling (sheet $4A / global sheet $07)
CreditsGfx_Bean:
  db 1
  db $00, $00, $A6, $3B, $02
CreditsGfx_SproutA:
  db 2
  db $00, $04, $C8, $38, $00
  db $08, $04, $C9, $78, $00
CreditsGfx_SproutB:
  db 2
  db $00, $04, $CA, $38, $00
  db $08, $04, $C8, $78, $00

; Tile sheets: ZS InitTilesetsLongCalls also treats module $1A as outdoors, so
; each scene loads its area's own sheets (see ZSCustomOverworld.asm).

pushpc

org $02E4D4 ; @hook module=Overworld name=OracleCredits_ExitHook kind=jml target=OracleCredits_ExitHook expected_m=16 expected_x=8
  JML OracleCredits_ExitHook
  assert pc() == $02E4D8

; $0E988D (the old JSR Credits_AddEndingSequenceText) becomes a bare RTS; the
; no-actor sprite load vectors below point at it.
org $0E9889 ; @hook module=Overworld name=OracleCredits_LoadNextScene kind=jsl target=OracleCredits_LoadNextScene expected_m=8 expected_x=8
  JSL OracleCredits_LoadNextScene
  RTS
  assert pc() == $0E988E
!OracleCredits_NoActor = $988D

; Module1A sub vectors: scene 1 (vanilla Sanctuary) is an overworld scene here.
org $0E9824 ; @hook module=Overworld kind=data name=OracleCreditsSubVectors
  dw $9889, $9958

; Credits_LoadScene_Overworld_PrepGFX sends subs $0C and $1E (vanilla Zora's
; Domain / Master Sword) to LoadSpecialOverworld, which overwrites the area's
; tile sheets and palette after the camera hook. All Oracle scenes are normal
; overworld areas, so compare against $FF (load subs are even; never matches).
org $02861D ; @hook module=Overworld kind=data name=OracleCreditsNoSpecialA
  db $FF
org $028621 ; @hook module=Overworld kind=data name=OracleCreditsNoSpecialB
  db $FF

; Credits_LoadScene_Overworld .sprite_gfx / .sprite_palette for scenes 0-7.
; Matched strictly to each scene's verified NPC sprite sheets above!
org $0285E2 ; @hook module=Overworld kind=data name=OracleCreditsSpriteGfx
  db $06, $0A, $09, $28, $06, $8E, $08, $06
org $0285F3 ; @hook module=Overworld kind=data name=OracleCreditsSpritePalette
  db $01, $01, $01, $01, $01, $01, $0E, $01

; Credits_LoadNextScene_Underworld ($0E9891) only ran for vanilla subs $02,
; $14 and $16; $02 is an overworld scene here and $14/$16 come after the last
; scene, so its 8 bytes hold the shared per-scene actor draw vector.
org $0E9891 ; @hook module=Overworld name=OracleCredits_ActorVector kind=jsl target=OracleCredits_DrawSceneActors expected_m=8 expected_x=8
OracleCredits_ActorVector:
  JSL OracleCredits_DrawSceneActors
  RTS
  assert pc() <= $0E9899

; Credits_PrepAndLoadSprites .vectors: stateless OAM actors need no prep.
org $0E9899 ; @hook module=Overworld kind=data name=OracleCreditsLoadSprites
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor
  dw !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor, !OracleCredits_NoActor

; Credits_ScrollScene .target_y / .target_x / .movement_y / .movement_x.
; Scene 3 ($0B) pans up from $0300 -> $02A0, framing Kalyxo Castle cleanly.
org $0E98D8 ; @hook module=Overworld kind=data name=OracleCreditsTargetY
  dw $00C0, $0940, $0220, $02A0, $0EA0, $0690, $0DA0, $0090
org $0E98F8 ; @hook module=Overworld kind=data name=OracleCreditsTargetX
  dw $0200, $0700, $0C80, $0740, $0700, $0C30, $0C80, $0C70
org $0E9918 ; @hook module=Overworld kind=data name=OracleCreditsMoveY
  dw 0, 1, 0, -1, 0, 1, -1, 1
org $0E9938 ; @hook module=Overworld kind=data name=OracleCreditsMoveX
  dw 1, 0, 1, 0, -1, 0, 0, 0

; Credits_SpriteDraw_vectors: all 8 scenes draw their animated actors!
org $0E99A5 ; @hook module=Overworld kind=data name=OracleCreditsSpriteDraw
  dw OracleCredits_ActorVector, OracleCredits_ActorVector, OracleCredits_ActorVector, OracleCredits_ActorVector
  dw OracleCredits_ActorVector, OracleCredits_ActorVector, OracleCredits_ActorVector, OracleCredits_ActorVector

; Credits_HandleSceneFade .timer: frames before the fade-out starts.
; Synced to ending song $21 (measured in Mesen2 from the N-SPC pattern
; pointer): each fade lands ~20 frames before a pattern starts, so the next
; scene opens on the new phrase, and the staff roll (song $22) starts when
; song $21 ends. A scene lasts timer + ~88 frames (fade out, load, fade in).
; Cuts at song patterns 3, 5, 7, 10, 12, 13, 14; scene 7 holds pattern 14.
org $0E9A0A ; @hook module=Overworld kind=data name=OracleCreditsTimer
  dw $06C0, $0814, $0700, $06CC, $04FC, $0488, $0368, $06C8

pullpc
