/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Resident-side service module; no foreign code/title pointers. Retained
 * command images live in bank 1 $CD00-$CFFF, not in the client's runtime. */
#include "udeks/banked_graphics.h"
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
#define R ((volatile unsigned char *)0xf359)
#define P ((volatile unsigned char *)0xf367)
#define C ((volatile unsigned char *)0xf369)
#endif
/* Direct byte indexing keeps the two-client lifecycle within resident space. */
static struct {
    unsigned char running[2], closing[2], handle[2], count[2];
    char title[2][9];
} clients;
unsigned char udeks_banked_graphics_installed;
#pragma data-name(push, "GRAPHICSCODE")
/* Initialized with the lazily installed module; read only for live clients. */
unsigned char udeks_banked_graphics_selected=0;
unsigned char udeks_banked_graphics_names[2][16]={{0}};
#pragma data-name(pop)
const unsigned char udeks_banked_legacy_names[2][6]={"xcalc","xdraw"};
static unsigned int wx, ww;
static unsigned char wy, wh;
/* Launching a native console task must not switch on or clear the VIC.
 * Only CREATE asks for a desktop; keep this small helper resident. */
static unsigned char desktop(void)
{
    return udeks_vic_graphics_is_active()?0:udeks_vic_graphics_initialize();
}
#pragma code-name(push, "GRAPHICSHELP")
static unsigned int retained(unsigned char index) { return index ? 0xce80u : 0xcd00u; }
static void closed(unsigned char handle)
{
    unsigned char i;
    for(i=0;i<2;++i) if(clients.handle[i]==handle) {
        clients.handle[i]=0; clients.closing[i]=1;
    }
}
#pragma code-name(pop)

#pragma code-name(push, "GRAPHICSCODE")
static void paint(unsigned char handle)
{
    unsigned char i, row, bit, data, count, index;
    unsigned int address, x;
    unsigned int y;
    index = udeks_window_owner(handle)-0x83u;
    if (index >= 2) return;
    count = clients.count[index];
    address = retained(index);
    udeks_window_get_geometry(handle,&wx,&wy,&ww,&wh);
    for (i=0; i<count; ++i, address+=8u) {
        udeks_banked_read(address);
        x=wx+C[1]; y=wy+C[2];
        if (C[0]==0) udeks_vic_bitmap_fill(x,y,C[3],C[4],C[5]);
        else if (C[0]==1) udeks_vic_bitmap_line(x,y,wx+C[3],wy+C[4],C[5]);
        else if (C[0]==2) {
            for (row=0;row<5;++row) {
                data=C[3+row];
                for (bit=0;bit<3;++bit)
                    if (data & (4u>>bit)) udeks_vic_bitmap_fill(x+bit*2u,y+row*2u,2,2,0);
            }
        }
    }
}
void udeks_banked_graphics_request(void)
{
    unsigned char task,index,op,handle,count,i,error=22;
    unsigned int source,limit,destination;
    const struct udeks_window_click *click;
    task=udeks_banked_call(0x30);
    index=task-3u;
    if(R[5]<9) { error=38; goto done; }
    if(R[9] || R[13] || R[10]!=24 || index>=2) goto done;
    if(!clients.running[index]) goto done;
    op=P[0]; handle=P[1];
    if(op==UDEKS_GFX_CREATE) {
        if(clients.handle[index] || clients.closing[index] || (P[6]&0xf9u)!=0x10u) goto done;
        if(desktop()) { error=5; goto done; }
        /* Exactly eight title bytes, plus a service-owned terminator. */
        memcpy(clients.title[index],(const void *)(P+7),8);
        clients.title[index][8]=0;
        handle=udeks_window_create(task+0x80u,1,P[6],P[1]|((unsigned int)P[2]<<8),
            P[3],P[4],P[5],(const unsigned char *)clients.title[index],paint,closed);
        clients.handle[index]=handle;
        R[11]=handle; error=handle?0:12;
    } else {
        if(op==UDEKS_GFX_EVENT && clients.closing[index]) { P[0]=0; R[11]=4; error=0; goto done; }
        if(!handle || handle!=clients.handle[index] || udeks_window_owner(handle)!=task+0x80u) goto done;
        if(op==UDEKS_GFX_PRESENT) {
            count=P[4]; source=P[2]|((unsigned int)P[3]<<8);
            limit=index?0x4000u:0x3500u;
            if(count>UDEKS_GFX_COMMANDS || source<(index?0x3500u:0x2300u) ||
               source>=limit || (unsigned int)count*8u>limit-source) goto done;
            destination=retained(index);
            /* Validate the entire candidate before altering retained pixels. */
            for(i=0;i<count;++i) {
                udeks_banked_read(source+(unsigned int)i*8u);
                if(C[0]>2 || (C[0]<2 && C[5]!=0 && C[5]!=7)) goto done;
            }
            for(i=0;i<count;++i,source+=8u,destination+=8u) {
                udeks_banked_read(source); udeks_banked_write(destination);
            }
            clients.count[index]=count;
            udeks_window_repaint(handle);
            R[11]=0; error=0;
        } else if(op==UDEKS_GFX_EVENT) {
            click=udeks_window_take_click(handle);
            P[0]=click?3:1;
            if(click) { P[1]=click->x; P[2]=click->x>>8; P[3]=click->y; }
            R[11]=4; error=0;
        } else if(op==UDEKS_GFX_CLOSE) {
            udeks_window_destroy(handle); R[11]=0; error=0;
        }
    }
done:
    R[12]=error; R[6]=error?0x80:2;
    if(error) R[11]=0;
}
#pragma code-name(pop)

/* Lifecycle glue stays in the ordinary resident segment. The renderer and
 * request policy are a separate split-output module installed at $0C00. */
void udeks_banked_graphics_poll(void)
{
    unsigned char i,state;
    for(i=0;i<2;++i) if(clients.running[i]) {
        state=udeks_banked_call(0x63u+i);
        if(state==0 || state==6) {
            if(clients.handle[i]) udeks_window_destroy(clients.handle[i]);
            if(!udeks_banked_call(0xc3u+i)) clients.running[i]=0;
        }
    }
}
unsigned char __fastcall__ udeks_banked_graphics_start(unsigned char index)
{
    if(index>=2) return 4;
    if(clients.running[index]) return 4;
    return udeks_banked_graphics_exec(index?udeks_banked_legacy_names[1]:udeks_banked_legacy_names[0]);
}
unsigned char udeks_banked_graphics_launch(void)
{
    /* Launch is serialized on the root poll, never a task callback. */
    static unsigned char error;
    if(!udeks_banked_graphics_installed) {
        if(udeks_banked_call(0x10)) return 5;
        udeks_banked_graphics_installed=1;
    }
    error=udeks_banked_call(0);
    if(error) return error==2?3:(error==16 || error==12)?4:error==5?6:5;
    udeks_banked_graphics_selected=R[11]-3u;
    memcpy(udeks_banked_graphics_names[udeks_banked_graphics_selected],(const void *)(P+1),16);
    clients.handle[udeks_banked_graphics_selected]=0;
    clients.count[udeks_banked_graphics_selected]=0;
    clients.closing[udeks_banked_graphics_selected]=0;
    clients.running[udeks_banked_graphics_selected]=1;
#ifndef UDEKS_GRAPHICS_HOST_TEST
    *(volatile unsigned char *)0xf083=0xff; /* invalidate running-panel names */
#endif
    return 0;
}
#pragma code-name(push, "GRAPHICSHELP")
unsigned char __fastcall__ udeks_banked_graphics_stop(unsigned char index)
{
    if(index>=2) return 1;
    if(!clients.running[index] || clients.closing[index]) return 1;
    if(clients.handle[index]) udeks_window_destroy(clients.handle[index]);
    clients.closing[index]=1;
    return 0;
}
unsigned char __fastcall__ udeks_banked_graphics_running(unsigned char index)
{
    return index<2 && clients.running[index] && !clients.closing[index];
}
#pragma code-name(pop)
