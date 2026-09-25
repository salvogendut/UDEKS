# Bank-1 8502 cooperative-task gate 0.1

The persistent `/bin/ush` task cannot occupy bank-0 application slot 1 or 2:
those slots currently retain `xclock` and `xwave`. It instead executes from
bank 1 at `$9000`, with its cc65 software stack growing down from `$EFF0`.
The resident Z80 image remains at `$2000-$3FFF`, and the VIC-IIe window remains
at `$4000-$7FFF`. Its saved `$02-$1F` cc65 zero-page image occupies bank-1
`$8FE0-$8FFD`, immediately below the program load address; the resident copy is
kept in ordinary bank-0 BSS.

The 8502 enters the task through common RAM, which remains visible under both
MMU profiles:

| Address | Operation |
|---:|---|
| `$FF05` | `UTG1` header and state |
| `$FF10` | Reset the saved user context |
| `$FF13` | Run one cooperative poll at `$9000` |

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

Code in bank 1 cannot call the bank-0 `$CF00` syscall page. The next ABI step
will define a common-RAM request/yield protocol so task-side Linux-shaped
wrappers can ask the resident kernel to perform terminal and process services
between polls. Only after that protocol exists can init install and poll
`/bin/ush`.
