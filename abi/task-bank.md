# Bank-1 8502 cooperative-task gate 0.2

The persistent `/bin/ush` task cannot occupy bank-0 application slot 1 or 2:
those slots retain loader-managed `xclock` and `xwave` after first use. It instead executes from
bank 1 at `$9000`, with its cc65 software stack growing down from `$EFF0`.
The resident Z80 image remains at `$2000-$3FFF`, and the VIC-IIe window remains
at `$4000-$7FFF`. Each physical bank reserves `$E2E2-$E2FF` for its own saved
`$02-$1F` cc65 zero-page image. Selecting the MMU profile therefore selects the
context without consuming common RAM.

The `none` runtime places its two-byte software-stack pointer at zero-page
`$02-$03`. Because the saved context begins with zero page `$02`, context
bytes 0 and 1 must be initialized to `$EFF0`. This offset is an executable ABI
invariant: initializing `$06-$07` instead leaves `sp` at zero and makes the
first C stack allocation wrap into top common RAM.

The 8502 enters the task through common RAM, which remains visible under both
MMU profiles:

| Address | Operation |
|---:|---|
| `$FF05` | `UTG1` header and state |
| `$FF10` | Reset the saved user context |
| `$FF13` | Run one cooperative poll at `$9000` |
| `$FF16` | Perform one synchronous common-record request |

The poll gate performs this bounded transition:

1. mask interrupts and save the resident cc65 zero-page reservation `$02-$1F`;
2. select the bank-1 flat MMU profile and restore the task's saved zero page,
   including its `$EFF0` software-stack pointer;
3. call `$9000` and preserve its A/X result on the physical bank-0 hardware
   stack;
4. save the task zero page and return to the bank-0 kernel-I/O profile;
5. restore the resident context and the caller's interrupt state;
6. return the task's eight-bit result in A, with X preserved from task return.

The hardware stack remains physical bank-0 page one and must be balanced when
the poll returns. Interrupts remain disabled during this initial cooperative
gate. A later scheduler will save full CPU and hardware-stack contexts rather
than treating task entry as a returning subroutine.

Code in bank 1 cannot directly call the bank-0 `$CF00` syscall page. The `$FF16`
gate saves the task context, restores the resident context, dispatches the
common [task request record](task-request.md) through `$CF30` and the permanent
`$F800` request gateway, and reverses the transition before returning. The
task-side wrappers provide nonblocking `read`, bounded `write`, compatibility
`exec`, foreground `wait`, and terminal `prompt`; signals and a true scheduler
yield remain later operations.

Request ABI 0.3 keeps those operations unchanged and reserves lifecycle
operations `10`-`15` (`yield`, `exit`, `waitpid`, `sleep`, `cancel`, and
`spawn`). The resident gateway accepts minor versions through `3` and returns
`ENOSYS` for the reserved operations until their implementations land.
