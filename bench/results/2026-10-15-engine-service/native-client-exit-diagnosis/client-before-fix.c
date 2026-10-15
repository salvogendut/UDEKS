/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/native_engine.h"
#include "udeks/task_request.h"
#include <string.h>
unsigned char engine_client_state,engine_client_error,engine_client_samples[8];
unsigned int engine_client_result;
static const unsigned char expected[8]={250,0,6,9,14,19,23,25};
unsigned char udeks_program_main(unsigned char argc,unsigned char **argv)
{
    unsigned char rc,i;
    engine_client_state=1;
    if(argc==1) {
        rc=udeks_engine_wave(250,7,8,engine_client_samples,&engine_client_result);
        if(!rc) {
            for(i=0;i<8;++i)if(engine_client_samples[i]!=expected[i])rc=1;
            if(engine_client_result!=50)rc=1;
            if(rc)udeks_errno=UDEKS_TREQ_EPROTO;
        }
    } else if(argc==2 && !strcmp((const char *)argv[1],"--nop"))rc=udeks_engine_nop();
    else if(argc==2 && !strcmp((const char *)argv[1],"--stop"))rc=udeks_engine_stop();
    else { udeks_write_bytes(UDEKS_STDERR,(const unsigned char *)"engtest [--nop|--stop]\n",23);return 2; }
    if(rc) {
        engine_client_error=udeks_errno;engine_client_state=3;
        udeks_write_bytes(UDEKS_STDERR,(const unsigned char *)"engtest: error\n",15);return udeks_errno?udeks_errno:1;
    }
    engine_client_state=2;udeks_write_bytes(UDEKS_STDOUT,(const unsigned char *)"engtest: OK\n",12);return 0;
}
