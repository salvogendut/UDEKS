/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Isolated 1986 runner; no media attached and no sibling source changes. */
#include "c128.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int g_debug_enabled;
int main(int argc, char **argv)
{
    if (argc != 4) return 2;
    unsigned mode = (unsigned)strtoul(argv[3], NULL, 0);
    if (mode != 0 && mode != 64) return 2;
    FILE *input = fopen(argv[1], "rb");
    if (!input) return 2;
    unsigned char image[0x1802];
    size_t size = fread(image, 1, sizeof image, input);
    int extra = fgetc(input); fclose(input);
    if (size < 3 || extra != EOF || image[0] != 0 || image[1] != 0x28) return 2;
    Config config; config_set_defaults(&config);
    config.notify_mode = NOTIFY_MODE_CONSOLE;
    C128 *machine = calloc(1, sizeof *machine);
    if (!machine) return 2;
    c128_init(machine, &config);
    c128_power_cycle(machine);
    memcpy(machine->mem.ram + 0x2800, image + 2, size - 2);
    machine->mem.ram[0x70f0] = mode;
    c128_mem_write(machine, 0xff00, 0x3e);
    c128_mem_write(machine, 0xd505, machine->mem.mmu.mcr5 | 1);
    cpu_pc(&machine->cpu, 0x2800);
    unsigned frames;
    for (frames = 0; frames < 300; ++frames) {
        c128_frame(machine);
        if (!memcmp(machine->mem.ram+0x7000, "SWIN", 4) &&
            (machine->mem.ram[0x7005] == 2 || machine->mem.ram[0x7005] == 0x80)) break;
    }
    if (frames == 300) {
        fprintf(stderr, "window timeout PC=%04X state=%u\n", machine->cpu.pc, machine->mem.ram[0x7005]);
        return 1;
    }
    FILE *output = fopen(argv[2], "wb");
    if (!output) return 2;
    size_t written = fwrite(machine->mem.ram+0x7000, 1, 32, output);
    int error = fclose(output);
    printf("window: %u frames, state=%u\n", frames+1, machine->mem.ram[0x7005]);
    free(machine);
    return written != 32 || error ? 2 : 0;
}
