/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/bitmap_store.h"
unsigned char bitmap_guarded[2306];
unsigned int bitmap_lengths[4];
static struct udeks_bitmap_store store={bitmap_guarded+1,bitmap_lengths};
void bitmap_reset(void)
{
    memset(bitmap_guarded,0xa5,sizeof(bitmap_guarded));
    memset(bitmap_lengths,0,sizeof(bitmap_lengths));
}
unsigned char bitmap_request(unsigned char index,const unsigned char *request)
{ return udeks_bitmap_request(&store,index,request); }
const unsigned char *bitmap_view(unsigned char index)
{ return udeks_bitmap_view(&store,index); }
void bitmap_discard(unsigned char index)
{ udeks_bitmap_discard(&store,index); }
