/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/native_ipc.h"
#include "udeks/task_request.h"
unsigned char udeks_errno;
unsigned char engine_test_mode,engine_test_bad_offset=255,engine_test_bad_value;
unsigned char engine_test_sent[8],engine_test_ack[8];
unsigned int engine_test_sends,engine_test_sleeps,engine_test_closes,engine_test_lookups;
static unsigned char got_reply;
void engine_test_reset(void)
{
    engine_test_mode=0;engine_test_bad_offset=255;engine_test_bad_value=0;
    engine_test_sends=0;engine_test_sleeps=0;engine_test_closes=0;engine_test_lookups=0;
    got_reply=0;udeks_errno=0;memset(engine_test_sent,0,8);memset(engine_test_ack,0,8);
}
udeks_ipc_handle udeks_ipc_lookup(const unsigned char *name)
{
    (void)name;++engine_test_lookups;
    if(engine_test_mode==1 || (got_reply && engine_test_mode!=12 && engine_test_sent[1]==3)) { udeks_errno=2;return 0; }
    return 123;
}
udeks_ipc_handle udeks_ipc_create(const unsigned char *name)
{ (void)name;if(engine_test_mode==2) { udeks_errno=28;return 0; }return 456; }
unsigned char udeks_ipc_close(udeks_ipc_handle handle)
{ (void)handle;++engine_test_closes;if(engine_test_mode==9) { udeks_errno=5;return 255; }udeks_errno=0;return 0; }
unsigned char udeks_sleep(unsigned int ticks)
{ (void)ticks;++engine_test_sleeps;if(engine_test_mode==10) { udeks_errno=5;return 255; }udeks_errno=0;return 0; }
unsigned char udeks_ipc_send(udeks_ipc_handle peer,udeks_ipc_handle endpoint,const unsigned char *p,unsigned char count)
{
    (void)peer;(void)endpoint;(void)count;++engine_test_sends;
    if(engine_test_mode==3 || engine_test_mode==10 || (engine_test_mode==4 && engine_test_sends<=2)) { udeks_errno=11;return 255; }
    if(engine_test_mode==5) { udeks_errno=9;return 255; }
    if(p[1]==4)memcpy(engine_test_ack,p,8);else memcpy(engine_test_sent,p,8);
    udeks_errno=0;return 0;
}
unsigned char udeks_ipc_receive(udeks_ipc_handle handle,udeks_ipc_handle *sender,unsigned char *p,unsigned char capacity)
{
    unsigned char i,n=engine_test_sent[7];
    (void)handle;(void)capacity;
    if(engine_test_mode==6) { udeks_errno=11;return 255; }
    *sender=engine_test_mode==7?124:123;got_reply=1;
    p[0]=1;p[1]=2;p[2]=engine_test_sent[2];p[3]=engine_test_sent[3];
    p[4]=0;p[5]=(unsigned char)(engine_test_sent[5]+engine_test_sent[6]*n);p[6]=0;p[7]=n;
    for(i=0;i<n;++i)p[8+i]=i+16;
    if(engine_test_mode==8) { p[4]=38;p[5]=0;p[7]=0;n=0; }
    if(engine_test_bad_offset<16)p[engine_test_bad_offset]=engine_test_bad_value;
    if(engine_test_mode==11)return 7;
    return n+8;
}
