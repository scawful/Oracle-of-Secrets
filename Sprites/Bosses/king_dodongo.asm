
org $1E86E5
KingHelmasaur_CheckBombDamage:

org $1E8385
HelmasaurKing_CheckMaskDamageFromHammer:
#_1E8385: LDA.w $0DB0,X
#_1E8388: CMP.b #$03
#_1E838A: BCS .exit

JSR KingHelmasaur_CheckBombDamage
.exit
RTS
