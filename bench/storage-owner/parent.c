/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native parent uses the real SPAWN/CANCEL/WAITPID syscall boundary. */
#include <string.h>
#define R ((volatile unsigned char *)0xf359)
#define CHILD (*(volatile unsigned char *)0x02f0)
unsigned char parent_stage, parent_release;
unsigned char parent_error, parent_result;
static void request(unsigned char op)
{
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[4]=0; R[5]=13;
    R[6]=1; R[7]=op; ++R[8]; R[9]=0; R[13]=0;
    __asm__("jsr $ff16");
}
void udeks_graphical_main(void)
{
    parent_stage=1;
    memset((void *)(R+14),0,24);
    R[14]=5; R[15]='c'; R[16]='h'; R[17]='i'; R[18]='l'; R[19]='d';
    R[10]=17; request(15);
    parent_error=R[12]; parent_result=R[11];
    if(R[12] || R[11]!=1 || R[14]!=2 || R[15]) { parent_stage=0x81; return; }
    while(CHILD!=2) { R[10]=0; request(10); }
    parent_stage=2;
    while(!parent_release) { R[10]=0; request(10); }
    /* A running parent is not the owner of its child's file descriptor. */
    R[10]=0; R[0]='U'; R[5]=13; R[7]=9; R[9]=4;
    R[6]=1; R[13]=0; ++R[8]; __asm__("jsr $ff16");
    if(R[12]!=9) { parent_stage=0x85; return; }
    R[14]=2; R[15]=0; R[16]=130; R[10]=3; request(14);
    parent_error=R[12]; parent_result=R[11];
    if(R[12]) { parent_stage=0x82; return; }
    R[14]=2; R[15]=0; R[10]=2; request(12);
    parent_error=R[12]; parent_result=R[11];
    if(R[12] || R[11]!=1 || R[14]!=2 || R[16]!=130) { parent_stage=0x83; return; }
    parent_stage=3;
    /* Prove the cancelled child's open stream was released before reuse. */
    /* A real call also invalidates cc65's cached indirect-address scratch. */
    memset((void *)(R+14),0,24);
    R[14]='/'; R[15]='h'; R[16]='e'; R[17]='l'; R[18]='l'; R[19]='o';
    R[10]=6; request(6);
    parent_error=R[12]; parent_result=R[11];
    if(R[12] || R[11]!=4) { parent_stage=0x84; return; }
    parent_stage=4; /* second leaked stream is closed by this parent's EXIT */
}
