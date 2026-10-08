/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native keyboard and 1351, no injected requests or lifecycle state. */
static void capacity_owners(unsigned a,unsigned b,unsigned c,unsigned d) {
    const unsigned expected[]={a,b,c,d};
    for(unsigned i=0;i<4;++i)
        wait_byte(UDEKS_NATIVE_OWNED+i,expected[i],"wrong native memory ownership");
}
static void capacity_guards(void) {
    for(unsigned i=0;i<16;++i)
        require(byte(0x13f00+i)==0xa5 && byte(0x13fb0+i)==0xa5,"large C stack guard");
    require(byte(0x1d600)==0xa5,"large CPU stack guard");
    require(!byte(0xf11b),"root/child guard");
}
static void capacity_canvas(void) {
    frames(500);
    require(!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000),
            "large client shadow/bitmap mismatch");
}
static void native_capacity_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete");idle();
    command("large &");idle();wait_byte(0xf246,1,"large window missing");
    wait_byte(UDEKS_LARGE_READY,0xa5,"large client not ready");
    require(!byte(UDEKS_LARGE_ERROR),"large client validation failed");
    capacity_owners(2,3,0,0);capacity_guards();capacity_canvas();
    unsigned x=40,y=32;
    for(unsigned i=0;i<4;++i) {
        unsigned nx=48+i*13,ny=40+i*9;
        window_gesture(x+8+12,y+5+40,nx+8+12,ny+5+40);
        x=nx;y=ny;capacity_guards();capacity_canvas();
    }
    command("orbit &");idle();command("canvas &");idle();
    wait_byte(0xf246,3,"three client windows missing");capacity_owners(2,3,2,2);
    command("extra &");idle();require(console_contains("slot busy"),"loan not reserved");
    command("echo capacity input alive");idle();
    require(console_contains("capacity input alive"),"drag broke console input");
    command("large -q");idle();wait_byte(0xf246,2,"large close failed");
    command("orbit &");idle();command("canvas &");idle();
    wait_byte(0xf246,4,"four ordinary clients not restored");capacity_owners(2,2,2,2);
    command("xinit -q");idle();wait_byte(0xf246,0,"shutdown windows");capacity_owners(0,0,0,0);
    command("bigcon");
    wait_byte(UDEKS_BIGCON_READY,0xa5,"large console client not ready");
    require(!byte(UDEKS_BIGCON_ERROR),"large console BSS validation");
    require(!byte(0xf246),"console app created a window");capacity_owners(2,3,0,0);capacity_guards();
    /* Finite console job returns naturally; no synthetic control pokes. */
    idle();capacity_owners(0,0,0,0);
    command("large");wait_byte(UDEKS_LARGE_READY,0xa5,"large reload");
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);idle();
    wait_byte(0xf246,0,"foreground large close");capacity_owners(0,0,0,0);
    /* Existing bundled programs still occupy the four ordinary allocations. */
    command("xclock &");idle();command("xwave &");idle();
    command("xcalc &");idle();command("xdraw &");idle();
    wait_byte(0xf246,4,"bundled four-app regression");capacity_owners(2,2,2,2);
    const unsigned stacks[]={0x13400,0x13f00,0x18f00,0x1cf00};
    for(unsigned task=0;task<4;++task) for(unsigned i=0;i<16;++i)
        require(byte(stacks[task]+i)==0xa5 && byte(stacks[task]+0xb0+i)==0xa5,
                "ordinary stack guard after joined allocation reuse");
    command("xinit -q");idle();wait_byte(0xf246,0,"bundled shutdown");capacity_owners(0,0,0,0);
    command("echo capacity passed");idle();require(console_contains("capacity passed"),"final console");
    puts("PASS native capacity: large graphics/console, four drags, guards, loan rejection/reuse, four small apps, bundled apps, graphical Ctrl+C");
}
