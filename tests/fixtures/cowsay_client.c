/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Host stubs for cowsay.c: capture console output. */
#include <string.h>

unsigned char cowsay_output[512];
unsigned int cowsay_output_length;

unsigned char udeks_write(unsigned char fd, const unsigned char *text)
{
    (void)fd;
    while (*text != 0 && cowsay_output_length < sizeof cowsay_output) {
        cowsay_output[cowsay_output_length++] = *text++;
    }
    return 0;
}

unsigned char udeks_write_byte(unsigned char fd, unsigned char value)
{
    (void)fd;
    if (cowsay_output_length < sizeof cowsay_output) {
        cowsay_output[cowsay_output_length++] = value;
    }
    return 0;
}

void test_reset(void)
{
    cowsay_output_length = 0;
    memset(cowsay_output, 0, sizeof cowsay_output);
}