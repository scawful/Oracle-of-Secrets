#!/usr/bin/env python3
"""Static audit + compiled 65816 (LakeSnes) tests for ALL Sprites/Enemies/*.asm.

Covers:
1. Static parity contract across all 20 files in Sprites/Enemies/:
   - Zero unconditional `SprState == $06 : BEQ .dying` body-vanish bugs.
   - Vanilla `$0DD0 == $06` pre-poof drawing while `SprTimerA >= #$0A`
     (and `$10` for Vampire Bat subtype 2 in keese.asm).
   - Skipping `Sprite_OAM_AllocateDeferToPlayer` while `SprState == $06`.
   - Off-screen `Sprite_PrepOamCoord` Carry clipping (`BCC`).
   - Adequate `!NbrTiles >= 4 + max_body_tiles` so `SpriteModule_Die`'s
     4 poof tiles + `SprNbrOAM -= 4` never underflow or overflow Region A.
   - `SprFlash` pre-shifted vs raw flash parity (`EOR` instead of `ORA`).
   - Enemy-specific parity fixes (Octorok ripple/recoil/palette/submerged init,
     AntiKirby priority 2 & `%GotoAction(7)`, SeaUrchin HP=4 recoil/no premature
     drop, Keese HP=1/no premature drop/throttled `Sprite_SelectNewDirection`,
     PolsVoice flute `$06`/`$1F` death, Puffstool spore no `ForcePrizeDrop_long`,
     HelmetChuchu `X & #$03` speed mask).
2. Compiled 65816 execution (real Asar output on LakeSnes C CPU core) for every
   custom enemy in Sprites/Enemies/*.asm, isolated in temp dirs with zero
   dependency on built/shared ROMs.
"""
from __future__ import annotations

import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_wolfos_combat import (  # noqa: E402
    Cpu,
    JUMP_TABLE_LOCAL_ASM,
    find_asar,
    get_lakesnes_lib,
    lorom_pc,
    parse_sym,
)

ROOT = Path(__file__).resolve().parents[1]
ENEMIES_DIR = ROOT / "Sprites" / "Enemies"

# Custom enemies that have their own _Long sprite loop in Sprites/Enemies/.
CUSTOM_ENEMIES = [
    ("octorok.asm", "Sprite_Octorok_Long", "Sprite_Octorok_Draw", "Sprite_Octorok_Prep", 1, True),
    ("darknut.asm", "Sprite_Darknut_Long", "Sprite_Darknut_Draw", "Sprite_Darknut_Prep", 3, True),
    ("goriya.asm", "Sprite_Goriya_Long", "Sprite_Goriya_Draw", "Sprite_Goriya_Prep", 2, True),
    ("helmet_chuchu.asm", "Sprite_HelmetChuchu_Long", "Sprite_HelmetChuchu_Draw", "Sprite_HelmetChuchu_Prep", 3, True),
    ("booki.asm", "Sprite_Booki_Long", "Sprite_Booki_Draw", "Sprite_Booki_Prep", 1, True),
    ("puffstool.asm", "Sprite_Puffstool_Long", "Sprite_Puffstool_Draw", "Sprite_Puffstool_Prep", 2, True),
    ("anti_kirby.asm", "Sprite_AntiKirby_Long", "Sprite_AntiKirby_Draw", "Sprite_AntiKirby_Prep", 2, True),
    ("pols_voice.asm", "Sprite_PolsVoice_Long", "Sprite_PolsVoice_Draw", "Sprite_PolsVoice_Prep", 2, True),
    ("thunder_ghost.asm", "Sprite_ThunderGhost_Long", "Sprite_ThunderGhost_Draw", "Sprite_ThunderGhost_Prep", 3, True),
    ("poltergeist.asm", "Sprite_Poltergeist_Long", "Sprite_Poltergeist_Draw", "Sprite_Poltergeist_Prep", 6, False),
    ("sea_urchin.asm", "Sprite_SeaUrchin_Long", "Sprite_SeaUrchin_Draw", "Sprite_SeaUrchin_Prep", 1, True),
    ("keese.asm", "Sprite_Keese_Long", "Sprite_Keese_Draw", "Sprite_Keese_Prep", 2, True),
    ("leever.asm", "Sprite_Leever_Long", "Sprite_Leever_Draw", None, 1, False),
    ("business_scrub.asm", "Sprite_BusinessScrub_Long", "Sprite_BusinessScrub_Draw", "Sprite_BusinessScrub_Prep", 4, False),
]

# Non-custom / hook-only files in Sprites/Enemies/ audited for absence of _Long vanish bugs.
AUX_ENEMY_FILES = [
    "business_scrub_shield.asm",
    "chain_chomp_opt.asm",
    "custom_guard.asm",
    "darknut_weapon_hitbox.asm",
    "eon_scrub.asm",
    "stalfos_patrol.asm",
]

# Sprite WRAM addresses
SPR_Y = 0x0D00
SPR_X = 0x0D10
SPR_ACTION = 0x0D80
SPR_FRAME = 0x0D90
SPR_MISCA = 0x0DA0
SPR_MISCB = 0x0DB0
SPR_GFX = 0x0DC0
SPR_STATE = 0x0DD0
SPR_MISCC = 0x0DE0
SPR_TIMERA = 0x0DF0
SPR_TYPE = 0x0E20
SPR_SUBTYPE = 0x0E30
SPR_NBROAM = 0x0E40
SPR_HEALTH = 0x0E50
SPR_MISCG = 0x0ED0
SPR_TIMERD = 0x0EE0
SPR_FLASH = 0x0B89
WORLDFLAG = 0x7E0FFF
SONG_FLAG = 0x030F

EXTERNAL_STUBS = [
    "BlindLaser_SpawnTrailGarnish",
    "BossKit_FireTrail",
    "CheckIfHitBoxesOverlap",
    "D4Warden_Long",
    "D4Warden_Prep",
    "Darknut_CheckDamage",
    "Darknut_DrawFlash",
    "Darknut_PrepDefense",
    "DragPlayer",
    "ForcePrizeDrop_long",
    "GetDistance8bit_Long",
    "GetRandomInt",
    "Link_ReceiveItem",
    "OAM_AllocateFromRegionC",
    "Probe_CheckTileSolidity",
    "Sound_SetSfx2PanLong",
    "SpriteSFX_QueueSFX2WithPan",
    "SpriteSFX_QueueSFX3WithPan",
    "Sprite_ApplySpeedTowardsPlayer",
    "Sprite_BounceFromTileCollision",
    "Sprite_BounceTowardPlayer",
    "Sprite_CheckActive",
    "Sprite_CheckDamageFromPlayer",
    "Sprite_CheckDamageToPlayer",
    "Sprite_CheckDamageToPlayerSameLayer",
    "Sprite_CheckIfLifted",
    "Sprite_CheckIfRecoiling",
    "Sprite_CheckTileCollision",
    "Sprite_ConvertVelocityToAngle",
    "Sprite_DamageFlash_Long",
    "Sprite_DirectionToFacePlayer",
    "Sprite_DrawShadow",
    "Sprite_DrawWaterRipple",
    "Sprite_FloatTowardPlayer",
    "Sprite_InvertSpeed_XY",
    "Sprite_IsBelowPlayer",
    "Sprite_IsToRightOfPlayer",
    "Sprite_Move",
    "Sprite_MoveAltitude",
    "Sprite_MoveLong",
    "Sprite_MoveVert",
    "Sprite_MoveXyz",
    "Sprite_OAM_AllocateDeferToPlayer",
    "Sprite_PlayerCantPassThrough",
    "Sprite_PrepOamCoord",
    "Sprite_ProjectSpeedTowardsEntityLong",
    "Sprite_ProjectSpeedTowardsPlayer",
    "Sprite_SelectNewDirection",
    "Sprite_SetSpawnedCoordinates",
    "Sprite_SetSpawnedCoords",
    "Sprite_SetupHitBox",
    "Sprite_SpawnDynamically",
    "Sprite_SpawnSparkleGarnish",
    "Sprite_TransmuteToBomb",
    "ThrownSprite_TileAndSpriteInteraction_long",
]


@dataclass
class CompiledPack:
    rom: bytes
    labels: dict[str, int]
    stub_addrs: dict[str, int]


_COMPILED_PACK: CompiledPack | None = None


def build_all_enemies_rom() -> CompiledPack:
    global _COMPILED_PACK
    if _COMPILED_PACK is not None:
        return _COMPILED_PACK

    asar = find_asar()
    assert asar, "asar binary required"

    symbols_txt = (ROOT / "Core" / "symbols.asm").read_text(encoding="utf-8", errors="replace")
    defined_syms: dict[str, int] = {}
    for m in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\$([0-9A-Fa-f]+)", symbols_txt):
        defined_syms[m.group(1)] = int(m.group(2), 16)

    # Read actual symbol table; only define external symbols absent from Core/symbols.asm.
    stub_addrs: dict[str, int] = {}
    extra_defs: list[str] = []
    next_stub = 0x3E8000
    for name in EXTERNAL_STUBS:
        if name in defined_syms:
            addr = defined_syms[name]
            if (addr >> 16) >= 0x01 or (addr & 0xFFFF) >= 0x8000:
                stub_addrs[name] = addr
            continue
        stub_addrs[name] = next_stub
        extra_defs.append(f"{name} = ${next_stub:06X}")
        next_stub += 0x10

    stub_defs = "\n".join(extra_defs)

    # Assemble all 14 custom enemy modules (plus companion shield/hitbox/eon_scrub)
    # into LoROM banks. Note darknut.asm JSRs Goriya_HandleTileCollision in goriya.asm,
    # so both share bank $33.
    bank_includes = [
        ("Sprites/Enemies/octorok.asm", 0x31),
        ("Sprites/Enemies/goriya.asm", 0x33),
        ("Sprites/Enemies/darknut.asm", 0x33),
        ("Sprites/Enemies/darknut_weapon_hitbox.asm", 0x33),
        ("Sprites/Enemies/helmet_chuchu.asm", 0x34),
        ("Sprites/Enemies/booki.asm", 0x35),
        ("Sprites/Enemies/puffstool.asm", 0x36),
        ("Sprites/Enemies/anti_kirby.asm", 0x37),
        ("Sprites/Enemies/pols_voice.asm", 0x38),
        ("Sprites/Enemies/thunder_ghost.asm", 0x39),
        ("Sprites/Enemies/poltergeist.asm", 0x3A),
        ("Sprites/Enemies/sea_urchin.asm", 0x3B),
        ("Sprites/Enemies/keese.asm", 0x3C),
        ("Sprites/Enemies/leever.asm", 0x3D),
        ("Sprites/Enemies/business_scrub.asm", 0x3F),
        ("Sprites/Enemies/business_scrub_shield.asm", 0x3F),
        ("Sprites/Enemies/eon_scrub.asm", 0x3F),
    ]

    inc_lines = []
    seen_banks: set[int] = set()
    for rel, bank in bank_includes:
        if bank not in seen_banks:
            inc_lines.append(f"org ${bank:02X}8000")
            seen_banks.add(bank)
        inc_lines.append(f'incsrc "{rel}"')

    asm_source = f"""lorom
!DISABLE_MASKS = 0
incsrc "Config/feature_flags.asm"
incsrc "Core/sram.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"

POSY      = $0020
POSYH     = $0021
POSX      = $0022
POSXH     = $0023
ROOM      = $00A0
BRANDISH  = $02DA
WORLDFLAG = $7E0FFF

NewMainSprFunction     = $308000
NewSprPrepFunction     = $308010
NewSprRoutinesLong     = $309000
NewSprPrepRoutinesLong = $309400

{stub_defs}
org $3CFF00
Sprite_VampireBat_Draw:
  RTS
Sprite_VampireBat_Main:
  RTS
{JUMP_TABLE_LOCAL_ASM}
{chr(10).join(inc_lines)}
"""

    with tempfile.TemporaryDirectory(prefix="oos-enemy-death-audit-") as td:
        tmp = Path(td)
        rom_path = tmp / "enemies_test.sfc"
        rom_path.write_bytes(b"\x00" * 0x200000)  # 2 MiB (banks $00-$3F)
        src_path = tmp / "main.asm"
        src_path.write_text(asm_source, encoding="utf-8")
        sym_path = tmp / "enemies_test.sym"
        res = subprocess.run(
            [
                asar,
                "--no-title-check",
                "-I" + str(ROOT),
                "--symbols=wla",
                f"--symbols-path={sym_path}",
                str(src_path),
                str(rom_path),
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            errors="replace",
        )
        assert res.returncode == 0, f"asar failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        _COMPILED_PACK = CompiledPack(
            rom=rom_path.read_bytes(),
            labels=parse_sym(sym_path),
            stub_addrs=stub_addrs,
        )
        return _COMPILED_PACK


class EnemyCpuRunner:
    """LakeSnes 65816 execution harness for compiled enemy routines."""

    def __init__(self, pack: CompiledPack):
        self.lib = get_lakesnes_lib()
        assert self.lib is not None, "LakeSnes CPU library (cpu.c) unavailable"
        self.pack = pack
        self.rom = pack.rom
        self.ram = bytearray(0x20000)
        self.calls: list[str] = []
        self.oam_writes: list[tuple[int, int]] = []
        self.offscreen = False
        self.active = False
        self.check_damage_carry = False
        self.random_val = 0x25
        self.darknut_armor = False
        self.region_c_base = 0x0900
        self.ripple_writes: list[int] = []
        self.stubs = {addr: name for name, addr in pack.stub_addrs.items()}
        self.jsr_stubs: dict[int, str] = {}
        for jname in ("Sprite_VampireBat_Draw", "Sprite_VampireBat_Main"):
            if jname in pack.labels:
                self.jsr_stubs[pack.labels[jname]] = jname

        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self._read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self._write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = self.lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self.reset_cpu()

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def reset_cpu(self) -> None:
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, flag, False)
        self.cpu.mf = self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x01FF
        self.cpu.a = self.cpu.x = self.cpu.y = 0
        self.cpu.db = 0

    @staticmethod
    def _ram_off(a: int) -> int | None:
        bank = a >> 16
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def _read(self, a: int) -> int:
        if a in self.stubs:
            return 0x6B  # RTL after stub hook runs
        off = self._ram_off(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = lorom_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, a: int, v: int) -> None:
        off = self._ram_off(a)
        if off is not None:
            self.ram[off] = v & 0xFF
            if 0x0800 <= off < 0x0B00:
                self.oam_writes.append((off, v & 0xFF))

    def get(self, a: int) -> int:
        off = self._ram_off(a)
        assert off is not None
        return self.ram[off]

    def put(self, a: int, v: int) -> None:
        off = self._ram_off(a)
        assert off is not None
        self.ram[off] = v & 0xFF

    def get16(self, a: int) -> int:
        return self.get(a) | (self.get(a + 1) << 8)

    def put16(self, a: int, v: int) -> None:
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def _handle_stub(self, name: str) -> None:
        self.calls.append(name)
        c = self.cpu
        slot = c.x & 0x0F
        if name == "Sprite_PrepOamCoord":
            if self.offscreen:
                c.c = True
                self.put(0x0F00 + slot, 0x01)
            else:
                c.c = False
                self.put16(0x00, 0x0080)
                self.put16(0x02, 0x0070)
                self.put(0x05, 0x20)
                self.put(0x0F00 + slot, 0x00)
        elif name == "Sprite_OAM_AllocateDeferToPlayer":
            self.put16(0x90, 0x0800)
            self.put16(0x92, 0x0A20)
        elif name == "OAM_AllocateFromRegionC":
            self.put16(0x90, self.region_c_base)
            self.put16(0x92, 0x0A40)
        elif name == "Sprite_DrawShadow":
            # Replicate vanilla SpriteDraw_Shadow offset ($0E40 & $1F)*4 from $90
            oam_ptr = self.get16(0x90)
            shadow_off = (self.get(SPR_NBROAM + slot) & 0x1F) * 4
            self.ram[oam_ptr + shadow_off + 2] = 0x38
            self.oam_writes.append((oam_ptr + shadow_off, 0x38))
        elif name == "Sprite_DrawWaterRipple":
            oam_ptr = self.get16(0x90)
            self.ripple_writes.append(oam_ptr)
            for i in range(8):
                self.ram[oam_ptr + i] = 0xEE
                self.oam_writes.append((oam_ptr + i, 0xEE))
        elif name == "Sprite_CheckActive":
            if not self.active:
                # Simulate vanilla PLA : PLA return from caller
                c.c = False
                sp = c.sp
                # Pop CheckActive RTL (3 bytes), then pop Long's own return address? No:
                # Sprite_CheckActive leaves Carry clear when inactive (RTS/BCC).
            else:
                c.c = True
        elif name == "Sprite_CheckDamageFromPlayer":
            c.c = self.check_damage_carry
        elif name == "GetRandomInt":
            c.a = (c.a & 0xFF00) | (self.random_val & 0xFF)
            c.z = (self.random_val & 0xFF) == 0
            c.n = bool(self.random_val & 0x80)
        elif name == "GetDistance8bit_Long":
            c.a = (c.a & 0xFF00) | 0x20
            c.c = False
        elif name == "Darknut_DrawFlash":
            flash = self.get(SPR_FLASH + slot)
            val = (flash | 0x02) if self.darknut_armor else flash
            self.put(0x08, val)
        elif name == "Sprite_SelectNewDirection":
            self.put(SPR_TIMERA + slot, 48)
            self.put(0x0D50 + slot, 8)
        elif name == "Sprite_SpawnDynamically":
            c.n = False
            c.y = 0x05
        elif name == "Sprite_VampireBat_Draw":
            # Simulate VampireBat drawing 1 OAM tile when on-screen
            if not self.offscreen:
                oam_ptr = self.get16(0x90)
                self.ram[oam_ptr + 2] = 0x80
                self.oam_writes.append((oam_ptr + 2, 0x80))

    def call_jsl(self, addr: int, *, x: int = 0, a: int = 0, max_steps: int = 12000) -> int:
        c = self.cpu
        c.mf = True
        c.xf = True
        c.a = a & 0xFF
        c.x = x & 0xFF
        c.y = 0
        c.k = addr >> 16
        c.db = c.k
        c.pc = addr & 0xFFFF
        sentinel_bank = 0x2F
        sentinel_pc = 0x8000
        # Push JSL return address (sentinel - 1)
        ret = sentinel_pc - 1
        self.put(c.sp, sentinel_bank)
        self.put(c.sp - 1, (ret >> 8) & 0xFF)
        self.put(c.sp - 2, ret & 0xFF)
        c.sp -= 3

        steps = 0
        while not (c.k == sentinel_bank and c.pc == sentinel_pc):
            pc_addr = (c.k << 16) | c.pc
            if pc_addr in self.stubs:
                self._handle_stub(self.stubs[pc_addr])
            elif pc_addr in self.jsr_stubs:
                self._handle_stub(self.jsr_stubs[pc_addr])
            self.lib.cpu_runOpcode(self.p)
            steps += 1
            assert steps < max_steps, f"Infinite loop / exceeded {max_steps} steps at ${c.k:02X}:{c.pc:04X}"
        return steps

    def call_jsr(self, addr: int, *, x: int = 0, a: int = 0, max_steps: int = 12000) -> int:
        c = self.cpu
        c.mf = True
        c.xf = True
        c.a = a & 0xFF
        c.x = x & 0xFF
        c.y = 0
        c.k = addr >> 16
        c.db = c.k
        c.pc = addr & 0xFFFF
        sentinel_pc = 0x7F00
        ret = sentinel_pc - 1
        self.put(c.sp, (ret >> 8) & 0xFF)
        self.put(c.sp - 1, ret & 0xFF)
        c.sp -= 2

        steps = 0
        while not (c.k == (addr >> 16) and c.pc == sentinel_pc):
            pc_addr = (c.k << 16) | c.pc
            if pc_addr in self.stubs:
                self._handle_stub(self.stubs[pc_addr])
            elif pc_addr in self.jsr_stubs:
                self._handle_stub(self.jsr_stubs[pc_addr])
            self.lib.cpu_runOpcode(self.p)
            steps += 1
            assert steps < max_steps, f"Infinite loop / exceeded {max_steps} steps at ${c.k:02X}:{c.pc:04X}"
        return steps


class CustomSpriteDeathAuditStaticTests(unittest.TestCase):
    """Static vanilla-parity audit across ALL 20 files in Sprites/Enemies/."""

    def test_all_enemy_files_exist_and_no_vanish_bug(self) -> None:
        actual = sorted(p.name for p in ENEMIES_DIR.glob("*.asm"))
        expected = sorted([name for name, *_ in CUSTOM_ENEMIES] + AUX_ENEMY_FILES)
        self.assertEqual(actual, expected, "Sprites/Enemies file list drifted")

        for filename, long_sym, draw_sym, _, max_tiles, has_shadow in CUSTOM_ENEMIES:
            txt = (ENEMIES_DIR / filename).read_text(encoding="utf-8", errors="replace")
            with self.subTest(file=filename):
                # 1. Must NOT use the unconditional death vanish `CMP.b #$06 : BEQ` in _Long
                long_m = re.search(rf"{long_sym}:(.*?)\n\}}", txt, re.S)
                self.assertIsNotNone(long_m, f"Missing {long_sym}")
                long_body = long_m.group(1)
                self.assertNotRegex(
                    long_body,
                    r"CMP\.b #\$06\s*:\s*BEQ",
                    f"{filename} still unconditionally skips drawing for all $0DD0 == $06!",
                )
                self.assertIn("CMP.b #$0A", long_body, f"{filename} missing vanilla SprTimerA >= $0A threshold")

                # 2. Must preserve !DeathAnimation = 00 and adequate !NbrTiles (except vanilla-hooked leever)
                if "!DeathAnimation" in txt:
                    self.assertRegex(txt, r"!DeathAnimation\s*=\s*00\b")
                if "!NbrTiles" in txt:
                    m_nbr = re.search(r"!NbrTiles\s*=\s*(\d+)", txt)
                    self.assertIsNotNone(m_nbr)
                    nbr_tiles = int(m_nbr.group(1), 10)
                    min_needed = 4 + max_tiles
                    self.assertGreaterEqual(
                        nbr_tiles,
                        min_needed,
                        f"{filename} !NbrTiles={nbr_tiles} too small for 4 poof + {max_tiles} body tiles",
                    )

                # 3. _Draw must clip on Sprite_PrepOamCoord Carry, defer OAM in $06, and handle SprFlash cleanly
                draw_m = re.search(rf"{draw_sym}:(.*?)\n\}}", txt, re.S)
                self.assertIsNotNone(draw_m, f"Missing {draw_sym}")
                draw_body = draw_m.group(1)
                self.assertRegex(
                    draw_body,
                    r"JSL Sprite_PrepOamCoord\s*:\s*BCC\b",
                    f"{filename} missing Sprite_PrepOamCoord Carry offscreen check",
                )
                self.assertIn(
                    "CMP.b #$06",
                    draw_body,
                    f"{filename} {draw_sym} missing SprState == $06 guard around Sprite_OAM_AllocateDeferToPlayer",
                )
                self.assertRegex(
                    draw_body,
                    r"AND\.b #\$0E",
                    f"{filename} {draw_sym} missing clean $0E flash mask",
                )
                self.assertIn("EOR", draw_body, f"{filename} {draw_sym} should XOR flash palette bits cleanly")

        # Aux files must not introduce unconditional $0DD0 == $06 skip
        for filename in AUX_ENEMY_FILES:
            txt = (ENEMIES_DIR / filename).read_text(encoding="utf-8", errors="replace")
            if filename == "eon_scrub.asm":
                self.assertRegex(txt, r"JSL Sprite_PrepOamCoord\s*:\s*BCC\b")
                self.assertIn("CMP.b #$06", txt)
            else:
                self.assertNotRegex(txt, r"CMP\.b #\$06\s*:\s*BEQ")

    def test_specific_parity_contracts(self) -> None:
        octorok = (ENEMIES_DIR / "octorok.asm").read_text(encoding="utf-8")
        self.assertIn("JSL Sprite_CheckIfRecoiling", octorok)
        self.assertIn("ADC.w #$0004 : STA.b $90", octorok)
        self.assertIn("JSL Sprite_DrawWaterRipple", octorok)

        anti_kirby = (ENEMIES_DIR / "anti_kirby.asm").read_text(encoding="utf-8")
        self.assertIn("%GotoAction(7)", anti_kirby)
        self.assertNotIn("%GotoAction(4)", anti_kirby)
        self.assertNotIn("db $0B", anti_kirby)
        self.assertIn("db $2B", anti_kirby)

        sea_urchin = (ENEMIES_DIR / "sea_urchin.asm").read_text(encoding="utf-8")
        self.assertNotIn("ForcePrizeDrop_long", sea_urchin)
        self.assertIn("JSL Sprite_CheckIfRecoiling", sea_urchin)

        keese = (ENEMIES_DIR / "keese.asm").read_text(encoding="utf-8")
        self.assertRegex(keese, r"!Health\s*=\s*01\b")
        self.assertNotIn("ForcePrizeDrop_long", keese)
        self.assertNotIn("STA.w SprNbrOAM, X", keese)
        self.assertIn("CMP.b #$10 : BCC .bat_done", keese)

        pols_voice = (ENEMIES_DIR / "pols_voice.asm").read_text(encoding="utf-8")
        self.assertNotIn("ForcePrizeDrop_long", pols_voice)
        self.assertIn("LDA.b #$1F : STA.w SprTimerA, X", pols_voice)

        puffstool = (ENEMIES_DIR / "puffstool.asm").read_text(encoding="utf-8")
        self.assertNotIn("ForcePrizeDrop_long", puffstool)

        helmet = (ENEMIES_DIR / "helmet_chuchu.asm").read_text(encoding="utf-8")
        self.assertIn("TXA : AND.b #$03 : TAX", helmet)


class CustomSpriteDeathCompiledTests(unittest.TestCase):
    """Real 65816 execution tests across ALL custom enemies in Sprites/Enemies/."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = build_all_enemies_rom()

    def _new_runner(self) -> EnemyCpuRunner:
        r = EnemyCpuRunner(self.pack)
        self.addCleanup(r.close)
        return r

    def _run_death_draw_matrix(
        self,
        *,
        long_sym: str,
        slot: int,
        action: int = 1,
        subtype: int = 0,
        frame: int = 0,
        pre_poof_timer: int = 0x18,
        cutoff_timer: int = 0x09,
        nbr_oam_base: int = 8,
    ) -> None:
        r = self._new_runner()
        entry = self.pack.labels[long_sym]

        def setup_state(state: int, timer_a: int, offscreen: bool, flash: int) -> None:
            r.ram[:] = b"\x00" * len(r.ram)
            r.calls.clear()
            r.oam_writes.clear()
            r.ripple_writes.clear()
            r.offscreen = offscreen
            r.active = False
            r.put(WORLDFLAG, 0)
            r.put(SPR_STATE + slot, state)
            r.put(SPR_TIMERA + slot, timer_a)
            r.put(SPR_ACTION + slot, action)
            r.put(SPR_SUBTYPE + slot, subtype)
            r.put(SPR_FRAME + slot, frame)
            r.put(SPR_NBROAM + slot, nbr_oam_base)
            r.put(SPR_FLASH + slot, flash)
            # Simulate Sprite_TimersAndOAM / SpriteModule_Die $90/$92 allocation:
            # slots 0..3 ($0800..$080F) hold SpriteDeath_DrawPoof; shifted $90=$0810.
            base = 0x0810 if state == 0x06 else 0x0800
            hi_base = 0x0A24 if state == 0x06 else 0x0A20
            r.put16(0x90, base)
            r.put16(0x92, hi_base)

        # 1. Active ($09) on-screen: must allocate OAM and draw body
        setup_state(0x09, 0x00, offscreen=False, flash=0x00)
        r.call_jsl(entry, x=slot)
        self.assertIn("Sprite_OAM_AllocateDeferToPlayer", r.calls, f"{long_sym} active should allocate OAM")
        self.assertGreater(len(r.oam_writes), 0, f"{long_sym} active wrote 0 OAM bytes")

        # 2. Dying pre-poof ($06, timer >= cutoff+1): must draw body cleanly WITHOUT deferring OAM!
        setup_state(0x06, pre_poof_timer, offscreen=False, flash=0x26)
        r.call_jsl(entry, x=slot)
        self.assertNotIn(
            "Sprite_OAM_AllocateDeferToPlayer",
            r.calls,
            f"{long_sym} pre-poof dying must NOT call Sprite_OAM_AllocateDeferToPlayer!",
        )
        body_writes = [addr for addr, _ in r.oam_writes if addr >= 0x0810]
        poof_clobber = [addr for addr, _ in r.oam_writes if 0x0800 <= addr < 0x0810]
        self.assertGreater(len(body_writes), 0, f"{long_sym} vanished during pre-poof SprTimerA=${pre_poof_timer:02X}!")
        self.assertEqual(poof_clobber, [], f"{long_sym} overwrote poof slots 0..3!")

        # 3. Exact boundary minimum active dying frame (cutoff_timer + 1 = $0A for normal sprites)
        setup_state(0x06, cutoff_timer + 1, offscreen=False, flash=0x22)
        r.call_jsl(entry, x=slot)
        self.assertNotIn("Sprite_OAM_AllocateDeferToPlayer", r.calls)
        self.assertGreater(
            len([a for a, _ in r.oam_writes if a >= 0x0810]),
            0,
            f"{long_sym} vanished at boundary SprTimerA=${cutoff_timer + 1:02X}!",
        )

        # 4. Dying poof/cloud window (timer == cutoff_timer, e.g. $09): must NOT draw body!
        setup_state(0x06, cutoff_timer, offscreen=False, flash=0x26)
        r.call_jsl(entry, x=slot)
        self.assertEqual(r.oam_writes, [], f"{long_sym} drew body over explosion cloud at SprTimerA=${cutoff_timer:02X}!")

        # 5. Offscreen clipping (both active & pre-poof): 0 OAM writes, 0 OAM defer!
        for st, tm in ((0x09, 0x00), (0x06, pre_poof_timer)):
            setup_state(st, tm, offscreen=True, flash=0x00)
            r.call_jsl(entry, x=slot)
            self.assertNotIn("Sprite_OAM_AllocateDeferToPlayer", r.calls, f"{long_sym} allocated offscreen")
            self.assertEqual(r.oam_writes, [], f"{long_sym} wrote OAM while offscreen (state=${st:02X})")

    def test_every_custom_enemy_death_and_offscreen_matrix(self) -> None:
        for filename, long_sym, _, _, max_tiles, _ in CUSTOM_ENEMIES:
            with self.subTest(enemy=filename):
                # Poltergeist action=0..2 (action=3 is intentionally hidden flying), subtype=0/chair
                # Leever action=1..2 (action=0 is underground)
                # Goriya subtype=0 (Goriya), subtype=1 (Boomerang also tested separately)
                self._run_death_draw_matrix(
                    long_sym=long_sym,
                    slot=2,
                    action=1,
                    subtype=0,
                    frame=0,
                    pre_poof_timer=0x1F,
                    cutoff_timer=0x09,
                    nbr_oam_base=max(4, max_tiles + 4),
                )

    def test_special_subtypes_death_and_offscreen(self) -> None:
        # Water Octorok (subtype 1), Goriya Boomerang (subtype 1), Fire Keese (subtype 1),
        # Eon Scrub (WORLDFLAG != 0)
        self._run_death_draw_matrix(long_sym="Sprite_Octorok_Long", slot=1, subtype=1, frame=8, nbr_oam_base=6)
        self._run_death_draw_matrix(long_sym="Sprite_Goriya_Long", slot=1, subtype=1, frame=0, nbr_oam_base=6)
        self._run_death_draw_matrix(long_sym="Sprite_Keese_Long", slot=1, subtype=1, frame=0, nbr_oam_base=8)

        # Vampire Bat (Keese subtype 2): draws through SprTimerA >= $10, yields at $0F
        r = self._new_runner()
        keese_long = self.pack.labels["Sprite_Keese_Long"]
        for state, timer_a, expect_bat_draw in (
            (0x09, 0x00, True),
            (0x06, 0x1F, True),
            (0x06, 0x10, True),
            (0x06, 0x0F, False),
        ):
            r.ram[:] = b"\x00" * len(r.ram)
            r.calls.clear()
            r.oam_writes.clear()
            r.put(SPR_STATE + 1, state)
            r.put(SPR_SUBTYPE + 1, 2)
            r.put(SPR_TIMERA + 1, timer_a)
            r.put(SPR_NBROAM + 1, 8)
            r.put16(0x90, 0x0810 if state == 6 else 0x0800)
            r.put16(0x92, 0x0A24 if state == 6 else 0x0A20)
            r.call_jsl(keese_long, x=1)
            if expect_bat_draw:
                self.assertIn("Sprite_VampireBat_Draw", r.calls)
                self.assertGreater(len(r.oam_writes), 0)
            else:
                self.assertNotIn("Sprite_VampireBat_Draw", r.calls)
                self.assertEqual(r.oam_writes, [])

        # Eon Scrub (WORLDFLAG = 1 via Sprite_BusinessScrub_Long)
        r = self._new_runner()
        entry = self.pack.labels["Sprite_BusinessScrub_Long"]
        for timer_a, expect_writes in ((0x1F, True), (0x0A, True), (0x09, False)):
            r.ram[:] = b"\x00" * len(r.ram)
            r.calls.clear()
            r.oam_writes.clear()
            r.put(WORLDFLAG, 1)
            r.put(SPR_STATE + 3, 0x06)
            r.put(SPR_TIMERA + 3, timer_a)
            r.put(SPR_NBROAM + 3, 8)
            r.put16(0x90, 0x0810)
            r.put16(0x92, 0x0A24)
            r.call_jsl(entry, x=3)
            self.assertNotIn("Sprite_OAM_AllocateDeferToPlayer", r.calls)
            if expect_writes:
                self.assertGreater(len(r.oam_writes), 0)
            else:
                self.assertEqual(r.oam_writes, [])

    def test_octorok_locked_audit_palette_flash_ripple_recoil(self) -> None:
        r = self._new_runner()
        draw_entry = self.pack.labels["Sprite_Octorok_Draw"]
        long_entry = self.pack.labels["Sprite_Octorok_Long"]
        prep_entry = self.pack.labels["Sprite_Octorok_Prep"]
        move_entry = self.pack.labels["Sprite_Octorok_Move"]

        # 1. Prep initializes Water Octorok (subtype 1) submerged (action 4, frame 8)
        r.put(SPR_SUBTYPE + 4, 1)
        r.call_jsl(prep_entry, x=4)
        self.assertEqual(r.get(SPR_ACTION + 4), 4)
        self.assertEqual(r.get(SPR_FRAME + 4), 8)

        # 2. Land/Water/Abyss palettes + active vs dying SprFlash math
        def check_prop(worldflag: int, subtype: int, state: int, flash: int) -> int:
            r.ram[:] = b"\x00" * len(r.ram)
            r.oam_writes.clear()
            r.put(WORLDFLAG, worldflag)
            r.put(SPR_SUBTYPE + 2, subtype)
            r.put(SPR_STATE + 2, state)
            r.put(SPR_TIMERA + 2, 0x18 if state == 6 else 0)
            r.put(SPR_FLASH + 2, flash)
            r.put(SPR_FRAME + 2, 8 if subtype else 0)
            r.put16(0x90, 0x0800)
            r.put16(0x92, 0x0A20)
            r.call_jsr(draw_entry, x=2)
            return r.ram[0x0803]

        self.assertEqual(check_prop(0, 0, 9, 0), 0x27)  # Land: priority 2, Pal 3 ($06)
        self.assertEqual(check_prop(0, 1, 9, 0), 0x35)  # Water: priority 3, Pal 2 ($04)
        self.assertEqual(check_prop(1, 0, 9, 0), 0x2D)  # Eon Abyss: Aux Pal 6 ($0C)
        self.assertEqual(check_prop(0, 0, 9, 3), 0x21 | ((3 << 1) ^ 0x06))  # Active raw flash 3 -> 0
        self.assertEqual(check_prop(0, 0, 6, 0x26), 0x21 | (0x06 ^ 0x06))  # Dying pre-shifted flash $26 -> no double ASL

        # 3. Water Octorok ripple advances $90 by +4 so body slot 0 ($0800) is NOT clobbered
        r.ram[:] = b"\x00" * len(r.ram)
        r.ripple_writes.clear()
        r.put(WORLDFLAG, 0)
        r.put(SPR_STATE + 1, 0x09)
        r.put(SPR_SUBTYPE + 1, 1)
        r.put(SPR_FRAME + 1, 8)
        r.put(SPR_NBROAM + 1, 6)
        r.put16(0x90, 0x0800)
        r.put16(0x92, 0x0A20)
        r.call_jsl(long_entry, x=1)
        self.assertEqual(r.ripple_writes, [0x0804])
        self.assertEqual(r.ram[0x0802], 0xAA)  # Body CHR ($AA) at $0802 survived intact!

        # 4. Sprite_Octorok_Move calls Sprite_CheckIfRecoiling before Sprite_Move
        r.ram[:] = b"\x00" * len(r.ram)
        r.calls.clear()
        r.put(SPR_TYPE + 1, 0x08)
        r.put(SPR_TIMERA + 1, 10)
        r.call_jsr(move_entry, x=1)
        self.assertIn("Sprite_CheckIfRecoiling", r.calls)
        self.assertLess(r.calls.index("Sprite_CheckIfRecoiling"), r.calls.index("Sprite_Move"))

    def test_darknut_anti_kirby_sea_urchin_keese_pols_puffstool_helmet(self) -> None:
        r = self._new_runner()

        # 1. Darknut: armored palette bit $02 + dying pre-shifted flash
        dn_draw = self.pack.labels["Sprite_Darknut_Draw"]
        for armor, state, flash, expected_pal in (
            (False, 9, 0, 0x08),
            (True, 9, 0, 0x0A),
            (True, 6, 0x26, 0x08 ^ (0x06 ^ 0x02)),
        ):
            r.ram[:] = b"\x00" * len(r.ram)
            r.darknut_armor = armor
            r.put(SPR_STATE + 1, state)
            r.put(SPR_FLASH + 1, flash)
            r.put16(0x90, 0x0800)
            r.put16(0x92, 0x0A20)
            r.call_jsr(dn_draw, x=1)
            self.assertEqual(r.ram[0x0803] & 0x0E, expected_pal)

        # 2. AntiKirby: Priority 2 ($2B) & zero health goes to Action 7 (Death), NOT Action 4 (Full!)
        ak_long = self.pack.labels["Sprite_AntiKirby_Long"]
        ak_main = self.pack.labels["Sprite_AntiKirby_Main"]
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(SPR_STATE + 1, 9)
        r.put(SPR_NBROAM + 1, 6)
        r.put16(0x90, 0x0800)
        r.put16(0x92, 0x0A20)
        r.call_jsl(ak_long, x=1)
        self.assertEqual((r.ram[0x0803] >> 4) & 0x03, 2, "AntiKirby priority must be 2, not 0!")

        # Run Sprite_AntiKirby_Main via JumpTableLocal with SprHealth=0 -> Action becomes 7, then 2nd call runs Death
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(SPR_STATE + 1, 9)
        r.put(SPR_HEALTH + 1, 0)
        r.put(0x4B, 0x0C)
        for _ in range(2):
            r.call_jsr(ak_main, x=1)
        self.assertEqual(r.get(SPR_ACTION + 1), 7)
        self.assertEqual(r.get(SPR_STATE + 1), 6)
        self.assertEqual(r.get(SPR_TIMERA + 1), 0x1F)
        self.assertEqual(r.get(0x4B), 0)

        # 3. SeaUrchin: no ForcePrizeDrop_long on hit; checks recoil + bounce
        su_main = self.pack.labels["Sprite_SeaUrchin_Main"]
        r.ram[:] = b"\x00" * len(r.ram)
        r.calls.clear()
        r.check_damage_carry = True
        r.put(SPR_STATE + 1, 9)
        r.call_jsr(su_main, x=1)
        self.assertNotIn("ForcePrizeDrop_long", r.calls)
        self.assertIn("Sprite_CheckIfRecoiling", r.calls)
        self.assertNotEqual(r.get(SPR_STATE + 1), 6)

        # 4. Keese: !Health = 1 in ROM table, no ForcePrizeDrop_long on hit, throttled direction select
        keese_hp = self.pack.rom[lorom_pc(0x0DB173 + 0x11)]
        self.assertEqual(keese_hp, 1)
        keese_fly = self.pack.labels["Keese_FlyAround"]
        r.ram[:] = b"\x00" * len(r.ram)
        r.calls.clear()
        r.check_damage_carry = True
        r.put(SPR_TIMERA + 1, 10)
        r.put(SPR_TIMERD + 1, 20)
        r.call_jsr(keese_fly, x=1)
        self.assertNotIn("ForcePrizeDrop_long", r.calls)
        self.assertNotIn("Sprite_SelectNewDirection", r.calls)

        # 5. PolsVoice flute kills via state $06 / SprTimerA $1F (no uninitialized ForcePrizeDrop_long)
        pv_flute = self.pack.labels["PolsVoice_CheckForFluteSong"]
        song_flag_addr = self.pack.labels.get("SongFlag", 0xFE)
        r.ram[:] = b"\x00" * len(r.ram)
        r.calls.clear()
        r.put(song_flag_addr, 1)
        r.put(SPR_STATE + 2, 9)
        r.call_jsr(pv_flute, x=2)
        self.assertNotIn("ForcePrizeDrop_long", r.calls)
        self.assertEqual(r.get(SPR_STATE + 2), 6)
        self.assertEqual(r.get(SPR_TIMERA + 2), 0x1F)

        # 6. Puffstool spore expires cleanly without ForcePrizeDrop_long
        ps_spores = self.pack.labels["Puffstool_Spores"]
        r.ram[:] = b"\x00" * len(r.ram)
        r.calls.clear()
        r.put(SPR_STATE + 2, 9)
        r.call_jsr(ps_spores, x=2)
        self.assertNotIn("ForcePrizeDrop_long", r.calls)
        self.assertEqual(r.get(SPR_STATE + 2), 0)

        # 7. HelmetChuchu hookshot spawn at slot 7 wraps speed table index & #$03 (7&3 == 3 -> 11, -11)
        hc_spawn = self.pack.labels["HelmetChuchu_SpawnHookshotDrag"]
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(SPR_ACTION + 7, 1)
        r.call_jsr(hc_spawn, x=7)
        self.assertEqual(r.get(0x0D50 + 5), 11)
        self.assertEqual(r.get(0x0D40 + 5), (-11) & 0xFF)

    def test_sea_urchin_prep_populates_dmgtable_and_preserves_x(self) -> None:
        r = self._new_runner()
        su_prep = self.pack.labels["Sprite_SeaUrchin_Prep"]
        expected_dmg_row = bytes([
            0x03, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x03,
            0x01, 0x01, 0x02, 0x01, 0x03, 0x03, 0x01, 0x07,
        ])
        dmg_offset = 0x16AE0  # $7F6AE0 - $7E0000

        # Light World (WORLDFLAG = 0): populates DMGTABLE[$AE], preserves X, sets SprPrize=1, leaves SprDefl sword-vulnerable
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(WORLDFLAG, 0)
        r.call_jsl(su_prep, x=5)
        self.assertEqual(r.cpu.x, 5)
        self.assertEqual(bytes(r.ram[dmg_offset : dmg_offset + 16]), expected_dmg_row)
        self.assertEqual(r.get(0x0BE0 + 5), 0x01)
        self.assertEqual(r.get(0x0CAA + 5) & 0x04, 0x00)

        # Dark World (WORLDFLAG != 0): populates DMGTABLE[$AE], sets SprDefl=%10000100 (sword/hammer impervious), SprPrize=7
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(WORLDFLAG, 0x40)
        r.call_jsl(su_prep, x=3)
        self.assertEqual(r.cpu.x, 3)
        self.assertEqual(bytes(r.ram[dmg_offset : dmg_offset + 16]), expected_dmg_row)
        self.assertEqual(r.get(0x0BE0 + 3), 0x07)
        self.assertEqual(r.get(0x0CAA + 3), 0b10000100)


if __name__ == "__main__":
    unittest.main()
