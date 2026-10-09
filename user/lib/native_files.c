/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Optional native SDK member. A file is owned by the trusted task/generation
 * in the service, not by this library or a task-supplied identity. */
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
extern unsigned char udeks_native_request(unsigned char, unsigned char, unsigned char);
extern unsigned char udeks_native_request_version(unsigned char, unsigned char, unsigned char, unsigned char);
extern unsigned char udeks_native_failure(unsigned char);

unsigned char udeks_open(const unsigned char *path, unsigned char mode)
{
    unsigned char count,result;
    if(!path || (mode!=UDEKS_O_RDONLY && mode!=UDEKS_O_CREATE_EXCL))
        return udeks_native_failure(UDEKS_TREQ_EINVAL);
    count=0;
    while(path[count]) {
        if(count==23) return udeks_native_failure(UDEKS_TREQ_EINVAL);
        ++count;
    }
    if(!count) return udeks_native_failure(UDEKS_TREQ_EINVAL);
    /* Validate the complete path before touching the shared request. */
    for(result=0;result<=count;++result) P[result]=path[result];
    result=udeks_native_request_version(UDEKS_TREQ_OP_OPEN,mode,count,
        mode==UDEKS_O_RDONLY?8:14);
    if(result==UDEKS_IO_ERROR || result==4) return result;
    if(result==3) {
        /* Recovery bootfs can only OPEN directories. Do not retain its
         * unowned fd 3 across a yield: close it in this same SDK call. */
        result=udeks_native_request(UDEKS_TREQ_OP_CLOSE,3,0);
        if(result==UDEKS_IO_ERROR) return result;
        if(!result) return udeks_native_failure(UDEKS_TREQ_EISDIR);
    }
    return udeks_native_failure(UDEKS_TREQ_EPROTO);
}

unsigned char udeks_close(unsigned char fd)
{
    unsigned char result;
    if(fd!=4) return udeks_native_failure(UDEKS_TREQ_EBADF);
    result=udeks_native_request(UDEKS_TREQ_OP_CLOSE,fd,0);
    if(result!=UDEKS_IO_ERROR && result) return udeks_native_failure(UDEKS_TREQ_EPROTO);
    return result;
}
