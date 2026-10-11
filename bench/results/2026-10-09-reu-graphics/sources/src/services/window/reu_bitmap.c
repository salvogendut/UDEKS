/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Serialized bitmap service in bank-0 RAM beneath I/O. Kernel-flat entry;
 * only the bounded assembly I/O gate selects devices/another physical bank. */
#include "udeks/reu.h"
#include "udeks/reu_store.h"
#include "udeks/reu_bitmap.h"

uint16_t udeks_bitmap_handles[4];
unsigned char udeks_bitmap_row_buffer[30];
unsigned int udeks_bitmap_row_offset;
unsigned char *udeks_bitmap_transfer_buffer;
extern unsigned char udeks_bitmap_io_gate(void);

unsigned char udeks_reu_store_io(unsigned char direction, uint16_t address,
                                unsigned char *bytes, uint16_t count)
{
    /* Only public <=19-byte uploads and <=30-byte renderer rows use this
     * binding. $4180-$419D is outside both pointer templates and cache code. */
    if (!count || count > 30u) return 22;
    udeks_reu_request[0]=direction; udeks_reu_request[1]=1;
    udeks_reu_request[2]=0x80; udeks_reu_request[3]=0x41;
    udeks_reu_request[4]=address; udeks_reu_request[5]=address>>8;
    udeks_reu_request[6]=0;
    udeks_reu_request[7]=count; udeks_reu_request[8]=0;
    udeks_bitmap_transfer_buffer=bytes;
    return udeks_bitmap_io_gate();
}

void __fastcall__ udeks_bitmap_release_hidden(unsigned char index)
{
    if(index>=4) return;
    udeks_reu_store_release_owner(index+1u);
    udeks_bitmap_handles[index]=0;
}

unsigned char __fastcall__ udeks_bitmap_fetch_row(unsigned char index)
{
    return udeks_reu_store_read(index+1u,udeks_bitmap_handles[index],
        udeks_bitmap_row_offset,udeks_bitmap_row_buffer,udeks_bitmap_row_stride);
}
