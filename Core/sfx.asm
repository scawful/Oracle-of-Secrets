; =========================================================
; SFX instruments - Table: ARAM $3E00, ROM $1A:9C04

; ID     VOL L,R     Pitch    SRCN     ADSR      Gain    Mult   Name
; -----------------------------------------------------------------------------
; $00    $70, $70    $1000    $00      $F6 $6A   $B8     $03    Fwoosh
; $01    $70, $70    $1000    $01      $8E $E0   $B8     $02    Swish
; $02    $70, $70    $1000    $14      $FE $6A   $B8     $02    Bomp
; $03    $70, $70    $1000    $03      $FE $F8   $B8     $0D    Ting
; $04    $70, $70    $1000    $04      $FE $6A   $7F     $03    Rrrrr
; $05    $70, $70    $1000    $02      $FE $6A   $7F     $03    Clunk
; $06    $70, $70    $1000    $05      $FE $6A   $70     $03    Ching
; $07    $70, $70    $1000    $06      $FE $6A   $70     $03    Fwomp
; $08    $70, $70    $1000    $08      $FA $6A   $70     $03    Squee
; $09    $70, $70    $1000    $06      $FE $6A   $70     $01    Unused
; $0A    $70, $70    $1000    $07      $FE $6A   $70     $05    Bzzzrt
; $0B    $70, $70    $1000    $0B      $FE $6A   $B8     $03    Brrfft
; $0C    $70, $70    $1000    $0C      $FE $E0   $B8     $02    Brrwwww
; $0D    $70, $70    $1000    $0D      $F9 $6E   $B8     $03    Twee
; $0E    $70, $70    $1000    $0E      $FE $F5   $B8     $07    Pwing
; $0F    $70, $70    $1000    $0F      $FE $F5   $B8     $06    Pling
; $10    $70, $70    $1000    $01      $FE $FC   $B8     $03    Chshtsh
; $11    $70, $70    $1000    $10      $8E $E0   $B8     $03    Splssh
; $12    $70, $70    $1000    $08      $8E $E0   $B8     $02    Weewoo
; $13    $70, $70    $1000    $14      $8E $E0   $B8     $02    Brbrbrb
; $14    $70, $70    $1000    $0A      $88 $E0   $B8     $02    Bwow
; $15    $70, $70    $1000    $17      $8E $E0   $B8     $02    Uughf
; $16    $70, $70    $1000    $15      $FF $E0   $B8     $04    Aaaaaa
; $17    $70, $70    $1000    $03      $DF $11   $B8     $0F    Twing
; $18    $70, $70    $1000    $01      $88 $E0   $B8     $01    Whooo

; -----------------------------------------------------------------------------

; SFX instruments by usage

; $00   SFX1.13, SFX1.14
;       SFX2.07, SFX2.09, SFX2.0D, SFX2.0E, SFX2.2C, SFX2.3A
;       SFX3.05, SFX3.26
;       SFXU2533

; $01   SFX1.01, SFX1.02, SFX1.03, SFX1.04
;       SFX2.01, SFX2.02, SFX2.12, SFX2.1A, SFX2.1E, SFX2.1F
;       SFX2.21, SFX2.23, SFX2.29, SFX2.32, SFX2.39
;       SFX3.02, SFX3.1E, SFX3.23, SFX3.31

; $02   SFX2.03, SFX2.04, SFX2.08, SFX2.0B, SFX2.12, SFX2.1F, SFX2.21
;       SFX3.06, SFX3.0E
;       SFXU2831

; $03   SFX2.06
;       SFX3.0A, SFX3.30

; $04   SFX2.3C
;       SFX3.32
;       SFXU2831

; $05   SFX2.10, SFX2.11, SFX2.22
;       SFX3.18, SFX3.3E
;       SFXU252D

; $06   SFX2.05, SFX2.0A, SFX2.0F, SFX2.3B
;       SFX3.04, SFX3.14, SFX3.25

; $07   SFX2.14, SFX2.15, SFX2.33
;       SFX3.01, SFX3.11, SFX3.12, SFX3.19, SFX3.27, SFX3.28, SFX3.29, SFX3.35, SFX3.39
;       SFXU26A2

; $08   SFX3.17

; $09   nothing

; $0A   SFX1.15, SFX1.16
;       SFX3.1C, SFX3.2A, SFX3.2B, SFX3.2C

; $0B   SFX2.27
;       SFX3.0B, SFX3.0F, SFX3.2E, SFX3.34, SFX3.35, SFX3.36, SFX3.3C, SFX3.3D, SFX3.3F

; $0C   SFX2.2A
;       SFX3.07, SFX3.08, SFX3.09

; $0D   SFX1.0B, SFX1.0C, SFX1.17, SFX1.18, SFX1.1B, SFX1.1C
;       SFX2.13, SFX2.20, SFX2.31, SFX2.3E, SFX2.3F
;       SFX3.0C, SFX3.13, SFX3.24
;       SFXU1EE2, SFXU279D, SFXU27F6, SFXU2807, SFXU2818

; $0E   SFX1.0D, SFX1.0E, SFX1.0F, SFX1.10, SFX1.1D, SFX1.1E, SFX1.1F, SFX1.20
;       SFX2.2B, SFX2.37
;       SFX3.0D, SFX3.10, SFX3.1B, SFX3.2F, SFX3.33, SFX3.3A, SFX3.3B

; $0F   SFX2.2D
;       SFX3.1A, SFX3.1D, SFX3.20, SFX3.2D, SFX3.37
;       SFXU1D1C

; $10   SFX2.16, SFX2.17, SFX2.18, SFX2.19

; $11   SFX2.1B, SFX2.1C, SFX2.24, SFX2.25, SFX2.28, SFX2.2E, SFX2.34, SFX3.28, SFX2.3D

; $12   SFX3.04

; $13   SFX1.07, SFX1.08
;       SFX2.0C, SFX2.35, SFX2.36
;       SFX3.03, SFX3.15, SFX3.16, SFX3.25, SFX3.38

; $14   SFX3.21, SFX3.22
;       SFXU277E

; $15   SFX2.26, SFX2.30
;       SFXU1F13

; $16   SFX1.11, SFX1.12
;       SFX2.1D
;       SFX3.1F

; $17   SFX2.2C, SFX2.3A

; $18   SFX1.09, SFX1.0A

; -----------------------------------------------------------------------------
; SFX1 - queued via $012D | Table: ARAM $17C0, ROM $1A:8B70

; ID          ARAM      ROM         Name
; -----------------------------------------------------------------------------
; SFX1.01     $2652     $1A9A02     Rain / Zora area
; SFX1.02     $2662     $1A9A12     Rain / Zora area (packaged with $01)
; SFX1.03     $2677     $1A9A27     Rain
; SFX1.04     $2687     $1A9A37     Rain (packaged with $03)
; SFX1.05     $284F     $1A9BFF     Silence
; SFX1.06     $284F     $1A9BFF     Silence (packaged with $05)
; SFX1.07     $2739     $1A9AE9     The Rumbling
; SFX1.08     $2736     $1A9AE6     The Rumbling (packaged with $08)
; SFX1.09     $1C8E     $1A903E     Wind
; SFX1.0A     $1CBC     $1A906C     Wind (packaged with $09 by APU)
; SFX1.0B     $1BA3     $1A8F53     Flute song by flute boy
; SFX1.0C     $1B62     $1A8F12     Flute song by flute boy (packaged with $0B)
; SFX1.0D     $1B0E     $1A8EBE     Magic jingle
; SFX1.0E     $1B1D     $1A8ECD     Magic jingle (packaged with $0D)
; SFX1.0F     $1B2C     $1A8EDC     Crystal / Save and quit
; SFX1.10     $1B3E     $1A8EEE     Crystal / Save and quit (packaged with $0F)
; SFX1.11     $1EAC     $1A925C     Choir melody
; SFX1.12     $1EC8     $1A9278     Choir countermelody (packaged with $11)
; SFX1.13     $1AD2     $1A8E82     Large boss swoosh
; SFX1.14     $1AE1     $1A8E91     Large boss swoosh (packaged with $13)
; SFX1.15     $1AF0     $1A8EA0     Triforce door / Pyramid hole opening
; SFX1.16     $1AFF     $1A8EAF     VOMP (packaged with $15)
; SFX1.17     $1C24     $1A8FD4     Flute song for weathervane
; SFX1.18     $1BE3     $1A8F93     Flute song for weathervane (packaged with $17)
; SFX1.19     $0000     -------     Nothing (unused)
; SFX1.1A     $0000     -------     Nothing (unused; packaged with $19)
; SFX1.1B     $1BA3     $1A8F53     Flute song by flute boy duplicate (unused)
; SFX1.1C     $1B62     $1A8F12     Flute song by flute boy duplicate (unused; packaged with $1B)
; SFX1.1D     $1B0E     $1A8EBE     Magic jingle duplicate (unused)
; SFX1.1E     $1B1D     $1A8ECD     Magic jingle duplicate (unused; packaged with $1D)
; SFX1.1F     $1B2C     $1A8EDC     Crystal / Save and quit duplicate (unused)
; SFX1.20     $1B3E     $1A8EEE     Crystal / Save and quit duplicate (unused; packaged with $1F)

; $80..$FF          Initiates a fade to half volume for SFX1


; -----------------------------------------------------------------------------
; SFX2 - queued via $012E | Table: ARAM $1820, ROM $1A:8BD0

; ID          ARAM      ROM         Name
; -----------------------------------------------------------------------------
;      00     $0020     -------     Undefined; when queued value of $40, $C0, $80
; SFX2.01     $2614     $1A99C4     Slash
; SFX2.02     $2625     $1A99D5     Slash
; SFX2.03     $2634     $1A99E4     Slash
; SFX2.04     $2643     $1A99F3     Slash
; SFX2.05     $25DD     $1A998D     Clink
; SFX2.06     $25D7     $1A9987     Bombable door clink
; SFX2.07     $25B7     $1A9967     Fwoosh
; SFX2.08     $25E3     $1A9993     Arrow smash
; SFX2.09     $25AD     $1A995D     Boomerang fwish
; SFX2.0A     $25C7     $1A9977     Hookshot clink
; SFX2.0B     $2478     $1A9828     Placing bomb
; SFX2.0C     $269C     $1A9A4C     Explosion
; SFX2.0D     $2414     $1A97C4     Powder (paired $0D→$3F)
; SFX2.0E     $2404     $1A97B4     Fire rod shot
; SFX2.0F     $24C3     $1A9873     Ice rod shot
; SFX2.10     $23FA     $1A97AA     Hammer use
; SFX2.11     $23F0     $1A97A0     Hammering peg
; SFX2.12     $23CD     $1A977D     Digging
; SFX2.13     $23A0     $1A9750     Flute (paired $13→$3E)
; SFX2.14     $2380     $1A9730     Cape on
; SFX2.15     $2390     $1A9740     Cape off / Wallmaster grab
; SFX2.16     $232C     $1A96DC     Staircase
; SFX2.17     $2344     $1A96F4     Staircase
; SFX2.18     $2356     $1A9706     Staircase
; SFX2.19     $236E     $1A971E     Staircase
; SFX2.1A     $2316     $1A96C6     Tall grass / Hammer hitting bush
; SFX2.1B     $2307     $1A96B7     Shallow water
; SFX2.1C     $2301     $1A96B1     Mire shallow water
; SFX2.1D     $22BB     $1A966B     Lifting object
; SFX2.1E     $2577     $1A9927     Cutting grass
; SFX2.1F     $22E9     $1A9699     Item breaking
; SFX2.20     $22DA     $1A968A     Item falling in pit
; SFX2.21     $22CF     $1A967F     Bomb hitting ground / General thud
; SFX2.22     $2107     $1A94B7     Pushing object / Armos bounce
; SFX2.23     $22B1     $1A9661     Boots dust
; SFX2.24     $22A5     $1A9655     Splashing (paired $24→$3D)
; SFX2.25     $2296     $1A9646     Mire shallow water again?
; SFX2.26     $2844     $1A9BF4     Link taking damage
; SFX2.27     $2252     $1A9602     Fainting
; SFX2.28     $2287     $1A9637     Item splash
; SFX2.29     $243F     $1A97EF     Rupee refill (paired $29→$3B)
; SFX2.2A     $2033     $1A93E3     Fire splash / Bombos spell
; SFX2.2B     $1FF2     $1A93A2     Heart beep / Text box
; SFX2.2C     $1FD9     $1A9389     Sword up (paired $2C→$3A) (also uses instrument $17)
; SFX2.2D     $20A6     $1A9456     Magic drain
; SFX2.2E     $1FCA     $1A937A     GT opening (paired $2E→$39)
; SFX2.2F     $1F47     $1A92F7     GT opening / Water drain (paired $2F→$38)
; SFX2.30     $1EF1     $1A92A1     Cucco
; SFX2.31     $20CE     $1A947E     Fairy
; SFX2.32     $1D47     $1A90F7     Bug net
; SFX2.33     $1CDC     $1A908C     Teleport (paired $34→$33)
; SFX2.34     $1F6F     $1A931F     Teleport (paired $34→$33)
; SFX2.35     $1C67     $1A9017     Shaking
; SFX2.36     $1C64     $1A9014     Mire entrance (extends above; paired $35→$36)
; SFX2.37     $1A43     $1A8DF3     Spin charged
; SFX2.38     $1F6F     $1A931F     Water sound (paired $2F→$38)
; SFX2.39     $1F9C     $1A934C     Thunder (paired $2E→$39)
; SFX2.3A     $1FE7     $1A9397     Sword up (paired $2C→$3A)
; SFX2.3B     $2462     $1A9812     Rupee refill (paired $29→$3B)
; SFX2.3C     $1A37     $1A8DE7     Error beep
; SFX2.3D     $22AB     $1A965B     Big splash (paired $24→$3D)
; SFX2.3E     $23B5     $1A9765     Flute (paired $13→$3E)
; SFX2.3F     $2435     $1A97E5     Powder (paired $0D→$3F)

; -----------------------------------------------------------------------------
; SFX3 - queued via $012F |  Table: ARAM $191C, ROM $1A:8CCC

; ID          ARAM      ROM         Name
; -----------------------------------------------------------------------------
;      00     $003C     -------     Undefined; when queued value of $40, $C0, $80
; SFX3.01     $1A18     $1A8DC8     Sword beam
; SFX3.02     $254E     $1A98FE     TR opening
; SFX3.03     $224A     $1A95FA     Pyramid hole
; SFX3.04     $220E     $1A95BE     Angry soldier
; SFX3.05     $25B7     $1A9967     Lynel shot / Javelin toss
; SFX3.06     $21F5     $1A95A5     Swoosh
; SFX3.07     $223D     $1A95ED     Cannon fire
; SFX3.08     $21E6     $1A9596     Damage to enemy; $0BEX.4=1
; SFX3.09     $21C1     $1A9571     Enemy death
; SFX3.0A     $21A9     $1A9559     Collecting rupee
; SFX3.0B     $2198     $1A9548     Collecting heart
; SFX3.0C     $218E     $1A953E     Non-blank text character
; SFX3.0D     $21B5     $1A9565     HUD heart
; SFX3.0E     $2182     $1A9532     Opening chest
; SFX3.0F     $24B9     $1A9869     ♪Do do do doooooo♫ (paired $0F→$3C→$3D→$3E→$3F)
; SFX3.10     $216D     $1A951D     Map (paired $10→$3B)
; SFX3.11     $214F     $1A94FF     Opening item menu / Bomb shop guy breathing
; SFX3.12     $215E     $1A950E     Closing item menu / Bomb shop guy breathing
; SFX3.13     $213B     $1A94EB     Throwing object / Stalfos jump
; SFX3.14     $246C     $1A981C     Key door
; SFX3.15     $212F     $1A94DF     Door / Chest (used with SFX2.29)
; SFX3.16     $2123     $1A94D3     Armos Knight thud
; SFX3.17     $25A6     $1A9956     Rat squeak
; SFX3.18     $20DD     $1A948D     Dragging
; SFX3.19     $250A     $1A98BA     Fireball / Laser shot
; SFX3.1A     $1E8A     $1A923A     Chest reveal jingle (paired $1A→$38)
; SFX3.1B     $20B6     $1A9466     Puzzle jingle (paired $1B→$3A)
; SFX3.1C     $1A62     $1A8E12     Damage to enemy
; SFX3.1D     $20A6     $1A9456     Magic meter
; SFX3.1E     $2091     $1A9441     Wing flapping
; SFX3.1F     $204B     $1A93FB     Link falling
; SFX3.20     $276C     $1A9B1C     Menu / Text cursor moved
; SFX3.21     $27E2     $1A9B92     Damage to boss
; SFX3.22     $26CF     $1A9A7F     Boss dying / Deleting file
; SFX3.23     $2001     $1A93B1     Spin attack swoosh (paired $23→$39)
; SFX3.24     $2043     $1A93F3     OW map perspective change
; SFX3.25     $1E9D     $1A924D     Pressure switch (also uses instrument $06)
; SFX3.26     $1E7B     $1A922B     Lightning / Game over / Laser / Ganon bat / Trinexx lunge
; SFX3.27     $1E40     $1A91F0     Agahnim charge
; SFX3.28     $26F7     $1A9AA7     Agahnim / Ganon teleport
; SFX3.29     $1E21     $1A91D1     Agahnim shot
; SFX3.2A     $1E12     $1A91C2     Somaria / Byrna / Ether spell / Helma fire ball
; SFX3.2B     $1DF3     $1A91A3     Electrocution
; SFX3.2C     $1DC0     $1A9170     Bees
; SFX3.2D     $1DA9     $1A9159     Milestone jingle (paired $2D→$37)
; SFX3.2E     $1D5D     $1A910D     Heart container jingle (paired $2E→$35→$34)
; SFX3.2F     $1D80     $1A9130     Key jingle (paired $2F→$33)
; SFX3.30     $1B53     $1A8F03     Magic zap / Plop
; SFX3.31     $1ACA     $1A8E7A     Sprite falling / Moldorm shuffle
; SFX3.32     $1A78     $1A8E28     BOING
; SFX3.33     $1D93     $1A9143     Key jingle (paired $2F→$33)
; SFX3.34     $1D66     $1A9116     Heart container jingle (paired $2E→$35→$34)
; SFX3.35     $1D73     $1A9123     Heart container jingle (paired $2E→$35→$34)
; SFX3.36     $1AA7     $1A8E57     Magic attack
; SFX3.37     $1DB4     $1A9164     Milestone jingle (paired $2D→$37)
; SFX3.38     $1E93     $1A9243     Chest reveal jingle (paired $1A→$38)
; SFX3.39     $2017     $1A93C7     Swish (paired $23→$39)
; SFX3.3A     $20C0     $1A9470     Puzzle jingle (paired $1B→$3A)
; SFX3.3B     $2176     $1A9526     Map (paired $10→$3B)
; SFX3.3C     $248A     $1A983A     Item jingle (paired $0F→$3C→$3D→$3E→$3F)
; SFX3.3D     $2494     $1A9844     Item jingle ($0F→$3C→$3D→$3E→$3F)
; SFX3.3E     $249E     $1A984E     Item jingle (paired $0F→$3C→$3D→$3E→$3F)
; SFX3.3F     $2480     $1A9830     Item jingle (paired $0F→$3C→$3D→$3E→$3F)

; -----------------------------------------------------------------------------
; Unused SFX

; ARAM      ROM         Description
; -----------------------------------------------------------------------------
; $1A5B     $1A8E0B     Noisy fsssh; bleeds into SFX3.1C
; $1D1C     $1A90CC     Radar ping
; $1EE2     $1A9292     Slide whistle / Chirp
; $1F13     $1A92C3     Cucco clucking
; $252D     $1A98DD     Brighter hammer peg
; $2533     $1A98E3     Bat wings flapping
; $2657     $1A9A07     Broken static
; $267C     $1A9A2C     Static; Loops
; $26A2     $1A9A52     Tuba jingle followed by a roar
; $277E     $1A9B2E     UFO winding up
; $279D     $1A9B4D     Distant whistling
; $27C9     $1A9B79     Bwuuuoow
; $27F6     $1A9BA6     Cat call
; $2807     $1A9BB7     Higher pitched cat call
; $2818     $1A9BC8     Reverse cat call
; $2829     $1A9BD9     Dial-up
; $2831     $1A9BE1     Bumper peg

