"""Focused source-model controls for the private room-$97 cart shutter.

Executes the actual ASM predicate with the existing small Somaria WRAM model.
This is not assembled-byte, CPU, door-collision or controller acceptance.
"""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sprites/Objects/minecart.asm"
SPEC = importlib.util.spec_from_file_location("somaria_source_model", ROOT / "Tests/test_somaria_socket_door.py")
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def body(path, name):
    text = path.read_text().split(name + ":\n{", 1)[1].split("\n}", 1)[0]
    return [part.strip() for line in text.splitlines()
            for part in line.split(";", 1)[0].split(" : ") if part.strip()]


SYMBOLS = {name: int(value, 16) for filename in
           ("Core/symbols.asm", "Sprites/sprite_registry_ids.asm", "Sprites/Objects/switch_track.asm")
           for name, value in re.findall(r"^(\w+)\s*=\s*\$([0-9A-Fa-f]+)", (ROOT / filename).read_text(), re.M)}
SYMBOLS.update({"!MinecartCurrent": 0x07EA, "!LinkInCart": 0x35})


def program(lines):
    # Resolve source symbol operands without changing branch/exit labels.
    for name, value in sorted(SYMBOLS.items(), key=lambda p: -len(p[0])):
        lines = [re.sub(r"(?<!\w)" + re.escape(name) + r"(\+1)?(?!\w)",
                        lambda m: f"${value + bool(m[1]):04X}", line) for line in lines]
    return base.parse(lines)


def with_hold(name):
    lines = body(SOURCE, name) + [".hold_predicate"] + body(SOURCE, "CartShutter97_Hold")
    return program([line.replace("JSR.w CartShutter97_Hold", "JSR.w .hold_predicate") for line in lines])


class Machine(base.Machine):
    def run(self, code, labels, limit=1000):
        pc = 0
        stack = []
        def push(kind, value, size):
            stack.append((kind, value, size)); self.sp -= size
        def pop(kind, size):
            actual, value, count = stack.pop()
            assert (actual, count) == (kind, size), (actual, kind, count, size)
            self.sp += size
            return value
        for _ in range(limit):
            op, suffix, arg = code[pc]
            pc += 1
            if op in ("REP", "SEP"):
                if op == "REP": self.p &= ~int(arg[2:], 16)
                else: self.p |= int(arg[2:], 16)
                self._normalize_index()
            elif op in ("LDA", "LDX"):
                wide = self.m16() if op == "LDA" else self.x16()
                value = self.load(suffix, arg, wide)
                if op == "LDA": self.a = value if wide else (self.a & 0xFF00) | value
                else: self.x = value
                self.flags_nz(value, wide)
            elif op in ("CMP", "CPX", "CPY"):
                wide = self.m16() if op == "CMP" else self.x16()
                register = {"CMP": self.a, "CPX": self.x, "CPY": self.y}[op]
                self.compare(register, self.load(suffix, arg, wide), wide)
            elif op == "BIT":
                value = self.load(suffix, arg, self.m16())
                self.z = not (self.a & value)
            elif op in ("AND", "ORA"):
                operand = self.load(suffix, arg, self.m16())
                value = self.a & operand if op == "AND" else self.a | operand
                self.a = value if self.m16() else (self.a & 0xFF00) | (value & 255)
                self.flags_nz(value & (65535 if self.m16() else 255), self.m16())
            elif op == "TXA":
                self.a = self.x if self.m16() else (self.a & 0xFF00) | (self.x & 255)
                self.flags_nz(self.a & (65535 if self.m16() else 255), self.m16())
            elif op == "XBA":
                self.a = ((self.a << 8) | (self.a >> 8)) & 0xFFFF
                self.flags_nz(self.a & 0xFF, False)
            elif op in ("DEX", "INX"):
                self.x = (self.x + (1 if op == "INX" else -1)) & (0xFFFF if self.x16() else 0xFF)
                self.flags_nz(self.x, self.x16())
            elif op in ("CLC", "SEC"):
                self.c = op == "SEC"
            elif op == "PHP":
                value = (self.p & 0x3C) | int(self.c) | (int(self.z) << 1) | (int(self.v) << 6) | (int(self.n) << 7)
                push("p", value, 1)
            elif op == "PLP":
                self.p = pop("p", 1)
                self.c, self.z, self.v, self.n = [bool(self.p & mask) for mask in (1, 2, 0x40, 0x80)]
                self._normalize_index()
            elif op in ("PHA", "PHX"):
                size = 2 if (self.m16() if op == "PHA" else self.x16()) else 1
                push(op, self.a if op == "PHA" else self.x, size)
            elif op in ("PLA", "PLX"):
                size = 2 if (self.m16() if op == "PLA" else self.x16()) else 1
                value = pop("PHA" if op == "PLA" else "PHX", size)
                if op == "PLA": self.a = value if size == 2 else (self.a & 0xFF00) | (value & 255)
                else: self.x = value & (65535 if size == 2 else 255)
                self.flags_nz(value, size == 2)
            elif op == "JSR":
                push("return", pc, 2); pc = labels[arg]
            elif op == "JSL" and arg in getattr(self, "long_stubs", {}):
                self.long_stubs[arg](self)
            elif op == "JSL":
                assert arg == "DragPlayer", "Only the shared drag ABI stub is admitted"
                self.drag_calls.append((self.read(0x0FD8, True), self.x, self.y, self.p & 0x30))
                # Model only DragPlayer's documented A/P clobber and M8/X8
                # return. This checks wrapper admission/cache/stack, not drag
                # movement, collision, CPU instructions or doorway passage.
                self.a, self.p = 0xBEEF, self.p | 0x30
            elif op == "RTS":
                pc = pop("return", 2)
            elif op == "RTL":
                assert not stack, "Unbalanced source-model stack at RTL"
                return "RTL"
            elif op in ("STA", "STX", "STZ"):
                wide = self.x16() if op == "STX" else self.m16()
                value = {"STA": self.a, "STX": self.x, "STZ": 0}[op]
                self.write(self.effective(arg), value, wide)
            elif op in ("BEQ", "BNE", "BCC", "BCS", "BPL", "BRA", "JMP"):
                take = {"BEQ": self.z, "BNE": not self.z, "BCC": not self.c,
                        "BCS": self.c, "BPL": not self.n, "BRA": True, "JMP": True}[op]
                if take: pc = labels[arg]
            elif op == "JML":
                assert not stack, "Unbalanced source-model stack at JML"
                return arg
            else:
                raise AssertionError("Instruction outside this source model: " + op)
        raise AssertionError("Source model exceeded step limit")


def word(memory, address, value):
    memory[address], memory[address + 1] = value & 255, value >> 8


def room(closed=True, key_open=True, link=(0x0E40, 0x1280), mounted=False, **extra):
    m = {0x1B: 1, 0xEE: 0, 0x35: int(mounted), 0x36: 0xA5, 0x07EA: 3,
         0x0230: 0xA5, 0x0231: 1, 0x0232: 0x5A, 0x11: 0, 0x12F: 0x66,
         0xAE: 0x37, 0xAF: 0}
    for address, value in ((0xA0, 0x97), (0x0400, 0x4000 if key_open else 0),
                           (0x0468, int(closed)), (0x068E, 0xA55A), (0x0690, 0x3CC3),
                           (0x22, link[0]), (0x20, link[1])):
        word(m, address, value)
    m.update({int(k, 16): v for k, v in extra.items()})
    return m


def cart(memory, slot=3, xy=(0x0F80, 0x1348), action=2, state=9, kind=0xA3, layer=0):
    m = dict(memory)
    for address, value in ((0x0DD0, state), (0x0E20, kind), (0x0F20, layer), (0x0D80, action),
                           (0x0D10, xy[0] & 255), (0x0D30, xy[0] >> 8),
                           (0x0D00, xy[1] & 255), (0x0D20, xy[1] >> 8)):
        m[address + slot] = value
    return m


class LocalCartShutter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code, cls.labels = with_hold("RoomTag_CartShutter97")

    def execute(self, memory):
        machine = Machine(memory, y=0x5A)
        self.assertEqual(machine.run(self.code, self.labels), "$01CC5A")
        self.assertEqual((machine.y, machine.sp, machine.p & 0x30), (0x5A, 0x01FB, 0x30))
        self.assertLessEqual(set(machine.writes), {0x0231, 0x0468, 0x0469, 0x068E,
                            0x068F, 0x0690, 0x0691, 0x012F, 0x11})
        self.assertNotIn(0x36, machine.reads)
        return machine

    def assert_transition(self, machine, closed):
        wanted = {0x0468: int(closed), 0x0469: 0, 0x068E: 0, 0x068F: 0,
                  0x0690: 0, 0x0691: 0, 0x11: 5}
        if not closed: wanted[0x012F] = 0x1B
        self.assertEqual(machine.writes, wanted)

    def test_opens_only_for_two_vertical_approaches(self):
        for xy, action in (((0x0F80, 0x1348), 2), ((0x0F80, 0x1300), 4)):
            with self.subTest(xy=xy, action=action):
                m = room(mounted=True, link=(xy[0] - 2, xy[1] - 8))
                self.assert_transition(self.execute(cart(m, xy=xy, action=action)), False)

    def test_denies_foot_stale_slot_wrong_actor_layer_and_departure(self):
        mounted = room(mounted=True, link=(0x0F7E, 0x1340))
        cases = [cart(room(link=(0x0F7E, 0x1340))),
                 cart({**mounted, 0x07EA: 16}), cart(mounted, state=0), cart(mounted, kind=0xB0),
                 cart(mounted, layer=1), cart({**mounted, 0xEE: 1}), cart({**mounted, 0x1B: 0}),
                 cart(mounted, action=3), cart(mounted, action=4),
                 cart(mounted, xy=(0x0F80, 0x1300), action=2), cart(room(mounted=True))]
        for number, m in enumerate(cases):
            with self.subTest(case=number): self.assertFalse(self.execute(m).writes)

    def test_approach_edges_do_not_open_elsewhere_in_the_room(self):
        for xy, action, opens in (((0x0F78, 0x1328), 2, True), ((0x0F88, 0x1350), 2, True),
                                  ((0x0F77, 0x1340), 2, False), ((0x0F89, 0x1340), 2, False),
                                  ((0x0F80, 0x1351), 2, False), ((0x0F80, 0x12B7), 4, False),
                                  ((0x0F80, 0x12B8), 4, True), ((0x0F80, 0x1328), 4, False)):
            with self.subTest(xy=xy, action=action):
                m = cart(room(mounted=True, link=(xy[0] - 2, xy[1] - 8)), xy=xy, action=action)
                self.assertEqual(bool(self.execute(m).writes), opens)

    def test_holds_for_link_or_any_live_cart_including_dismounted_and_parked(self):
        for slot in range(16):
            with self.subTest(slot=slot):
                self.assertFalse(self.execute(cart(room(closed=False), slot=slot,
                                                   xy=(0x0F80, 0x1328), action=0)).writes)
        for xy in ((0x0F50, 0x12B0), (0x0FB0, 0x1358), (0x0F80, 0x1328)):
            self.assertFalse(self.execute(room(closed=False, link=xy)).writes)

    def test_closes_after_both_actors_clear_and_ignores_other_layers_or_sprites(self):
        for xy in ((0x0F4F, 0x1328), (0x0FB1, 0x1328), (0x0F80, 0x12AF),
                   (0x0F80, 0x1359), (0x0F80, 0x12A0), (0x0F00, 0x1360)):
            self.assert_transition(self.execute(cart(room(closed=False), xy=xy)), True)
        for overrides in ({"state": 0}, {"kind": 0xB0}, {"layer": 1}):
            self.assert_transition(self.execute(cart(room(closed=False), xy=(0x0F80, 0x1328),
                                                     **overrides)), True)
        self.assert_transition(self.execute(room(closed=False, link=(0x0F80, 0x1328), EE=1)), True)

    def test_clearance_then_close_does_not_oscillate_or_open_on_foot(self):
        m = cart(room(closed=False, mounted=True, link=(0x0F7E, 0x12A0)),
                 xy=(0x0F80, 0x12A8), action=2)
        closed = self.execute(m)
        self.assert_transition(closed, True)
        closed.memory[0x11] = 0  # only model vanilla completion; native must observe it.
        self.assertFalse(self.execute(closed.memory).writes)
        foot = room(closed=False, link=(0x0F80, 0x1328))
        self.assertFalse(self.execute(foot).writes)
        foot[0x0468] = 1
        self.assertFalse(self.execute(foot).writes)

    def test_stable_states_do_not_restart_the_animator(self):
        for closed in (True, False):
            m = room(closed=closed, link=(0x0F80, 0x1328) if not closed else (0x0E40, 0x1280))
            self.assertFalse(self.execute(m).writes)

    def test_hold_includes_full_cart_and_link_footprint_plus_eight_pixel_margin(self):
        # Whole paired-door union: upper F8 y27..28 plus lower F0 y37..38.
        # Include an extra upper row conservatively through $12EF.
        # Probe all corners of each origin range that intersects it, expanded
        # by eight pixels. Link's feet extend through top-left Y+23.
        aperture = (0x0F70, 0x0F8F, 0x12D8, 0x133F)
        for actor, bounds in (("cart", (-8, 23, -12, 24)), ("link", (0, 15, 0, 23))):
            xmin, xmax = aperture[0] - bounds[1] - 8, aperture[1] - bounds[0] + 8
            ymin, ymax = aperture[2] - bounds[3] - 8, aperture[3] - bounds[2] + 8
            for x in (xmin, xmax):
                for y in (ymin, ymax):
                    with self.subTest(actor=actor, xy=(x, y)):
                        m = room(closed=False, link=(x, y)) if actor == "link" else cart(
                            room(closed=False), xy=(x, y), action=0)
                        self.assertFalse(self.execute(m).writes)

    def test_complete_paired_door_cycle_closes_at_north20_then_opens_before_upper_face(self):
        # Model only the tag, with vanilla animation completion acknowledged
        # between movement steps. Native must prove actual camera/collision.
        m = room(mounted=True)
        transitions = []
        for action, positions in ((2, range(0x1350, 0x129F, -1)),
                                  (4, range(0x12A0, 0x1369))):
            for y in positions:
                word(m, 0x22, 0x0F7E); word(m, 0x20, y - 8)
                m = cart(m, xy=(0x0F80, y), action=action)
                result = self.execute(m)
                if 0x0468 in result.writes:
                    transitions.append((action, y, result.writes[0x0468]))
                m = result.memory
                m[0x11] = 0
        self.assertEqual(transitions, [(2, 0x1350, 0), (2, 0x12AF, 1),
                                       (4, 0x12B8, 0), (4, 0x1361, 1)])
        # At the return trigger, the full cart front is still eight pixels
        # north of the upper face. N20 and its mounted Link are clear.
        self.assertEqual(0x12D8 - (0x12B8 + 24), 8)
        self.assertLess(0x12A0, 0x12B0)

    def test_only_locked_keydoor_resets_selector1(self):
        m = self.execute(room(key_open=False))
        self.assertEqual(m.writes, {0x0231: 0})
        self.assertEqual((m.memory[0x0230], m.memory[0x0232]), (0xA5, 0x5A))
        for flags in (0x4000, 0xC000, 0xFFFF):
            memory = room(); word(memory, 0x0400, flags)
            self.assertFalse(self.execute(memory).writes)
        memory = room(key_open=False); memory[0x0231] = 0
        self.assertFalse(self.execute(memory).writes)

    def test_gateway_scopes_exact_room_word_and_retains_legacy_elsewhere(self):
        code, labels = program(body(SOURCE, "RoomTag_CartShutterDispatch"))
        for room_id in (0x97, 0x197, 0x77, 0x98):
            m = {0xAE: 0x37, 0xAF: 0}; word(m, 0xA0, room_id)
            actual = Machine(m).run(code, labels)
            self.assertEqual(actual, "RoomTag_CartShutter97" if room_id == 0x97
                             else "RoomTag_ShutterDoorRequiresCart")

    def test_lever_prep_resets_only_locked_room97_group1(self):
        lines = body(ROOT / "Sprites/Objects/mineswitch.asm", "Sprite_LeverSwitch_Prep")
        start = lines.index("if !ENABLE_MINECART_CART_SHUTTERS") + 1
        lines = lines[start:lines.index("endif", start)] + ["JML $01CC5A"]
        code, labels = program(lines)
        for room_id, group, flags, writes in ((0x97, 1, 0, {0x0231: 0}),
                                             (0x97, 0, 0, {}), (0x77, 1, 0, {}),
                                             (0x197, 1, 0, {}), (0x97, 1, 0x4000, {})):
            m = room(); word(m, 0xA0, room_id); word(m, 0x0400, flags)
            machine = Machine(m, y=group)
            self.assertEqual(machine.run(code, labels), "$01CC5A")
            self.assertEqual(machine.writes, writes)
            self.assertEqual(machine.y, group)

    def test_new_code_stays_inside_existing_default_off_guard(self):
        text = SOURCE.read_text()
        flag = "if !ENABLE_MINECART_CART_SHUTTERS"
        guarded = text.split("\n" + flag + "\npushpc\n", 1)[1].split("\nendif", 1)[0]
        for label in ("RoomTag_CartShutterDispatch:", "RoomTag_CartShutter97:", "CartShutter97_DragPlayer:"):
            self.assertIn(label, guarded)
        for direction in ("North", "South"):
            self.assertRegex(text, flag + r"\s+CartShutter97_Drag" + direction + r"Call:\s+"
                             r"JSL CartShutter97_DragPlayer\s+CartShutter97_Drag" + direction +
                             r"Call_End:\s+else\s+JSL DragPlayer\s+endif")
        self.assertEqual(text.count("JSL CartShutter97_DragPlayer"), 2)
        flags = (ROOT / "Util/macros.asm").read_text() + (ROOT / "Config/feature_flags.asm").read_text()
        self.assertNotRegex(flags, r"!ENABLE_MINECART_CART_SHUTTERS\s*(?:\?=|=)\s*1\b")
        self.assertEqual(body(SOURCE, "RoomTag_ShutterDoorRequiresCart"), [
            "LDA.w !LinkInCart", "BEQ .no_cart", "REP #$30", "LDX.w #$0000",
            "CPX.w $0468", "BEQ .exit", "STZ.w $0468", "STZ.w $068E", "STZ.w $0690",
            "SEP #$30", "LDA.b #$1B", "STA.w $012F", "LDA.b #$05", "STA.b $11",
            ".exit", "SEP #$30", ".no_cart", "JML $01CC5A"])

    def test_gate_allocation_is_bounded_outside_sprite_bank31(self):
        text = SOURCE.read_text()
        self.assertRegex(text, r"pushpc\s+org \$2CFA00\s+[^{}]*CartShutter97_DragPlayer:")
        self.assertRegex(text, r"CartShutter97_DragPlayer_End:\s+assert pc\(\) <= \$2CFB00")
        self.assertRegex(text, r"pushpc\s+org \$2CFB00\s+RoomTag_CartShutterDispatch:")
        self.assertRegex(text, r'RoomTag_CartShutter97_End:\s+assert pc\(\) <= \$2CFD00[^\n]*\s+pullpc\s+incsrc "Sprites/Objects/cart_shutter97_preserved.asm"\s+endif')
        sprites = (ROOT / "Sprites/all_sprites.asm").read_text()
        self.assertRegex(sprites, r'incsrc "Sprites/NPCs/goron.asm"[\s\S]*?'
                                  r'if !ENABLE_MINECART_CART_SHUTTERS\s+assert pc\(\) <= \$2CF000')
        sizes = {op: 1 for op in ("XBA", "DEX", "INX", "CLC", "SEC", "RTS", "PHP", "PLP", "PHA", "PLA", "PHX", "PLX")}
        sizes.update({"JML": 4, "JMP": 3, "JSR": 3, "REP": 2, "SEP": 2,
                 "BEQ": 2, "BNE": 2, "BCC": 2, "BCS": 2, "BPL": 2, "BRA": 2}
                     )
        total = 0
        for name in ("RoomTag_CartShutterDispatch", "RoomTag_CartShutter97", "CartShutter97_Hold", "CartShutter97_TransitionHold"):
            code, _ = program(body(SOURCE, name))
            total += sum(sizes[op] if op in sizes else 1 + {"b": 1, "w": 2}[suffix]
                         for op, suffix, _ in code)
        self.assertLessEqual(total, 0x200)

    def test_drag_wrapper_admits_only_current_room97_floor0_shaft_cart(self):
        code, labels = program(body(SOURCE, "CartShutter97_DragPlayer"))
        baseline = cart(room(mounted=True), xy=(0x0F78, 0x1300))
        word(baseline, 0x0FD8, 0xA55A)
        rejected = []
        for address, value in ((0x1B, 0), (0xEE, 1), (0x35, 0), (0x0F23, 1)):
            state = dict(baseline); state[address] = value
            rejected.append(state)
        for address, values in ((0xA0, (0x77, 0x98, 0x197)), (0x07EA, (2, 0x103))):
            for value in values:
                state = dict(baseline); word(state, address, value)
                rejected.append(state)
        rejected.extend(cart(baseline, xy=xy) for xy in
                        ((0x0F77, 0x1300), (0x0F79, 0x1300), (0x0F80, 0x1300),
                         (0x1F78, 0x1300), (0x0F78, 0x12AF), (0x0F78, 0x1359),
                         (0x0F78, 0x22B0)))
        admitted = [cart(baseline, xy=(0x0F78, y)) for y in (0x12B0, 0x1300, 0x1358)]
        for qualifies, states in ((False, rejected), (True, admitted)):
            for state in states:
                for direction in (0, 1):
                    with self.subTest(qualifies=qualifies, state=state, direction=direction):
                        machine = Machine(state, a=0xABCD, x=3, y=direction)
                        machine.drag_calls = []
                        self.assertEqual(machine.run(code, labels), "RTL" if qualifies else "DragPlayer")
                        self.assertEqual(machine.drag_calls, [(0x0F7A, 3, direction, 0x30)] if qualifies else [])
                        self.assertEqual(machine.memory, state)
                        self.assertEqual((machine.x, machine.y, machine.sp, machine.p & 0x30),
                                         (3, direction, 0x01FB, 0x30))

    def test_transition_close_skips_only_open_room97_held_corridor(self):
        code, labels = with_hold("CartShutter97_TransitionHold")
        near_link = room(closed=False, link=(0x0F7E, 0x12D0))
        near_cart = cart(room(closed=False), xy=(0x0F80, 0x12E0), action=2)
        cases = [(near_link, "$028A05"), (near_cart, "$028A05"),
                 (room(closed=False), "$0289F8"),
                 (room(closed=True, link=(0x0F7E, 0x12D0)), "$028A05"),
                 (cart(room(closed=False), xy=(0x0F80, 0x12E0), state=0), "$0289F8"),
                 (cart(room(closed=False), xy=(0x0F80, 0x12E0), layer=1), "$0289F8")]
        for room_id in (0x77, 0x87, 0x98, 0x197):
            memory = dict(near_link); word(memory, 0xA0, room_id)
            cases.append((memory, "$0289F8"))
        for i, (memory, target) in enumerate(cases):
            for carry in (False, True):
                with self.subTest(case=i, carry=carry):
                    machine = Machine(memory, p=0x3C, a=0xABCD, x=0x7B, y=0x5A)
                    machine.c, machine.v = carry, True
                    self.assertEqual(machine.run(code, labels), target)
                    self.assertEqual((machine.x, machine.y, machine.sp, machine.a),
                                     (0x7B, 0x5A, 0x01FB, 0xAB00 | memory[0x0468]))
                    self.assertEqual((machine.c, machine.v, machine.p & 0x3C), (carry, True, 0x3C))
                    self.assertFalse(machine.writes)

    def test_transition_gateway_pins_original_five_bytes_and_exact_resume_addresses(self):
        text = SOURCE.read_text()
        self.assertIn('assert read4($0289F3) == $D00468AD && read1($0289F7) == $0D', text)
        self.assertRegex(text, r'org \$0289F3[^\n]*\s+JML CartShutter97_TransitionHold\s+NOP\s+assert pc\(\) == \$0289F8')

    def test_every_relative_branch_fits_without_assembling(self):
        offsets, offset = [], 0
        for op, suffix, arg in self.code:
            offsets.append(offset)
            if op in ("XBA", "DEX", "INX", "CLC", "SEC", "RTS", "PHP", "PLP", "PHA", "PLA", "PHX", "PLX"): size = 1
            elif op == "JML": size = 4
            elif op in ("JMP", "JSR"): size = 3
            elif op in ("REP", "SEP", "BEQ", "BNE", "BCC", "BCS", "BPL", "BRA"): size = 2
            else: size = 1 + {"b": 1, "w": 2}[suffix]
            offset += size
        for i, (op, _, arg) in enumerate(self.code):
            if op in ("BEQ", "BNE", "BCC", "BCS", "BPL", "BRA"):
                displacement = offsets[self.labels[arg]] - offsets[i] - 2
                self.assertTrue(-128 <= displacement <= 127, (op, arg, displacement))


if __name__ == "__main__":
    unittest.main()
