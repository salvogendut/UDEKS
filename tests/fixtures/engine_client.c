/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_engine.h"
#include <string.h>
unsigned char udeks_errno,engine_cli_test_error;
unsigned char udeks_write_bytes(unsigned char fd,const unsigned char *data,unsigned char count)
{ (void)fd;(void)data;udeks_errno=0;return count; }
unsigned char udeks_engine_wave(unsigned char phase,unsigned char step,unsigned char count,unsigned char *samples,unsigned int *result)
{
    static const unsigned char expected[8]={250,0,6,9,14,19,23,25};
    (void)phase;(void)step;
    if(engine_cli_test_error) { udeks_errno=engine_cli_test_error;return 255; }
    memcpy(samples,expected,count);*result=50;return 0;
}
unsigned char udeks_engine_nop(void)
{ udeks_errno=engine_cli_test_error;return engine_cli_test_error?255:0; }
unsigned char udeks_engine_stop(void) { return udeks_engine_nop(); }
