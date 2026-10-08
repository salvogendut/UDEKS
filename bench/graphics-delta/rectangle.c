/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Execute the production assembly with the real cc65 runtime in sim65.
 * Verify every fill argument and software-stack balance, not source text. */
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include "udeks/vic_graphics.h"
extern unsigned int rectangle_sp(void);
static int args[4][4];
static unsigned char calls, expected_color;
void udeks_vic_bitmap_fill(int x,int y,int w,int h,unsigned char color)
{
    if (calls>=4 || args[calls][0]!=x || args[calls][1]!=y ||
        args[calls][2]!=w || args[calls][3]!=h || color!=expected_color) {
        puts("rectangle argument mismatch"); exit(1);
    }
    ++calls;
}
static void check(int x,int y,int w,int h,unsigned char color)
{
    unsigned int before;
    unsigned char i;
    for(i=0;i<4;++i) { args[i][0]=x; args[i][1]=y; args[i][2]=w; args[i][3]=h; }
    args[0][3]=args[1][3]=1;
    args[1][1]=(int)((unsigned int)y+(unsigned int)h-1);
    args[2][2]=args[3][2]=1;
    args[3][0]=(int)((unsigned int)x+(unsigned int)w-1);
    calls=0; expected_color=color;
    before=rectangle_sp();
    udeks_vic_bitmap_rectangle(x,y,w,h,color);
    if(rectangle_sp()!=before || calls!=(w>0 && h>0?4:0)) {
        puts("rectangle stack/count mismatch"); exit(2);
    }
}
int main(void)
{
    unsigned int i;
    for(i=0;i<1024;++i)
        check((int)(i%420)-50,(int)(i%270)-30,(int)(i%322)-1,(int)(i%202)-1,i&7);
    check(32760,32760,100,100,7);
    check(INT_MIN,INT_MIN,INT_MAX,INT_MAX,0);
    check(1,1,INT_MIN,12,0);check(1,1,12,INT_MIN,0);
    puts("PASS 1028 production rectangle calls: arguments and cc65 stack");
    return 0;
}
