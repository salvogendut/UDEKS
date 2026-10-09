/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_console.h"
#include "udeks/task_request.h"

#ifdef UDEKS_NATIVE_CONSOLE_HOST_TEST
extern volatile unsigned char native_console_request[UDEKS_TASK_REQUEST_SIZE];
#define R native_console_request
#else
extern volatile unsigned char udeks_native_console_record[UDEKS_TASK_REQUEST_SIZE];
#define R udeks_native_console_record
#endif
#define P (R+UDEKS_TREQ_PAYLOAD)
/* SDK-private shared sequence/error handling, not kernel imports. */
extern unsigned char udeks_native_request(unsigned char, unsigned char, unsigned char);
extern unsigned char udeks_native_failure(unsigned char);
#define failure udeks_native_failure

unsigned char udeks_poll(unsigned char fd, unsigned int ticks)
{
    unsigned char result;
    if(fd!=UDEKS_STDIN) return failure(UDEKS_TREQ_EBADF);
    if(ticks>600 && ticks!=UDEKS_TREQ_POLL_FOREVER) return failure(UDEKS_TREQ_EINVAL);
    P[0]=1; P[1]=0; P[2]=(unsigned char)ticks; P[3]=(unsigned char)(ticks>>8);
    result=udeks_native_request(UDEKS_TREQ_OP_POLL,fd,4);
    if(result==UDEKS_IO_ERROR) return result;
    if(result>1 || (!result && ticks==UDEKS_TREQ_POLL_FOREVER) || P[0]!=result || P[1] ||
       P[2]!=(unsigned char)ticks || P[3]!=(unsigned char)(ticks>>8))
        return failure(UDEKS_TREQ_EPROTO);
    return result;
}

/* Canonical, blocking stdin: POLL sleeps cooperatively with an owned reply;
 * READ copies from common RAM only after returning to this task's bank. */
unsigned char udeks_read(unsigned char fd, unsigned char *buffer, unsigned char count)
{
    unsigned char result,i;
    if(fd!=UDEKS_STDIN) return failure(UDEKS_TREQ_EBADF);
    if(count>UDEKS_FILE_CHUNK || (!buffer && count)) return failure(UDEKS_TREQ_EINVAL);
    if(!count) { udeks_errno=0; return 0; }
    if(udeks_poll(fd,UDEKS_TREQ_POLL_FOREVER)==UDEKS_IO_ERROR) return UDEKS_IO_ERROR;
    result=udeks_native_request(UDEKS_TREQ_OP_READ,fd,count);
    if(result==UDEKS_IO_ERROR) return result;
    if(result>count) return failure(UDEKS_TREQ_EPROTO);
    for(i=0;i<result;++i) buffer[i]=P[i];
    return result;
}
