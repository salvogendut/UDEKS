/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Public commands entered with the emulator's real keyboard. No OS patches. */
static void write_command(const char *line,unsigned status,const char *expected) {
    idle(); command(line); idle();
    if(byte(0xf287)!=status || !console_contains(expected)) {
        diagnostic();
        for(unsigned row=0;row<21;++row)
            printf("%.*s\n",64,(char *)&machine->mem.ram[UDEKS_CONSOLE_BASE+row*65]);
        require(0,"public write command failed");
    }
    printf("PASS %s: %s\n",line,expected); fflush(stdout);
}
static void storage_write_smoke(void) {
    wait_byte(0xf3e0,2,"startup incomplete"); idle();
    require(byte(0xf3dd)==1 && !console_contains("RC failed"),"disk shell/startup failed");
    write_command("save /denied 1",1,"Read-only filesystem");
    write_command("df",0,"Read-only mount");
    if(getenv("UDEKS_WRITE_REBOOT")) {
        write_command("save -c /binary 515",0,"save: verified");
        write_command("save -c /zero 0",0,"save: verified");
        write_command("save -c /nmitest 515",0,"save: verified");
        write_command("save -c /graphics 24",0,"save: verified");
    } else {
        write_command("mount -o remount,rw 8 /",0,"ready (read-write)");
        write_command("df",0,"Read-write mount");
        write_command("save /binary 515",0,"save: created and verified");
        write_command("save /zero 0",0,"save: created and verified");
        write_command("save /binary 515",1,"File exists");
        unsigned before=word(0xfff6);
        c128_key_event(machine,SDL_SCANCODE_PAGEUP,true); frames(4);
        c128_key_event(machine,SDL_SCANCODE_PAGEUP,false); frames(4);
        require(word(0xfff6)!=before && byte(0xfff5)==0,"RESTORE not drained");
        /* CIA2 timer NMI continues through real keyboard, disk loading and
         * the guarded write service. Device registers only, no OS hooks. */
        before=word(0xfff6);
        cia_write(&machine->cia2,0xdd04,0); cia_write(&machine->cia2,0xdd05,0x40);
        cia_write(&machine->cia2,0xdd0d,0x81); cia_write(&machine->cia2,0xdd0e,0x11);
        write_command("save /nmitest 515",0,"save: created and verified");
        cia_write(&machine->cia2,0xdd0e,0); frames(4);
        cia_write(&machine->cia2,0xdd0d,0x7f); (void)cia_read(&machine->cia2,0xdd0d);
        require(word(0xfff6)!=before && !byte(0xfff5),"CIA2 NMI not drained");
        printf("PASS RESTORE and CIA2 NMI drained, count=%u\n",word(0xfff6));
        command("xclock &"); idle(); wait_byte(0xf246,1,"clock did not open");
        window_gesture(146,96,42,56);
        write_command("save /graphics 24",0,"save: created and verified");
        command("xclock -q"); idle(); wait_byte(0xf246,0,"clock did not close");
        write_command("mount -o remount,ro 8 /",0,"ready (read-only)");
        write_command("save /denied 1",1,"Read-only filesystem");
    }
    write_command("cat /hello",0,"HELLO UDEKS");
    require(!byte(0xf11b),"task canary failure");
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"save evidence");
    require(drive_attach_disk(&machine->drive,NULL)==0,"flush/detach written disk");
    puts("PASS native 1986 public binary/empty write/readback, native input, RO defaults");
}
