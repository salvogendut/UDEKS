.export __SERVICEBOOT_RUN__ = $93d0, __SERVICEBOOT_SIZE__: absolute = $0000
.segment "CODE"
test_trap: brk
.export _udeks_banked_graphics_installed = test_trap
.export _udeks_banked_graphics_request = test_trap
.export _udeks_line_editor_read = test_trap
.export _udeks_root_terminal_prompt = test_trap
.export _udeks_root_terminal_write_request = test_trap
.export _udeks_service_control_request = test_trap
.export _udeks_shell_command_line = test_trap
.export _udeks_shell_foreground_job = test_trap
.export _udeks_stream_write = test_trap
.export _udeks_stream_write_byte = test_trap
.export _udeks_task_worker_request = test_trap
.export _udeks_terminal_input_access = test_trap
.export _udeks_time_now = test_trap
.export _udeks_time_slot_control = test_trap
.export _udeks_time_slot_reset = test_trap
.export _udeks_time_slot_set = test_trap
.export _udeks_time_slot_state = test_trap
.export _udeks_vic_bitmap_fill = test_trap
.export _udeks_vic_bitmap_line = test_trap
.export _udeks_vic_bitmap_pixel = test_trap
.export _udeks_vic_graphics_is_active = test_trap
.export _udeks_window_begin_paint = test_trap
.export _udeks_window_create = test_trap
.export _udeks_window_destroy = test_trap
.export _udeks_window_end_paint = test_trap
.export _udeks_window_get_geometry = test_trap
.export _udeks_window_image_complete = test_trap
.export _udeks_window_is_dragging = test_trap
.export _udeks_window_is_focused = test_trap
.export _udeks_window_repaint = test_trap
.export _udeks_window_take_click = test_trap
.export _udeks_z80_submit = test_trap
