/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent, pixel-exact .CBM viewer. No kernel/map imports or app IDs.
 * Decode completely before CREATE; retain tiles, not an open file or an
 * 8 KiB bitmap. Blank tiles are omitted, never nonblank pixels. */
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
#define BAD_PICTURE UDEKS_TREQ_ENOEXEC

/* Map exports are only for tests; these are private relocated app bytes. */
unsigned char xview_commands[UDEKS_GFX_COMMANDS][8];
unsigned char xview_count, xview_width, xview_height, xview_ready;
static unsigned char row_data[MAX_WIDTH/8], tile_index[MAX_WIDTH/8];
static unsigned char handle;
static unsigned char title[8];
static const unsigned char padding_masks[8]={0,127,63,31,15,7,3,1};
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
        wanted=left>24?24:left;
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

static unsigned char decode(void)
{
    unsigned char stride,row,col,y,i,error,padding,n;
    unsigned int width,height;
    unsigned char *c;
    xview_count=0;
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
    padding=padding_masks[xview_width&7u];
    for(y=0;y<xview_height;y+=5) {
        memset(tile_index,255,sizeof(tile_index));
        for(row=0;row<5u && (unsigned char)(y+row)<xview_height;++row) {
            error=exact(stride);
            if(error) return error;
            if(row_data[stride-1]&padding) return BAD_PICTURE;
            for(col=0;col<stride;++col) {
                if(!row_data[col]) continue;
                n=tile_index[col];
                if(n==255) {
                    if(xview_count==UDEKS_GFX_COMMANDS) return TOO_LARGE;
                    n=tile_index[col]=xview_count++;
                    c=xview_commands[n];
                    c[0]=UDEKS_GFX_TILE(1); c[1]=4u+col*8u; c[2]=14u+y;
                    memset(c+3,0,5);
                }
                xview_commands[n][3+row]=row_data[col];
            }
        }
    }
    error=read_bytes(1);
    if(error) return error;
    n=R[11];
    return n?BAD_PICTURE:0;
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
static unsigned char show(void)
{
    unsigned char result,i;
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
    for(;;) {
        payload();
#ifndef UDEKS_NATIVE_CONSOLE_HOST_TEST
        P[2]=(unsigned int)xview_commands; P[3]=(unsigned int)xview_commands>>8;
#endif
        P[4]=xview_count;
        result=request(UDEKS_GFX_PRESENT);
        if(!result) break;
        if(result!=UDEKS_TREQ_EAGAIN) return result;
        result=gfx_sleep();
        if(result) return result;
    }
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
    handle=0; xview_ready=0;
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
    error=decode();
    R[9]=4; R[10]=0;
    closed=native_file_request(UDEKS_TREQ_OP_CLOSE);
    if(!error) error=closed;
    if(!error) error=show();
    if(handle) { payload(); request(UDEKS_GFX_CLOSE); }
    return error?fail(error):0;
}
