/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Same public WHOLD fixture as VICE. Only client release/case flags are poked;
 * no UDEKS request, service, lifecycle, or error response is patched. */
static void eject_command(const char *line,const char *expected) {
    idle(); command(line); idle();
    if(byte(0xf287) || !console_contains(expected)) diagnostic();
    require(!byte(0xf287) && console_contains(expected),"ejection command failed");
    printf("PASS %s: %s\n",line,expected); fflush(stdout);
}
static unsigned eject_start(unsigned number) {
    unsigned generation=byte(UDEKS_EJECT_GENERATION);
    command("whold &"); idle();
    wait_byte(UDEKS_EJECT_STAGE,1,"writer did not reach first yield");
    machine->mem.ram[UDEKS_EJECT_CASE]=number;
    machine->mem.ram[UDEKS_EJECT_RELEASE]=1;
    for(unsigned n=0;n<10000 && byte(UDEKS_EJECT_STAGE)<2;++n) frames(1);
    if(byte(UDEKS_EJECT_STAGE)!=2) diagnostic();
    require(byte(UDEKS_EJECT_STAGE)==2,"first 24-byte write failed");
    return generation;
}
static void eject_retired(unsigned generation) {
    wait_byte(slots+5*8+1,0,"writer task not released");
    require(byte(UDEKS_EJECT_GENERATION)==((generation+1)&255),"owner generation not retired");
    require(!byte(UDEKS_EJECT_CLEANUP),"owner cleanup did not release closed handle");
    require(!byte(0xf11b),"task stack guard failed");
}
static void storage_eject_smoke(const char *data_path) {
    wait_byte(0xf3e0,2,"startup incomplete"); idle();
    require(machine->drive2_raw_iec && machine->real_drive_type[1]==1581,
            "drive 9 must be a connected ROM-backed 1581");
    require(machine->drive2.disk_attached && machine->real1581[1].fdc.image,
            "drive 9 media missing");
    eject_command("mount -o rw 9 /mnt","ready (read-write)");
    eject_command("save -c /mnt/keep 24","save: verified");
    if(getenv("UDEKS_EJECT_REBOOT")) {
        eject_command("save -c /mnt/recover 24","save: verified");
        eject_command("save -c /mnt/owner4 24","save: verified");
    } else {
        unsigned generation=eject_start(2);
        printf("EJECT writer stage=%u, 24 initial bytes accepted, generation=%u\n",
               byte(UDEKS_EJECT_STAGE),generation); fflush(stdout);
        require(drive_attach_disk(&machine->drive2,NULL)==0,"eject disposable D81");
        frames(2); /* normal media-generation propagation; no reset or power-off */
        require(machine->drive2_raw_iec && machine->real_drive_type[1]==1581 &&
                !machine->drive2.disk_attached && !machine->real1581[1].fdc.image,
                "must eject media without disconnecting drive 9");
        machine->mem.ram[UDEKS_EJECT_RELEASE]=2; /* WRITE another 24, then CLOSE */
        wait_byte(UDEKS_EJECT_STAGE,4,"writer did not return after media loss");
        eject_retired(generation);
        unsigned error=byte(UDEKS_EJECT_ERRNO),accepted=byte(UDEKS_EJECT_WRITTEN);
        unsigned closed=byte(UDEKS_EJECT_CLOSED);
        printf("EJECTION_RESULT write_error=%u accepted=%u close_error=%u generation_before=%u generation_after=%u cleanup_error=%u\n",
               error,accepted,closed,generation,byte(UDEKS_EJECT_GENERATION),byte(UDEKS_EJECT_CLEANUP));
        fflush(stdout);
        require((error==5 || error==19 || (!error && accepted>0 && accepted<24)) &&
                accepted<24 && (closed==5 || closed==19),"media loss was not reported");
        eject_command("cat /hello","HELLO UDEKS");
        eject_command("umount /mnt","");
        require(drive_attach_disk(&machine->drive2,data_path)==0,"reinsert same data D81");
        frames(2);
        require(machine->drive2_raw_iec && machine->real1581[1].fdc.image,
                "drive did not receive reinserted media");
        eject_command("mount -o rw 9 /mnt","ready (read-write)");
        eject_command("save -c /mnt/keep 24","save: verified");
        eject_command("save /mnt/recover 24","save: created and verified");
        generation=eject_start(4); /* reuse same native allocation after failure */
        machine->mem.ram[UDEKS_EJECT_RELEASE]=1;
        wait_byte(UDEKS_EJECT_STAGE,3,"reused writer did not exit");
        eject_retired(generation);
        eject_command("save -c /mnt/owner4 24","save: verified");
    }
    eject_command("cat /hello","HELLO UDEKS");
    eject_command("umount /mnt","");
    require(!byte(0xf11b),"task stack guard failed");
    require(snapshot_save(machine,snapshot_path)==SNAPSHOT_OK,"save ejection evidence");
    require(drive_attach_disk(&machine->drive2,NULL)==0,"flush data disk");
    require(drive_attach_disk(&machine->drive,NULL)==0,"flush system disk");
    puts("PASS native 1986 1581 ejection/recovery checks");
}
