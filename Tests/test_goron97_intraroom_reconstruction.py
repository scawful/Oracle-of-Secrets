"""Host-side admission for the room97 intraroom follower reconstruction window.

Evidence: native candidate-r4 controller-steps.jsonl frames3792,3793,3874,3875;
B2 anchor from R05/ALIGNMENT_PROOF.json. Fixtures are literals only (no AFS paths).
"""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).parent / "native" / "goron97_cart_gate.py"
SPEC = importlib.util.spec_from_file_location("goron97_cart_gate", PATH)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)

OFFSCREEN = {"state": 0, "kind": 0, "subtype": 0, "action": 0, "direction": 0,
             "timer": 0, "floor": 0, "x": -3584, "y": -4608}
CART14_RIDE = {"state": 9, "kind": 0xA3, "subtype": 0, "action": 2, "direction": 0,
               "timer": 0, "floor": 0, "x": 376, "y": 281}
CART14_RELEASE = {"state": 9, "kind": 0xA3, "subtype": 0, "action": 6, "direction": 0,
                  "timer": 0, "floor": 0, "x": 376, "y": 280}
CART15_B2 = {"state": 9, "kind": 0xA3, "subtype": 0, "action": 3, "direction": 1,
             "timer": 0, "floor": 0, "x": 376, "y": 184}


def sprites(overrides):
    rows = []
    for slot in range(16):
        row = {"slot": slot, **OFFSCREEN}
        if slot in overrides:
            row.update(overrides[slot])
        rows.append(row)
    return rows


def snap(submodule, ly, doorway, cart_slot, cart_overrides):
    return {"module": 7, "submodule": submodule, "indoors": 1, "room": gate.ROOM,
            "lx": 376, "ly": ly, "layer": 0, "mounted": 1, "track": 0, "doorway": doorway,
            "cart_slot": cart_slot, "sprites": sprites(cart_overrides)}


FRAME_3792 = snap(0, 274, 1, 14, {14: CART14_RIDE})
FRAME_3793 = snap(1, 273, 1, 14, {14: CART14_RIDE})
FRAME_3874 = snap(1, 192, 0, 14, {14: CART14_RIDE})
FRAME_3875 = snap(0, 192, 0, 15, {14: CART14_RELEASE, 15: CART15_B2})


def route_stub(frame_count, owned_slot=14):
    route = gate.Route.__new__(gate.Route)
    route.seam = None
    route.intraroom = None
    route.owned_cart = (gate.ROOM, owned_slot)
    route.frame_count = frame_count
    route.result = {}
    return route


def open_hold(route):
    gate.Route.validate_cart(route, FRAME_3792, FRAME_3793)
    route.frame_count = 3875


class Goron97IntraroomReconstruction(unittest.TestCase):
    def test_hold_entry_hold_and_exit_through_validate_cart(self):
        route = route_stub(3793, owned_slot=14)
        gate.Route.validate_cart(route, FRAME_3792, FRAME_3793)
        self.assertEqual(route.intraroom, {"old_slot": 14, "start_frame": 3793})
        route.frame_count = 3875
        cart = gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)
        self.assertEqual(cart["slot"], 15)
        self.assertEqual(route.owned_cart, (gate.ROOM, 15))
        self.assertIsNone(route.intraroom)
        self.assertEqual(route.result["intraroom_reconstructions"][0]["new_slot"], 15)

    def test_exit_without_hold_entry_is_rejected(self):
        route = route_stub(3875)
        with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)

    def test_off_aperture_hold_entry_is_rejected(self):
        route = route_stub(3793)
        bad_prev = snap(0, 200, 1, 14, {14: CART14_RIDE})
        bad_state = snap(1, 199, 1, 14, {14: CART14_RIDE})
        gate.Route.validate_cart(route, bad_prev, bad_state)
        self.assertIsNone(route.intraroom)
        route.frame_count = 3875
        with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)

    def test_wrong_prior_ownership_at_entry_is_rejected(self):
        route = route_stub(3793, owned_slot=5)
        with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
            gate.Route.validate_cart(route, FRAME_3792, FRAME_3793)

    def test_previous_unmounted_at_entry_is_rejected(self):
        route = route_stub(3793)
        gate.Route.validate_cart(route, dict(FRAME_3792, mounted=0), FRAME_3793)
        self.assertIsNone(route.intraroom)
        route.frame_count = 3875
        with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)

    def test_wrong_track_at_entry_is_rejected(self):
        route = route_stub(3793)
        with self.assertRaisesRegex(RuntimeError, "changed track"):
            gate.Route.validate_cart(route, FRAME_3792, dict(FRAME_3793, track=1))

    def test_exit_rejections_after_qualified_hold(self):
        cases = [
            ("link_layer_one", dict(FRAME_3875, layer=1), "qualified ride context"),
            ("new_cart_wrong_floor", {**FRAME_3875,
             "sprites": sprites({14: CART14_RELEASE, 15: {**CART15_B2, "floor": 1}})},
             "qualified reconstruction"),
            ("wrong_new_cart_action", {**FRAME_3875,
             "sprites": sprites({14: CART14_RELEASE, 15: {**CART15_B2, "action": 2}})},
             "qualified reconstruction"),
            ("wrong_new_cart_direction", {**FRAME_3875,
             "sprites": sprites({14: CART14_RELEASE, 15: {**CART15_B2, "direction": 0}})},
             "qualified reconstruction"),
            ("cart_slot_identity_mismatch", dict(FRAME_3875, cart_slot=14),
             "qualified reconstruction"),
            ("off_route_replacement", {**FRAME_3875,
             "sprites": sprites({14: CART14_RELEASE, 15: {**CART15_B2, "x": 320}})},
             "qualified reconstruction"),
        ]
        for name, exit_state, pattern in cases:
            with self.subTest(name=name):
                route = route_stub(3793)
                open_hold(route)
                with self.assertRaisesRegex(RuntimeError, pattern):
                    gate.Route.validate_cart(route, FRAME_3874, exit_state)

    def test_delayed_reconstruction_is_rejected(self):
        route = route_stub(3793)
        open_hold(route)
        route.frame_count = 3890
        with self.assertRaisesRegex(RuntimeError, "bounded window"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)

    def test_too_early_reconstruction_is_rejected(self):
        route = route_stub(3793)
        gate.Route.validate_cart(route, FRAME_3792, FRAME_3793)
        route.frame_count = 3799
        with self.assertRaisesRegex(RuntimeError, "qualified reconstruction"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)


if __name__ == "__main__":
    unittest.main()
