/* SPDX-License-Identifier: GPL-3.0-or-later */
volatile unsigned char ipc_test_record[38];
unsigned char udeks_errno;
unsigned int ipc_test_calls;
unsigned char ipc_test_action,ipc_test_count,ipc_test_sent[24];
unsigned char ipc_test_error,ipc_test_data_count=4,ipc_test_bad_offset=255,ipc_test_bad_value;
unsigned char ipc_test_reply_count=255,ipc_test_result_count=255,ipc_test_reply_state=255;
unsigned int ipc_test_handle=0x1234,ipc_test_sender=0x4321;
void udeks_native_console_gate(void)
{
    unsigned char i,count;
    ++ipc_test_calls;ipc_test_action=ipc_test_record[9];ipc_test_count=ipc_test_record[10];
    for(i=0;i<24;++i)ipc_test_sent[i]=ipc_test_record[14+i];
    count=0;
    if(ipc_test_action<2) {
        count=2;ipc_test_record[14]=ipc_test_handle;ipc_test_record[15]=ipc_test_handle>>8;
    } else if(ipc_test_action==3) {
        count=2+ipc_test_data_count;
        ipc_test_record[14]=ipc_test_sender;ipc_test_record[15]=ipc_test_sender>>8;
        for(i=0;i<22;++i)ipc_test_record[16+i]=i*17;
    }
    ipc_test_record[6]=ipc_test_error?128:2;
    ipc_test_record[11]=ipc_test_error?0:count;
    ipc_test_record[12]=ipc_test_error;
    ipc_test_record[10]=ipc_test_error?ipc_test_count:count;
    if(ipc_test_reply_state!=255)ipc_test_record[6]=ipc_test_reply_state;
    if(ipc_test_reply_count!=255)ipc_test_record[10]=ipc_test_reply_count;
    if(ipc_test_result_count!=255)ipc_test_record[11]=ipc_test_result_count;
    if(ipc_test_bad_offset<38)ipc_test_record[ipc_test_bad_offset]=ipc_test_bad_value;
}
