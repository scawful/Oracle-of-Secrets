"""Synthetic proof scripts for Scripts/Agents/proof_audit.py; no emulator needed."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "proof_audit", ROOT / "Scripts" / "Agents" / "proof_audit.py")
proof_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = proof_audit
SPEC.loader.exec_module(proof_audit)

HEADER = """
W = 0x7E0000
def w8(addr, val):
    b.write_memory(addr, val & 0xFF)
def w16(addr, val):
    w8(addr, val & 0xFF)
    w8(addr + 1, val >> 8)
def walk_up(n):
    case.tick(n, "up")
"""


class ProofAuditTest(unittest.TestCase):
    def audit(self, body, **contract):
        base = {
            "row": "QUEUE999", "tier": "T2", "script": "proof.py",
            "under_test": ["0x7EF3CC"],
            "routes": [{"name": "route", "function": "route"}],
            "control": "baseline build", "break_it": [],
        }
        base.update(contract)
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "proof.py").write_text(HEADER + textwrap.dedent(body))
            (d / "proof_contract.json").write_text(json.dumps(base))
            return proof_audit.run(d / "proof_contract.json")

    def test_poke_of_state_under_test_fails(self):
        rep = self.audit("""
        def route():
            walk_up(10)
            w8(0x7EF3CC, 0x08)
        """)
        self.assertEqual(rep.status, "FAIL")
        self.assertEqual(len(rep.under_test_writes), 1)
        self.assertIn("$7EF3CC", rep.failures[0])

    def test_wrapper_width_constant_and_low_ram_fold(self):
        rep = self.audit("""
        def route():
            walk_up(10)
            w16(W + 0x0FFE, 0x0100)
        """, under_test=["0x7E0FFF"])
        self.assertEqual(rep.status, "FAIL")
        self.assertEqual(rep.under_test_writes[0]["bytes"], ["$7E0FFE", "$7E0FFF"])
        rep = self.audit("""
        def route():
            walk_up(10)
            b.write_memory(0x0FFF, 1)
        """, under_test=["0x7E0FFF"])
        self.assertEqual(rep.status, "FAIL")

    def test_write_block_covers_range(self):
        rep = self.audit("""
        def route():
            walk_up(1)
            b.write_block(0x7EF3CA, [0, 0, 8])
        """)
        self.assertEqual(rep.status, "FAIL")

    def test_control_marker_passes(self):
        rep = self.audit("""
        def route():
            walk_up(10)
        def control():
            # proof: control-begin
            w8(0x7EF3CC, 0x08)
            # proof: control-end
            w8(0x7EF3CC, 0x08)  # proof: control
        """)
        self.assertEqual(rep.status, "PASS", rep.failures)
        self.assertEqual(len(rep.control_writes), 2)

    def test_setup_marker_only_before_input(self):
        rep = self.audit("""
        def route():
            w8(0x7EF3CC, 0x00)  # proof: setup
            walk_up(10)
        """)
        self.assertEqual(rep.status, "PASS", rep.failures)
        self.assertEqual(len(rep.start_state_writes), 1)
        rep = self.audit("""
        def route():
            walk_up(10)
            w8(0x7EF3CC, 0x07)  # proof: setup
        """)
        self.assertEqual(rep.status, "FAIL")
        self.assertIn("after input", rep.failures[0])

    def test_route_without_input_fails(self):
        rep = self.audit("""
        def route():
            case.tick(30)
            w8(0x7E0022, 0x40)
        """)
        self.assertEqual(rep.status, "FAIL")
        self.assertIn("drives no joypad input", rep.failures[0])

    def test_route_input_forms(self):
        for call in ('b.press_button("A", frames=4)',
                     'b.send_command("INPUT", {"buttons": "up", "frames": 4})',
                     'case.tick(2, buttons=["up"])',
                     'drive(3)'):
            rep = self.audit(f"""
            def route():
                {call}
            """, input_functions=["drive"])
            self.assertEqual(rep.status, "PASS", (call, rep.failures))

    def test_contract_completeness(self):
        rep = self.audit("""
        def route():
            walk_up(1)
        """, tier="T3", break_it=["a", "b"], control="")
        self.assertEqual(rep.status, "FAIL")
        text = " ".join(rep.failures)
        self.assertIn("3 break_it", text)
        self.assertIn("control is empty", text)

    def test_unresolved_addresses_are_listed_not_failed(self):
        rep = self.audit("""
        def route(slot):
            walk_up(1)
            w8(W + 0x0F70 + slot, 0)
        """)
        self.assertEqual(rep.status, "PASS")
        self.assertEqual(len(rep.unresolved_writes), 1)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.json"
            missing.write_text(json.dumps({"tier": "T2", "script": "absent.py"}))
            self.assertEqual(proof_audit.main([str(missing)]), 2)


if __name__ == "__main__":
    unittest.main()
