/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Scripted machine-level input through unmodified 1986 keyboard/1351 APIs.
 * No UDEKS request, keyboard queue, pointer or window state is patched. */
#include "c128.h"
#include "snapshot.h"
#include <SDL3/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int g_debug_enabled;
static C128 *machine;
static unsigned slots;
static const char *snapshot_path;
static unsigned max_press_frames, max_release_frames;
static unsigned last_release_frames;

static unsigned byte(unsigned address) { return machine->mem.ram[address]; }
static unsigned word(unsigned address) { return byte(address) | (byte(address + 1) << 8); }
static void frames(unsigned count) { while (count--) c128_frame(machine); }
static void require(int condition, const char *message) {
    if (!condition) {
        if (!machine) { fprintf(stderr, "FAIL: %s\n", message); exit(1); }
        if (snapshot_path) snapshot_save(machine, snapshot_path);
        fprintf(stderr, "FAIL: %s (frame %d, PC $%04X, request %02X/%02X/%02X)\n",
                message, c128_frame_count, machine->cpu.pc,
                byte(0xF35F), byte(0xF360), byte(0xF365));
        for (unsigned i = 0; i < 12; ++i) {
            frames(1);
            fprintf(stderr, "trace PC=$%04X drag=%u buttons=%u moves=%u finishes=%u\n",
                    machine->cpu.pc, byte(0xF248), byte(0xF1DC),
                    word(0xF256), word(0xF25A));
        }
        exit(1);
    }
}
static void wait_byte(unsigned address, unsigned value, const char *message) {
    unsigned limit = 10000;
    while (byte(address) != value && limit--) frames(1);
    require(byte(address) == value, message);
}
static void key(SDL_Scancode code) {
    unsigned presses = word(0xF134), releases = word(0xF136), limit = 500;
    int row, col; bool shift;
    require(kbd_map_scancode(code, &row, &col, &shift), "unmapped smoke key");
    unsigned started = c128_frame_count;
    c128_key_event(machine, code, true);
    while ((word(0xF134) == presses || !(byte(0xF138 + row) & (1u << col)))
           && limit--) frames(1);
    require(word(0xF134) != presses && (byte(0xF138 + row) & (1u << col)),
            "keyboard press was not sampled");
    unsigned elapsed = c128_frame_count - started;
    if (elapsed > max_press_frames) max_press_frames = elapsed;
    c128_key_event(machine, code, false);
    started = c128_frame_count;
    /* Initial graphics painting may delay the next polled input pass. */
    limit = 10000;
    while ((word(0xF136) == releases || (byte(0xF138 + row) & (1u << col)))
           && limit--) frames(1);
    require(word(0xF136) != releases && !(byte(0xF138 + row) & (1u << col)),
            "keyboard release was not sampled");
    elapsed = c128_frame_count - started;
    last_release_frames = elapsed;
    if (elapsed > max_release_frames) max_release_frames = elapsed;
    frames(6);
}
static void text(const char *value) {
    for (; *value; ++value) {
        if (*value >= 'a' && *value <= 'z') key(SDL_SCANCODE_A + *value - 'a');
        else if (*value == ' ') key(SDL_SCANCODE_SPACE);
        else if (*value == '\n') key(SDL_SCANCODE_RETURN);
        else if (*value == '\b') key(SDL_SCANCODE_BACKSPACE);
        else if (*value == '-') key(SDL_SCANCODE_EQUALS);
        else if (*value == '&') {
            /* Native Shift+6, the same matrix binding as 1986 paste.c. */
            kbd_set(&machine->kbd, KBD_SHIFT_ROW, KBD_SHIFT_COL, true);
            key(SDL_SCANCODE_6);
            kbd_set(&machine->kbd, KBD_SHIFT_ROW, KBD_SHIFT_COL, false); frames(6);
        } else require(0, "unsupported smoke-test character");
    }
}
static void command(const char *line) {
    char edited[55]; unsigned length = 0, checksum = 0;
    for (const char *p = line; *p; ++p) {
        if (*p == '\b') { if (length) --length; }
        else { require(length < sizeof(edited), "smoke command too long"); edited[length++] = *p; }
    }
    for (unsigned i = 0; i < length; ++i) checksum += (unsigned char)edited[i];
    unsigned before = byte(0xF3D8);
    text(line); key(SDL_SCANCODE_RETURN);
    wait_byte(0xF3D8, (before + 1) & 255, "typed command was not accepted");
    if (strcmp(line, "xwave") != 0) frames(400);
    require(byte(0xF164) == length && word(0xF165) == checksum,
            "typed submission differs from expected text");
    printf("command: %.*s -> accepted (Return release=%u frames)\n",
           (int)length, edited, last_release_frames); fflush(stdout);
}
static void idle(void) {
    wait_byte(slots + 1, 4, "shell did not return to input waiting");
    require(byte(slots + 2) == 2, "shell waits for wrong event");
}
static void pointer_to(unsigned x, unsigned y) {
    for (unsigned attempt = 0; attempt < 200; ++attempt) {
        int dx = (int)x - (int)word(0xF1D8);
        int dy = (int)y - (int)byte(0xF1DA);
        if (abs(dx) <= 1 && abs(dy) <= 1) return;
        if (dx > 8) dx = 8; if (dx < -8) dx = -8;
        if (dy > 8) dy = 8; if (dy < -8) dy = -8;
        joyports_mouse_motion(&machine->joyports, 0, dx, dy);
        frames(4);
    }
    require(0, "1351 pointer did not reach its target");
}
/* Optional regression stress: move a foreground wave while its first paint is
 * incomplete, then replay it repeatedly at screen edges. Native input only. */
#define CACHE_WINDOWS 0xe238u
#define CACHE_ACCEPT 0x5cd8u
#define CACHE_PHASE 0x5cdcu
#define CACHE_OWNER 0x5cdbu
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

int main(int argc, char **argv) {
    require(argc == 5, "usage: smoke ROMDIR DISK SLOTADDR SNAPSHOT");
    Config config;
    config_set_defaults(&config);
    config.col_mode_80 = true;
    config.joy_port_mode[0] = JOYPORT_MOUSE;
    config.joy_port_mode[1] = JOYPORT_JOYSTICK;
    config.notify_mode = NOTIFY_MODE_CONSOLE;
    machine = calloc(1, sizeof(*machine));
    require(machine != NULL, "allocate emulator");
    slots = strtoul(argv[3], NULL, 0);
    snapshot_path = argv[4];
    c128_init(machine, &config);
    require(mem_load_c128_roms(&machine->mem, argv[1]) != 0, "load authorized ROMs");
    require(drive_attach_disk(&machine->drive, argv[2]) == 0, "attach native disk");
    machine->col_mode_80 = true;
    c128_power_cycle(machine);
    IecCallbacks iec = {
        .ctx = machine, .force_slow_serial = true,
        .attention = c128_iec_attention, .send = c128_iec_send,
        .receive = c128_iec_receive, .take_status = c128_iec_take_status,
    };
    cpu_install_iec_traps(machine->mem.kernal, &iec);
    wait_byte(0xF3D9, 0xA5, "native ush did not boot");
    idle();
    unsigned initial = word(0xFF0D);
    frames(50);
    require(word(0xFF0D) == initial, "idle shell still busy-polls");
    command("echo smokk\be"); idle();
    unsigned before = byte(0xF3D8);
    unsigned recalls = word(0xF150 + 28);
    unsigned previous_sum = word(0xF165), previous_length = byte(0xF164);
    key(SDL_SCANCODE_UP);
    printf("history: count=%u recalls=%u -> %u scan=%u\n", byte(0xF16A), recalls,
           word(0xF16C), byte(0xF143)); fflush(stdout);
    key(SDL_SCANCODE_RETURN);
    wait_byte(0xF3D8, (before + 1) & 255, "cursor-up history did not execute");
    require(word(0xF150 + 28) > recalls, "history recall not recorded"); idle();
    require(word(0xF165) == previous_sum && byte(0xF164) == previous_length,
            "history submitted different text");
    command("xinit"); require(byte(0xF1B5) == 3, "VIC graphics did not initialize"); idle();
    if (getenv("UDEKS_DRAG_STRESS")) {
        if (getenv("UDEKS_DRAG_CLOCK")) { command("xclock &"); idle(); }
        drag_stress(strtoul(getenv("UDEKS_DRAG_STRESS"), NULL, 0));
        require(drive_attach_disk(&machine->drive, NULL) == 0, "detach stress disk");
        free(machine);
        return 0;
    }
    command("xclock &"); require(byte(0xF225) == 3, "clock did not start"); idle();
    /* Clock's initial title bar is x=124,y=61; pointer includes VIC borders. */
    pointer_to(150, 106);
    unsigned starts = word(0xF240 + 24), finishes = word(0xF240 + 26);
    joyports_mouse_button(&machine->joyports, 0, false, true);
    for (unsigned limit = 0; limit < 500 &&
         (word(0xF258) == starts || byte(0xF248) == 0); ++limit) frames(1);
    require(word(0xF240 + 24) == starts + 1 && byte(0xF248) != 0,
            "mouse button did not begin a window drag");
    pointer_to(174, 122);
    for (unsigned limit = 0; limit < 500 && word(0xF256) == 0; ++limit) frames(1);
    require(word(0xF240 + 22) != 0, "window outline did not move");
    joyports_mouse_button(&machine->joyports, 0, false, false);
    for (unsigned limit = 0; limit < 500 &&
         (word(0xF25A) == finishes || byte(0xF248) != 0); ++limit) frames(1);
    require(word(0xF240 + 26) == finishes + 1 && byte(0xF248) == 0,
            "mouse release did not finish window drag");
    printf("drag: starts=%u moves=%u finishes=%u\n", word(0xF258), word(0xF256), word(0xF25A));
    idle();
    command("echo pointer released"); idle();
    command("xwave"); require(byte(0xF265) == 3, "foreground wave did not start");
    require(byte(0xF27A) < 21, "initial wave completed before cancellation test");
    printf("wave: cancel during row=%u column=%u leases=%u\n",
           byte(0xF27A), byte(0xF27B), word(0xF26C));
    unsigned cancel_start = c128_frame_count;
    c128_key_event(machine, SDL_SCANCODE_LCTRL, true);
    key(SDL_SCANCODE_C);
    c128_key_event(machine, SDL_SCANCODE_LCTRL, false);
    wait_byte(0xF265, 2, "Ctrl+C did not stop foreground wave"); idle();
    require(byte(0xF27A) < 21, "Ctrl+C only completed after full plotting");
    printf("wave: cancelled in %u frames, row=%u\n",
           c128_frame_count - cancel_start, byte(0xF27A));
    require(byte(0xF225) == 3, "Ctrl+C stopped background clock");
    command("echo console alive"); idle();
    command("xwave &");
    wait_byte(0xF27A, 21, "background wave did not finish bounded plotting");
    require(word(0xF26C) == 21 && word(0xF26E) == 0,
            "wave did not acquire exactly 21 successful row leases");
    unsigned cached_leases = word(0xF26C);
    pointer_to(166, 132);
    starts = word(0xF258); finishes = word(0xF25A);
    joyports_mouse_button(&machine->joyports, 0, false, true);
    for (unsigned limit = 0; limit < 10000 &&
         (word(0xF258) == starts || byte(0xF248) == 0); ++limit) frames(1);
    require(word(0xF258) == starts + 1 && byte(0xF248), "wave drag did not start");
    pointer_to(142, 104);
    joyports_mouse_button(&machine->joyports, 0, false, false);
    for (unsigned limit = 0; limit < 10000 &&
         (word(0xF25A) == finishes || byte(0xF248)); ++limit) frames(1);
    require(word(0xF25A) == finishes + 1 && !byte(0xF248), "wave drag did not finish");
    require(word(0xF26C) == cached_leases, "wave move reacquired Z80");
    printf("wave: complete rows=%u leases=%u; cached drag without recomputation\n",
           byte(0xF27A), word(0xF26C));
    require(byte(0xF11B) == 0, "lifecycle canary failures");
    printf("sampling: maximum press=%u release=%u frames (functional, not a latency benchmark)\n",
           max_press_frames, max_release_frames);
    require(snapshot_save(machine, argv[4]) == SNAPSHOT_OK, "save smoke evidence");
    printf("PASS: native boot, stable idle, typing/backspace/history, 1351 drag, "
           "foreground Ctrl+C, background clock and console recovery (%d frames)\n",
           c128_frame_count);
    require(drive_attach_disk(&machine->drive, NULL) == 0, "detach native disk");
    free(machine);
    return 0;
}
