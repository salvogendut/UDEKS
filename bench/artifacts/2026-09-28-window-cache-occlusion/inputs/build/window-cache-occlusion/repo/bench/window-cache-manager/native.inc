/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native keyboard/1351 only. Read-only pixel/state oracles, no OS patching. */
static unsigned wave_record(void) {
    for(unsigned i=0;i<4;++i) {
        unsigned record=CACHE_WINDOWS+i*17;
        if(byte(record)&&byte(record+1)==2)return record;
    }
    require(0,"no live wave window");return 0;
}
static unsigned wave_x(void) {return word(wave_record()+4);}
static unsigned wave_y(void) {return byte(wave_record()+6);}
static unsigned image_bit(unsigned x,unsigned y) {
    return (byte(0x15350+y*21+x/8)>>(7-(x&7)))&1;
}
static unsigned screen_bit(unsigned base,unsigned x,unsigned y) {
    return (byte(base+(y&248)*40+(y&7)+(x&~7u))>>(7-(x&7)))&1;
}
static void pixel_oracle(void) {
    unsigned x=wave_x(),y=wave_y();
    require(word(wave_record()+7)==168 && byte(wave_record()+9)==104,"oracle geometry changed");
    for(unsigned yy=0;yy<104;++yy)for(unsigned xx=0;xx<168;++xx) {
        require(screen_bit(0xA1E0,x+xx,y+yy)==image_bit(xx,yy),"cache/shadow pixel mismatch");
        require(screen_bit(0x16000,x+xx,y+yy)==image_bit(xx,yy),"cache/VIC pixel mismatch");
    }
    for(unsigned a=0x1523a;a<0x15250;++a)
        require(byte(a)==0,"private state guard overwritten");
    for(unsigned a=0x15340;a<0x15350;++a)
        require(byte(a)==0,"private stack guard overwritten");
}
static void ready(void) {
    for(unsigned n=0;n<10000;++n) {
        wait_byte(CACHE_PHASE,2,"capture/paste did not become READY");
        frames(8);if(byte(CACHE_PHASE)==2)break;
        require(n!=9999,"cached screen never settled");
    }
    require(byte(CACHE_OWNER)==1+(wave_record()-CACHE_WINDOWS)/17,"cache belongs to another window");
}
static unsigned drag_begin(unsigned resize) {
    unsigned before=word(0xF258);
    pointer_to(wave_x()+12+(resize?164:8),wave_y()+40+(resize?100:6));
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==before);++n)frames(1);
    require(byte(0xF248)&&word(0xF258)==((before+1)&65535),"native drag did not begin");
    return word(0xF25A);
}
static unsigned drag_release(unsigned before) {
    unsigned start=c128_frame_count;
    joyports_mouse_button(&machine->joyports,0,false,false);
    for(unsigned n=0;n<10000 && (byte(0xF248)||word(0xF25A)==before);++n)frames(1);
    require(!byte(0xF248)&&word(0xF25A)==((before+1)&65535),"native drag did not finish");
    return c128_frame_count-start;
}
static void drag_stress(unsigned count) {
    (void)count;
    wait_byte(CACHE_ACCEPT,0x80,"resident pre-C acceptance failed");
    command("xwave");
    for(unsigned n=0;n<10000 && byte(CACHE_WINDOWS+18)!=2;++n)frames(1);
    require(byte(0xF27A)<21,"early drag gate not partial");
    unsigned before=drag_begin(0);pointer_to(35+20,19+46);drag_release(before);
    wait_byte(0xF27A,21,"ordinary early-drag fallback did not converge");ready();pixel_oracle();
    require(word(0xF26C)==21 && word(0xF26E)==0,"wave worker failed");
    /* Deferred RESTORE/NMI with the actual installed gateway/C runtime. */
    c128_key_event(machine,SDL_SCANCODE_PAGEUP,true);frames(4);
    c128_key_event(machine,SDL_SCANCODE_PAGEUP,false);frames(4);
    cia_write(&machine->cia2,0xDD04,0);cia_write(&machine->cia2,0xDD05,0x10);
    cia_write(&machine->cia2,0xDD0D,0x81);cia_write(&machine->cia2,0xDD0E,0x11);
    unsigned paints=word(0xF270),max_release=0,max_paste=0;
    for(unsigned i=0;i<16;++i) {
        before=drag_begin(0);
        pointer_to((i*37+3)%153+20,(i*23+1)%97+46);
        unsigned delay=drag_release(before),start=c128_frame_count;
        if(delay>max_release)max_release=delay;
        ready();if(c128_frame_count-start>max_paste)max_paste=c128_frame_count-start;
        pixel_oracle();
        require(word(0xF270)==paints && byte(0xF27A)==21,"cached move called the wave painter");
        require(word(0xF26C)==21,"cached move acquired Z80");
        printf("cache move %u: x=%u y=%u release=%u paste=%u pixels=OK\n",
            i,wave_x(),wave_y(),delay,c128_frame_count-start);fflush(stdout);
    }
    /* Partial paste + Ctrl+C must cancel, without stranding the console. */
    before=drag_begin(0);pointer_to(80+20,30+46);drag_release(before);
    require(byte(CACHE_PHASE)==3,"cancellation gate was not a live paste");
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    wait_byte(0xF265,2,"Ctrl+C did not cancel pasted wave");
    wait_byte(CACHE_PHASE,0,"cancelled cache ownership retained");idle();
    require(byte(0xF225)==3,"cancellation killed background clock");
    cia_write(&machine->cia2,0xDD0E,0);frames(4);cia_write(&machine->cia2,0xDD0D,0x7f);
    (void)cia_read(&machine->cia2,0xDD0D);frames(4);
    require(byte(0xFFF5)==0 && word(0xFFF6)>100,"installed NMI was not drained");
    require(byte(0xF11B)==0,"lifecycle/context canary damaged");
    command("echo console alive");idle();command("xwave &");idle();
    wait_byte(0xF27A,21,"replacement wave did not finish");ready();pixel_oracle();
    /* Enlarged image must use redraw fallback, not overrun the cache lease. */
    before=drag_begin(0);pointer_to(50+20,20+46);drag_release(before);ready();pixel_oracle();
    before=drag_begin(1);pointer_to(wave_x()+12+174,wave_y()+40+109);drag_release(before);
    wait_byte(0xF27A,21,"oversized resize fallback did not finish");
    require(byte(CACHE_PHASE)==0 && word(wave_record()+7)>168,"oversize image was cached");
    require(word(0xF26C)==21,"resize acquired Z80");
    command("xinit -q");idle();require(byte(CACHE_PHASE)==0,"shutdown retained cache");
    command("xinit");idle();command("xwave &");idle();
    wait_byte(0xF27A,21,"restart wave did not finish");ready();pixel_oracle();
    command("echo graphics restarted");idle();
    ready();pixel_oracle();
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"save cache evidence");
    printf("cache latency: release=%u paste=%u PAL frames; NMI drains=%u\n",
        max_release,max_paste,word(0xFFF6));
    puts("PASS: live cached moves, full pixels, fallback, cancellation and restart");
}
