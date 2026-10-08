/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent foreground loader. File policy stays outside the kernel. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/service.h"
#ifdef UDEKS_SERVICE_CLIENT_TEST
extern unsigned char udeks_service_slot[UDEKS_SERVICE_CAPACITY];
#define SLOT udeks_service_slot
#else
#define SLOT ((unsigned char *)UDEKS_SERVICE_BASE)
#endif
static unsigned char buffer[UDEKS_FILE_CHUNK];

static unsigned char fail(unsigned char error)
{
    udeks_write(2,(const unsigned char *)"svc: ");
    udeks_write(2,udeks_error_string(error));
    udeks_write_byte(2,'\n');
    return 1;
}

unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char action,state,fd,n,error,closed;
    unsigned int received;
    const unsigned char *path;
    if(argc<2 || argc>3) goto usage;
    if(!strcmp((const char *)argv[1],"status") && argc==2) action=0;
    else if(!strcmp((const char *)argv[1],"stop") && argc==2) action=3;
    else if(!strcmp((const char *)argv[1],"load")) action=1;
    else goto usage;
    /* A baseline kernel rejects this new version before any slot write. */
    state=udeks_service_control(0,0);
    if(state==UDEKS_IO_ERROR) return fail(udeks_errno);
    if(action==3) state=udeks_service_control(3,0);
    else if(action==1) {
        if(state) return fail(16);
        path=argc==3 ? (const unsigned char *)argv[2] : (const unsigned char *)"/TIME.SVC";
        fd=udeks_open(path,UDEKS_O_RDONLY);
        if(fd==UDEKS_IO_ERROR) return fail(udeks_errno);
        state=udeks_service_control(1,0);
        if(state==UDEKS_IO_ERROR) {
            error=udeks_errno; udeks_close(fd); return fail(error);
        }
        received=0; error=0;
        for(;;) {
            n=udeks_read(fd,buffer,sizeof(buffer));
            if(n==UDEKS_IO_ERROR) { error=udeks_errno; break; }
            if(!n) break;
            if(n>sizeof(buffer) || n>UDEKS_SERVICE_CAPACITY-received) {
                error=8; break;
            }
            memcpy(SLOT+received,buffer,n);
            received+=n;
        }
        closed=udeks_close(fd);
        if(!error && closed==UDEKS_IO_ERROR) error=udeks_errno;
        if(!error) {
            state=udeks_service_control(2,received);
            if(state==UDEKS_IO_ERROR) error=udeks_errno;
        }
        if(error) {
            udeks_service_control(3,0); /* abort own load, preserve first error */
            return fail(error);
        }
    }
    if(state==UDEKS_IO_ERROR) return fail(udeks_errno);
    udeks_write(1,(const unsigned char *)(state==2 ? "time: ready\n" :
                                           state==1 ? "time: loading\n" : "time: offline\n"));
    return 0;
usage:
    udeks_write(2,(const unsigned char *)"svc status | stop | load [FILE; default /TIME.SVC]\n");
    return 1;
}
