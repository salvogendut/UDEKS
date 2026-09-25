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
        self.assertIn(".byte $0b", table)

        descriptor = (ROOT / "src/services/display/descriptor.s").read_text(
            encoding="utf-8"
        )
        self.assertIn(".byte $03, $01", descriptor)
        self.assertIn(".addr _udeks_vic_graphics_start", descriptor)
        self.assertIn(".addr _udeks_vic_graphics_poll", descriptor)

    def test_transport_uses_reserved_bank1_window_and_common_gateway(self):
        source = (ROOT / "src/8502/vic_graphics.s").read_text(encoding="utf-8")
        for declaration in (
            "COMMON_GATEWAY          = $f68a",
            "VIC_SCREEN              = $5c00",
            "VIC_BITMAP              = $6000",
            "VIC_SPRITE_NORMAL       = $4100",
            "VIC_SPRITE_BUSY         = $4140",
            "VIC_SPRITE              = $7fc0",
            "VIC_SPRITE_POINTER      = $5ff8",
            "CPU_PORT                = $0001",
        ):
            self.assertIn(declaration, source)
        self.assertIn("sta MMU_LCR_WORKER_FLAT", source)
        self.assertIn("sta MMU_LCR_KERNEL_IO", source)
        self.assertIn("ora #$40", source)
        self.assertIn("and #$bf", source)
        self.assertIn("lda #$78", source)
        self.assertIn("lda #$3b", source)
        self.assertIn("VIC common gateway exceeds one-page installer", source)
        self.assertIn("_udeks_vic_bitmap_commit_page", source)
        self.assertIn("_udeks_vic_bitmap_outline_blit", source)
        self.assertIn("COMMON_BUFFER           = $f400", source)
        self.assertIn("OUTLINE_BUFFER          = $f380", source)
        self.assertIn("OUTLINE_GATEWAY_TAG     = $f3ed", source)
        self.assertIn("jmp _udeks_vic_buffer_restore", source)
        self.assertIn("cmp #$a5", source)
        self.assertIn("cmp #$1f", source)
        self.assertIn("outline_gateway:", source)
        self.assertIn("draw_horizontal:", source)
        self.assertIn("draw_vertical:", source)
        self.assertIn("sta $ffff", source)

        enable = source.split("_udeks_vic_graphics_enable:", 1)[1].split(
            "_udeks_vic_graphics_disable:", 1
        )[0]
        self.assertIn("sta saved_chargen_overlay", enable)
        self.assertIn("ora #$04", enable)
        self.assertIn("sta CPU_PORT", enable)
        self.assertLess(enable.index("and #$ef"), enable.index("ora #$04"))
        self.assertLess(enable.index("sta CPU_PORT"), enable.index("jsr COMMON_GATEWAY"))

        gateway_init = source.split("\nvic_gateway:", 1)[1].split(
            "\nsprite_data:", 1
        )[0]
        self.assertLess(gateway_init.index("and #$bf"), gateway_init.index("ora #$40"))
        self.assertLess(
            gateway_init.index("sta VIC_SPRITE_ENABLE"),
            gateway_init.index("sta VIC_CONTROL_1"),
        )
        self.assertLess(gateway_init.index("sei"), gateway_init.index("and #$bf"))
        self.assertGreater(gateway_init.index("plp"), gateway_init.index("sta VIC_CONTROL_1"))

        gateway = source.split("\noutline_gateway:", 1)[1].split(
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
        self.assertIn("start = $AF00", config)

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
        self.assertIn("_udeks_vic_pointer_select_shape", source)
        self.assertIn("sprite_data_end-sprite_data = 63", source)
        stage1 = (ROOT / "src/boot/stage1.s").read_text(encoding="utf-8")
        loader = (ROOT / "src/boot/stage1-gateway.s").read_text(
            encoding="utf-8"
        )
        self.assertIn('.incbin "build/assets/24x21-pipe-sprite.vic"', stage1)
        self.assertIn("busy_sprite_image_end-busy_sprite_image = 63", stage1)
        self.assertIn("BUSY_SPRITE_SOURCE      = $1fc0", loader)
        self.assertIn("VIC_BUSY_TEMPLATE       = $4140", loader)
        self.assertIn("sta VIC_BUSY_TEMPLATE,y", loader)
        self.assertIn("sprite_swap_gateway:", source)
        self.assertIn("sta VIC_SPRITE_NORMAL,x", source)
        self.assertIn("lda VIC_SPRITE_BUSY,x", source)
        shutdown = source.split("_udeks_vic_graphics_disable:", 1)[1]
        shutdown = shutdown.split("vic_gateway:", 1)[0]
        self.assertIn("and #$fe", shutdown)
        self.assertIn("and #$cf", shutdown)
        self.assertIn("and #$bf", shutdown)
        self.assertIn("and #$fb", shutdown)
        self.assertIn("sta CPU_PORT", shutdown)

        self.assertIn("_udeks_vic_pointer_busy_begin:", source)
        self.assertIn("_udeks_vic_pointer_busy_end:", source)
        self.assertIn("_udeks_vic_pointer_busy_tick:", source)
        self.assertIn("BUSY_HOLD_FRAMES        = $03", source)
        self.assertIn("cmp #BUSY_RELEASE_PENDING", source)
        self.assertIn("sta VIC_STATUS_POINTER_SHAPE", source)

        display = (ROOT / "src/services/display/vic_graphics.c").read_text(
            encoding="utf-8"
        )
        self.assertIn("udeks_vic_pointer_busy_tick();", display)

if __name__ == "__main__":
    unittest.main()
