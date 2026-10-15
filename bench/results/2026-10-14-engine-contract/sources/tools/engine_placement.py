#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build engine slice-1 link probes and verify all mixed launch orders."""
import hashlib,json,subprocess
from pathlib import Path
from native_app_layout import fitting_allocations,check_coexistence
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'build/engine'
    jobs=[('server','server-placement','EPLSRV',['tools/build_native_console.py','--source','bench/engine/placement_server.c']),
          ('client','client-placement','EPLCLI',['tools/build_native_console.py','--source','bench/engine/placement_client.c']),
          ('clock','clock','ECLOCK',['tools/build_graphical_example.py','--source','user/bin/xclock_native.c','--source','user/lib/clock_face.c','--graphics-abi','10','--static-locals','--capacity','2816']),
          ('draw','draw','EDRAW',['tools/build_graphical_example.py','--source','user/bin/xdraw.c','--capacity','2560'])]
    programs={};fits={}
    for label,directory,name,args in jobs:
        subprocess.run(['python3',*args,'--name',name,'--output',str(out/directory)],cwd=ROOT,check=True)
        path=out/directory/(name+'.BIN');data=path.read_bytes()
        fits[label]=fitting_allocations(data)
        programs[label]={'file':len(data),'image':int.from_bytes(data[10:12],'little'),'bss':int.from_bytes(data[12:14],'little'),'fits':fits[label],'sha256':hashlib.sha256(data).hexdigest()}
    report={'scope':'compile/link placement only; not runnable service or runtime qualification','programs':programs,'launch_orders':check_coexistence(fits),'resident_bytes_added':0}
    (out/'placement.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
