/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Native keyboard/1351 input only: no app, clock, task or request injection. */
static unsigned native_clock_vdc_byte(unsigned address) {
    /* Inspect logical VDC bytes without touching its registers/update pointer.
     * The 16K addressing convention on fitted 64K RAM permutes DRAM lines. */
    bool mode64=(machine->vdc.regs[28]&0x10)!=0;
    bool fitted64=machine->vdc.address_mask==0xffff;
    if(!mode64 && fitted64)
        address=(address&0x80ff)|((address&0x3f00)<<1)|(address&0x0100);
    else if(mode64 && !fitted64)
        address=(address&0x00ff)|((address&0x7e00)>>1);
    else if(!mode64) address&=0x3fff;
    return machine->vdc.ram[address];
}
static bool native_clock_panel_matches(unsigned address,const unsigned char *expected) {
    for(unsigned i=0;i<9;++i)
        if(native_clock_vdc_byte(address+i)!=expected[i]) return false;
    return true;
}
static void native_clock_panel_row(unsigned row,const char *text) {
    unsigned char expected[9];
    memset(expected,32,sizeof(expected));
    for(unsigned i=0;text[i] && i<sizeof(expected);++i) {
        unsigned c=(unsigned char)text[i];
        if(c>='a' && c<='z') c-=32;
        expected[i]=(c>='A' && c<='Z') ? c&31 : c;
    }
    unsigned address=0x04b2+row*80;
    for(unsigned n=0;n<10000 && !native_clock_panel_matches(address,expected);++n) frames(1);
    printf("panel row %u: ",row);
    for(unsigned i=0;i<9;++i) printf("%02x ",native_clock_vdc_byte(address+i));
    printf("expected %s\n",text);fflush(stdout);
    require(native_clock_panel_matches(address,expected),"running panel text mismatch");
    for(unsigned i=0;i<9;++i)
        require(native_clock_vdc_byte(address+0x800+i)==(row>=2 && row<7 ? 0x80 : 0),
                "running panel text attributes mismatch");
}
static unsigned native_clock_address(unsigned slot,unsigned offset) {
    return 0x10000+(slot?0x3500:0x2300)+offset;
}
static void native_clock_time(unsigned slot,unsigned hour,unsigned minute) {
    wait_byte(native_clock_address(slot,UDEKS_NATIVE_CLOCK_HOUR),hour,"native clock hour stale");
    wait_byte(native_clock_address(slot,UDEKS_NATIVE_CLOCK_MINUTE),minute,"native clock minute stale");
    wait_byte(slots+(slot+2)*8+1,4,"native clock did not sleep");
    unsigned commands=native_clock_address(slot,UDEKS_NATIVE_CLOCK_COMMANDS);
    require(!memcmp(machine->mem.ram+commands,machine->mem.ram+0x1cd00+slot*384,344),
            "native clock retained image differs from private commands");
    require(byte(native_clock_address(slot,UDEKS_NATIVE_CLOCK_PRESENTS)),"native clock did not present");
    printf("clock task %u: %02u:%02u, presents %u\n",slot+3,hour,minute,
           byte(native_clock_address(slot,UDEKS_NATIVE_CLOCK_PRESENTS)));fflush(stdout);
}
static void native_clock_canvas(void) {
    for(unsigned i=0;i<10000 && memcmp(machine->mem.ram+0xa1e0,
                                     machine->mem.ram+0x16000,8000);++i) frames(1);
    require(!memcmp(machine->mem.ram+0xa1e0,machine->mem.ram+0x16000,8000),
            "native clock bitmap/shadow mismatch");
}
static void native_clock_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete");
    native_clock_panel_row(1,"RUNNING");native_clock_panel_row(2,"NONE");
    unsigned char legacy[32];memcpy(legacy,machine->mem.ram+0xf220,32);
    command("nclock &");idle();wait_byte(0xf246,1,"first native clock window missing");
    native_clock_panel_row(2,"xinit");native_clock_panel_row(3,"nclock");
    command("date 031500");idle();native_clock_time(0,3,15);
    command("clock2");wait_byte(0xf246,2,"second native clock window missing");
    wait_byte(0xf184,8,"native clock did not own foreground");
    native_clock_panel_row(4,"clock2");
    native_clock_time(1,3,15);
    window_gesture(146,96,44,96); /* second clock from 124,50 to 22,50 */
    native_clock_canvas();
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);idle();
    wait_byte(0xf246,1,"Ctrl+C must leave the background peer");
    wait_byte(slots+25,0,"foreground clock allocation not reaped");
    native_clock_panel_row(3,"nclock");native_clock_panel_row(4,"");
    require(byte(slots+17)>=2 && byte(slots+17)<=4,"background clock was stopped");
    command("clock2 &");idle();wait_byte(0xf246,2,"native clock slot not reusable");
    native_clock_panel_row(4,"clock2");
    command("date 214500");idle();native_clock_time(0,21,45);native_clock_time(1,21,45);
    window_gesture(146,96,44,96);
    /* Close the moved instance through the real 1351 and reuse it once more. */
    client_click(22+64+12,50+6+40,0);
    wait_byte(0xf246,1,"native clock close box did not close");
    wait_byte(slots+25,0,"closed native clock was not reaped");
    command("clock2 &");idle();wait_byte(0xf246,2,"closed native clock slot not reusable");
    require(!memcmp(legacy,machine->mem.ram+0xf220,32),"native clock changed legacy clock state");
    command("xclock &");idle();wait_byte(0xf246,3,"legacy clock coexistence failed");
    command("xwave &");idle();wait_byte(0xf246,4,"legacy wave coexistence failed");
    wait_byte(0xf27a,21,"legacy wave did not complete");
    native_clock_panel_row(2,"xinit");native_clock_panel_row(3,"xclock");
    native_clock_panel_row(4,"xwave");native_clock_panel_row(5,"nclock");
    native_clock_panel_row(6,"clock2");
    command("cowsay native clocks");idle();
    require(console_contains("native clocks"),"console failed beside native clocks");
    native_clock_canvas();
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"save native clock evidence");
    command("xinit -q");idle();wait_byte(0xf246,0,"desktop shutdown failed");
    native_clock_panel_row(2,"NONE");native_clock_panel_row(3,"");
    native_clock_panel_row(4,"");native_clock_panel_row(5,"");native_clock_panel_row(6,"");
    wait_byte(slots+17,0,"first native clock not reaped");
    wait_byte(slots+25,0,"second native clock not reaped");
    for(unsigned base=0x18a00;base<=0x18d00;base+=0x300)
        for(unsigned i=0;i<16;++i)
            require(byte(base+i)==0xa5 && byte(base+0x2b0+i)==0xa5,"private stack guard failed");
    require(!byte(0xf11b),"lifecycle canary failed");
    puts("PASS native clock: both slots, date, native drag/close, Ctrl+C, reload, four windows, console, guards, bitmap");
    puts("PASS running panel: header, complete names, digit suffix, updates, cleared rows, attributes");
}
