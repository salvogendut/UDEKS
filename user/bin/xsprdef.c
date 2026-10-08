/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Eight monochrome sprites. S/L confirm disk Save/Load of /SPRITES.SPR;
 * the list's E button exports a BASIC-compatible /SPRITES.BSV.
 * B keeps the current edit in the session bank and returns to the list.
 * All controls are clickable; no keyboard focus protocol is assumed. */
#include <string.h>
#include "udeks/banked_graphics.h"
#include "xspr_file.h"
#ifndef R
extern volatile unsigned char udeks_graphics_record[38];
#define R udeks_graphics_record
#define P (R+14)
#endif
extern unsigned char __fastcall__ gfx_request(unsigned char op);
extern void gfx_sleep(void);
extern void gfx_yield(void);

#define SPRITES      8
#define SPRITE_BYTES 63
#define CELL         8
#define MAX_COMMANDS 63
#define MAG_X        8
#define MAG_Y        20
#define PRE_X        208
#define PRE_Y        20
#define BTN_S_X      208
#define BTN_S_Y      52
#define BTN_B_Y      78
#define BTN_C_Y      104
#define BTN_I_Y      130
#define BTN_L_Y      156
#define LIST_X       30
#define LIST_Y       80
#define LIST_STEP    26

static unsigned char handle;
unsigned char udeks_xsprdef_bank[SPRITES][SPRITE_BYTES];
#define sprite_bank udeks_xsprdef_bank
/* Exported only in the application's map for reproducible emulator probes. */
unsigned char udeks_xsprdef_pixels[SPRITE_BYTES];
#define edit udeks_xsprdef_pixels
/* LOAD temporarily borrows the private command buffer. The service owns an
 * independent retained copy. No presentation until I/O has closed. */
static union {
    unsigned char commands[MAX_COMMANDS][8];
    unsigned char loaded[SPRITES*SPRITE_BYTES];
} scratch;
#define commands scratch.commands
static unsigned char count;
static unsigned char mode;       /* 0 list, 1 editor */
static unsigned char selected;
unsigned char udeks_xsprdef_dialog; /* 1 save, 2 load, 3 result, 4 export */
unsigned char udeks_xsprdef_file_error;
static unsigned char exporting;
#define confirming udeks_xsprdef_dialog
#define file_error udeks_xsprdef_file_error
static unsigned char pixel_delta, pixel_x, pixel_y;
static unsigned char stroke, stroke_ink, stroke_x, stroke_y;
static unsigned char line_pending, target_x, target_y;
static signed char line_dx, line_dy, line_sx, line_sy, line_error;

/* 3x5 glyphs, one byte per row, low three bits. */
static const unsigned char glyphs[][5] = {
    {7,5,5,5,7},{2,6,2,2,7},{7,1,7,4,7},{7,1,7,1,7},{5,5,7,1,1},
    {7,4,7,1,7},{7,4,7,5,7},{7,1,1,1,1},{7,5,7,5,7},{7,5,7,1,7},
    {2,5,7,5,5},{6,5,6,5,6},{7,4,6,4,7},{3,4,2,1,6},{5,5,5,5,2},
    {6,1,2,0,2},{7,4,4,4,7},{7,2,2,2,7},
    {4,4,4,4,7},{6,5,5,5,6},{7,4,6,4,4},{7,5,7,4,4},
    {6,5,6,5,5},{7,2,2,2,2},{5,7,7,7,5},{7,5,5,5,7},
    {5,5,2,2,2},{5,5,2,5,5},{0,0,0,0,2},{5,5,7,5,5},
    {5,5,5,5,7},{5,5,6,5,5}
};
#define GLYPH_TEXT "0123456789ABESV?CILDFPRTNOYX.HUK"

static const unsigned char row3[21] = {
    0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57, 60
};
static const unsigned char bit_mask[8] = { 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01 };

static void bit_flip(unsigned char *s, unsigned char x, unsigned char y)
{
    unsigned char index = (unsigned char)(row3[y] + (x >> 3));
    s[index] ^= bit_mask[x & 7u];
}

static void fill(unsigned char x, unsigned char y, unsigned char w, unsigned char h,
    unsigned char color)
{
    register unsigned char *c;
    if (count == MAX_COMMANDS) return;
    c = commands[count++];
    c[0] = 0; c[1] = x; c[2] = y; c[3] = w; c[4] = h; c[5] = color; c[6] = 0; c[7] = 0;
}
static void glyph(unsigned char x, unsigned char y, unsigned char ch)
{
    unsigned char i, row;
    register unsigned char *c;
    for (i = 0; GLYPH_TEXT[i] && GLYPH_TEXT[i] != ch; ++i) {}
    if (!GLYPH_TEXT[i] || count == MAX_COMMANDS) return;
    c = commands[count++];
    c[0] = 2; c[1] = x; c[2] = y;
    for (row = 0; row < 5; ++row) c[3 + row] = glyphs[i][row];
}
static void text(unsigned char x, unsigned char y, const char *s)
{
    while (*s) { glyph(x, y, *s++); x = (unsigned char)(x + 7u); }
}
/* A button or picture frame is a black rectangle with a background inset:
 * two retained commands and no extra drawing code. */
static void box(unsigned char x, unsigned char y, unsigned char w, unsigned char h)
{
    fill(x, y, w, h, 0);
    fill((unsigned char)(x + 1u), (unsigned char)(y + 1u),
        (unsigned char)(w - 2u), (unsigned char)(h - 2u), 7);
}

/* Exactly 15 tiles for ANY sprite, including checkerboards and noise. The
 * last tile row is zero-padded, never read beyond the 63-byte definition.
 * Both views, all controls and the sprite number take 50 commands. */
static void emit_sprite(const unsigned char *s, unsigned char ox, unsigned char oy,
    unsigned char cell)
{
    unsigned char x, y, row;
    register unsigned char *c;
    for (y = 0; y < 21u; y += 5u) for (x = 0; x < 3u; ++x) {
        c = commands[count++];
        c[0] = UDEKS_GFX_TILE(cell);
        c[1] = (unsigned char)(ox + x * 8u * cell);
        c[2] = (unsigned char)(oy + y * cell);
        for (row = 0; row < 5u; ++row)
            c[3 + row] = y + row < 21u ? s[row3[y + row] + x] : 0;
    }
}

static void payload(void)
{
    unsigned char i;
    for (i = 0; i < 24u; ++i) P[i] = 0;
    P[1] = handle;
}
static unsigned char present(void)
{
    unsigned char error, color;
    payload();
    P[2] = (unsigned char)((unsigned int)commands);
    P[3] = (unsigned char)((unsigned int)commands >> 8);
    P[4] = count;
    if (pixel_delta) {
        color = edit[row3[pixel_y] + (pixel_x >> 3)] & bit_mask[pixel_x & 7u] ? 0 : 7;
        P[12] = MAG_X + pixel_x*CELL; P[13] = MAG_Y + pixel_y*CELL;
        P[14] = CELL; P[15] = CELL; P[16] = color;
        P[17] = PRE_X + pixel_x; P[18] = PRE_Y + pixel_y;
        P[19] = 1; P[20] = 1; P[21] = color;
        error = gfx_request(UDEKS_GFX_PRESENT_DELTA);
        if (!error) pixel_delta = 0;
        return error;
    }
    return gfx_request(UDEKS_GFX_PRESENT);
}
static unsigned char list_present(void)
{
    unsigned char i, bx;
    count = 0;
    for (i = 0; i < SPRITES; ++i) {
        bx = (unsigned char)(LIST_X + i * LIST_STEP);
        box(bx, LIST_Y, 20, 20);
        glyph((unsigned char)(bx + 7u), (unsigned char)(LIST_Y + 5u), (unsigned char)('1' + i));
    }
    box(80,120,24,25); glyph(89,127,'S');
    box(140,120,24,25); glyph(149,127,'L');
    box(200,120,24,25); glyph(209,127,'E');
    return present();
}
static unsigned char editor_present(void)
{
    unsigned char i;
    count = 0;
    box(MAG_X - 1u, MAG_Y - 1u, 194, 170);
    emit_sprite(edit, MAG_X, MAG_Y, CELL);
    box((unsigned char)(PRE_X - 2u), (unsigned char)(PRE_Y - 2u), 28, 25);
    emit_sprite(edit, PRE_X, PRE_Y, 1);
    glyph(236,24,(unsigned char)('1'+selected));
    for (i = 0; i < 5u; ++i) {
        unsigned char by = (unsigned char)(BTN_S_Y + i * 26u);
        box(BTN_S_X, by, 24, 25);
        glyph(BTN_S_X + 9u, (unsigned char)(by + 7u), "SBCIL"[i]);
    }
    return present();
}
static unsigned char dialog_present(void)
{
    const char *message;
    count=0;
    box(36,50,176,104);
    message=confirming==1?"SAVE SPRITES?":"LOAD SPRITES?";
    if(confirming==4) message="EXPORT BASIC?";
    if(confirming==3) {
        switch(file_error) {
        case 0: message="DONE"; break;
        case 2: message="NO SUCH FILE"; break;
        case 8: message="BAD FILE SIZE"; break;
        case 16: message="DISK BUSY"; break;
        case 17: message="FILE EXISTS"; break;
        case 28: message="DISK FULL"; break;
        case 30: message="READ ONLY"; break;
        default: message="DISK ERROR";
        }
    }
    text(50,66,message); text(50,86,exporting?"SPRITES.BSV":"SPRITES.SPR");
    box(76,116,40,24); glyph(92,123,confirming==3?'B':'Y');
    if(confirming!=3) { box(134,116,40,24); glyph(150,123,'N'); }
    if(mode) glyph(236,24,(unsigned char)('1'+selected));
    return present();
}
static void copy_sprite(unsigned char *dst, const unsigned char *src)
{
    unsigned char i;
    for (i = 0; i < SPRITE_BYTES; ++i) dst[i] = src[i];
}

/* Shared hit testing for the live event loop and host behavioural tests.
 * Bounds match the drawn controls exactly; confirmation freezes the edit. */
static unsigned char click_at(unsigned char x, unsigned char y)
{
    unsigned char i, bx;
    pixel_delta = 0;
    if(confirming) {
        if(y<116 || y>=140) return 0;
        if(x>=134 && x<174 && confirming!=3) { confirming=0; return 1; }
        if(x<76 || x>=116) return 0;
        if(confirming==3) { confirming=0; return 1; }
        if(confirming==1 || confirming==4) {
            if(mode) copy_sprite(sprite_bank[selected],edit);
            file_error=xspr_file(exporting?XSPR_EXPORT:XSPR_SAVE,sprite_bank[0]);
        } else {
            file_error=xspr_file(0,scratch.loaded);
            if(!file_error) {
                memcpy(sprite_bank,scratch.loaded,sizeof(sprite_bank));
                if(mode) copy_sprite(edit,sprite_bank[selected]);
            }
        }
        confirming=3;
        return 1;
    }
    if (!mode) {
        if(y>=120 && y<145) {
            if(x>=80 && x<104) confirming=1;
            else if(x>=140 && x<164) confirming=2;
            else if(x>=200 && x<224) confirming=4;
            else return 0;
            exporting=confirming==4;
            return 1;
        }
        for (i = 0; i < SPRITES; ++i) {
            bx = (unsigned char)(LIST_X + i * LIST_STEP);
            if (x >= bx && x < bx + 20u && y >= LIST_Y && y < LIST_Y + 20u) {
                selected = i;
                copy_sprite(edit, sprite_bank[i]);
                mode = 1; confirming = 0;
                return 1;
            }
        }
    } else if (!confirming && x >= MAG_X && x < MAG_X + 24u * CELL &&
               y >= MAG_Y && y < MAG_Y + 21u * CELL) {
        pixel_x = (x - MAG_X) / CELL; pixel_y = (y - MAG_Y) / CELL;
        bit_flip(edit, pixel_x, pixel_y);
        pixel_delta = 1;
        return 1;
    } else if (x >= BTN_S_X && x < BTN_S_X + 24u) {
        if (y >= BTN_S_Y && y < BTN_S_Y + 25u) {
            confirming = 1; exporting = 0;
        } else if (y >= BTN_B_Y && y < BTN_B_Y + 25u) {
            copy_sprite(sprite_bank[selected],edit);
            mode = 0;
        } else if (!confirming && y >= BTN_C_Y && y < BTN_C_Y + 25u) {
            for (i = 0; i < SPRITE_BYTES; ++i) edit[i] = 0;
        } else if (!confirming && y >= BTN_I_Y && y < BTN_I_Y + 25u) {
            for (i = 0; i < SPRITE_BYTES; ++i) edit[i] ^= 255u;
        } else if(y>=BTN_L_Y && y<BTN_L_Y+25u) {
            confirming=2; exporting=0;
        } else return 0;
        return 1;
    }
    return 0;
}

/* Advance only one changed cell per presentation. Every step uses the fast
 * two-fill path; there is no full-window repaint during a long stroke. */
static unsigned char stroke_next(void)
{
    unsigned char index,mask;
    signed char twice;
    while(line_pending) {
        if(stroke_x==target_x && stroke_y==target_y) { line_pending=0; break; }
        twice=line_error*2;
        if(twice>-line_dy) { line_error-=line_dy; stroke_x+=line_sx; }
        if(twice<line_dx) { line_error+=line_dx; stroke_y+=line_sy; }
        index=row3[stroke_y]+(stroke_x>>3); mask=bit_mask[stroke_x&7u];
        if(((edit[index]&mask)!=0)!=stroke_ink) {
            edit[index]^=mask;
            pixel_x=stroke_x;pixel_y=stroke_y;pixel_delta=1;
            return 1;
        }
    }
    return 0;
}

/* A stroke chooses draw/erase from the first pixel, then keeps that ink until
 * release or leaving the grid. Held input never activates toolbar/dialogs.
 * Interpolate skipped cells so faster movement cannot leave holes. */
static unsigned char input_at(unsigned char state, unsigned char x, unsigned char y)
{
    unsigned char changed;
    if(state==UDEKS_GFX_CLICK) {
        stroke=0;line_pending=0;
        changed=click_at(x,y);
        if(pixel_delta) {
            stroke=1; stroke_x=pixel_x; stroke_y=pixel_y;
            stroke_ink=(edit[row3[pixel_y]+(pixel_x>>3)] & bit_mask[pixel_x&7u])!=0;
        }
        return changed;
    }
    if(state!=UDEKS_GFX_HELD || !mode || confirming ||
       x<MAG_X || x>=MAG_X+24u*CELL || y<MAG_Y || y>=MAG_Y+21u*CELL) {
        stroke=0;line_pending=0;
        return 0;
    }
    if(!stroke) return 0;
    target_x=(x-MAG_X)/CELL; target_y=(y-MAG_Y)/CELL;
    line_sx=stroke_x<target_x?1:-1;line_sy=stroke_y<target_y?1:-1;
    line_dx=stroke_x<target_x?target_x-stroke_x:stroke_x-target_x;
    line_dy=stroke_y<target_y?target_y-stroke_y:stroke_y-target_y;
    line_error=line_dx-line_dy;line_pending=1;
    return stroke_next();
}

unsigned char udeks_graphical_main(void)
{
    unsigned char i, pending = 0, error;
    payload(); P[1] = 4; P[3] = 4; P[4] = 248; P[5] = 192; P[6] = 0x16;
    for (i = 0; i < 7u; ++i) P[7 + i] = "XSPRDEF"[i];
    if (gfx_request(UDEKS_GFX_CREATE)) return 1;
    handle = R[11];
    mode = 0; confirming = 0; pixel_delta = 0; exporting = 0; stroke = 0; line_pending=0;
    if (list_present()) return 2;
    for (;;) {
        if(!pending && line_pending) pending=stroke_next();
        if (!pending) {
            payload(); P[2] = 248; P[4] = 192; /* acknowledge our fixed geometry */
            if (gfx_request(UDEKS_GFX_INPUT)) return 3;
            if (!P[0]) return 0;
            if(P[2] || (P[0]==UDEKS_GFX_HELD && P[7])) stroke=0;
            else pending=input_at(P[0],P[1],P[3]);
        }
        if (pending) {
            error = confirming ? dialog_present() : mode ? editor_present() : list_present();
            if (!error) pending = 0;
            /* Drag/capture/paste is temporarily frozen: retain this edit and
             * yield before retrying, never toggle the pixel twice. */
            else if (error != 11) return 4;
        }
        if(line_pending) gfx_yield(); else gfx_sleep();
    }
}
