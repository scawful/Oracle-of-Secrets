; =========================================================
; Impa (Intro Guide / Zelda Replacement)
;
; NARRATIVE ROLE: Replaces Zelda's ALTTP role as the intro guide who
;   leads Link through the early game. In Oracle of Secrets, Impa serves
;   as the Sheikah guide who introduces Link to the island. At the Kydrog
;   ambush Farore is kidnapped and Kydrog spares Impa as a messenger to
;   Zelda (msg $35); she stops following ($7EF3CC = 0) and stays at the Hall
;   of Secrets as guide (decisions.org, 2026-09-26).
;
; TERMINOLOGY: "Impa" = Zelda (code) / Impa (narrative)
;   - Uses vanilla ALTTP Zelda sprite code with hooks
;   - Follower system (follower cleared by Kydrog at $7EF3CC = 0)
;   - SPAWNPT tracks player spawn location
;
; SPAWN POINT VALUES:
;   0x00 - Link's house
;   0x01 - Sanctuary (Hall of Secrets)
;   0x02 - Castle Prison
;   0x03 - Castle Basement
;   0x04 - Throne
;   0x05 - Old man cave
;   0x06 - Old man home
;
; ROM HOOKS:
;   $05EE46 - Zelda_AtSanctuary: Set spawn point flag
;   $05EBCF - Sword check modification
;   $029E2E - Module15_0C: Overlay activation
;   $05ED43 - Zelda_BecomeFollower: Prevent spawn point set
;   $05ED63 - NOP padding
;   $05ED10 - Zelda_ApproachHero: Prevent song change
;
; FLAGS WRITTEN:
;   $7EF372 - Spawn point data
;   $7EF3D6 |= 0x04 - OOSPROG bit 2 (intro progress)
;   $7EF3C8 = 0 - SPAWNPT reset
;   $7EF2A3 |= 0x20 - Overlay flag
;
; RELATED:
;   - kydrog.asm (clears the Impa follower)
;   - followers.asm (follower system)
;   - farore.asm (kidnapped in the same scene; Impa stays the guide)
;
; NOTE: The code repurposes vanilla ALTTP Zelda behavior.
;   Comments like "Zelda_AtSanctuary" refer to original ALTTP labels.
; =========================================================

; SPAWN POINT VALUES:
; 0x00 - Link's house
; 0x01 - Sanctuary (Hall of Secrets)
; 0x02 - Castle Prison
; 0x03 - Castle Basement
; 0x04 - Throne
; 0x05 - Old man cave
; 0x06 - Old man home
SPAWNPT         = $7EF3C8

; set spawn point flag for hall of secrets by impa
Impa_SetSpawnPointFlag:
{
  STA.l $7EF372
  LDA.l $7EF3D6 : ORA.b #$04 : STA.l $7EF3D6
  RTL
}

pushpc

; Zelda_AtSanctuary
org $05EE46 : JSL Impa_SetSpawnPointFlag ; @hook module=Sprites name=Impa_SetSpawnPointFlag kind=jsl target=Impa_SetSpawnPointFlag

; TODO: Figure out what to do with this
org $05EBCF : LDA $7EF359 : CMP.b #$05

; Module15_0C
; Change overlay that Impa activates after intro
org $029E2E : LDA.l $7EF2A3 : ORA.b #$20 : STA.l $7EF2A3

; Prevent Impa from setting spawn point
org $05ED43
Zelda_BecomeFollower:
STZ.w $02E4
LDA.b #$00 : STA.l $7EF3C8

org $05ED63 : NOP #5

; Prevent Impa from changing the song
org $05ED10
Zelda_ApproachHero:
  NOP #5

pullpc

; Position-triggered follower hints (default off; see Util/macros.asm).
if !ENABLE_IMPA_FOLLOWER_HINTS == 1
  incsrc "impa_hints.asm"
endif
