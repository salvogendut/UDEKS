#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate capability force-import flags and the private typed bridge.

od65 reports raw import records, not unique symbols: hardware_capability.o has
32 records resolving to 23 unique providers (21 absolute, 2 zero-page). The
canonical set is validated, deduplicated by name, and sorted for deterministic
output. The same canonical set feeds the typed bridge generation, which must
define exactly those 23 symbols.
"""

import re
import subprocess
import sys
from pathlib import Path

EXPECTED_RECORDS = 32
EXPECTED_IMPORTS = 23
EXPECTED_ABSOLUTE = 21
EXPECTED_ZEROPAGE = 2
ZEROPAGE = "01"
ABSOLUTE = "02"
SYMBOL_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
MAP_SYMBOL = re.compile(
    r"(?<!\S)([A-Za-z_][A-Za-z0-9_]*)\s+"
    r"([0-9A-Fa-f]{6})\s+(RLA|RLZ|REA)(?!\S)"
)


def canonicalize(records: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Deduplicate (name, size) records and reject conflicting types."""
    canonical: dict[str, str] = {}
    for name, size in records:
        if SYMBOL_NAME.fullmatch(name) is None:
            raise ValueError(f"unsafe symbol name {name!r}")
        if size not in (ZEROPAGE, ABSOLUTE):
            raise ValueError(f"{name}: unsupported address size 0x{size}")
        if name in canonical and canonical[name] != size:
            raise ValueError(
                f"{name}: conflicting address types "
                f"0x{canonical[name]} and 0x{size}"
            )
        canonical[name] = size
    return sorted(canonical.items())


def validate_contract(imports: list[tuple[str, str]]) -> None:
    """Lock the canonical provider count and address-class split."""
    absolute = sum(size == ABSOLUTE for _, size in imports)
    zeropage = sum(size == ZEROPAGE for _, size in imports)
    if len(imports) != EXPECTED_IMPORTS:
        raise ValueError(
            f"expected {EXPECTED_IMPORTS} unique imports, found {len(imports)}"
        )
    if absolute != EXPECTED_ABSOLUTE or zeropage != EXPECTED_ZEROPAGE:
        raise ValueError(
            "expected import types "
            f"{EXPECTED_ABSOLUTE} absolute/{EXPECTED_ZEROPAGE} zero-page, "
            f"found {absolute} absolute/{zeropage} zero-page"
        )


def object_imports(path: str) -> list[tuple[str, str]]:
    dump = subprocess.run(
        ["od65", "--dump-imports", path],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    entries = re.findall(
        r'Address size:\s+0x([0-9A-Fa-f]+).*?Name:\s*"([^"]+)"', dump, re.S
    )
    if len(entries) != EXPECTED_RECORDS:
        raise ValueError(
            f"expected {EXPECTED_RECORDS} import records, found {len(entries)}"
        )
    imports = canonicalize([(name, size.lower()) for size, name in entries])
    validate_contract(imports)
    return imports


def render_flags(imports: list[tuple[str, str]]) -> str:
    # ld65's command-line force import is absolute and therefore unsuitable
    # for zero-page providers. The resident kernel naturally imports ptr1/sp;
    # bridge validation still requires them in both maps with RLZ type.
    return " ".join(
        f"-u {name}" for name, size in imports if size == ABSOLUTE
    ) + "\n"


def map_exports(text: str) -> dict[str, tuple[int, str]]:
    """Parse the by-name export table from an ld65 map."""
    marker = "Exports list by name:"
    end_marker = "Exports list by value:"
    if marker not in text or end_marker not in text:
        raise ValueError("ld65 map has no complete by-name export table")
    table = text.split(marker, 1)[1].split(end_marker, 1)[0]
    exports: dict[str, tuple[int, str]] = {}
    for match in MAP_SYMBOL.finditer(table):
        name, address, kind = match.groups()
        value = (int(address, 16), kind)
        if name in exports and exports[name] != value:
            raise ValueError(f"{name}: conflicting definitions in linker map")
        exports[name] = value
    return exports


def resolve_bridge(
    imports: list[tuple[str, str]],
    normal: dict[str, tuple[int, str]],
    panic: dict[str, tuple[int, str]],
) -> list[tuple[str, str, int]]:
    """Resolve the canonical imports and enforce normal/panic parity."""
    resolved: list[tuple[str, str, int]] = []
    for name, size in imports:
        expected_kind = "RLZ" if size == ZEROPAGE else "RLA"
        if name not in normal:
            raise ValueError(f"{name}: missing from normal kernel map")
        if name not in panic:
            raise ValueError(f"{name}: missing from panic kernel map")
        if normal[name] != panic[name]:
            raise ValueError(
                f"{name}: normal/panic mismatch "
                f"{normal[name]} != {panic[name]}"
            )
        address, kind = normal[name]
        if kind != expected_kind:
            raise ValueError(
                f"{name}: map type {kind}, expected {expected_kind}"
            )
        resolved.append((name, size, address))
    return resolved


def render_bridge(resolved: list[tuple[str, str, int]]) -> str:
    """Render absolute ca65 exports plus link-time image assertions."""
    lines = [
        "; Generated by tools/gen_capability_imports.py; do not edit.",
        "; SPDX-License-Identifier: GPL-3.0-or-later",
        "",
        '        .setcpu "6502"',
        "",
    ]
    for name, size, address in resolved:
        directive = ".exportzp" if size == ZEROPAGE else ".export"
        lines.append(f"        {directive} {name}")
        lines.append(f"{name} = ${address:04x}")
    lines.extend(
        [
            "",
            "        .import _udeks_capability_start",
            "        .import __CODE_SIZE__, __BSS_RUN__, __BSS_SIZE__",
            "        .assert _udeks_capability_start = $0200, lderror, \"capability entry moved\"",
            "        .assert __CODE_SIZE__ = $03c7, lderror, \"capability image size drift\"",
            "        .assert __BSS_RUN__ = $05c7, lderror, \"capability BSS moved\"",
            "        .assert __BSS_SIZE__ = $0001, lderror, \"capability BSS size drift\"",
            "",
        ]
    )
    return "\n".join(lines)


def write_bridge(
    object_path: str, normal_map: str, panic_map: str, output_path: str
) -> None:
    imports = object_imports(object_path)
    normal = map_exports(Path(normal_map).read_text(encoding="utf-8"))
    panic = map_exports(Path(panic_map).read_text(encoding="utf-8"))
    resolved = resolve_bridge(imports, normal, panic)
    Path(output_path).write_text(render_bridge(resolved), encoding="utf-8")


def write_constants(
    image_path: str, normal_map: str, panic_map: str, output_path: str,
    config_path: str,
) -> None:
    image = Path(image_path).read_bytes()
    if len(image) != 0x03C7:
        raise ValueError(f"capability image is {len(image)} bytes, expected 967")
    normal = map_exports(Path(normal_map).read_text(encoding="utf-8"))
    panic = map_exports(Path(panic_map).read_text(encoding="utf-8"))
    name = "__VICSHADOW_RUN__"
    if name not in normal or name not in panic:
        raise ValueError("VICSHADOW start is missing from a resident map")
    if normal[name] != panic[name]:
        raise ValueError("normal/panic VICSHADOW starts differ")
    source, kind = normal[name]
    if kind != "RLA":
        raise ValueError("VICSHADOW start is not an absolute label")
    end = source + len(image) - 1
    if end >= 0xACD9:
        raise ValueError(
            f"capability staging ${source:04x}-${end:04x} reaches the "
            "scheduler manifest"
        )
    checksum = sum(image) & 0xFFFF
    installer = end + 1
    installer_size = 0xACD9 - installer
    lines = [
        "; Generated by tools/gen_capability_imports.py; do not edit.",
        "; SPDX-License-Identifier: GPL-3.0-or-later",
        f"CAPABILITY_STAGE_SOURCE = ${source:04x}",
        f"CAPABILITY_IMAGE_SIZE = ${len(image):04x}",
        f"CAPABILITY_IMAGE_CHECKSUM = ${checksum:04x}",
        "CAPABILITY_DESTINATION = $0200",
        "CAPABILITY_BSS = $05c7",
        f"CAPABILITY_INSTALLER = ${installer:04x}",
        "",
    ]
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    config = f"""# Generated by tools/gen_capability_imports.py; do not edit.
# SPDX-License-Identifier: GPL-3.0-or-later

MEMORY {{
    INSTALL: start = ${installer:04X}, size = ${installer_size:04X},
             type = ro, file = %O;
}}

SEGMENTS {{
    CODE: load = INSTALL, type = ro;
}}
"""
    Path(config_path).write_text(config, encoding="utf-8")


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "flags":
        try:
            imports = object_imports(sys.argv[2])
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        Path(sys.argv[3]).write_text(render_flags(imports), encoding="utf-8")
        return 0
    if len(sys.argv) == 6 and sys.argv[1] == "bridge":
        try:
            write_bridge(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    if len(sys.argv) == 7 and sys.argv[1] == "constants":
        try:
            write_constants(
                sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
            )
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        return 0
    else:
        print(
            "usage:\n"
            "  gen_capability_imports.py flags <object> <out.txt>\n"
            "  gen_capability_imports.py bridge <object> <normal.map> "
            "<panic.map> <out.s>\n"
            "  gen_capability_imports.py constants <image> <normal.map> "
            "<panic.map> <out.inc> <out.cfg>",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
