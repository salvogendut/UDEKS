/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Synchronous, bounded worker requests. No user pointers cross this boundary. */
#include "udeks/task_request.h"
#include "udeks/mailbox.h"
#include "udeks/z80_worker.h"

extern volatile unsigned char udeks_graphics_record[38];
extern volatile unsigned char udeks_worker_mailbox[64];
#define R udeks_graphics_record
#define P (udeks_graphics_record+14)

unsigned char udeks_task_worker_request(void)
{
    if(R[5]<11) return UDEKS_TREQ_ENOSYS;
    if(R[9] || R[13] || R[10]!=4) return UDEKS_TREQ_EINVAL;
    if(P[0]==UDEKS_MB_OP_NOP) {
        if(P[1] || P[2] || P[3]) return UDEKS_TREQ_EINVAL;
    } else {
        if(P[0]!=UDEKS_MB_OP_WAVE_SAMPLES && P[0]!=UDEKS_MB_OP_SURFACE_ROWS) {
            return UDEKS_TREQ_ENOSYS;
        }
        if(!P[3] || P[3]>64) return UDEKS_TREQ_EINVAL;
    }
    /* The worker is the single authority for per-kernel operand bounds. It
     * validates before touching output; malformed rows return in one lease. */
    switch(udeks_z80_submit(P[0],P[1],P[2],P[3],0)) {
    case UDEKS_Z80_OK: break;
    case UDEKS_Z80_WORKER_REJECTED: return UDEKS_TREQ_EINVAL;
    default: return UDEKS_TREQ_EIO;
    }
    P[0]=udeks_worker_mailbox[UDEKS_MB_RESULT_LO];
    P[1]=udeks_worker_mailbox[UDEKS_MB_RESULT_HI]; P[2]=P[3];
    return 0;
}
