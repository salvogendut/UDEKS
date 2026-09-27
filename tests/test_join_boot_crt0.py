# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from join_boot_crt0 import (  # noqa: E402
    CAPABILITY_ADDRESS,
    CAPABILITY_BSS_SIZE,
    CAPABILITY_SIZE,
    CRT0_ADDRESS,
    CRT0_SIZE,
    INSTALLER_ADDRESS,
    INSTALLER_OFFSET,
    INSTALLER_SIZE,
    KERNEL_ADDRESS,
    PROBE_ADDRESS,
    PROBE_SIZE,
    SCHEDULER_ADDRESS,
    SCHEDULER_SIZE,
    join,
)


def gateway_image() -> bytes:
    gateway = bytearray(757)
    gateway[INSTALLER_OFFSET : INSTALLER_OFFSET + INSTALLER_SIZE] = (
        bytes([0x11]) * INSTALLER_SIZE
    )
    return bytes(gateway)


class JoinBootCrt0Tests(unittest.TestCase):
    def test_join_places_every_delivery_page(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            capability = bytes([0x55]) * CAPABILITY_SIZE
            probe = bytes([0x11]) * PROBE_SIZE
            scheduler = bytes([0x22]) * 8
            crt0 = bytes([0x33]) * CRT0_SIZE
            kernel = bytes([0x44]) * 16
            destination = root / "direct.bin"

            join(
                capability, probe, scheduler, crt0, kernel, gateway_image(),
                destination,
            )

            image = destination.read_bytes()
            self.assertEqual(
                len(image),
                INSTALLER_ADDRESS - CAPABILITY_ADDRESS + INSTALLER_SIZE,
            )
            self.assertEqual(image[:CAPABILITY_SIZE], capability)
            self.assertEqual(
                image[CAPABILITY_SIZE : CAPABILITY_SIZE + CAPABILITY_BSS_SIZE],
                bytes(CAPABILITY_BSS_SIZE),
            )
            probe_offset = PROBE_ADDRESS - CAPABILITY_ADDRESS
            self.assertEqual(image[probe_offset : probe_offset + PROBE_SIZE], probe)
            scheduler_offset = SCHEDULER_ADDRESS - CAPABILITY_ADDRESS
            self.assertEqual(
                image[scheduler_offset : scheduler_offset + 8], scheduler
            )
            crt0_offset = CRT0_ADDRESS - CAPABILITY_ADDRESS
            self.assertEqual(image[crt0_offset : crt0_offset + CRT0_SIZE], crt0)
            self.assertEqual(
                image[KERNEL_ADDRESS - CAPABILITY_ADDRESS :][:16], kernel
            )
            installer_offset = INSTALLER_ADDRESS - CAPABILITY_ADDRESS
            self.assertEqual(
                image[installer_offset : installer_offset + INSTALLER_SIZE],
                bytes([0x11]) * INSTALLER_SIZE,
            )

    def test_rejects_oversize_scheduler(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "1024-byte"):
                join(
                    bytes(CAPABILITY_SIZE),
                    bytes(PROBE_SIZE),
                    bytes(SCHEDULER_SIZE + 1),
                    bytes(CRT0_SIZE),
                    b"\x44",
                    gateway_image(),
                    root / "direct.bin",
                )

    def test_rejects_empty_kernel(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "empty"):
                join(
                    bytes(CAPABILITY_SIZE),
                    bytes(PROBE_SIZE),
                    bytes(8),
                    bytes(CRT0_SIZE),
                    b"",
                    gateway_image(),
                    root / "direct.bin",
                )

    def test_rejects_wrong_capability_size(self):
        with TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "expected 967"):
                join(
                    bytes(CAPABILITY_SIZE - 1),
                    bytes(PROBE_SIZE),
                    bytes(8),
                    bytes(CRT0_SIZE),
                    b"\x44",
                    gateway_image(),
                    Path(directory) / "direct.bin",
                )


if __name__ == "__main__":
    unittest.main()
