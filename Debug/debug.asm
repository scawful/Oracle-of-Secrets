;===========================================================
; Debug Hacks
;
; Gives player all items when pressing L (not for main game)
; Bank 0x3C used for code
; WRITTEN: by XaserLE
; THANKS TO: -MathOnNapkins' Zelda Doc's
; -wiiqwertyuiop for his Zelda Disassembly
;===========================================================

namespace Debug
{
  Main: 
  {
    lorom

    ORG $068365 ; go to an originally JSL that is executed every frame
    JSL $3CA62A ; overwrite it (originally JSL $099F91)

    ORG $3CA62A ; go to expanded space to write our routine (keep EveryFrame.asm in mind for the right adresses)

    LDA $F2     ; load unfiltered joypad 1 register (AXLR|????)
    CMP #$20    ; L button pressed?
    BEQ $03     ; if yes, branch behind the jump that leads to the end and load items instead
    JMP END

    LDA #$03    ; 0 - nothing. 1 - bow w/ no arrows. 2 - bow w/ arrows. 3 - silver arrows
    STA $7EF340
    LDA #$02    ; 0 - nothing. 1 - blue boomerang. 2 - red boomerang
    STA $7EF341
    LDA #$01    ; 0 - nothing. 1 - hookshot.
    STA $7EF342
    LDA #$32    ; How many bombs you have. Can exceed 0x50, up to 0xff.
    STA $7EF343
    LDA #$02    ; 0 - nothing. 1 - Mushroom. 2 - Magic Powder
    STA $7EF344
    LDA #$01    ; 0 - nothing. 1 - Fire Rod
    STA $7EF345
    LDA #$01    ; 0 - nothing. 1 - Ice Rod
    STA $7EF346
    LDA #$01    ; 0 - nothing. 1 - Bombos Medallion
    STA $7EF347
    LDA #$01    ; 0 - nothing. 1 - Ether Medallion
    STA $7EF348
    LDA #$01    ; 0 - nothing. 1 - Quake Medallion
    STA $7EF349
    LDA #$01    ; 0 - nothing. 1 - Torch
    STA $7EF34A
    LDA #$01    ; 0 - nothing. 1 - Magic Hammer
    STA $7EF34B
    LDA #$03    ; 0 - nothing. 1 - shovel. 2 - flute, no bird. 3 - flue, bird activated
    STA $7EF34C
    LDA #$01    ; 0 - nothing. 1 - bug catching net
    STA $7EF34D
    LDA #$01    ; 0 - nothing. 1 - Book of Mudora
    STA $7EF34E
    LDA #$01    ; 0 - nothing. 1 - has bottles.
    STA $7EF34F
    LDA #$01    ; 0 - nothing. 1 - cane of somaria.
    STA $7EF350
    LDA #$01    ; 0 - nothing. 1 - cane of byrna.
    STA $7EF351
    LDA #$01    ; 0 - nothing. 1 - magic cape.
    STA $7EF352
    LDA #$02    ; 0 - nothing. 1 - scroll looking thing that works like mirror. 2 - mirror with correct graphic.
    STA $7EF353
    LDA #$02    ; 0 - normal strength. 1 - Power Gloves. 2 - Titan's Mitt
    STA $7EF354
    LDA #$01    ; 0 - nothing. 1 - pegasus boots. 
                ; *Just having the boots isn't enough to dash. You must have the ability flag corresponding to run set as well. See $379.
    STA $7EF355
    LDA #$01    ; 0 - nothing. 1 - flippers. Having this allows you to swim, but doesn't make the swim ability text show up by itself. See $379. Unlike the boots, the ability is granted, as long as you have this item.
    STA $7EF356
    LDA #$01    ; 0 - nothing. 1 - moon pearl.
    STA $7EF357
    LDA #$01    ; 0-No sword. 1-Fighter Sword. 2-Master Sword. 3-Tempered Sword. 4-Golden Sword
    STA $7EF359
    LDA #$01    ; 0-No shield. 1-Blue Shield. 2-Hero's Shield. 3-Mirror Shield  
    STA $7EF35A
    LDA #$00    ; 0-Green Jerkin. 1-Blue Mail. 2-Red Mail
    STA $7EF35B
    LDA #$02    ; 0-No bottle. 1-Mushroom (no use). 2-Empty bottle. 3-Red Potion. 4-Green Potion. 5-Blue Potion. 6-Fairy. 7-Bee. 8-Good Bee
    STA $7EF35C
    LDA #$08    ; second bottle
    STA $7EF35D
    LDA #$05    ; third bottle
    STA $7EF35E
    LDA #$06    ; fourth bottle
    STA $7EF35F
    LDA #$E7    ; 2 bytes for rupees (goal, for counting up)
    STA $7EF360
    LDA #$03
    STA $7EF361

    ; a few bytes for dungeon items like compasses, maps and big keys are here, we jump over that

    LDA #$A0    ; health capacity (maximum number of hearts)
    STA $7EF36C
    LDA #$80    ; magic power, maximum is 0x80
    STA $7EF36E
    LDA #$A0    ; Fill all hearts
    STA $7EF372
    LDA #$07    ; Pendants: Bit 0 = Courage, Bit 1 = Wisdom, Bit 2 = Power
    STA $7EF374
    LDA #$32    ; How many arrows you have. Can exceed 0x70.
    STA $7EF377
    LDA #$6E    ; Ability Flags: Bit 0: ----. Bit 1: Swim. Bit 2: Run / Dash. Bit 3: Pull. Bit 4: ----. Bit 5: Talk. Bit 6: Read. Bit 7: ----
    STA $7EF379
    LDA #$7F
    STA $7EF37A ; Crystals: Bit 0 = Misery Mire, Bit 1 = Dark Palace, Bit 2 = Ice Palace, Bit 3 = Turtle Rock, Bit 4 = Swamp Palace, Bit 5 = Gargoyle's Domain, Bit 6 = Skull Woods
    LDA #$02    ; Magic usage: 0: normal consumption. 1: 1/2 consumption. 2: 1/4 consumption
    STA $7EF37B

    END:

    JSL $099F91 ; at least execute original code

    RTL
  }
}