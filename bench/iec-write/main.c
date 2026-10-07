/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <stdint.h>
#include "udeks/cbm_write.h"
#include "udeks/cbm_file.h"
#include "udeks/task_request.h"

#define R ((volatile uint8_t *)0x6000)
#define MODE (*(volatile uint8_t *)0x60f0) /* 0=create+read, 1=reboot, 2=empty, 3=write-protect */
#define SPEED (*(volatile uint8_t *)0xd030)
#define CIA (*(volatile uint8_t *)0xdd00)
static const uint16_t lengths[] = {0, 1, 2, 23, 24, 253, 254, 255, 256, 508, 515, 1};
static uint8_t name[] = "WRTEST00";
static uint8_t buffer[24];
extern uint8_t udeks_cbm_dos_error;

int main(void)
{
    uint8_t file, n, i, error, same, saved_speed, saved_bank;
    uint16_t position, value, length;
    for (i = 0; i < 32u; ++i) R[i] = 0;
    R[0] = 1;
    /* Exercise restoration to 2 MHz and preservation of the VIC bank. */
    SPEED |= 1; saved_speed = SPEED; saved_bank = CIA & 3u;
    R[8] = saved_speed; R[9] = saved_bank;
    if (MODE == 3u) {
        R[2] = 10;
        error = udeks_cbm_create(8, (const uint8_t *)"NOCHANGE", 8);
        R[3] = error;
        if (error != UDEKS_CBM_EROFS) goto failed;
        R[10] = SPEED; R[11] = CIA & 3u;
        if (SPEED != saved_speed || (CIA & 3u) != saved_bank || (CIA & 0x38u)) goto failed;
        R[0] = 2;
        return 0;
    }
    if (MODE == 2u) {
        R[2] = 9; /* maximum-length physical filename, host checks exact size */
        error = udeks_cbm_create(8, (const uint8_t *)"EMPTY-1234567890", 16);
        if (error) goto failed;
        error = udeks_cbm_write_close();
        if (error) goto failed;
        R[0] = 2;
        return 0;
    }
    for (file = 0; file < 12u; ++file) {
        R[1] = file; R[2] = 1;
        name[6] = '0'+file/10u; name[7] = '0'+file%10u; length = lengths[file];
        if (!MODE) {
            error = udeks_cbm_create(8, name, 8);
            if (error) goto failed;
            R[2] = 2;
            error = udeks_cbm_write(buffer, 0);
            if (error) goto failed;
            position = 0;
            while (position < length) {
                n = length-position > 24u ? 24u : length-position;
                for (i = 0; i < n; ++i) buffer[i] = file == 11u ? 13u : (uint8_t)(position+i);
                error = udeks_cbm_write(buffer, n);
                if (error || udeks_cbm_written != n) goto failed;
                position += n;
            }
            R[2] = 3;
            error = udeks_cbm_write_close();
            if (error) goto failed;
            R[2] = 4;
            /* An existing exact name must survive a second create attempt. */
            error = udeks_cbm_create(8, name, 8);
            if (error != UDEKS_TREQ_EEXIST) goto failed;
        }
        R[2] = 5;
        error = udeks_cbm_begin(8);
        if (error) goto failed;
        do {
            error = udeks_cbm_next();
            if (error != 1u) goto failed;
            same = udeks_cbm_entry[11] == 0xa0u;
            for (i = 0; i < 8u; ++i) if (udeks_cbm_entry[3u+i] != name[i]) same = 0;
        } while (!same);
        if (udeks_cbm_entry[0] != 0x81u) goto failed;
        error = udeks_cbm_select();
        if (error) goto failed;
        R[2] = 6;
        for (position = 0; position < length; ++position) {
            value = udeks_cbm_read();
            if (value != (file == 11u ? 13u : (uint8_t)position)) {
                R[4] = position; R[5] = position >> 8;
                R[6] = value; R[7] = value >> 8;
                goto failed;
            }
        }
        R[2] = 7;
        if (udeks_cbm_read() != 256u) goto failed;
        error = udeks_cbm_close();
        if (error) goto failed;
        R[2] = 8;
        R[10] = SPEED; R[11] = CIA & 3u;
        if (SPEED != saved_speed || (CIA & 3u) != saved_bank || (CIA & 0x38u)) goto failed;
        ++R[12];
    }
    R[0] = 2;
    return 0;
failed:
    R[3] = error; R[13] = udeks_cbm_write_dos_error;
    R[14] = udeks_cbm_dos_error;
    udeks_cbm_write_close(); udeks_cbm_close();
    R[0] = 0x80;
    return 1;
}
