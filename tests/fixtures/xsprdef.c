/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char editor_request[38];
#define R editor_request
#define P (editor_request+14)
#include "../../user/bin/xsprdef.c"
#include "../../user/bin/xspr_file.c"

unsigned char io_data[600],io_written[600],io_flags,io_error,io_close_error;
unsigned char io_chunk=24,io_invalid;
unsigned char io_basic;
unsigned int io_length,io_offset,io_calls,io_closes,io_fail_at,io_short_at,io_over_at;
unsigned char native_file_request(unsigned char op) {
    unsigned char n=R[10],result=0;
    ++io_calls;
    if(op==UDEKS_TREQ_OP_CLOSE) { ++io_closes; return io_close_error; }
    if(io_calls==io_fail_at) return io_error;
    if(op==UDEKS_TREQ_OP_OPEN) {
        io_basic=!memcmp(P,"/SPRITES.BSV",13);
        if(R[10]!=12 || (!io_basic && memcmp(P,"/SPRITES.SPR",13)) ||
           (io_basic ? R[9]!=4 : (R[9]!=0 && R[9]!=3))) io_invalid=1;
        io_flags=R[9];io_offset=0;R[11]=4;return 0;
    }
    if(R[9]!=4 || !n || n>24) io_invalid=1;
    if(io_calls==io_over_at) { R[11]=n+1; return 0; }
    if(io_calls==io_short_at) n=0;
    if(op==UDEKS_TREQ_OP_READ) {
        if(n>io_chunk) n=io_chunk;
        while(result<n && io_offset<io_length) P[result++]=io_data[io_offset++];
    } else if(op==UDEKS_TREQ_OP_WRITE) {
        while(result<n && io_offset<sizeof(io_written)) io_written[io_offset++]=P[result++];
    } else io_invalid=1;
    R[11]=result;return 0;
}
void editor_io_reset(void) {
    memset(io_data,0,sizeof(io_data));memset(io_written,0,sizeof(io_written));
    io_length=io_offset=io_calls=io_closes=io_fail_at=io_short_at=io_over_at=0;
    io_basic=io_flags=io_invalid=io_error=io_close_error=0;io_chunk=24;
}
unsigned char editor_file(unsigned char save,unsigned char *data) { return xspr_file(save,data); }

unsigned char editor_op, editor_error;
unsigned char gfx_request(unsigned char op) { editor_op=op; return editor_error; }
void gfx_sleep(void) {}
void gfx_yield(void) {}
void editor_reset(void) {
    memset(sprite_bank,0,sizeof(sprite_bank)); memset(edit,0,sizeof(edit));
    memset(commands,0,sizeof(commands)); mode=selected=confirming=count=0;
    file_error=exporting=0;editor_io_reset();
    pixel_delta=pixel_x=pixel_y=editor_op=editor_error=0;
    stroke=stroke_ink=stroke_x=stroke_y=line_pending=0;
}
unsigned char editor_click(unsigned char x,unsigned char y) { return click_at(x,y); }
unsigned char editor_input(unsigned char state,unsigned char x,unsigned char y) { return input_at(state,x,y); }
unsigned char editor_step(void) { return stroke_next(); }
unsigned char editor_draw(void) {
    if(confirming) dialog_present(); else if(mode) editor_present(); else list_present();
    return count;
}
unsigned char editor_mode(void) { return mode; }
unsigned char editor_confirming(void) { return confirming; }
unsigned char editor_selected(void) { return selected; }
unsigned char *editor_pixels(void) { return edit; }
unsigned char *editor_bank(void) { return sprite_bank[0]; }
unsigned char *editor_commands(void) { return commands[0]; }
