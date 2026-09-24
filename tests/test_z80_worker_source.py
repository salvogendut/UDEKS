# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Z80WorkerSourceTests(unittest.TestCase):
    def test_worker_precedes_console_and_has_service_descriptor(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        descriptor = (ROOT / "src/services/engine/descriptor.s").read_text(
            encoding="utf-8"
        )
        worker = table.index(".addr _udeks_z80_worker_service_descriptor")
        console = table.index(".addr _udeks_console_service_descriptor", worker)
        self.assertLess(worker, console)
        self.assertIn(".byte $08, $00", descriptor)
        self.assertIn(".addr _udeks_z80_worker_start", descriptor)

    def test_8502_gateway_restores_each_private_bank(self):
        source = (ROOT / "src/8502/z80_handoff.s").read_text(encoding="utf-8")
        self.assertIn("Z80_HANDOFF_GATEWAY     = $ffd0", source)
        self.assertIn("Z80_CONTINUATION        = $ffed", source)
        self.assertIn("$3e, $3e", source)
        self.assertIn("$3e, $7e", source)
        self.assertIn("$3e, $b1", source)
        self.assertIn("Z80 bootstrap size drift", source)
        self.assertIn("Z80 common gateways overlap", source)

    def test_worker_validates_and_publishes_state_last(self):
        source = (ROOT / "src/z80/worker.c").read_text(encoding="utf-8")
        self.assertIn("validate_request()", source)
        self.assertIn("UDEKS_MB_STATUS_RESERVED", source)
        self.assertIn("UDEKS_MB_STATE_RUNNING", source)
        complete = source.index("UDEKS_MB_STATE_COMPLETE")
        status = source.index("UDEKS_MB_STATUS_OK", source.index("void z80_main"))
        self.assertLess(status, complete)
        self.assertIn("udeks_z80_yield()", source)

    def test_requester_checks_sequence_and_response(self):
        source = (ROOT / "src/services/engine/z80_worker.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("UDEKS_MB_STATE_SUBMITTED", source)
        self.assertIn("UDEKS_Z80_SEQUENCE_INVALID", source)
        self.assertIn("UDEKS_Z80_RESPONSE_INVALID", source)
        self.assertIn("UDEKS_Z80_TIMING_STOCK", source)
        self.assertIn("UDEKS_MB_OP_NOP", source)
        self.assertIn("BOOT_CHAIN_BYTE(12) == 2u", source)


if __name__ == "__main__":
    unittest.main()
