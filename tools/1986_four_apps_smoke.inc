/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real emulated keyboard/1351 input; application RAM is observed, not injected. */
static void four_windows(unsigned count, unsigned panel) {
    wait_byte(0xf246,count,"wrong live window count");
    wait_byte(0xf083,panel,"running panel mask stale");
    frames(500);
}
static void draw_click(unsigned x,unsigned y) {
    client_click(x+12,y+40,0);frames(400);
}
static void draw_state(unsigned bits) {
    for(unsigned i=0;i<24;++i)
        require(byte(0x10000+UDEKS_DRAW_CELLS+i)==((bits>>i)&1),"drawing state differs");
}
static void four_canvas(void) {
    for(unsigned i=0;i<1000 && memcmp(machine->mem.ram+0xa1e0,
                                    machine->mem.ram+0x16000,8000);++i) frames(1);
    require(!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000),
            "four-app bitmap/shadow mismatch");
}
static void four_apps_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete");
    command("xclock &");idle();
    window_gesture(146,107,34,58); /* expose the clock beside later clients */
    command("xwave &");idle();wait_byte(0xf27a,21,"wave incomplete");
    command("xcalc &");idle();four_windows(3,15);
    calc_expression("1.25+2.75=",400);
    command("xdraw &");idle();four_windows(4,31);
    draw_click(226,89);draw_click(306,137);draw_state(1u|(1u<<23));
    command("xdraw &");idle();
    require(console_contains("xdraw: slot busy"),"fifth launch not rejected");
    four_windows(4,31);draw_state(1u|(1u<<23));
    require(calc_value()==400,"capacity rejection changed calculator");
    command("cowsay four alive");idle();
    require(console_contains("four alive"),"four-app console failed");
    command("free");idle();
    require(console_contains("total 2560  used 0  free 2560"),"foreground pool accounting wrong");
    four_canvas();
    window_gesture(238,111,42,131);  /* xdraw (216,65) -> (20,85) */
    draw_state(1u|(1u<<23));four_canvas();
    draw_click(34,177);draw_state(0); /* clear after moving */
    draw_click(112,91);four_windows(3,15);idle();
    command("xdraw &");idle();four_windows(4,31);draw_state(0);
    /* Every executable closes/reloads while its three peers remain live. */
    const char *names[]={"xclock","xwave","xcalc","xdraw"};
    const unsigned masks[]={29,27,23,15};
    for(unsigned i=0;i<4;++i) {
        char line[24];snprintf(line,sizeof line,"%s -q",names[i]);command(line);idle();
        four_windows(3,masks[i]);
        snprintf(line,sizeof line,"%s &",names[i]);command(line);idle();four_windows(4,31);
        if(i==1) wait_byte(0xf27a,21,"reloaded wave incomplete");
    }
    command("xdraw -q");idle();four_windows(3,15);
    command("xdraw");frames(500);four_windows(4,31);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);idle();four_windows(3,15);
    require(byte(0xf225)==3 && byte(0xf265)==3,"Ctrl+C killed background peer");
    calc_expression("C7.5/2.5=",300);
    command("xdraw &");idle();four_windows(4,31);four_canvas();
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"snapshot failed");
    command("xinit -q");idle();four_windows(0,0);
    for(unsigned b=0x18a00;b<=0x18d00;b+=0x300)
        for(unsigned i=0;i<16;++i)
            require(byte(b+i)==0xa5 && byte(b+0x2b0+i)==0xa5,"private stack guard failed");
    require(!byte(0xf11b),"lifecycle canary failed");
    puts("PASS four apps: native input, drawing, calculator, drag, panel, capacity, independent reload, Ctrl+C, shutdown, guards, bitmap");
}
