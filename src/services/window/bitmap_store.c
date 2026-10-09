/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Unlinked first increment: packed storage/transaction semantics. No new
 * physical allocation and no executable placement is implied by this file. */
#include <string.h>
#include "udeks/bitmap_store.h"
#include "udeks/task_request.h"

static unsigned int le16(const unsigned char *p)
{
    return p[0]|((unsigned int)p[1]<<8);
}
static unsigned int offset(struct udeks_bitmap_store *s,unsigned char index)
{
    unsigned int result=0;
    while(index) result+=s->lengths[--index]&UDEKS_BITMAP_LENGTH;
    return result;
}
static void resize(struct udeks_bitmap_store *s,unsigned char index,unsigned int size)
{
    unsigned int start=offset(s,index),old=s->lengths[index]&UDEKS_BITMAP_LENGTH;
    unsigned int end=offset(s,UDEKS_BITMAP_CLIENTS);
    memmove(s->pool+start+size,s->pool+start+old,end-start-old);
    s->lengths[index]=size;
}
static unsigned char zeroes(const unsigned char *p,unsigned char start)
{
    while(start<24) if(p[start++]) return 0;
    return 1;
}
void udeks_bitmap_discard(struct udeks_bitmap_store *s,unsigned char index)
{
    if(index<UDEKS_BITMAP_CLIENTS) resize(s,index,0);
}
const unsigned char *udeks_bitmap_view(struct udeks_bitmap_store *s,unsigned char index)
{
    if(index>=UDEKS_BITMAP_CLIENTS ||
       (s->lengths[index]&~UDEKS_BITMAP_LENGTH)!=UDEKS_BITMAP_FORMAT) return 0;
    return s->pool+offset(s,index);
}
unsigned char udeks_bitmap_request(struct udeks_bitmap_store *s,
    unsigned char index,const unsigned char *p)
{
    unsigned int size,received,at,x;
    unsigned char *header;
    unsigned char i,count,stride,padding;
    if(index>=UDEKS_BITMAP_CLIENTS) return UDEKS_TREQ_EINVAL;
    if(p[0]==UDEKS_BITMAP_BEGIN) {
        /* P[2..3] width LE16, P[4] height, P[5..6] x LE16, P[7] y.
         * Narrow coordinates are intentional for this first window-sized API. */
        x=le16(p+5);
        if(p[3] || !p[2] || p[2]>240 || !p[4] || p[4]>175 ||
           x>320u-p[2] || p[7]>200u-p[4] || !zeroes(p,8))
            return UDEKS_TREQ_EINVAL;
        if(s->lengths[index]) return UDEKS_TREQ_EBUSY;
        stride=(p[2]+7u)/8u;
        size=UDEKS_BITMAP_HEADER+(unsigned int)stride*p[4];
        if(size>UDEKS_BITMAP_POOL_BYTES-offset(s,UDEKS_BITMAP_CLIENTS))
            return UDEKS_TREQ_ENOMEM;
        resize(s,index,size);
        header=s->pool+offset(s,index);
        header[0]=p[5]; header[1]=p[6]; header[2]=p[7];
        header[3]=p[2]; header[4]=p[4]; header[5]=stride;
        header[6]=header[7]=0;
        s->lengths[index]|=UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING;
        return 0;
    }
    if((s->lengths[index]&~UDEKS_BITMAP_LENGTH)!=
       (UDEKS_BITMAP_FORMAT|UDEKS_BITMAP_PENDING)) return UDEKS_TREQ_EINVAL;
    header=s->pool+offset(s,index);
    size=(s->lengths[index]&UDEKS_BITMAP_LENGTH)-UDEKS_BITMAP_HEADER;
    received=le16(header+6);
    if(p[0]==UDEKS_BITMAP_WRITE) {
        at=le16(p+2); count=p[4];
        if(!count || count>UDEKS_BITMAP_CHUNK || at!=received || at>size ||
           count>size-at || !zeroes(p,5u+count)) return UDEKS_TREQ_EINVAL;
        stride=header[5];
        padding=header[3]&7u;
        if(padding) padding=(1u<<(8u-padding))-1u;
        /* Check the whole chunk before writing even its first byte. */
        for(i=0;i<count;++i)
            if((at+i+1u)%stride==0 && (p[5+i]&padding)) return UDEKS_TREQ_EINVAL;
        memcpy(header+UDEKS_BITMAP_HEADER+at,p+5,count);
        received+=count; header[6]=received; header[7]=received>>8;
        return 0;
    }
    if(!zeroes(p,2)) return UDEKS_TREQ_EINVAL;
    if(p[0]==UDEKS_BITMAP_COMMIT) {
        if(received!=size) return UDEKS_TREQ_EINVAL;
        s->lengths[index]&=~UDEKS_BITMAP_PENDING;
        return 0;
    }
    if(p[0]==UDEKS_BITMAP_ABORT) {
        resize(s,index,0);
        return 0;
    }
    return UDEKS_TREQ_EINVAL;
}
