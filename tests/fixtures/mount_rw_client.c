/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char test_device,test_op,test_flags,test_length,test_calls,test_error,test_fd;
unsigned char test_message[256];
void test_reset(void) { test_calls=test_error=0; test_message[0]=0; }
unsigned char udeks_mount_rw_request(unsigned char device,unsigned char op,unsigned char flags,unsigned char length)
{
    test_device=device; test_op=op; test_flags=flags; test_length=length;
    ++test_calls; return test_error;
}
unsigned char udeks_write(unsigned char fd,const unsigned char *text)
{
    test_fd=fd; strcat((char *)test_message,(const char *)text); return 0;
}
unsigned char udeks_write_byte(unsigned char fd,unsigned char value)
{
    unsigned char text[2]={value,0}; return udeks_write(fd,text);
}
