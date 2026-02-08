# Probe Sprite System

**Last Updated:** October 3, 2025  
**Purpose:** Document the probe sprite detection system used by guards and intelligent enemies

---

## Overview

The **Probe Sprite System** is a collision detection mechanism used by guard-type sprites (Blue Guard, Green Guard, Red Guard) and intelligent enemies to detect Link's presence. Instead of constantly checking collision with Link directly, these enemies spawn invisible "probe" sprites that move in the direction they're facing. When a probe makes contact with Link, it triggers the parent sprite to enter an alert/chase state.

This system is more efficient than constant direct collision checks and creates more realistic enemy behavior where guards react when Link enters their "line of sight."

---

## How It Works

### 1. Probe Spawning

When an enemy wants to check for Link in a specific direction, it spawns a probe sprite:

```asm
; From Sprites/Enemies/darknut.asm
JSL GetDistance8bit_Long : CMP.b #$80 : BCS .no_probe
    JSL Sprite_SpawnProbeAlways_long  ; Spawn probe if Link is nearby
.no_probe
```

**Key Details:**
- Probes are spawned only when Link is within range (distance < $80)
- Uses sprite ID $41 (Blue Guard sprite slot)
- Probes are invisible and have no collision with tiles
- Probes live for a very short time (usually < 1 second)

### 2. Probe Properties

When spawned, probes are configured with special properties:

```asm
; From Sprites/experimental/probe.asm (reference)
Sprite_SpawnProbeAlways:
{
  LDA.b #$41                     ; Use guard sprite ID
  LDY.b #$0A                     ; Sprite slot limit
  JSL Sprite_SpawnDynamically_slot_limited
  BMI .exit
  
  ; Set position (slightly offset from spawner)
  LDA.b $00 : CLC : ADC.b #$08  ; +8 pixels X
  STA.w SprX, Y
  
  LDA.b $02 : CLC : ADC.b #$04  ; +4 pixels Y
  STA.w SprY, Y
  
  ; Set velocity based on direction
  LDA.w .speed_x, X
  STA.w SprXSpeed, Y
  
  LDA.w .speed_y, X
  STA.w SprYSpeed, Y
  
  ; Store parent sprite ID
  TXA : INC A
  STA.w $0DB0, Y  ; Parent sprite index + 1
  STA.w $0BA0, Y
  
  ; Set timers
  LDA.b #$40
  STA.w $0F60, Y  ; Lifetime timer
  STA.w $0E60, Y
  
  LDA.b #$02
  STA.w $0CAA, Y  ; Priority
  
  .exit
  RTS
}
```

**Speed Tables:**
```asm
.speed_x:  ; X velocities for 64 directions
  db $00, $01, $03, $04, $05, $06, $07, $08
  db $08, $08, $07, $06, $05, $04, $03, $01
  db $00, -$01, -$03, -$04, -$05, -$06, -$07, -$08
  ; ... (continues for all 64 directions)
  
.speed_y:  ; Y velocities for 64 directions
  db -$08, -$08, -$07, -$06, -$05, -$04, -$03, -$01
  db $00, $01, $03, $04, $05, $06, $07, $08
  ; ... (continues for all 64 directions)
```

### 3. Probe Detection Logic

The probe sprite checks for collision every frame:

```asm
Probe:
{
  ; Move the probe
  LDY.b #$00
  LDA.w SprXSpeed, X : BPL .positive_x
    DEY
  .positive_x
  CLC : ADC.w SprX, X : STA.w SprX, X
  TYA : ADC.w SprXH, X : STA.w SprXH, X
  
  ; Same for Y...
  
  ; Check if probe hit Link
  REP #$20
  LDA.w $0FD8 : SEC : SBC.b $22  ; Link X - Probe X
  CLC : ADC.w #$0010 : CMP.w #$0020  ; Within hitbox?
  SEP #$20
  BCS .no_contact
  
  REP #$20
  LDA.b $20 : SEC : SBC.w $0FDA  ; Link Y - Probe Y
  CLC : ADC.w #$0018 : CMP.w #$0020
  SEP #$20
  BCS .no_contact
  
  ; Check same floor layer
  LDA.w $0F20, X : CMP.b $EE : BNE .no_contact
  
  .made_contact
  ; Get parent sprite index from $0DB0
  LDA.w $0DB0, X : DEC A : PHX : TAX
  
  ; Trigger parent sprite's alert state
  LDA.w SprAction, X : CMP.b #$03 : BEQ .dont_trigger_parent
    LDA.b #$03 : STA.w SprAction, X  ; Set to chase state
    LDA.b #$10 : STA.w SprTimerA, X  ; Alert duration
    STZ.w SprDelay, X
  .dont_trigger_parent
  
  PLX
  
  .no_contact
  ; Probe has served its purpose, despawn
  STZ.w $0DD0, X
  RTS
}
```

### 4. Parent Sprite Response

When a probe detects Link, the parent sprite (guard/enemy) reacts:

```asm
; From darknut.asm
LDA.w SprTimerD, X : BEQ .not_alerted
  ; Probe detected Link - chase behavior
  LDA.b #$08 : JSL Sprite_ApplySpeedTowardsPlayer
  JSL Sprite_DirectionToFacePlayer
  TYA
  STA.w SprMiscC, X  ; Store facing direction
  STA.w SprMiscE, X
  STA.w SprAction, X
  JSL Guard_ChaseLinkOnOneAxis
  JMP .continue
  
.not_alerted
  ; Normal patrol behavior
  JSR Sprite_Darknut_BasicMove
.continue
```

---

## Usage in Enemies

### Darknut Example

The Darknut uses probes for detection:

```asm
Sprite_Darknut_Main:
{
  ; Only spawn probe if Link is nearby
  JSL GetDistance8bit_Long : CMP.b #$80 : BCS .no_probe
    JSL Sprite_SpawnProbeAlways_long
  .no_probe
  
  ; Check if probe triggered alert
  LDA.w SprTimerD, X : BEQ .not_alerted
    LDA.b #$90 : STA.w SprTimerD, X  ; Refresh alert timer
    ; ... chase logic ...
  .not_alerted
    ; ... patrol logic ...
}
```

### Guard Example (Vanilla)

Vanilla guards use a more sophisticated probe system:

```asm
Guard_ShootProbeAndStuff:
{
  ; Calculate probe direction based on guard facing
  LDA.w SprMiscC, X  ; Guard's facing direction
  
  ; Use direction tables to set probe velocity
  LDY.b #$00
  LDA.w ProbeAndSparkCheckDirXSpeed, Y : STA.b $00
  LDA.w ProbeAndSparkCheckDirYSpeed, Y : STA.b $01
  
  ; Check tile collision before spawning
  JSL Probe_CheckTileSolidity : BCC .passable
    ; Don't spawn probe if blocked by wall
    RTS
  .passable
  
  ; Spawn the probe
  JSR Sprite_SpawnProbeAlways
  
  ; Set probe type and properties
  LDA.w ProbeType, Y : STA.w $0DB0, Y
}
```

---

## Best Practices

### When to Use Probes

✅ **Good Use Cases:**
- Guard-type enemies with "line of sight" detection
- Enemies that patrol and should react when Link crosses their path
- Boss phases where the boss "looks" for Link
- Security systems or alert mechanisms

❌ **Poor Use Cases:**
- Enemies that should always chase Link (use direct distance checks)
- Fast-moving enemies (probes are too slow)
- Enemies that need precise collision (use `Sprite_CheckDamageToLink`)
- Passive enemies that don't react to Link

### Performance Considerations

1. **Distance Check First:** Always check if Link is nearby before spawning probes
   ```asm
   JSL GetDistance8bit_Long : CMP.b #$80 : BCS .skip_probe
   ```

2. **Spawn Frequency:** Don't spawn probes every frame
   ```asm
   LDA.w SprTimerA, X : BNE .dont_spawn  ; Only spawn when timer expires
   ```

3. **Probe Lifetime:** Keep probes short-lived (max 64 frames / ~1 second)

4. **Sprite Slot Limit:** Probes use `Sprite_SpawnDynamically_slot_limited` with a limit of $0A (10 sprites max)

### Common Patterns

**Pattern 1: Continuous Scanning**
```asm
; Spawn probe every N frames
LDA.w SprTimerA, X : BNE .skip
  LDA.b #$20 : STA.w SprTimerA, X  ; Every 32 frames
  JSL Sprite_SpawnProbeAlways_long
.skip
```

**Pattern 2: Direction-Based Detection**
```asm
; Only probe in facing direction
LDA.w SprAction, X  ; Current facing direction
ASL A : TAY
LDA.w .probe_angles, Y  ; Get angle for this direction
JSL Sprite_SpawnProbeAlways_long
```

**Pattern 3: Alert State Management**
```asm
; Probe triggers alert, which decays over time
LDA.w SprTimerD, X : BEQ .calm
  ; Alert state - chase Link
  DEC.w SprTimerD, X  ; Decay alert
  BNE .still_alert
    ; Return to patrol when timer expires
    JSR Enemy_ReturnToPatrol
  .still_alert
  JSR Enemy_ChaseLink
  RTS
.calm
  JSR Enemy_Patrol
  RTS
```

---

## Integration with Other Systems

### Parrying System

Probes work alongside the guard parrying system:

```asm
; Darknut blocks sword attacks while alerted
LDA.w SprTimerD, X : BEQ .not_alert
  JSL Guard_ParrySwordAttacks  ; Active parrying when alert
.not_alert
```

### Multi-Part Sprites

For multi-part enemies (like Kydreeok), each segment can spawn probes:

```asm
; Head segment spawns probe
LDA.w SprSubtype, X : BEQ .not_head
  JSL Sprite_SpawnProbeAlways_long
.not_head
```

### Boss Mechanics

Bosses can use probes for phase transitions:

```asm
; Boss becomes aggressive when probe detects Link
.phase_check
LDA.w SprTimerD, X : BEQ .passive_phase
  LDA.b #$02 : STA.w SprAction, X  ; Aggressive phase
  JMP .continue
.passive_phase
  ; Spawn probe occasionally
  LDA.w SprFrame : AND.b #$3F : BNE .continue
    JSL Sprite_SpawnProbeAlways_long
.continue
```

---

## Debugging Probes

### Making Probes Visible

For debugging, you can make probes draw sprites:

```asm
; In probe sprite's main routine (normally invisible)
JSR Sprite_PrepOamCoord
LDA.b #$00 : JSL SpriteDraw_SingleLarge  ; Draw debug sprite
```

### Checking Probe State

Use WRAM viewer in Mesen-S:
- `$0DB0,X` - Parent sprite index (should be parent + 1)
- `$0DD0,X` - Probe state (should be $09 = active)
- `$0F60,X` - Probe lifetime timer

### Common Issues

**Problem:** Probe doesn't despawn
- **Solution:** Ensure `STZ.w $0DD0, X` is called in all exit paths

**Problem:** Parent doesn't react
- **Solution:** Check that `$0DB0,X` correctly stores parent index + 1

**Problem:** Probe spawns too frequently
- **Solution:** Add distance check and timer between spawns

---

## WRAM Variables

### Probe-Specific Variables

| Address | Variable | Purpose |
|---------|----------|---------|
| `$0DB0,X` | Probe Parent Index | Parent sprite slot + 1 (0 = no parent) |
| `$0BA0,X` | Probe Parent Copy | Backup of parent index |
| `$0F60,X` | Probe Lifetime | Frames until probe despawns |
| `$0E60,X` | Probe Timer Copy | Backup lifetime timer |
| `$0CAA,X` | Probe Priority | Draw priority (usually $02) |

### Parent Sprite Variables

| Address | Variable | Purpose |
|---------|----------|---------|
| `SprTimerD,X` | Alert Timer | Frames remaining in alert state |
| `SprTimerA,X` | Spawn Cooldown | Frames until next probe spawn |
| `SprAction,X` | Behavior State | Current AI state (patrol/chase) |

---

## Reference Implementation

See `Sprites/experimental/probe.asm` for the complete vanilla probe system implementation. Key enemies using probes:

- **Blue/Green/Red Guards** (`Sprite_41`, `Sprite_42`, `Sprite_43`) - Full probe system
- **Darknut** (`Sprites/Enemies/darknut.asm`) - Simplified probe detection
- **Blind Boss** (Special case: probes check for boss-specific collision)

---

## Future Enhancements

### Proposed Features

1. **Directional Probes:** Spawn probes in multiple directions simultaneously
2. **Cone of Vision:** Multiple probes in a fan pattern for wider detection
3. **Probe Types:** Different probe behaviors (slow/fast, short/long range)
4. **Team Alerts:** Probes trigger multiple nearby enemies
5. **Sound Integration:** Play alert sound when probe detects Link

### Castle Ambush System

Probes will be used in the upcoming castle ambush feature:
- Guards patrol castle corridors
- Probes detect Link entering restricted areas
- Detection triggers reinforcement spawn
- Multiple guards share alert state
- Capture sequence activates on detection

See: `Core/capture.asm` and `Sprites/Enemies/custom_guard.asm` (experimental)

---

## See Also

- `Docs/World/Sprites/Enemies/Darknut.md` - Darknut implementation with probes
- `Docs/World/Guides/SpriteCreationGuide.md` Section 10.9 - Advanced AI Patterns
- `Core/sprite_functions.asm` - `Sprite_SpawnProbeAlways_long` function
- `Core/symbols.asm` - Probe-related function addresses
