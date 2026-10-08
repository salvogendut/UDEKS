/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real cc65 C/ASM client, with a simulated CF30 gate (no filesystem IO). */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "udeks/program.h"
#include "udeks/task_request.h"
#include "udeks/file_mutation.h"
#define R ((volatile unsigned char *)0xf359)
static unsigned char calls, failed, scenario, operation, sequence = 250;
static const unsigned char *destination;

static void gate(void)
{
    unsigned char i, op = R[7];
    ++calls;
    ++sequence;
    if (R[0]!='U' || R[1]!='T' || R[2]!='R' || R[3]!='Q' || R[4] ||
        R[6]!=1 || R[8]!=sequence || R[11] || R[12] ||
        R[13]!=(scenario==6 && calls==3 ? 1 : 0)) failed=1;
    if (calls==1) {
        if (op!=6 || R[5]!=14 || R[9] || R[10]!=4 ||
            R[14]!='/' || R[15]!='s' || R[16]!='r' || R[17]!='c' || R[18]) failed=1;
        R[6]=scenario==3 ? 128 : 2;
        R[12]=scenario==3 ? 2 : 0;
        R[11]=scenario==3 ? 0 : 4;
    } else if (calls==2) {
        if (op!=operation || R[5]!=18 || R[9]!=4) failed=1;
        if (operation==UDEKS_FILE_UNLINK) {
            if (R[10]) failed=1;
        } else {
            if (R[10]!=strlen((const char *)destination)) failed=1;
            for (i=0;i<=R[10] && i<24;++i) if (R[14+i]!=destination[i]) failed=1;
        }
        R[6]=(scenario==1 || scenario==4 || scenario==5) ? 128 : 2;
        R[12]=scenario==1 ? 30 : scenario==5 ? 38 : 0;
        R[11]=scenario==2 ? 2 : scenario==6 ? 1 : 0;
    } else if (scenario==6 && calls==3) {
        if (op!=operation || R[5]!=18 || R[9]!=4 || R[10]) failed=1;
        R[6]=2; R[11]=0;
    } else {
        if (calls!=(scenario==6 ? 4 : 3) || op!=9 || R[5]!=14 || R[9]!=4 || R[10]) failed=1;
        R[6]=128;
        R[12]=scenario==1 ? 5 : 9; /* cannot hide operation's primary error */
    }
}

int main(void)
{
    unsigned char result, expected, n, cases=0;
    uint16_t entry = (uint16_t)gate;
    volatile unsigned char *vector = (volatile unsigned char *)0xcf30;
    vector[0]=0x4c; vector[1]=entry; vector[2]=entry>>8;
    *(volatile unsigned char *)0xf358=0x5a;
    *(volatile unsigned char *)0xf37f=0xa5;
    R[8]=sequence;
    for (operation=25;operation<=27;++operation) {
        for (scenario=0;scenario<7;++scenario) {
            destination=(const unsigned char *)(scenario & 1 ? "abcdefghijklmnopqrstuvw" : "/mnt/new");
            calls=0;
            if (operation==25) result=udeks_rename((const unsigned char *)"/src",destination);
            else if (operation==26) result=udeks_copy((const unsigned char *)"/src",destination);
            else result=udeks_unlink((const unsigned char *)"/src");
            expected=scenario==1 ? 30 : scenario==3 ? 2 : scenario==5 ? 38 : scenario && scenario!=6 ? 5 : 0;
            if (result!=(expected ? 255 : 0) || udeks_errno!=expected ||
                calls!=(scenario==3 ? 1 : scenario==6 ? 4 : 3) || failed) {
                printf("FAIL case %u op %u mode %u result %u errno %u calls %u gate %u\n",
                       cases,operation,scenario,result,udeks_errno,calls,failed);
                return 1;
            }
            ++cases;
        }
    }
    for (n=0;n<3;++n) {
        calls=0;
        destination=n==0 ? 0 : (const unsigned char *)(n==1 ? "" : "abcdefghijklmnopqrstuvwx");
        if (udeks_copy((const unsigned char *)"/src",destination)!=255 || udeks_errno!=22 || calls) {
            puts("FAIL invalid destination submitted to gate"); return 1;
        }
        ++cases;
    }
    if (*(volatile unsigned char *)0xf358!=0x5a || *(volatile unsigned char *)0xf37f!=0xa5) {
        puts("FAIL request guards");return 1;
    }
    printf("PASS %u SDK scenarios: cc65 stack, CF30 records, versions, sequence wrap, errors, cleanup, guards\n",cases);
    return 0;
}
