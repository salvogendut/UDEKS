/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private synchronous graphics/scene admission prototype; not UAPP ABI. */
#ifndef UDEKS_PRIVATE_REPAINT_ADMISSION_H
#define UDEKS_PRIVATE_REPAINT_ADMISSION_H
#define REPAINT_ADMISSION_FREE 0u
#define REPAINT_ADMISSION_EDIT 1u
#define REPAINT_ADMISSION_RASTER 2u
#define REPAINT_ADMISSION_CLIENT 3u
#define REPAINT_ADMISSION_CACHE 4u
#define REPAINT_ADMISSION_INVALID 2u
#define REPAINT_ADMISSION_DEFERRED 8u
struct udeks_repaint_rect;

/* Storage must be a dedicated, always-visible byte; cache readiness is not
 * admission. This prototype's only allowed lifetime is one synchronous
 * no-yield call frame: no saved token, task switch, app callback retaining
 * ownership, or release after reacquisition. The installed 8502 NMI stub
 * records only a flag and does not enter the manager. IRQ/other CPU callers
 * and exact placement still require an integration audit. */
extern unsigned char repaint_admission_owner;
unsigned char repaint_admission_try(unsigned char owner);
unsigned char repaint_admission_release(unsigned char owner);
/* begin keeps EDIT admission held on OK; caller edits synchronously and MUST
 * call end before returning/yielding. On every non-OK begin, ownership is
 * unchanged/free and no caller edit is authorized. This is only a reference
 * transaction envelope; geometry/provider placement remains unqualified. */
unsigned char repaint_edit_begin(const struct udeks_repaint_rect *old_bounds,
    const struct udeks_repaint_rect *new_bounds);
unsigned char repaint_edit_end(void);
#endif
