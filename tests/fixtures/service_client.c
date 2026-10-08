/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host boundary fakes for the REAL svc.c, not an alternate loader. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "udeks/program.h"
#include "udeks/service.h"
unsigned char udeks_errno,udeks_service_slot[UDEKS_SERVICE_CAPACITY];
static unsigned char source[800],state,error_report;
static unsigned int size,position,transferred;
static unsigned char unsupported,open_error,begin_error,read_error,close_error,commit_error,oversized_read;
static unsigned char opens,closes,begins,commits,stops,events[128],event_count;
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
unsigned char udeks_write(unsigned char fd,const unsigned char *text) {
    if(!strcmp((const char *)text,"Exec format error")) { CHECK(fd==2);error_report=8; }
    return 0;
}
unsigned char udeks_write_byte(unsigned char fd,unsigned char c) { (void)fd;(void)c;return 0; }
const unsigned char *udeks_error_string(unsigned char error) { error_report=error;return (const unsigned char *)"error"; }
unsigned char __fastcall__ udeks_service_control(unsigned char action,unsigned int received)
{
    events[event_count++]=action;
    udeks_errno=0;
    if(unsupported) { udeks_errno=71;return 255; }
    if(action==1) { ++begins; if(begin_error) udeks_errno=begin_error; else state=1; }
    if(action==2) { ++commits;transferred=received;udeks_errno=commit_error;state=commit_error?0:2; }
    if(action==3) { ++stops;state=0; }
    return udeks_errno?255:state;
}
unsigned char udeks_open(const unsigned char *path,unsigned char mode)
{
    ++opens;CHECK(mode==0);CHECK(!strcmp((const char *)path,"/TIME.SVC") || !strcmp((const char *)path,"/other"));
    udeks_errno=open_error;return open_error?255:3;
}
unsigned char udeks_read(unsigned char fd,unsigned char *out,unsigned char count)
{
    unsigned int n;
    CHECK(fd==3 && count==24 && state==1);events[event_count++]=10;
    if(read_error && position>=24) { udeks_errno=read_error;return 255; }
    if(oversized_read) return 25;
    n=size-position;if(n>count)n=count;
    memcpy(out,source+position,n);position+=n;return n;
}
unsigned char udeks_close(unsigned char fd)
{
    CHECK(fd==3);++closes;events[event_count++]=11;udeks_errno=close_error;return close_error?255:0;
}
static void reset(void)
{
    unsigned int i;
    memset(udeks_service_slot,0xa5,sizeof(udeks_service_slot));
    for(i=0;i<sizeof(source);++i)source[i]=(unsigned char)i;
    state=error_report=unsupported=open_error=begin_error=read_error=close_error=commit_error=oversized_read=0;
    opens=closes=begins=commits=stops=event_count=0;position=transferred=0;size=710;
}
static unsigned char run(const char *action,const char *path)
{
    unsigned char *argv[3]={(unsigned char *)"svc",(unsigned char *)action,(unsigned char *)path};
    return udeks_program_main(path?3:2,argv);
}
static void untouched(void)
{ unsigned int i;for(i=0;i<sizeof(udeks_service_slot);++i)CHECK(udeks_service_slot[i]==0xa5); }
int main(void)
{
    unsigned int i;
    reset();CHECK(run("load",0)==0);CHECK(state==2 && opens==1 && closes==1 && commits==1 && !stops);
    CHECK(transferred==710 && !memcmp(udeks_service_slot,source,710));
    for(i=710;i<sizeof(udeks_service_slot);++i)CHECK(udeks_service_slot[i]==0xa5);
    CHECK(events[event_count-2]==11 && events[event_count-1]==2); /* CLOSE before COMMIT */
    reset();CHECK(run("load","/other")==0);
    reset();unsupported=1;CHECK(run("load",0)==1);CHECK(error_report==71 && !opens && !begins);untouched();
    reset();open_error=2;CHECK(run("load",0)==1);CHECK(error_report==2 && !closes && !begins);untouched();
    reset();state=2;CHECK(run("load",0)==1);CHECK(error_report==16 && !opens && !begins && !stops);untouched();
    reset();state=1;CHECK(run("load",0)==1);CHECK(error_report==16 && !opens && !stops);untouched();
    reset();begin_error=11;close_error=5;CHECK(run("load",0)==1);
    CHECK(error_report==11 && closes==1 && !stops && !commits);untouched();
    reset();read_error=5;close_error=19;CHECK(run("load",0)==1);
    CHECK(error_report==5 && closes==1 && stops==1 && !commits && !state);CHECK(position==24);
    reset();close_error=19;CHECK(run("load",0)==1);CHECK(error_report==19 && !commits && stops==1 && !state);
    reset();commit_error=8;CHECK(run("load",0)==1);CHECK(error_report==8 && commits==1 && stops==1 && !state);
    reset();size=729;CHECK(run("load",0)==1);CHECK(error_report==8 && !commits && closes==1 && stops==1);
    CHECK(!memcmp(udeks_service_slot,source,720));
    for(i=720;i<sizeof(udeks_service_slot);++i)CHECK(udeks_service_slot[i]==0xa5);
    reset();size=728;CHECK(run("load",0)==0);CHECK(transferred==728 && !memcmp(udeks_service_slot,source,728));
    reset();oversized_read=1;CHECK(run("load",0)==1);CHECK(error_report==8 && !commits && stops==1);untouched();
    reset();size=0;commit_error=8;CHECK(run("load",0)==1);CHECK(transferred==0 && commits==1 && stops==1);untouched();
    reset();CHECK(run("status",0)==0);CHECK(!opens && !begins && !stops);untouched();
    reset();state=2;CHECK(run("stop",0)==0);CHECK(stops==1 && !state && !opens);untouched();
    reset();CHECK(run("unknown",0)==1);CHECK(!event_count && !opens);untouched();
    puts("PASS 17 real svc loader scenarios: bounded copies, close-before-commit, first-error preservation, old-kernel refusal");
    return 0;
}
