/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Read-only instruction breakpoints; continue the SAME partial machine frame.
 * No OS code, state, device or input queue is patched by this profiler. */
static unsigned profile_stage, profile_pages[3][32], profile_calls[3];
static unsigned profile_entry_id, profile_return_id;
static unsigned profile_return_pc, profile_call_stage;
static u64 profile_started, profile_cycles[3];
static unsigned shutdown_entry_id,shutdown_return_id,shutdown_return_pc;
static unsigned shutdown_raster;
static unsigned profile_clock_before;

static void profile_stop(void) {
    C128DebugCpu cpu;u16 pc;
    if(c128_debug_take_stop(machine,&cpu,&pc)!=C128_DEBUG_STOP_BREAKPOINT ||
       cpu!=C128_DEBUG_CPU_8502) {
        fprintf(stderr,"unexpected profiling stop\n");exit(1);
    }
    if(pc==PROFILE_DISABLE) {
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
        if(profile_return_id || machine->cpu.a>=32) {
            fprintf(stderr,"nested or invalid page copy\n");exit(1);
        }
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
