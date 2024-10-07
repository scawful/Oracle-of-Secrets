# This Makefile is used to extract the song data from the ROM
# The song data is extracted from the ROM and saved as a binary file
ROMFILE:= ../Roms/oos154.sfc

SONGBINS:= song01.bin \
           song02.bin \
           song03.bin \
           song04.bin \
           song05.bin \
           song06.bin \
           song07.bin \
           song08.bin \
           song09.bin \
           song0A.bin \
					 song0B.bin \
           song0C.bin \
           song0D.bin \
           song0E.bin \
           song0F.bin

.PHONY: clean

all: $(ROMFILE) $(SONGBINS)

clean:
	@rm -f $(SONGBINS)

# Triforce Intro Size: 201 bytes (0x00C9)
song01.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=859951 count=201 status=none

# Light World Overture Size 1899 bytes (0x76B)
song02.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=860152 count=1899 status=none

song03.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=862051 count=1085 status=none

song04.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=863136 count=574 status=none

song05.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=863710 count=1157 status=none

song06.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=864867 count=1394 status=none

song07.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=866261 count=1333 status=none

song08.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=867594 count=348 status=none

song09.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=867942 count=2214 status=none

song0A.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=870156 count=227 status=none

# TODO: Songs beneath this line don't have accurate skip or count
# Blame ZScream for having innacurate song size labels
song0B.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=859689 count=244 status=none

song0C.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=865054 count=255 status=none

song0D.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=865309 count=364 status=none

song0E.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=865673 count=15 status=none

song0F.bin: $(ROMFILE)
	@dd if=$< of=$@ bs=1 skip=865688 count=760 status=none
