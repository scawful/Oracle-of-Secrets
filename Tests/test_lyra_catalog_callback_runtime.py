"""Catalog callback source contracts and protocol models, never CPU execution.

The source assertions inspect the real owners/callers. The independent models
cover cache and DMA lifetime examples; they are not an assembler or emulator.
"""
from pathlib import Path
import copy
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FROZEN = "6e7e5f15d555dffb9f4b3d8807595c9e3f13305f"
sys.path.insert(0, str(ROOT / "Scripts/Graphics"))
import compile_graphics_pack as pack


def routine(source, name):
    match = re.search(r"^" + re.escape(name) + r":\s*\n\{\n(.*?)^\}",
                      source, re.M | re.S)
    if match is None:
        raise AssertionError("Missing real source routine: " + name)
    return match.group(1)


def mode_body(body, current):
    """Select only local CURRENT_MODE branches; this is not an Asar evaluator."""
    result, stack, active = [], [], True
    for raw in body.splitlines():
        line = raw.split(";", 1)[0].strip()
        if line.startswith("if "):
            known = re.fullmatch(r"if !LYRA_CURRENT_MODE\s*==\s*1", line) is not None
            stack.append((active, known, current))
            if known:
                active = active and current
            elif active:
                result.append(line)
        elif line == "else" and stack:
            if stack[-1][1]:
                active = stack[-1][0] and not stack[-1][2]
            elif active:
                result.append(line)
        elif line == "endif" and stack:
            parent, known, _ = stack.pop()
            if not known and active:
                result.append(line)
            active = parent
        elif active:
            result.append(line)
    if stack:
        raise AssertionError("Unbalanced local current-mode branch")
    return "\n".join(result)


def tokens(body):
    return " ".join(body.replace(":", " ").split())


def selected(parent, indoor=False, mode=True, bound=True):
    return mode and not indoor and 0xA0 <= parent < 0xC0 and bound


def resolve_skip(raw, slot, prior, underlying):
    # Deliberately independent of the destination domain: leaving a profile
    # still needs native $FF recovery from its retained sentinel/cache pair.
    return underlying[slot] if raw == 0xFF and 3 <= slot < 7 and prior[slot] == 0xFF else raw


def invalidate(mask, prior, underlying):
    for slot in range(3, 7):
        if mask & (1 << slot) and prior[slot] != 0xFF:
            underlying[slot], prior[slot] = prior[slot], 0xFF


def schedule(raw, slot, prior, underlying):
    value = resolve_skip(raw, slot, prior, underlying)
    if value == 0xFF or value == prior[slot]:
        return None
    prior[slot] = value
    return value


def transition_source(target, native_source, transition):
    mode = transition["mode"]
    start, end = transition.get("target_start_word", 0), transition.get("target_end_word", 0)
    if ((mode == "source_range" and start <= target < end) or
            (mode == "source_start" and target == start)):
        return transition["source"] + 2 * (target - start)
    return native_source


def stage_after_conversion(converted, records, assets, native):
    if not converted:
        return native
    output = bytearray(native)
    for record in records:
        at = record["wram_address"] - 0x7F0000
        start, count = record["source_offset"], record["byte_count"]
        output[at:at + count] = assets[record["resource_id"]][start:start + count]
    return bytes(output)


class CatalogCallbackSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = (ROOT / "Overworld/graphics_runtime.asm").read_text()
        cls.custom = (ROOT / "Overworld/custom_gfx.asm").read_text()
        cls.zs = (ROOT / "Overworld/ZSCustomOverworld.asm").read_text()

    def test_default_callback_instructions_equal_frozen_control(self):
        for path, source, names in (
            ("Overworld/custom_gfx.asm", self.custom,
             ["CheckForChangeGraphicsNormalLoadBoat"]),
            ("Overworld/graphics_runtime.asm", self.runtime,
             ["SharedGraphicsLookup", "SharedGraphicsInvalidateCache",
              "SharedGraphicsStageNative", "SharedGraphicsIncrementalSource"]),
        ):
            original = subprocess.check_output(
                ["git", "show", FROZEN + ":" + path], cwd=ROOT, text=True)
            for name in names:
                with self.subTest(path=path, name=name):
                    self.assertEqual(tokens(mode_body(routine(source, name), False)),
                                     tokens(mode_body(routine(original, name), False)))

    def test_current_domain_lookup_and_one_native_normal_fallback(self):
        lookup = tokens(mode_body(routine(self.runtime, "SharedGraphicsLookup"), True))
        self.assertIn("LDA.l $7E001B AND.w #$00FF BNE .none", lookup)
        self.assertLess(lookup.index("CMP.w #!LYRA_CURRENT_FIRST"),
                        lookup.index("CMP.w #!GfxRT_ParentCount"))
        normal = mode_body(routine(self.custom, "CheckForChangeGraphicsNormalLoadBoat"), True)
        self.assertEqual(normal.count("JSR ApplyGraphics1"), 1)
        self.assertEqual(normal.count("JSR ApplyGraphics2"), 1)
        self.assertIn("PHP REP #$20 PHA", tokens(normal))
        self.assertIn("PLA PLP JML SharedGraphicsNormalLoad", tokens(normal))
        self.assertIn(".native PLA PLP LDA $8A", tokens(normal))
        for parent in (0x9F, 0xA0, 0xA1, 0xBF, 0xC0):
            self.assertEqual(selected(parent), 0xA0 <= parent < 0xC0)
            self.assertFalse(selected(parent, indoor=True))
            self.assertFalse(selected(parent, mode=False))
            self.assertFalse(selected(parent, bound=False))

    def test_resolver_is_read_only_global_recovery_with_xy16(self):
        body = routine(self.custom, "ResolveCustomGraphicsTransitionSheet")
        self.assertIn("CPX.w #$0003", body)
        self.assertIn("CPX.w #$0007", body)
        self.assertIn("LDA.l $7E04CB, X", body)
        self.assertIn("LDA.l $7EC2F5, X", body)
        self.assertNotRegex(body, r"\b(?:STA|STX|STY|STZ|REP|SEP)\b")
        self.assertNotIn("LYRA_CURRENT_FIRST", body)
        self.assertEqual(tokens(body).count("PHP"), 1)
        self.assertEqual(tokens(body).count("PLP"), 1)
        for slot in range(3, 7):
            prior, native = [0] * 8, [0] * 8
            prior[slot], native[slot] = 0xFF, 0x31 + slot
            before = copy.deepcopy((prior, native))
            self.assertEqual(resolve_skip(0xFF, slot, prior, native), native[slot])
            self.assertEqual((prior, native), before)

    def test_real_aux_and_block_resolver_callers_keep_xy16(self):
        aux = mode_body(routine(self.zs, "NewLoadTransAuxGFX"), True)
        for slot in range(3, 7):
            with self.subTest(slot=slot):
                pattern = (r"PHX\s*(?::\s*)?LDX\.w #\$(?:00)?0" + str(slot) +
                           r"\s*(?::\s*)?JSL(?:\.l)? Oracle_ResolveCustomGraphicsTransitionSheet"
                           r"\s*(?::\s*)?PLX")
                self.assertRegex(aux, pattern)
        block = mode_body(routine(self.zs, "BlockGFXCheck"), True)
        call = block.index("Oracle_ResolveCustomGraphicsTransitionSheet")
        self.assertLess(call, block.index("STA.b $00"))
        self.assertIn("STZ.b $02", block[:call])
        self.assertRegex(block, r"PHX\s*(?::\s*)?LDX\.b \$02")

    def test_invalidation_before_aux_comparison_and_after_block_cache_writes(self):
        aux = mode_body(routine(self.zs, "NewLoadTransAuxGFX"), True)
        self.assertLess(aux.index("Oracle_InvalidateCustomGraphicsCache"),
                        aux.index("CMP.w TransGFXModule_PriorSheets+3"))
        finish = mode_body(routine(self.zs, "NewOverworld_FinishTransGfx"), True)
        blocks = re.findall(r"JSR\.w BlockGFXCheck(.*?)CPY\.b #\$08", finish, re.S)
        self.assertEqual(len(blocks), 2)
        for block in blocks:
            self.assertIn("Oracle_InvalidateCustomGraphicsCache", block)
        cache = tokens(mode_body(routine(self.runtime, "SharedGraphicsInvalidateCache"), True))
        self.assertIn("PHP REP #$30 PHX PHY PHA", cache)
        self.assertIn("PLA PLY PLX PLP RTL", cache)
        marker = tokens(routine(self.runtime, "SharedGraphicsMarkCache"))
        self.assertLess(marker.index("CMP.w #$00FF BEQ .skip"),
                        marker.index("STA.l $7EC2F5, X"))

    def test_both_nmi_sources_consume_callback_after_native_bank_before_count(self):
        nmi = mode_body(routine(self.zs, "NMI_UpdateChr_Bg2HalfAndAnimatedLONG"), True)
        self.assertEqual(nmi.count("Oracle_SelectCustomGraphicsTransitionSource"), 2)
        for index in (1, 2):
            start = nmi.index(f"LDA.w NewNMISource{index}")
            end = nmi.index(f"LDA.w NewNMICount{index}", start)
            block = nmi[start:end]
            self.assertIn("LDY.b #$7F", block)
            self.assertIn(f"LDA.w NewNMITarget{index}", block)
            self.assertIn("Oracle_SelectCustomGraphicsTransitionSource", block)
            self.assertLess(block.index("DMA.0_SourceAddrBank"),
                            block.index("Oracle_SelectCustomGraphicsTransitionSource"))
        helper = routine(self.runtime, "SharedGraphicsTransitionSource")
        writes = re.findall(r"STA\.l (\$[0-9A-F]+)", helper)
        self.assertEqual(set(writes), {"$004302", "$004304"})
        self.assertIn("PLA PLY PLX PLP RTL", tokens(helper))

    def test_stage_only_after_conversion_and_restores_private_frame_and_a(self):
        prep = mode_body(routine(self.zs, "NewPrepTransAuxGFX"), True)
        call = prep.index("Oracle_SharedGraphicsStageNative")
        self.assertLess(prep.index("JSL.l PrepTransAuxGFX"), call)
        self.assertLess(call, prep.index(".dontPrep", call))
        body = tokens(mode_body(routine(self.runtime, "SharedGraphicsStageNative"), True))
        self.assertIn("PHP REP #$30 PHX PHY PHA PHD", body)
        self.assertIn("TSC SEC SBC.w #$0010 TCS INC TCD", body)
        self.assertIn("TSC CLC ADC.w #$0010 TCS PLD PLA PLY PLX PLP RTL", body)
        self.assertIn("LDA [$00], Y STA [$03], Y", body)
        self.assertIn("STA.b $08 BNE .records JMP .done", body)

    def test_incremental_hook_has_exact_native_replay_and_no_extra_dma(self):
        current = mode_body(self.zs, True)
        self.assertRegex(current, r"org \$008C0E[^\n]*\n\s*JSL(?:\.l)? Oracle_SelectShipIncrementalGraphicsSource\s*\n\s*NOP")
        body = tokens(mode_body(routine(self.runtime, "SharedGraphicsIncrementalSource"), True))
        self.assertIn("PHP REP #$30 PHX PHY PHA", body)
        self.assertIn("PLA PLY PLX PLP LDA.b #$7F RTL", body)
        self.assertNotIn("$00420B", body)
        self.assertNotIn("$004305", body)
        self.assertNotIn("$002116", body)


class CatalogCallbackProtocolModels(unittest.TestCase):
    def test_leaving_profile_native_ff_or_same_id_schedules_underlying_sheet(self):
        for raw in (0xFF, 0x35):
            prior, underlying = [0] * 8, [0] * 8
            prior[3], underlying[3] = 0xFF, 0x35
            self.assertEqual(schedule(raw, 3, prior, underlying), 0x35)
            self.assertEqual(prior[3], 0x35)
            self.assertEqual(underlying[3], 0x35)
            self.assertIsNone(schedule(raw, 3, prior, underlying))

    def test_marker_does_not_recapture_ff_and_retains_other_slots(self):
        prior = [0x20 + i for i in range(8)]
        underlying = [0x40 + i for i in range(8)]
        invalidate(1 << 3, prior, underlying)
        first = copy.deepcopy((prior, underlying))
        invalidate(1 << 3, prior, underlying)
        self.assertEqual((prior, underlying), first)
        self.assertEqual(underlying[3], 0x23)
        self.assertEqual(prior[3], 0xFF)
        self.assertEqual(prior[4:], [0x24, 0x25, 0x26, 0x27])
        # The next block writes the desired native ID, then current profile
        # marking captures that ID once and reinstates its override sentinel.
        self.assertEqual(schedule(0x35, 3, prior, underlying), 0x35)
        invalidate(1 << 3, prior, underlying)
        self.assertEqual((prior[3], underlying[3]), (0xFF, 0x35))

    def test_two_dma_records_reset_native_bank_and_preserve_destination_count(self):
        policy = dict(mode="source_range", source=0x5A9000,
                      target_start_word=0x2C00, target_end_word=0x3000)
        records = [(0x2C00, 0x7F0000, 0x800), (0x3000, 0x7F0800, 0x800)]
        result = [(target, transition_source(target, native, policy), count)
                  for target, native, count in records]
        self.assertEqual(result, [(0x2C00, 0x5A9000, 0x800), (0x3000, 0x7F0800, 0x800)])
        self.assertEqual(transition_source(0x2E00, 0x7F0400, policy), 0x5A9400)
        policy["mode"] = "source_start"
        self.assertEqual(transition_source(0x2E00, 0x7F0400, policy), 0x7F0400)

    def test_real_lowering_proves_staging_cache_mask_and_sparse_native_preservation(self):
        pixels = bytes(range(32))
        transfer = dict(resource_id="glyph", source_offset=0,
                        byte_count=32, vram_word_address=0x2C00)
        catalog = dict(schema_version=2, resources={"glyph": dict(
            format="snes4bpp", byte_count=32, sha256=pack.sha256(pixels))},
            profiles={"tail": dict(bg_character_base_word=0x2000,
                                    transfers=[transfer])},
            bindings=[dict(profile_id="tail", parent_maps=[0xA0, 0xA1, 0xBF])])
        policy = dict(schema_version=1, profiles={"tail": dict(
            runtime_enabled=True, normal="all_declared_transfers", cache_slots=[3],
            transition=dict(mode="native_staging"), late=None,
            staging=dict(mode="native_after_conversion", vram_start_word=0x2C00,
                         vram_end_word=0x3C00, wram_base=0x7F0000))})
        lowered = pack.lower_runtime_policy(catalog, {"glyph": pixels}, policy,
                                            parent_count=192)["profiles"]["tail"]
        self.assertEqual(lowered["cache_slot_mask"], 1 << 3)
        self.assertEqual(len(lowered["staging"]), 1)
        record = lowered["staging"][0]
        self.assertEqual(record["wram_address"], 0x7F0000)
        native = bytes([0xA5]) * 0x2000
        prepared = stage_after_conversion(True, lowered["staging"], {"glyph": pixels}, native)
        self.assertEqual(prepared[32:], native[32:])
        self.assertEqual(prepared[:32], pixels)
        self.assertEqual(stage_after_conversion(False, lowered["staging"],
                                                {"glyph": pixels}, native), native)
        self.assertEqual(stage_after_conversion(True, [], {"glyph": pixels}, native), native)
        self.assertEqual(native, bytes([0xA5]) * 0x2000)

    def test_incremental_native_result_and_flags_keep_hidden_b(self):
        original_a, original_p = 0xAB12, 0xEF  # M8/X16, arbitrary incoming N/Z.
        for parent in (0x9F, 0xA0, 0xA1, 0xBF, 0xC0):
            for step in (0x4F, 0x50, 0x5F, 0x60):
                source = (0x5A9000 + (step - 0x50) * 512
                          if selected(parent) and 0x50 <= step < 0x60 else 0x7F1234)
                result_a = (original_a & 0xFF00) | 0x7F
                result_p = original_p & ~0x82
                self.assertEqual((result_a, result_p), (0xAB7F, 0x6D))
                if not selected(parent) or step not in range(0x50, 0x60):
                    self.assertEqual(source, 0x7F1234)
        self.assertEqual(0x5A9000 + (0x5F - 0x50) * 512, 0x5AAE00)


if __name__ == "__main__":
    unittest.main()
