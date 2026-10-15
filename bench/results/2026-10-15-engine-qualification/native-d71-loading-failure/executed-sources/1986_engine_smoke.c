/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Unmodified sibling core; actual keyboard/disk/1351 paths, no IPC patches. */
#define main existing_input_smoke_main
#include "1986_input_smoke.c"
#undef main
#include "engine_bindings.h"
#include "paste.h"
static const char *output;
static unsigned app(unsigned base,unsigned offset) { return 0x10000+base+offset; }
static void dump(const char *name,unsigned address,unsigned count) {
    char path[1024];snprintf(path,sizeof(path),"%s/%s.bin",output,name);
    FILE *file=fopen(path,"wb");require(file!=NULL,"capture open");
    require(fwrite(machine->mem.ram+address,1,count,file)==count,"capture write");fclose(file);
}
static void submit(const char *line) {
    unsigned before=byte(0xf3d8);text(line);key(SDL_SCANCODE_RETURN);
    wait_byte(0xf3d8,(before+1)&255,"command not accepted");idle();
    require(!byte(0xf11b),"task canary");printf("command: %s\n",line);fflush(stdout);
}
static void empty(void) { require(!byte(IPC_STATE) && !byte(IPC_STATE+1),"endpoint leak");require(!byte(IPC_STATE+6) && !byte(IPC_STATE+7),"queue leak"); }
static void guards(unsigned base,unsigned stack,const unsigned char *image,unsigned count) {
    require(!memcmp(machine->mem.ram+0x10000+base,image,count),"code overwritten");
    for(unsigned i=0;i<16;++i)require(byte(0x10000+stack+i)==0xa5 && byte(0x10000+stack+176+i)==0xa5,"stack guard");
}
static void client(const char *command,unsigned wave) {
    unsigned jobs=word(app(0x8000,SERVER_JOBS));submit(command);
    wait_byte(app(0x8000,SERVER_JOBS),(jobs+1)&255,"new server job not completed");
    wait_byte(app(0x2300,CLIENT_STATE),2,"reply not consumed");idle();
    require(byte(app(0x2300,CLIENT_STATE))==2 && !byte(app(0x2300,CLIENT_ERROR)),"client error");
    require(!byte(0xf17a),"client exit");
    guards(0x2300,0x3400,client_image,sizeof(client_image));guards(0x8000,0x8f00,server_image,sizeof(server_image));
    if(wave) {
        static const unsigned char expected[8]={250,0,6,9,14,19,23,25};
        require(!memcmp(machine->mem.ram+app(0x2300,CLIENT_SAMPLES),expected,8),"exact samples");
        require(word(app(0x2300,CLIENT_RESULT))==50,"next phase");
        dump("samples",app(0x2300,CLIENT_SAMPLES),8);dump("result",app(0x2300,CLIENT_RESULT),2);
    }
    require(word(app(0x8000,SERVER_JOBS))==jobs+1,"worker job count");
    require((byte(IPC_STATE)==5 && !byte(IPC_STATE+1)) || (!byte(IPC_STATE) && byte(IPC_STATE+1)==5),"client retirement");
    require(!byte(IPC_STATE+6) && !byte(IPC_STATE+7),"reply queue not consumed");
    puts("PASS engine exact exchange and guards");fflush(stdout);
}
static void stop(void) {
    submit("engtest --stop");wait_byte(app(0x8000,SERVER_STATE),4,"shutdown not complete");idle();empty();require(byte(app(0x8000,SERVER_STATE))==4,"server shutdown");
    require(byte(app(0x2300,CLIENT_STATE))==2 && !byte(0xf17a),"stop client");
}
int main(int argc,char **argv) {
    require(argc==5 || argc==6,"usage: engine-smoke ROMDIR DISK SLOTADDR OUTPUT [BOOT_SNAPSHOT]");
    Config config;config_set_defaults(&config);config.col_mode_80=true;
    config.joy_port_mode[0]=JOYPORT_MOUSE;config.joy_port_mode[1]=JOYPORT_JOYSTICK;
    config.real_disk_drive=true;config.drive_type=ENGINE_DRIVE;config.notify_mode=NOTIFY_MODE_CONSOLE;
    output=argv[4];slots=strtoul(argv[3],NULL,0);snapshot_path=NULL;
    machine=calloc(1,sizeof(*machine));require(machine!=NULL,"allocate emulator");
    c128_init(machine,&config);require(mem_load_c128_roms(&machine->mem,argv[1]),"load machine ROMs");
    char rom[1024];snprintf(rom,sizeof(rom),"%s/%s",argv[1],ENGINE_DRIVE==1581?"dos1581.bin":"dos1571cr.bin");
    require(ENGINE_DRIVE==1581?drive1581_load_rom(&machine->real1581[0],rom):drive1571cr_load_rom(&machine->integrated_drive,rom),"load drive ROM");
    require(!drive_attach_disk(&machine->drive,argv[2]),"attach engine disk");machine->col_mode_80=true;
    require(c128_configure_real_drives(machine),"configure real drive");c128_power_cycle(machine);
    if(argc==6) {
        require(snapshot_load(machine,argv[5])==SNAPSHOT_OK,"restore local cold-boot checkpoint");
        require(byte(0xf3e0)==2 && !byte(0xf246),"checkpoint is not initial UDEKS startup");
        puts("1986 engine: resumed local cold-boot checkpoint");fflush(stdout);
    }
    puts("1986 engine: raw-IEC boot started");fflush(stdout);
    Paste boot_keys;paste_init(&boot_keys);
    for(unsigned n=0;n<10000 && byte(0xf3e0)!=2;++n) {
        if(n==2000 && byte(0xf3d9)!=0xa5) {
            puts("1986 engine: typing BOOT through the BASIC keyboard");
            for(unsigned row=0;row<10;++row) {
                for(unsigned col=0;col<80;++col) { unsigned c=machine->vdc.ram[row*80+col]&127;putchar(c>0 && c<27?c+64:c>=32 && c<=126?c:' '); }putchar('\n');
            }
            fflush(stdout);paste_text(&boot_keys,"boot");
        }
        paste_tick(&boot_keys,&machine->kbd);frames(1);if(!(n%2500)) { printf("boot frame %u PC=%04X startup=%u drive=%04X\n",n,machine->cpu.pc,byte(0xf3e0),ENGINE_DRIVE==1581?machine->real1581[0].cpu.pc:machine->integrated_drive.cpu.pc);fflush(stdout); }
    }
    paste_free(&boot_keys);wait_byte(0xf3e0,2,"startup did not finish");idle();empty();
    if(argc==5) {
        char checkpoint[1024];snprintf(checkpoint,sizeof(checkpoint),"%s/boot-private.vsf",output);
        require(snapshot_save(machine,checkpoint)==SNAPSHOT_OK,"save private cold-boot checkpoint");
    }

    submit("engtest");
    dump("missing-console",CONSOLE_BASE,0x558);dump("missing-client",app(0x2300,CLIENT_STATE),16);dump("missing-slots",slots,128);
    printf("missing: exit=%u state=%u error=%u\n",byte(0xf17a),byte(app(0x2300,CLIENT_STATE)),byte(app(0x2300,CLIENT_ERROR)));fflush(stdout);
    wait_byte(app(0x2300,CLIENT_STATE),3,"missing-server client not complete");idle();
    require(byte(0xf17a)==2 && byte(app(0x2300,CLIENT_ERROR))==2,"missing server");empty();
    submit("xclock &");wait_byte(0xf246,1,"clock missing");unsigned clock=byte(0xf247);
    submit("xdraw &");wait_byte(0xf246,2,"draw missing");
    submit("engine &");wait_byte(app(0x8000,SERVER_STATE),1,"server missing");
    unsigned first=word(app(0x8000,SERVER_HANDLE));client("engtest --nop",0);client("engtest",1);
    pointer_to(238,129);joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf24d,1,"draw press");joyports_mouse_button(&machine->joyports,0,false,false);
    wait_byte(0xf24d,0,"draw release");wait_byte(app(0xc600,DRAW_CELLS),1,"draw cell");
    unsigned moves=word(0xf256);pointer_to(146,95);joyports_mouse_button(&machine->joyports,0,false,true);
    wait_byte(0xf248,clock,"clock drag");pointer_to(162,111);
    joyports_mouse_button(&machine->joyports,0,false,false);wait_byte(0xf248,0,"clock release");
    require(word(0xf256)>moves,"clock movement");client("engtest",1);stop();
    for(unsigned cycle=0;cycle<RESTART_CYCLES;++cycle) {
        submit("engine &");wait_byte(app(0x8000,SERVER_STATE),1,"restart missing");
        unsigned fresh=word(app(0x8000,SERVER_HANDLE));
        require(fresh>first,"handle reused");first=fresh;
        client("engtest --nop",0);client("engtest",1);stop();
        require(byte(0xf246)==2,"graphics lost during restart");
        require(byte(app(0xc600,DRAW_CELLS))==1,"drawing lost during restart");
        printf("PASS engine restart cycle %u/%u handle=%u\n",cycle+1,RESTART_CYCLES,fresh);fflush(stdout);
    }
    dump("client-code",0x12300,sizeof(client_image));dump("server-code",0x18000,sizeof(server_image));
    dump("ipc-final",IPC_STATE,62);dump("console-final",CONSOLE_BASE,0x558);
    submit("xdraw -q");submit("xclock -q");require(!byte(0xf246),"window cleanup");empty();
    submit("engtest");wait_byte(app(0x2300,CLIENT_STATE),3,"stopped-service client not complete");idle();require(byte(0xf17a)==2,"stopped service availability");empty();
    puts("PASS native 1986 engine: samples, NOP, missing server, restart, mouse, code/stack guards, stop and cleanup");fflush(stdout);
    free(machine);return 0;
}
