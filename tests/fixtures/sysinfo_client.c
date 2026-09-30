/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <string.h>
unsigned char sysinfo_payload[24], sysinfo_error, sysinfo_tasks[16], sysinfo_capability[32];
unsigned char test_output[1024], test_error[128], test_result[8], test_calls;
unsigned int test_output_length, test_error_length;
void test_reset(void)
{
    test_output_length = test_error_length = test_calls = sysinfo_error = 0;
    memcpy(sysinfo_tasks, "UTSK\0\1\1", 7); sysinfo_tasks[9] = 1;
    sysinfo_capability[10] = 64;
}
unsigned char file_request(unsigned char op, unsigned char fd, unsigned char count)
{
    ++test_calls;
    if (op != 19 || fd || count != 4 || memcmp(sysinfo_payload, "/mnt", 4))
        sysinfo_error = 22;
    if (sysinfo_error) return 255;
    memcpy(sysinfo_payload, test_result, 8);
    return 8;
}
unsigned char udeks_write_byte(unsigned char fd, unsigned char value)
{
    if (fd == 1) test_output[test_output_length++] = value;
    else test_error[test_error_length++] = value;
    return 0;
}
unsigned char udeks_write(unsigned char fd, const unsigned char *s)
{
    while (*s) udeks_write_byte(fd, *s++);
    return 0;
}
