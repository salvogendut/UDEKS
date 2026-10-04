/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Real private cc65 frames survive SLEEP at variable recursion depths. */
#ifndef CLIENT_TAG
#error CLIENT_TAG is required
#endif
extern void __fastcall__ probe_request(unsigned char operation);
volatile unsigned char probe_ready, probe_control, probe_error;
volatile unsigned int probe_progress;
volatile unsigned char probe_operation, probe_sequence;
volatile unsigned int probe_low_sp = 0xffffu;
volatile unsigned int probe_value = CLIENT_TAG * 1000u;

static unsigned int frame(unsigned char depth, unsigned int seed)
{
    unsigned char bytes[9];
    unsigned char i;
    unsigned int result, expected;
    for (i = 0; i != 9; ++i) bytes[i] = (unsigned char)(seed+i+CLIENT_TAG);
    expected = seed;
    if (depth) result = frame(depth-1u, seed+17u)-17u;
    else {
        probe_request(13);           /* SLEEP(2), with these C locals still live */
        result = seed;
    }
    for (i = 0; i != 9; ++i)
        if (bytes[i] != (unsigned char)(expected+i+CLIENT_TAG)) probe_error = 1;
    if (result != expected) probe_error = 2;
    return result;
}

#ifdef PROBE_RELOCATION
/* Linker relocation must cover initialized data/function/BSS pointers, not
 * just JSR operands. Numeric lookalikes and the common syscall address stay. */
extern unsigned char probe_split_ok(void);
static unsigned int (* volatile indirect_frame)(unsigned char, unsigned int) = frame;
static volatile unsigned int * volatile value_pointer = &probe_value;
static volatile unsigned int * volatile bss_pointer = &probe_progress;
static const unsigned char text[] = "relocation";
static const unsigned char * volatile text_pointer = text;
static volatile unsigned int address_lookalike = 0x1234;
#endif

unsigned char udeks_program_main(unsigned char count, unsigned char **arguments)
{
    if (count || arguments) return 0xfe;
#ifdef PROBE_RELOCATION
    if (probe_progress || probe_ready || probe_control || probe_error ||
        *bss_pointer || *value_pointer != 3000 || text_pointer[3] != 'o' ||
        address_lookalike != 0x1234 || !probe_split_ok()) return 0xfd;
#endif
    probe_ready = 0xa5;
    while (!probe_control && !probe_error) {
#ifdef PROBE_RELOCATION
        if (indirect_frame(2u+(probe_progress&3u), *value_pointer) != *value_pointer ||
            *bss_pointer != probe_progress || !probe_split_ok()) probe_error = 5;
#else
        if (frame(2u+(probe_progress&3u), probe_value) != probe_value) probe_error = 3;
#endif
        probe_value += CLIENT_TAG;
        ++probe_progress;
        probe_request(10);           /* ordinary cooperative YIELD */
    }
    return probe_error ? probe_error : 40u+CLIENT_TAG;
}
