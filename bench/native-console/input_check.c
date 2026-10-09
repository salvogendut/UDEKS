/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Execute the production 6502 reader and owner check, with guarded buffers. */
#include <stdio.h>
#include <string.h>
#include "udeks/line_editor.h"

unsigned char udeks_line_editor_submitted_text[55];
unsigned char udeks_line_editor_submitted_length_value;
unsigned char udeks_line_editor_submitted_ready_value;
unsigned char udeks_line_editor_submitted_cursor;
unsigned char udeks_shell_foreground_job;
static unsigned char calls,render_error;
unsigned char udeks_root_terminal_input(void) { ++calls; return render_error; }
extern unsigned char udeks_terminal_input_access(void);
static unsigned char output[58];

int main(void)
{
    unsigned int id,cap,len,ready,cases=0;
    unsigned char result,index,fg,expected;
    static const unsigned char masks[]={0,1,2,4,8,3,16,255};
    /* Stub only the trusted caller query, not the ownership instructions. */
    *(unsigned char *)0xc8fc=0xa9; *(unsigned char *)0xc8fe=0x60;
    for(id=0;id<256;++id) for(index=0;index<sizeof(masks);++index) {
        fg=masks[index]; udeks_shell_foreground_job=fg;
        *(unsigned char *)0xc8fd=id; calls=0;
        expected=id<2 ? !fg : id>=3 && id<=6 && fg==(1u<<(id-3));
        result=udeks_terminal_input_access();
        if(result!=(expected?0:5) || calls!=(expected && id>=3)) {
            printf("FAIL owner %u/%u: %u/%u\n",id,fg,result,calls); return 1;
        }
    }
    *(unsigned char *)0xc8fd=3; udeks_shell_foreground_job=1; render_error=2;
    if(udeks_terminal_input_access()!=5) { puts("FAIL render error mapping"); return 5; }
    for(len=0;len<=54;++len) for(cap=0;cap<=56;++cap) for(ready=0;ready<2;++ready) {
        for(index=0;index<55;++index) udeks_line_editor_submitted_text[index]=index+32;
        udeks_line_editor_submitted_text[len]=0;
        memset(output,0xa5,sizeof(output));
        udeks_line_editor_submitted_length_value=len;
        udeks_line_editor_submitted_ready_value=ready;
        udeks_line_editor_submitted_cursor=7;
        expected=!ready?1:cap<=len?2:0;
        result=udeks_line_editor_get_line(output+1,cap);
        if(result!=expected || udeks_line_editor_submitted_ready_value!=(expected?ready:0) ||
           udeks_line_editor_submitted_cursor!=(expected?7:0)) {
            puts("FAIL reader result/state"); return 2;
        }
        for(index=0;index<sizeof(output);++index) {
            unsigned char want=!expected && index>0 && index<=len+1 ?
                udeks_line_editor_submitted_text[index-1]:0xa5;
            if(output[index]!=want) { puts("FAIL reader guard/data"); return 3; }
        }
        ++cases;
    }
    puts("PASS 2048 owner checks (all task ids); 6270 guarded whole-line reads");
    return cases==6270?0:4;
}
