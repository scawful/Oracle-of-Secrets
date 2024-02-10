;===========================================================
; Debug Hacks
;
; Gives player all items when pressing L (not for main game)
; Bank 0x3C used for code
; WRITTEN: by XaserLE, refactored by scawful
; THANKS TO: -MathOnNapkins' Zelda Doc's
; -wiiqwertyuiop for his Zelda Disassembly
;===========================================================

lorom

!Bow = $7EF340
!Boomerang = $7EF341
!Hookshot = $7EF342
!Bombs = $7EF343
!MagicPowder = $7EF344
!FireRod = $7EF345
!IceRod = $7EF346
!BunnyMask = $7EF348
!DekuMask = $7EF349
!ZoraMask = $7EF347
!Lamp = $7EF34A
!MagicHammer = $7EF34B
!Flute = $7EF34C
!JumpFeather = $7EF34D
!BookOfMudora = $7EF34E
!Bottles = $7EF34F
!CaneOfSomaria = $7EF350
!CaneOfByrna = $7EF351
!MagicCape = $7EF352
!Mirror = $7EF353
!TitansMitt = $7EF354
!PegasusBoots = $7EF355
!Flippers = $7EF356
!MoonPearl = $7EF357
!WolfMask = $7EF358
!Sword = $7EF359
!Shield = $7EF35A
!Mail = $7EF35B
!Bottle1 = $7EF35C
!Bottle2 = $7EF35D
!Bottle3 = $7EF35E
!Bottle4 = $7EF35F
!Rupees = $7EF360
!RupeesGoal = $7EF361
!HealthCapacity = $7EF36C
!MagicPower = $7EF36E
!Hearts = $7EF372
!Pendants = $7EF374
!Arrows = $7EF377
!AbilityFlags = $7EF379
!Crystals = $7EF37A
!MagicUsage = $7EF37B

org $068365
  JSL $3CA62A ; Overwrite JSL executed every frame

org $3CA62A ; Expanded space for our routine
{
  LDA $F2 : CMP #$30 : BEQ $03 : JMP END ; Check L and R button

  ; 0 - nothing. 1 - bow w/ no arrows. 2 - bow w/ arrows. 3 - silver arrows
  LDA #$02 : STA !Bow

  ; 0 - nothing. 1 - blue boomerang. 2 - red boomerang
  LDA #$02 : STA !Boomerang

  ; 0 - nothing. 1 - hookshot
  LDA #$01 : STA !Hookshot 

  ; How many bombs you have. Can exceed 0x50, up to 0xff.
  LDA #$50 : STA !Bombs

  ; 0 - nothing. 1 - Mushroom. 2 - Magic Powder
  LDA #$02 : STA !MagicPowder

  ; 0 - nothing. 1 - Fire Rod
  LDA #$01 : STA !FireRod 
             STA !IceRod 

  ; 0 - nothing. 1 - Lamp
  LDA #$01 : STA !Lamp 
             STA !MagicHammer

  LDA #$01 : STA !JumpFeather

  LDA #$01 : STA !BunnyMask 

  LDA #$01 : STA !DekuMask
  LDA #$01 : STA !ZoraMask 
  LDA #$01 : STA !WolfMask
  LDA #$01 : STA !MagicCape

  ; 0 - nothing. 1 - shovel. 2 - flute, no bird. 3 - flue, bird activated
  LDA #$03 : STA !Flute
  LDA #$01 : STA !BookOfMudora  
  LDA #$01 : STA !CaneOfByrna 
             STA !CaneOfSomaria 

  LDA #$02 : STA !Mirror 
             STA !TitansMitt

  LDA #$01 : STA !PegasusBoots 
             STA !Flippers 
             STA !MoonPearl 
             STA !WolfMask

  ; 0 - nothing. 1 - Fighter Sword. 2 - Master Sword. 3 - Tempered Sword. 4 - Golden Sword
  LDA #$02 : STA !Sword

  ; 0 - nothing. 1 - Fighter Shield. 2 - Fire Shield. 3 - Mirror Shield
  LDA #$01 : STA !Shield

  ; 0 - nothing. 1 - Green Mail. 2 - Blue Mail. 3 - Red Mail
  LDA #$01 : STA !Mail

  ; 0-No bottle. 
  ; 1-Mushroom (no use). 2-Empty bottle. 
  ; 3-Red Potion. 4-Green Potion. 
  ; 5-Blue Potion. 6-Fairy. 
  ; 7-Bee. 8-Good Bee
  LDA #$01 : STA !Bottles ; has bottles 
  LDA #$03 : STA !Bottle1 
  LDA #$05 : STA !Bottle2 
  LDA #$04 : STA !Bottle3
  LDA #$06 : STA !Bottle4

  ; How many arrows you have. Can exceed 0x70.
  LDA #$32 : STA !Arrows

  ; 2 bytes for rupees (goal, for counting up)
  LDA #$E7 : STA !Rupees
  LDA #$03 : STA !RupeesGoal



  ; Pendants: Bit 0 = Courage, Bit 1 = Wisdom, Bit 2 = Power
  LDA #$00 : STA !Pendants

  ; Ability Flags: Bit 0: ----. 
  ; Bit 1: Swim.
  ; Bit 2: Run / Dash.
  ; Bit 3: Pull. Bit 4: ----. 
  ; Bit 5: Talk. 
  ; Bit 6: Read. Bit 7: ----
  LDA #$6E : STA !AbilityFlags

  ; Crystals: 
  ; Bit 0 = Misery Mire
  ; Bit 1 = Dark Palace
  ; Bit 2 = Ice Palace 
  ; Bit 3 = Turtle Rock
  ; Bit 4 = Swamp Palace
  ; Bit 5 = Gargoyle's Domain
  ; Bit 6 = Skull Woods
  LDA #$00 : STA !Crystals 

  ; Magic usage: 0: normal consumption. 1: 1/2 consumption. 2: 1/4 consumption
  LDA #$02 : STA !MagicUsage

  ; health capacity (maximum number of hearts)
  LDA #$A0 : STA !HealthCapacity

  ; fill all hearts
  LDA #$A0 : STA !Hearts
  
  ; magic power, maximum is 0x80
  LDA #$80 : STA !MagicPower

END:

  JSL $099F91 ; Execute original code
  RTL
}