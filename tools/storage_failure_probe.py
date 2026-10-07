#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public storage failures and real writer retirement on disposable media.

Drive 8 is a copied system disk; drive 9 is generated test data only. Faults
are drive/media actions, not patched OS replies. The monitor changes only
keyboard events and the independent clients' documented release bytes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from add_disk_apps import add_apps
import build_d71 as d71
import build_d81 as d81
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import ALLOCATIONS
from storage_owner_probe import with_spawn_child
from storage_public_probe import files
from storage_shell_probe import sp, byte, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, monitor_command

ROOT=Path(__file__).resolve().parents[1]


def make_data(drive, remaining=None):
    """A valid DOS disk, optionally filled by a real linked SEQ, not fake BAM."""
    image=d81.blank_d81() if drive=='1581' else d71.blank_d71()
    install=d81.install_file if drive=='1581' else d71.install_prg_file
    install(image,'KEEP',bytes(range(24)),file_type=0x81)
    if drive=='1541': image=bytearray(d71.d64_compatibility_image(image))
    offset=d81.sector_offset if drive=='1581' else d71.sector_offset
    free=[]
    for track in range(1,81 if drive=='1581' else 71 if drive=='1571' else 36):
        if track in ((40,) if drive=='1581' else (18,53)): continue
        for sector in range(40 if drive=='1581' else d71.sectors_per_track(track)):
            if drive=='1581': available=d81.is_free(image,track,sector)
            elif track<=35: available=d71.sector_is_free(image,track,sector)
            else:
                available=image[offset(53,0)+(track-36)*3+sector//8] & (1<<(sector%8))
            if available: free.append((track,sector))
    if remaining is not None:
        if not 0<=remaining<len(free): raise ValueError('invalid free-block target')
        allocated=free[:len(free)-remaining]
        for i,(track,sector) in enumerate(allocated):
            pos=offset(track,sector)
            image[pos:pos+2]=bytes(allocated[i+1] if i+1<len(allocated) else (0,255))
            image[pos+2:pos+256]=bytes([0x5a])*254
            (d81.mark_used if drive=='1581' else d71.mark_used)(image,track,sector)
        pos=offset(40,3) if drive=='1581' else offset(18,1)
        entry=pos+2+32  # KEEP owns the first slot; FILL owns the second.
        if image[entry]: raise AssertionError('fixture directory slot occupied')
        image[entry:entry+3]=bytes((0x81,*allocated[0]))
        image[entry+3:entry+19]=b'FILL'.ljust(16,b'\xa0')
        image[entry+28:entry+30]=len(allocated).to_bytes(2,'little')
    return bytes(image)


def audit(before,after,allowed):
    """Existing bytes unchanged; report partial new files without calling success."""
    old=files(before)
    offset,start=(d81.sector_offset,(40,3)) if len(after)==d81.SIZE else (d71.sector_offset,(18,1))
    actual={}; added={}
    for e in d81.entries(after,offset,*start):
        name=bytes(c-128 if 193<=c<=218 else c for c in e[3:19].rstrip(b'\xa0'))
        if name in actual: raise AssertionError('duplicate filename')
        actual[name]=e
        if name in old:
            if e[0] not in (0x81,0x82) or d81.file_bytes(after,e,offset)!=old[name]:
                raise AssertionError(('existing file changed',name))
        else:
            if name.decode() not in allowed: raise AssertionError(('unexpected new file',name))
            added[name.decode()]={'closed':bool(e[0]&128),'blocks':int.from_bytes(e[28:30],'little')}
            if e[0]&128:
                payload=d81.file_bytes(after,e,offset)
                added[name.decode()]['bytes']=len(payload)
                added[name.decode()]['sha256']=hashlib.sha256(payload).hexdigest()
    if not old.keys()<=actual.keys(): raise AssertionError('existing file disappeared')
    return added


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--drive',choices=('1541','1571','1581'),default='1541')
    p.add_argument('--disk',type=Path,default=ROOT/'build/boot/udeks.d64')
    p.add_argument('--output',type=Path,default=ROOT/'build/storage/failures')
    p.add_argument('--full-only',action='store_true',help='diagnostic: run only full-disk create')
    p.add_argument('--skip-media-removal',action='store_true',
                   help='explicit partial qualification; still test drive loss on CLOSE')
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=a.drive+'-',dir=a.output.resolve()))
    print('evidence:',work,flush=True)
    ext={'1541':'.d64','1571':'.d71','1581':'.d81'}[a.drive]
    fixture=ROOT/'build/storage-failures'
    original=a.disk.read_bytes()
    system=with_spawn_child(original,(fixture/'CHILD.BIN').read_bytes())
    system=add_apps(system,[(name,(fixture/path).read_bytes()) for name,path in
                          (('WLEAK.BIN','foreground/WLEAK.BIN'),('WHOLD.BIN','holder/WHOLD.BIN'),('PARENT.BIN','parent/PARENT.BIN'))])
    disk=work/('system'+ext); disk.write_bytes(system)
    media={}; preimages={}
    for name,remaining in (('protected',None),('normal',None),('full',0),('partial',3),('removed',None),('close',None)):
        preimages[name]=make_data(a.drive,remaining)
        media[name]=work/(name+ext); media[name].write_bytes(preimages[name])
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    segments=map_segments(text)
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    exports=map_exports((ROOT/'build/storage/module.map').read_text())
    generations=exports['_udeks_storage_generations'][0]; cleanup=exports['_udeks_storage_cleanup_error'][0]
    base=dict((row[0],row[1]) for row in ALLOCATIONS)[6]
    maps={n:map_exports((fixture/n/(n+'.map')).read_text()) for n in ('holder','parent')}
    records=[]; port=choose_port()
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',a.drive,
         '-drive9truedrive','-drive9type',a.drive,'-attach9rw' if a.full_only else '-attach9ro',
         '-9',str(media['full' if a.full_only else 'protected'])),
        log_path=work/'vice.log')
    def capture(tag,address,size=1,bank='kernel'):
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def wait(tag,address,expected,bank='kernel'):
        until=time.monotonic()+150
        while True:
            value=capture(tag,address,len(expected),bank)
            if value==expected: return
            if time.monotonic()>until: raise TimeoutError((tag,value.hex(),expected.hex()))
            if tag in ('writer-stage','parent-stage') and value[0]>=128: raise AssertionError((tag,value.hex()))
            time.sleep(.05)
    def console():
        cells=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(cells[i:i+64].decode('ascii',errors='replace').rstrip() for i in range(0,1365,65))
    def command(line,contains='',status=0):
        wait('prompt',slots+1,b'\4\2'); previous=byte(port,0xf3d8)
        type_command(port,queue,line,time.monotonic()+150)
        sp.wait_for_byte(port,0xf3d8,(previous+1)&255,time.monotonic()+150)
        wait('prompt',slots+1,b'\4\2'); output=console()
        messages=(contains,) if isinstance(contains,str) else contains
        if not any(message in output for message in messages) or (status is not None and byte(port,0xf287)!=status):
            raise AssertionError((line,byte(port,0xf287),output))
        records.append(dict(command=line,console=output,status=status)); print('PASS',line,flush=True)
    def addr(name,symbol): return maps[name][symbol][0]-0x1000+base
    def client(symbol): return addr('holder','_writer_'+symbol)
    def release(value): sp.write_blocks(port,[(client('release'),bytes((value,)))],'worker')
    def gen(tag): return capture('generation',generations+tag,1,'worker')[0]
    def retired(tag,previous,error=0):
        wait('retired',generations+tag,bytes(((previous+1)&255,)),'worker')
        wait('cleanup',cleanup,bytes((error,)),'worker')
        records.append(dict(retired=tag,before=previous,after=gen(tag),cleanup_error=error))
    def start(case):
        before=gen(6); command('whold &',status=None)
        wait('writer-stage',client('stage'),b'\1','worker')
        sp.write_blocks(port,[(client('case'),bytes((case,)))],'worker'); release(1)
        wait('writer-stage',client('stage'),b'\2','worker')
        return before
    def select(name):
        command('umount /mnt')
        monitor_command(port,'detach 9')
        monitor_command(port,f'attach "{media[name]}" 9')
        command('mount -o rw 9 /mnt','ready (read-write)')
    def resource(name,value):
        response=monitor_command(port,f'resourceset "{name}" "{value}"')
        observed=monitor_command(port,f'resourceget "{name}"').decode(errors='replace')
        if 'ERROR' in response.decode(errors='replace').upper() or f'{name}={value}' not in observed:
            raise AssertionError(('resource change failed',response,observed))
    try:
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        if a.full_only:
            command('mount -o rw 9 /mnt','ready (read-write)')
            command('save /mnt/FULL 515','No space left on device',1)
            return  # diagnostic only, never emits a full qualification report
        # A failed IEC handshake may report EIO before absence is classified.
        command('mount 11 /mnt',('No such device','Input/output error'),1)
        command('mount -o rw 9 /mnt','ready (read-write)')
        command('save /mnt/NO 24','Read-only filesystem',1)
        command('save -c /mnt/KEEP 24','save: verified')
        command('umount /mnt'); monitor_command(port,'detach 9')
        if media['protected'].read_bytes()!=preimages['protected']: raise AssertionError('protected disk changed')
        # Qualify the writable phase in a fresh drive instance. Do not depend
        # on emulator-specific runtime write-protect resource/cache behavior.
        sp.terminate(proc,port); os.close(master); master=None
        port=choose_port()
        proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
            ('-console','-jamaction','5','-drive8truedrive','-drive8type',a.drive,
             '-drive9truedrive','-drive9type',a.drive,'-attach9rw','-9',str(media['normal'])),
            log_path=work/'vice-writable.log')
        sp.wait_for_byte(port,0xf3e0,2,time.monotonic()+240)
        records.append(dict(phase='fresh-writable-boot'))
        command('mount -o rw 9 /mnt','ready (read-write)')
        for name in ('RETURN1','RETURN2'):
            previous=gen(9); command('wleak /mnt/'+name); retired(9,previous)
            command('save -c /mnt/'+name+' 24','save: verified')
        previous=start(0); release(1)
        wait('writer-stage',client('stage'),b'\3','worker'); wait('writer-free',slots+5*8+1,b'\0')
        retired(6,previous); command('save -c /mnt/OWNER0 24','save: verified')
        # A pure native writer does not poll the GRAPHICS close event used by
        # name -q; don't mistake that advisory UI event for lifecycle CANCEL.
        # Reuse/EXIT here; the parent below issues actual CANCEL/WAITPID.
        previous=start(1); release(1)
        wait('writer-free',slots+5*8+1,b'\0'); retired(6,previous)
        command('save -c /mnt/OWNER1 24','save: verified')
        parent_before,child_before=gen(6),gen(2)
        command('parent &',status=None)
        wait('parent-stage',addr('parent','_parent_stage'),b'\2','worker')
        sp.write_blocks(port,[(addr('parent','_parent_release'),b'\1')],'worker')
        wait('parent-stage',addr('parent','_parent_stage'),b'\4','worker')
        wait('parent-free',slots+5*8+1,b'\0'); wait('child-reaped',slots+8+1,b'\0')
        retired(6,parent_before); retired(2,child_before)
        command('save -c /mnt/CHILD 24','save: verified')
        select('full'); command('save /mnt/FULL 515','No space left on device',1)
        command('save -c /mnt/KEEP 24','save: verified'); command('cat /hello','HELLO UDEKS')
        select('partial'); command('save /mnt/PARTIAL 4096','No space left on device',1)
        command('save -c /mnt/KEEP 24','save: verified'); command('cat /hello','HELLO UDEKS')
        for name,action,case in (('removed',2,2),('close',3,3)):
            if action==2 and a.skip_media_removal:
                records.append(dict(skipped='media-removal-during-write'))
                continue
            select(name); previous=start(case)
            # Media removal checks WRITE. Power-off checks CLOSE separately:
            # drive firmware can acknowledge a buffered CLOSE despite eject.
            if action==3:
                resource('BusDevice9',0)
                resource('Drive9Type',0)
            else:
                monitor_command(port,'detach 9')
            release(action)
            wait('writer-stage',client('stage'),b'\4','worker'); wait('writer-free',slots+5*8+1,b'\0')
            error=capture('write-error',client('errno'),1,'worker')[0]
            closed=capture('close-error',client('closed'),1,'worker')[0]
            accepted=capture('write-accepted',client('written'),1,'worker')[0]
            if closed not in (5,19) or (action==2 and not error and accepted==24):
                raise AssertionError((name,error,closed,accepted))
            retired(6,previous)
            records.append(dict(fault=name,write_error=error,accepted=accepted,close_error=closed))
            command('umount /mnt')
            if action==3:
                monitor_command(port,'detach 9')
                resource('Drive9Type',a.drive)
            monitor_command(port,f'attach "{media["normal"]}" 9')
            command('mount -o rw 9 /mnt','ready (read-write)')
            command('save /mnt/RECOVER'+str(case)+' 24','save: created and verified')
        command('xclock &',status=None); sp.wait_for_byte(port,0xf246,1,time.monotonic()+120)
        command('save /mnt/AFTER 515','save: created and verified')
        command('xclock -q',status=None); sp.wait_for_byte(port,0xf246,0,time.monotonic()+120)
        command('cat /hello','HELLO UDEKS'); command('umount /mnt')
        if byte(port,0xf11b): raise AssertionError('task canary failure')
    except Exception as failure:
        (work/'failure.json').write_text(json.dumps(dict(
            drive=a.drive,error=repr(failure),vice_exit_status=proc.poll(),checks=records),indent=2)+'\n')
        try:
            print(console(),flush=True); print(monitor_command(port,'r').decode(errors='replace'),flush=True)
            capture('failure-request',0xf359,38); capture('failure-tasks',slots,64)
            capture('failure-storage',0xe000,384,'worker')
        except (OSError,TimeoutError) as diagnostic:
            print('monitor unavailable for diagnostics:',diagnostic,flush=True)
        raise
    finally:
        sp.terminate(proc,port)
        if master is not None: os.close(master)
    expected={'protected':set(),'normal':{'RETURN1','RETURN2','OWNER0','OWNER1','CHILD','RECOVER2','RECOVER3','AFTER'},
              'full':{'FULL'},'partial':{'PARTIAL'},'removed':{'OWNER2'},'close':{'OWNER3'}}
    if a.skip_media_removal:
        expected['normal'].remove('RECOVER2'); expected['removed']=set()
    results={name:audit(preimages[name],path.read_bytes(),expected[name]) for name,path in media.items()}
    normal=files(media['normal'].read_bytes())
    for name in expected['normal']:
        length=515 if name=='AFTER' else 24
        if normal.get(name.encode())!=bytes(i&255 for i in range(length)): raise AssertionError(('readback',name))
    if disk.read_bytes()!=system or a.disk.read_bytes()!=original: raise AssertionError('system/source disk changed')
    report=dict(drive=a.drive,disk_sha256=hashlib.sha256(original).hexdigest(),
        skipped=['media-removal-during-write'] if a.skip_media_removal else [],
        system_sha256=hashlib.sha256(system).hexdigest(),checks=records,files=results,
        media={n:dict(before_sha256=hashlib.sha256(preimages[n]).hexdigest(),
                      after_sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for n,path in media.items()})
    (work/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS selected public failure/retirement checks; skipped:',report['skipped'],work,flush=True)


if __name__=='__main__': main()
