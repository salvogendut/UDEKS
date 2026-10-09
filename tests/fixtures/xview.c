/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/task_request.h"
#include "udeks/bitmap_store.h"
volatile unsigned char native_console_request[38];
#define R native_console_request
#define P (R+14)
unsigned char viewer_data[8012],viewer_retained[2304],viewer_geometry[24];
unsigned char viewer_pool[2304],viewer_text[256];
unsigned int viewer_lengths[4];
static struct udeks_bitmap_store store={viewer_pool,viewer_lengths};
unsigned int viewer_size,viewer_offset,viewer_reads,viewer_sleeps,viewer_text_size;
unsigned int viewer_fail_at,viewer_retained_size;
unsigned char viewer_opens,viewer_closes,viewer_creates,viewer_presents,viewer_events,viewer_window_closes;
unsigned char viewer_open_error,viewer_close_error,viewer_present_error,viewer_create_error;
unsigned char viewer_short_read,viewer_sleep_error,viewer_busy,viewer_begin_error;
unsigned char viewer_protocol_failure,viewer_aborts,viewer_begins,viewer_writes;
unsigned char viewer_fd,viewer_oversized_reply;
unsigned char viewer_close_pending;
static unsigned char window_live;
void viewer_retire(void)
{
    if(window_live) ++viewer_window_closes;
    window_live=0; udeks_bitmap_discard(&store,0);
}
void viewer_reset(void)
{
    memset((void *)R,0,38); memset(viewer_text,0,256);
    memset(viewer_retained,0,sizeof(viewer_retained));
    memset(viewer_pool,0,sizeof(viewer_pool)); memset(viewer_lengths,0,sizeof(viewer_lengths));
    viewer_size=viewer_offset=viewer_reads=viewer_sleeps=viewer_text_size=viewer_retained_size=0;
    viewer_opens=viewer_closes=viewer_creates=viewer_presents=viewer_events=viewer_window_closes=0;
    viewer_open_error=viewer_close_error=viewer_present_error=viewer_create_error=0;
    viewer_sleep_error=viewer_busy=viewer_begin_error=viewer_protocol_failure=0;
    viewer_aborts=viewer_begins=viewer_writes=0;
    viewer_short_read=24; viewer_fail_at=65535;
    viewer_fd=4; viewer_oversized_reply=0;
    viewer_close_pending=0;
    window_live=0;
}
void udeks_native_console_gate(void)
{
    unsigned char i,n=0,error=0,payload[24];
    switch(R[7]) {
    case UDEKS_TREQ_OP_OPEN:
        ++viewer_opens; error=viewer_open_error; n=viewer_fd; break;
    case UDEKS_TREQ_OP_READ:
        ++viewer_reads;
        if(viewer_offset>=viewer_fail_at) { error=5; break; }
        n=R[10];
        if(n>viewer_short_read) n=viewer_short_read;
        if(n>viewer_size-viewer_offset) n=viewer_size-viewer_offset;
        for(i=0;i<n;++i) P[i]=viewer_data[viewer_offset++];
        if(viewer_oversized_reply) n=R[10]+1;
        break;
    case UDEKS_TREQ_OP_CLOSE:
        ++viewer_closes; error=viewer_close_error; break;
    case UDEKS_TREQ_OP_SLEEP:
        ++viewer_sleeps; error=viewer_sleep_error;
        memset((void *)P,0xda,24);
        break;
    case UDEKS_TREQ_OP_WRITE:
        n=R[10];
        for(i=0;i<n && viewer_text_size<255;++i) viewer_text[viewer_text_size++]=P[i];
        break;
    case UDEKS_TREQ_OP_GRAPHICS:
        if(R[5]!=20 || R[9] || R[10]!=24) viewer_protocol_failure=1;
        for(i=0;i<24;++i) payload[i]=P[i];
        if(P[0]>=8 && P[0]<=11) {
            if(P[1]!=1) viewer_protocol_failure=1;
            switch(P[0]) {
            case 8: ++viewer_begins; error=viewer_begin_error; break;
            case 9: ++viewer_writes; break;
            case 10:
                ++viewer_presents; error=viewer_present_error;
                if(viewer_busy) { --viewer_busy; error=11; }
                if(viewer_closes!=1 || viewer_close_error || viewer_offset!=viewer_size)
                    viewer_protocol_failure=1;
                break;
            case 11: ++viewer_aborts; break;
            }
            if(!error) error=udeks_bitmap_request(&store,0,payload);
            if(!error && P[0]==10) {
                viewer_retained_size=viewer_lengths[0]&UDEKS_BITMAP_LENGTH;
                memcpy(viewer_retained,viewer_pool,viewer_retained_size);
            }
            memset((void *)P,0xdb,24);
        } else switch(P[0]) {
        case 1:
            ++viewer_creates; error=viewer_create_error; n=1;
            if(!error) window_live=1;
            for(i=0;i<24;++i) viewer_geometry[i]=P[i];
            break;
        case 3:
            if(viewer_lengths[0]&UDEKS_BITMAP_PENDING) P[0]=viewer_close_pending?0:1;
            else { ++viewer_events; P[0]=viewer_events<3?1:0; }
            n=7;
            if(!P[0]) { window_live=0; udeks_bitmap_discard(&store,0); }
            break;
        case 4: ++viewer_window_closes; udeks_bitmap_discard(&store,0); break;
        default: error=22;
        }
        break;
    default: error=38;
    }
    R[6]=error?128:2; R[11]=n; R[12]=error;
}
unsigned char native_file_request(unsigned char op)
{
    memcpy((void *)R,"UTRQ\0\24",6);
    R[6]=1; R[7]=op; ++R[8]; R[13]=0;
    udeks_native_console_gate();
    return R[12];
}
unsigned char gfx_request(unsigned char op)
{
    P[0]=op; R[9]=0; R[10]=24;
    return native_file_request(UDEKS_TREQ_OP_GRAPHICS);
}
unsigned char gfx_sleep(void)
{
    P[0]=2; P[1]=0; R[9]=0; R[10]=2;
    return native_file_request(UDEKS_TREQ_OP_SLEEP);
}
