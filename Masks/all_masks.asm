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

!KORL_MOUNT_DEFINED = 1

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
  ; Bank $35 from $35F800 holds Booki and Pols Voice (Sprites/all_sprites.asm);
  ; Deku's bank $35 bound is asserted inside Masks/deku_mask.asm before org $07A64B.

org $368000
  incbin gfx/zora_link.4bpp
  incsrc "Masks/zora_mask.asm"

org $388000
  incbin gfx/wolf_link.4bpp
  incsrc "Masks/wolf_mask.asm"

org $3B8000
  incbin gfx/gbc_link.4bpp
  incsrc "Masks/gbc_form.asm"
if !ENABLE_GLADE_AMBUSH == 1
  assert pc() <= $3BF400, "GBC form reached the glade-ambush Kydrog block"
endif

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

; Dedicated bank $53 avoids bank $51 special-overworld semantic code and bank $52 prison ($528000-$529FFF).
if !ENABLE_HORSE_FORM == 1
org $538000
HorseGraphics:
  incbin "gfx/horse_sparse.4bpp"
HorseGraphics_End:
HorseItemRestore:
  incbin "gfx/horse_item_restore.4bpp"
assert pc()-HorseItemRestore == 384, "Native item restoration must contain twelve Tile8s"
HorseRanchRestore:
  incbin "gfx/horse_ranch_restore.4bpp"
assert pc()-HorseRanchRestore == 1024, "Ranch C2 restoration must contain first32 Tile8s"
  incsrc "Masks/gfx/horse_sparse_tables.asm"
assert HorseGraphics_End-HorseGraphics == !Horse_DictionaryBytes, "Sparse dictionary size mismatch"
HorsePalette:
  incbin "gfx/horse_palette.bin"
assert pc()-HorsePalette == 14, "Horse palette must be 14 bytes (7 BGR555 colors for SP-3[9..15])"
HorseNpcTail:
  incbin "gfx/horse_npc_rows.4bpp"
assert pc()-HorseNpcTail == 512, "NPC tail rows must preserve its final four sparse pieces"
  incsrc "Masks/horse_form.asm"
assert pc() <= $53D000, "Horse Form behavior overlapped Sprite_HorseNPC slot in bank $53"
endif

; King of Red Lions Water Mount in dedicated free bank $60 ($608000-$60FFFF, PC 0x300000-0x307FFF;
; zero ZScream / Special Overworld overlap; >= 16 KiB headroom remaining).
org $608000
KORL_Graphics:
  incbin "Data/graphics/mounts/korl_sparse.4bpp"
KORL_Graphics_End:
assert (KORL_Graphics>>16) == ((KORL_Graphics_End-1)>>16), "KORL sparse graphics crossed bank $60"
KORL_Palette:
  incbin "Data/graphics/mounts/korl_palette.bin"
assert pc()-KORL_Palette == 14, "KORL palette must be 14 bytes (7 BGR555 colors for SP-3[9..15])"
  incsrc "Data/graphics/mounts/korl_sparse_tables.asm"
assert KORL_Graphics_End-KORL_Graphics == !KORL_DictionaryBytes, "KORL sparse dictionary size mismatch"
  incsrc "Masks/korl_mount.asm"
assert pc() <= $60C000, "King of Red Lions exceeded its bounded Bank $60 slice ($608000-$60BFFF)"
print "End of Masks/korl_mount.asm       ", pc
