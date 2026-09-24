# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VicGraphicsSourceTests(unittest.TestCase):
    def test_passive_service_starts_after_pointer_and_before_keyboard(self):
        table = (ROOT / "src/services/table.s").read_text(encoding="utf-8")
        console = table.index(".addr _udeks_console_service_descriptor")
        pointer = table.index(".addr _udeks_pointer_service_descriptor")
        graphics = table.index(".addr _udeks_vic_graphics_service_descriptor")
        keyboard = table.index(".addr _udeks_keyboard_service_descriptor")
        self.assertLess(console, pointer)
        self.assertLess(pointer, graphics)
        self.assertLess(graphics, keyboard)
        self.assertIn(".byte $0c", table)

        descriptor = (ROOT / "src/services/display/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte $03, $01", descriptor)
        self.assertIn(".addr _udeks_vic_graphics_start", descriptor)
        self.assertIn(".addr _udeks_vic_graphics_poll", descriptor)

    def test_transport_uses_reserved_bank1_window_and_common_gateway(self):
        source = (ROOT / "src/8502/vic_graphics.s").read_text(encoding="utf-8")
        for declaration in (
            "COMMON_GATEWAY          = $f800",
            "VIC_SCREEN              = $5c00",
            "VIC_BITMAP              = $6000",
            "VIC_SPRITE              = $7fc0",
            "VIC_SPRITE_POINTER      = $5ff8",
        ):
            self.assertIn(declaration, source)
        self.assertIn("sta MMU_LCR_WORKER_FLAT", source)
        self.assertIn("sta MMU_LCR_KERNEL_IO", source)
        self.assertIn("ora #$40", source)
        self.assertIn("lda #$78", source)
        self.assertIn("lda #$3b", source)
        self.assertIn("VIC common gateway exceeds one-page installer", source)
        self.assertIn("_udeks_vic_bitmap_commit_page", source)
        self.assertIn("_udeks_vic_bitmap_outline_blit", source)
        self.assertIn("COMMON_BUFFER           = $f900", source)
        self.assertIn("OUTLINE_BUFFER          = $fa00", source)
        self.assertIn("OUTLINE_GATEWAY_TAG     = $f7fe", source)
        self.assertIn("cmp #$a5", source)
        self.assertIn("cmp #$1f", source)
        self.assertIn("outline_gateway:", source)
        self.assertIn("draw_horizontal:", source)
        self.assertIn("draw_vertical:", source)
        self.assertIn("sta $ffff", source)

        gateway = source.split("outline_gateway:", 1)[1].split(
            "outline_gateway_end:", 1
        )[0]
        bare_jumps = re.findall(
            r"^\s+jmp\s+(?!COMMON_GATEWAY\+)[A-Za-z_]", gateway, re.MULTILINE
        )
        self.assertEqual(bare_jumps, [])

    def test_shadow_surface_is_aligned_and_commits_only_dirty_pages(self):
        source = (ROOT / "src/services/display/vic_graphics.c").read_text(
            encoding="utf-8"
        )
        config = (ROOT / "cfg/8502-bootstrap.cfg").read_text(encoding="utf-8")
        self.assertIn('bss-name(push, "VICSHADOW")', source)
        self.assertIn("udeks_vic_bitmap_shadow[8192]", source)
        self.assertIn("dirty_pages[pixel_offset >> 8] = 1", source)
        self.assertIn("udeks_vic_bitmap_commit_page(page)", source)
        self.assertIn("udeks_vic_bitmap_outline_toggle", source)
        self.assertIn("udeks_vic_bitmap_outline_move", source)
        self.assertIn("OUTLINE_RECORD_SIZE", source)
        self.assertIn("UDEKS_VIC_ROW_TABLE_BASE", source)
        rectangle = source.split("void udeks_vic_bitmap_rectangle", 1)[1].split(
            "void udeks_vic_bitmap_fill", 1
        )[0]
        self.assertIn("last_x = x + width - 1", rectangle)
        self.assertIn("last_y = y + height - 1", rectangle)
        self.assertIn("x, last_y, last_x, last_y", rectangle)
        fill = source.split("void udeks_vic_bitmap_fill", 1)[1].split(
            "void udeks_vic_bitmap_set_clip", 1
        )[0]
        self.assertIn("offset += 8u", fill)
        self.assertNotIn("for (column", fill)
        self.assertIn("VICSHADOW:", config)
        self.assertIn("align = $100", config)

    def test_display_module_does_not_drive_window_or_application_policy(self):
        source = (ROOT / "src/services/display/vic_graphics.c").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"udeks/window.h"', source)
        self.assertNotIn('"udeks/xclock.h"', source)
        self.assertNotIn("udeks_window_manager_poll", source)
        self.assertNotIn("udeks_xclock_poll", source)

    def test_pointer_is_black_centered_sprite_and_shutdown_is_bounded(self):
        source = (ROOT / "src/8502/vic_graphics.s").read_text(encoding="utf-8")
        self.assertIn("lda #$ac", source)
        self.assertIn("lda #$8c", source)
        self.assertIn("sta VIC_SPRITE0_COLOR", source)
        self.assertIn("_udeks_vic_pointer_set_x", source)
        self.assertIn("_udeks_vic_pointer_set_y", source)
        self.assertIn("sprite_data_end-sprite_data = 63", source)
        shutdown = source.split("_udeks_vic_graphics_disable:", 1)[1]
        shutdown = shutdown.split("vic_gateway:", 1)[0]
        self.assertIn("and #$fe", shutdown)
        self.assertIn("and #$cf", shutdown)
        self.assertIn("and #$bf", shutdown)


if __name__ == "__main__":
    unittest.main()
