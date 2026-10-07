/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native public-client fixture. The monitor controls only these client flags. */
#include <string.h>
#define R ((volatile unsigned char *)0xf359)
unsigned char writer_stage,writer_release,writer_case;
unsigned char writer_errno,writer_written,writer_closed;
static unsigned char i,action;
static void request(unsigned char op,unsigned char fd,unsigned char count)
{
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[4]=0; R[5]=14;
    R[7]=op; ++R[8]; R[9]=fd; R[10]=count; R[11]=R[12]=R[13]=0;
    R[6]=1;
    __asm__("jsr $ff16");
}
void udeks_graphical_main(void)
{
    writer_stage=1;
    while(!writer_release) request(10,0,0);
    writer_release=0;
    memcpy((void *)(R+14),"/mnt/OWNER0",11);
    R[24]='0'+writer_case;
    request(6,3,11);
    if(R[12] || R[11]!=4) { writer_errno=R[12]; writer_stage=0x81; return; }
    for(i=0;i<24;++i) R[14+i]=i;
    request(2,4,24);
    if(R[12] || R[11]!=24) { writer_errno=R[12]; writer_stage=0x82; return; }
    writer_stage=2;
    while(!writer_release) request(10,0,0);
    action=writer_release;
    if(action==1) { writer_stage=3; return; } /* EXIT must finalize */
    if(action==2) {
        for(i=0;i<24;++i) R[14+i]=24+i;
        request(2,4,24);
        writer_errno=R[12]; writer_written=R[11];
    }
    request(9,4,0);
    writer_closed=R[12];
    writer_stage=4;
}
