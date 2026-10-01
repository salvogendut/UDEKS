/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Included by the native raw-IEC harness. All actions use emulated input. */
static unsigned calc_x=108, calc_y=30;
#ifndef UDEKS_CALC_BANK
#define UDEKS_CALC_BANK 0
#endif
static long calc_value(void) {
    unsigned long v=word(UDEKS_CALC_BANK+UDEKS_CALC_VALUE) | ((unsigned long)word(UDEKS_CALC_BANK+UDEKS_CALC_VALUE+2)<<16);
    return (long)(int32_t)v;
}
static void calc_key(char keychar) {
    const char *keys="789/456*123-C0=+.N  ";
    const char *p=strchr(keys,keychar);
    require(p != NULL, "unknown calculator key");
    unsigned index=p-keys;
#if UDEKS_CALC_BANK
    client_click(calc_x+14+(index%4)*25+12,calc_y+41+(index/4)*20+40,3);
#else
    pointer_to(calc_x+14+(index%4)*25+12,calc_y+41+(index/4)*20+40);
    joyports_mouse_button(&machine->joyports,0,false,true);frames(150);
    joyports_mouse_button(&machine->joyports,0,false,false);frames(150);
#endif
}
static void calc_expression(const char *keys,long expected) {
    for (const char *p=keys;*p;++p) calc_key(*p);
    printf("calculator %s => %ld (expected %ld)\n",keys,calc_value(),expected);fflush(stdout);
    require(calc_value()==expected,"calculator arithmetic/mouse click mismatch");
}
static void calculator_smoke(void) {
    wait_byte(0xf3e0,2,"startup did not complete");
    command("xcalc &");idle();
    require(console_contains("xcalc started &"),"calculator did not load");
    require(byte(0xf246)==1,"calculator window missing");
    calc_expression("1.25+2.75=",400);
    calc_expression("C7.5/2.5=",300);
    calc_expression("C5+N.25=",475);
    calc_expression("C12*3=",3600);
    calc_key('C');calc_key('8');calc_key('/');calc_key('0');calc_key('=');
    require(byte(UDEKS_CALC_BANK+UDEKS_CALC_ERROR)==1,"division by zero not reported");
    calc_expression("C2+3=",500);
    command("echo calculator alive");idle();
    require(console_contains("calculator alive"),"mouse use broke console typing");
    command("xclock &");idle();
    require(console_contains("xclock: slot busy") && byte(0xf246)==1,
            "clock overwrote live calculator");
    window_gesture(calc_x+22,calc_y+46,52,66);
    calc_x=30;calc_y=20;
    calc_expression("C4+5=",900);
    command("xwave &");idle();
    wait_byte(0xf27a,21,"wave did not finish alongside calculator");
    require(byte(0xf246)==2,"wave/calculator coexistence failed");
    command("xwave -q");idle();
    calc_expression("C3.5*2=",700);
    command("xcalc -q");idle();
    command("xclock &");idle();
    require(byte(0xf225)==3,"clock cannot replace stopped calculator");
    command("xcalc &");idle();
    require(console_contains("xcalc: slot busy"),"calculator overwrote live clock");
    command("xclock -q");idle();
    command("xcalc");frames(400);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);
    key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    idle();require(byte(0xf246)==0,"Ctrl+C did not close calculator");
    command("xcalc &");idle();calc_x=108;calc_y=30;
    calc_expression("C1.25+2.75=",400);
    require(byte(0xf11b)==0,"lifecycle canary failed");
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"snapshot failed");
    puts("PASS xcalc: native mouse arithmetic, drag, console, slot conflicts, wave coexistence, restart, Ctrl+C");
}
