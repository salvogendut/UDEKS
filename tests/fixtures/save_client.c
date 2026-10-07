/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#include "udeks/program.h"
unsigned char udeks_errno, test_error, test_close_error, test_short, test_corrupt;
unsigned char test_opens, test_closes, test_writes, test_modes[4], test_fd;
unsigned char test_data[4096], test_message[256];
unsigned int test_size, test_pos;
void test_reset(void)
{
    udeks_errno=test_error=test_close_error=test_short=test_corrupt=0;
    test_opens=test_closes=test_writes=0;
    test_size=test_pos=0; test_message[0]=0;
}
unsigned char udeks_open(const unsigned char *path,unsigned char mode)
{
    (void)path;
    test_modes[test_opens++]=mode;
    test_pos=0;
    return 4;
}
unsigned char udeks_write_bytes(unsigned char fd,const unsigned char *data,unsigned char count)
{
    (void)fd; ++test_writes;
    if(test_error) { udeks_errno=test_error; return 255; }
    if(test_short) count/=2;
    memcpy(test_data+test_size,data,count); test_size+=count;
    return count;
}
unsigned char udeks_read(unsigned char fd,unsigned char *data,unsigned char count)
{
    (void)fd;
    if(test_size-test_pos<count) count=test_size-test_pos;
    memcpy(data,test_data+test_pos,count); test_pos+=count;
    if(test_corrupt && count) data[0]^=1;
    return count;
}
unsigned char udeks_close(unsigned char fd)
{
    (void)fd; ++test_closes;
    udeks_errno=test_close_error;
    return test_close_error ? 255 : 0;
}
unsigned char udeks_write(unsigned char fd,const unsigned char *text)
{
    test_fd=fd; strcat((char *)test_message,(const char *)text); return 0;
}
unsigned char udeks_write_byte(unsigned char fd,unsigned char value)
{
    unsigned char text[2]={value,0}; return udeks_write(fd,text);
}
