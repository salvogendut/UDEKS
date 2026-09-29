/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Read-only entry/return probes. Time is emulated bus time, not wall time. */
static void frames(unsigned count);
static void require(int condition, const char *message);
struct repaint_watch {
    unsigned pc, entry_id, return_pc, return_id, sp, a, x, y, p;
    unsigned calls, retries;
    u64 started, last, max_call, max_gap;
};
static struct repaint_watch repaint_watches[2];
static unsigned repaint_active, repaint_case;
static u64 repaint_started;

static unsigned repaint_return_pc(void) {
    unsigned sp=machine->cpu.sp;
    return (1+c128_debug_mem_read(machine,C128_DEBUG_CPU_8502,0x100|((sp+1)&255))+
        (c128_debug_mem_read(machine,C128_DEBUG_CPU_8502,0x100|((sp+2)&255))<<8))&65535;
}

static unsigned repaint_stop(unsigned pc) {
    if(!repaint_active)return 0;
    for(unsigned i=0;i<2;++i) {
        struct repaint_watch *w=&repaint_watches[i];
        if(pc!=w->pc)continue;
        unsigned caller=repaint_return_pc();
        if(w->return_id) {
            /* IRQ dispatch can precede execution of the entry opcode, then
             * RTI to the same PC. This is still the original invocation. */
            require(w->sp==machine->cpu.sp && w->a==machine->cpu.a &&
                w->x==machine->cpu.x && w->y==machine->cpu.y && w->p==machine->cpu.p &&
                w->return_pc==caller,"nested or changed repaint probe entry");
            ++w->retries;
        } else {
            u64 now=machine->bus_cycles,gap=now-w->last;
            if(gap>w->max_gap)w->max_gap=gap;
            w->last=w->started=now;++w->calls;
            w->sp=machine->cpu.sp;w->a=machine->cpu.a;w->x=machine->cpu.x;
            w->y=machine->cpu.y;w->p=machine->cpu.p;w->return_pc=caller;
            w->return_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,caller);
            require(w->return_id!=0,"no repaint return breakpoint");
        }
        c128_debug_continue(machine);return 1;
    }
    for(unsigned i=0;i<2;++i) {
        struct repaint_watch *w=&repaint_watches[i];
        if(!w->return_id || pc!=w->return_pc || machine->cpu.sp!=((w->sp+2)&255))continue;
        u64 elapsed=machine->bus_cycles-w->started;
        if(elapsed>w->max_call)w->max_call=elapsed;
        unsigned id=w->return_id;w->return_id=0;
        /* The service registry can reuse one indirect-call return address. */
        if(repaint_watches[1-i].return_id!=id)c128_debug_breakpoint_remove(machine,id);
        c128_debug_continue(machine);return 1;
    }
    return 0;
}

static void repaint_begin(unsigned index) {
    require(!repaint_active,"overlapping repaint measurements");
    memset(repaint_watches,0,sizeof(repaint_watches));
    repaint_case=index;repaint_started=machine->bus_cycles;
    repaint_watches[0].pc=REPAINT_MANAGER_PC;
    repaint_watches[1].pc=REPAINT_KEYBOARD_PC;
    for(unsigned i=0;i<2;++i) {
        repaint_watches[i].last=repaint_started;
        repaint_watches[i].entry_id=c128_debug_breakpoint_add(machine,C128_DEBUG_CPU_8502,
            repaint_watches[i].pc);
        require(repaint_watches[i].entry_id!=0,"no repaint entry breakpoint");
    }
    repaint_active=1;
}

static void repaint_finish(unsigned index) {
    require(repaint_active && repaint_case==index,"wrong repaint measurement case");
    /* READY alone can precede the final commit's return. Observe completion,
     * not a fixed delay or a patched cache/window/keyboard record. */
    for(unsigned n=0;n<10000;++n) {
        unsigned dirty=repaint_watches[0].return_id || repaint_watches[1].return_id || profile_return_id;
        for(unsigned page=0;page<32;++page)dirty|=byte(0xE190+page);
        if(!dirty && memcmp(machine->mem.ram+0xA1E0,machine->mem.ram+0x16000,8000)==0)break;
        require(n!=9999,"repaint measurement did not settle");frames(1);
    }
    for(unsigned i=0;i<2;++i) {
        struct repaint_watch *w=&repaint_watches[i];
        u64 gap=machine->bus_cycles-w->last;
        if(gap>w->max_gap)w->max_gap=gap; /* Include leading/trailing fragments. */
        require(w->calls!=0 && !w->return_id,"incomplete repaint service measurement");
        printf("repaint service: case=%u service=%s calls=%u retries=%u max_call=%llu max_gap=%llu span=%llu\n",
            index,i?"keyboard":"manager",w->calls,w->retries,
            (unsigned long long)w->max_call,(unsigned long long)w->max_gap,
            (unsigned long long)(machine->bus_cycles-repaint_started));
        c128_debug_breakpoint_remove(machine,w->entry_id);
    }
    repaint_active=0;fflush(stdout);
}
