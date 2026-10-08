/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef XSPR_FILE_H
#define XSPR_FILE_H
#define XSPR_BANK_BYTES 504u
#define XSPR_FILE_PATH "/SPRITES.SPR"
#define XSPR_BASIC_PATH "/SPRITES.BSV"
#define XSPR_BASIC_BYTES 514u
#define XSPR_LOAD 0u
#define XSPR_SAVE 1u
#define XSPR_EXPORT 2u
/* save=1 creates exclusively; save=2 exports $0E00 plus eight padded slots;
 * save=0 reads an exact-size raw bank into a
 * disposable staging buffer. Caller commits only on success (including CLOSE). */
unsigned char xspr_file(unsigned char save, unsigned char *data);
#endif
