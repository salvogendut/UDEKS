# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bench_decode import parse_result as parse_bench
from context_decode import parse_result as parse_context
from handoff_decode import parse_result as parse_handoff
from irq_probe_decode import parse_result as parse_irq_probe
from irq_service_decode import parse_result as parse_irq_service
from kernel_decode import parse_result as parse_kernel
from offload_decode import parse_result as parse_offload


class PreservedViceResultTests(unittest.TestCase):
    def test_all_r2_blocks_pass_strict_decoding(self):
        result_root = ROOT / "bench/results/vice-3.10-2026-09-24-r2"
        cases = {
            parse_bench: (
                "raw/shared-c-8502-1mhz.bin",
                "raw/shared-c-8502-2mhz.bin",
                "raw/shared-c-z80-stock.bin",
            ),
            parse_irq_probe: (
                "raw/irq-entry-8502-1mhz.bin",
                "raw/irq-entry-8502-2mhz.bin",
                "raw/irq-entry-z80-stock.bin",
            ),
            parse_irq_service: (
                "raw/irq-service-8502-1mhz.bin",
                "raw/irq-service-8502-2mhz.bin",
                "raw/irq-service-z80-stock.bin",
                "repeats/irq-service-8502-1mhz-run2.bin",
                "repeats/irq-service-8502-1mhz-run3.bin",
                "repeats/irq-service-8502-2mhz-run2.bin",
                "repeats/irq-service-8502-2mhz-run3.bin",
                "repeats/irq-service-z80-stock-run2.bin",
                "repeats/irq-service-z80-stock-run3.bin",
            ),
            parse_context: (
                "raw/context-8502-1mhz.bin",
                "raw/context-8502-2mhz.bin",
                "raw/context-z80-stock.bin",
            ),
            parse_kernel: (
                "raw/kernel-8502-1mhz.bin",
                "raw/kernel-8502-2mhz.bin",
                "raw/kernel-z80-stock.bin",
            ),
            parse_handoff: ("raw/handoff-1mhz.bin", "raw/handoff-2mhz.bin"),
            parse_offload: (
                "raw/offload-1mhz.bin",
                "raw/offload-2mhz.bin",
                "repeats/offload-1mhz-run2.bin",
                "repeats/offload-1mhz-run3.bin",
                "repeats/offload-2mhz-run2.bin",
                "repeats/offload-2mhz-run3.bin",
            ),
        }
        for parser, names in cases.items():
            for name in names:
                with self.subTest(result=name):
                    parser((result_root / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
