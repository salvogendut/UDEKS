/* SPDX-License-Identifier: GPL-3.0-or-later */
/* No request/WM injection: actual keyboard and 1351 input, unmodified core. */
static void native_windows(unsigned count) {
    wait_byte(0xf246,count,"wrong native window count");frames(300);
}
static void native_guards(void) {
    const unsigned pages[]={0x13400,0x13f00,0x18f00,0x1cf00};
    const unsigned cpu[]={0x1d600,0x1d800,0x1e200,0x10100};
    for(unsigned task=0;task<4;++task) {
        require(byte(cpu[task])==0xa5,"native hardware stack canary");
        for(unsigned i=0;i<16;++i)
            require(byte(pages[task]+i)==0xa5 && byte(pages[task]+0xb0+i)==0xa5,
                    "native software stack canary");
    }
    require(!byte(0xf11b),"root/foreground stack guard");
}
static void native_canvas(void) {
    for(unsigned n=0;n<10000 && memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000);++n)
        frames(1);
    require(!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000),"native bitmap/shadow mismatch");
}
static void four_native_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete");idle();
    command("xclock &");idle();native_windows(1);
    window_gesture(146,96,42,56);
    command("xwave &");idle();native_windows(2);
    wait_byte(UDEKS_WAVE_PRESENTS,1,"wave initial image missing");
    unsigned leases=word(0xf19c),presents=byte(UDEKS_WAVE_PRESENTS);
    window_gesture(50,74,66,90); /* (28,28) -> approximately (44,44) */
    require(byte(UDEKS_WAVE_PRESENTS)==presents,"move reprojected wave");
    /* Native mouse resize; don't release until WM sampled the final pointer. */
    pointer_to(44+176+9,44+112+37);
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && !byte(0xf248);++n) frames(1);
    require(byte(0xf248),"wave resize did not start");
    pointer_to(44+230+11,44+140+39);frames(40);
    require(byte(UDEKS_WAVE_PRESENTS)==presents,"wave published while outline held");
    joyports_mouse_button(&machine->joyports,0,false,false);
    wait_byte(0xf248,0,"wave resize did not finish");
    wait_byte(UDEKS_WAVE_PRESENTS,presents+1,"wave resize not published");
    require(word(UDEKS_WAVE_WIDTH)>220 && byte(UDEKS_WAVE_HEIGHT)>130,"wave size unchanged");
    require(word(0xf19c)==leases,"move/resize called worker again");
    command("xcalc &");idle();native_windows(3);
    calc_expression("1.25+2.75=",400);
    command("xdraw &");idle();native_windows(4);
    client_click(226+12,89+40,6);
    wait_byte(UDEKS_DRAW_CELLS,1,"drawing click not delivered");
    native_guards();native_canvas();
    command("cowsay four native");idle();
    require(console_contains("four native"),"native mouse use broke console typing");
    command("xclock &");idle();
    require(console_contains("slot busy"),"fifth client not rejected");native_windows(4);
    const char *names[]={"xclock","xwave","xcalc","xdraw"};
    for(unsigned i=0;i<4;++i) {
        char line[24];snprintf(line,sizeof line,"%s -q",names[i]);command(line);idle();native_windows(3);
        snprintf(line,sizeof line,"%s &",names[i]);command(line);idle();native_windows(4);
    }
    command("xdraw -q");idle();native_windows(3);
    command("xdraw");native_windows(4);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);idle();native_windows(3);
    command("xdraw &");idle();native_windows(4);native_guards();native_canvas();
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"snapshot failed");
    command("xinit -q");idle();native_windows(0);
    command("echo input survived");idle();require(console_contains("input survived"),"cleanup console");
    puts("PASS four native: mouse drag/resize, held outline, worker reuse, arithmetic, drawing, console, capacity, reload, Ctrl+C, guards, canvas");
}
