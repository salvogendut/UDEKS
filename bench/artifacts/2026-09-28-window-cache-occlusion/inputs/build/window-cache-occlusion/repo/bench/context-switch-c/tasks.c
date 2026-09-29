/* SPDX-License-Identifier: GPL-3.0-or-later */

#define RESULT_FAILURE  (*(volatile unsigned char *)0xF1A7u)
#define RESULT_STEP_A   (*(volatile unsigned char *)0xF1AAu)
#define RESULT_STEP_B   (*(volatile unsigned char *)0xF1ABu)
#define RESULT_SUM_A_LO (*(volatile unsigned char *)0xF1ACu)
#define RESULT_SUM_A_HI (*(volatile unsigned char *)0xF1ADu)
#define RESULT_SUM_B_LO (*(volatile unsigned char *)0xF1AEu)
#define RESULT_SUM_B_HI (*(volatile unsigned char *)0xF1AFu)

#define ROUNDS 32u

void compiled_context_yield(void);

static unsigned char markers_equal(
    volatile unsigned char *markers,
    unsigned char first)
{
    unsigned char index;

    for (index = 0; index < 6u; ++index) {
        if (markers[index] != (unsigned char)(first + index)) {
            return 0;
        }
    }
    return 1;
}

void task_a_main(void)
{
    volatile unsigned char markers[6];
    unsigned char index;
    unsigned int total;
    unsigned int expected;

    total = 0x1234u;
    expected = 0x1234u;
    for (index = 0; index < 6u; ++index) {
        markers[index] = (unsigned char)(0xA1u + index);
    }
    for (index = 0; index < ROUNDS; ++index) {
        total += (unsigned int)index + 1u;
        expected += (unsigned int)index + 1u;
        RESULT_STEP_A = (unsigned char)(index + 1u);
        compiled_context_yield();
        if (total != expected || !markers_equal(markers, 0xA1u)) {
            RESULT_FAILURE = 1u;
        }
    }
    RESULT_SUM_A_LO = (unsigned char)total;
    RESULT_SUM_A_HI = (unsigned char)(total >> 8);
}

void task_b_main(void)
{
    volatile unsigned char markers[6];
    unsigned char index;
    unsigned int total;
    unsigned int expected;

    total = 0x4321u;
    expected = 0x4321u;
    for (index = 0; index < 6u; ++index) {
        markers[index] = (unsigned char)(0x51u + index);
    }
    for (index = 0; index < ROUNDS; ++index) {
        total += ((unsigned int)index + 1u) << 1;
        expected += ((unsigned int)index + 1u) << 1;
        RESULT_STEP_B = (unsigned char)(index + 1u);
        compiled_context_yield();
        if (total != expected || !markers_equal(markers, 0x51u)) {
            RESULT_FAILURE = 2u;
        }
    }
    RESULT_SUM_B_LO = (unsigned char)total;
    RESULT_SUM_B_HI = (unsigned char)(total >> 8);
}
