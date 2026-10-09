/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Resident-side service module; no foreign code/title pointers. Retained
 * images share bank-0 $1300-$1BFF, not the client's runtime. */
#include "udeks/banked_graphics.h"
#include "udeks/retained_paths.h"
#include "udeks/retained_bitmap.h"
#include "udeks/window.h"
#include "udeks/window_service.h"
#include "udeks/vic_graphics.h"
#include <string.h>
#pragma rodata-name("MODULERODATA")
#ifdef UDEKS_GRAPHICS_HOST_TEST
extern unsigned char graphics_request[38];
#define R graphics_request
#define P (graphics_request+14)
#define C (graphics_request+16)
#else
/* Absolute array binding lets cc65 use direct indexed accesses rather than
 * repeatedly materializing pointer casts in zero page. No extra storage. */
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)
#define C (udeks_graphics_record+16)
#endif
/* Only admission state is needed before lazy installation. Geometry and
 * retained-image state arrive with the paths overlay, before any admission. */
static unsigned char running[UDEKS_NATIVE_CLIENTS];
static struct {
    unsigned char closing[UDEKS_NATIVE_CLIENTS], handle[UDEKS_NATIVE_CLIENTS];
    char title[UDEKS_NATIVE_CLIENTS][9];
} clients;
unsigned int udeks_retained_lengths[UDEKS_NATIVE_CLIENTS];
unsigned char udeks_banked_graphics_installed;
unsigned char udeks_banked_graphics_selected;
extern unsigned char udeks_shell_foreground_job;
unsigned char udeks_banked_graphics_names[UDEKS_NATIVE_CLIENTS][16];
#pragma bss-name(push, "PATHSTATE")
unsigned int udeks_graphics_origin_x;
unsigned char udeks_graphics_origin_y;
#define wx udeks_graphics_origin_x
#define wy udeks_graphics_origin_y
unsigned int udeks_graphics_width;
#define ww udeks_graphics_width
#pragma bss-name(pop)
unsigned char udeks_graphics_height;
#define wh udeks_graphics_height
unsigned char udeks_graphics_event(void);
#pragma code-name(push, "GRAPHICSHELP")
static void closed(unsigned char handle)
{
    unsigned char i;
    for(i=0;i<UDEKS_NATIVE_CLIENTS;++i) if(clients.handle[i]==handle) {
        clients.handle[i]=0; clients.closing[i]=1;
        udeks_retained_discard(i);
    }
}
#pragma code-name(pop)

#pragma code-name(push, "GRAPHICSCODE")
#pragma rodata-name(push, "GRAPHICSCODE")
/* Launching a native console task must not switch on or clear the VIC.
 * Only CREATE asks for a desktop, after this module has been installed. */
#pragma code-name(push, "CODE")
static unsigned char desktop(void)
{
    return udeks_vic_graphics_is_active()?0:udeks_vic_graphics_initialize();
}
#pragma code-name(pop)
/* Runs exactly once after the base module copy. Preserve the pending launch
 * name: the private eight-byte transport borrows request payload bytes 0..9. */
#pragma code-name(push, "CODE")
static void complete_install(void)
{
    unsigned char saved[10];
    unsigned int offset;
    memcpy(saved,(const void *)P,10);
    for(offset=0;offset<1008;offset+=8) {
        udeks_banked_read(0xcd00u+offset);
#ifdef UDEKS_GRAPHICS_HOST_TEST
        extern unsigned char graphics_overlay[1008];
        memcpy(graphics_overlay+offset,(const void *)C,8);
#else
        memcpy((void *)(0x96b8u+offset),(const void *)C,8);
#endif
    }
    memcpy((void *)P,saved,10);
}
#pragma code-name(pop)
void __fastcall__ udeks_graphics_geometry(unsigned char handle);
#define geometry udeks_graphics_geometry
static void paint(unsigned char handle)
{
    unsigned char row, data, count, index, scale;
    unsigned int address, x, y;
    index = udeks_window_owner(handle)-0x83u;
    if (index >= UDEKS_NATIVE_CLIENTS) return;
    geometry(handle);
    if(udeks_retained_lengths[index] & (UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING)) {
        udeks_retained_bitmap_paint(index); return;
    }
    if(udeks_retained_lengths[index]&UDEKS_RETAINED_PATH_FLAG) {
        udeks_retained_paths_paint(index); return;
    }
    count = udeks_retained_lengths[index]>>3;
    address = udeks_retained_address(index);
    for (; count; --count, address+=8u) {
        udeks_retained_read(address);
        x=wx+C[1]; y=wy+C[2];
        if (C[0]==0) udeks_vic_bitmap_fill(x,y,C[3],C[4],C[5]);
        else if (C[0]==1) udeks_vic_bitmap_line(x,y,wx+C[3],wy+C[4],C[5]);
        else {
            scale=C[0]==2?2:C[0]-2u;
            for (row=3;row<8;++row) {
                data=C[row];
                if(C[0]==2) data<<=5;
                x=wx+C[1];
                while (data) {
                    if (data & 128u) udeks_vic_bitmap_fill(x,y,scale,scale,0);
                    data<<=1; x+=scale;
                }
                y+=scale;
            }
        }
    }
}
/* Complete retained state is committed before any pixels. The small fill
 * list is a client-supplied delta from the last successfully presented image,
 * not a new source of window ownership or foreign-memory pointers. */
#pragma code-name(push, "CODE")
static unsigned char present_delta(unsigned char index, unsigned char handle)
{
    unsigned char n, error;
    if (R[5] < 15) return 38;
    for (n = 16; n <= 21; n += 5) if (P[n] != 0 && P[n] != 7) return 22;
    for (n = 5; n < 12; ++n) if (P[n]) return 22;
    if (P[22] || P[23]) return 22;
    if (udeks_window_update_busy()) return 11;
    /* P[12..21] survives the retained transport's P[0..9] scratch. */
    error = udeks_retained_present(index);
    if (error) return error;
    if (udeks_window_begin_paint(handle)) {
        /* Background window: the compositor owns overlap/occlusion. */
        udeks_window_repaint(handle);
    } else {
        geometry(handle);
        for (n = 12; n < 22; n += 5)
            udeks_vic_bitmap_fill(wx+P[n], wy+(P+1)[n], (P+2)[n], (P+3)[n], (P+4)[n]);
        udeks_window_end_paint();
    }
    return 0;
}
#pragma code-name(pop)
void udeks_banked_graphics_request(void)
{
    unsigned char task,index,op,handle,error=22;
    task=udeks_banked_call(0x30);
    index=task-3u;
    if(R[5]<9) { error=38; goto done; }
    if(R[9] || R[13] || R[10]!=24 || index>=UDEKS_NATIVE_CLIENTS) goto done;
    if(!running[index]) goto done;
    op=P[0]; handle=P[1];
    if(op==UDEKS_GFX_INPUT && R[5]>=17)
        op=UDEKS_GFX_EVENT; /* wire opcode remains available to the adapter */
    if(op==UDEKS_GFX_CREATE) {
        if(clients.handle[index] || clients.closing[index]) goto done;
        if((P[6]&0xf9u)!=0x10u && (R[5]<10 || (P[6]&0xf9u)!=0x08u)) goto done;
        if(desktop()) { error=5; goto done; }
        /* Exactly eight title bytes, plus a service-owned terminator. */
        memcpy(clients.title[index],(const void *)(P+7),8);
        clients.title[index][8]=0;
        handle=udeks_window_create(task+0x80u,1,P[6],P[1]|((unsigned int)P[2]<<8),
            P[3],P[4],P[5],(const unsigned char *)clients.title[index],paint,closed);
        clients.handle[index]=handle;
        R[11]=handle; error=handle?0:12;
    } else {
        if(op==UDEKS_GFX_EVENT && clients.closing[index]) { P[0]=0; R[11]=R[5]>=10?7:4; error=0; goto done; }
        if(!handle || handle!=clients.handle[index] || udeks_window_owner(handle)!=task+0x80u) goto done;
        if(op>=UDEKS_BITMAP_BEGIN && op<=UDEKS_BITMAP_ABORT) {
            if(R[5]<20) { error=38; goto done; }
            /* Repaint can be deferred during a drag/cache operation. Keep the
             * upload pending and retry COMMIT instead of losing its damage. */
            if(op==UDEKS_BITMAP_COMMIT && udeks_window_update_busy()) {
                error=11; goto done;
            }
            error=udeks_retained_bitmap_request(index);
            if(!error && op==UDEKS_BITMAP_COMMIT) udeks_window_repaint(handle);
            R[11]=0;
        } else if(op==UDEKS_GFX_PRESENT_DELTA) {
            error=present_delta(index,handle);
            R[11]=0;
        } else if(op==UDEKS_GFX_PRESENT || op==UDEKS_GFX_PATHS) {
            error=udeks_retained_present(index);
            if(error) goto done;
            udeks_window_repaint(handle);
            R[11]=0; error=0;
        } else if(op==UDEKS_GFX_EVENT) {
            error=udeks_graphics_event();
        } else if(op==UDEKS_GFX_CLOSE) {
            udeks_window_destroy(handle); R[11]=0; error=0;
        }
    }
done:
    R[12]=error; R[6]=error?0x80:2;
    if(error) R[11]=0;
}
#pragma rodata-name(pop)
#pragma code-name(pop)

/* Lifecycle glue stays in the ordinary resident segment. The renderer and
 * request policy are a separate split-output module installed at $0C00. */
void udeks_banked_graphics_poll(void)
{
    unsigned char i,state;
    for(i=0;i<UDEKS_NATIVE_CLIENTS;++i) if(running[i]) {
        state=udeks_banked_call(0x63u+i);
        /* Snapshot before destroying a window can borrow the request, and
         * before reap clears the lifecycle record. Background exits cannot
         * overwrite the foreground command's completion status. */
        if(state==6 && udeks_shell_foreground_job==(1u<<i)) {
#ifdef UDEKS_GRAPHICS_HOST_TEST
            extern unsigned char graphics_foreground_exit;
            graphics_foreground_exit=R[11];
#else
            *(volatile unsigned char *)0xf17a=R[11];
#endif
        }
        if(state==0 || state==6) {
            if(clients.handle[i]) udeks_window_destroy(clients.handle[i]);
            if(!udeks_banked_call(0xc3u+i)) running[i]=0;
        }
    }
}
unsigned char __fastcall__ udeks_banked_graphics_stop_name(const unsigned char *name)
{
    unsigned char i;
    for(i=0;i<UDEKS_NATIVE_CLIENTS;++i)
        if(running[i] && !strcmp((const char *)name,(const char *)udeks_banked_graphics_names[i]))
            return udeks_banked_graphics_stop(i);
    return 1;
}
unsigned char udeks_banked_graphics_launch(void)
{
    /* Launch is serialized on the root poll, never a task callback. */
    static unsigned char error;
    if(!udeks_banked_graphics_installed) {
        if(udeks_banked_call(0x10)) return 5;
        complete_install();
        udeks_banked_graphics_installed=1;
    }
    error=udeks_banked_call(0);
    if(error) return error==2?3:(error==16 || error==12)?4:error==5?6:5;
    udeks_banked_graphics_selected=R[11]-3u;
    memcpy(udeks_banked_graphics_names[udeks_banked_graphics_selected],(const void *)(P+1),16);
    clients.handle[udeks_banked_graphics_selected]=0;
    udeks_retained_discard(udeks_banked_graphics_selected);
    clients.closing[udeks_banked_graphics_selected]=0;
    running[udeks_banked_graphics_selected]=1;
#ifndef UDEKS_GRAPHICS_HOST_TEST
    *(volatile unsigned char *)0xf083=0xff; /* invalidate running-panel names */
#endif
    return 0;
}
#pragma code-name(push, "GRAPHICSHELP")
unsigned char __fastcall__ udeks_banked_graphics_stop(unsigned char index)
{
    if(index>=UDEKS_NATIVE_CLIENTS) return 1;
    if(!running[index] || clients.closing[index]) return 1;
    if(clients.handle[index]) udeks_window_destroy(clients.handle[index]);
    clients.closing[index]=1;
    return 0;
}
unsigned char __fastcall__ udeks_banked_graphics_running(unsigned char index)
{
    return index<UDEKS_NATIVE_CLIENTS && running[index] && !clients.closing[index];
}
#pragma code-name(pop)
