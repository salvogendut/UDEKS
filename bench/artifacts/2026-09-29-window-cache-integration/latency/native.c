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
#define PROFILE_PAGE 0x23c8u
#define PROFILE_DISABLE 0x231cu
/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Read-only instruction breakpoints; continue the SAME partial machine frame.
 * No OS code, state, device or input queue is patched by this profiler. */
static unsigned profile_stage, profile_pages[3][32], profile_calls[3];
static unsigned entry_sp,entry_a,entry_x,entry_y,entry_p,entry_retries;
static unsigned profile_entry_id, profile_return_id;
static unsigned profile_return_pc, profile_call_stage;
static u64 profile_started, profile_cycles[3];
static unsigned shutdown_entry_id,shutdown_return_id,shutdown_return_pc;
static unsigned shutdown_raster;
static unsigned profile_clock_before;
/* Published/link-asserted syscall entry, not an unexported implementation PC. */
#define CLOCK_SET 0xcf40u
#define CLOCK_CACHE_PHASE 0x5cc6u
static unsigned clock_armed,clock_started,clock_done,clock_minute,clock_start,clock_finish;
static unsigned clock_copies,clock_callbacks;
static unsigned clock_entry_id;

static void profile_stop(void) {
    C128DebugCpu cpu;u16 pc;
    if(c128_debug_take_stop(machine,&cpu,&pc)!=C128_DEBUG_STOP_BREAKPOINT ||
       cpu!=C128_DEBUG_CPU_8502) {
        fprintf(stderr,"unexpected profiling stop\n");exit(1);
    }
    if(pc==CLOCK_SET && clock_armed) {
        if(!clock_started) {
            clock_started=1;clock_start=c128_frame_count;
            memset(profile_pages,0,sizeof(profile_pages));memset(profile_calls,0,sizeof(profile_calls));
            memset(profile_cycles,0,sizeof(profile_cycles));profile_stage=2;
            profile_clock_before=word(0xF230);
        }
    } else if(pc==PROFILE_DISABLE) {
        shutdown_raster=machine->vic.current_raster;
        unsigned sp=machine->cpu.sp;
        shutdown_return_pc=1+c128_debug_mem_read(machine,cpu,0x100|((sp+1)&255))+
            (c128_debug_mem_read(machine,cpu,0x100|((sp+2)&255))<<8);
        shutdown_return_id=c128_debug_breakpoint_add(machine,cpu,shutdown_return_pc);
        if(!shutdown_return_id){fprintf(stderr,"no shutdown return breakpoint\n");exit(1);}
    } else if(shutdown_return_id && pc==shutdown_return_pc) {
        printf("shutdown profile: raster=%u target=%u\n",shutdown_raster,machine->vic.raster_irq_line);
        if(machine->vic.raster_irq_line>=256){fprintf(stderr,"shutdown lost low raster IRQ target\n");exit(1);}
        c128_debug_breakpoint_remove(machine,shutdown_return_id);shutdown_return_id=0;
    } else if(pc==PROFILE_PAGE && profile_stage) {
        /* A breakpoint precedes interrupt dispatch. An IRQ/NMI can run
         * instead of the first opcode and RTI to this same entry. Count the
         * call once, require the identical registers and caller frame, and
         * leave the interrupt's cycles in the elapsed measurement. */
        unsigned current_return=1+c128_debug_mem_read(machine,cpu,0x100|((machine->cpu.sp+1)&255))+
            (c128_debug_mem_read(machine,cpu,0x100|((machine->cpu.sp+2)&255))<<8);
        if(profile_return_id && machine->cpu.sp==entry_sp && machine->cpu.a==entry_a &&
           machine->cpu.x==entry_x && machine->cpu.y==entry_y && machine->cpu.p==entry_p &&
           current_return==profile_return_pc) {
            ++entry_retries;c128_debug_continue(machine);return;
        }
        if(profile_return_id || machine->cpu.a>=32) {
            fprintf(stderr,"nested or invalid page copy\n");exit(1);
        }
        entry_sp=machine->cpu.sp;entry_a=machine->cpu.a;entry_x=machine->cpu.x;
        entry_y=machine->cpu.y;entry_p=machine->cpu.p;
        ++profile_pages[profile_stage][machine->cpu.a];
        ++profile_calls[profile_stage];
        profile_call_stage=profile_stage;profile_started=machine->cpu.cycles;
        unsigned sp=machine->cpu.sp;
        profile_return_pc=1+c128_debug_mem_read(machine,cpu,0x100|((sp+1)&255))+
            (c128_debug_mem_read(machine,cpu,0x100|((sp+2)&255))<<8);
        profile_return_id=c128_debug_breakpoint_add(machine,cpu,profile_return_pc);
        if(!profile_return_id){fprintf(stderr,"no return breakpoint\n");exit(1);}
    } else if(profile_return_id && pc==profile_return_pc) {
        profile_cycles[profile_call_stage]+=machine->cpu.cycles-profile_started;
        c128_debug_breakpoint_remove(machine,profile_return_id);profile_return_id=0;
    }
    c128_debug_continue(machine);
}
static void frames(unsigned count) {
    while(count--) {
        unsigned before=c128_frame_count;
        do {
            c128_frame(machine);
            if(machine->paused)profile_stop();
        } while((unsigned)c128_frame_count==before);
        if(clock_started && !clock_done && byte(0xF22C)==12 && byte(0xF22D)==clock_minute &&
           byte(CLOCK_CACHE_PHASE)==2) {
            /* READY is the lease state; the final batch's commit can still
             * be in flight. Require the fixed dirty-page map to drain and
             * the measured page call to return before declaring visible. */
            unsigned dirty=profile_return_id!=0;
            for(unsigned page=0;page<32;++page)dirty|=byte(0xE190+page);
            if(!dirty) {
                clock_done=1;clock_finish=c128_frame_count;clock_copies=profile_calls[2];
                clock_callbacks=(word(0xF230)-profile_clock_before)&65535;profile_stage=0;
            }
        }
    }
}
static void profile_begin(void) {
    memset(profile_pages,0,sizeof(profile_pages));memset(profile_calls,0,sizeof(profile_calls));
    memset(profile_cycles,0,sizeof(profile_cycles));profile_stage=1;
    profile_clock_before=word(0xF230);
    if(!profile_entry_id)profile_entry_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,PROFILE_PAGE);
    if(!shutdown_entry_id)shutdown_entry_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,PROFILE_DISABLE);
    if(!profile_entry_id){fprintf(stderr,"no page breakpoint\n");exit(1);}
}
static void profile_end(unsigned move) {
    profile_stage=0;
    if(profile_return_id){fprintf(stderr,"unfinished page copy\n");exit(1);}
    for(unsigned stage=1;stage<=2;++stage) {
        unsigned unique=0;for(unsigned p=0;p<32;++p)if(profile_pages[stage][p])++unique;
        printf("page profile %u stage=%u calls=%u unique=%u cycles=%llu\n",move,stage,
            profile_calls[stage],unique,(unsigned long long)profile_cycles[stage]);
    }
    printf("clock profile %u: paints=%u\n",move,(word(0xF230)-profile_clock_before)&65535);
}

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
        else if (*value >= '1' && *value <= '9') key(SDL_SCANCODE_1 + *value - '1');
        else if (*value == '0') key(SDL_SCANCODE_0);
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
#define CACHE_ACCEPT 0x5cc2u
#define CACHE_PHASE 0x5cc6u
#define CACHE_OWNER 0x5cc5u
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
    unsigned start=c128_frame_count,phase=byte(CACHE_PHASE);
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==before);++n)frames(1);
    printf("drag start: resize=%u phase=%u frames=%u x=%u y=%u\n",
        resize,phase,(unsigned)c128_frame_count-start,wave_x(),wave_y());fflush(stdout);
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
static void clock_repairs(void) {
    const unsigned xs[3]={109,109,144},ys[3]={40,65,88};
    unsigned paints=word(0xF270),jobs=word(0xF26C);
    clock_entry_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,CLOCK_SET);
    require(clock_entry_id!=0,"no clock-set breakpoint");
    for(unsigned i=0;i<3;++i) {
        unsigned before=drag_begin(0);pointer_to(xs[i]+20,ys[i]+46);
        /* pointer_to allows one pixel, appropriate for general mouse input.
         * Here use real relative mouse motion to settle an exact geometry
         * before release so both timing variants see the identical strip. */
        for(unsigned n=0;n<500;++n) {
            int dx=(int)xs[i]-(int)word(0xF249),dy=(int)ys[i]-(int)byte(0xF24B);
            if(!dx && !dy) {frames(8);if(word(0xF249)==xs[i] && byte(0xF24B)==ys[i])break;}
            else {if(dx>8)dx=8;if(dx< -8)dx=-8;if(dy>8)dy=8;if(dy< -8)dy=-8;
                joyports_mouse_motion(&machine->joyports,0,dx,dy);frames(8);}
            require(n!=499,"exact native drag did not settle");
        }
        drag_release(before);
        ready();pixel_oracle();require(wave_x()==xs[i] && wave_y()==ys[i],"clock case geometry");
        clock_armed=1;clock_started=clock_done=0;clock_minute=10+i;
        char text[32];snprintf(text,sizeof(text),"date 12%02u00",clock_minute);command(text);idle();
        for(unsigned n=0;n<10000 && !clock_done;++n)frames(1);
        require(clock_started && clock_done,"native date did not repaint clock");
        require(clock_callbacks==1,"clock update callback was repeated or omitted");
        unsigned callbacks=word(0xF230);frames(120);ready();pixel_oracle();
        require(word(0xF230)==callbacks,"hidden clock repeatedly requested a repair");
        require(word(0xF270)==paints && word(0xF26C)==jobs,"clock update repainted/recomputed wave");
        require(memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0,
            "clock repair left VIC/shadow disagreement");
        for(unsigned surface=0;surface<2;++surface) {
            char filename[4096];snprintf(filename,sizeof(filename),"%.*s-clock-%u-%s.bin",
                (int)strlen(snapshot_path)-4,snapshot_path,i,surface?"bitmap":"shadow");
            FILE *file=fopen(filename,"wb");require(file!=NULL,"open clock pixel evidence");
            require(fwrite(machine->mem.ram+(surface?0x16000:0xA1E0),1,8000,file)==8000,
                "write clock pixel evidence");fclose(file);
        }
        printf("clock repair %u: x=%u y=%u frames=%u pages=%u callbacks=%u pixels=OK\n",
            i,wave_x(),wave_y(),clock_finish-clock_start,clock_copies,clock_callbacks);
        clock_armed=clock_started=0;
    }
    c128_debug_breakpoint_remove(machine,clock_entry_id);
    printf("profiler entry redispatches: %u\n",entry_retries);
}
static void drag_stress(unsigned count) {
    (void)count;
    wait_byte(CACHE_ACCEPT,0x80,"resident pre-C acceptance failed");
    /* Also measure the clock while it is the only window. */
    pointer_to(144,107);
    unsigned clock_before=word(0xF258),clock_start=c128_frame_count;
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==clock_before);++n)frames(1);
    require(byte(0xF248)&&word(0xF258)==((clock_before+1)&65535),"clock drag did not begin");
    printf("clock drag start: frames=%u\n",(unsigned)c128_frame_count-clock_start);
    unsigned clock_finish=word(0xF25A);drag_release(clock_finish);
    frames(300);require(byte(CACHE_PHASE)==0,"clock-only drag retained a cache");
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
        profile_begin();
        unsigned delay=drag_release(before),start=c128_frame_count;
        profile_stage=2;
        if(delay>max_release)max_release=delay;
        ready();if(c128_frame_count-start>max_paste)max_paste=c128_frame_count-start;
        profile_end(i);
        pixel_oracle();
        require(word(0xF270)==paints && byte(0xF27A)==21,"cached move called the wave painter");
        require(word(0xF26C)==21,"cached move acquired Z80");
        printf("cache move %u: x=%u y=%u release=%u paste=%u pixels=OK\n",
            i,wave_x(),wave_y(),delay,c128_frame_count-start);fflush(stdout);
    }
    /* Place the wave below the clock title, then drag the clock while a
     * completed wave is underneath. This is the user's reported case. */
    before=drag_begin(0);pointer_to(144+20,88+46);drag_release(before);ready();pixel_oracle();
    pointer_to(144,107);clock_before=word(0xF258);clock_start=c128_frame_count;
    joyports_mouse_button(&machine->joyports,0,false,true);
    for(unsigned n=0;n<10000 && (!byte(0xF248)||word(0xF258)==clock_before);++n)frames(1);
    require(byte(0xF248)==1 && word(0xF258)==((clock_before+1)&65535),"overlap clock drag did not begin");
    require((unsigned)c128_frame_count-clock_start <= 30,"overlap clock drag-start exceeded 30 frames");
    printf("overlap clock drag start: frames=%u\n",(unsigned)c128_frame_count-clock_start);
    unsigned outline_moves=word(0xF256);
    pointer_to(156,114);frames(40);
    require(word(0xF256)>outline_moves,"clock outline did not track native mouse");
    clock_finish=word(0xF25A);drag_release(clock_finish);frames(300);
    require(word(0xF26C)==21,"clock drag unexpectedly acquired the Z80");
    for(unsigned n=0;n<10000;++n) {
        unsigned dirty=0;
        for(unsigned page=0;page<32;++page)dirty|=byte(0xE190+page);
        if(!dirty && memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0)break;
        require(n!=9999,"clock drag repaint did not settle");frames(1);
    }
    require(memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0,
        "clock drag left shadow/VIC disagreement");
    /* xwave is still the foreground command: stop it before testing typing. */
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    wait_byte(0xF265,2,"foreground wave did not cancel after clock drag");idle();
    command("echo clock drag alive");idle();command("xinit -q");idle();
    puts("PASS: native clock-only/overlap drag-start timing and shutdown");
    return; /* Diagnostic scope, not another full compositor qualification. */
    /* Partial paste + Ctrl+C must cancel, without stranding the console. */
    before=drag_begin(0);pointer_to(80+20,30+46);drag_release(before);
    require(byte(CACHE_PHASE)==3,"cancellation gate was not a live paste");
    unsigned cancel_start=c128_frame_count;
    c128_key_event(machine,SDL_SCANCODE_LCTRL,true);key(SDL_SCANCODE_C);
    c128_key_event(machine,SDL_SCANCODE_LCTRL,false);
    wait_byte(0xF265,2,"Ctrl+C did not cancel pasted wave");
    wait_byte(CACHE_PHASE,0,"cancelled cache ownership retained");idle();
    printf("cancel profile: frames=%u\n",c128_frame_count-cancel_start);
    require(byte(0xF225)==3,"cancellation killed background clock");
    cia_write(&machine->cia2,0xDD0E,0);frames(4);cia_write(&machine->cia2,0xDD0D,0x7f);
    (void)cia_read(&machine->cia2,0xDD0D);frames(4);
    require(byte(0xFFF5)==0 && word(0xFFF6)>100,"installed NMI was not drained");
    require(byte(0xF11B)==0,"lifecycle/context canary damaged");
    command("echo console alive");idle();command("xwave &");idle();
    wait_byte(0xF27A,21,"replacement wave did not finish");ready();pixel_oracle();
    clock_repairs();
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
