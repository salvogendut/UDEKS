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

static void storage_command(const char *line, unsigned expected_exit) {
    idle();
    unsigned before = byte(0xf17e);
    for (const char *p = line; *p; ++p) {
        if (*p == '/') key(SDL_SCANCODE_SLASH);
        else if (*p >= '1' && *p <= '9') key(SDL_SCANCODE_1 + *p - '1');
        else if (*p == '0') key(SDL_SCANCODE_0);
        else { char letter[2] = {*p, 0}; text(letter); }
    }
    key(SDL_SCANCODE_RETURN);
    wait_byte(0xf17e, (before + 1) & 255, "resident command not complete");
    idle();
    printf("command %s: ", line); diagnostic();
    for (unsigned row = 0; row < 21; ++row)
        printf("%.*s\n", 64, (char *)&machine->mem.ram[0xc00 + row * 65]);
    require(byte(0xf285) == 3 && byte(0xf287) == expected_exit,
            "unexpected command exit status");
}

int main(int argc, char **argv) {
    require(argc == 5, "usage: storage-smoke ROMDIR DISK SLOTADDR SNAPSHOT");
    Config config;
    config_set_defaults(&config);
    config.col_mode_80 = true;
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
    storage_command("ls /bin", 0);
    storage_command("mount 8 /mnt", 0);
    storage_command("ls /mnt", 0);
    storage_command("cat /mnt/hello", 0);
    require(console_contains("HELLO UDEKS"), "file contents missing");
    storage_command("cat /mnt/empty", 0);
    storage_command("cat /mnt/one", 0);
    require(console_contains("X"), "one-byte file missing");
    storage_command("cat /mnt/nofile", 1);
    storage_command("cat /mnt/hello", 0);
    storage_command("umount /mnt", 0);
    storage_command("ls /bin", 0);
    require(drive_attach_disk(&machine->drive, NULL) == 0, "remove disk");
    storage_command("mount 8 /mnt", 1);
    storage_command("ls /bin", 0);
    require(drive_attach_disk(&machine->drive, argv[2]) == 0, "reinsert disk");
    storage_command("mount 8 /mnt", 0);
    storage_command("cat /mnt/hello", 0);
    require(console_contains("HELLO UDEKS"), "reinserted file missing");
    storage_command("umount /mnt", 0);
    require(snapshot_save(machine, snapshot_path) == SNAPSHOT_OK, "save evidence");
    require(drive_attach_disk(&machine->drive, NULL) == 0, "detach disk copy");
    puts("PASS native 1986 raw-IEC mount/list/tiny-file/error/media-recovery/unmount");
    free(machine);
    return 0;
}
