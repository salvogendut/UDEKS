/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native boot/input diagnostic against the sibling's unmodified raw IEC core. */
#define main input_smoke_main
#include "1986_input_smoke.c"
#undef main

static bool console_contains(const char *text) {
    for (unsigned row = 0; row < 21; ++row)
        if (strstr((char *)&machine->mem.ram[0xc00 + row * 65], text)) return true;
    return false;
}

static void diagnostic(void) {
    Drive1571Cr *d = &machine->integrated_drive;
    printf("PC=%04X drive=%04X jam=%u speed=%u CIA2=%02X/%02X "
           "bus=%d%d%d via=%02X/%02X request=%02X/%02X/%02X exit=%u\n",
           machine->cpu.pc, d->cpu.pc, d->cpu.jammed, d->clock_2mhz,
           machine->cia2.pra, machine->cia2.ddra,
           machine->iec_bus.atn_high, machine->iec_bus.clock_high,
           machine->iec_bus.data_high, d->via1.orb, d->via1.ddrb,
           byte(0xf35f), byte(0xf360), byte(0xf365), byte(0xf287));
    fflush(stdout);
}

static void storage_result(const char *line, unsigned expected_exit, unsigned error) {
    idle();
    unsigned before = byte(0xf17e);
    for (const char *p = line; *p; ++p) {
        if (*p == '/') key(SDL_SCANCODE_SLASH);
        else if (*p >= '1' && *p <= '9') key(SDL_SCANCODE_1 + *p - '1');
        else if (*p == '0') key(SDL_SCANCODE_0);
        else { char letter[2] = {*p, 0}; text(letter); }
    }
    key(SDL_SCANCODE_RETURN);
    if (error) wait_byte(0xf17a, error, "loader rejection missing");
    else wait_byte(0xf17e, (before + 1) & 255, "resident command not complete");
    idle();
    printf("command %s: ", line); diagnostic();
    for (unsigned row = 0; row < 21; ++row)
        printf("%.*s\n", 64, (char *)&machine->mem.ram[0xc00 + row * 65]);
    require(byte(0xf286) == error && byte(0xf285) == (error ? 0x80 | error : 3),
            "unexpected loader status");
    if (!error) require(byte(0xf287) == expected_exit, "unexpected command exit status");
}
static void storage_command(const char *line, unsigned expected_exit) {
    storage_result(line, expected_exit, 0);
}

#ifdef UDEKS_DISK_GRAPHICS_SMOKE
static void window_gesture(unsigned x, unsigned y, unsigned dx, unsigned dy) {
    unsigned starts = word(0xf258), finishes = word(0xf25a);
    pointer_to(x, y);
    joyports_mouse_button(&machine->joyports, 0, false, true);
    for (unsigned n = 0; n < 10000 &&
         (word(0xf258) == starts || !byte(0xf248)); ++n) frames(1);
    require(word(0xf258) == starts+1 && byte(0xf248), "window gesture did not start");
    pointer_to(dx, dy);
    joyports_mouse_button(&machine->joyports, 0, false, false);
    for (unsigned n = 0; n < 10000 &&
         (word(0xf25a) == finishes || byte(0xf248)); ++n) frames(1);
    require(word(0xf25a) == finishes+1 && !byte(0xf248), "window gesture did not finish");
    frames(500);
}

static void disk_graphics(void) {
    command("xinit"); idle();
    command("xclock &"); idle();
    require(byte(0xf225) == 3, "disk clock did not start");
    unsigned clock_handle = byte(0xf247);
    window_gesture(150, 106, 110, 86);
    require(byte(0xf228) < 100 && byte(0xf229) < 50, "clock did not move");
    unsigned x = byte(0xf228), y = byte(0xf229);
    unsigned w = byte(0xf22a), h = byte(0xf22b);
    /* The window manager subtracts pointer biases 12,40. */
    window_gesture(x+w+7, y+h+35, x+w+25, y+h+47);
    require(byte(0xf22a) > w && byte(0xf22b) > h, "clock did not resize");
    command("xwave");
    wait_byte(0xf265, 3, "disk foreground wave did not start");
    c128_key_event(machine, SDL_SCANCODE_LCTRL, true);
    key(SDL_SCANCODE_C);
    c128_key_event(machine, SDL_SCANCODE_LCTRL, false);
    wait_byte(0xf265, 2, "foreground Ctrl+C did not stop disk wave"); idle();
    require(byte(0xf225) == 3, "Ctrl+C stopped background clock");
    command("xwave &"); idle();
    wait_byte(0xf27a, 21, "wave did not finish");
    unsigned wave_handle = byte(0xf247);
    require(wave_handle != clock_handle, "wave did not become focused");
    window_gesture(166, 132, 142, 104);
    require(byte(0xf274) < 130, "wave did not move");
    wait_byte(0xf27a, 21, "wave did not repaint after move");
    /* Switch both ways with real clicks in exposed title bars. */
    x = byte(0xf228); y = byte(0xf229);
    pointer_to(x+22, y+46);
    joyports_mouse_button(&machine->joyports, 0, false, true); frames(80);
    joyports_mouse_button(&machine->joyports, 0, false, false); frames(500);
    require(byte(0xf247) == clock_handle, "clock focus click failed");
    pointer_to(byte(0xf274)+92, byte(0xf275)+46);
    joyports_mouse_button(&machine->joyports, 0, false, true); frames(80);
    joyports_mouse_button(&machine->joyports, 0, false, false); frames(500);
    require(byte(0xf247) == wave_handle, "wave focus click failed");
    command("cowsay both alive"); idle();
    require(console_contains("both alive"), "console with both apps failed");
    command("xclock -q"); idle(); require(byte(0xf225) == 2, "clock stop failed");
    command("xwave -q"); idle(); require(byte(0xf265) == 2, "wave stop failed");
    command("xclock &"); idle(); require(byte(0xf225) == 3, "clock restart failed");
    command("xwave &"); idle(); require(byte(0xf265) == 3, "wave restart failed");
    require(byte(0xf11b) == 0, "lifecycle canary failure");
    puts("PASS disk graphics: load both, drag/resize clock, Ctrl+C wave, drag/focus, console, stop/restart");
}
#ifdef UDEKS_DRAG_REGRESSION
static void window_border(unsigned x, unsigned y, unsigned width, unsigned height) {
    unsigned missing = 0;
    for (unsigned yy = y; yy < y+height; ++yy)
        for (unsigned xx = x; xx < x+width; ++xx) {
            if (xx != x && xx != x+width-1 && yy != y && yy != y+height-1) continue;
            unsigned offset = (yy/8)*320 + (xx/8)*8 + (yy%8);
            if (!(byte(0x16000+offset) & (128 >> (xx%8)))) ++missing;
        }
    printf("border %u,%u %ux%u: %u missing pixels\n", x, y, width, height, missing);
    fflush(stdout);
    require(!missing, "focused window border was clipped or lost");
}

static void drag_regression(void) {
#ifdef UDEKS_BOOT_MOUNT_SMOKE
    wait_byte(0xf3e0, 2, "default startup did not finish");
    require(!console_contains("mount: failed"), "default startup mount failed");
#else
    storage_command("mount 8 /mnt", 0);
#endif
    storage_command("uname -a", 0);
    command("z80ctl test"); idle();
    require(console_contains("Z80 self-test: OK"), "engine control did not finish");
    command("xclock &"); idle();
    require(byte(0xf225) == 3, "implicit desktop clock did not start");
    for (unsigned i = 0; i < 12; ++i) {
        unsigned x = byte(0xf228), y = byte(0xf229);
        unsigned next_x = (i * 37 + 24) % 176;
        unsigned next_y = (i * 17 + 16) % 96;
        printf("drag %u from %u,%u to %u,%u clip-code=$%02X\n",
               i, x, y, next_x, next_y, byte(0x8000)); fflush(stdout);
        window_gesture(x+22, y+46, next_x+22, next_y+46);
        require(abs((int)byte(0xf228) - (int)next_x) <= 1 &&
                abs((int)byte(0xf229) - (int)next_y) <= 1,
                "clock geometry did not follow drag");
        window_border(byte(0xf228), byte(0xf229), byte(0xf22a), byte(0xf22b));
    }
    command("xwave &"); idle();
    wait_byte(0xf27a, 21, "wave did not finish after clock drags");
    require(byte(0xf246) == 2, "both windows must exist");
    window_border(byte(0xf274), byte(0xf275), byte(0xf276), byte(0xf277));
    window_gesture(byte(0xf274)+22, byte(0xf275)+46, 42, 66);
    window_border(byte(0xf274), byte(0xf275), byte(0xf276), byte(0xf277));
    command("cowsay hello"); idle();
    require(console_contains("hello") && console_contains("^__^"), "console after drags failed");
    require(snapshot_save(machine, snapshot_path) == SNAPSHOT_OK, "save drag regression evidence");
    puts("PASS reported sequence: implicit desktop, repeated clock drag, wave drag, cowsay");
}
#endif
#endif

int main(int argc, char **argv) {
    require(argc == 5, "usage: storage-smoke ROMDIR DISK SLOTADDR SNAPSHOT");
    Config config;
    config_set_defaults(&config);
    config.col_mode_80 = true;
    config.joy_port_mode[0] = JOYPORT_MOUSE;
    config.joy_port_mode[1] = JOYPORT_JOYSTICK;
    config.real_disk_drive = true;
    config.notify_mode = NOTIFY_MODE_CONSOLE;
    machine = calloc(1, sizeof(*machine));
    require(machine != NULL, "allocate emulator");
    slots = strtoul(argv[3], NULL, 0);
    snapshot_path = argv[4];
    c128_init(machine, &config);
    require(mem_load_c128_roms(&machine->mem, argv[1]) != 0, "load C128 ROMs");
    char rom[1024];
    snprintf(rom, sizeof(rom), "%s/dos1571cr.bin", argv[1]);
    require(drive1571cr_load_rom(&machine->integrated_drive, rom), "load drive ROM");
    require(drive_attach_disk(&machine->drive, argv[2]) == 0, "attach disk copy");
    machine->col_mode_80 = true;
    c128_power_cycle(machine);
    machine->drive_raw_iec = true; /* Same mode as main.c, no ROM traps. */
    for (unsigned n = 0; n < 30000 && byte(0xf3d9) != 0xa5; ++n) {
        frames(1);
        if (!(n % 2500)) diagnostic();
    }
    diagnostic();
    require(byte(0xf3d9) == 0xa5, "native raw-IEC boot failed");
#ifdef UDEKS_DRAG_REGRESSION
    drag_regression();
    free(machine);
    return 0;
#endif
#ifdef UDEKS_SYSINFO_SMOKE
    wait_byte(0xf3e0, 2, "startup script did not finish");
    require(!console_contains("RC failed"), "default startup script failed");
#endif
#ifdef UDEKS_DISK_SHELL_SMOKE
    require(byte(0xf3dd) == 1 && byte(0xf3de) == 0 && byte(0xf3df) == 8,
            "shell was not loaded from boot-device disk");
    idle();
    unsigned shell_before = byte(0xf3d8);
    text("help\n");
    wait_byte(0xf3d8, (shell_before+1) & 255, "shell builtin was not accepted");
    idle();
    require(console_contains("Recovery: mount umount"), "disk shell help failed");
    puts("PASS native disk shell source=1 error=0 device=8, help works");
#endif
    /* The normal RC now owns this mount. Keep explicit mount tests below
     * independent of the default policy, after proving RC completed. */
    wait_byte(0xf3e0, 2, "startup did not finish");
    storage_command("umount /mnt", 0);
    storage_command("mount 8 /mnt", 0);
    storage_command("ls /bin", 0);
    storage_command("ls /mnt", 0);
#ifdef UDEKS_SYSINFO_SMOKE
    storage_command("free", 0);
    require(console_contains("total 2560  used 0  free 2560"), "free accounting missing");
    storage_command("df", 0);
    require(console_contains("iec8") && console_contains("Read-only mount"), "df output missing");
    storage_command("df /bad", 1);
    require(console_contains("usage: df [/mnt]"), "df usage missing");
#endif
#ifdef UDEKS_DISK_EXEC_SMOKE
    storage_command("/mnt/diskcow hello", 0);
    require(console_contains("hello") && console_contains("^__^"), "disk cow missing");
    storage_command("/mnt/diskcow again", 0);
    require(console_contains("again"), "disk arguments lost");
    storage_result("/mnt/badudex", 0, 4);
    storage_result("/mnt/short", 0, 9);
    storage_result("/mnt/nofile", 0, 11);
    storage_command("/mnt/entry", 37);
    storage_command("/mnt/limit", 7);
    storage_command("/mnt/diskcow recovered", 0);
    require(console_contains("recovered"), "disk recovery failed");
    storage_command("cowsay bootfs", 0);
    require(console_contains("bootfs"), "bootfs fallback failed");
#else
    storage_command("cat /mnt/hello", 0);
    require(console_contains("HELLO UDEKS"), "file contents missing");
    storage_command("cat /mnt/empty", 0);
    storage_command("cat /mnt/one", 0);
    require(console_contains("X"), "one-byte file missing");
    storage_command("cat /mnt/nofile", 1);
#endif
#ifdef UDEKS_DISK_GRAPHICS_SMOKE
    disk_graphics();
#endif
    storage_command("cat /mnt/hello", 0);
    storage_command("umount /mnt", 0);
    command("echo recovery alive"); idle();
    require(drive_attach_disk(&machine->drive, NULL) == 0, "remove disk");
    storage_command("mount 8 /mnt", 1);
    command("echo recovery alive"); idle();
    require(drive_attach_disk(&machine->drive, argv[2]) == 0, "reinsert disk");
    storage_command("mount 8 /mnt", 0);
    storage_command("cat /mnt/hello", 0);
    require(console_contains("HELLO UDEKS"), "reinserted file missing");
    storage_command("umount /mnt", 0);
    require(snapshot_save(machine, snapshot_path) == SNAPSHOT_OK, "save evidence");
    require(drive_attach_disk(&machine->drive, NULL) == 0, "detach disk copy");
#ifdef UDEKS_DISK_EXEC_SMOKE
    puts("PASS native 1986 raw-IEC disk execution/argv/entry/BSS/limit/rejection/recovery/bootfs");
#else
    puts("PASS native 1986 raw-IEC mount/list/tiny-file/error/media-recovery/unmount");
#endif
    free(machine);
    return 0;
}
