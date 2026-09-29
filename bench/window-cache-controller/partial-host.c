/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent pixel oracle for the private prefix command. */
#include <assert.h>
#include <string.h>
#include "udeks/window_cache_flow.h"
#include "udeks/window_cache_command.h"
struct udeks_cache_flow fixed_flow;
struct udeks_cache_lease cache_test_lease;
struct udeks_cache_row cache_test_row;
struct udeks_cache_geometry cache_test_geometry;
uint8_t cache_test_owner, cache_test_eligible, controller_test_phase;
uint8_t flow_test_opcode;
uint16_t cache_test_generation;
uint8_t cache_test_params[14];
extern uint8_t cache_partial_end;
extern uint16_t cache_partial_width;
extern uint8_t udeks_cache_controller(uint8_t);
static uint8_t shadow[8000], image[2224], expected[8000];
static unsigned calls;

static unsigned offset(unsigned x, unsigned y)
{ return (y / 8) * 320 + y % 8 + (x / 8) * 8; }
static unsigned pixel(const uint8_t *p, unsigned x, unsigned y)
{ return !!(p[offset(x,y)] & (128u >> (x & 7))); }
static void set(uint8_t *p, unsigned x, unsigned y, unsigned value)
{
    unsigned o = offset(x,y), mask = 128u >> (x & 7);
    p[o] = (p[o] & ~mask) | (value ? mask : 0);
}
/* Emulate only the qualified primitive, using the produced parameter record.
 * Expected pixels below are calculated directly from the requested rectangle. */
void udeks_cache_overlay_row(void)
{
    unsigned o = cache_test_params[0] | cache_test_params[1] << 8;
    unsigned address = (cache_test_params[2] | cache_test_params[3] << 8) - 0x5350;
    unsigned stride = cache_test_params[4], shift = cache_test_params[6];
    unsigned bits = 0, mask = cache_test_params[7], i, k;
    while (mask & 128) { ++bits; mask = (mask << 1) & 255; }
    assert(stride && stride <= 40 && bits);
    assert(address + stride <= sizeof image);
    assert(cache_test_params[5] == (shift + (stride-1)*8 + bits + 7)/8);
    ++calls;
    if (!cache_test_params[8]) memset(image + address, 0, stride);
    for (i=0;i<(stride-1)*8+bits;++i) {
        unsigned so = o + ((shift+i)/8)*8;
        unsigned sm = 128u >> ((shift+i)&7), im = 128u >> (i&7);
        assert(so < sizeof shadow);
        k = address + i/8;
        if (cache_test_params[8])
            shadow[so] = (shadow[so] & ~sm) | ((image[k]&im) ? sm : 0);
        else if (shadow[so]&sm) image[k] |= im;
    }
}
struct snapshot {
    struct udeks_cache_flow flow;
    struct udeks_cache_lease lease;
    struct udeks_cache_row row;
    uint8_t params[14], end, owner, phase;
    uint16_t width, ticket;
    unsigned calls;
};
static struct snapshot snap(void)
{
    struct snapshot s;
    memset(&s,0,sizeof s);
    s.flow=fixed_flow; s.lease=cache_test_lease; s.row=cache_test_row;
    memcpy(s.params,cache_test_params,sizeof s.params);
    s.end=cache_partial_end; s.width=cache_partial_width;
    s.owner=cache_test_owner; s.phase=controller_test_phase;
    s.ticket=cache_test_generation; s.calls=calls;
    return s;
}
static void reject(unsigned op)
{
    struct snapshot before=snap(), after;
    uint8_t old_shadow[8000], old_image[2224];
    memcpy(old_shadow,shadow,sizeof shadow); memcpy(old_image,image,sizeof image);
    assert(udeks_cache_controller(op)==UDEKS_CACHE_INVALID);
    after=snap(); assert(!memcmp(&before,&after,sizeof before));
    assert(!memcmp(old_shadow,shadow,sizeof shadow));
    assert(!memcmp(old_image,image,sizeof image));
}
static void reject_backend(void)
{
    struct snapshot before=snap(), after;
    uint8_t old_shadow[8000], old_image[2224];
    memcpy(old_shadow,shadow,sizeof shadow); memcpy(old_image,image,sizeof image);
    assert(udeks_cache_overlay_command(4)==UDEKS_CACHE_INVALID);
    after=snap(); assert(!memcmp(&before,&after,sizeof before));
    assert(!memcmp(old_shadow,shadow,sizeof shadow));
    assert(!memcmp(old_image,image,sizeof image));
}
static void range(unsigned first,unsigned end,unsigned width)
{
    cache_test_params[10]=first; cache_test_params[11]=end;
    cache_test_params[12]=width; cache_test_params[13]=width>>8;
}
static void steps(unsigned count)
{
    unsigned i, previous=calls;
    for (i=0;i<count;++i) {
        assert(udeks_cache_controller(4)==UDEKS_CACHE_OK);
        assert(controller_test_phase==(i+1==count ? UDEKS_CACHE_READY :
            (cache_test_row.mode ? UDEKS_CACHE_PASTING : UDEKS_CACHE_CAPTURING)));
    }
    assert(calls==previous+count); reject(4);
}
static void seed(unsigned salt)
{
    unsigned i;
    for(i=0;i<8000;++i)shadow[i]=(i*31+salt) & 255;
}
static void example(unsigned sx,unsigned dx,unsigned width,unsigned first,
                    unsigned end,unsigned prefix)
{
    unsigned x,y,original[104][320];
    unsigned h=width==320 ? 55 : 104;
    struct udeks_cache_lease other, before;
    assert(udeks_cache_controller(0)==UDEKS_CACHE_OK);
    cache_test_owner=1; cache_test_eligible=1;
    cache_test_geometry=(struct udeks_cache_geometry){sx,width,3,h};
    seed(7);
    for(y=0;y<h;++y)for(x=0;x<width;++x)original[y][x]=pixel(shadow,sx+x,3+y);
    assert(udeks_cache_controller(2)==UDEKS_CACHE_OK); steps(h);
    assert(cache_partial_end==0 && cache_partial_width==0);
    other=cache_test_lease; before=other;
    assert(udeks_cache_paste_begin(&other,1,fixed_flow.generation,&cache_test_geometry)==UDEKS_CACHE_INVALID);
    udeks_cache_init(&other,1); udeks_cache_invalidate(&other,0);
    assert(!memcmp(&other,&before,sizeof other));
    assert(udeks_cache_capture_begin(&other,1,1,&cache_test_geometry,1)==UDEKS_CACHE_INVALID);
    seed(19); memcpy(expected,shadow,sizeof shadow);
    cache_test_geometry.x=dx; cache_test_geometry.y=83;
    range(end,end,prefix); reject(6);
    range(first,h+1,prefix); reject(6);
    range(first,end,0); reject(6);
    range(first,end,width+1); reject(6);
    range(first,end,65535); reject(6);
    range(first,end,prefix); cache_test_owner=2; reject(6); cache_test_owner=1;
    cache_test_geometry.x=320; reject(6); cache_test_geometry.x=dx;
    assert(udeks_cache_controller(6)==UDEKS_CACHE_OK);
    assert(cache_test_lease.row==first);
    cache_partial_width=0; reject_backend(); cache_partial_width=prefix;
    cache_partial_end=first; reject_backend(); cache_partial_end=end;
    cache_partial_end=h+1; reject_backend(); cache_partial_end=end;
    cache_partial_width=width+1; reject_backend(); cache_partial_width=prefix;
    cache_test_owner=2; reject(4); cache_test_owner=1;
    --cache_test_generation; reject(4); ++cache_test_generation;
    for(y=first;y<end;++y)for(x=0;x<prefix;++x)set(expected,dx+x,83+y,original[y][x]);
    steps(end-first);
    assert(!memcmp(expected,shadow,sizeof shadow));
    /* A normal paste after a partial paste must restore the full dimensions. */
    seed(23); memcpy(expected,shadow,sizeof shadow);
    assert(udeks_cache_controller(3)==UDEKS_CACHE_OK);
    assert(cache_partial_end==h && cache_partial_width==width);
    for(y=0;y<h;++y)for(x=0;x<width;++x)set(expected,dx+x,83+y,original[y][x]);
    steps(h); assert(!memcmp(expected,shadow,sizeof shadow));
    /* Interrupt a partial paste, cancel it, and start a fresh capture. */
    range(3,9,prefix); assert(udeks_cache_controller(6)==UDEKS_CACHE_OK);
    assert(udeks_cache_controller(4)==UDEKS_CACHE_OK);
    assert(udeks_cache_controller(1)==UDEKS_CACHE_OK);
    assert(cache_partial_end==0 && cache_partial_width==0);
    reject(6);
    cache_test_geometry.y=3;
    cache_test_owner=1;
    assert(udeks_cache_controller(2)==UDEKS_CACHE_OK); steps(h);
}
int main(void)
{
    static const unsigned widths[]={1,7,8,9,17,52,168};
    unsigned i,s,d;
    for(i=0;i<sizeof widths/sizeof widths[0];++i)
        for(s=0;s<8;++s)for(d=0;d<8;++d) {
            example(s,d,widths[i],0,104,widths[i]);
            example(s,d,widths[i],17,67,(widths[i]+1)/2);
            example(s,d,widths[i],103,104,1);
        }
    example(0,0,320,0,55,320);
    example(0,0,320,17,54,52);
    return 0;
}
