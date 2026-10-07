/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Actual banked C service, not mocked transport. Disposable media only. */
#include <stdint.h>
#include "udeks/task_request.h"
#include "udeks/storage_write.h"

extern uint8_t __fastcall__ lease_request(uint16_t owner);
extern uint8_t __fastcall__ lease_cleanup(uint16_t owner);
extern uint8_t __fastcall__ lease_init(uint16_t unused);
extern uint8_t lease_arm, lease_hidden, lease_visible;
extern uint16_t lease_stack;
#define R ((volatile uint8_t *)0xf359)
#define P (R+14)
#define OUT ((volatile uint8_t *)0xf100)
#define BYTE(a) (*(volatile uint8_t *)(a))
#define OWNER 0x1234u
static uint8_t seq, phase, i, n, got, chunk, saved[38];
static uint16_t pos;

static void fail(uint8_t why)
{
    OUT[5] = 0x80; OUT[6] = why; OUT[7] = phase;
    OUT[8] = R[12]; OUT[9] = R[11];
}
static void prepare(uint8_t op, uint8_t fd, const char *path)
{
    for (i=0; i<38; ++i) R[i] = 0;
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[5]=14;
    R[6]=1; R[7]=op; R[8]=++seq; R[9]=fd;
    if (path) { i=0; while (path[i]) { P[i]=path[i]; ++i; } R[10]=i; }
}
static uint8_t intact(void)
{
    if (BYTE(0xff00)!=0x7e || BYTE(0xd506)!=OUT[16] || lease_stack!=0xe200u) return 0;
    for (i=0; i<16; ++i) if (BYTE(0xe180u+i)!=0xa5) return 0;
    for (pos=0; pos<256u; ++pos) if (BYTE(0xf400u+pos)!=(uint8_t)(pos^0x5a)) return 0;
    return 1;
}
static uint8_t request(uint16_t owner, uint8_t error, uint8_t result)
{
    got=lease_request(owner);
    if (got!=1 || !intact() || R[6]!=(error ? 0x80u : 2u) ||
        R[8]!=seq || R[12]!=error || R[11]!=result) { fail(1); return 0; }
    ++OUT[10];
    return 1;
}
static uint8_t clean(uint16_t owner)
{
    for (i=0; i<38; ++i) saved[i]=R[i];
    got=lease_cleanup(owner);
    if (got || !intact()) { fail(2); return 0; }
    for (i=0; i<38; ++i) if (saved[i]!=R[i]) { fail(3); return 0; }
    ++OUT[11]; return 1;
}
static void mount(uint8_t flags)
{
    prepare(17,0,0); P[0]=8; P[1]='/'; R[10]=2; R[13]=flags;
}
void probe_main(void)
{
    OUT[0]='S'; OUT[1]='L'; OUT[2]='S'; OUT[3]='E'; OUT[4]=1;
    if (OUT[7]) { fail(4); return; }
    BYTE(0xf2a6)=0; BYTE(0xf3dd)=0;
    for (pos=0; pos<256u; ++pos) BYTE(0xf400u+pos)=(uint8_t)(pos^0x5a);
    phase=1;
    mount(0); lease_arm=1;
    if (!request(OWNER,0,0)) return;
    lease_arm=0;
    OUT[12]=lease_hidden; OUT[13]=lease_visible; OUT[14]=BYTE(0xfff5);
    if (lease_hidden!=1 || lease_visible || BYTE(0xfff5)!=1) { fail(5); return; }
    /* An existing pending recovery event must never be cleared by a request. */
    phase=2;
    prepare(6,3,"/blocked"); if (!request(OWNER,30,0)) return;
    if (BYTE(0xfff5)!=1) { fail(6); return; }
    BYTE(0xfff5)=0;
    BYTE(0xf3dd)=1;
    mount(3); if (!request(OWNER,0,0)) return;
    prepare(21,0,"/bin"); if (!request(OWNER,0,0)) return;
    prepare(22,0,0); if (!request(OWNER,0,4)) return;
    if (BYTE(0xf2a6)!=1 || P[0]!='/' || P[1]!='b' || P[2]!='i' || P[3]!='n') { fail(7); return; }
    prepare(21,0,"/"); if (!request(OWNER,0,0)) return;
    phase=3;
    prepare(6,3,"/lease"); if (!request(0,3,0)) return;
    prepare(6,3,"/lease"); if (!request(OWNER,0,4)) return;
    /* Re-init must not clear an open handle or reset permissions. */
    if (lease_init(0) || !intact()) { fail(8); return; }
    prepare(2,4,0); R[10]=1; P[0]=0x99;
    if (!request(0x1235,9,0)) return;
    if (!clean(0x1235)) return;
    prepare(9,4,0); if (!request(0x1235,9,0)) return;
    phase=4;
    /* 24 + 24 + 3 exact binary bytes, including NUL. */
    for (n=0; n<3; ++n) {
        prepare(2,4,0); chunk=n==2 ? 3u : 24u; R[10]=chunk;
        /* Do not loop on a volatile indexed count: cc65 -Oirs can retain
         * ptr1 across staspidx, which itself clobbers that pointer. */
        for (i=0; i<chunk; ++i) P[i]=(uint8_t)(n*24u+i);
        if (!request(OWNER,0,n==2 ? 3u : 24u)) return;
    }
    if (!clean(OWNER)) return; /* exit/cancel finalization, not normal CLOSE */
    prepare(9,4,0); if (!request(OWNER,9,0)) return;
    prepare(6,3,"/lease"); if (!request(OWNER,17,0)) return;
    phase=5;
    prepare(6,0,"/lease"); if (!request(0x2234,0,4)) return;
    for (n=0; n<3; ++n) {
        prepare(1,4,0); R[10]=24;
        if (!request(0x2234,0,n==2 ? 3u : 24u)) return;
        for (i=0; i<R[11]; ++i) if (P[i]!=(uint8_t)(n*24u+i)) { fail(9); return; }
    }
    prepare(1,4,0); R[10]=24; if (!request(0x2234,0,0)) return;
    prepare(9,4,0); if (!request(0x2234,0,0)) return;
    phase=6;
    prepare(6,3,"/empty"); if (!request(OWNER,0,4)) return;
    if (!clean(OWNER)) return; /* exact empty-file finalizer */
    prepare(6,0,"/empty"); if (!request(OWNER,0,4)) return;
    prepare(1,4,0); R[10]=24; if (!request(OWNER,0,0)) return;
    prepare(9,4,0); if (!request(OWNER,0,0)) return;
    phase=7;
    mount(2); if (!request(OWNER,0,0)) return;
    prepare(6,3,"/after"); if (!request(OWNER,30,0)) return;
    /* A rejected entry must leave request and mapping untouched. */
    for (i=0; i<38; ++i) saved[i]=R[i];
    n=OUT[16];
    BYTE(0xd506)=n&0xfeu; got=lease_request(OWNER);
    i=BYTE(0xd506); BYTE(0xd506)=n;
    if (got!=255u || i!=(n&0xfeu)) { fail(10); return; }
    for (i=0; i<38; ++i) if (saved[i]!=R[i]) { fail(11); return; }
    if (!intact()) { fail(12); return; }
    OUT[15]=BYTE(0xfff5);
    OUT[17]=BYTE(0xd506); OUT[18]=BYTE(0xff00);
    OUT[19]=(uint8_t)lease_stack; OUT[20]=lease_stack>>8;
    OUT[5]=2;
}
