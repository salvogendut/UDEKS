/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
#define UDEKS_USH_HOST_TEST
#define UDEKS_RECOVERY
#include "../../user/bin/ush.c"
unsigned char ush_test_memory[65536],udeks_errno;
unsigned char test_submit_result,test_wait_result,test_prompts;
char test_output[1024];
unsigned char udeks_write(unsigned char fd,const unsigned char *p)
{ (void)fd; strncat(test_output,(const char *)p,1023-strlen(test_output)); return 0; }
unsigned char udeks_write_byte(unsigned char fd,unsigned char c)
{ unsigned char p[2]; p[0]=c;p[1]=0;return udeks_write(fd,p); }
unsigned char udeks_prompt(void) { ++test_prompts; return 0; }
unsigned char udeks_wait_foreground(void) { return test_wait_result; }
unsigned char udeks_exec_line(const unsigned char *s,unsigned char n)
{ (void)s;(void)n;return test_submit_result; }
unsigned char submit_request(unsigned char op,unsigned char fd,unsigned char n)
{ (void)op;(void)fd;(void)n;return test_submit_result; }
unsigned char udeks_poll(unsigned char fd,unsigned int n) { (void)fd;(void)n;return 0; }
unsigned char udeks_read(unsigned char fd,unsigned char *b,unsigned char n)
{ (void)fd;(void)b;(void)n;return 0; }
void test_reset(void)
{
    memset(ush_test_memory,0,sizeof(ush_test_memory));
    started=waiting_foreground=last_status=line_length=test_submit_result=test_wait_result=test_prompts=0;
    line[0]=test_output[0]=0;
    udeks_ush_poll();
}
void test_command(const char *s)
{ strcpy((char *)line,s); line_length=strlen(s); test_output[0]=0; dispatch_line(); }
unsigned char test_status(void) { return last_status; }
