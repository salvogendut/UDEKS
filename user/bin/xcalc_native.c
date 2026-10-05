/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Calculator state and UI belong to the disk client. The graphical service
 * only retains/replays generic relative drawing commands and routes clicks. */
#include "udeks/calc.h"
#include "udeks/banked_graphics.h"
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);
static unsigned char commands[48][8], count, handle;
static char display[12];
static const unsigned char keys[]="789/456*123-C0=+.N  ";
static const unsigned char glyphs[][5]={
 {7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},
 {5,5,7,1,1},{7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},
 {7,5,7,5,7},{7,5,7,1,7},{2,2,7,2,2},{0,0,7,0,0},
 {5,2,7,2,5},{1,1,2,4,4},{0,7,0,7,0},{3,4,4,4,3},
 {0,0,0,0,2},{2,7,2,0,7},{7,4,6,4,7}
};
static void glyph(unsigned char x,unsigned char y,unsigned char c)
{
 unsigned char i,r;
 unsigned char *command;
 for(i=0;"0123456789+-*/=C.NE"[i] && "0123456789+-*/=C.NE"[i]!=c;++i) {}
 if(!"0123456789+-*/=C.NE"[i]) return;
 command=commands[count++];
 command[0]=2; command[1]=x; command[2]=y;
 for(r=0;r<5;++r) command[3+r]=glyphs[i][r];
}
static void line(unsigned char x,unsigned char y,unsigned char x2,unsigned char y2)
{
 unsigned char *command=commands[count++];
 command[0]=1; command[1]=x; command[2]=y;
 command[3]=x2; command[4]=y2; command[5]=0;
}
static void payload(void) { unsigned char i; for(i=0;i<24;++i) P[i]=0; P[1]=handle; }
static unsigned char present(void)
{
 unsigned char i;
 count=0; udeks_calc_format(display);
 for(i=0;display[i];++i) glyph(5+i*8u,17,display[i]);
 for(i=0;i<5;++i) line(2+i*25u,31,2+i*25u,131);
 for(i=0;i<6;++i) line(2,31+i*20u,102,31+i*20u);
 for(i=0;i<20;++i) glyph(11+(i%4u)*25u,36+(i/4u)*20u,keys[i]);
 payload(); P[2]=(unsigned int)commands; P[3]=(unsigned int)commands>>8; P[4]=count;
 return gfx_request(UDEKS_GFX_PRESENT);
}
unsigned char udeks_graphical_main(void)
{
 unsigned char i,x,y;
 udeks_calc_reset(); payload();
 P[1]=108;P[3]=30;P[4]=104;P[5]=133;P[6]=0x16;
 for(i=0;i<5;++i) P[7+i]="XCALC"[i];
 if(gfx_request(UDEKS_GFX_CREATE)) return 1;
 handle=R[11];
 if(present()) return 2;
 for(;;) {
  payload(); if(gfx_request(UDEKS_GFX_EVENT)) return 3;
  if(!P[0]) return 0;
  if(P[0]&2) {
   x=P[1];y=P[3];
   if(!P[2] && x>2 && x<102 && y>31 && y<131) {
    i=((y-31)/20)*4+(x-2)/25;
    if(keys[i]!=' ') { udeks_calc_key(keys[i]); if(present()) return 4; }
   }
  }
  gfx_sleep();
 }
}
