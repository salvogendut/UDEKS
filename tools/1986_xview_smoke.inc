/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real native keyboard/1351 input only; no patched UDEKS memory or replies. */
static void view_dump(const char *tag,const void *bytes,unsigned size) {
    char path[1024];snprintf(path,sizeof path,"%s/%s.bin",getenv("UDEKS_XVIEW_OUTPUT"),tag);
    FILE *f=fopen(path,"wb");require(f!=NULL,"open evidence");
    require(fwrite(bytes,1,size,f)==size,"write evidence");require(fclose(f)==0,"close evidence");
}
static void view_pixels(const char *name,unsigned x,unsigned y,const char *tag) {
    unsigned char file[8012];char path[1024];
    snprintf(path,sizeof path,"%s/%s.CBM",getenv("UDEKS_XVIEW_PICTURES"),name);
    FILE *f=fopen(path,"rb");require(f!=NULL,"expected CBM missing");
    unsigned n=fread(file,1,sizeof file,f);fclose(f);
    unsigned w=file[5]+256*file[6],h=file[7]+256*file[8],stride=file[9];
    require(n==11+stride*h && x+w<=320 && y+h<=200,"bad oracle geometry");
    bool good=false;
    for(unsigned tries=0;tries<10000;++tries) {
        good=!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000);
        for(unsigned yy=0;good && yy<h;++yy) for(unsigned xx=0;xx<w;++xx) {
            unsigned offset=((y+yy)/8)*320+((x+xx)/8)*8+(y+yy)%8;
            if(!!(byte(0x16000+offset)&(128>>((x+xx)%8)))!=
               !!(file[11+yy*stride+xx/8]&(128>>(xx%8)))) {good=false;break;}
        }
        if(good) break;
        frames(1);
    }
    require(good,"CBM pixels/shadow mismatch");view_dump(tag,machine->mem.ram+0x16000,8000);
    printf("PASS pixels %s %ux%u at %u,%u\n",tag,w,h,x,y);fflush(stdout);
}
static void view_ready(unsigned base,unsigned windows) {
    wait_byte(0xf246,windows,"viewer window count");
    wait_byte(base+UDEKS_XVIEW_READY,1,"viewer not ready");
    for(unsigned n=0;n<16;++n)
        require(byte((base==0x18000?0x18f00:0x13400)+n)==0xa5 &&
                byte((base==0x18000?0x18fb0:0x134b0)+n)==0xa5,"viewer C stack guards");
}
static void view_stopped(unsigned task,unsigned windows) {
    wait_byte(slots+(task-1)*8+1,0,"viewer task not retired");
    wait_byte(0xf246,windows,"viewer window not retired");
    require(!word(UDEKS_XVIEW_LENGTHS+(task-3)*2),"retained allocation leaked");
}
static void view_uploading(void) {
    unsigned uploaded=0;
    for(unsigned n=0;n<10000;++n) {
        uploaded=word(0x18000+UDEKS_XVIEW_UPLOADED);
        if((word(UDEKS_XVIEW_LENGTHS+4)&0x6000)==0x6000 && uploaded>=19 && uploaded<1280) break;
        frames(1);
    }
    require(uploaded>=19 && uploaded<1280 && !byte(0x18000+UDEKS_XVIEW_READY),"missed mid-upload window");
    printf("PASS active upload %u bytes\n",uploaded);fflush(stdout);
}
static void view_cancel(void) {
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);idle();
    require(byte(0xf17a)==130,"viewer cancellation status");
}
static void xview_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete");idle();
    storage_command("xview",2);storage_command("xview /missing.cbm",1);
    const char *bad[]={"bad","trail","pad","trunc","big"};
    for(unsigned n=0;n<5;++n) {
        char line[40];snprintf(line,sizeof line,"xview /%s.cbm",bad[n]);storage_command(line,1);
        view_stopped(5,0);
    }
    command("xview /alex128.cbm &");idle();view_ready(0x18000,1);
    view_pixels("ALEX128",24,18,"initial");
    unsigned char saved[1288];memcpy(saved,machine->mem.ram+0x1300,sizeof saved);
    storage_command("xview /clock160.cbm",1);
    require(console_contains("Not enough display memory"),"OOM message");view_stopped(3,1);
    require(!memcmp(saved,machine->mem.ram+0x1300,sizeof saved),"OOM damaged peer");
    window_gesture(37,48,67,78);view_pixels("ALEX128",54,48,"dragged");
    command("xclock &");idle();wait_byte(0xf246,2,"clock cover");frames(500);
    command("xclock -q");idle();wait_byte(0xf246,1,"clock close");
    view_pixels("ALEX128",54,48,"uncovered");
    require(!memcmp(saved,machine->mem.ram+0x1300,sizeof saved),"move/uncover changed image");
    command("xview -q");idle();view_stopped(5,0);
    const char *names[]={"CLOCK160","ODD","DENSE"};
    const char *commands[]={"xview /clock160.cbm &","xview /odd.cbm &","xview /dense.cbm &"};
    for(unsigned n=0;n<3;++n) {
        command(commands[n]);idle();view_ready(0x18000,1);view_pixels(names[n],24,18,names[n]);
        command("xview -q");idle();view_stopped(5,0);
    }
    command("xview /alex128.cbm &");idle();view_ready(0x18000,1);
    window_gesture(37,48,197,48);view_pixels("ALEX128",184,18,"aside");
    command("xview /clockwork.cbm");view_ready(0x12300,2);
    view_pixels("CLOCKWORK",24,18,"second");view_pixels("ALEX128",184,18,"pair");
    view_cancel();view_stopped(3,1);view_pixels("ALEX128",184,18,"survivor");
    command("xview -q");idle();view_stopped(5,0);
    command("xview /alex2.cbm &");idle();view_ready(0x18000,1);
    command("xclock &");idle();command("xwave &");idle();wait_byte(0xf246,3,"viewer/clock/wave");
    for(unsigned n=0;n<10000 && (word(UDEKS_XVIEW_LENGTHS)&0x1fff)!=1128;++n) frames(1);
    require((word(UDEKS_XVIEW_LENGTHS)&0x1fff)==1128 && word(UDEKS_XVIEW_LENGTHS+2),"peers not published");
    command("xwave -q");idle();command("xclock -q");idle();
    view_pixels("ALEX2",24,18,"small-uncovered");command("xview -q");idle();view_stopped(5,0);
    command("xview /alex128.cbm");view_uploading();view_cancel();view_stopped(5,0);
    storage_command("cat /hello",0);
    /* Position before launch so real mouse movement cannot miss the upload. */
    pointer_to(160,48);command("xview /alex128.cbm");view_uploading();
    client_click(160,48,0);idle();view_stopped(5,0);
    storage_command("cat /hello",0);
    require(!byte(0xf11b),"kernel canary");
    command("echo packed viewer passed");idle();
    require(console_contains("packed viewer passed"),"console after native mouse");
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"viewer snapshot");
    puts("PASS packed xview: large/odd/dense files, errors, OOM isolation, native drag/uncover, peers, pending Ctrl+C/close, stream reuse, guards");
}
