/* SPDX-License-Identifier: GPL-3.0-or-later */
/* PRIVATE backend proof on a host-created disposable disk, not a syscall. */
#include <stdint.h>
#include "udeks/cbm_mutate.h"
#include "udeks/cbm_write.h"
#define R ((volatile uint8_t *)0x6000)
#define RO (*(volatile uint8_t *)0x60f0)
#define SPEED (*(volatile uint8_t *)0xd030)
#define CIA (*(volatile uint8_t *)0xdd00)
static const uint8_t names[][16] = {
    {'S','R','C','S','E','Q',160,160,160,160,160,160,160,160,160,160},
    {'S','R','C','P','R','G',160,160,160,160,160,160,160,160,160,160},
    {'E','M','P','T','Y',160,160,160,160,160,160,160,160,160,160,160},
    {'C','O','P','Y','S','E','Q',160,160,160,160,160,160,160,160,160},
    {'C','O','P','Y','P','R','G',160,160,160,160,160,160,160,160,160},
    {'C','O','P','Y','E','M','P','T','Y',160,160,160,160,160,160,160},
    {'M','O','V','E','D',160,160,160,160,160,160,160,160,160,160,160},
    {'A','B','S','E','N','T',160,160,160,160,160,160,160,160,160,160},
    {'L','O','N','G','1','2','3','4','5','6','7','8','9','0','A','B'},
    {'L','O','N','G','S','O','U','R','C','E','1','2','3','4','5','6'}
};
static uint8_t step(uint8_t op, uint8_t src, uint8_t dst, uint8_t expected)
{
    uint8_t error;
    ++R[1]; R[3] = expected;
    error = udeks_cbm_mutate(8,op,names[src],op==UDEKS_CBM_REMOVE?0:names[dst]);
    R[2] = error;
    if (error != expected || SPEED != R[8] || (CIA & 3u) != R[9] || (CIA & 0x38u)) {
        R[0] = 0x80; return 1;
    }
    return 0;
}
/* The fixture proves EMPTY is zero-length SEQ. A real service must derive
 * this from the source, not its name: DOS COPY injects CR for empty files. */
static uint8_t empty_copy(void)
{
    uint8_t error;
    ++R[1]; R[3] = 0;
    error = udeks_cbm_create(8,names[5],9,1);
    if (!error) error = udeks_cbm_write_close();
    R[2] = error;
    if (error || SPEED != R[8] || (CIA & 3u) != R[9] || (CIA & 0x38u)) {
        R[0] = 0x80; return 1;
    }
    return 0;
}
int main(void)
{
    uint8_t i;
    for(i=0;i<32u;++i) R[i]=0;
    R[0]=1; SPEED|=1; R[8]=SPEED; R[9]=CIA&3u;
    if (RO) {
        if(step(UDEKS_CBM_COPY,0,3,30)) return 1;
    } else {
        for(i=0;i<2u;++i) if(step(UDEKS_CBM_COPY,i,i+3u,0)) return 1;
        if(empty_copy()) return 1;
        if(step(UDEKS_CBM_COPY,0,3,17)) return 1;  /* no replacement */
        if(step(UDEKS_CBM_RENAME,0,4,17)) return 1;
        if(step(UDEKS_CBM_COPY,7,6,2)) return 1;
        if(step(UDEKS_CBM_RENAME,3,6,0)) return 1;
        if(step(UDEKS_CBM_RENAME,7,3,2)) return 1;
        if(step(UDEKS_CBM_REMOVE,6,0,0)) return 1;
        if(step(UDEKS_CBM_REMOVE,7,0,2)) return 1;
        if(step(UDEKS_CBM_COPY,9,8,0)) return 1; /* maximum 38-byte command */
    }
    R[0]=2; return 0;
}
