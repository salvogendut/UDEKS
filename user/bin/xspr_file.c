/* SPDX-License-Identifier: GPL-3.0-or-later */
/* XSPRDEF raw bank: eight 63-byte, MSB-first sprites, no header.
 * BASIC export: load address $0E00 followed by eight 64-byte slots.
 * The export is a PRG: BASIC uses BLOAD "SPRITES.BSV",B0,P3584.
 * Caller supplies a 504-byte staging buffer for failure-atomic LOAD. */
#include "udeks/task_request.h"
#include "udeks/native_file.h"
#include "xspr_file.h"
#ifndef R
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#define P (R+14)
#endif

unsigned char xspr_file(unsigned char save, unsigned char *data)
{
    unsigned int left=save==XSPR_EXPORT?XSPR_BASIC_BYTES:XSPR_BANK_BYTES;
    unsigned int position=0;
    unsigned char i,n,wanted,error,closed,fd;
    const char *path=save==XSPR_EXPORT?XSPR_BASIC_PATH:XSPR_FILE_PATH;
    for(i=0;i<sizeof(XSPR_FILE_PATH);++i) P[i]=path[i];
    R[9]=save==XSPR_EXPORT?UDEKS_TREQ_OPEN_CREATE_PRG:save?UDEKS_TREQ_OPEN_CREATE:0;
    R[10]=sizeof(XSPR_FILE_PATH)-1;
    error=native_file_request(UDEKS_TREQ_OP_OPEN);
    if(error) return error;
    fd=R[11];
    while(left) {
        wanted=left<24u?(unsigned char)left:24;
        if(save) for(i=0;i<wanted;++i) {
            if(save!=XSPR_EXPORT) P[i]=data[i];
            else {
                /* Stream the extra ten bytes without another bank buffer.
                 * Never consume a source byte for the header or padding. */
                if(position<2u) P[i]=position?0x0e:0;
                else P[i]=((position-2u)&63u)==63u?0:*data++;
                ++position;
            }
        }
        R[9]=fd; R[10]=wanted;
        error=native_file_request(save?UDEKS_TREQ_OP_WRITE:UDEKS_TREQ_OP_READ);
        if(error) break;
        n=R[11];
        if(n>wanted || (save && n!=wanted)) { error=UDEKS_TREQ_EIO; break; }
        if(!n) { error=UDEKS_TREQ_ENOEXEC; break; }
        if(!save) for(i=0;i<n;++i) data[i]=P[i];
        if(save!=XSPR_EXPORT) data+=n;
        left-=n;
    }
    if(!error && !save) {
        R[9]=fd; R[10]=1;
        error=native_file_request(UDEKS_TREQ_OP_READ);
        if(!error && R[11]) error=UDEKS_TREQ_ENOEXEC;
    }
    R[9]=fd; R[10]=0;
    closed=native_file_request(UDEKS_TREQ_OP_CLOSE);
    return error?error:closed; /* CLOSE failure is never a successful save/load */
}
