/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Ordinary relocatable native client: no kernel imports, no graphics needed. */
#define R ((volatile unsigned char *)0xf359)
unsigned char owner_stage, owner_release;
static unsigned char i;
static void request(unsigned char op)
{
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[4]=0; R[5]=13;
    R[6]=1; R[7]=op; ++R[8]; R[9]=0; R[13]=0;
    __asm__("jsr $ff16");
}
void udeks_graphical_main(void)
{
    owner_stage=1;
    for(i=0;i<24;++i) R[14+i]=0;
    R[14]='/'; R[15]='h'; R[16]='e'; R[17]='l'; R[18]='l'; R[19]='o';
    R[10]=6; request(6);
    if(R[12] || R[11]!=4) { owner_stage=0x80; return; }
    owner_stage=2;
    while(!owner_release) { R[10]=0; request(10); }
    owner_stage=3; /* native return trampoline issues EXIT, no explicit CLOSE */
}
