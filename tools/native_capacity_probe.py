#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-loader boundaries, rollback, then independent large C clients in VICE.

Private loader calls are made by a one-shot normal poll hook BEFORE graphics
installation; public launch/retirement afterwards uses the unmodified shell.
No CPU takeover, manual allocation or synthetic context activation.
"""
import argparse
import hashlib
import json
import os
import socket
from pathlib import Path
import time

from add_disk_apps import add_apps
from banked_loader_probe import poll_hook, request_record, SCRATCH
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports
from native_app_layout import fitting_allocations
from o65_to_udex import relocate_executable
from storage_shell_probe import sp, keyboard_queue_address, type_command
from task_waitpid_probe import scheduler_symbols
from vice_capture import choose_port, receive_prompts, quote_monitor_path

ROOT = Path(__file__).resolve().parents[1]


def fixture(size=32, bss=0, relocations=()):
    return (b'UDEX\0\2\1\0' + b''.join(n.to_bytes(2,'little') for n in (0x1000,size,bss,0x1000)) +
            b'\x60' + b'\xea'*(size-1) + len(relocations).to_bytes(2,'little') +
            b''.join(n.to_bytes(2,'little') for n in relocations))


def fixtures():
    bad = bytearray(fixture(5500)); bad[-2:] = b'\xff\xff'
    return {'edge':fixture(7168), 'bssedge':fixture(32,7136),
            'bssbad':fixture(32,7137), 'filebad':fixture(7424-17),
            'badlarge':bytes(bad), 'small':fixture(),
            'tailonly':fixture(4000,0,range(1,1704))}


def public_files(root=ROOT):
    files={name:(root/path).read_bytes() for name,path in (
        ('large','build/native-capacity/graphics/LARGE.BIN'),
        ('bigcon','build/native-capacity/console/BIGCON.BIN'))}
    example=(root/'build/generic-apps/example/HELLO.BIN').read_bytes()
    files.update({name:example for name in ('orbit','canvas','extra')})
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk',type=Path,required=True)
    parser.add_argument('--drive',choices=('1541','1571','1581'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--public-only',action='store_true',help='omit large negative fixtures for D64/D71 capacity')
    args=parser.parse_args(); work=args.output.resolve(); work.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'build/8502/udeks-8502.map').read_text()
    exports=map_exports(text); segments=map_segments(text)
    slots=scheduler_symbols(ROOT/'build/8502/udeks-scheduler-overlay.map')['_udeks_lifecycle_slots_private']
    loader=map_exports((ROOT/'build/boot/banked-loader.map').read_text())
    owned=loader['banked_owned'][0]
    queue=keyboard_queue_address(text,(ROOT/'build/8502/keyboard.s').read_text())
    files={} if args.public_only else fixtures()
    files.update(public_files())
    maps={name:map_exports((ROOT/f'build/native-capacity/{folder}/{stem}.map').read_text())
          for name,folder,stem in (('large','graphics','client'),('bigcon','console','console'))}
    for name in maps:
        if fitting_allocations(files[name]) or fitting_allocations(files[name],joined=True)!=[3]:
            raise AssertionError(('fixture must require joined allocation',name))
    image=add_apps(args.disk.read_bytes(),[(n.upper()+'.BIN',data) for n,data in files.items()])
    disk=work/('capacity'+args.disk.suffix); disk.write_bytes(image)
    port=choose_port(); records=[]
    proc,master=sp.launch_vice(disk,port,'net.sf.VICE',
        ('-console','-jamaction','5','-drive8truedrive','-drive8type',args.drive),log_path=work/'vice.log')

    def capture(tag,address,size,bank='kernel'):
        if bank=='worker':
            # Physical RAM, not the CPU view: an active relocated zero page
            # can reverse-map its D5xx address to another physical page.
            path=work/(tag+'.bin'); path.unlink(missing_ok=True)
            with socket.create_connection(('127.0.0.1',port),timeout=3) as connection:
                connection.settimeout(15)
                try:
                    connection.sendall(b'bank ram01\n'); receive_prompts(connection,2)
                    connection.sendall(b'bank\n'); banks=receive_prompts(connection)
                    if b'*ram00-01(01)' not in banks:
                        raise RuntimeError(('VICE physical bank 1 not selected',banks))
                    command=f'save {quote_monitor_path(path)} 0 {address:04x} {address+size-1:04x}\n'
                    connection.sendall(command.encode()); reply=receive_prompts(connection)
                    if b'Saving' not in reply: raise RuntimeError(reply)
                finally:
                    connection.sendall(b'bank cpu\n'); receive_prompts(connection)
                    connection.sendall(b'x\n')
            data=path.read_bytes()[2:]
            if len(data)!=size: raise AssertionError('short physical RAM capture')
            return data
        return sp.capture_blocks(port,[(work/(tag+'.bin'),address,address+size-1,bank)])[0]
    def byte(address,bank='kernel'):
        return capture('byte',address,1,bank)[0]
    def wait(address,value,bank='kernel',timeout=180):
        end=time.monotonic()+timeout
        while True:
            try:
                if byte(address,bank)==value: return
            except ConnectionRefusedError:
                if proc.poll() is not None: raise
            if time.monotonic()>end: raise TimeoutError((hex(address),value,bank))
            time.sleep(.05)
    def ownership(expected):
        actual=capture('ownership',owned,4,'worker')
        if actual!=bytes(expected): raise AssertionError(('ownership',actual.hex(),expected))
    def invoke(selector,name='',error=0):
        poll=exports['_udeks_managed_apps_poll'][0]
        if byte(exports['_udeks_banked_graphics_installed'][0]):
            raise AssertionError('probe scratch already belongs to graphics')
        record=request_record(name); original=capture('poll',poll,3)
        sp.write_kernel_blocks(port,[(SCRATCH,poll_hook(poll,original,selector,record)),
                                    (poll,b'\x4c'+SCRATCH.to_bytes(2,'little'))])
        wait(SCRATCH+0xed,1)
        response=capture('response',SCRATCH+0xc6,41)
        if response!=record+bytes((error,1,0x3e)) or capture('poll-after',poll,3)!=original:
            raise AssertionError((selector,name,error,response.hex()))
        records.append(dict(selector=selector,name=name,errno=error,request_preserved=True))
        print('PASS loader',hex(selector),name,error,flush=True)
    def console():
        data=capture('console',segments['LOWBSS'][0],0x558)
        return '\n'.join(data[i:i+64].decode('ascii',errors='replace') for i in range(0,1365,65))
    def prompt():
        end=time.monotonic()+180
        while capture('root-state',slots+1,2)!=b'\x04\x02':
            if time.monotonic()>end: raise TimeoutError(('prompt',console()))
            time.sleep(.05)
    def command(line,contains=''):
        prompt(); before=byte(0xf3d8)
        type_command(port,queue,line,time.monotonic()+180)
        wait(0xf3d8,(before+1)&255); prompt()
        output=console()
        if contains not in output: raise AssertionError((line,output))
        records.append(dict(command=line,console=output)); print('PASS',line,flush=True)
    def address(name,symbol):
        return maps[name]['_capacity_'+symbol][0]+0x1300
    def ready(name):
        wait(address(name,'ready'),0xa5,'worker')
        if byte(address(name,'error'),'worker'): raise AssertionError((name,'client error'))
        if byte(exports['_udeks_native_stack_pages'][0])!=0x3f:
            raise AssertionError('bank-0 effective bound not published')
        for where,size in ((0x3f00,16),(0x3fb0,16),(0xd600,1)):
            if capture(name+'-guard-'+hex(where),where,size,'worker')!=b'\xa5'*size:
                raise AssertionError(('guard',name,hex(where)))
        if not 0x3f10<=int.from_bytes(capture(name+'-sp',0xd502,2,'worker'),'little')<=0x3fb0:
            raise AssertionError('C stack not in borrowed final page')
        records.append(dict(client=name,ready=True,stack_page=0x3f))

    def private_checks():
        ownership((0,0,0,0))
        # Upper neighbour is display/cache; never touched by rejected writes.
        neighbour=capture('neighbour-before',0x4000,256,'worker')
        for name in ('edge','bssedge','tailonly'):
            invoke(3,name)
            joined=name!='tailonly'
            ownership((1,3 if joined else 0,0,0))
            data=relocate_executable(files[name],0x2300,0x1d00)
            bss=int.from_bytes(data[12:14],'little')
            expected=data[16:]+bytes(bss)
            if capture(name+'-installed',0x2300,len(expected),'worker')!=expected:
                raise AssertionError(('installed bytes',name))
            if joined:
                donor=capture('donor-before',0x3500,0xb00,'worker')
                for op in (4,0x44,0x84,0xc4): invoke(op,'small',16)
                if capture('donor-after',0x3500,0xb00,'worker')!=donor:
                    raise AssertionError('borrowed donor touched')
            else:
                invoke(4,'small'); ownership((1,1,0,0)); invoke(0x84)
            invoke(0x83); ownership((0,0,0,0))
        for name,error in (('bssbad',12),('filebad',12),('badlarge',8),('missing',2)):
            invoke(3,name,error); ownership((0,0,0,0))
        invoke(4,'small'); peer=capture('peer-before',0x3500,0xb00,'worker')
        invoke(3,'large',12); ownership((0,1,0,0))
        if capture('peer-after',0x3500,0xb00,'worker')!=peer:
            raise AssertionError('owned FREE peer overwritten')
        invoke(0x84)
        invoke(3,'small'); ownership((1,0,0,0))
        invoke(4,'small'); ownership((1,1,0,0))
        invoke(0x83); invoke(0x84); ownership((0,0,0,0))
        if capture('neighbour-after',0x4000,256,'worker')!=neighbour:
            raise AssertionError('loader crossed display boundary')
    try:
        wait(0xf3e0,2,timeout=240)
        if not args.public_only: private_checks()
        # From here all lifecycle transitions are ordinary public shell jobs.
        command('large &'); wait(0xf246,1); ready('large'); ownership((2,3,0,0))
        if maps['large']['_commands'][0]+0x1300<0x3500:
            raise AssertionError('drawing source did not exercise borrowed memory')
        command('orbit &'); command('canvas &'); wait(0xf246,3)
        ownership((2,3,2,2)); ready('large')
        command('extra &','task slot busy'); wait(0xf246,3); ownership((2,3,2,2))
        command('cowsay capacity'); ready('large')
        command('large -q'); wait(0xf246,2)
        command('orbit &'); command('canvas &'); wait(0xf246,4); ownership((2,2,2,2))
        if byte(exports['_udeks_native_stack_pages'][0])!=0x34:
            raise AssertionError('ordinary activation retained joined bound')
        command('large &','task slot busy'); wait(0xf246,4); ownership((2,2,2,2))
        command('extra &','task slot busy'); wait(0xf246,4)
        command('xinit -q'); wait(0xf246,0); ownership((0,0,0,0))
        # The same allocator runs a large console-only C program: no CREATE.
        command('bigcon &'); ready('bigcon'); wait(0xf246,0); ownership((2,3,0,0))
        command('cowsay console peer'); ready('bigcon')
        sp.write_blocks(port,[(address('bigcon','control'),b'\1')],'worker')
        end=time.monotonic()+120
        while capture('ownership',owned,4,'worker')!=bytes(4):
            if time.monotonic()>end: raise TimeoutError('returned console task retained loan')
            time.sleep(.05)
        command('large &'); ready('large'); wait(0xf246,1)
        command('xinit -q'); wait(0xf246,0); ownership((0,0,0,0))
        result=dict(drive=args.drive,private_boundaries=not args.public_only,records=records,
                    disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
                    test_disk_sha256=hashlib.sha256(image).hexdigest(),
                    loader_sha256=hashlib.sha256((ROOT/'build/boot/banked-loader.bin').read_bytes()).hexdigest(),
                    client_sha256={name:hashlib.sha256(files[name]).hexdigest() for name in maps})
        (work/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS generic capacity: exact boundaries, loans, rollback, reuse, graphics and console',flush=True)
    except Exception:
        capture('failure-bank0',0,65536); capture('failure-bank1',0,65536,'worker')
        raise
    finally:
        sp.terminate(proc,port)
        if master is not None: os.close(master)


if __name__=='__main__': main()
