/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/mailbox.h"

#define MAILBOX_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_MAILBOX_BASE + (offset)))
#define WAVE_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WAVE_BUFFER_BASE + (offset)))

extern void udeks_z80_yield(void);

static const signed char sine64[64] = {
      0,  3,  6,  9, 12, 14, 17, 19, 21, 23, 25, 26, 28, 29, 29, 30,
     30, 30, 29, 29, 28, 26, 25, 23, 21, 19, 17, 14, 12,  9,  6,  3,
      0, -3, -6, -9,-12,-14,-17,-19,-21,-23,-25,-26,-28,-29,-29,-30,
    -30,-30,-29,-29,-28,-26,-25,-23,-21,-19,-17,-14,-12, -9, -6, -3
};

/* 40 * sinc(r), sampled every half unit from r=0 through r=17. */
static const signed char sinc_height[35] = {
    40, 38, 34, 27, 18, 10,  2, -4, -8, -9, -8, -5,
    -2,  1,  4,  5,  5,  4,  2,  0, -2, -3, -4, -3,
    -2,  0,  1,  2,  3,  3,  2,  1, -1, -2, -2
};

static unsigned char surface_height(
    unsigned char row, unsigned char column)
{
    unsigned char x;
    unsigned char y;
    unsigned char greater;
    unsigned char lesser;
    unsigned char radius;

    x = column > 12u ? column - 12u : 12u - column;
    y = row > 10u ? row - 10u : 10u - row;
    x *= 5u;
    y *= 6u;
    if (x > y) {
        greater = x;
        lesser = y;
    } else {
        greater = y;
        lesser = x;
    }
    radius = (unsigned char)(greater + (lesser >> 2) + (lesser >> 3));
    radius = (unsigned char)((radius * 2u + 2u) / 5u);
    if (radius > 34u) {
        radius = 34u;
    }
    return (unsigned char)sinc_height[radius];
}

static unsigned char validate_request(void)
{
    unsigned char offset;

    if (MAILBOX_BYTE(UDEKS_MB_MAGIC0) != 'U' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC1) != 'D' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC2) != 'E' ||
        MAILBOX_BYTE(UDEKS_MB_MAGIC3) != 'K') {
        return UDEKS_MB_STATUS_MAGIC;
    }
    if (MAILBOX_BYTE(UDEKS_MB_ABI_MAJOR) != UDEKS_MAILBOX_ABI_MAJOR ||
        MAILBOX_BYTE(UDEKS_MB_ABI_MINOR) > UDEKS_MAILBOX_ABI_MINOR) {
        return UDEKS_MB_STATUS_ABI;
    }
    if (MAILBOX_BYTE(UDEKS_MB_STATE) != UDEKS_MB_STATE_SUBMITTED) {
        return UDEKS_MB_STATUS_STATE;
    }
    if (MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_NOP &&
        MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_WAVE_SAMPLES &&
        MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_SURFACE_ROWS) {
        return UDEKS_MB_STATUS_OPCODE;
    }
    if (MAILBOX_BYTE(UDEKS_MB_OPCODE) == UDEKS_MB_OP_WAVE_SAMPLES &&
        (MAILBOX_BYTE(UDEKS_MB_LENGTH_HI) != 0 ||
         MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) == 0 ||
         MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) > UDEKS_WAVE_BUFFER_SIZE)) {
        return UDEKS_MB_STATUS_LENGTH;
    }
    if (MAILBOX_BYTE(UDEKS_MB_OPCODE) == UDEKS_MB_OP_SURFACE_ROWS &&
        (MAILBOX_BYTE(UDEKS_MB_ARG0_HI) != 0 ||
         MAILBOX_BYTE(UDEKS_MB_ARG0_LO) > 20u ||
         MAILBOX_BYTE(UDEKS_MB_ARG1_HI) != 0 ||
         MAILBOX_BYTE(UDEKS_MB_ARG1_LO) == 0 ||
         MAILBOX_BYTE(UDEKS_MB_ARG1_LO) > 2u ||
         MAILBOX_BYTE(UDEKS_MB_ARG0_LO) +
             MAILBOX_BYTE(UDEKS_MB_ARG1_LO) > 21u ||
         MAILBOX_BYTE(UDEKS_MB_LENGTH_HI) != 0 ||
         MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) !=
             MAILBOX_BYTE(UDEKS_MB_ARG1_LO) * 25u)) {
        return UDEKS_MB_STATUS_LENGTH;
    }
    for (offset = 20u; offset < UDEKS_MAILBOX_SIZE; ++offset) {
        if (MAILBOX_BYTE(offset) != 0) {
            return UDEKS_MB_STATUS_RESERVED;
        }
    }
    return UDEKS_MB_STATUS_OK;
}

void z80_main(void)
{
    unsigned char status;
    unsigned char phase;
    unsigned char step;
    unsigned char index;
    unsigned char row;
    unsigned char rows;
    unsigned char column;

    for (;;) {
        status = validate_request();
        if (status == UDEKS_MB_STATUS_OK) {
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_RUNNING;
            phase = MAILBOX_BYTE(UDEKS_MB_ARG0_LO);
            if (MAILBOX_BYTE(UDEKS_MB_OPCODE) ==
                    UDEKS_MB_OP_WAVE_SAMPLES) {
                step = MAILBOX_BYTE(UDEKS_MB_ARG1_LO);
                for (index = 0;
                     index < MAILBOX_BYTE(UDEKS_MB_LENGTH_LO); ++index) {
                    WAVE_BYTE(index) = (unsigned char)sine64[phase >> 2];
                    phase += step;
                }
            } else if (MAILBOX_BYTE(UDEKS_MB_OPCODE) ==
                    UDEKS_MB_OP_SURFACE_ROWS) {
                row = MAILBOX_BYTE(UDEKS_MB_ARG0_LO);
                rows = MAILBOX_BYTE(UDEKS_MB_ARG1_LO);
                index = 0;
                while (rows-- != 0) {
                    for (column = 0; column < 25u; ++column) {
                        WAVE_BYTE(index++) = surface_height(row, column);
                    }
                    ++row;
                }
                phase = row;
            } else {
                phase = 0;
            }
            MAILBOX_BYTE(UDEKS_MB_RESULT_LO) = phase;
            MAILBOX_BYTE(UDEKS_MB_RESULT_HI) = 0;
            MAILBOX_BYTE(UDEKS_MB_STATUS) = UDEKS_MB_STATUS_OK;
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_COMPLETE;
        } else {
            MAILBOX_BYTE(UDEKS_MB_STATUS) = status;
            MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_ERROR;
        }
        udeks_z80_yield();
    }
}
