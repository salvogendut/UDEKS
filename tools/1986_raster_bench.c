/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Raw standalone probe runner. No ROM, UDEKS disk or emulator edits needed. */
#include "c128.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int g_debug_enabled;
int main(int argc, char **argv)
{
    if (argc != 3) return 2;
    FILE *input = fopen(argv[1], "rb");
    if (!input) return 2;
    unsigned char image[0x5002];
    size_t size = fread(image, 1, sizeof image, input);
    int extra = fgetc(input); fclose(input);
    if (size < 3 || extra != EOF || image[0] != 0 || image[1] != 0x20) return 2;
    Config config; config_set_defaults(&config);
    config.notify_mode = NOTIFY_MODE_CONSOLE;
    C128 *machine = calloc(1, sizeof *machine);
    if (!machine) return 2;
    c128_init(machine, &config);
    c128_power_cycle(machine);
    memcpy(machine->mem.ram + 0x2000, image + 2, size - 2);
    c128_mem_write(machine, 0xff00, 0x3e);
    c128_mem_write(machine, 0xd505, machine->mem.mmu.mcr5 | 1);
    cpu_pc(&machine->cpu, 0x2000);
    unsigned frames = 0;
    while (machine->mem.ram[0x7fc5] != 2 && frames < 4000) {
        c128_frame(machine); ++frames;
    }
    if (machine->mem.ram[0x7fc5] != 2 || memcmp(machine->mem.ram + 0x7fc0, "RAST", 4)) {
        fprintf(stderr, "raster timeout: PC=%04X state=%u\n", machine->cpu.pc, machine->mem.ram[0x7fc5]);
        return 1;
    }
    FILE *output = fopen(argv[2], "wb");
    if (!output) return 2;
    size_t written = fwrite(machine->mem.ram + 0x7fc0, 1, 8096, output);
    int failed = fclose(output);
    if (written != 8096 || failed) return 2;
    printf("%s: completed in %u PAL frames (timer count in result)\n", argv[1], frames);
    return 0;
}
