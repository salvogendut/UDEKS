/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <string.h>
#include "udeks/shell.h"
unsigned char udeks_shell_native_argc,udeks_shell_command_line[55],udeks_shell_offsets[8];
void test_copy_args(void);
unsigned char udeks_program_entry(void);
static unsigned char called,failed,saved[81],expected_count;
#define ARGS ((unsigned char *)0x80)

unsigned char udeks_program_main(unsigned char count,unsigned char **argv)
{
    unsigned char i;
    ++called;
    if(count!=expected_count || (unsigned int)argv!=0x88 || argv[count]) { failed=1; return 99; }
    for(i=0;i<count;++i) {
        if((unsigned int)argv[i]!=0x9a+udeks_shell_offsets[i] ||
           strcmp((const char *)argv[i],(const char *)udeks_shell_command_line+udeks_shell_offsets[i])) {
            failed=2; return 98;
        }
    }
    return 37;
}

static unsigned char check(const char *text)
{
    unsigned char count,i,n,last=0;
    memset(udeks_shell_command_line,0x5a,55);
    strcpy((char *)udeks_shell_command_line,text);
    count=udeks_shell_tokenize(udeks_shell_command_line,udeks_shell_offsets,8);
    if(count>8) return 1;
    udeks_shell_native_argc=expected_count=count;
    memset(ARGS,0,81); *(unsigned char *)0x7f=0xa5; *(unsigned char *)0xd1=0x5a;
    test_copy_args();
    if(memcmp(ARGS,"UARG\0\1",6) || ARGS[6]!=count || ARGS[7]) return 2;
    for(i=count*2;i<18;++i) if(ARGS[8+i]) return 3;
    if(count) last=udeks_shell_offsets[count-1]+strlen((const char *)udeks_shell_command_line+udeks_shell_offsets[count-1])+1;
    for(i=last;i<55;++i) if(ARGS[26+i]) return 4; /* no stale source suffix */
    if(*(unsigned char *)0x7f!=0xa5 || *(unsigned char *)0xd1!=0x5a) return 5;
    called=failed=0;
    if(udeks_program_entry()!=37 || called!=1 || failed) return 6;
    memcpy(saved,ARGS,81);
    for(i=0;i<6;++i) {
        ARGS[i]^=0xff;
        n=udeks_program_entry();
        if(n!=126 || called!=1) return 7;
        memcpy(ARGS,saved,81);
    }
    ARGS[6]=9;
    if(udeks_program_entry()!=126 || called!=1) return 8;
    memset(ARGS,0,81); /* old kernel without UARG */
    if(udeks_program_entry()!=126 || called!=1) return 9;
    return 0;
}
int main(void)
{
    unsigned char result,i;
    char text[55];
    const char *cases[]={"", "ticker", "  ticker\tAlpha  B ", "ticker a b c d e f last"};
    for(i=0;i<4;++i) if((result=check(cases[i]))!=0) { printf("FAIL entry case %u: %u\n",i,result); return 1; }
    memcpy(text,"ticker ",7); memset(text+7,'X',47); text[54]=0;
    if((result=check(text))!=0) { printf("FAIL entry length 54: %u\n",result); return 1; }
    puts("PASS argument copy/entry: counts 0/1/3/8, length 54, guards, padding, calling convention, fail-closed ABI");
    return 0;
}
