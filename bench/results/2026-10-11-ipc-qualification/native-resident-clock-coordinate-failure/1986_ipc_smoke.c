/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Actual raw IEC, keyboard and 1351 input; no fabricated task/IPC state. */
#define main existing_input_smoke_main
#include "1986_input_smoke.c"
#undef main
#include "ipc_bindings.h"
#include "paste.h"
static const char *output;
static unsigned app(unsigned base,unsigned offset) { return 0x10000+base+offset; }
static void dump(const char *tag,unsigned address,unsigned count) {
    char path[1024];snprintf(path,sizeof(path),"%s/%s.bin",output,tag);
    FILE *file=fopen(path,"wb");require(file!=NULL,"open capture");
    require(fwrite(machine->mem.ram+address,1,count,file)==count,"write capture");fclose(file);
}
static void submit(const char *line) {
    unsigned before=byte(0xf3d8);text(line);key(SDL_SCANCODE_RETURN);
    wait_byte(0xf3d8,(before+1)&255,"shell command not accepted");
    printf("command: %s\n",line);fflush(stdout);
}
static void guards(unsigned base,unsigned stack,const unsigned char *image,unsigned length) {
    require(!memcmp(machine->mem.ram+0x10000+base,image,length),"application code changed");
    for(unsigned i=0;i<16;++i)require(byte(0x10000+stack+i)==0xa5 && byte(0x10000+stack+0xb0+i)==0xa5,"application stack guard");
    require(!byte(0xf11b),"task canary");
}
static void empty(void) { require(!byte(IPC_STATE) && !byte(IPC_STATE+1),"endpoint leak"); }
static void exchange(const char *text_value) {
    char line[55];snprintf(line,sizeof(line),"ipcping %s",text_value);submit(line);idle();
    require(byte(app(0x2300,CLIENT_STATE))==2 && !byte(app(0x2300,CLIENT_ERROR)),"client failed");
    unsigned count=strlen(text_value)+1;require(byte(app(0x2300,CLIENT_COUNT))==count,"reply length");
    require(byte(app(0x2300,CLIENT_REPLY))==2,"reply kind");
    for(unsigned i=0;i<count-1;++i) {
        unsigned c=text_value[i];if(c>='a' && c<='z')c-='a'-'A';
        require(byte(app(0x2300,CLIENT_REPLY+1+i))==c,"reply contents");
    }
    require(word(app(0x2300,CLIENT_PEER))==word(app(0x8000,SERVER_HANDLE)),"authenticated source");
    require((byte(IPC_STATE)==5 && !byte(IPC_STATE+1)) || (byte(IPC_STATE+1)==5 && !byte(IPC_STATE)),"client endpoint cleanup");
    require(!byte(IPC_STATE+6) && !byte(IPC_STATE+7),"queued message leak");
    guards(0x2300,0x3400,client_image,sizeof(client_image));guards(0x8000,0x8f00,server_image,sizeof(server_image));
    dump("reply",app(0x2300,CLIENT_REPLY),16);printf("PASS reply: %s\n",text_value);fflush(stdout);
}
static void stop_server(void) {
    submit("ipcping --stop");idle();empty();
    require(byte(app(0x8000,SERVER_STATE))==3,"server shutdown");
    require(byte(app(0x2300,CLIENT_STATE))==2 && !byte(app(0x2300,CLIENT_ERROR)),"shutdown client");
}
int main(int argc,char **argv) {
    require(argc==5 || argc==6,"usage: ipc-smoke ROMDIR DISK SLOTADDR OUTPUT [BOOT_SNAPSHOT]");
    Config config;config_set_defaults(&config);config.col_mode_80=true;
    config.joy_port_mode[0]=JOYPORT_MOUSE;config.joy_port_mode[1]=JOYPORT_JOYSTICK;
    config.real_disk_drive=true;config.drive_type=1581;config.notify_mode=NOTIFY_MODE_CONSOLE;
    output=argv[4];slots=strtoul(argv[3],NULL,0);snapshot_path=NULL;
    machine=calloc(1,sizeof(*machine));require(machine!=NULL,"allocate emulator");
    c128_init(machine,&config);require(mem_load_c128_roms(&machine->mem,argv[1]),"load machine ROMs");
    char rom[1024];snprintf(rom,sizeof(rom),"%s/dos1581.bin",argv[1]);
    require(drive1581_load_rom(&machine->real1581[0],rom),"load 1581 ROM");
    require(!drive_attach_disk(&machine->drive,argv[2]),"attach D81");machine->col_mode_80=true;
    require(c128_configure_real_drives(machine),"configure real drive");c128_power_cycle(machine);
    if(argc==6) {
        require(snapshot_load(machine,argv[5])==SNAPSHOT_OK,"restore local cold-boot checkpoint");
        require(byte(0xf3e0)==2 && !byte(0xf246),"checkpoint is not initial UDEKS startup");
        puts("1986 IPC: resumed local cold-boot checkpoint");fflush(stdout);
    }
    puts("1986 IPC: raw-IEC boot started");fflush(stdout);
    Paste boot_keys;paste_init(&boot_keys);
    for(unsigned n=0;n<10000 && byte(0xf3e0)!=2;++n) {
        if(n==2000 && byte(0xf3d9)!=0xa5) {
            puts("1986 IPC: typing BOOT through the BASIC keyboard");
            for(unsigned row=0;row<10;++row) {
                for(unsigned col=0;col<80;++col) { unsigned c=machine->vdc.ram[row*80+col]&127;putchar(c>0 && c<27?c+64:c>=32 && c<=126?c:' '); }putchar('\n');
            }
            fflush(stdout);paste_text(&boot_keys,"boot");
        }
        paste_tick(&boot_keys,&machine->kbd);frames(1);if(!(n%2500)) { printf("boot frame %u PC=%04X startup=%u drive=%04X\n",n,machine->cpu.pc,byte(0xf3e0),machine->real1581[0].cpu.pc);fflush(stdout); }
    }
    paste_free(&boot_keys);wait_byte(0xf3e0,2,"startup did not finish");idle();empty();
    if(argc==5) {
        char checkpoint[1024];snprintf(checkpoint,sizeof(checkpoint),"%s/boot-private.vsf",output);
        require(snapshot_save(machine,checkpoint)==SNAPSHOT_OK,"save private cold-boot checkpoint");
    }
    submit("xclock &");idle();wait_byte(0xf246,1,"clock missing");unsigned clock=byte(0xf247);
    submit("xdraw &");idle();wait_byte(0xf246,2,"drawing missing");
    submit("ipcsrv &");idle();wait_byte(app(0x8000,SERVER_STATE),1,"server not ready");
    exchange("hello");exchange("1234567890abcde");
    /* Observe actual request work before Ctrl-C. The parent ush emits CANCEL. */
    submit("ipcping cancelme");
    unsigned limit=10000;while((byte(app(0x8000,SERVER_STATE))!=4 || byte(app(0x2300,CLIENT_STATE))!=1) && limit--)frames(1);
    require(limit,"no cancellation window");unsigned delivered=word(app(0x8000,SERVER_COUNT));
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    idle();wait_byte(slots+17,0,"cancelled client not reaped");require(byte(0xf17a)==130,"cancel status");
    wait_byte(app(0x8000,SERVER_STATE),1,"server did not survive cancellation");
    require(word(app(0x8000,SERVER_COUNT))==delivered,"reply delivered after cancellation");
    exchange("recovered");stop_server();
    unsigned previous=0;for(unsigned cycle=0;cycle<3;++cycle) {
        submit("ipcsrv &");idle();wait_byte(app(0x8000,SERVER_STATE),1,"restart failed");
        unsigned handle=word(app(0x8000,SERVER_HANDLE));require(handle>previous,"handle reuse");previous=handle;
        exchange("restart");stop_server();require(byte(0xf246)==2,"graphical peers lost");
    }
    /* Native 1351 clock drag while IPC's server lifetime is active. */
    submit("ipcsrv &");idle();unsigned moves=word(0xf256);
    pointer_to(238,129);joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf24d,1,"drawing press missing");joyports_mouse_button(&machine->joyports,0,false,false);
    wait_byte(0xf24d,0,"drawing release missing");wait_byte(app(0xc600,DRAW_CELLS),1,"drawing cell unchanged");
    pointer_to(150,106);joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf248,clock,"clock drag missing");pointer_to(174,122);
    joyports_mouse_button(&machine->joyports,0,false,false);wait_byte(0xf248,0,"clock drag release missing");
    require(word(0xf256)>moves,"clock movement missing");exchange("graphics");stop_server();
    dump("ipc-final",IPC_STATE,62);dump("console-final",CONSOLE_BASE,0x558);
    dump("client-code",0x12300,sizeof(client_image));dump("server-code",0x18000,sizeof(server_image));
    submit("xdraw -q");idle();submit("xclock -q");idle();empty();
    puts("PASS native 1986 IPC: exact replies, parent cancellation, restart, graphics and cleanup");fflush(stdout);
    free(machine);return 0;
}
