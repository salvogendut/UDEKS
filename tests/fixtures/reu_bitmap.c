/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real bitmap adapter/store/allocator; only physical DMA is substituted. */
#include "retained_bitmap.c"
#define udeks_reu_store_io mock_transport
#include "../../bench/reu/store_mock.c"
#undef udeks_reu_store_io
unsigned char udeks_reu_request[9],udeks_bitmap_row_stride;
extern unsigned char *udeks_bitmap_transfer_buffer;
unsigned char udeks_bitmap_io_gate(void)
{
    return mock_transport(udeks_reu_request[0],udeks_reu_request[4] |
        ((unsigned int)udeks_reu_request[5]<<8),udeks_bitmap_transfer_buffer,
        udeks_reu_request[7]);
}
void udeks_bitmap_release(unsigned char index)
{
    udeks_bitmap_release_hidden(index);
}
