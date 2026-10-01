#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pack the actual linked native image and BSS, never an estimated BSS size."""
from pathlib import Path
import sys
from build_udex import build_executable
from build_scheduler_overlay import map_segments
from gen_capability_imports import map_exports

image, map_path, output = map(Path, sys.argv[1:])
text = map_path.read_text()
segments = map_segments(text)
base = segments['STARTUP'][0]
entry = map_exports(text)['_udeks_program_entry'][0]
Path(output).write_bytes(build_executable(image.read_bytes(),cpu=1,
    load_address=base,entry_address=entry,bss_size=segments['BSS'][2],flags=0))
