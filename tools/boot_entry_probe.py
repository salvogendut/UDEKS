#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check a typed BASIC BOOT with a true drive, separately from autoboot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import shadow_boot_probe as sp
from build_d71 import blank_d71, d64_compatibility_image
from build_d81 import blank_d81
from vice_capture import choose_port, monitor_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disk', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', default='c128')
    parser.add_argument('--drive', choices=('1541','1571','1581'), default='1541')
    args = parser.parse_args()
    work = args.output.resolve(); work.mkdir(parents=True, exist_ok=True)
    suffix={'1541':'.d64','1571':'.d71','1581':'.d81'}[args.drive]
    blank = work/('blank'+suffix)
    blank.write_bytes(blank_d81() if args.drive=='1581' else
                      d64_compatibility_image(blank_d71()) if args.drive=='1541' else blank_d71())
    port = choose_port()
    process, master = sp.launch_vice(blank, port, 'net.sf.VICE',
        ('-drive8truedrive', '-drive8type', args.drive, '-model', args.model))
    try:
        # Let the stock ROM reach BASIC on a non-bootable disk. No machine
        # state is patched: attach the candidate, then type the BASIC command.
        time.sleep(10)
        monitor_command(port, f'attach "{args.disk.resolve()}" 8')
        # The monitor's keybuf consumes the rest of the line literally;
        # surrounding quotes would type a quote into BASIC (syntax error).
        monitor_command(port, 'keybuf boot\\n')
        print('BASIC BOOT submitted', flush=True)
        try:
            sp.wait_for_byte(port, 0xf3d9, 0xa5, time.monotonic()+210)
        except TimeoutError:
            (work/'registers.txt').write_bytes(monitor_command(port, 'r'))
            (work/'map.txt').write_bytes(monitor_command(port, 'm ff00 ff04'))
            (work/'basic-screen.txt').write_bytes(monitor_command(port, 'm 0400 07e7'))
            raise
        status = sp.capture_blocks(port, [
            (work/'boot.bin', 0xf040, 0xf0bf, 'kernel'),
            (work/'shell.bin', 0xf3d8, 0xf3e2, 'kernel'),
            (work/'probe-site.bin', 0x8000, 0x8007, 'kernel')])
        (work/'result.json').write_text(json.dumps(dict(
            disk_sha256=hashlib.sha256(args.disk.read_bytes()).hexdigest(),
            entry='BASIC BOOT', model=args.model, drive=args.drive,
            shell=status[1].hex(), probe_site=status[2].hex()), indent=2)+'\n')
        print('PASS typed BOOT:', args.model, args.disk, flush=True)
    finally:
        sp.terminate(process, port); os.close(master)


if __name__ == '__main__': main()
