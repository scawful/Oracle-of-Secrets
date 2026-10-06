; =========================================================
; Mirror experiment scene (!ENABLE_EXPERIMENT_SCENE), phase 3
;
; Included from Core/Cutscene/opening.asm (bank $3A, after the arrival code).
; Storyboard (approved, revision 2):
;   Docs/Planning/Plans/experiment_scene_storyboard_2026-09-25.md
;
; New file, before the arrival: the Tail Pond Mirror test. Kalyxo is the real
; Tail Pond screen (LW $2D); the Abyss is the real mirror screen (DW $6D).
; 1. Arrival_SpotlightGate sends the new file here (module $0D).
; 2. %exp_area loads a screen with vanilla Module08_OverworldLoad, one step
;    per frame, under forced blank (the ZSCustomOverworld hooks build it):
;    - Kalyxo: $A0 = room $0E6, whose exit leads to OW $2D.
;    - Abyss: $A0 = room $124, which takes LoadCachedEntranceProperties; the
;      cache ($7EC140) holds the $2D camera with area $6D (Exp_CacheScreen).
;      World flag $7EF3CA = $40 for the load, back to 0 for the next Kalyxo
;      load. Moon Pearl is set for the load so Link does not turn into a
;      bunny (Link is not drawn), then restored.
;    After each load: the actor sheets go into the four spriteset slots,
;    and the Abyss gets the Kalyxo sprite palettes (same actor colors in
;    both worlds).
; 3. Actors are OAM tableaus drawn by this module every frame (no sprite
;    slots, no AI): Zora A and Zora B (Sea Zora sheet $56), Farore (sheet
;    $55), Kydrog's Stalfos (village pirate look: sheet $0D, palette 6).
; 4. A full reload (module $05, room $104) rebuilds the bedroom and tucks
;    Link into bed. Exp_Done tells the gate to start the arrival this time.
; Start skips to step 4 at any point.
;
; Messages $1D9-$1DF: Data/dialogue/message_registry.json, owner
; experiment-scene.
; =========================================================

Experiment_RenderText    = $0EC440 ; RTL, message engine (state in $1CD8)
Experiment_OverworldLoad = $0283BF ; RTL, Module08_OverworldLoad (step in $11)
Exp_LoadSpriteGraphics   = $00E583 ; RTS; Y = sheet, X = buffer page, $02 = buffer bank
Exp_Bank00_RTL           = $00E33A ; RTL (end of InitializeTilesets)

!ExpArea_Room   = $00E6 ; UnderworldExitData exit $12: room $0E6 -> OW $2D
!ExpCache_Room  = $0124 ; rooms $101-$17F (not $104) load from the cache
!ExpAbyss_Area  = $6D   ; DW mirror of $2D (same grid cell, small area)
; !ExpDoneMarker is defined in opening.asm (the gate reads it first).
!ExpLoadMaxSteps = 60   ; frames before a stuck load gives up

; Actor sheets, spriteset slots 0-3 (VRAM $5000-$5FFF, OAM chars $100-$1FF).
; Each sheet sits in the slot its own sprite uses, so the chars below match
; the sprites' draw code.
!ExpSheet0 = $48 ; slot 0: village spriteset $11 slot 0 (no actor uses it yet)
!ExpSheet1 = $0D ; slot 1: pirate Stalfos (village spriteset $11)
!ExpSheet2 = $55 ; slot 2: Farore (Sprites/NPCs/farore.asm, spriteset $09)
!ExpSheet3 = $56 ; slot 3: Sea Zora (Sprites/NPCs/zora.asm, spriteset $1F)

; Transient state while module $0D runs. Vanilla free WRAM (Core/ram.asm
; UNUSED_7FF180); the arrival uses $7FF300-$7FF312, Impa hints $7FF340,
; text shade $7FF350, the 2P PoC $7FF400-$7FF5FF. This scene:
; $7FF180-$7FF1D9, $7FF200-$7FF2C3, $7FF320-$7FF335, $7FF600-$7FF77F.
Exp_State   = $7FF320
Exp_PC      = $7FF321 ; 16-bit offset into Experiment_Script
Exp_Timer   = $7FF323
Exp_Block   = $7FF324 ; op that holds the script (see Exp_RunBlock)
Exp_Arg     = $7FF325 ; fade target, or frames to hold a cut-off message
Exp_Math    = $7FF326 ; base look: CGADSUB ($9A) and fixed color, 0-31 each
Exp_TintR   = $7FF327
Exp_TintG   = $7FF328
Exp_TintB   = $7FF329
Exp_Area    = $7FF32A ; screen being shown: 0 Kalyxo ($2D), 1 Abyss ($6D)
Exp_Flicker = $7FF32B ; Kalyxo/Abyss palette flicker frames; $FF = until stopped
Exp_Shake   = $7FF32C ; screen shake frames; $FF = until stopped
Exp_ShakeX  = $7FF32D ; current shake offset (signed px)
Exp_Pearl   = $7FF32E ; bit 7: Moon Pearl borrowed; bits 0-6: saved value
Exp_CutArm  = $7FF32F ; 1 once a cut-off message has drawn its last character
Exp_Tries   = $7FF330 ; load steps so far
Exp_Done    = $7FF331 ; !ExpDoneMarker after the scene; the gate clears it
Exp_Save8A  = $7FF332 ; area before the scene
Exp_Save40A = $7FF333 ; 16-bit $040A before the scene
Exp_HideHUD = $7FF335 ; 1: blank the HUD next frame

!ExpActors  = 10
Exp_ActPose = $7FF180 ; per actor; 0 = hidden
Exp_ActX    = $7FF190 ; screen X of the actor's feet tile (16x16, top-left)
Exp_ActY    = $7FF1A0
Exp_ActTX   = $7FF1B0 ; walk target
Exp_ActTY   = $7FF1C0
Exp_Order   = $7FF1D0 ; actors in draw order, front (largest Y) first

Exp_PalSpr  = $7FF200 ; Kalyxo sprite palettes 1-6 (CGRAM rows 9-14), $C0 bytes
Exp_BackLW  = $7FF2C0 ; backdrop color, Kalyxo
Exp_BackDW  = $7FF2C2 ; backdrop color, Abyss
Exp_PalLW   = $7FF600 ; Kalyxo BG palettes 2-7 (CGRAM rows 2-7), $C0 bytes
Exp_PalDW   = $7FF6C0 ; Abyss BG palettes 2-7

; Actors
!ExpA_ZoraA  = 0
!ExpA_ZoraB  = 1
!ExpA_Farore = 2
!ExpA_Stal0  = 3 ; Stalfos 0-6 = actors 3-9
!ExpA_Stal1  = 4
!ExpA_Stal2  = 5
!ExpA_Stal3  = 6
!ExpA_Stal4  = 7
!ExpA_Stal5  = 8
!ExpA_Stal6  = 9

; Poses (Exp_Poses)
!ExpP_Hide        = 0
!ExpP_ZoraFront   = 1
!ExpP_ZoraRight   = 2
!ExpP_ZoraLeft    = 3
!ExpP_FaroreFront = 4
!ExpP_FaroreStep  = 5
!ExpP_FaroreBack  = 6
!ExpP_StalLow     = 7 ; skull out of the ground
!ExpP_StalMid     = 8 ; half risen
!ExpP_Stal        = 9 ; standing, facing south (the camera)
!ExpP_StalWest    = 10
!ExpP_StalEast    = 11
!ExpP_StalNorth   = 12
!ExpP_Count       = 13

; Messages
!ExpMsg_ZoraA_Resonance = $01D9 ; M1a
!ExpMsg_ZoraB_Report    = $01DA ; M1b
!ExpMsg_Farore_Still    = $01DB ; M2
!ExpMsg_ZoraA_Quiet     = $01DC ; M3
!ExpMsg_ZoraB_Behind    = $01DD ; M4
!ExpMsg_ZoraA_WontClose = $01DE ; M6
!ExpMsg_Farore_Plea     = $01DF ; M5, cut off by the white-out

; Looks: CGADSUB value, then the fixed color. BG3 (text) is never included.
; Actors are hidden while the look is not Kalyxo (OBJ palettes 0-3 ignore
; color math) and while a flash runs.
!ExpLook_Kalyxo = $00, 0, 0, 0     ; the map as loaded
!ExpLook_Black  = $A3, 31, 31, 31  ; subtract white from BG1/BG2/backdrop
!ExpLook_White  = $23, 31, 31, 31  ; add white

; ---------------------------------------------------------
; Script opcodes
macro exp_end()
  db $00
endmacro
macro exp_wait(frames)
  db $01, <frames>
endmacro
macro exp_text(id)                 ; show a message, wait until it closes
  db $02 : dw <id>
endmacro
macro exp_look(define)             ; set the base look (!ExpLook_* name without the !)
  db $03, !<define>
endmacro
macro exp_fade(target)             ; step brightness ($13) to target
  db $04, <target>
endmacro
macro exp_song(id)                 ; $012C
  db $05, <id>
endmacro
macro exp_sfx1(id)                 ; $012D (ambient; $05 = off)
  db $06, <id>
endmacro
macro exp_sfx2(id)                 ; $012E
  db $07, <id>
endmacro
macro exp_sfx3(id)                 ; $012F
  db $08, <id>
endmacro
macro exp_flicker(frames)          ; Kalyxo/Abyss BG palettes alternate; runs under other ops
  db $09, <frames>
endmacro
macro exp_cut(id, hold)            ; show a message, close it <hold> frames after its last character
  db $0A : dw <id> : db <hold>
endmacro
macro exp_flash(frames)            ; white for <frames>, then the base look
  db $0B, <frames>
endmacro
macro exp_actor(actor, pose, x, y) ; place an actor (pose 0 hides it)
  db $0C, <actor>, <pose>, <x>, <y>
endmacro
macro exp_walk(actor, x, y)        ; walk to x,y (1 px every other frame); runs under other ops
  db $0D, <actor>, <x>, <y>
endmacro
macro exp_area(area)               ; load a screen under forced blank: 0 Kalyxo, 1 Abyss
  db $0E, <area>
endmacro
macro exp_shake(frames)            ; shake the map; runs under other ops
  db $0F, <frames>
endmacro
macro exp_pose(actor, pose)        ; change pose, keep position
  db $10, <actor>, <pose>
endmacro
macro exp_rise(actor, x, y, pose)  ; Stalfos rises out of the ground with a rattle
  %exp_actor(<actor>, !ExpP_StalLow, <x>, <y>)
  %exp_sfx2($22)
  %exp_wait(5)
  %exp_pose(<actor>, !ExpP_StalMid)
  %exp_wait(5)
  %exp_pose(<actor>, <pose>)
endmacro
macro exp_sink(actor)              ; the rise in reverse
  %exp_pose(<actor>, !ExpP_StalMid)
  %exp_wait(5)
  %exp_pose(<actor>, !ExpP_StalLow)
  %exp_wait(5)
  %exp_pose(<actor>, !ExpP_Hide)
endmacro

; Stage (screen px, top-left of the actor's lower 16x16 tile; the camera is
; room $0E6's exit camera). Kalyxo $2D: the pond is a U of water around a
; paved island (x 96-160, y 112-168); banks left (x < 64) and right
; (x > 192). The text box is at the top (glyph rows y 80-127), so the actors
; stand below it. The Abyss ($6D) is the same camera on the mirror screen.
!ExpX_ZoraA  = 124
!ExpY_ZoraA  = 146
!ExpX_ZoraB  = 100
!ExpY_ZoraB  = 138
!ExpX_Farore = 206
!ExpY_Farore = 142
!ExpX_Behind = 146 ; the Stalfos that follows Zora A home
!ExpY_Behind = 128

; ---------------------------------------------------------
; The scene.
Experiment_Script:
{
  ; Shot 1: Tail Pond. Zora A at the water, Zora B with a slate, Farore apart.
  %exp_area(0)
  %exp_sfx1($05)                        ; no rain ambience from the load
  %exp_song($F1)                        ; fade out the load's music
  %exp_look(ExpLook_Kalyxo)
  %exp_actor(!ExpA_ZoraA, !ExpP_ZoraFront, !ExpX_ZoraA, !ExpY_ZoraA)
  %exp_actor(!ExpA_ZoraB, !ExpP_ZoraRight, !ExpX_ZoraB, !ExpY_ZoraB)
  %exp_actor(!ExpA_Farore, !ExpP_FaroreFront, !ExpX_Farore, !ExpY_Farore)
  %exp_fade($0F)
  %exp_wait(40)
  %exp_text(!ExpMsg_ZoraA_Resonance)
  %exp_text(!ExpMsg_ZoraB_Report)
  %exp_text(!ExpMsg_Farore_Still)
  %exp_wait(30)

  ; Shot 2: Zora A steps to the edge; the Mirror opens.
  %exp_walk(!ExpA_ZoraA, !ExpX_ZoraA, !ExpY_ZoraA+8)
  %exp_wait(30)
  %exp_song($08)
  %exp_flash(10)
  %exp_look(ExpLook_Black)
  %exp_wait(20)

  ; Shot 3: the Abyss. Same spot, Zora A alone, near silence.
  %exp_actor(!ExpA_ZoraB, !ExpP_Hide, 0, 0)
  %exp_actor(!ExpA_Farore, !ExpP_Hide, 0, 0)
  %exp_actor(!ExpA_ZoraA, !ExpP_ZoraFront, !ExpX_ZoraA, !ExpY_ZoraA+8)
  %exp_area(1)
  %exp_sfx1($05)
  %exp_look(ExpLook_Kalyxo)
  %exp_fade($0F)
  %exp_wait(50)
  %exp_text(!ExpMsg_ZoraA_Quiet)
  %exp_wait(30)

  ; Shot 4: Stalfos rise in a ring around Zora A. Zora A flashes out.
  %exp_rise(!ExpA_Stal0, !ExpX_ZoraA-36, !ExpY_ZoraA-8, !ExpP_StalEast)
  %exp_wait(8)
  %exp_pose(!ExpA_ZoraA, !ExpP_ZoraLeft)
  %exp_rise(!ExpA_Stal1, !ExpX_ZoraA+36, !ExpY_ZoraA-8, !ExpP_StalWest)
  %exp_wait(8)
  %exp_pose(!ExpA_ZoraA, !ExpP_ZoraRight)
  %exp_rise(!ExpA_Stal2, !ExpX_ZoraA+2, !ExpY_ZoraA+36, !ExpP_StalNorth)
  %exp_pose(!ExpA_ZoraA, !ExpP_ZoraFront)
  %exp_walk(!ExpA_ZoraA, !ExpX_ZoraA, !ExpY_ZoraA)   ; backs away
  %exp_wait(20)
  %exp_song($08)
  %exp_flash(10)
  %exp_look(ExpLook_Black)
  %exp_wait(20)

  ; Shot 5a: back at the pond. One Stalfos rises behind Zora A.
  %exp_actor(!ExpA_Stal0, !ExpP_Hide, 0, 0)
  %exp_actor(!ExpA_Stal1, !ExpP_Hide, 0, 0)
  %exp_actor(!ExpA_Stal2, !ExpP_Hide, 0, 0)
  %exp_actor(!ExpA_ZoraA, !ExpP_ZoraFront, !ExpX_ZoraA, !ExpY_ZoraA)
  %exp_actor(!ExpA_ZoraB, !ExpP_ZoraRight, !ExpX_ZoraB, !ExpY_ZoraB)
  %exp_actor(!ExpA_Farore, !ExpP_FaroreFront, !ExpX_Farore, !ExpY_Farore)
  %exp_area(0)
  %exp_sfx1($05)
  %exp_look(ExpLook_Kalyxo)
  %exp_fade($0F)
  %exp_wait(30)
  %exp_rise(!ExpA_Stal0, !ExpX_Behind, !ExpY_Behind, !ExpP_Stal)
  %exp_wait(24)
  %exp_text(!ExpMsg_ZoraB_Behind)

  ; Shot 5b: Zora B strikes it; it sinks. Pause. It rises again.
  %exp_pose(!ExpA_ZoraA, !ExpP_ZoraRight)
  %exp_walk(!ExpA_ZoraB, !ExpX_Behind-18, !ExpY_Behind-14)
  %exp_wait(50)
  %exp_sfx2($0C)
  %exp_wait(12)
  %exp_sfx2($1F)
  %exp_sink(!ExpA_Stal0)
  %exp_walk(!ExpA_ZoraB, !ExpX_ZoraB, !ExpY_ZoraB)
  %exp_wait(70)
  %exp_rise(!ExpA_Stal0, !ExpX_Behind, !ExpY_Behind, !ExpP_Stal)
  %exp_wait(40)

  ; Shot 5c: the Mirror won't close. Kalyxo and Abyss flicker; the map shakes.
  %exp_pose(!ExpA_ZoraA, !ExpP_ZoraFront)
  %exp_sfx1($07)
  %exp_flicker($FF)
  %exp_shake($FF)
  %exp_wait(40)
  %exp_text(!ExpMsg_ZoraA_WontClose)
  %exp_wait(20)

  ; Shot 5d: Stalfos rise all around the pond. Music out, rattles only.
  %exp_song($F1)
  %exp_rise(!ExpA_Stal1, 24, 128, !ExpP_StalEast)
  %exp_wait(4)
  %exp_rise(!ExpA_Stal2, 226, 112, !ExpP_StalWest)
  %exp_wait(2)
  %exp_rise(!ExpA_Stal3, 44, 168, !ExpP_StalEast)
  %exp_wait(4)
  %exp_rise(!ExpA_Stal4, 236, 166, !ExpP_StalWest)
  %exp_wait(2)
  %exp_rise(!ExpA_Stal5, 40, 204, !ExpP_StalEast)
  %exp_wait(2)
  %exp_rise(!ExpA_Stal6, 212, 198, !ExpP_StalWest)
  %exp_wait(24)
  %exp_flicker(0)                       ; stop; back on Kalyxo
  %exp_shake(0)

  ; Shot 6: Farore steps forward. The white-out cuts her plea off.
  %exp_walk(!ExpA_Farore, !ExpX_Farore-14, !ExpY_Farore+10)
  %exp_wait(36)
  %exp_pose(!ExpA_Farore, !ExpP_FaroreFront)
  %exp_cut(!ExpMsg_Farore_Plea, 12)
  %exp_look(ExpLook_White)
  %exp_wait(30)
  %exp_sfx1($05)                        ; rumble off
  %exp_look(ExpLook_Black)
  %exp_fade($00)
  %exp_wait(30)
  %exp_end()
}

; ---------------------------------------------------------
; Actor poses. Per pose: piece count, then per piece dx, dy (signed, from
; the actor's X/Y), char, OAM props, size ($02 = 16x16). The first piece is
; drawn in front. Chars and props come from the sprites' own draw code:
; Sea Zora (zora.asm), Farore (farore.asm frames 0, 1, 3). Stalfos: the
; village pirate look (IntroPatrol_DrawPirate, stalfos_patrol.asm), which is
; vanilla SpriteDraw_TutorialGuard: 5 objects per facing ($05D5BF-$05D63B),
; listed front to back; slot-1 chars ($40+, sheet $0D) in palette 6, slot-0
; chars (sheet $48: shield, spear, feet) in palette 4. The rise poses are the
; south frame sunk into the ground.
Exp_Poses:
{
  .start
  db .hide-.data, .zora_front-.data, .zora_right-.data, .zora_left-.data
  db .farore_front-.data, .farore_step-.data, .farore_back-.data
  db .stal_low-.data, .stal_mid-.data, .stal-.data
  db .stal_west-.data, .stal_east-.data, .stal_north-.data

  ; Pose shown on odd 8-frame steps while walking (0 = same pose).
  .walk_alt
  db 0, 0, 0, 0
  db !ExpP_FaroreStep, !ExpP_FaroreFront, 0
  db 0, 0, 0
  db 0, 0, 0

  .data
  .hide
  db 0
  .zora_front
  db 2
  db 0, 0, $EE, $35, $02
  db 0, -8, $DE, $35, $02
  .zora_right                             ; side frame as drawn (faces right)
  db 2
  db 0, 0, $EC, $35, $02
  db 0, -8, $DC, $35, $02
  .zora_left                              ; side frame, mirrored
  db 2
  db 0, 0, $EC, $75, $02
  db 0, -8, $DC, $75, $02
  .farore_front
  db 2
  db 0, 0, $AA, $3B, $02
  db 0, -12, $A8, $3B, $02
  .farore_step
  db 2
  db 0, 0, $88, $7B, $02
  db 0, -12, $A8, $3B, $02
  .farore_back
  db 2
  db 0, 0, $8C, $3B, $02
  db 0, -12, $8A, $3B, $02
  .stal_low                               ; skull only, at the ground line
  db 1
  db 0, 2, $40, $3D, $02
  .stal_mid                               ; south frame 6 px down, feet under ground
  db 3
  db -6, 2, $00, $39, $02                 ; shield
  db 0, -4, $40, $3D, $02                 ; skull
  db 4, 6, $46, $7D, $02                  ; body
  .stal                                   ; south: TutorialGuard frame 0
  db 5
  db 2, 12, $29, $39, $00                 ; feet
  db -6, 12, $28, $39, $00
  db -6, -4, $00, $39, $02                ; shield
  db 0, -10, $40, $3D, $02                ; skull
  db 4, 0, $46, $7D, $02                  ; body
  .stal_west                              ; frame 1
  db 5
  db -7, 5, $3A, $39, $00                 ; spear
  db -7, -3, $2A, $39, $00
  db -7, -11, $39, $39, $00
  db 0, -9, $42, $3D, $02                 ; skull
  db 0, 0, $4E, $3D, $02                  ; body
  .stal_east                              ; frame 2 (frame 1 mirrored)
  db 5
  db 15, 5, $3A, $79, $00
  db 15, -3, $2A, $79, $00
  db 15, -11, $39, $79, $00
  db 0, -9, $42, $7D, $02
  db 0, 0, $4E, $7D, $02
  .stal_north                             ; frame 3
  db 5
  db 0, -9, $44, $3D, $02                 ; skull
  db 4, 0, $64, $7D, $02                  ; body halves
  db -4, 0, $64, $3D, $02
  db 14, 5, $38, $79, $00                 ; spear
  db 6, -11, $26, $39, $02
  .end
}
assert Exp_Poses_end-Exp_Poses_data <= $100, "Exp_Poses data must stay under 256 bytes"

; ---------------------------------------------------------
; Module $0D. Entered by JML from Module_MainRouting; must RTL.
Experiment_Module:
{
  PHB : PHK : PLB
  SEP #$30
  LDA.l Exp_State : ASL A : TAX
  JSR (.states, X)
  PLB
  RTL

  .states
  dw Exp_Init
  dw Exp_Run
  dw Exp_Reload
}

; State 0 (bedroom loaded, iris not open): reset the scene and run the
; script, which starts with a screen load.
Exp_Init:
{
  LDA.b #$80 : STA.b $13                  ; forced blank until the first load
  STZ.b $9B                               ; no HDMA
  STZ.b $9A
  LDA.b $8A : STA.l Exp_Save8A
  REP #$20
  LDA.w $040A : STA.l Exp_Save40A
  LDA.w #$0000 : STA.l Exp_PC
  SEP #$20
  LDA.b #$00
  STA.l Exp_Block : STA.l Exp_Timer : STA.l Exp_Flicker
  STA.l Exp_Shake : STA.l Exp_ShakeX : STA.l Exp_Pearl : STA.l Exp_Area
  STA.l Exp_HideHUD
  STA.l Exp_Math : STA.l Exp_TintR : STA.l Exp_TintG : STA.l Exp_TintB
  LDX.b #!ExpActors-1
  .clear
    STA.l Exp_ActPose, X
    DEX : BPL .clear
  LDA.b #$01 : STA.l Exp_State
  RTS
}

; State 1: run the script and draw the actors. Start skips to the reload.
Exp_Run:
{
  LDA.b $F4 : AND.b #$10 : BEQ .no_skip
    JMP Exp_Reload
  .no_skip

  ; A finished load leaves $0710 = 4 ($17 = 4 full map upload): the NMI skips
  ; its sprite section, which also sets DMA0 to VRAM mode, so a HUD upload
  ; would go out in the palette upload's CGRAM mode. Clear it once the map
  ; is up, then blank the HUD (the text engine sets $0710 again as needed).
  LDA.l Exp_Block : CMP.b #$07 : BEQ .loading
    STZ.w $0710
    LDA.l Exp_HideHUD : BEQ .loading
      JSR Opening_HideHUD                 ; the reload rebuilds it
      LDA.b #$00 : STA.l Exp_HideHUD
  .loading

  JSR Exp_FlickerStep
  JSR Exp_ShakeStep
  JSR Exp_RunScript
  LDA.l Exp_State : CMP.b #$01 : BNE .done
    JSR Exp_MoveActors
    JSR Exp_DrawActors
  .done
  RTS
}

Exp_RunScript:
{
  LDA.l Exp_Block : BEQ .next_op
    JSR Exp_RunBlock
    LDA.l Exp_Block : BNE .hold
  .next_op
  JSR Exp_Step
  LDA.l Exp_State : CMP.b #$01 : BNE .hold
  LDA.l Exp_Block : BEQ .next_op          ; non-holding ops chain in one frame
  .hold
  RTS
}

; State 2: rebuild the bedroom with a full reload. The new-file room load
; (Module05 -> LoadUnderworldRoomRebuildHUD -> Module06) tucks Link into bed
; again; Arrival_SpotlightGate then sees Exp_Done and starts the arrival.
Exp_Reload:
{
  JSR Exp_CloseText
  LDA.b #$05 : STA.w $012D                ; ambient off
  LDA.b #!ExpDoneMarker : STA.l Exp_Done
  LDA.b #$00 : STA.l $7EF3CA              ; Kalyxo (a skip can land mid-Abyss)
  JSR Exp_ReturnPearl
  LDA.l Exp_Save8A : STA.b $8A
  REP #$20
  LDA.l Exp_Save40A : STA.w $040A
  STZ.w $011A : STZ.w $011C
  LDA.w #$0104 : STA.b $A0                ; Link's house
  SEP #$20
  LDA.b #$01 : STA.b $1B                  ; indoors
  STZ.b $9A : STZ.b $13
  STZ.b $11 : STZ.b $B0
  LDA.b #$00 : STA.l Exp_State
  LDA.b #$05 : STA.b $10                  ; Module05_LoadFile
  RTS
}

; Read and run one script op. X = 16-bit script offset while it runs.
Exp_Step:
{
  REP #$30
  LDA.l Exp_PC : TAX
  LDA.w Experiment_Script, X : INX
  AND.w #$00FF
  CMP.w #$0011 : BCC .valid
    LDA.w #$0000                          ; unknown op: end the scene
  .valid
  ASL A : TAY
  LDA.w .ops, Y : STA.b $00
  SEP #$20
  JMP ($0000)

  .ops
  dw .end, .wait, .text, .look, .fade, .song
  dw .sfx1, .sfx2, .sfx3, .flicker, .cut, .flash
  dw .actor, .walk, .area, .shake, .pose

  .end
    LDA.b #$02 : STA.l Exp_State
    JMP .done
  .wait
    LDA.w Experiment_Script, X : INX : STA.l Exp_Timer
    LDA.b #$01 : STA.l Exp_Block
    JMP .done
  .text
    JSR .open_message
    LDA.b #$02 : STA.l Exp_Block
    JMP .done
  .look
    LDA.w Experiment_Script, X : INX : STA.l Exp_Math
    LDA.w Experiment_Script, X : INX : STA.l Exp_TintR
    LDA.w Experiment_Script, X : INX : STA.l Exp_TintG
    LDA.w Experiment_Script, X : INX : STA.l Exp_TintB
    JSR Exp_ApplyBaseLook
    JMP .done
  .fade
    LDA.w Experiment_Script, X : INX : STA.l Exp_Arg
    LDA.b #$03 : STA.l Exp_Block
    JMP .done
  .song
    LDA.w Experiment_Script, X : INX : STA.w $012C
    JMP .done
  .sfx1
    LDA.w Experiment_Script, X : INX : STA.w $012D
    JMP .done
  .sfx2
    LDA.w Experiment_Script, X : INX : STA.w $012E
    JMP .done
  .sfx3
    LDA.w Experiment_Script, X : INX : STA.w $012F
    JMP .done
  .flicker
    LDA.w Experiment_Script, X : INX : STA.l Exp_Flicker
    BNE ..running
      PHX : SEP #$10
      JSR Exp_ShowKalyxoPalette
      REP #$10 : PLX
    ..running
    JMP .done
  .cut
    JSR .open_message
    LDA.w Experiment_Script, X : INX : STA.l Exp_Arg
    LDA.b #$00 : STA.l Exp_CutArm
    LDA.b #$05 : STA.l Exp_Block
    JMP .done
  .flash
    LDA.w Experiment_Script, X : INX : STA.l Exp_Timer
    LDA.b #$23 : STA.b $9A                ; add white to BG1/BG2/backdrop
    LDA.b #$3F : STA.b $9C
    LDA.b #$5F : STA.b $9D
    LDA.b #$9F : STA.b $9E
    LDA.b #$06 : STA.l Exp_Block
    JMP .done
  ; Actor ops: the actor tables are in bank $7F (long,X only), so the
  ; operands go to $02-$05 and X switches to the actor for the writes.
  .actor
    LDA.w Experiment_Script+3, X : STA.b $05
    LDA.w Experiment_Script+2, X : STA.b $04
    LDA.w Experiment_Script+1, X : STA.b $03
    LDA.w Experiment_Script, X : STA.b $02
    INX #4
    PHX : SEP #$10
    LDX.b $02
    LDA.b $03 : STA.l Exp_ActPose, X
    LDA.b $04 : STA.l Exp_ActX, X : STA.l Exp_ActTX, X
    LDA.b $05 : STA.l Exp_ActY, X : STA.l Exp_ActTY, X
    REP #$10 : PLX
    JMP .done
  .walk
    LDA.w Experiment_Script+2, X : STA.b $04
    LDA.w Experiment_Script+1, X : STA.b $03
    LDA.w Experiment_Script, X : STA.b $02
    INX #3
    PHX : SEP #$10
    LDX.b $02
    LDA.b $03 : STA.l Exp_ActTX, X
    LDA.b $04 : STA.l Exp_ActTY, X
    REP #$10 : PLX
    JMP .done
  .area
    LDA.w Experiment_Script, X : INX
    PHX : SEP #$10
    JSR Exp_StartLoad
    REP #$10 : PLX
    LDA.b #$07 : STA.l Exp_Block
    JMP .done
  .shake
    LDA.w Experiment_Script, X : INX : STA.l Exp_Shake
    JMP .done
  .pose
    LDA.w Experiment_Script, X : STA.b $02
    LDA.w Experiment_Script+1, X : STA.b $03
    INX : INX
    PHX : SEP #$10
    LDX.b $02
    LDA.b $03 : STA.l Exp_ActPose, X
    REP #$10 : PLX

  .done
  REP #$20 : TXA : STA.l Exp_PC : SEP #$20
  SEP #$10
  RTS

  ; Message ID from the script (16-bit). Same call pattern as Arrival_OpenText.
  ; RenderText reaches JumpTableLocal, which needs 8-bit X/Y: save the 16-bit
  ; script offset on the stack across the call.
  .open_message
    REP #$20
    LDA.w Experiment_Script, X : INX : INX
    STA.w $1CF0
    SEP #$20
    STZ.w $1CD8
    LDA.b #$0D : STA.w $010C              ; text end returns to module $0D
    PHX
    SEP #$10
    JSL Experiment_RenderText
    REP #$10
    SEP #$20
    PLX
    RTS
}
; Run the op that holds the script. Clears Exp_Block when it is done.
Exp_RunBlock:
{
  LDA.l Exp_Block : ASL A : TAX
  JMP (.blocks, X)

  .blocks
  dw .none, .wait, .text, .fade, .none, .cut, .flash, .load

  .none
    LDA.b #$00 : STA.l Exp_Block
    RTS

  .wait
    LDA.l Exp_Timer : DEC A : STA.l Exp_Timer
    BNE ..hold
      LDA.b #$00 : STA.l Exp_Block
    ..hold
    RTS

  .text
    JSL Experiment_RenderText
    SEP #$30
    LDA.w $1CD8 : BNE ..hold
      LDA.b #$00 : STA.l Exp_Block
    ..hold
    RTS

  .fade
    LDA.b $1A : AND.b #$01 : BNE ..hold
    LDA.b $13 : CMP.l Exp_Arg : BEQ ..done
    BCC ..up
      DEC.b $13
      RTS
    ..up
      INC.b $13
      RTS
    ..done
      LDA.b #$00 : STA.l Exp_Block
    ..hold
    RTS

  .cut
    JSL Experiment_RenderText
    SEP #$30
    LDA.w $1CD8 : BEQ ..closed            ; the player closed it first
    LDA.l Exp_CutArm : BNE ..count
      ; Armed once the engine waits on the terminator: the next byte in the
      ; decoded buffer ($7F1200, offset $1CD9) is $7F.
      LDA.w $1CD4 : CMP.b #$03 : BNE ..hold
      REP #$10
      LDX.w $1CD9
      LDA.l $7F1200, X
      SEP #$10
      CMP.b #$7F : BNE ..hold
        LDA.b #$01 : STA.l Exp_CutArm
        RTS
    ..count
    LDA.l Exp_Arg : DEC A : STA.l Exp_Arg
    BNE ..hold
      JSR Exp_CloseText
    ..closed
      LDA.b #$00 : STA.l Exp_Block
    ..hold
    RTS

  .flash
    LDA.l Exp_Timer : DEC A : STA.l Exp_Timer
    BNE ..hold
      LDA.b #$00 : STA.l Exp_Block
      JSR Exp_ApplyBaseLook
    ..hold
    RTS

  .load
    JMP Exp_LoadStep
}

; ---------------------------------------------------------
; Screen loads

; A = 0 Kalyxo ($2D), 1 Abyss ($6D). M/X 8-bit.
Exp_StartLoad:
{
  STA.l Exp_Area
  LDA.b #$80 : STA.b $13                  ; forced blank while the screen loads
  STZ.b $9B
  STZ.b $11
  LDA.b #$00 : STA.l Exp_Tries
  LDA.l Exp_Area : BNE .abyss
    LDA.b #$00 : STA.l $7EF3CA            ; light world
    REP #$20
    LDA.w #!ExpArea_Room : STA.b $A0      ; exit data -> OW $2D
    SEP #$20
    RTS
  .abyss
  LDA.b #$40 : STA.l $7EF3CA              ; dark world
  LDA.l Exp_Pearl : BMI .borrowed
    LDA.l $7EF357 : AND.b #$7F : ORA.b #$80 : STA.l Exp_Pearl
    LDA.b #$01 : STA.l $7EF357            ; no bunny for the load
  .borrowed
  REP #$20
  LDA.w #!ExpAbyss_Area : STA.l $7EC14C   ; cached $8A (Exp_CacheScreen wrote the rest)
  LDA.w #!ExpCache_Room : STA.b $A0
  SEP #$20
  RTS
}

; One Module08_OverworldLoad step per frame, called the way
; Module_MainRouting calls it ($10 = $08, DB = $00, M/X 8-bit). Its last step
; sets $10 = $10 (iris open); the scene fades in by itself instead.
Exp_LoadStep:
{
  LDA.b #$08 : STA.b $10
  PHB
  LDA.b #$00 : PHA : PLB
  JSL Experiment_OverworldLoad
  PLB
  SEP #$30
  LDA.b $10 : CMP.b #$10 : BEQ .loaded
    LDA.b #$0D : STA.b $10
    LDA.l Exp_Tries : INC A : STA.l Exp_Tries
    CMP.b #!ExpLoadMaxSteps : BCC .wait
      LDA.b #$02 : STA.l Exp_State        ; stuck: go back to the bedroom
    .wait
    RTS
  .loaded
  LDA.b #$0D : STA.b $10
  STZ.b $11 : STZ.b $B0
  JSR Exp_LoadSheets
  LDA.l Exp_Area : BNE .abyss
    JSR Exp_CacheScreen
    JSR Exp_SaveKalyxoPalettes
    BRA .screen
  .abyss
  JSR Exp_SaveAbyssPalettes
  JSR Exp_ReturnPearl
  .screen
  LDA.b #$01 : STA.b $15                  ; upload CGRAM
  JSR Exp_SetupScreen
  LDA.b #$00 : STA.l Exp_Block
  RTS
}

; The map is built. Show BG2 (map), BG3 (text) and OBJ (actors).
Exp_SetupScreen:
{
  STZ.b $13                               ; display on, brightness 0
  LDA.b #$16 : STA.b $1C                  ; main screen: BG2 + BG3 + OBJ
  STZ.b $1D : STZ.b $1E : STZ.b $1F       ; no subscreen, no windows
  STZ.b $9B                               ; no HDMA
  STZ.b $99                               ; color math everywhere, fixed color
  JSR Exp_ApplyBaseLook
  LDA.b #$01 : STA.l Exp_HideHUD          ; next frame, after the map upload
  REP #$20
  ; Text box position follows Link's screen Y (RenderText_SetDefaultWindowPosition):
  ; screen Y >= $78 puts the box at the top, above the actors.
  LDA.b $E8 : CLC : ADC.w #$00A0 : STA.b $20
  LDA.b $E2 : STA.w $011E                 ; BG2 scroll without shake
  LDA.b $E8 : STA.w $0122
  SEP #$20
  RTS
}

; Put the actor sheets into spriteset slots 0-3 (VRAM $5000-$5FFF) with the
; vanilla loader InitializeTilesets uses (decompress to $7E7800, 3bpp->4bpp,
; write VMDATA). Forced blank must be on. LoadSpriteGraphics ends in RTS, so
; the call returns through an RTL in bank $00.
Exp_LoadSheets:
{
  ; Overworld_LoadAndBuildScreen just set $13 = 0; a lag NMI during the
  ; decompression would write it to INIDISP and drop the VRAM writes.
  LDA.b #$80 : STA.b $13 : STA.w $2100    ; forced blank now and in NMI
  PHB
  LDA.b #$00 : PHA : PLB                  ; GFXSheetPointers_sprite_* are DB-relative
  LDA.b #$80 : STA.w $2115
  STZ.w $2116
  LDA.b #$50 : STA.w $2117                ; VRAM word $5000
  LDX.b #$00
  .next
    PHX
    LDA.l .sheets, X : TAY
    LDA.b #$7E : STA.b $02
    LDX.b #$78                            ; buffer $7E7800
    PHK : PEA.w .return-1
    PEA.w Exp_Bank00_RTL-1
    JML Exp_LoadSpriteGraphics
    .return
    SEP #$30
    PLX
    INX : CPX.b #$04 : BCC .next
  PLB
  RTS

  .sheets
  db !ExpSheet0, !ExpSheet1, !ExpSheet2, !ExpSheet3
}

; Same writes as the vanilla entrance cache ($02D8C5), from the $2D screen
; that just loaded; Exp_StartLoad then swaps in the Abyss area id.
Exp_CacheScreen:
{
  REP #$20
  LDA.w $040A : STA.l $7EC140
  LDA.b $1C   : STA.l $7EC142
  LDA.b $E8   : STA.l $7EC144
  LDA.b $E2   : STA.l $7EC146
  LDA.b $20   : STA.l $7EC148
  LDA.b $22   : STA.l $7EC14A
  LDA.b $8A   : AND.w #$00FF : STA.l $7EC14C
  LDA.b $84   : STA.l $7EC14E
  LDA.w $0618 : STA.l $7EC150
  LDA.w $061C : STA.l $7EC152
  LDA.w $0600 : STA.l $7EC154
  LDA.w $0602 : STA.l $7EC156
  LDA.w $0604 : STA.l $7EC158
  LDA.w $0606 : STA.l $7EC15A
  LDA.w $0610 : STA.l $7EC15C
  LDA.w $0612 : STA.l $7EC15E
  LDA.w $0614 : STA.l $7EC160
  LDA.w $0616 : STA.l $7EC162
  LDA.w $0624 : STA.l $7EC16A
  LDA.w $0626 : STA.l $7EC16C
  LDA.w $0628 : STA.l $7EC16E
  LDA.w $062A : STA.l $7EC170
  LDA.w $0AA0 : STA.l $7EC164             ; $0AA0-$0AA3
  LDA.w $0AA2 : STA.l $7EC166
  SEP #$20
  RTS
}

Exp_ReturnPearl:
{
  LDA.l Exp_Pearl : BPL .done
    AND.b #$7F : STA.l $7EF357
    LDA.b #$00 : STA.l Exp_Pearl
  .done
  RTS
}

; ---------------------------------------------------------
; Palettes. CGRAM buffer $7EC500 (NMI uploads it while $15 != 0):
; rows 2-7 = map, row 0 color 0 = backdrop, rows 9-14 = sprite palettes 1-6.

Exp_SaveKalyxoPalettes:
{
  REP #$30
  LDX.w #$00BE
  .loop
    LDA.l $7EC540, X : STA.l Exp_PalLW, X
    LDA.l $7EC620, X : STA.l Exp_PalSpr, X
    DEX : DEX : BPL .loop
  LDA.l $7EC500 : STA.l Exp_BackLW
  SEP #$30
  RTS
}

; The Abyss keeps its own map palettes; the actors keep their Kalyxo colors.
Exp_SaveAbyssPalettes:
{
  REP #$30
  LDX.w #$00BE
  .loop
    LDA.l $7EC540, X : STA.l Exp_PalDW, X
    LDA.l Exp_PalSpr, X : STA.l $7EC620, X
    DEX : DEX : BPL .loop
  LDA.l $7EC500 : STA.l Exp_BackDW
  SEP #$30
  RTS
}

Exp_ShowKalyxoPalette:
{
  REP #$30
  LDX.w #$00BE
  .loop
    LDA.l Exp_PalLW, X : STA.l $7EC540, X
    DEX : DEX : BPL .loop
  LDA.l Exp_BackLW : STA.l $7EC500
  SEP #$30
  LDA.b #$01 : STA.b $15
  RTS
}

Exp_ShowAbyssPalette:
{
  REP #$30
  LDX.w #$00BE
  .loop
    LDA.l Exp_PalDW, X : STA.l $7EC540, X
    DEX : DEX : BPL .loop
  LDA.l Exp_BackDW : STA.l $7EC500
  SEP #$30
  LDA.b #$01 : STA.b $15
  RTS
}

; Every 4 frames, swap the map between its Kalyxo and Abyss palettes.
Exp_FlickerStep:
{
  LDA.l Exp_Block : CMP.b #$07 : BEQ .off ; a load owns the palettes
  LDA.l Exp_Flicker : BEQ .off
  CMP.b #$FF : BEQ .run
    DEC A : STA.l Exp_Flicker
    BNE .run
      JMP Exp_ShowKalyxoPalette
  .run
  LDA.b $1A : AND.b #$03 : BNE .off
  LDA.b $1A : AND.b #$04 : BEQ .kalyxo
    JMP Exp_ShowAbyssPalette
  .kalyxo
  JMP Exp_ShowKalyxoPalette
  .off
  RTS
}

; Shake the map 2 px left/right every 2 frames (BG2 scroll registers).
Exp_ShakeStep:
{
  LDA.l Exp_Block : CMP.b #$07 : BEQ .done ; a load owns the scroll
  LDA.l Exp_Shake : BEQ .still
  CMP.b #$FF : BEQ .run
    DEC A : STA.l Exp_Shake
    BEQ .still
  .run
  LDA.b $1A : AND.b #$02 : BEQ .left
    LDA.b #$02
    BRA .set
  .left
    LDA.b #$FE
    BRA .set
  .still
  LDA.b #$00
  .set
  STA.l Exp_ShakeX
  REP #$20
  AND.w #$00FF : CMP.w #$0080 : BCC + : ORA.w #$FF00 : +
  CLC : ADC.b $E2 : STA.w $011E
  SEP #$20
  .done
  RTS
}

Exp_ApplyBaseLook:
{
  LDA.l Exp_Block : CMP.b #$06 : BEQ .flashing ; the flash owns the color
  LDA.l Exp_Math : STA.b $9A
  LDA.l Exp_TintR : ORA.b #$20 : STA.b $9C
  LDA.l Exp_TintG : ORA.b #$40 : STA.b $9D
  LDA.l Exp_TintB : ORA.b #$80 : STA.b $9E
  .flashing
  RTS
}

; Close an open message now: RenderText_FinalizeWindow ($1CD4 = 4) clears
; the box and sets $1CD8 = 0 (and $10 = $010C, $11 = 0).
Exp_CloseText:
{
  LDA.w $1CD8 : BEQ .closed
    LDA.b #$04 : STA.w $1CD4
    JSL Experiment_RenderText
    SEP #$30
  .closed
  RTS
}

; ---------------------------------------------------------
; Actors

; Walkers move 1 px toward their target every other frame, X and Y at once.
Exp_MoveActors:
{
  LDA.b $1A : AND.b #$01 : BNE .done
  LDX.b #!ExpActors-1
  .actor
    LDA.l Exp_ActX, X : CMP.l Exp_ActTX, X : BEQ .y
    BCC .right
      DEC A : BRA .set_x
    .right
      INC A
    .set_x
    STA.l Exp_ActX, X
    .y
    LDA.l Exp_ActY, X : CMP.l Exp_ActTY, X : BEQ .next
    BCC .down
      DEC A : BRA .set_y
    .down
      INC A
    .set_y
    STA.l Exp_ActY, X
    .next
    DEX : BPL .actor
  .done
  RTS
}

; Exp_Order = actors by screen Y, largest first (lower on screen = nearer,
; drawn in front); equal Y keeps actor order. Insertion sort, DP $0D-$0F.
Exp_SortActors:
{
  LDX.b #!ExpActors-1
  .init
    TXA : STA.l Exp_Order, X
    DEX : BPL .init
  LDA.b #$01 : STA.b $0E                  ; i
  .outer
    LDX.b $0E
    LDA.l Exp_Order, X : STA.b $0F       ; key actor
    PHX : TAX : LDA.l Exp_ActY, X : STA.b $0D : PLX
    DEX                                   ; j = i - 1
    .inner
      CPX.b #$FF : BEQ .place
      LDA.l Exp_Order, X
      PHX : TAX : LDA.l Exp_ActY, X : PLX
      CMP.b $0D : BCS .place              ; Y[order[j]] >= key Y: stop
      LDA.l Exp_Order, X : STA.l Exp_Order+1, X
      DEX
      BRA .inner
    .place
    INX
    LDA.b $0F : STA.l Exp_Order, X
    INC.b $0E
    LDA.b $0E : CMP.b #!ExpActors : BCC .outer
  RTS
}

; Write every visible actor into the OAM buffer ($0800 low table, $0A20
; size/X-high bytes; ClearOAMBuffer hid all entries this frame), nearest
; actor first (Exp_SortActors), so it is in front. DB = $3A: banks $00-$3F see WRAM $0000-$1FFF, so $0800,Y works.
; DP scratch: $00 actor, $01 pieces left, $02 OAM byte offset, $03 OAM
; entry, $04-$05 base X, $06-$07 base Y, $08-$09 piece X, $0A pose,
; $0C-$0D shake (signed), $0E-$0F walk bob.
Exp_DrawActors:
{
  LDA.l Exp_Block : CMP.b #$06 : BEQ .hidden ; flash
  CMP.b #$07 : BEQ .hidden                ; load
  LDA.l Exp_Math : BEQ .visible           ; black/white looks
  .hidden
  RTS
  .visible
  JSR Exp_SortActors
  STZ.b $00
  STZ.b $02
  STZ.b $03
  LDA.l Exp_ShakeX : STA.b $0C
  STZ.b $0D
  BPL + : DEC.b $0D : +
  .actor
    LDX.b $00
    LDA.l Exp_Order, X : TAX
    LDA.l Exp_ActPose, X : BNE +
      JMP .next
    +
    STA.b $0A
    ; Walking: alternate pose and a 1 px bob every 8 frames.
    STZ.b $0E : STZ.b $0F
    LDA.l Exp_ActX, X : CMP.l Exp_ActTX, X : BNE .moving
    LDA.l Exp_ActY, X : CMP.l Exp_ActTY, X : BEQ .still
    .moving
    LDA.b $1A : AND.b #$08 : BEQ .still
      INC.b $0E
      LDY.b $0A
      LDA.w Exp_Poses_walk_alt, Y : BEQ .still
        STA.b $0A
    .still
    REP #$20
    LDA.l Exp_ActX, X : AND.w #$00FF
    SEC : SBC.b $0C                       ; move with the shaking map
    STA.b $04
    LDA.l Exp_ActY, X : AND.w #$00FF
    SEC : SBC.b $0E
    STA.b $06
    SEP #$20
    LDX.b $0A
    LDA.w Exp_Poses_start, X : TAX        ; X = offset of the pose in .data
    LDA.w Exp_Poses_data, X : BNE +
      JMP .next
    +
    STA.b $01
    INX
    .piece
      LDA.b $03 : CMP.b #$40 : BCC +      ; OAM entries 0-63 only
        RTS
      +
      ; X = base + dx (9 bits)
      REP #$20
      LDA.w Exp_Poses_data, X : AND.w #$00FF
      CMP.w #$0080 : BCC + : ORA.w #$FF00 : +
      CLC : ADC.b $04 : STA.b $08
      SEP #$20
      LDY.b $02
      STA.w $0800, Y
      INX
      ; Y = base + dy; off screen -> $F0
      REP #$20
      LDA.w Exp_Poses_data, X : AND.w #$00FF
      CMP.w #$0080 : BCC + : ORA.w #$FF00 : +
      CLC : ADC.b $06
      CLC : ADC.w #$0010 : CMP.w #$0100 : BCC +
        LDA.w #$0100                      ; -> $F0 below
      +
      SEC : SBC.w #$0010
      SEP #$20
      STA.w $0801, Y
      INX
      LDA.w Exp_Poses_data, X : STA.w $0802, Y : INX ; char
      LDA.w Exp_Poses_data, X : STA.w $0803, Y : INX ; props
      LDA.b $09 : AND.b #$01
      ORA.w Exp_Poses_data, X : INX       ; size
      LDY.b $03
      STA.w $0A20, Y
      LDA.b $02 : CLC : ADC.b #$04 : STA.b $02
      INC.b $03
      DEC.b $01 : BNE .piece
    .next
    INC.b $00
    LDA.b $00 : CMP.b #!ExpActors : BCS .done
    JMP .actor
  .done
  RTS
}
