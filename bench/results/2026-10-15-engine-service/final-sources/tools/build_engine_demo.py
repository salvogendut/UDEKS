#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Add the engine server/client to new system disk copies; preserve baseline."""
import hashlib,json
from pathlib import Path
from add_disk_apps import add_apps,directory_names
from native_app_layout import fitting_allocations,check_coexistence
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'build/engine/demo';out.mkdir(parents=True,exist_ok=True)
    programs={name:(ROOT/f'build/engine/{folder}/{name}.BIN').read_bytes() for name,folder in [('ENGINE','server'),('ENGTEST','client')]}
    fits={name:fitting_allocations(data) for name,data in programs.items()}
    fits.update({name:fitting_allocations((ROOT/f'build/user/{name}.udx').read_bytes()) for name in ('xclock','xdraw')})
    h=lambda data:hashlib.sha256(data).hexdigest()
    report={'scope':'independent engine IPC server/client; unchanged kernel and standard apps','programs':{name:{'sha256':h(data),'fits':fits[name]} for name,data in programs.items()},'graphics':{name:{'sha256':h((ROOT/f'build/user/{name}.udx').read_bytes()),'fits':fits[name]} for name in ('xclock','xdraw')},'launch_orders':check_coexistence(fits),'disks':{}}
    for fmt in ('d64','d71','d81'):
        path=out/f'udeks-engine.{fmt}';original=(ROOT/f'build/boot/udeks.{fmt}').read_bytes()
        try:data=add_apps(original,[(name+'.BIN',image) for name,image in programs.items()])
        except ValueError as error:
            if fmt!='d64' or str(error)!='side one has no room for disk PRG':raise
            path.unlink(missing_ok=True);report['d64']={'skipped':str(error),'program_blocks':sum((len(p)+253)//254 for p in programs.values())};continue
        assert directory_names(data)==directory_names(original)|{b'ENGINE.BIN',b'ENGTEST.BIN'}
        path.write_bytes(data);report['disks'][fmt]={'source_sha256':h(original),'sha256':h(data)}
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
