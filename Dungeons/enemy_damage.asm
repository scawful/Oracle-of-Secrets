; Change Enemy Damage 
; tzpd bbbb
;   t - TODO
;   z - High priority target for bees to give hints
;   p - Powder interaction (0: normal | 1: ignore)
;   d - Behavior when a boss spawns (0: die | 1: live)
;   b - bump damage class
;   Bump damage classes are read from a table at $06F42D
;   Each table entry has 3 values, for green, blue, and red mails
;   class   g    b    r
;   0x00    2    1    1
;   0x01    4    4    4
;   0x02    0    0    0
;   0x03    8    4    2
;   0x04    8    8    8
;   0x05   16    8    4
;   0x06   32   16    8
;   0x07   32   24   16
;   0x08   24   16    8
;   0x09   64   48   24

; Moblin
org $0DB266+$12
  db $01

; Hopping Bulb Plant
org $0DB266+$22
  db $04

; Stalfos Knight
org $0DB266+$91
  db $04

org $0DB330
  db $05

; Armos Knight
org $0DB266+$53
  db $13

org $0DB1C6 ;  0x53 - ARMOS KNIGHT health 
  db 64

org $0DB44C+$7F
  db $64

