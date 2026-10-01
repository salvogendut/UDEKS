/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Fixed-point model inspired by GEOBENCH's calculator. No graphics, kernel,
 * floating point, or CPU handoff dependencies. Truncation is toward zero.
 * GEOBENCH attribution and BSD-3-Clause notice: LICENSES/GEOBENCH.txt. */
#include "udeks/calc.h"

long udeks_calc_value;
unsigned char udeks_calc_error;
static long accumulator;
static unsigned char operation, fresh, fraction, negative, ready;

void udeks_calc_reset(void)
{
    udeks_calc_value = accumulator = 0;
    udeks_calc_error = operation = fraction = negative = 0;
    fresh = ready = 1;
}

static void fail(unsigned char error)
{
    udeks_calc_error = error;
    operation = 0;
    fresh = 1;
}

static void evaluate(void)
{
    long left, right, result;
    left = accumulator;
    right = udeks_calc_value;
    if (operation == '+') result = left + right;
    else if (operation == '-') result = left - right;
    else if (operation == '*') {
        /* Bound intermediate products explicitly on both 32-bit cc65 and
         * wider host longs. The v1 range limit is intentional. */
        if ((right < 0 ? -right : right) != 0 &&
            (left < 0 ? -left : left) >
            2000000000L / (right < 0 ? -right : right)) {
            fail(UDEKS_CALC_OVERFLOW);
            return;
        }
        result = left * right / 100L;
    } else {
        if (!right) { fail(UDEKS_CALC_DIV_ZERO); return; }
        result = left * 100L / right;
    }
    if (result > UDEKS_CALC_MAX || result < -UDEKS_CALC_MAX)
        fail(UDEKS_CALC_OVERFLOW);
    else udeks_calc_value = result;
}

void udeks_calc_key(unsigned char key)
{
    long magnitude;
    if (key == 'C') { udeks_calc_reset(); return; }
    if ((key >= '0' && key <= '9') || key == '.') {
        if (udeks_calc_error) udeks_calc_reset();
        if (fresh) {
            udeks_calc_value = 0;
            fraction = negative = fresh = 0;
        }
        ready = 1;
        if (key == '.') { if (!fraction) fraction = 1; return; }
        magnitude = udeks_calc_value < 0 ? -udeks_calc_value : udeks_calc_value;
        key -= '0';
        if (!fraction) magnitude = magnitude * 10L + (long)key * 100L;
        else if (fraction < 3) {
            magnitude += fraction == 1 ? key * 10u : key;
            ++fraction;
        } else return;
        if (magnitude > UDEKS_CALC_MAX) { fail(UDEKS_CALC_OVERFLOW); return; }
        udeks_calc_value = negative ? -magnitude : magnitude;
        return;
    }
    if (udeks_calc_error) return;
    if (key == 'N') {
        if (fresh && operation && !ready) {
            udeks_calc_value = 0;
            fraction = fresh = negative = 0;
        }
        negative = !negative;
        udeks_calc_value = -udeks_calc_value;
        ready = 1;
        return;
    }
    if (key != '=' && key != '+' && key != '-' && key != '*' && key != '/') return;
    if (operation && ready) evaluate();
    if (udeks_calc_error) return;
    if (key == '=') operation = 0;
    else { accumulator = udeks_calc_value; operation = key; }
    fresh = 1;
    ready = 0;
    fraction = negative = 0;
}

void udeks_calc_format(char *buffer)
{
    char digits[9];
    unsigned char count = 0;
    unsigned long magnitude;
    if (udeks_calc_error) {
        *buffer++ = 'E';
        *buffer++ = (char)('0' + udeks_calc_error);
    } else {
        if (udeks_calc_value < 0 || (!fresh && negative)) *buffer++ = '-';
        magnitude = udeks_calc_value < 0 ? -udeks_calc_value : udeks_calc_value;
        do {
            digits[count++] = (char)('0' + magnitude % 10u);
            magnitude /= 10u;
        } while (magnitude || count < 3);
        while (count) {
            if (count == 2) *buffer++ = '.';
            *buffer++ = digits[--count];
        }
    }
    *buffer = 0;
}
