/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private per-task runtime. Never give a bank-1 pointer to a bank-0 veneer. */
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
extern void udeks_native_console_gate(void);

unsigned char udeks_errno;
static unsigned char sequence;

static unsigned char failure(unsigned char error)
{
    udeks_errno=error;
    return UDEKS_IO_ERROR;
}

static unsigned char request(unsigned char operation, unsigned char fd,
                             unsigned char count)
{
    unsigned char expected;
    expected=++sequence;
    R[0]='U'; R[1]='T'; R[2]='R'; R[3]='Q'; R[4]=0; R[5]=3;
    R[7]=operation; R[8]=expected; R[9]=fd; R[10]=count;
    R[11]=0; R[12]=0; R[13]=0;
    R[6]=UDEKS_TREQ_STATE_REQUEST;
    udeks_native_console_gate();
    /* WRITE is synchronous. SLEEP's owned response is restored on resumption.
     * YIELD does not currently restore a private reply, so do not use this
     * helper for it or read another task's common record after a raw yield. */
    if(R[0]!='U' || R[1]!='T' || R[2]!='R' || R[3]!='Q' || R[4] ||
       R[7]!=operation || R[8]!=expected || R[9]!=fd || R[10]!=count || R[13])
        return failure(UDEKS_TREQ_EPROTO);
    if(R[6]==UDEKS_TREQ_STATE_ERROR && R[12]) return failure(R[12]);
    if(R[6]!=UDEKS_TREQ_STATE_COMPLETE || R[12]) return failure(UDEKS_TREQ_EPROTO);
    udeks_errno=0;
    return R[11];
}

unsigned char udeks_write_bytes(unsigned char fd, const unsigned char *buffer,
                               unsigned char count)
{
    unsigned char i,result;
    if(fd!=UDEKS_STDOUT && fd!=UDEKS_STDERR) return failure(UDEKS_TREQ_EBADF);
    if(count>UDEKS_FILE_CHUNK || (!buffer && count)) return failure(UDEKS_TREQ_EINVAL);
    for(i=0;i<count;++i) P[i]=buffer[i];
    result=request(UDEKS_TREQ_OP_WRITE,fd,count);
    if(result!=UDEKS_IO_ERROR && result>count) return failure(UDEKS_TREQ_EPROTO);
    return result;
}

unsigned char udeks_write_byte(unsigned char fd, unsigned char value)
{
    return udeks_write_bytes(fd,&value,1)==1 ? 0 : 1;
}

unsigned char udeks_write(unsigned char fd, const unsigned char *text)
{
    unsigned char count;
    if(fd!=UDEKS_STDOUT && fd!=UDEKS_STDERR) { failure(UDEKS_TREQ_EBADF); return 1; }
    if(!text) { failure(UDEKS_TREQ_EINVAL); return 1; }
    udeks_errno=0;
    while(*text) {
        count=0;
        while(count<UDEKS_FILE_CHUNK && text[count]) ++count;
        if(udeks_write_bytes(fd,text,count)!=count) {
            if(!udeks_errno) failure(UDEKS_TREQ_EIO);
            return 1;
        }
        text+=count;
    }
    return 0;
}

unsigned char udeks_sleep(unsigned int ticks)
{
    unsigned char result;
    if(!ticks || ticks>UDEKS_TREQ_SLEEP_TICKS_MAX) return failure(UDEKS_TREQ_EINVAL);
    P[0]=(unsigned char)ticks; P[1]=(unsigned char)(ticks>>8);
    result=request(UDEKS_TREQ_OP_SLEEP,0,2);
    if(result!=UDEKS_IO_ERROR && result) return failure(UDEKS_TREQ_EPROTO);
    return result;
}
