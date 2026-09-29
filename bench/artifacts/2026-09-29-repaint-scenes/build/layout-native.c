#include "udeks/window.h"
#include "packet.h"
struct udeks_window {
    unsigned char flags;
    unsigned int x;
    unsigned char y;
    unsigned int width;
    unsigned char height;
    unsigned char z;
    const unsigned char *title;
    udeks_window_paint_fn paint;
    udeks_window_close_fn close;
};
const unsigned char layout[] = {offsetof(struct udeks_window,flags),offsetof(struct udeks_window,x),offsetof(struct udeks_window,y),offsetof(struct udeks_window,width),offsetof(struct udeks_window,height),offsetof(struct udeks_window,z),offsetof(struct udeks_window,title),sizeof(struct repaint_scene),sizeof(struct repaint_packet),offsetof(struct repaint_packet,ticket),offsetof(struct repaint_packet,work),offsetof(struct repaint_packet,result),offsetof(struct repaint_packet,snapshot)};
