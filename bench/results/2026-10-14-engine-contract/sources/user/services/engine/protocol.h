/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_ENGINE_PROTOCOL_H
#define UDEKS_ENGINE_PROTOCOL_H
#include "udeks/task_request.h"
#define ENGINE_VERSION 1u
#define ENGINE_REQUEST 1u
#define ENGINE_REPLY 2u
#define ENGINE_STOP 3u
#define ENGINE_ACK 4u
#define ENGINE_HEADER 8u
#define ENGINE_SAMPLES_MAX 8u
#define ENGINE_WAIT 600u
/* Request: version, kind, sequence LE16, worker opcode, arg0, arg1, count.
 * Reply: version, REPLY, sequence LE16, errno, result LE16, sample count,
 * followed by up to eight samples. STOP/ACK have zero bytes 4..7. */
static unsigned char engine_validate(const unsigned char *p,unsigned char n)
{
    if(n!=8 || p[0]!=ENGINE_VERSION || !(p[2]|p[3]))return UDEKS_TREQ_EPROTO;
    if(p[1]==ENGINE_STOP || p[1]==ENGINE_ACK)
        return (p[4]|p[5]|p[6]|p[7])?UDEKS_TREQ_EINVAL:0;
    if(p[1]!=ENGINE_REQUEST)return UDEKS_TREQ_EPROTO;
    if(p[4]==0)return (p[5]|p[6]|p[7])?UDEKS_TREQ_EINVAL:0;
    if(p[4]!=4)return UDEKS_TREQ_ENOSYS;
    return (!p[7] || p[7]>ENGINE_SAMPLES_MAX)?UDEKS_TREQ_EINVAL:0;
}
#endif
