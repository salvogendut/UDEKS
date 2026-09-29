/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Private C compositor adapter. Never entered by the normal build yet. */
#include "udeks/window_cache_state.h"
#include "udeks/window_cache_command.h"
extern volatile unsigned char cache_accept_state, cache_owner, cache_phase;
extern unsigned char cache_accept_poll(void);
extern unsigned char cache_step(void);
extern unsigned char __fastcall__ cache_command(unsigned char op);
#ifdef UDEKS_CACHE_MANAGER_HOST_TEST
extern struct udeks_cache_geometry manager_test_geometry;
extern unsigned char manager_test_owner, manager_test_eligible;
#define CACHE_GEOMETRY manager_test_geometry
#define CACHE_OWNER manager_test_owner
#define CACHE_ELIGIBLE manager_test_eligible
#else
#define CACHE_GEOMETRY (*(volatile struct udeks_cache_geometry *)0xF7A1u)
#define CACHE_OWNER (*(volatile unsigned char *)0xF792u)
#define CACHE_ELIGIBLE (*(volatile unsigned char *)0xF795u)
#endif
#define CACHED_MOVE 0x80u

static unsigned char cache_request(unsigned char handle, unsigned char op)
{
    register struct udeks_window *window = window_by_handle(handle);
    CACHE_OWNER = handle;
    CACHE_GEOMETRY.x = window->x;
    CACHE_GEOMETRY.width = window->width;
    CACHE_GEOMETRY.y = window->y;
    CACHE_GEOMETRY.height = window->height;
    CACHE_ELIGIBLE = 1;
    return cache_command(op);
}

static void cache_invalidate(void)
{
    cache_command(UDEKS_CACHE_COMMAND_INVALIDATE);
}
