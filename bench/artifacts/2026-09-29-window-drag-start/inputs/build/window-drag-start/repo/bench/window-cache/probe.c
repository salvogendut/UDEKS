/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "cache.h"
#ifndef CASE
#define CASE 0
#endif
#define RESULT ((volatile unsigned char *)0x7FC0u)
#define SHADOW ((unsigned char *)0xA1E0u)
#define STAGE ((volatile unsigned char *)0xF400u)
#define ADDRESS (*(volatile unsigned int *)0xF380u)
#define COUNT (*(volatile unsigned char *)0xF382u)
#if CASE < 8
#define SX (8u+CASE)
#define SY (16u+CASE)
#define DX (112u+7u-CASE)
#define DY (80u+CASE)
#define WIDTH 168u
#define HEIGHT 104u
#elif CASE == 8
#define SX 303u
#define SY 189u
#define DX 0u
#define DY 0u
#define WIDTH 17u
#define HEIGHT 11u
#elif CASE == 9
#define SX 319u
#define SY 199u
#define DX 319u
#define DY 199u
#define WIDTH 1u
#define HEIGHT 1u
#else
#define SX 7u
#define SY 7u
#define DX 100u
#define DY 40u
#define WIDTH 220u
#define HEIGHT 160u
#endif
#define IMAGE_END (0x4200u + ((WIDTH+7u)/8u)*HEIGHT)
#pragma bss-name(push, "VICSHADOW")
unsigned char cache_probe_shadow[8000];
#pragma bss-name(pop)
extern void raster_timer_start(void);
extern void raster_timer_stop(void);

static unsigned char service_ok(void)
{
    unsigned int i;
    for (i = 0; i < 256u; ++i)
        if (STAGE[i] != (unsigned char)(i * 3u + 1u)) return 0;
    return 1;
}

static void guard_write(unsigned int address, unsigned char value)
{
    ADDRESS = address;
    COUNT = 1;
    STAGE[0] = value;
    cache_transfer(0);
    cache_transfer(2);
}

static unsigned char guard_read(unsigned int address)
{
    unsigned char result;
    ADDRESS = address;
    COUNT = 1;
    cache_transfer(1);
    result = STAGE[0];
    cache_transfer(2);
    return result;
}

int main(void)
{
    unsigned int i;
    for (i = 0; i < 64u; ++i) RESULT[i] = 0;
    RESULT[0]='W'; RESULT[1]='C'; RESULT[2]='A'; RESULT[3]='C';
    RESULT[4]=1; RESULT[5]=1; RESULT[6]=CASE;
    /* Unlike a native disk boot, the raw launcher has no stage 1 to install
     * the preconfiguration profiles used by the common gateway. */
    *(volatile unsigned char *)0xD501u = 0x3Eu;
    *(volatile unsigned char *)0xD504u = 0x7Fu;
    for (i = 0; i < 256u; ++i) STAGE[i] = (unsigned char)(i * 3u + 1u);
    cache_seed_service();
    guard_write(0x41FFu, 0x5Au);
    guard_write(IMAGE_END, 0xA5u);
    guard_write(0x5C00u, 0xC3u);
    for (i = 0; i < 8000u; ++i) SHADOW[i] = (unsigned char)(i * 13u + 7u);
    for (i = 0; i < 32u; ++i) ((unsigned char *)0xE190u)[i] = 0;
    raster_timer_start();
    if (!cache_capture(SX, SY, WIDTH, HEIGHT)) RESULT[7]=1;
    raster_timer_stop();
    for (i = 0; i < 4u; ++i) RESULT[18u+i]=RESULT[8u+i];
    if (!service_ok()) RESULT[7]=2;
    for (i = 0; i < 8000u; ++i) SHADOW[i] = (unsigned char)(i * 31u + 19u);
    raster_timer_start();
    if (!cache_paste(DX, DY)) RESULT[7]=3;
    raster_timer_stop();
    for (i = 0; i < 4u; ++i) RESULT[22u+i]=RESULT[8u+i];
    if (!service_ok()) RESULT[7]=4;
    RESULT[12]=guard_read(0x41FFu);
    RESULT[13]=guard_read(IMAGE_END);
    RESULT[14]=*(volatile unsigned char *)0xFF00u;
    RESULT[15]=service_ok();
    if (cache_paste(320u, 200u) || cache_capture(0, 0, 320u, 200u))
        RESULT[7]=5;
    else RESULT[16]=1;
    RESULT[17]=guard_read(0x5C00u);
    for (i = 0; i < 8000u; ++i) RESULT[64u+i]=SHADOW[i];
    for (i = 0; i < 32u; ++i) RESULT[8064u+i]=((unsigned char *)0xE190u)[i];
    RESULT[5]=2;
    return 0;
}
