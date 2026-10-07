/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Deliberately leaks a READ descriptor on normal synchronous return. */
#include "udeks/program.h"
#define R ((volatile unsigned char *)0xf359)
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char i;
    (void)argc; (void)argv;
    for(i=0;i<38;++i) R[i]=0;
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[5]=14;
    R[6]=1; R[7]=6; R[8]=71; R[10]=6;
    R[14]='/'; R[15]='h'; R[16]='e'; R[17]='l'; R[18]='l'; R[19]='o';
    /* Neither a newer ABI nor a create mode bypasses the public RO gate. */
    __asm__("jsr $cf30");
    if(R[12]!=71) return 91;
    R[5]=13; R[6]=1; R[9]=3; ++R[8];
    __asm__("jsr $cf30");
    if(R[12]!=22) return 92;
    R[6]=1; R[9]=0; ++R[8];
    __asm__("jsr $cf30");
    return R[12] ? R[12] : R[11]==4 ? 0 : 99;
}
