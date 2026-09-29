/* SPDX-License-Identifier: GPL-3.0-or-later */
/*
 * Compiled APP1 child for the SPAWN qualification. Checking both C arguments
 * exercises the real cc65 software stack before a normal return becomes
 * EXIT(37) in the common launcher.
 */

unsigned char udeks_program_main(
    unsigned char count, unsigned char **arguments)
{
    if (count != 0u || arguments != (unsigned char **)0) {
        return 0xFEu;
    }
    return 37u;
}
