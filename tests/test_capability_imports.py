# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gen_capability_imports", ROOT / "tools/gen_capability_imports.py"
)
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)


class CanonicalizeTests(unittest.TestCase):
    def test_same_type_duplicates_collapse(self):
        got = gen.canonicalize(
            [("pusha", "02"), ("pusha", "02"), ("incsp2", "02"), ("ptr1", "01")]
        )
        self.assertEqual(got, [("incsp2", "02"), ("ptr1", "01"), ("pusha", "02")])

    def test_conflicting_types_are_rejected(self):
        with self.assertRaises(ValueError):
            gen.canonicalize([("pusha", "02"), ("pusha", "01")])

    def test_unsupported_address_size_is_rejected(self):
        with self.assertRaises(ValueError):
            gen.canonicalize([("pusha", "03")])

    def test_unsafe_symbol_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe symbol"):
            gen.canonicalize([("pusha;touch", "02")])

    def test_output_is_sorted_and_unique(self):
        got = gen.canonicalize([("sp", "01"), ("incsp6", "02"), ("sp", "01")])
        self.assertEqual(got, [("incsp6", "02"), ("sp", "01")])

    def test_contract_rejects_the_wrong_unique_count(self):
        with self.assertRaisesRegex(ValueError, "23 unique imports"):
            gen.validate_contract([("sp", "01")])

    def test_contract_rejects_the_wrong_type_split(self):
        imports = [(f"absolute{index}", "02") for index in range(22)]
        imports.append(("sp", "01"))
        with self.assertRaisesRegex(ValueError, "21 absolute/2 zero-page"):
            gen.validate_contract(imports)

    def test_force_flags_omit_zero_page_imports(self):
        got = gen.render_flags(
            [("absolute", "02"), ("ptr1", "01"), ("sp", "01")]
        )
        self.assertEqual(got, "-u absolute\n")

    def test_bridge_requires_normal_panic_address_and_type_parity(self):
        imports = [("absolute", "02"), ("sp", "01")]
        normal = {"absolute": (0x2345, "RLA"), "sp": (0x0006, "RLZ")}
        self.assertEqual(
            gen.resolve_bridge(imports, normal, dict(normal)),
            [("absolute", "02", 0x2345), ("sp", "01", 0x0006)],
        )
        panic = dict(normal)
        panic["absolute"] = (0x2346, "RLA")
        with self.assertRaisesRegex(ValueError, "normal/panic mismatch"):
            gen.resolve_bridge(imports, normal, panic)
        wrong_type = dict(normal)
        wrong_type["sp"] = (0x0006, "RLA")
        with self.assertRaisesRegex(ValueError, "map type"):
            gen.resolve_bridge(imports, wrong_type, wrong_type)

    def test_bridge_preserves_zero_page_exports_and_image_assertions(self):
        source = gen.render_bridge(
            [("absolute", "02", 0x2345), ("sp", "01", 0x0006)]
        )
        self.assertIn(".export absolute\nabsolute = $2345", source)
        self.assertIn(".exportzp sp\nsp = $0006", source)
        self.assertIn("_udeks_capability_start = $0200", source)
        self.assertIn("__CODE_SIZE__ = $03c7", source)
        self.assertIn("__BSS_RUN__ = $05c7", source)

    def test_constants_reject_normal_panic_shadow_mismatch(self):
        map_template = (
            "Exports list by name:\n---------------------\n"
            "__VICSHADOW_RUN__ {address:06X} RLA\n\n"
            "Exports list by value:\n----------------------\n"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "capability.bin"
            delivery = root / "boot-delivery.bin"
            normal = root / "normal.map"
            panic = root / "panic.map"
            image.write_bytes(bytes(0x03C7))
            delivery.write_bytes(bytes(0x010B))
            normal.write_text(
                map_template.format(address=0xA89E), encoding="utf-8"
            )
            panic.write_text(
                map_template.format(address=0xA89F), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "starts differ"):
                gen.write_constants(
                    str(image), str(delivery), str(normal), str(panic),
                    str(root / "out.inc"), str(root / "out.cfg"),
                )


if __name__ == "__main__":
    unittest.main()
