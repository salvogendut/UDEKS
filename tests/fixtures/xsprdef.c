/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char editor_request[38];
#define R editor_request
#define P (editor_request+14)
#include "../../user/bin/xsprdef.c"

unsigned char gfx_request(unsigned char op) { (void)op; return 0; }
void gfx_sleep(void) {}
void editor_reset(void) {
    memset(sprite_bank,0,sizeof(sprite_bank)); memset(edit,0,sizeof(edit));
    memset(commands,0,sizeof(commands)); mode=selected=confirming=count=0;
}
unsigned char editor_click(unsigned char x,unsigned char y) { return click_at(x,y); }
unsigned char editor_draw(void) {
    if(mode) editor_present(); else list_present();
    return count;
}
unsigned char editor_mode(void) { return mode; }
unsigned char editor_confirming(void) { return confirming; }
unsigned char editor_selected(void) { return selected; }
unsigned char *editor_pixels(void) { return edit; }
unsigned char *editor_bank(void) { return sprite_bank[0]; }
unsigned char *editor_commands(void) { return commands[0]; }
