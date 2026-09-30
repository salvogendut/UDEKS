# SPDX-License-Identifier: GPL-3.0-or-later

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_d71 import (
    BOOT_CONSOLE_INSTALLER_ADDRESS,
    BOOT_CONSOLE_SIZE,
    BUSY_SPRITE_ADDRESS,
    BUSY_SPRITE_SIZE,
    BOOT_DELIVERY_SIZE,
    BOOTFS_SIZE,
    BOOTFS_TAIL_STAGING_ADDRESS,
    BOOTFS_Z80_OFFSET,
    CAPABILITY_SIZE,
    CRT0_SIZE,
    CRT0_STAGING_ADDRESS,
    D64_SIZE,
    PROBE_SIZE,
    PROBE_STAGING_ADDRESS,
    BOOTFS_REQUEST_STAGING_ADDRESS,
    BOOTFS_REQUEST_STAGING_SIZE,
    MODULE_STAGING_ADDRESS,
    MODULE_STAGING_SIZE,
    PAYLOAD_BLOCKS,
    PAYLOAD_SIZE,
    SCATTER_MANIFEST_ADDRESS,
    SCHEDULER_TAIL_INSTALLER_SIZE,
    SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS,
    SECTOR_SIZE,
    TASK_LOADER_STAGING_ADDRESS,
    TASK_LOADER_STAGING_SIZE,
    TASK_BANK_GATE_STAGING_ADDRESS,
    TASK_BANK_GATE_STAGING_SIZE,
    TASK_REQUEST_STAGING_ADDRESS,
    TASK_REQUEST_STAGING_SIZE,
    TASK_SWITCH_ACTIVATION_SIZE,
    USH_ALLOCATION_SIZE,
    blank_d71,
    boot_locations,
    build_image,
    d64_compatibility_image,
    sector_offset,
    install_prg_file,
)
from build_bootfs import build_bootfs


def stage0() -> bytes:
    return b"CBM\x00\x1c\x00\xd4" + bytes(25)


def ush_executable(
    payload: bytes = b"shell-code", *, bss_size: int = 3, flags: int = 1
) -> bytes:
    return (
        b"UDEX" + bytes((0, 1, 1, flags)) + b"\x00\x90"
        + len(payload).to_bytes(2, "little")
        + bss_size.to_bytes(2, "little") + b"\x00\x90" + payload
    )


def bootfs_with_ush(executable: bytes) -> bytes:
    return build_bootfs([("cowsay", b"x"), ("ush", executable)])


class BuildD71Tests(unittest.TestCase):
    def test_ush_is_a_separate_raw_udex_on_both_formats(self):
        from disk_shell_fixture import shell_file
        program = ush_executable()
        image = build_image(stage0(), b'', b'', b'',
                            bootfs=bootfs_with_ush(program), ush=program)
        for view in (image, d64_compatibility_image(image)):
            _, offsets = shell_file(view)
            self.assertEqual(bytes(view[p] for p in offsets), program)

    def test_hello_is_raw_seq_without_prg_load_address_on_both_formats(self):
        data = b'HELLO UDEKS\n'
        image = build_image(stage0(), b'', b'', b'', hello=data)
        for view in (image, d64_compatibility_image(image)):
            entry = sector_offset(18, 1) + 2
            self.assertEqual(view[entry], 0x81)
            self.assertEqual(view[entry+3:entry+8], b'HELLO')
            offset = sector_offset(view[entry+1], view[entry+2])
            self.assertEqual(view[offset:offset+2], bytes((0, len(data)+1)))
            self.assertEqual(view[offset+2:offset+2+len(data)], data)

    def test_rejects_empty_prg_and_unsupported_file_type(self):
        for content, file_type in ((b'', 0x82), (b'x', 0x83)):
            with self.assertRaises(ValueError):
                install_prg_file(blank_d71(), 'BAD', content, file_type=file_type)

    def test_empty_seq_has_one_sector_with_zero_payload(self):
        image = blank_d71()
        install_prg_file(image, 'EMPTY', b'', file_type=0x81)
        entry = sector_offset(18, 1)+2
        offset = sector_offset(image[entry+1], image[entry+2])
        self.assertEqual(image[offset:offset+2], b'\0\1')
        self.assertEqual(image[entry+28:entry+30], b'\1\0')

    def test_blank_image_has_standard_size_and_directory(self):
        image = blank_d71()
        self.assertEqual(len(image), 349696)
        self.assertEqual(image[sector_offset(18, 1) : sector_offset(18, 1) + 2], b"\x00\xff")

    def test_d64_compatibility_image_is_standard_first_side(self):
        image = build_image(stage0(), b"", b"", b"")
        d64 = d64_compatibility_image(image)
        self.assertEqual(len(d64), D64_SIZE)
        self.assertEqual(d64[:4], b"CBM\x00")
        self.assertEqual(d64, image[:D64_SIZE])

    def test_d64_compatibility_image_rejects_nonstandard_source(self):
        with self.assertRaisesRegex(ValueError, "standard D71"):
            d64_compatibility_image(bytes(D64_SIZE))

    def test_side_one_prg_round_trips_through_directory_chain(self):
        image = bytearray(build_image(stage0(), b"", b"", b""))
        data = bytes(index & 0xFF for index in range(700))
        install_prg_file(image, "schedovr", data)
        directory = sector_offset(18, 1) + 2
        self.assertEqual(image[directory], 0x82)
        self.assertEqual(image[directory + 3 : directory + 11], b"SCHEDOVR")
        track = image[directory + 1]
        sector = image[directory + 2]
        result = bytearray()
        blocks = 0
        while track != 0:
            offset = sector_offset(track, sector)
            next_track = image[offset]
            next_sector = image[offset + 1]
            used = 254 if next_track else next_sector - 1
            result += image[offset + 2 : offset + 2 + used]
            track, sector = next_track, next_sector
            blocks += 1
        self.assertEqual(bytes(result), data)
        self.assertEqual(
            int.from_bytes(image[directory + 28 : directory + 30], "little"),
            blocks,
        )
        self.assertEqual(
            bytes(image[:D64_SIZE]), d64_compatibility_image(bytes(image))
        )

    def test_native_payload_round_trips_from_sequential_sectors(self):
        first = b"stage-one"
        kernel = b"kernel"
        z80 = b"z80"
        image = build_image(stage0(), first, kernel, z80)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        self.assertEqual(len(payload), PAYLOAD_SIZE)
        self.assertEqual(payload[: len(first)], first)
        self.assertEqual(payload[0x400 : 0x400 + len(kernel)], kernel)
        self.assertEqual(payload[0xB400 : 0xB400 + len(z80)], z80)

    def test_boot_blocks_are_reserved_in_bam(self):
        image = build_image(stage0(), b"", b"", b"")
        bam = sector_offset(18, 0)
        self.assertEqual(image[bam + 4], 0)
        self.assertEqual(image[bam + 8], 0)
        self.assertEqual(image[bam + 44], 18)

    def test_high_memory_module_is_packed_after_bootfs_data(self):
        module = b"module"
        image = build_image(stage0(), b"", b"", b"", module=module)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = MODULE_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(module)], module)

    def test_bootfs_is_packed_into_unused_z80_staging(self):
        bootfs = b"UBFS" + bytes(20)
        image = build_image(stage0(), b"", b"", b"", bootfs=bootfs)
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        z80 = payload[0xB400 : 0xB400 + 0x2000]
        self.assertEqual(
            z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + len(bootfs)],
            bootfs,
        )

    def test_persistent_ush_is_resolved_from_bootfs(self):
        executable = ush_executable()
        bootfs = bootfs_with_ush(executable)
        image = build_image(stage0(), b"", b"", b"", bootfs=bootfs,
                            ush=executable)
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        z80 = payload[0xB400 : 0xB400 + 0x2000]
        self.assertEqual(
            z80[BOOTFS_Z80_OFFSET : BOOTFS_Z80_OFFSET + len(bootfs)], bootfs
        )

    def test_ush_bootfs_validation_is_independent_of_directory_position(self):
        executable = ush_executable()
        bootfs = build_bootfs([
            ("aardvark", b"first"), ("cowsay", b"x"), ("ush", executable),
        ])
        build_image(stage0(), b"", b"", b"", bootfs=bootfs, ush=executable)

    def test_rejects_nonpersistent_ush(self):
        executable = ush_executable(b"x", bss_size=0, flags=0)
        with self.assertRaisesRegex(ValueError, "persistent-poll"):
            build_image(stage0(), b"", b"", b"",
                        bootfs=bootfs_with_ush(executable), ush=executable)

    def test_rejects_oversize_ush_allocation(self):
        executable = ush_executable(bytes(USH_ALLOCATION_SIZE), bss_size=1)
        with self.assertRaisesRegex(ValueError, "2560-byte"):
            build_image(stage0(), b"", b"", b"",
                        bootfs=bootfs_with_ush(executable), ush=executable)

    def test_task_request_gateway_is_staged_in_vic_shadow(self):
        gateway = b"request-gateway"
        image = build_image(
            stage0(), b"", b"", b"", task_request_gateway=gateway
        )
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_REQUEST_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(gateway)], gateway)

    def test_rejects_oversize_task_request_gateway(self):
        with self.assertRaisesRegex(ValueError, "265-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_request_gateway=bytes(TASK_REQUEST_STAGING_SIZE + 1),
            )

    def test_crt0_is_staged_below_bootfs_staging(self):
        crt0 = b"crt0-image"
        image = build_image(stage0(), b"", b"", b"", crt0=crt0)
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = CRT0_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(crt0)], crt0)
        self.assertLessEqual(
            CRT0_STAGING_ADDRESS + CRT0_SIZE, BOOTFS_TAIL_STAGING_ADDRESS
        )

    def test_probe_is_staged_below_crt0_staging(self):
        probe = b"probe-image"
        image = build_image(stage0(), b"", b"", b"", probe=probe)
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = PROBE_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(probe)], probe)
        self.assertLessEqual(
            PROBE_STAGING_ADDRESS + PROBE_SIZE, CRT0_STAGING_ADDRESS
        )

    def test_capability_and_installer_are_staged_at_shadow_start(self):
        shadow_start = 0xA895
        capability = bytes((index % 251) + 1 for index in range(CAPABILITY_SIZE))
        installer = b"capability-installer"
        image = build_image(
            stage0(), b"", b"", b"", capability=capability,
            capability_installer=installer, shadow_start=shadow_start,
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = shadow_start - 0x1C00
        self.assertEqual(payload[offset : offset + len(capability)], capability)
        self.assertEqual(
            payload[offset + len(capability) :][: len(installer)], installer
        )

    def test_capability_requires_exact_size_and_installer(self):
        with self.assertRaisesRegex(ValueError, "expected 967"):
            build_image(
                stage0(), b"", b"", b"", capability=b"short",
                capability_installer=b"installer", shadow_start=0xA895,
            )
        with self.assertRaisesRegex(ValueError, "installer is empty"):
            build_image(
                stage0(), b"", b"", b"",
                capability=bytes(CAPABILITY_SIZE), shadow_start=0xA895,
            )

    def test_capability_installer_cannot_reach_scheduler_manifest(self):
        installer_size = SCATTER_MANIFEST_ADDRESS - (0xA895 + CAPABILITY_SIZE) + 1
        with self.assertRaisesRegex(ValueError, "reaches the scheduler manifest"):
            build_image(
                stage0(), b"", b"", b"",
                capability=bytes(CAPABILITY_SIZE),
                capability_installer=bytes(installer_size),
                shadow_start=0xA895,
            )

    def test_scheduler_does_not_reuse_zero_tail_of_boot_console_installer(self):
        shadow_start = 0xA1E0
        boot_delivery = bytes(
            (index % 239) + 1 for index in range(BOOT_DELIVERY_SIZE)
        )
        capability = bytes((index % 251) + 1 for index in range(CAPABILITY_SIZE))
        capability_installer = bytes((index % 253) + 1 for index in range(102))
        boot_console = bytes((index % 249) + 1 for index in range(BOOT_CONSOLE_SIZE))
        # The real installer ends in a two-byte checksum that may legitimately
        # be zero.  Its complete linked extent must remain reserved anyway.
        boot_console_installer = b"I" * 97 + b"\x00\x00"
        scheduler = bytes((index % 247) + 1 for index in range(297))
        image = build_image(
            stage0(), b"", b"", b"", scheduler=scheduler,
            shadow_start=shadow_start, capability=capability,
            capability_installer=capability_installer,
            boot_console=boot_console,
            boot_console_installer=boot_console_installer,
            boot_delivery=boot_delivery,
        )

        boot_sector = image[:SECTOR_SIZE]
        installer_offset = BOOT_CONSOLE_INSTALLER_ADDRESS - 0x0B00
        installer_end = installer_offset + len(boot_console_installer)
        self.assertEqual(
            boot_sector[installer_offset:installer_end],
            boot_console_installer,
        )

        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        manifest_offset = SCATTER_MANIFEST_ADDRESS - 0x1C00
        manifest = payload[manifest_offset : manifest_offset + 39]
        self.assertEqual(manifest[:4], b"USCT")
        chunks = []
        for index in range(manifest[4]):
            offset = 7 + index * 4
            start = int.from_bytes(manifest[offset : offset + 2], "little")
            length = int.from_bytes(manifest[offset + 2 : offset + 4], "little")
            chunks.append((start, length))

        installer_first = BOOT_CONSOLE_INSTALLER_ADDRESS
        installer_last = installer_first + len(boot_console_installer) - 1
        for start, length in chunks:
            last = start + length - 1
            self.assertTrue(last < installer_first or start > installer_last)
        boot_chunks = [chunk for chunk in chunks if chunk[0] < 0x0C00]
        self.assertEqual(boot_chunks[0][0], installer_last + 1)

        delivery_offset = shadow_start - 0x1C00
        self.assertEqual(
            payload[delivery_offset : delivery_offset + len(boot_delivery)],
            boot_delivery,
        )
        capability_offset = delivery_offset + len(boot_delivery)
        self.assertEqual(
            payload[capability_offset : capability_offset + len(capability)],
            capability,
        )

    def test_activation_is_staged_immediately_after_the_console(self):
        shadow_start = 0xA1E0
        console = bytes([0x66]) * BOOT_CONSOLE_SIZE
        activation = bytes([0x77]) * TASK_SWITCH_ACTIVATION_SIZE
        image = build_image(
            stage0(), b"", b"", b"", shadow_start=shadow_start,
            boot_console=console, task_activation=activation,
            boot_console_installer=b"I",
        )
        payload = b"".join(
            image[sector_offset(track, sector):sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = shadow_start - 0x1C00
        self.assertEqual(payload[offset:offset + len(console)], console)
        self.assertEqual(
            payload[offset + len(console):offset + len(console) + len(activation)],
            activation,
        )

    def test_rejects_oversize_probe(self):
        with self.assertRaisesRegex(ValueError, "256-byte"):
            build_image(
                stage0(), b"", b"", b"", probe=bytes(PROBE_SIZE + 1)
            )

    def test_rejects_probe_staging_collision(self):
        kernel = bytes(PROBE_STAGING_ADDRESS - 0x2000) + b"x"
        with self.assertRaisesRegex(ValueError, "probe staging overlaps"):
            build_image(stage0(), b"", kernel, b"", probe=b"p")

    def test_rejects_oversize_crt0(self):
        with self.assertRaisesRegex(ValueError, "256-byte"):
            build_image(
                stage0(), b"", b"", b"", crt0=bytes(CRT0_SIZE + 1)
            )

    def test_rejects_crt0_staging_collision(self):
        kernel = bytes(CRT0_STAGING_ADDRESS - 0x2000) + b"x"
        with self.assertRaisesRegex(ValueError, "crt0 staging overlaps"):
            build_image(stage0(), b"", kernel, b"", crt0=b"c")

    def test_task_loader_is_staged_in_reclaimable_vic_shadow(self):
        loader = b"task-loader"
        image = build_image(
            stage0(), b"", b"", b"", task_loader=loader
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_LOADER_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(loader)], loader)

    def test_rejects_module_staging_collision(self):
        bootfs = bytes(BOOTFS_SIZE - MODULE_STAGING_SIZE) + b"x"
        with self.assertRaisesRegex(ValueError, "overlaps bootfs"):
            build_image(stage0(), b"", b"", b"", bootfs=bootfs, module=b"m")

    def test_rejects_oversize_module(self):
        with self.assertRaisesRegex(ValueError, "836-byte"):
            build_image(
                stage0(), b"", b"", b"",
                module=bytes(MODULE_STAGING_SIZE + 1),
            )

    def test_rejects_oversize_bootfs(self):
        with self.assertRaisesRegex(ValueError, "12544-byte"):
            build_image(
                stage0(), b"", b"", b"", bootfs=bytes(BOOTFS_SIZE + 1)
            )

    def test_rejects_oversize_task_loader(self):
        with self.assertRaisesRegex(ValueError, "1520-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_loader=bytes(TASK_LOADER_STAGING_SIZE + 1),
            )

    def test_bootfs_request_service_is_staged_in_vic_shadow(self):
        service = b"bootfs-request-service"
        image = build_image(
            stage0(), b"", b"", b"", bootfs_request_service=service
        )
        payload = b"".join(
            image[sector_offset(track, sector) : sector_offset(track, sector) + SECTOR_SIZE]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = BOOTFS_REQUEST_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(service)], service)

    def test_rejects_oversize_bootfs_request_service(self):
        with self.assertRaisesRegex(ValueError, "785-byte"):
            build_image(
                stage0(), b"", b"", b"",
                bootfs_request_service=bytes(BOOTFS_REQUEST_STAGING_SIZE + 1),
            )

    def test_task_bank_gateway_is_staged_below_syscall_page(self):
        gateway = b"UTG1" + bytes(12)
        image = build_image(
            stage0(), b"", b"", b"", task_bank_gateway=gateway
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = TASK_BANK_GATE_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(gateway)], gateway)

    def test_rejects_oversize_task_bank_gateway(self):
        with self.assertRaisesRegex(ValueError, "192-byte"):
            build_image(
                stage0(), b"", b"", b"",
                task_bank_gateway=bytes(TASK_BANK_GATE_STAGING_SIZE + 1),
            )

    def test_scheduler_tail_installer_is_staged_in_the_request_gap(self):
        installer = bytes((index % 255) + 1 for index in range(
            SCHEDULER_TAIL_INSTALLER_SIZE
        ))
        image = build_image(
            stage0(), b"", b"", b"", scheduler_tail_installer=installer
        )
        payload = b"".join(
            image[
                sector_offset(track, sector) :
                sector_offset(track, sector) + SECTOR_SIZE
            ]
            for track, sector in list(boot_locations(1 + PAYLOAD_BLOCKS))[1:]
        )
        offset = SCHEDULER_TAIL_INSTALLER_STAGING_ADDRESS - 0x1C00
        self.assertEqual(payload[offset : offset + len(installer)], installer)

    def test_scheduler_tail_installer_requires_the_exact_gate_size(self):
        with self.assertRaisesRegex(ValueError, "expected 192"):
            build_image(
                stage0(), b"", b"", b"",
                scheduler_tail_installer=bytes(
                    SCHEDULER_TAIL_INSTALLER_SIZE - 1
                ),
            )

    def test_busy_sprite_is_staged_after_the_boot_console_installer(self):
        sprite = bytes((index % 255) + 1 for index in range(BUSY_SPRITE_SIZE))
        image = build_image(stage0(), b"", b"", b"", busy_sprite=sprite)
        sector = image[sector_offset(1, 0) : sector_offset(1, 0) + SECTOR_SIZE]
        offset = BUSY_SPRITE_ADDRESS - 0x0B00
        self.assertEqual(sector[offset : offset + len(sprite)], sprite)

    def test_busy_sprite_requires_exactly_63_bytes(self):
        with self.assertRaisesRegex(ValueError, "expected 63"):
            build_image(
                stage0(), b"", b"", b"",
                busy_sprite=bytes(BUSY_SPRITE_SIZE - 1),
            )

    def test_rejects_header_layout_drift(self):
        bad = bytearray(stage0())
        bad[6] = 211
        with self.assertRaisesRegex(ValueError, "block count"):
            build_image(bytes(bad), b"", b"", b"")


if __name__ == "__main__":
    unittest.main()
