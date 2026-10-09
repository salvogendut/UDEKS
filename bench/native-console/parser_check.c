/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdio.h>
#include <string.h>
#include "udeks/shell.h"
unsigned char reference_tokenize(unsigned char *,unsigned char *,unsigned char);
static unsigned char input[256],a[258],b[258],ao[10],bo[10];
static unsigned int seed=0x5231,checks;

static unsigned char compare(unsigned char capacity)
{
    unsigned char x,y;
    memset(a,0xa5,sizeof(a)); memset(b,0xa5,sizeof(b));
    memcpy(a+1,input,256); memcpy(b+1,input,256);
    memset(ao,0xa5,sizeof(ao)); memset(bo,0xa5,sizeof(bo));
    x=udeks_shell_tokenize(a+1,ao+1,capacity);
    y=reference_tokenize(b+1,bo+1,capacity);
    ++checks;
    if(x!=y || memcmp(a,b,sizeof(a)) || memcmp(ao,bo,sizeof(ao))) {
        printf("FAIL tokenizer case %u capacity %u: %u/%u\n",checks,capacity,x,y);
        return 1;
    }
    return 0;
}
int main(void)
{
    unsigned int n,i;
    unsigned char capacity,length,value;
    for(n=0;n<1024;++n) {
        length=n%55;
        memset(input,0,sizeof(input));
        for(i=0;i<length;++i) {
            seed=(seed>>1)^((seed&1)?0xb400:0);
            value=(unsigned char)seed;
            input[i]=(value&3)==0?' ':((value&3)==1?9:(value?value:'X'));
        }
        for(capacity=0;capacity<=8;++capacity) if(compare(capacity)) return 1;
    }
    /* Full unsigned-byte range: no early NUL, no line/offset overrun. */
    for(n=0;n<256;++n) {
        memset(input,'X',sizeof(input)); input[n]=0;
        for(capacity=0;capacity<=8;++capacity) if(compare(capacity)) return 1;
    }
    printf("PASS tokenizer: %u CPU comparisons, exact mutation and guards\n",checks);
    return 0;
}
