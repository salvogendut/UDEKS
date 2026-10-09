/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent, pixel-exact .CBM viewer. No kernel/map imports or app IDs.
 * Stream into an unpublished service transaction; validate EOF and CLOSE
 * before COMMIT. No tile array, full framebuffer or file reads on repaint. */
#include <string.h>
#include "udeks/program.h"
#include "udeks/native_file.h"
#include "udeks/task_request.h"
#include "udeks/banked_graphics.h"

#ifdef UDEKS_NATIVE_CONSOLE_HOST_TEST
extern volatile unsigned char native_console_request[38];
#define R native_console_request
#else
#define R udeks_graphics_record
#endif
#define P (R+14)
#define MAX_WIDTH 240u
#define MAX_HEIGHT 175u
#define TOO_LARGE 253u
#define CLOSED_PICTURE 254u
#define BAD_PICTURE UDEKS_TREQ_ENOEXEC

/* Map exports are only for tests; these are private relocated app bytes. */
unsigned char xview_width, xview_height, xview_ready;
unsigned int xview_uploaded;
static unsigned char row_data[19];
static unsigned char handle,pending;
static unsigned char title[8];
static unsigned char stride;
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern unsigned char gfx_sleep(void);

/* Use the existing small native graphics/file request veneer. A picture
 * viewer needs no canonical input editor, POLL or general stream runtime. */
static unsigned char __fastcall__ read_bytes(unsigned char count)
{
    R[9]=4; R[10]=count;
    return native_file_request(UDEKS_TREQ_OP_READ);
}
static void __fastcall__ output(const char *text)
{
    unsigned char n;
    while(*text) {
        n=0;
        while(*text && n<24) P[n++]=*text++;
        R[9]=2; R[10]=n;
        if(native_file_request(UDEKS_TREQ_OP_WRITE)) return;
    }
}

static unsigned char __fastcall__ exact(unsigned char left)
{
    unsigned char n,i,error,wanted,offset=0;
    while(left) {
        wanted=left;
        error=read_bytes(wanted);
        if(error) return error;
        n=R[11];
        if(n>wanted) return UDEKS_TREQ_EPROTO;
        if(!n) return BAD_PICTURE;
        for(i=0;i<n;++i) row_data[offset+i]=P[i];
        offset+=n; left-=n;
        /* All disk responses are copied before yielding. */
        error=gfx_sleep();
        if(error) return error;
    }
    return 0;
}

static unsigned char header(void)
{
    unsigned char i,error;
    unsigned int width,height;
    error=exact(11);
    if(error) return error;
    for(i=0;i<5;++i) if(row_data[i]!=(unsigned char)"CBM\0\1"[i]) return BAD_PICTURE;
    /* The format allows 1..320 x 1..200. Check both LE bytes before
     * narrowing to the viewer's byte coordinates; do not silently wrap. */
    width=row_data[5]+((unsigned int)row_data[6]<<8);
    height=row_data[7]+((unsigned int)row_data[8]<<8);
    if(!width || width>320 || !height || height>200 || row_data[10] ||
       row_data[9]!=(width+7)/8) return BAD_PICTURE;
    if(width>MAX_WIDTH || height>MAX_HEIGHT) return TOO_LARGE;
    stride=row_data[9];
    xview_width=row_data[5]; xview_height=row_data[7];
    return 0;
}

static unsigned char __fastcall__ fail(unsigned char error)
{
    const unsigned char *message;
    message=(const unsigned char *)(error==TOO_LARGE?"Picture exceeds viewer limits":
        error==BAD_PICTURE?"Invalid CBM picture":
        error==UDEKS_TREQ_ENOENT?"No such file or directory":
        error==UDEKS_TREQ_EISDIR?"Is a directory":
        error==UDEKS_TREQ_ENOMEM?"Not enough display memory":
        error==UDEKS_TREQ_EMFILE || error==UDEKS_TREQ_EBUSY?"Filesystem busy":
        error==UDEKS_TREQ_ENODEV?"No such device":"I/O error");
    output("xview: "); output((const char *)message); output("\n");
    return 1;
}
static void payload(void)
{
    unsigned char i;
    for(i=0;i<24;++i) P[i]=0;
    P[1]=handle;
}
static unsigned char __fastcall__ request(unsigned char op)
{
    return gfx_request(op);
}
static unsigned char window_event(void)
{
    unsigned char result;
    payload(); result=request(UDEKS_GFX_EVENT);
    if(result) return result;
    if(P[0]!=UDEKS_GFX_CLOSED) return 0;
    handle=pending=0;
    return CLOSED_PICTURE;
}
static unsigned char upload(void)
{
    unsigned char result,i,n;
    unsigned int size;
    for(;;) {
        payload(); P[1]=20; P[3]=4;
        P[4]=xview_width<40?48:xview_width+8;
        P[5]=xview_height<31?48:xview_height+17;
        P[6]=UDEKS_GFX_MOVABLE|UDEKS_GFX_CLOSABLE|UDEKS_GFX_FIXED_SIZE;
        for(i=0;i<8;++i) P[7+i]=title[i];
        result=request(UDEKS_GFX_CREATE);
        if(!result) break;
        if(result!=UDEKS_TREQ_EAGAIN) return result;
        result=gfx_sleep();
        if(result) return result;
    }
    handle=R[11];
    payload(); P[2]=xview_width; P[4]=xview_height; P[5]=4; P[7]=14;
    result=request(UDEKS_GFX_BITMAP_BEGIN);
    if(result) return result;
    pending=1;
    size=(unsigned int)stride*xview_height;
    while(xview_uploaded<size) {
        n=size-xview_uploaded>19?19:size-xview_uploaded;
        result=exact(n);
        if(result) return result;
        result=window_event();
        if(result) return result;
        payload(); P[2]=xview_uploaded; P[3]=xview_uploaded>>8; P[4]=n;
        for(i=0;i<n;++i) P[5+i]=row_data[i];
        result=request(UDEKS_GFX_BITMAP_WRITE);
        /* The validated geometry/ordered offsets leave row padding as the
         * only file-data EINVAL. Never publish malformed padding. */
        if(result) return result==UDEKS_TREQ_EINVAL?BAD_PICTURE:result;
        xview_uploaded+=n;
    }
    result=read_bytes(1);
    if(result) return result;
    return R[11]?BAD_PICTURE:0;
}
static unsigned char show(void)
{
    unsigned char result;
    for(;;) {
        result=window_event();
        if(result) return result;
        payload();
        result=request(UDEKS_GFX_BITMAP_COMMIT);
        if(!result) break;
        if(result!=UDEKS_TREQ_EAGAIN) return result;
        result=gfx_sleep();
        if(result) return result;
    }
    pending=0;
    xview_ready=1;
    for(;;) {
        payload();
        result=request(UDEKS_GFX_EVENT);
        if(result) return result;
        if(P[0]==UDEKS_GFX_CLOSED) { handle=0; return 0; }
        result=gfx_sleep();
        if(result) return result;
    }
}
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char fd,error,closed,i,n;
    const unsigned char *name;
    handle=pending=xview_ready=0; xview_uploaded=0;
    if(argc!=2) { output("xview FILE.CBM\n"); return 2; }
    n=0; name=argv[1];
    while(argv[1][n]) {
        if(n==23) return fail(UDEKS_TREQ_EINVAL);
        if(argv[1][n]=='/') name=argv[1]+n+1;
        ++n;
    }
    if(!n) return fail(UDEKS_TREQ_EINVAL);
    for(i=0;i<8;++i) title[i]=0;
    for(i=0;i<8 && name[i] && name[i]!='.';++i) title[i]=name[i];
    for(i=0;i<=n;++i) P[i]=argv[1][i];
    R[9]=0; R[10]=n;
    error=native_file_request(UDEKS_TREQ_OP_OPEN);
    if(error) return fail(error);
    fd=R[11];
    if(fd!=4) {
        if(fd!=3) return fail(UDEKS_TREQ_EPROTO);
        R[9]=fd; R[10]=0;
        native_file_request(UDEKS_TREQ_OP_CLOSE);
        return fail(UDEKS_TREQ_EISDIR);
    }
    error=header();
    if(!error) error=upload();
    R[9]=4; R[10]=0;
    closed=native_file_request(UDEKS_TREQ_OP_CLOSE);
    if(!error) error=closed;
    if(!error) error=show();
    /* A close can race any file/syscall return; acknowledge it quietly. */
    if(error && handle && window_event()==CLOSED_PICTURE) error=CLOSED_PICTURE;
    if(pending) { payload(); request(UDEKS_GFX_BITMAP_ABORT); }
    /* EXIT retires the frame after recording status. Explicit CLOSE here
     * would release foreground ownership before our diagnostic/exit status. */
    return error && error!=CLOSED_PICTURE?fail(error):0;
}
