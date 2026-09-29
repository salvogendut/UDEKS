/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Read-only failure-state report. Do not archive the snapshot's ROM contents. */
#include "c128.h"
#include "snapshot.h"
#include <stdio.h>
#include <stdlib.h>
int g_debug_enabled;
int main(int argc,char **argv) {
    if(argc!=2)return 1;
    Config cfg;config_set_defaults(&cfg);
    C128 *c=calloc(1,sizeof(*c));if(!c)return 1;
    c128_init(c,&cfg);
    if(snapshot_load(c,argv[1])!=SNAPSHOT_OK)return 1;
    printf("{\"irq_target\":%u,\"raster\":%u,\"sampler_phase\":%u,"
           "\"keyboard_matrix_row0\":%u,\"physical_return_down\":%u}\n",
           c->vic.raster_irq_line,c->vic.current_raster,c->mem.ram[0xf1ea],
           c->mem.ram[0xf138],kbd_matrix(&c->kbd,0)&2?0:1);
    free(c);return 0;
}
