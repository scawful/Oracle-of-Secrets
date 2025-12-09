  ; This is which room each track should start in if it hasn't already
  ; been given a track.
  .TrackStartingRooms
  dw $0098, $0088, $0087, $0088, $0089, $0089, $0089, $0089
  dw $0089, $0089, $0089, $0089, $0089, $0089, $0089, $0089
  dw $0089, $0089, $0089, $0089, $0089, $0089, $0089, $0089
  dw $0089, $0089, $0089, $0089, $0089, $0089, $0089, $0089

  ; This is where within the room each track should start in if it hasn't
  ; already been given a position. This is necessary to allow for more
  ; than one stopping point to be in one room.
  .TrackStartingX
  dw $1190, $1160, $1300, $1100, $1300, $1300, $1300, $1300
  dw $1300, $1300, $1300, $1300, $1300, $1300, $1300, $1300
  dw $1300, $1300, $1300, $1300, $1300, $1300, $1300, $1300
  dw $1300, $1300, $1300, $1300, $1300, $1300, $1300, $1300

  .TrackStartingY
  dw $1380, $10C9, $1100, $10D0, $1100, $1100, $1100, $1100
  dw $1100, $1100, $1100, $1100, $1100, $1100, $1100, $1100
  dw $1100, $1100, $1100, $1100, $1100, $1100, $1100, $1100
  dw $1100, $1100, $1100, $1100, $1100, $1100, $1100, $1100
