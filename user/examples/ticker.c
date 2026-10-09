/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Independent no-window native task; intentionally unknown to kernel/ush. */
#include "udeks/native_console.h"
#include <string.h>

unsigned char ticker_step, ticker_failure;
unsigned char ticker_private[4];
unsigned char ticker_argc, ticker_argument_check;
unsigned char ticker_arguments[81];

static unsigned char argument_check(unsigned char argc, unsigned char **argv)
{
    unsigned char result=0,i;
    const unsigned char *p;
    for(i=0;i<argc;++i) for(p=argv[i];*p;++p) result=(result<<1)^*p;
    return result;
}

unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    unsigned char i;
    if(!argc || !argv || argv[argc] || ticker_step || ticker_failure) return 90;
    ticker_argc=argc;
    ticker_argument_check=argument_check(argc,argv);
    memcpy(ticker_arguments,(const void *)0x80,sizeof(ticker_arguments));
    for(i=0;i<4;++i) {
        if(ticker_private[i]) return 91;
        ticker_private[i]=0x31u+i;
    }
    if(udeks_write(UDEKS_STDOUT,(const unsigned char *)"ticker: native task started\n")) return 92;
    if(udeks_write(UDEKS_STDERR,(const unsigned char *)"ticker: stderr works\n")) return 93;
    for(i=0;i<argc;++i) {
        udeks_write(UDEKS_STDOUT,(const unsigned char *)"arg: ");
        udeks_write(UDEKS_STDOUT,argv[i]);
        udeks_write_byte(UDEKS_STDOUT,'\n');
    }
    for(ticker_step=1;ticker_step<=5;++ticker_step) {
        if(udeks_write(UDEKS_STDOUT,(const unsigned char *)"tick ") ||
           udeks_write_byte(UDEKS_STDOUT,'0'+ticker_step) ||
           udeks_write_byte(UDEKS_STDOUT,'\n')) { ticker_failure=1; return 94; }
        /* Long enough to observe mouse/clock progress with real input. */
        if(udeks_sleep(120)) { ticker_failure=2; return 95; }
        if(argument_check(argc,argv)!=ticker_argument_check) { ticker_failure=4; return 98; }
        for(i=0;i<4;++i) if(ticker_private[i]!=0x31u+i) { ticker_failure=3; return 96; }
    }
    if(udeks_write(UDEKS_STDOUT,(const unsigned char *)"ticker: complete\n")) return 97;
    return 37;                      /* ordinary native return uses EXIT */
}
