/* SPDX-License-Identifier: GPL-3.0-or-later */
/* UTRQ 0.18 exact-file operations; filesystem policy stays in the service. */
#ifndef UDEKS_FILE_MUTATION_H
#define UDEKS_FILE_MUTATION_H
#define UDEKS_FILE_MUTATION_MINOR 18u
#define UDEKS_FILE_RENAME 25u
#define UDEKS_FILE_COPY   26u
#define UDEKS_FILE_UNLINK 27u
#define UDEKS_FILE_EXDEV 18u

/* Transient console SDK. Exact paths, same mounted filesystem, no overwrite,
 * wildcards or recursion. Return 0 or UDEKS_IO_ERROR, setting udeks_errno.
 * They open/close their own source descriptor; never retry a failed mutation.
 * An error can follow partial on-disk work: no rollback guarantee. */
unsigned char udeks_rename(const unsigned char *source, const unsigned char *destination);
unsigned char udeks_copy(const unsigned char *source, const unsigned char *destination);
unsigned char udeks_unlink(const unsigned char *source);
#endif
