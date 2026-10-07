/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Disk command. The small bootfs recovery mount remains read-only. */
#include <string.h>
#include "udeks/program.h"
unsigned char __fastcall__ udeks_mount_rw_request(unsigned char device, unsigned char op,
                                                unsigned char flags, unsigned char length);
unsigned char udeks_program_main(unsigned char argc, unsigned char **argv)
{
    const unsigned char *name,*p,*path;
    unsigned char op=17,flags=0,arg=1,device=0,error,length;
    name=argv[0]; p=name;
    while(*p) { if(*p++=='/') name=p; }
    if((name[0]|32u)=='u') op=18;
    if(op==17 && argc>2 && !strcmp((const char *)argv[1],"-o")) {
        p=argv[2]; arg=3;
        if(!strcmp((const char *)p,"rw")) flags=1;
        else if(!strcmp((const char *)p,"ro")) flags=0;
        else if(!strcmp((const char *)p,"remount,rw")) flags=3;
        else if(!strcmp((const char *)p,"remount,ro")) flags=2;
        else goto usage;
    }
    if(argc!=arg+1u+(op==17)) goto usage;
    path=argv[argc-1];
    if(!strcmp((const char *)path,"/")) length=1;
    else if(!strcmp((const char *)path,"/mnt")) length=4;
    else goto usage;
    if(op==17) {
        p=argv[arg];
        if(p[0]=='8' && !p[1]) device=8;
        else if(p[0]=='9' && !p[1]) device=9;
        else if(p[0]=='1' && (p[1]=='0'||p[1]=='1') && !p[2]) device=10+p[1]-'0';
        else goto usage;
    }
    error=udeks_mount_rw_request(device,op,flags,length);
    if(error) {
        udeks_write(2,(const unsigned char *)"mount: ");
        udeks_write(2,udeks_error_string(error));
        udeks_write_byte(2,'\n');
        return 1;
    }
    if(op==17) {
        udeks_write(1,(const unsigned char *)"mount: "); udeks_write(1,path);
        udeks_write(1,(const unsigned char *)(flags&1 ? " ready (read-write)\n" : " ready (read-only)\n"));
    }
    return 0;
usage:
    udeks_write(2,(const unsigned char *)"mount [-o ro|rw|remount,ro|remount,rw] 8 /|/mnt\numount /mnt\n");
    return 1;
}
