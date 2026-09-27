# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gen_scheduler_overlay_imports",
    ROOT / "tools/gen_scheduler_overlay_imports.py",
)
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)


class SchedulerOverlayImportTests(unittest.TestCase):
    def test_external_imports_exclude_overlay_providers(self):
        original = gen.object_records
        records = {
            ("state.o", "imports"): [("runtime", "02")],
            ("state.o", "exports"): [("lifecycle", "02")],
            ("policy.o", "imports"): [("lifecycle", "02"), ("sp", "01")],
            ("policy.o", "exports"): [("policy", "02")],
        }
        try:
            expected = (
                gen.EXPECTED_EXTERNALS,
                gen.EXPECTED_ABSOLUTE,
                gen.EXPECTED_ZEROPAGE,
            )
            gen.EXPECTED_EXTERNALS = 2
            gen.EXPECTED_ABSOLUTE = 1
            gen.EXPECTED_ZEROPAGE = 1
            gen.object_records = lambda path, section: records[(path, section)]
            self.assertEqual(
                gen.external_imports(["state.o", "policy.o"]),
                [("runtime", "02"), ("sp", "01")],
            )
        finally:
            gen.object_records = original
            (
                gen.EXPECTED_EXTERNALS,
                gen.EXPECTED_ABSOLUTE,
                gen.EXPECTED_ZEROPAGE,
            ) = expected

    def test_runtime_contract_count_is_locked(self):
        original = gen.object_records
        try:
            gen.object_records = lambda path, section: (
                [("runtime", "02")] if section == "imports" else []
            )
            with self.assertRaisesRegex(ValueError, "expected overlay runtime contract"):
                gen.external_imports(["state.o"])
        finally:
            gen.object_records = original

    def test_type_conflicts_and_missing_map_symbols_fail(self):
        with self.assertRaisesRegex(ValueError, "conflicting address types"):
            gen.canonicalize([("sp", "01"), ("sp", "02")])
        with self.assertRaisesRegex(ValueError, "missing from normal"):
            gen.resolve_bridge([("sp", "01")], {}, {"sp": (6, "RLZ")})

    def test_normal_panic_parity_and_address_class_are_required(self):
        imports = [("runtime", "02"), ("sp", "01")]
        normal = {"runtime": (0x4000, "RLA"), "sp": (0x0006, "RLZ")}
        self.assertEqual(
            gen.resolve_bridge(imports, normal, dict(normal)),
            [("runtime", "02", 0x4000), ("sp", "01", 0x0006)],
        )
        panic = dict(normal)
        panic["runtime"] = (0x4001, "RLA")
        with self.assertRaisesRegex(ValueError, "normal/panic mismatch"):
            gen.resolve_bridge(imports, normal, panic)
        wrong = dict(normal)
        wrong["sp"] = (0x0006, "RLA")
        with self.assertRaisesRegex(ValueError, "map type"):
            gen.resolve_bridge(imports, wrong, wrong)

    def test_bridge_locks_both_placement_windows(self):
        source = gen.render_bridge(
            [("runtime", "02", 0x4000), ("sp", "01", 0x0006)]
        )
        self.assertIn(".export runtime\nruntime = $4000", source)
        self.assertIn(".exportzp sp\nsp = $0006", source)
        self.assertIn("__SCHEDULER_RUN__ = $1c00", source)
        self.assertIn("__SCHEDULER_SIZE__ <= $0400", source)
        self.assertIn("__CODE_RUN__ = $c120", source)
        self.assertIn("__BSS_RUN__ + __BSS_SIZE__ <= $cc00", source)


class SchedulerOverlaySourceTests(unittest.TestCase):
    def test_transition_engine_is_assigned_to_the_scheduler_page(self):
        source = (ROOT / "src/kernel/task_state.c").read_text(encoding="utf-8")
        push = source.index('#pragma code-name(push, "SCHEDULER")')
        apply = source.index("unsigned char udeks_lifecycle_apply", push)
        pop = source.index("#pragma code-name(pop)", apply)
        self.assertLess(push, apply)
        self.assertLess(apply, pop)

    def test_link_only_layout_uses_the_frozen_reclaim_windows(self):
        config = (ROOT / "cfg/8502-scheduler-overlay.cfg").read_text(
            encoding="utf-8"
        )
        self.assertIn("PAGE: start = $1C00, size = $0400", config)
        self.assertIn("TAIL: start = $C120, size = $0DE0", config)
        self.assertIn('file = "build/8502/udeks-scheduler-overlay-tail.bin"', config)


if __name__ == "__main__":
    unittest.main()
