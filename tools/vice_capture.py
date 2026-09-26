#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run one UDEKS benchmark under VICE and capture its raw result block."""

from __future__ import annotations

import argparse
import os
import pty
import re
import socket
import subprocess
import threading
import time
from pathlib import Path


PROMPT_RE = re.compile(rb"\([A-Za-z0-9]+:\$[0-9a-fA-F]+\) ")


def parse_number(value: str) -> int:
    return int(value, 0)


def parse_poke(value: str) -> tuple[int, int]:
    try:
        address_text, byte_text = value.split("=", 1)
        address = parse_number(address_text)
        byte = parse_number(byte_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("poke must be ADDRESS=BYTE") from error
    if not 0 <= address <= 0xFFFF or not 0 <= byte <= 0xFF:
        raise argparse.ArgumentTypeError("poke address/byte is out of range")
    return address, byte


def parse_block(value: str) -> tuple[int, bytes]:
    address_text, separator, data_text = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("block must use ADDRESS=HEXBYTES")
    try:
        address = parse_number(address_text)
        data = bytes.fromhex(data_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("block address/data is invalid") from error
    if not data or address < 0 or address + len(data) > 0x10000:
        raise argparse.ArgumentTypeError("block must fit in 64 KiB")
    return address, data


def parse_keybuf(value: str) -> str:
    return value.replace(r"\n", "\n").replace(r"\r", "\r")


def parse_monitor_byte(reply: bytes, address: int) -> int:
    pattern = re.compile(
        rb">[A-Za-z0-9]+:" + f"{address:04x}".encode() + rb"\s+([0-9a-fA-F]{2})",
        re.IGNORECASE,
    )
    match = pattern.search(reply)
    if match is None:
        raise ValueError(f"VICE monitor did not return ${address:04X}")
    return int(match.group(1), 16)


def receive_prompts(connection: socket.socket, count: int = 1) -> bytes:
    reply = bytearray()
    while len(PROMPT_RE.findall(reply)) < count:
        chunk = connection.recv(4096)
        if not chunk:
            raise RuntimeError("VICE monitor closed before returning a prompt")
        reply.extend(chunk)
    return bytes(reply)


def monitor_command(port: int, command: str) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as connection:
        connection.settimeout(2.0)
        connection.sendall(command.encode("ascii") + b"\n")
        # A fresh text-monitor connection emits its initial prompt before the
        # command result, followed by a second prompt when the result is done.
        reply = receive_prompts(connection, 2)
        connection.sendall(b"x\n")
        return reply


def monitor_resume(port: int, command: str) -> None:
    """Send a monitor command that resumes the CPU and emits no completion."""
    with socket.create_connection(("127.0.0.1", port), timeout=2.0) as connection:
        connection.settimeout(0.5)
        connection.sendall(command.encode("ascii") + b"\n")
        try:
            connection.recv(4096)
        except (ConnectionError, OSError):
            pass


def choose_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def quote_monitor_path(path: Path) -> str:
    text = str(path.resolve())
    if '"' in text or "\n" in text or "\r" in text:
        raise ValueError("VICE monitor paths cannot contain quotes or newlines")
    return f'"{text}"'


def quote_monitor_text(text: str) -> str:
    if any(ord(character) < 0x20 and character not in "\n\r\t" for character in text):
        raise ValueError("VICE key buffer text contains an unsupported control byte")
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def make_basic_wrapper(program: bytes, entry: int) -> bytes:
    if len(program) < 2:
        raise ValueError("PRG is missing its load address")
    source_address = int.from_bytes(program[:2], "little")
    basic_address = 0x1C01
    digits = str(entry).encode("ascii")
    next_line = basic_address + 6 + len(digits)
    basic = (
        next_line.to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + b"\x9e"
        + digits
        + b"\x00\x00\x00"
    )
    if source_address < basic_address + len(basic):
        raise ValueError("PRG payload overlaps the temporary BASIC launcher")
    padding = bytes(source_address - basic_address - len(basic))
    return basic_address.to_bytes(2, "little") + basic + padding + program[2:]


def save_result_block(
    port: int, vice_output: Path, output: Path, address: int, size: int
) -> None:
    end = address + size - 1
    reply = monitor_command(
        port,
        f"save {quote_monitor_path(vice_output)} 0 {address:04x} {end:04x}",
    )
    if b"Saving file" not in reply:
        raise RuntimeError("VICE monitor did not confirm the result save")

    saved = vice_output.read_bytes()
    expected_prefix = address.to_bytes(2, "little")
    if saved[:2] != expected_prefix:
        raise RuntimeError("VICE result file has the wrong load address")
    block = saved[2:]
    if len(block) != size:
        raise RuntimeError(f"VICE captured {len(block)} bytes; expected {size}")
    output.write_bytes(block)


def capture(args: argparse.Namespace) -> None:
    program = args.program.resolve()
    output = args.output.resolve()
    screenshot = None if args.screenshot is None else args.screenshot.resolve()
    if not program.is_file():
        raise SystemExit(f"input image does not exist: {program}")
    if sum((args.autostart, args.native_disk, args.raw_load)) > 1:
        raise SystemExit(
            "--autostart, --native-disk, and --raw-load are mutually exclusive"
        )
    if not 0 <= args.entry <= 0xFFFF:
        raise SystemExit("entry address must fit in 16 bits")
    if not 0 <= args.result_address <= 0xFFFF:
        raise SystemExit("result address must fit in 16 bits")
    if args.result_size <= 0 or args.result_address + args.result_size > 0x10000:
        raise SystemExit("result block must fit in 64 KiB")
    if not 0 <= args.state_offset < args.result_size:
        raise SystemExit("state offset must lie inside the result block")
    if args.screenshot_delay < 0:
        raise SystemExit("screenshot delay must be non-negative")

    work = Path("build/vice").resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if screenshot is not None:
        if screenshot.suffix.lower() != ".bmp":
            raise SystemExit("VICE monitor screenshots must use a .bmp output name")
        screenshot.parent.mkdir(parents=True, exist_ok=True)
        screenshot.unlink(missing_ok=True)
    tag = f"{output.stem}-{os.getpid()}"
    commands_path = work / f"{tag}.mon"
    vice_output = work / f"{tag}.prg"
    wrapper_path = work / f"{tag}-launch.prg"
    log_path = work / f"{tag}.log"
    port = choose_port()

    launch_program = program
    if not args.autostart and not args.native_disk and not args.raw_load:
        try:
            wrapper_path.write_bytes(make_basic_wrapper(program.read_bytes(), args.entry))
        except ValueError as error:
            raise SystemExit(f"cannot wrap benchmark PRG: {error}") from error
        launch_program = wrapper_path

    commands = []
    if args.fast:
        commands.append("> d030 01")
    for address, byte in args.poke:
        commands.append(f"> {address:04x} {byte:02x}")
    commands.append("x")
    commands_path.write_text("\n".join(commands) + "\n", encoding="ascii")

    command = [
        "flatpak",
        "run",
        "--share=network",
        "--command=x128",
        args.flatpak_id,
        "-default",
        "+sound",
        "-warp",
        "-seed",
        "0",
        "-remotemonitor",
        "-remotemonitoraddress",
        f"ip4://127.0.0.1:{port}",
    ]
    if not args.raw_load:
        command.extend(
            (
                "-initbreak",
                f"0x{args.entry:04x}",
                "-moncommands",
                str(commands_path),
            )
        )
    command.extend(args.vice_arg)
    if args.native_disk:
        command.extend(("-8", str(launch_program)))
    elif not args.raw_load:
        command.extend(("-autostart", str(launch_program)))
    log_file = log_path.open("wb")
    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    def drain_output() -> None:
        try:
            while True:
                chunk = os.read(master_fd, 4096)
                if not chunk:
                    break
                log_file.write(chunk)
                log_file.flush()
        except OSError:
            pass

    output_thread = threading.Thread(target=drain_output, daemon=True)
    output_thread.start()
    deadline = time.monotonic() + args.timeout
    state_address = args.result_address + args.state_offset
    succeeded = False

    try:
        # Connecting during Flatpak/GTK startup can occupy the monitor socket
        # before the initial breakpoint plays its command file. VICE buffers
        # redirected logs, so a short fixed grace period is more reliable than
        # waiting for a log marker.
        time.sleep(min(5.0, max(0.0, deadline - time.monotonic())))
        if args.raw_load:
            # Launcher pokes need the inherited I/O map, so apply them before
            # switching to flat RAM for the load.
            if args.fast:
                monitor_command(port, "> d030 01")
            for address, byte in args.poke:
                monitor_command(port, f"> {address:04x} {byte:02x}")
            # Flat bank-0 RAM so the load reaches the RAM under the BASIC and
            # KERNAL ROMs; crt0 re-establishes the native profiles on entry.
            monitor_command(port, "> ff00 3f")
            monitor_command(port, f"load {quote_monitor_path(program)} 0")
            monitor_resume(port, f"goto {args.entry:04x}")
        if args.keybuf_ready is not None or args.keybuf_ready_block is not None:
            while time.monotonic() < deadline:
                try:
                    matches = True
                    expected = []
                    if args.keybuf_ready is not None:
                        expected.append(args.keybuf_ready)
                    if args.keybuf_ready_block is not None:
                        address, data = args.keybuf_ready_block
                        expected.extend(
                            (address + offset, value)
                            for offset, value in enumerate(data)
                        )
                    for ready_address, ready_value in expected:
                        reply = monitor_command(
                            port, f"m {ready_address:04x} {ready_address:04x}"
                        )
                        if parse_monitor_byte(reply, ready_address) != ready_value:
                            matches = False
                            break
                    if matches:
                        break
                except (ConnectionError, OSError, RuntimeError, ValueError):
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("VICE post-boot readiness byte did not match")
        for address, byte in args.ready_poke:
            monitor_command(port, f"> {address:04x} {byte:02x}")
        for address, data in args.ready_block:
            values = " ".join(f"{byte:02x}" for byte in data)
            monitor_command(port, f"> {address:04x} {values}")
        if args.ready_repeat_until is not None:
            repeat_address, repeat_value = args.ready_repeat_until
            while time.monotonic() < deadline:
                reply = monitor_command(
                    port, f"m {repeat_address:04x} {repeat_address:04x}"
                )
                if parse_monitor_byte(reply, repeat_address) == repeat_value:
                    break
                for address, data in args.ready_block:
                    values = " ".join(f"{byte:02x}" for byte in data)
                    monitor_command(port, f"> {address:04x} {values}")
                time.sleep(0.05)
            else:
                raise TimeoutError("VICE repeated ready block did not take effect")
        if args.keybuf is not None:
            monitor_command(port, f"keybuf {quote_monitor_text(args.keybuf)}")
        if args.followup_ready_block is not None:
            address, data = args.followup_ready_block
            while time.monotonic() < deadline:
                try:
                    matches = True
                    for offset, value in enumerate(data):
                        ready_address = address + offset
                        reply = monitor_command(
                            port, f"m {ready_address:04x} {ready_address:04x}"
                        )
                        if parse_monitor_byte(reply, ready_address) != value:
                            matches = False
                            break
                    if matches:
                        break
                except (ConnectionError, OSError, RuntimeError, ValueError):
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("VICE follow-up readiness block did not match")
        for address, data in args.followup_block:
            values = " ".join(f"{byte:02x}" for byte in data)
            monitor_command(port, f"> {address:04x} {values}")
        if args.followup_keybuf is not None:
            monitor_command(
                port, f"keybuf {quote_monitor_text(args.followup_keybuf)}"
            )
        state = None
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"VICE exited with status {process.returncode}")
            try:
                reply = monitor_command(port, f"m {state_address:04x} {state_address:04x}")
                state = parse_monitor_byte(reply, state_address)
            except (ConnectionError, OSError, RuntimeError, ValueError) as error:
                last_error = error
                time.sleep(0.1)
                continue
            if state == args.complete_value:
                break
            if state >= 0x80:
                if args.capture_incomplete:
                    save_result_block(
                        port,
                        vice_output,
                        output,
                        args.result_address,
                        args.result_size,
                    )
                raise RuntimeError(f"benchmark reported error state ${state:02X}")
            time.sleep(0.1)
        else:
            shown = "unreadable" if state is None else f"${state:02X}"
            if args.capture_incomplete and state is not None:
                save_result_block(
                    port,
                    vice_output,
                    output,
                    args.result_address,
                    args.result_size,
                )
                try:
                    registers = monitor_command(port, "r")
                    print(registers.decode("utf-8", errors="replace"))
                    stack = monitor_command(port, "m f2b0 f2ff")
                    print(stack.decode("utf-8", errors="replace"))
                    mmu = monitor_command(port, "m d505 d50a")
                    print(mmu.decode("utf-8", errors="replace"))
                    gateway = monitor_command(port, "m ffd0 fff4")
                    print(gateway.decode("utf-8", errors="replace"))
                except (ConnectionError, OSError, RuntimeError):
                    pass
            detail = "" if last_error is None else f"; last monitor error: {last_error}"
            raise TimeoutError(
                f"benchmark did not complete; state is {shown}{detail}; "
                f"VICE log: {log_path}"
            )

        save_result_block(
            port,
            vice_output,
            output,
            args.result_address,
            args.result_size,
        )
        if args.capture_incomplete:
            registers = monitor_command(port, "r")
            print(registers.decode("utf-8", errors="replace"))
        if screenshot is not None:
            if args.screenshot_delay != 0:
                time.sleep(args.screenshot_delay)
            monitor_command(
                port,
                f"screenshot {quote_monitor_path(screenshot)} 0",
            )
            if not screenshot.is_file():
                raise RuntimeError("VICE monitor did not create the requested screenshot")
        succeeded = True
        print(
            f"captured {args.result_size} bytes from "
            f"${args.result_address:04X} to {output}"
        )
    finally:
        if process.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1.0) as connection:
                    connection.settimeout(1.0)
                    connection.sendall(b"quit\n")
            except (ConnectionError, OSError, RuntimeError):
                process.terminate()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        os.close(master_fd)
        output_thread.join(timeout=1.0)
        commands_path.unlink(missing_ok=True)
        vice_output.unlink(missing_ok=True)
        wrapper_path.unlink(missing_ok=True)
        log_file.close()
        if succeeded:
            log_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("program", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--entry", type=parse_number, required=True)
    parser.add_argument("--result-address", type=parse_number, required=True)
    parser.add_argument("--result-size", type=parse_number, required=True)
    parser.add_argument("--state-offset", type=parse_number, required=True)
    parser.add_argument("--complete-value", type=parse_number, default=2)
    parser.add_argument("--fast", action="store_true", help="set $D030 bit 0 before entry")
    parser.add_argument(
        "--poke",
        action="append",
        default=[],
        type=parse_poke,
        metavar="ADDRESS=BYTE",
        help="write one launcher-owned byte before entering the benchmark",
    )
    parser.add_argument(
        "--keybuf",
        type=parse_keybuf,
        help=r"type text after launch; use \n for Return",
    )
    parser.add_argument(
        "--keybuf-ready",
        type=parse_poke,
        metavar="ADDRESS=BYTE",
        help="wait for a memory byte before typing --keybuf text",
    )
    parser.add_argument(
        "--keybuf-ready-block",
        type=parse_block,
        metavar="ADDRESS=HEXBYTES",
        help="wait for an exact memory byte sequence before injecting input",
    )
    parser.add_argument(
        "--followup-ready-block",
        type=parse_block,
        metavar="ADDRESS=HEXBYTES",
        help="after initial input, wait for a block before follow-up input",
    )
    parser.add_argument(
        "--followup-keybuf",
        type=parse_keybuf,
        help="type a second input after --followup-ready-block matches",
    )
    parser.add_argument(
        "--followup-block",
        action="append",
        default=[],
        type=parse_block,
        metavar="ADDRESS=HEXBYTES",
        help="write a block after --followup-ready-block matches",
    )
    parser.add_argument(
        "--ready-poke",
        action="append",
        default=[],
        type=parse_poke,
        metavar="ADDRESS=BYTE",
        help="write one byte after --keybuf-ready matches",
    )
    parser.add_argument(
        "--ready-block",
        action="append",
        default=[],
        type=parse_block,
        metavar="ADDRESS=HEXBYTES",
        help="write one contiguous byte block after --keybuf-ready matches",
    )
    parser.add_argument(
        "--ready-repeat-until",
        type=parse_poke,
        metavar="ADDRESS=BYTE",
        help="repeat --ready-block writes until a memory byte matches",
    )
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="input already contains a BASIC autostart stub",
    )
    parser.add_argument(
        "--native-disk",
        action="store_true",
        help="attach a C128 native-autoboot disk instead of autostarting a PRG",
    )
    parser.add_argument(
        "--raw-load",
        action="store_true",
        help="load the PRG through the monitor and jump to --entry; use for "
             "images that start below the BASIC launcher",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="save the active VICE canvas as a BMP after the result is ready",
    )
    parser.add_argument(
        "--screenshot-delay",
        type=float,
        default=0.0,
        help="seconds to let the display refresh after the result is ready",
    )
    parser.add_argument(
        "--vice-arg",
        action="append",
        default=[],
        help="append one raw VICE option (use --vice-arg=-option)",
    )
    parser.add_argument(
        "--capture-incomplete",
        action="store_true",
        help="save the result block on timeout for diagnosis",
    )
    parser.add_argument("--flatpak-id", default="net.sf.VICE")
    capture(parser.parse_args())


if __name__ == "__main__":
    main()
