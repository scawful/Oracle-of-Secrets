# Music Creation Guide

This document details the process for creating and integrating custom music into Oracle of Secrets. The project uses the native Super Nintendo Packet Chip (N-SPC) music format, abstracted through a powerful set of `asar` macros.

## 1. N-SPC Music Format Primer

Music in the N-SPC engine is structured around eight independent channels. Each channel is a stream of bytes that are read sequentially. The stream consists of two types of data:

-   **Commands:** Special bytes (from `$E0` to `$FF`) that control aspects of the sound, such as setting the instrument, changing volume, or calling a subroutine.
-   **Notes:** A note consists of a duration byte followed by one or more tone bytes. The duration byte (e.g., `$48` for a quarter note) determines how long the following tone(s) will play.

## 2. The Macro System (`Core/music_macros.asm`)

To make composing more intuitive, the project uses a comprehensive library of macros that wrap the raw N-SPC commands into readable names. All music files must include `Core/music_macros.asm`.

### Key Concepts

-   **Note Durations:** Constants are defined for standard note lengths (e.g., `!4th`, `!8th`, `!16th`).
-   **Note Tones:** Constants are defined for all notes across several octaves (e.g., `C4`, `G4s` for G#4, `A5`).
-   **Special Notes:** `Tie` (`$C8`) continues the previous note for the new duration, and `Rest` (`$C9`) signifies silence.

### Core Macros

-   **`%SetInstrument(id)`:** Sets the instrument for the current channel (e.g., `%SetInstrument($09)` for Strings). Helper macros like `%Strings()`, `%Piano()`, etc., exist for common instruments.
-   **`%SetTempo(value)`:** Sets the overall playback speed of the song.
-   **`%SetMasterVolume(value)` / `%SetChannelVolume(value)`:** Sets the volume for the entire song or just the current channel.
-   **`%CallSubroutine(address, repeats)`:** The most important macro for structuring songs. It jumps to a labeled subroutine, plays it `repeats+1` times, and then returns. **This is the primary method for looping musical phrases.**
-   **`%VibratoOn(delay, rate, depth)`:** Adds a vibrato effect.
-   **`%TremoloOn(delay, rate, depth)`:** Adds a tremolo (volume fluctuation) effect.
-   **`%SetPan(value)`:** Sets the stereo position (left/right) of the channel.
-   **`%EchoVBits(switch, left, right)`:** Enables and configures echo for the channel.

## 3. Song File Structure

Every song `.asm` file follows a standard structure.

#### 1. Header

The file begins with a header that defines metadata for the song engine.

```asm
MyNewSong:
!ARAMAddr = $D86A      ; Base address in ARAM for this song
dw !ARAMAddr+$0A      ; Pointer to the Intro section
dw !ARAMAddr+$1A      ; Pointer to the Main (looping) section
dw $00FF              ; Default fade-in
dw !ARAMAddr+$02      ; Start of the looping section data
dw $0000
```

#### 2. Channel Pointers

Next is a table of pointers to each of the eight channel data blocks. The `!ARAMC` constant is used to make these pointers relative to the song's ARAM address.

```asm
.Channels
!ARAMC = !ARAMAddr-MyNewSong
dw .Channel0+!ARAMC
dw .Channel1+!ARAMC
; ...up to 8 channels, use dw $0000 for unused channels
```

#### 3. Channel Data

Each channel is a block of code containing commands and notes.

```asm
.Channel0
  %SetMasterVolume($DA)
  %SetTempo(62)
  %SetInstrument($02) ; Tympani
  %SetDurationN(!4th, $7F)
  %CallSubroutine(.sub1+!ARAMC, 23) ; Call subroutine .sub1 24 times
  db End ; $00, signifies end of channel data
```

#### 4. Subroutines

The bulk of a song is made of small, labeled subroutines containing musical phrases. These are placed after the channel data.

```asm
.sub1
  db !4th, B1, B1, !8th, Tie, C2, !4th, F3s
  db End ; Subroutines must also end with $00
```

## 4. How to Add a New Song

1.  **Create the File:** Create a new `.asm` file in the `Music/` directory.
2.  **Copy Template:** Copy the contents of an existing song (e.g., `stone_tower_temple_v2.asm`) into your new file to use as a template.
3.  **Set Header:** Change the main label (e.g., `MyNewSong:`) and set the `!ARAMAddr`. This address must be unique and not conflict with other songs.
4.  **Compose:** Write your music in the channel and subroutine blocks using the note constants and macros.
5.  **Integrate the Song:**
    -   Open `Music/all_music.asm` and add an `incsrc` for your new file.
    -   To replace a vanilla song, find its label in the ROM map and use `org` to place your new song at that address. For example, to replace the Lost Woods theme:
        ```asm
        org $1AADDE ; Original address of Lost Woods theme
        incsrc "Music/MyNewSong.asm"
        ```
    -   To add a new song to the expanded Dark World bank, open `Music/expanded.asm` and add a new entry to the `SongBank_OverworldExpanded_Main` table.

## 5. Proposals for Improved Organization

The current system is functional but can be made more readable and maintainable.

1.  **Standardize Subroutine Naming:** The current convention of `.sub1`, `.sub101`, etc., is ambiguous. A clearer naming scheme would greatly improve readability. 
    -   **Proposal:** Name subroutines based on their musical function, like `.MelodyVerseA`, `.BasslineIntro`, `.PercussionFill1`. This makes the main channel blocks easier to read as a high-level song structure.

2.  **Create a Common Patterns Library:** Many songs use similar rhythmic or melodic patterns (e.g., a standard 4/4 drum beat, an arpeggiated chord). 
    -   **Proposal:** Create a `Music/common_patterns.asm` file. This file could contain a library of generic, reusable subroutines for things like drum patterns, basslines, or common arpeggios. Songs could then `incsrc` this library and call these patterns, reducing code duplication and speeding up composition.

3.  **Develop Advanced Composition Macros:** The existing helper macros are basic. More advanced macros could abstract away the manual process of defining and calling subroutines.
    -   **Proposal:**
        -   `%DefineMeasure(Name, Notes...)`: A macro that takes a name and a list of notes and automatically creates a correctly formatted subroutine block.
        -   `%PlayMeasure(Name, Repeats)`: A macro that automatically calculates the relative address (`+!ARAMC`) and calls `%CallSubroutine`.

    -   **Example Workflow with Proposed Macros:**
        ```asm
        ; --- Subroutine Definitions ---
        %DefineMeasure(VerseMelody, !8th, C4, D4, E4, F4, G4, A4, B4, C5)
        %DefineMeasure(VerseBass, !4th, C2, G2, A2, F2)

        ; --- Channel Data ---
        .Channel0
          ; ... setup ...
          %PlayMeasure(VerseMelody, 4) ; Plays the melody 4 times
          db End

        .Channel1
          ; ... setup ...
          %PlayMeasure(VerseBass, 4) ; Plays the bassline 4 times
          db End
        ```
        This approach would make the main channel data blocks read like a high-level song arrangement, significantly improving clarity.

4.  **Improve In-File Documentation:**
    -   **Proposal:** Encourage the use of comments to label major song sections directly within the channel data (e.g., `; --- VERSE 1 ---`, `; --- CHORUS ---`). This provides crucial signposting when navigating complex song files.
