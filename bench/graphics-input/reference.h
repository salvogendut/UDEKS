/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Test oracle for graphics_event.s: no production replacement or raw pointer
 * access in clients. Shared by host policy tests and the real-6502 check. */
#ifndef EVENT_FUNCTION
#define EVENT_FUNCTION udeks_graphics_event
#endif
unsigned char EVENT_FUNCTION(void)
{
    unsigned char handle=R[15], op=R[14], height=R[18];
    unsigned int width=R[16]|((unsigned int)R[17]<<8), x;
    int y;
    const struct udeks_window_click *click;
    R[11]=4;
    if(R[5]>=10) {
        udeks_graphics_geometry(handle);
        R[18]=udeks_graphics_width; R[19]=udeks_graphics_width>>8;
        R[20]=udeks_graphics_height; R[11]=op==7?8:7;
        if((width!=udeks_graphics_width || height!=udeks_graphics_height) &&
           !udeks_window_is_dragging(handle)) { R[14]=2; return 0; }
    }
    click=udeks_window_take_click(handle);
    R[14]=1;
    if(click) {
        R[14]=3; R[15]=click->x; R[16]=click->x>>8; R[17]=click->y;
    } else if(op==7 && udeks_window_is_focused(handle) &&
              !udeks_window_update_busy() && (input_pointer[11]&5)) {
        x=(input_pointer[8]|((unsigned int)input_pointer[9]<<8))-12-udeks_graphics_origin_x;
        y=(int)input_pointer[10]-40-udeks_graphics_origin_y;
        R[14]=4; R[15]=x; R[16]=x>>8; R[17]=y; R[21]=(unsigned int)y>>8;
    }
    return 0;
}
