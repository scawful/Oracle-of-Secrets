; =========================================================
;  Oracle of Secrets - Mask Library
; =========================================================

; 00 = Human
; 01 = Deku
; 02 = Zora
; 03 = Wolf
; 04 = Bunny Hood
; 05 = Minish Form
; 06 = GBC Form
; 07 = Moosh Form
; 08 = Garo Master
!CurrentMask  = $02B2

; Indexed by the bank number
!LinkGraphics = $BC

; If set, player is diving with Zora Mask
!ZoraDiving = $0AAB

; If set, deku is hovering and can drop bombs
DekuFloating   = $70

; If set, on deku platform and can hover
; Unset, will shoot deku bubble instead
DekuHover      = $71

if !ENABLE_MINISH_AUTO_PORTAL == 1
; Volatile portal state after the cart arrays/cache and its 16-bit slot word.
; Boot clears this pair at $0087CE. LinkMain_FrameHook (mask_routines.asm)
; calls MinishPortal_Maintain; collision $64 refreshes contact in Tick.
; ResetTrackVars must not clear it. All portal accesses remain 8-bit absolute.
MinishPortalTimer = $7E07EC ; 0 = armed; $80 = contact, $81-$83 = missing samples
MinishPortalFrame = $7E07ED ; $1A of the last frame the portal was handled
assert MinishPortalFrame == MinishPortalTimer+1
assert MinishPortalTimer >= $7E0718
assert MinishPortalFrame < $7E0800 ; OAM buffer begins here
if !DISABLE_SPRITES == 0
  assert MinishPortalTimer >= $7E0000+!MinecartTrackRoom+$40
  assert MinishPortalTimer >= $7E0000+!MinecartTrackX+$40
  assert MinishPortalTimer >= $7E0000+!MinecartTrackY+$40
  assert MinishPortalTimer > $7E0000+!MinecartTrackCache
  assert MinishPortalTimer > $7E0000+!MinecartDirectionCache
  ; Mount/release/transition paths access MinecartCurrent with M=16.
  assert MinishPortalTimer >= $7E0000+!MinecartCurrent+$02
endif
endif

AddTransformationCloud = $09912C
Link_CheckNewY_ButtonPress = $07B073
LinkItem_EvaluateMagicCost = $07B0AB
Player_DoSfx2 = $078028

; Prototype state follows the Minish portal pair and ends before OAM at $0800.
; StartupMasks clears the shared prototype range $07EE-$07FF.
GaroGuardTimer = $07EE
GaroCounterTimer = $07EF
GaroCooldown = $07F0
GaroLungeTimer = $07FF ; the last byte; $07F1-$07FE belong to Items/
assert GaroGuardTimer == $07EE
assert GaroCooldown < $0800
assert GaroLungeTimer == $07FF

incsrc "Masks/mask_routines.asm"

; Start of free space in bank 07
org $07F89D : pushpc

org $378000
  incbin gfx/bunny_link.4bpp
  incsrc "Masks/bunny_hood.asm"
  print  "End of Masks/bunny_hood.asm       ", pc

org $398000
  incbin gfx/minish_link.4bpp
  print  "End of Minish Form GFX            ", pc
  incsrc "Masks/minish_form.asm"

org $358000
  incbin gfx/deku_link.bin
  incsrc "Masks/deku_mask.asm"

org $368000
  incbin gfx/zora_link.4bpp
  incsrc "Masks/zora_mask.asm"

org $388000
  incbin gfx/wolf_link.4bpp
  incsrc "Masks/wolf_mask.asm"

org $3B8000
  incbin gfx/gbc_link.4bpp
  incsrc "Masks/gbc_form.asm"

org $338000
  incbin gfx/moosh.4bpp
  incsrc "Masks/moosh.asm"

; First complete bank after the two world maps ($40/$41). The player sheet
; uses the existing $BC bank-select loader; no source/base-ROM data is replaced.
org $428000
GaroMasterGraphics:
  incbin "gfx/garo_master.4bpp"
assert pc() == $42F000, "Garo Master must use the complete $7000-byte Link sheet"
  incsrc "Masks/garo_mask.asm"
assert pc() <= $430000, "Garo Master exceeded its graphics/behavior bank"
