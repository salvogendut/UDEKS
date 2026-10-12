/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Raw-gate qualification fixture, not the slice-2 SDK or shipped demo. */
#include "udeks/native_console.h"
#include <string.h>
extern volatile unsigned char udeks_native_console_record[38];
void udeks_native_console_gate(void);
#define R udeks_native_console_record
#define P (R+14)
unsigned char ipc_phase,ipc_failure,ipc_release;
unsigned int ipc_handle,ipc_peer;
static unsigned char sequence;
static unsigned char request(unsigned char op,unsigned char count)
{
    unsigned char s=++sequence;
    R[0]='U';R[1]='T';R[2]='R';R[3]='Q';R[4]=0;R[5]=21;R[6]=1;
    R[7]=29;R[8]=s;R[9]=op;R[10]=count;R[11]=0;R[12]=0;R[13]=0;
    udeks_native_console_gate();
    if(R[8]!=s || R[7]!=29 || R[9]!=op || R[5]!=21) return 71;
    if(R[6]==128 && R[12])return R[12];
    if(R[6]!=2 || R[12] || R[11]!=R[10])return 71;
    return 0;
}
static void put(unsigned char offset,unsigned int value)
{ P[offset]=value;P[offset+1]=value>>8; }
static unsigned int get(void) { return P[0]|((unsigned int)P[1]<<8); }
static unsigned char named(unsigned char op,const char *name)
{
    unsigned char n=strlen(name),i;for(i=0;i<n;++i)P[i]=name[i];return request(op,n);
}
#define CHECK(c) do { if(!(c)) { ipc_failure=__LINE__;ipc_phase=128;return 1; } } while(0)
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char i;
    ipc_phase=0;ipc_failure=0;
    if(argc>1 && argv[1][0]=='h') {
        CHECK(!named(0,"held"));ipc_handle=get();ipc_phase=1;
        while(!ipc_release)CHECK(!udeks_sleep(1));
        ipc_phase=2;return 0; /* ownership cleanup comes from normal return */
    }
    if(argc>1 && argv[1][0]=='s') {
        /* IPC remains available after graphics stop. */
        CHECK(!named(0,"solo"));ipc_handle=get();put(0,ipc_handle);CHECK(!request(4,2));ipc_phase=3;return 0;
    }
    CHECK(!named(1,"held"));ipc_peer=get();
    CHECK(named(0,"held")==17); /* duplicate name, even for a foreign owner */
    CHECK(named(0,"ninechars")==22);
    CHECK(request(5,0)==22); /* unknown IPC suboperation */
    put(0,ipc_peer);P[2]=16;CHECK(request(3,3)==13);
    put(0,ipc_peer);CHECK(request(4,2)==13);
    CHECK(!named(0,"probe"));ipc_handle=get();CHECK(ipc_handle!=ipc_peer);
    CHECK(named(0,"third")==28); /* full endpoint pool must stay usable */
    put(0,ipc_handle);P[2]=16;CHECK(request(3,3)==11);
    put(0,ipc_peer);put(2,ipc_peer);P[4]=1;CHECK(request(2,5)==13);
    put(0,ipc_handle);put(2,ipc_handle);for(i=0;i<16;++i)P[4+i]=i*17;
    CHECK(!request(2,20));
    put(0,ipc_handle);put(2,ipc_handle);P[4]=255;CHECK(request(2,5)==11);
    put(0,ipc_handle);P[2]=17;CHECK(request(3,3)==22);
    put(0,ipc_handle);P[2]=15;CHECK(request(3,3)==90);
    put(0,ipc_handle);P[2]=16;CHECK(!request(3,3));CHECK(R[10]==18 && get()==ipc_handle);
    for(i=0;i<16;++i)CHECK(P[2+i]==(unsigned char)(i*17));
    put(0,ipc_handle);CHECK(!request(4,2));
    put(0,ipc_handle);P[2]=16;CHECK(request(3,3)==9);
    CHECK(!named(0,"probe"));CHECK(get()!=ipc_handle);ipc_handle=get();
    put(0,ipc_peer);put(2,ipc_handle);P[4]=0x37;CHECK(!request(2,5));
    ipc_phase=3;
    return 0; /* must purge the peer's queued message during retirement */
}
