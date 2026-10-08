/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Prototype XSPRDEF raw bank: eight 63-byte, MSB-first sprites, no header.
 * Caller supplies a 504-byte staging buffer for failure-atomic LOAD. */
#include "udeks/task_request.h"
#ifndef R
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#define P (R+14)
#endif
extern unsigned char __fastcall__ native_file_request(unsigned char op);

unsigned char xspr_file(unsigned char save, unsigned char *data)
{
    unsigned int left=504;
    unsigned char i,n,wanted,error,closed,fd;
    for(i=0;i<13;++i) P[i]="/SPRITES.SPR"[i];
    R[9]=save?3:0; R[10]=12;
    error=native_file_request(UDEKS_TREQ_OP_OPEN);
    if(error) return error;
    fd=R[11];
    while(left) {
        wanted=left<24u?(unsigned char)left:24;
        if(save) for(i=0;i<wanted;++i) P[i]=data[i];
        R[9]=fd; R[10]=wanted;
        error=native_file_request(save?UDEKS_TREQ_OP_WRITE:UDEKS_TREQ_OP_READ);
        if(error) break;
        n=R[11];
        if(n>wanted || !n || (save && n!=wanted)) { error=save?5:8; break; }
        if(!save) for(i=0;i<n;++i) data[i]=P[i];
        data+=n; left-=n;
    }
    if(!error && !save) {
        R[9]=fd; R[10]=1;
        error=native_file_request(UDEKS_TREQ_OP_READ);
        if(!error && R[11]) error=8; /* trailing data: not a raw sprite bank */
    }
    R[9]=fd; R[10]=0;
    closed=native_file_request(UDEKS_TREQ_OP_CLOSE);
    return error?error:closed; /* CLOSE failure is never a successful save/load */
}
