; =========================================================
; Item Graphics
; Lack of an item will be handled by the "NothingGFX" data
; Everything else will be used as follows:
;   top left, top right, bottom left, bottom right
; =========================================================

NothingGFX:
	dw $20F5, $20F5, $20F5, $20F5
  
; ---------------------------------------------------------

BowsGFX:
	dw $28BA, $28E9, $28E8, $28CB ; Empty bow
	dw $28BA, $28BB, $28CA, $28CB ; Bow and arrows
	dw $28BA, $28E9, $28E8, $28CB ; Empty silvers bow
	dw $28BA, $28BB, $24CA, $28CB ; Silver bow and arrows

; ---------------------------------------------------------

BoomsGFX:
	dw $2CB8, $2CB9, $2CC9, $ACB9 ; Blue boomerang
	dw $24B8, $24B9, $24C9, $A4B9 ; Red boomerang

; ---------------------------------------------------------

HookGFX:
	dw $24F5, $24F6, $24C0, $24F5 ; Hookshot
  dw $2C17, $3531, $2D40, $3541 ; Ball & Chain

; ---------------------------------------------------------

BombsGFX:
	dw $2CB2, $2CB3, $2CC2, $6CC2 ; Bombs

; ---------------------------------------------------------

PowderGFX:
	dw $2444, $2445, $2446, $2447 ; Mushroom
	dw $283B, $283C, $283D, $283E ; Powder

; ---------------------------------------------------------

Fire_rodGFX:
	dw $24B0, $24B1, $24C0, $24C1 ; Fire Rod

; ---------------------------------------------------------

Ice_rodGFX:
	dw $2CB0, $2CBE, $2CC0, $2CC1 ; Ice Rod

; ---------------------------------------------------------
; formerly Quake

DekuMaskGFX:
  dw $2066, $6066, $2076, $6076

; ---------------------------------------------------------
; formerly Ether

BunnyHoodGFX:
  dw $3469, $7469, $3479, $7479

; ---------------------------------------------------------

LampGFX:
	dw $24BC, $24BD, $24CC, $64CC

; ---------------------------------------------------------

HammerGFX:
	dw $24B6, $24B7, $20C6, $24C7

; ---------------------------------------------------------

ShovelGFX:
	dw $30D0, $20D1, $30E0, $30E1

; ---------------------------------------------------------

OcarinaGFX:
  dw $2CD4, $2CD5, $2CE4, $2CE5 ; Blue
  dw $3CD4, $3CD5, $3CE4, $3CE5 ; Green
  dw $24D4, $24D5, $24E4, $24E5 ; Red
  dw $34D4, $34D5, $34E4, $34E5 ; Gold

; ---------------------------------------------------------

BigKeyGFX:
  dw $34D6, $74D6, $34E6, $34E7

; ---------------------------------------------------------

BigChestKeyGFX:
  dw $34BF, $74BF, $34E6, $34E7

; ---------------------------------------------------------

MapGFX:
  dw $2936, $2937, $2946, $2947 

; ---------------------------------------------------------

TreasureChestGFX:
  dw $294B, $294C, $294D, $294E

; ---------------------------------------------------------
; formerly fishing net

JumpFeatherGFX:
  dw $2840, $2841, $3C42, $3C43

; ---------------------------------------------------------

BookGFX:
	dw $3CA5, $3CA6, $3CD8, $3CD9 

; ---------------------------------------------------------

BottlesGFX:
  dw $2044, $2045, $2046, $2047 ; Mushroom
	dw $2837, $2838, $2CC3, $2CD3 ; Empty bottle
	dw $24D2, $64D2, $24E2, $24E3 ; Red potion
	dw $3CD2, $7CD2, $3CE2, $3CE3 ; Green potion
	dw $2CD2, $6CD2, $2CE2, $2CE3 ; Blue potion
	dw $2855, $6855, $2C57, $2C5A ; Fairy
	dw $2837, $2838, $2839, $283A ; Bee
	dw $2837, $2838, $2839, $283A ; Good bee
  dw $2837, $2838, $3CF7, $3CF8 ; Magic Bean
  dw $2837, $2838, $3CFB, $3CFC ; Milk Bottle

; ---------------------------------------------------------

SomariaGFX:
	dw $24DC, $24DD, $24EC, $24ED 

; ---------------------------------------------------------

ByrnaGFX:
	dw $2CDC, $2CDD, $2CEC, $2CED

FishingRodGFX:
  dw $2C82, $2C83, $2C8B, $2C8C 

PortalRodGFX:
  dw $2CF0, $24F1, $30EC, $E4F0

; ---------------------------------------------------------

; formerly Magic Cape
StoneMaskGFX:
  dw $30B4, $30B5, $30C4, $30C5 

; ---------------------------------------------------------

WolfMaskGFX:
  dw $3086, $7086, $3087, $7087
  dw $3086, $7086, $3087, $7087
  dw $3086, $7086, $3087, $7087
  dw $3086, $7086, $3087, $7087

; ---------------------------------------------------------

; Formerly Bombos
ZoraMaskGFX:
  dw $2C88, $6C88, $2C89, $6C89

; ---------------------------------------------------------

MirrorGFX:
	dw $2C72, $2C73, $2C62, $2C63 ; Mirror
  dw $2C62, $2C63, $2C72, $2C73 ; Mirror


; =============================================================================
;  Collectibles
; ---------------------------------------------------------

; vhopppcc cccccccc

QuarterNoteGFX:
  dw $30AA, $306B, $307A, $306A ; Gray Note
  dw $2CAA, $2C6B, $2C7A, $2C6A ; Blue Note
  dw $3CAA, $3C6B, $3C7A, $3C6A ; Green Note
  dw $24AA, $246B, $247A, $246A ; Red Note
  dw $34AA, $346B, $347A, $346A ; Gold Note

; ---------------------------------------------------------

BananaGFX:
  dw $341E, $341F, $342E, $342F ; Banana

RingGFX:
  dw $3049, $304A, $B049, $B04A ; Gray Ring
  dw $2449, $244A, $A449, $A44A ; Red Ring
  dw $2C49, $2C4A, $AC49, $AC4A ; Blue Ring
  dw $3C49, $3C4A, $BC49, $BC4A ; Green Ring
  dw $2849, $284A, $A849, $A84A ; Gold Ring
  dw $3449, $344A, $B449, $B44A ; Silver Ring
  dw $2049, $204A, $A049, $A04A ; Black Ring

PineappleGFX:
  dw $3D7C, $3D7D, $356C, $756C ; Pineapple

RockMeatGFX:
  dw $20D0, $20D1, $20E0, $20E1 ; Rock Meat

SeashellGFX:
  dw $2D06, $2D07, $2D16, $2D17 ; Seashell

HoneycombGFX:
  dw $28F9, $68F9, $28FB, $28FC ; Honeycomb

DekuStickGFX:
  dw $2067, $20F5, $2077, $20F5 ; Deku Stick

; =========================================================
; Equipped Items

PegasusBootsGFX:
  dw $2429, $242A, $242B, $242C ; Pegasus Boots 

; ---------------------------------------------------------

PowerGloveGFX:
  dw $30DA, $30DB, $30EA, $30EB ; Worn-Out Glove
  dw $28DA, $28DB, $28EA, $28EB ; Power Glove

; ---------------------------------------------------------

FlippersGFX:
  dw $2C9A, $2C9B, $2C9D, $2C9E 

; ---------------------------------------------------------

MoonPearlGFX:
  dw $2433, $2434, $2435, $2436 

; ---------------------------------------------------------

SwordGFX:
  dw $2C64, $2CCE, $2C75, $EC64 ; level one 
  dw $2C64, $2C65, $2C74, $2D26 ; level two 
  dw $248A, $2465, $3C74, $2D48 ; level three
  dw $288A, $2865, $2C74, $2D39 ; level four

; ---------------------------------------------------------

ShieldGFX:
  dw $2CFD, $6CFD, $2CFE, $6CFE ; baby shield
  dw $2CFF, $6CFF, $2C9F, $6C9F ; island shield
  dw $2C80, $2C81, $2C8D, $2C8E ; mirror shield

; ---------------------------------------------------------

TunicGFX:
  dw $3C68, $7C68, $3C78, $7C78 ; green tunic
  dw $2C68, $6C68, $2C78, $6C78 ; blue tunic
  dw $2468, $6468, $2478, $6478 ; red tunic

; =============================================================================
; Static Text on the Menu 

SelectItemTXT:
  dw $2562, $2554, $255B, $2554
  dw $2552, $2563, $2417, $2417
  dw $2558, $2563, $2554, $255C

QuestStatusTXT:
  dw $2560, $2564, $2554, $2562
  dw $2563, $2417, $2562, $2563
  dw $2550, $2563, $2564, $2562 

AreaNameTXT:
  dw $243F, $2550, $2561, $2554
  dw $2550, $2417, $255D, $2550
  dw $255C, $2554, $241C, $2430
  dw $2430, $2430, $2430, $2430
  dw $2430, $2430, $2430, $2430 