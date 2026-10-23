"""Host-side admission for the room97 intraroom follower reconstruction window.

Evidence: native candidate-r4 controller-steps.jsonl frames3792,3793,3874,3875;
B2 anchor from R05/ALIGNMENT_PROOF.json. Fixtures are literals only (no AFS paths).
R10 retirement-candidate-r1 frame3850 retains inactive old14 action2/y281.
South literals are R10 candidate-r2 frames4184,4185,4262,4263 (not mirrored).
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
CART15_SOUTH = {"state": 9, "kind": 0xA3, "subtype": 0, "action": 4, "direction": 2,
                "timer": 0, "floor": 0, "x": 376, "y": 236}
CART14_SOUTH = {**CART15_SOUTH, "x": 378, "y": 305}
FRAME_4184 = snap(0, 227, 1, 15, {15: CART15_SOUTH})
FRAME_4185 = snap(1, 244, 1, 15, {15: CART15_SOUTH})
FRAME_4262 = snap(1, 304, 0, 15, {15: CART15_SOUTH})
FRAME_4263 = snap(0, 304, 0, 14, {15: {**CART15_SOUTH, "state": 0}, 14: CART14_SOUTH})


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


def south_route():
    route = route_stub(4185, owned_slot=15)
    route.expect_retired_cart = True
    route.phase = "ride-south"
    return route


def open_south_hold(route):
    gate.Route.validate_cart(route, FRAME_4184, FRAME_4185)
    route.frame_count = 4263


def alter_actor(snapshot, slot, **changes):
    return {**snapshot, "sprites": [{**actor, **changes} if actor["slot"] == slot else dict(actor)
                                   for actor in snapshot["sprites"]]}


class Goron97IntraroomReconstruction(unittest.TestCase):
    def test_captured_south_entry_hold_and_retired_exit(self):
        route = south_route()
        open_south_hold(route)
        self.assertEqual(route.intraroom, {"old_slot": 15, "start_frame": 4185,
                                          "profile": gate.SOUTH_PROFILE})
        route.frame_count = 4262
        gate.Route.validate_cart(route, FRAME_4185, FRAME_4262)
        self.assertEqual(route.owned_cart, (gate.ROOM, 15))
        route.frame_count = 4263
        cart = gate.Route.validate_cart(route, FRAME_4262, FRAME_4263)
        self.assertEqual(cart["slot"], 14)
        self.assertEqual(route.owned_cart, (gate.ROOM, 14))
        self.assertIsNone(route.intraroom)
        self.assertEqual(route.result["intraroom_reconstructions"], [{
            "old_slot": 15, "start_frame": 4185, "profile": gate.SOUTH_PROFILE,
            "new_slot": 14, "end_frame": 4263, "old_retired": True}])

    def test_south_requires_retirement_mode_and_ride_south_phase(self):
        for mode, phase in ((False, "ride-south"), (True, "ride-north")):
            with self.subTest(mode=mode, phase=phase):
                route = south_route()
                route.expect_retired_cart, route.phase = mode, phase
                open_south_hold(route)
                self.assertIsNone(route.intraroom)
                with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
                    gate.Route.validate_cart(route, FRAME_4262, FRAME_4263)

    def test_south_exit_requires_the_captured_entry(self):
        route = south_route()
        gate.Route.validate_cart(route, dict(FRAME_4184, ly=200), FRAME_4185)
        self.assertIsNone(route.intraroom)
        route.frame_count = 4263
        with self.assertRaisesRegex(RuntimeError, "owned T0 slot"):
            gate.Route.validate_cart(route, FRAME_4262, FRAME_4263)

    def test_south_entry_rejects_wrong_context_owner_or_actor(self):
        cases = [(dict(FRAME_4184, **change), FRAME_4185) for change in (
            {"room": gate.ENTRY}, {"module": 9}, {"submodule": 1}, {"indoors": 0},
            {"mounted": 0}, {"layer": 1}, {"track": 1}, {"doorway": 0},
            {"cart_slot": 14}, {"lx": 368}, {"ly": 220})]
        cases += [(FRAME_4184, dict(FRAME_4185, **change)) for change in (
            {"room": gate.ENTRY}, {"module": 9}, {"submodule": 0}, {"indoors": 0},
            {"layer": 1}, {"track": 1}, {"doorway": 0}, {"cart_slot": 14},
            {"lx": 368}, {"ly": 250})]
        cases += [(FRAME_4184, alter_actor(FRAME_4185, 15, **change)) for change in (
            {"state": 0}, {"kind": 0xB0}, {"subtype": 1}, {"floor": 1},
            {"action": 2}, {"direction": 0}, {"x": 384}, {"y": 244})]
        for previous, state in cases:
            with self.subTest(previous=previous, state=state):
                self.assertFalse(gate.south_hold_started(
                    previous, state, (gate.ROOM, 15), None, gate.Route.live_cart(state)))
        for owned, seam in (((gate.ROOM, 14), None), ((gate.ENTRY, 15), None),
                            ((gate.ROOM, 15), {"active": True})):
            self.assertFalse(gate.south_hold_started(
                FRAME_4184, FRAME_4185, owned, seam, gate.Route.live_cart(FRAME_4185)))

    def test_south_exit_rejects_wrong_context_pose_and_retirement(self):
        exits = [dict(FRAME_4263, **change) for change in (
            {"room": gate.ENTRY}, {"module": 9}, {"submodule": 1}, {"indoors": 0},
            {"layer": 1}, {"track": 1}, {"doorway": 1}, {"cart_slot": 15},
            {"lx": 368}, {"ly": 296})]
        exits += [alter_actor(FRAME_4263, 15, **change) for change in (
            {"state": 9}, {"kind": 0xB0}, {"subtype": 1}, {"floor": 1},
            {"action": 6}, {"direction": 0}, {"x": 384}, {"y": 244})]
        exits += [alter_actor(FRAME_4263, 14, **change) for change in (
            {"state": 0}, {"kind": 0xB0}, {"subtype": 1}, {"floor": 1},
            {"action": 3}, {"direction": 1}, {"x": 384}, {"y": 312})]
        for state in exits:
            with self.subTest(state=state):
                route = south_route()
                open_south_hold(route)
                with self.assertRaises(RuntimeError):
                    gate.Route.validate_cart(route, FRAME_4262, state)

    def test_south_exit_rejects_wrong_previous_context(self):
        previous_states = [dict(FRAME_4262, **change) for change in (
            {"module": 9}, {"submodule": 0}, {"indoors": 0}, {"layer": 1},
            {"track": 1}, {"mounted": 0}, {"doorway": 1}, {"cart_slot": 14},
            {"lx": 368}, {"ly": 296})]
        previous_states += [alter_actor(FRAME_4262, 15, state=0)]
        for previous in previous_states:
            with self.subTest(previous=previous):
                route = south_route()
                open_south_hold(route)
                with self.assertRaises(RuntimeError):
                    gate.Route.validate_cart(route, previous, FRAME_4263)

    def test_south_hold_rejects_departure_and_lost_owned_actor(self):
        states = [dict(FRAME_4262, lx=368), dict(FRAME_4262, ly=320),
                  dict(FRAME_4262, cart_slot=14), dict(FRAME_4262, mounted=0),
                  alter_actor(FRAME_4262, 15, state=0),
                  alter_actor(FRAME_4262, 15, action=2)]
        for state in states:
            with self.subTest(state=state):
                route = south_route()
                open_south_hold(route)
                route.frame_count = 4262
                with self.assertRaises(RuntimeError):
                    gate.Route.validate_cart(route, FRAME_4185, state)

    def test_south_reconstruction_rejects_short_or_expired_cadence(self):
        for elapsed in (69, 87):
            with self.subTest(elapsed=elapsed):
                route = south_route()
                open_south_hold(route)
                route.frame_count = 4185 + elapsed
                with self.assertRaises(RuntimeError):
                    gate.Route.validate_cart(route, FRAME_4262, FRAME_4263)

    def test_retirement_candidate_requires_old_actor_inactive(self):
        route = route_stub(3793)
        route.expect_retired_cart = True
        open_hold(route)
        retired = {**FRAME_3875, "sprites": sprites({
            14: {**CART14_RIDE, "state": 0}, 15: CART15_B2})}
        gate.Route.validate_cart(route, FRAME_3874, retired)
        self.assertEqual(route.owned_cart, (gate.ROOM, 15))
        self.assertTrue(route.result["intraroom_reconstructions"][0]["old_retired"])

    def test_retirement_candidate_rejects_wrong_inactive_pose(self):
        for old in ({**CART14_RELEASE, "state": 0},
                    {**CART14_RIDE, "state": 0, "y": 288}):
            with self.subTest(old=old):
                route = route_stub(3793)
                route.expect_retired_cart = True
                open_hold(route)
                retired = {**FRAME_3875, "sprites": sprites({14: old, 15: CART15_B2})}
                with self.assertRaisesRegex(RuntimeError, "qualified reconstruction"):
                    gate.Route.validate_cart(route, FRAME_3874, retired)

    def test_retirement_candidate_rejects_live_superseded_actor(self):
        route = route_stub(3793)
        route.expect_retired_cart = True
        open_hold(route)
        with self.assertRaisesRegex(RuntimeError, "qualified reconstruction"):
            gate.Route.validate_cart(route, FRAME_3874, FRAME_3875)

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
