/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native keyboard/1351 input only: no app, queue or request injection. */
static void xspr_canvas(void) {
    for(unsigned n=0;n<10000 && memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000);++n)
        frames(1);
    require(!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000),"sprite bitmap/shadow mismatch");
}
static void xspr_cell(unsigned char *image,unsigned sx,unsigned sy,bool ink) {
    for(unsigned pane=0;pane<2;++pane) {
        unsigned scale=pane?1:8,ox=pane?208:8;
        for(unsigned dy=0;dy<scale;++dy) for(unsigned dx=0;dx<scale;++dx) {
            unsigned x=4+ox+sx*scale+dx,y=4+20+sy*scale+dy;
            unsigned off=(y/8)*320+(x/8)*8+y%8,mask=128>>(x%8);
            if(ink) image[off]|=mask;else image[off]&=~mask;
        }
    }
}
static void xspr_expect(const unsigned char *expected) {
    for(unsigned n=0;n<10000 && (memcmp(expected,machine->mem.ram+0x16000,8000) ||
            memcmp(expected,machine->mem.ram+0xa1e0,8000));++n) frames(1);
    require(!memcmp(expected,machine->mem.ram+0x16000,8000) &&
            !memcmp(expected,machine->mem.ram+0xa1e0,8000),"held stroke bitmap mismatch");
}
/* Do not enqueue the same correction repeatedly while a graphics request is
 * in flight. Wait for the previous relative motion to be sampled, otherwise
 * the harness itself overshoots outside the canvas and ends the stroke. */
static void xspr_pointer_to(unsigned x,unsigned y) {
    for(unsigned attempt=0;attempt<200;++attempt) {
        unsigned oldx=word(0xf1d8),oldy=byte(0xf1da);
        int dx=(int)x-oldx,dy=(int)y-oldy;
        if(abs(dx)<=1 && abs(dy)<=1) return;
        if(dx>8) dx=8;if(dx<-8) dx=-8;
        if(dy>8) dy=8;if(dy<-8) dy=-8;
        joyports_mouse_motion(&machine->joyports,0,dx,dy);
        for(unsigned n=0;n<200 && word(0xf1d8)==oldx && byte(0xf1da)==oldy;++n) frames(1);
        require(word(0xf1d8)!=oldx || byte(0xf1da)!=oldy,"held pointer motion not sampled");
    }
    require(0,"held pointer failed to converge");
}
static void xsprdef_smoke(void) {
    const unsigned coordinates[][2]={{0,0},{23,20},{7,7},{8,8},{12,10}};
    unsigned char expected[8000];
    wait_byte(0xf3e0,2,"startup incomplete");idle();
    command("xsprdef &");idle();wait_byte(0xf246,1,"editor window missing");
    frames(500);
    client_click(4+222+12,4+90+40,3); /* centre of sprite 8; joined allocation */
    frames(500);xspr_canvas();
    require(!(byte(0x16000+(24/8)*320+(12/8)*8+24%8)&(128>>(12%8))),"initial sprite must be blank");
    for(unsigned cell=0;cell<5;++cell) for(unsigned toggle=0;toggle<2;++toggle) {
        unsigned sx=coordinates[cell][0],sy=coordinates[cell][1];
        pointer_to(4+8+sx*8+4+12,4+20+sy*8+4+40);
        xspr_canvas();memcpy(expected,machine->mem.ram+0x16000,8000);
        for(unsigned pane=0;pane<2;++pane) {
            unsigned scale=pane?1:8,ox=pane?208:8;
            for(unsigned dy=0;dy<scale;++dy) for(unsigned dx=0;dx<scale;++dx) {
                unsigned x=4+ox+sx*scale+dx,y=4+20+sy*scale+dy;
                expected[(y/8)*320+(x/8)*8+y%8]^=128>>(x%8);
            }
        }
        unsigned compositions=word(0xf25e),started=c128_frame_count;
        joyports_mouse_button(&machine->joyports,0,false,true);
        wait_byte(0xf24d,1,"sprite mouse press missed");
        joyports_mouse_button(&machine->joyports,0,false,false);
        wait_byte(0xf24d,0,"sprite mouse release missed");
        for(unsigned n=0;n<10000 && (memcmp(expected,machine->mem.ram+0x16000,8000) ||
                memcmp(expected,machine->mem.ram+0xa1e0,8000));++n) frames(1);
        require(!memcmp(expected,machine->mem.ram+0x16000,8000) &&
                !memcmp(expected,machine->mem.ram+0xa1e0,8000),"pixel edit changed wrong bitmap region");
        require(word(0xf25e)==compositions,"pixel edit repainted entire window");
        printf("native pixel %u,%u toggle %u: %u PAL frames, no full composition\n",
            sx,sy,toggle,c128_frame_count-started);fflush(stdout);
        frames(20);
    }
    xspr_canvas();memcpy(expected,machine->mem.ram+0x16000,8000);
    unsigned stroke_compositions=word(0xf25e);
    /* Real 1351 held button: no app/queue writes, including interpolation,
     * retracing, stationary hold, release and erase on the next stroke. */
    for(unsigned ink=1;ink<=2;++ink) {
        xspr_pointer_to(4+8+4+12,4+20+4+40);
        joyports_mouse_button(&machine->joyports,0,false,true);
        wait_byte(0xf24d,1,"paint press missed");
        xspr_cell(expected,0,0,ink==1);xspr_expect(expected);
        xspr_pointer_to(4+8+23*8+4+12,4+20+4+40);
        for(unsigned x=0;x<24;++x) xspr_cell(expected,x,0,ink==1);
        xspr_expect(expected);frames(100);xspr_expect(expected);
        xspr_pointer_to(4+8+4+12,4+20+4+40);frames(100);xspr_expect(expected);
        joyports_mouse_button(&machine->joyports,0,false,false);
        wait_byte(0xf24d,0,"paint release missed");frames(100);
    }
    xspr_pointer_to(4+8+4+12,4+20+4+40);
    joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf24d,1,"diagonal press missed");
    xspr_cell(expected,0,0,true);xspr_expect(expected);
    /* Equal physical steps keep the expected diagonal independent of sample rate. */
    for(unsigned n=1;n<=20;++n) {
        xspr_pointer_to(4+8+n*8+4+12,4+20+n*8+4+40);
        xspr_cell(expected,n,n,true);xspr_expect(expected);
    }
    /* Leave horizontally first: cells crossed on the way out really ARE part
     * of the stroke. Then travel up outside the grid to the S button. */
    xspr_pointer_to(4+8+23*8+4+12,4+20+20*8+4+40);
    for(unsigned x=21;x<24;++x) xspr_cell(expected,x,20,true);
    xspr_expect(expected);
    xspr_pointer_to(4+220+12,4+20+20*8+4+40);frames(100);
    /* Holding over S must not open a dialog; returning cannot start a stroke. */
    xspr_pointer_to(4+220+12,4+64+40);frames(100);xspr_expect(expected);
    xspr_pointer_to(4+8+23*8+4+12,4+20+4+40);frames(100);xspr_expect(expected);
    joyports_mouse_button(&machine->joyports,0,false,false);
    wait_byte(0xf24d,0,"toolbar release missed");frames(100);
    require(word(0xf25e)==stroke_compositions,"held stroke caused full composition");
    puts("PASS native held strokes: paint, erase, stationary/retrace, diagonal, toolbar isolation");
    /* Title dragging is still the WM's gesture, never a paint stroke. */
    pointer_to(4+40+12,4+6+40);
    joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf248,1,"editor title drag did not start");
    pointer_to(24+40+12,4+6+40);frames(30);
    joyports_mouse_button(&machine->joyports,0,false,false);
    wait_byte(0xf248,0,"editor title drag did not finish");frames(300);xspr_canvas();
    command("echo editor input alive");idle();
    require(console_contains("editor input alive"),"sprite mouse use broke console input");
    command("xsprdef -q");idle();wait_byte(0xf246,0,"editor close failed");
    require(!byte(0xf11b),"lifecycle canary failure");
    puts("PASS native sprite: ten exact pixel edits, mouse release, console, close");
}

#ifdef UDEKS_XSPRDEF_FILES
static void xspr_click(unsigned x,unsigned y) {
    client_click(4+x+12,4+y+40,3);
    frames(200);
}
static void xspr_dialog(unsigned kind) {
    wait_byte(UDEKS_XSPR_DIALOG,kind,"sprite dialog state mismatch");
    frames(200);xspr_canvas();
}
static void xspr_result(unsigned error) {
    xspr_dialog(3);
    require(byte(UDEKS_XSPR_ERROR)==error,"sprite file errno mismatch");
    xspr_click(92,123);xspr_dialog(0);
}
static void xsprdef_files_smoke(void) {
    unsigned char expected[504]={0};
    bool reboot=getenv("UDEKS_XSPR_REBOOT")!=NULL;
    wait_byte(0xf3e0,2,"startup incomplete");idle();
    command("xsprdef &");idle();wait_byte(0xf246,1,"editor window missing");
    frames(500);xspr_canvas();
    require(!memcmp(machine->mem.ram+UDEKS_XSPR_BANK,expected,504),"fresh bank not blank");
    expected[441]=128;expected[503]=1;
    if(reboot) {
        xspr_click(152,132);xspr_dialog(2);
        xspr_click(92,123);xspr_result(0);
        xspr_click(222,90);
    } else {
        xspr_click(222,90); /* sprite 8 */
        xspr_click(12,24);xspr_click(196,184);
        require(!memcmp(machine->mem.ram+UDEKS_XSPR_PIXELS,expected+441,63),"mouse edit mismatch");
        xspr_click(220,64);xspr_dialog(1);
        xspr_click(150,123);xspr_dialog(0); /* cancel */
        xspr_click(220,64);xspr_click(92,123);xspr_result(30); /* read-only */
        xspr_click(220,168);xspr_click(92,123);xspr_result(2); /* missing */
        require(!memcmp(machine->mem.ram+UDEKS_XSPR_PIXELS,expected+441,63),"failed load changed edit");
        command("mount -o remount,rw 8 /");idle();
        xspr_click(220,64);xspr_click(92,123);xspr_result(0);
        xspr_click(20,24);
        require(byte(UDEKS_XSPR_PIXELS)==192,"extra edit missing");
        xspr_click(220,64);xspr_click(92,123);xspr_result(17); /* exclusive create */
        xspr_click(220,168);xspr_click(150,123);xspr_dialog(0);
        require(byte(UDEKS_XSPR_PIXELS)==192,"cancelled load changed edit");
        xspr_click(220,168);xspr_click(92,123);xspr_result(0);
        xspr_click(220,90); /* B: bank list */
        xspr_click(212,132);xspr_dialog(4);
        xspr_click(150,123);xspr_dialog(0); /* export cancellation */
        xspr_click(212,132);xspr_click(92,123);xspr_result(0);
        xspr_click(212,132);xspr_click(92,123);xspr_result(17);
        command("mount -o remount,ro 8 /");idle();
        xspr_click(212,132);xspr_click(92,123);xspr_result(30);
        xspr_click(222,90); /* inspect sprite 8 again */
    }
    require(!memcmp(machine->mem.ram+UDEKS_XSPR_BANK,expected,504),"loaded bank differs");
    require(!memcmp(machine->mem.ram+UDEKS_XSPR_PIXELS,expected+441,63),"loaded edit differs");
    xspr_canvas();
    command("echo sprite files alive");idle();
    require(console_contains("sprite files alive"),"file dialogs broke keyboard input");
    command("xsprdef -q");idle();wait_byte(0xf246,0,"editor close failed");
    require(!byte(0xf11b),"lifecycle canary failure");
    puts("PASS native sprite files: mouse dialogs, BASIC export, exact bank, console, close");
}
#endif
