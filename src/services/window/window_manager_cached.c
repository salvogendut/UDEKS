/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/pointer.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"
#include "udeks/window_service.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))

#define POINTER_X_BIAS       12u
#define POINTER_Y_BIAS       40u
#define ACTION_BUTTONS       0x05u
#define DRAG_MOVE            1u
#define DRAG_RESIZE          2u
#define MINIMUM_WIDTH        48u
#define MINIMUM_HEIGHT       48u
#define IMAGE_COMPLETE       0x80u /* private; never accepted from create flags */

struct udeks_window {
    unsigned char active;
    unsigned char owner;
    unsigned char surface;
    unsigned char flags;
    unsigned int x;
    unsigned char y;
    unsigned int width;
    unsigned char height;
    unsigned char z;
    const unsigned char *title;
    udeks_window_paint_fn paint;
    udeks_window_close_fn close;
};

#pragma bss-name(push, "HIGHBSS")
static struct udeks_window windows[UDEKS_WINDOW_MAX];
static unsigned char active_count;
static unsigned char focused_handle;
static unsigned char dragging_handle;
static unsigned char previous_buttons;
static unsigned int drag_pointer_x;
static unsigned char drag_pointer_y;
static unsigned int drag_x;
static unsigned char drag_y;
static unsigned int drag_width;
static unsigned char drag_height;
static unsigned char drag_mode;
static unsigned int damage_left;
static unsigned char damage_top;
static unsigned int damage_right;
static unsigned char damage_bottom;
#pragma bss-name(pop)

static unsigned char click_handle;
static struct udeks_window_click pending_click;

const struct udeks_window_click * __fastcall__ udeks_window_take_click(unsigned char handle)
{
    if (!handle || handle != click_handle || handle != focused_handle || dragging_handle)
        return 0;
    click_handle = 0;
    return &pending_click;
}

static const unsigned char title_glyphs[26][5] = {
    {2, 5, 7, 5, 5}, {6, 5, 6, 5, 6}, {3, 4, 4, 4, 3},
    {6, 5, 5, 5, 6}, {7, 4, 6, 4, 7}, {7, 4, 6, 4, 4},
    {3, 4, 5, 5, 3}, {5, 5, 7, 5, 5}, {7, 2, 2, 2, 7},
    {1, 1, 1, 5, 2}, {5, 5, 6, 5, 5}, {4, 4, 4, 4, 7},
    {5, 7, 7, 5, 5}, {5, 7, 7, 7, 5}, {2, 5, 5, 5, 2},
    {6, 5, 6, 4, 4}, {2, 5, 5, 3, 1}, {6, 5, 6, 5, 5},
    {3, 4, 2, 1, 6}, {7, 2, 2, 2, 2}, {5, 5, 5, 5, 7},
    {5, 5, 5, 5, 2}, {5, 5, 7, 7, 5}, {5, 5, 2, 5, 5},
    {5, 5, 2, 2, 2}, {7, 1, 2, 4, 7}
};

static void increment_counter(unsigned char low_offset)
{
    ++STATUS_BYTE(low_offset);
    if (STATUS_BYTE(low_offset) == 0) {
        ++STATUS_BYTE(low_offset + 1u);
    }
}

static struct udeks_window *window_by_handle(unsigned char handle)
{
    if (handle == UDEKS_WINDOW_NONE || handle > UDEKS_WINDOW_MAX ||
        windows[handle - 1u].active == 0) {
        return 0;
    }
    return &windows[handle - 1u];
}

unsigned char __fastcall__ udeks_window_owner(unsigned char handle)
{
    struct udeks_window *window = window_by_handle(handle);
    return window == 0 ? UDEKS_WINDOW_NONE : window->owner;
}

static void publish_state(void)
{
    register struct udeks_window *window;

    STATUS_BYTE(6) = active_count;
    STATUS_BYTE(7) = focused_handle;
    STATUS_BYTE(8) = dragging_handle;
    STATUS_BYTE(14) = UDEKS_WINDOW_MAX;
    STATUS_BYTE(15) = 0x3Fu;
    if (dragging_handle == UDEKS_WINDOW_NONE) {
        STATUS_BYTE(9) = 0;
        STATUS_BYTE(10) = 0;
        STATUS_BYTE(11) = 0;
        STATUS_BYTE(12) = 0;
        STATUS_BYTE(13) = previous_buttons;
        return;
    }
    window = window_by_handle(dragging_handle);
    if (window == 0) {
        return;
    }
    STATUS_BYTE(9) = (unsigned char)drag_x;
    STATUS_BYTE(10) = (unsigned char)(drag_x >> 8);
    STATUS_BYTE(11) = drag_y;
    STATUS_BYTE(12) = (unsigned char)drag_width;
    STATUS_BYTE(13) = previous_buttons;
}

static unsigned char point_inside(
    unsigned int x, unsigned char y, register const struct udeks_window *window)
{
    return x >= window->x && x < window->x + window->width &&
        y >= window->y && y < (unsigned char)(window->y + window->height);
}

static void damage_set(register const struct udeks_window *window)
{
    damage_left = window->x;
    damage_top = window->y;
    damage_right = window->x + window->width;
    damage_bottom = (unsigned char)(window->y + window->height);
}

static void damage_add(register const struct udeks_window *window)
{
    unsigned int right;
    unsigned char bottom;

    right = window->x + window->width;
    bottom = (unsigned char)(window->y + window->height);
    if (window->x < damage_left) {
        damage_left = window->x;
    }
    if (window->y < damage_top) {
        damage_top = window->y;
    }
    if (right > damage_right) {
        damage_right = right;
    }
    if (bottom > damage_bottom) {
        damage_bottom = bottom;
    }
}

#ifdef UDEKS_CACHE_MANAGER_HOST_TEST
extern unsigned char manager_partial_first, manager_partial_end;
extern unsigned int manager_partial_width;
#define CACHE_PARTIAL_FIRST manager_partial_first
#define CACHE_PARTIAL_END manager_partial_end
#define CACHE_PARTIAL_WIDTH manager_partial_width
#else
#define CACHE_PARTIAL_FIRST (*(volatile unsigned char *)0xF78Au)
#define CACHE_PARTIAL_END (*(volatile unsigned char *)0xF78Bu)
#define CACHE_PARTIAL_WIDTH (*(volatile unsigned int *)0xF78Cu)
#endif
static unsigned char set_damage_intersection(
    unsigned int x, unsigned char y,
    unsigned int width, unsigned char height)
{
    unsigned int left;
    unsigned char top;
    unsigned int right;
    unsigned char bottom;

    left = x > damage_left ? x : damage_left;
    top = y > damage_top ? y : damage_top;
    right = x + width;
    if (right > damage_right) right = damage_right;
    bottom = (unsigned char)(y + height);
    if (bottom > damage_bottom) bottom = damage_bottom;
    if (left >= right || top >= bottom) {
        return 0;
    }
    udeks_vic_bitmap_set_clip(left, top, right - left, bottom - top);
    CACHE_PARTIAL_FIRST = top - y;
    CACHE_PARTIAL_END = bottom - y;
    CACHE_PARTIAL_WIDTH = right - x;
    return 1;
}

static void draw_glyph(
    int x, int y, const unsigned char *glyph)
{
    unsigned char row;
    unsigned char column;

    for (row = 0; row < 5u; ++row) {
        for (column = 0; column < 3u; ++column) {
            if ((glyph[row] & (unsigned char)(4u >> column)) != 0) {
                udeks_vic_bitmap_pixel(
                    x + column, y + row, UDEKS_VIC_COLOR_BLACK);
            }
        }
    }
}

static void draw_title(register const struct udeks_window *window)
{
    const unsigned char *text;
    unsigned char character;
    int x;
    int limit;

    text = window->title;
    x = (int)window->x + 4;
    limit = (int)(window->x + window->width) - 14;
    while (text != 0 && *text != 0 && x + 3 <= limit) {
        character = *text++;
        if (character >= 'a' && character <= 'z') {
            character = (unsigned char)(character - ('a' - 'A'));
        }
        if (character >= 'A' && character <= 'Z') {
            draw_glyph(x, window->y + 4,
                title_glyphs[character - 'A']);
        }
        x += 4;
    }
}

static void draw_chrome(register const struct udeks_window *window)
{
    int close_x;
    int right;
    int bottom;
    int x = window->x;
    int y = window->y;
    int width = window->width;
    int height = window->height;

    udeks_vic_bitmap_rectangle(
        x, y, width, height,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_rectangle(
        x + 2, y + 2,
        width - 4, height - 4,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        x + 2, y + UDEKS_WINDOW_TITLE_HEIGHT,
        x + width - 3,
        y + UDEKS_WINDOW_TITLE_HEIGHT,
        UDEKS_VIC_COLOR_BLACK);
    draw_title(window);
    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) != 0) {
        close_x = (int)(x + width) - 12;
        udeks_vic_bitmap_rectangle(
            close_x, y + 3, 8, 8, UDEKS_VIC_COLOR_BLACK);
        udeks_vic_bitmap_line(
            close_x + 2, y + 5,
            close_x + 5, y + 8, UDEKS_VIC_COLOR_BLACK);
        udeks_vic_bitmap_line(
            close_x + 5, y + 5,
            close_x + 2, y + 8, UDEKS_VIC_COLOR_BLACK);
    }
    if ((window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) == 0) {
        return;
    }
    right = x + width - 5;
    bottom = y + height - 5;
    udeks_vic_bitmap_line(
        right - 6, bottom, right, bottom - 6, UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        right - 3, bottom, right, bottom - 3, UDEKS_VIC_COLOR_BLACK);
}

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
#ifdef UDEKS_CACHE_MANAGER_HOST_TEST
extern unsigned char manager_test_row_offset;
#define CACHE_ROW_OFFSET manager_test_row_offset
#else
/* Last successful STEP's bitmap offset: low three bits are its scanline.
 * No intervening gateway/user call before this read; IRQ/NMI don't use it. */
#define CACHE_ROW_OFFSET (*(volatile unsigned char *)0xF780u)
#endif

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

static unsigned char paint_window_damage(unsigned char handle);

unsigned char udeks_window_begin_paint(unsigned char handle)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0 || dragging_handle != UDEKS_WINDOW_NONE ||
        window->z != active_count) {
        return UDEKS_WINDOW_INVALID;
    }
    if (cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING)
        return UDEKS_WINDOW_INVALID;
    cache_invalidate();
    window->flags &= (unsigned char)~IMAGE_COMPLETE;
    udeks_vic_bitmap_set_clip(
        window->x + 3, window->y + UDEKS_WINDOW_TITLE_HEIGHT + 1,
        window->width - 6,
        window->height - UDEKS_WINDOW_TITLE_HEIGHT - 4);
    return UDEKS_WINDOW_OK;
}

void udeks_window_end_paint(void)
{
    udeks_vic_bitmap_reset_clip();
    udeks_vic_bitmap_commit();
}

unsigned char __fastcall__ udeks_window_image_complete(unsigned char handle)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0 || dragging_handle != UDEKS_WINDOW_NONE ||
        window->z != active_count ||
        (window->flags & UDEKS_WINDOW_FLAG_VISIBLE) == 0 ||
        window->surface != UDEKS_WINDOW_SURFACE_BITMAP) {
        return UDEKS_WINDOW_INVALID;
    }
    window->flags |= IMAGE_COMPLETE;
    if (cache_accept_state == 0x80u && cache_phase == UDEKS_CACHE_EMPTY)
        cache_request(handle, UDEKS_CACHE_COMMAND_CAPTURE);
    return UDEKS_WINDOW_OK;
}

static unsigned char paint_window_damage(unsigned char handle)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0 ||
        (window->flags & UDEKS_WINDOW_FLAG_VISIBLE) == 0) {
        return 0;
    }
    if (set_damage_intersection(
            window->x, window->y,
            window->width, window->height) == 0) {
        return 0;
    }
    window->flags &= (unsigned char)~IMAGE_COMPLETE;
    udeks_vic_bitmap_fill(
        window->x, window->y, window->width, window->height,
        UDEKS_VIC_COLOR_YELLOW);
    draw_chrome(window);
    if (window->paint != 0 &&
        set_damage_intersection(
            window->x + 3,
            (unsigned char)(window->y + UDEKS_WINDOW_TITLE_HEIGHT + 1u),
            window->width - 6u,
            (unsigned char)(window->height -
                UDEKS_WINDOW_TITLE_HEIGHT - 4u)) != 0) {
        window->paint(handle);
    }
    increment_counter(20u);
    return 1;
}

static void compose_damage(unsigned char skip_handle)
{
    unsigned char rank;
    unsigned char index;

    /* A retained move skips its owner and repairs only background.
     * Other composition cancels before pixels change. A partially pasted
     * destination expands damage so fallback repairs its whole window. */
    if ((drag_mode & CACHED_MOVE) == 0 || (skip_handle != cache_owner && skip_handle != 255u)) {
        if (cache_phase == UDEKS_CACHE_PASTING) {
            struct udeks_window *cached = window_by_handle(cache_owner);
            if (cached != 0) damage_add(cached);
        }
        cache_invalidate();
    }
    udeks_vic_pointer_busy_begin(UDEKS_VIC_BUSY_REPAINT);
    udeks_vic_bitmap_set_clip(
        damage_left, damage_top,
        damage_right - damage_left,
        (unsigned char)(damage_bottom - damage_top));
    udeks_vic_bitmap_fill(
        damage_left, damage_top,
        damage_right - damage_left,
        (unsigned char)(damage_bottom - damage_top),
        UDEKS_VIC_COLOR_YELLOW);
    /* Private erase-only mode: no client callbacks until release. */
    for (rank = 1u; skip_handle != 255u && rank <= active_count; ++rank) {
        for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
            if (windows[index].active != 0 && windows[index].z == rank) {
                if ((unsigned char)(index + 1u) != skip_handle) {
                    paint_window_damage((unsigned char)(index + 1u));
                }
                break;
            }
        }
    }
    udeks_vic_bitmap_reset_clip();
    udeks_vic_bitmap_commit();
    udeks_vic_pointer_busy_end(UDEKS_VIC_BUSY_REPAINT);
    increment_counter(30u);
}

static void cache_paint_image(unsigned char handle)
{
    register struct udeks_window *cached = window_by_handle(handle);
    unsigned char paste;
    /* READY describes retained pixels, not a finished screen repair. Mark
     * frontend composition busy before erasing; banked flow stays READY. */
    cache_phase |= 0x80u;
    drag_mode |= CACHED_MOVE;
    compose_damage(handle);
    drag_mode = 0;
    /* Composition owns the shared VIC workspace. Prepare the prefix only
     * after callbacks/commits finish, immediately before the banked request. */
    paste = set_damage_intersection(cached->x, cached->y, cached->width, cached->height);
    udeks_vic_bitmap_reset_clip();
    if (paste == 0) cache_phase = UDEKS_CACHE_READY;
    else if (cache_request(handle, 6) != UDEKS_CACHE_OK)
        compose_damage(UDEKS_WINDOW_NONE);
}

static unsigned char top_window(void)
{
    unsigned char index;

    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        if (windows[index].active != 0 &&
            windows[index].z == active_count) {
            return (unsigned char)(index + 1u);
        }
    }
    return UDEKS_WINDOW_NONE;
}

static unsigned char raise_window(unsigned char handle)
{
    unsigned char index;
    unsigned char old_z;
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0 || window->z == active_count) {
        return 0;
    }
    old_z = window->z;
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        if (windows[index].active != 0 && windows[index].z > old_z) {
            --windows[index].z;
        }
    }
    window->z = active_count;
    return 1;
}

static unsigned char top_window_at(unsigned int x, unsigned char y)
{
    unsigned char index;
    unsigned char handle;
    unsigned char highest_z;

    handle = UDEKS_WINDOW_NONE;
    highest_z = 0;
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        if (windows[index].active != 0 &&
            (windows[index].flags & UDEKS_WINDOW_FLAG_VISIBLE) != 0 &&
            point_inside(x, y, &windows[index]) != 0 &&
            (handle == UDEKS_WINDOW_NONE || windows[index].z >= highest_z)) {
            handle = (unsigned char)(index + 1u);
            highest_z = windows[index].z;
        }
    }
    return handle;
}

static unsigned char close_hit(
    unsigned int x, unsigned char y, register const struct udeks_window *window)
{
    unsigned int left;

    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) == 0) {
        return 0;
    }
    left = window->x + window->width - 12u;
    return x >= left && x < left + 8u &&
        y >= window->y + 3u && y < window->y + 11u;
}

static unsigned char title_hit(
    unsigned int x, unsigned char y, register const struct udeks_window *window)
{
    return (window->flags & UDEKS_WINDOW_FLAG_MOVABLE) != 0 &&
        x >= window->x && x < window->x + window->width &&
        y >= window->y && y < window->y + UDEKS_WINDOW_TITLE_HEIGHT;
}

static unsigned char resize_hit(
    unsigned int x, unsigned char y, register const struct udeks_window *window)
{
    return (window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) != 0 &&
        x >= window->x + window->width - 10u &&
        y >= window->y + window->height - 10u;
}

static void begin_drag(
    unsigned char handle, unsigned int pointer_x, unsigned char pointer_y,
    unsigned char mode)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0) {
        return;
    }
    dragging_handle = handle;
    drag_mode = mode;
    if (mode == DRAG_MOVE && cache_phase == UDEKS_CACHE_READY && cache_owner == handle)
        drag_mode |= CACHED_MOVE;
    else cache_invalidate();
    drag_pointer_x = pointer_x - window->x;
    drag_pointer_y = (unsigned char)(pointer_y - window->y);
    drag_x = window->x;
    drag_y = window->y;
    drag_width = window->width;
    drag_height = window->height;
    damage_set(window);
    /* Erase content without invoking lower applications on the button path.
     * The old/new union is fully recomposed by finish_drag on release. */
    compose_damage(255u);
    udeks_vic_bitmap_outline_toggle(
        drag_x, drag_y, window->width, window->height);
    increment_counter(24u);
}

static void move_drag(unsigned int pointer_x, unsigned char pointer_y)
{
    register struct udeks_window *window;
    unsigned int new_x;
    unsigned char new_y;

    window = window_by_handle(dragging_handle);
    if (window == 0) {
        dragging_handle = UDEKS_WINDOW_NONE;
        return;
    }
    new_x = pointer_x > drag_pointer_x ?
        pointer_x - drag_pointer_x : 0u;
    new_y = pointer_y > drag_pointer_y ?
        (unsigned char)(pointer_y - drag_pointer_y) : 0u;
    if (new_x > UDEKS_VIC_WIDTH - window->width) {
        new_x = UDEKS_VIC_WIDTH - window->width;
    }
    if (new_y > UDEKS_VIC_HEIGHT - window->height) {
        new_y = UDEKS_VIC_HEIGHT - window->height;
    }
    if (new_x == drag_x && new_y == drag_y) {
        return;
    }
    udeks_vic_bitmap_reset_clip();
    udeks_vic_bitmap_outline_move(
        drag_x, drag_y, new_x, new_y,
        window->width, window->height);
    drag_x = new_x;
    drag_y = new_y;
    increment_counter(22u);
}

static void resize_drag(unsigned int pointer_x, unsigned char pointer_y)
{
    unsigned int new_width;
    unsigned char new_height;

    new_width = pointer_x > drag_x ? pointer_x - drag_x + 1u : MINIMUM_WIDTH;
    new_height = pointer_y > drag_y ?
        (unsigned char)(pointer_y - drag_y + 1u) : MINIMUM_HEIGHT;
    if (new_width < MINIMUM_WIDTH) {
        new_width = MINIMUM_WIDTH;
    }
    if (new_height < MINIMUM_HEIGHT) {
        new_height = MINIMUM_HEIGHT;
    }
    if (new_width > UDEKS_VIC_WIDTH - drag_x) {
        new_width = UDEKS_VIC_WIDTH - drag_x;
    }
    if (new_height > UDEKS_VIC_HEIGHT - drag_y) {
        new_height = (unsigned char)(UDEKS_VIC_HEIGHT - drag_y);
    }
    if (new_width == drag_width && new_height == drag_height) {
        return;
    }
    udeks_vic_bitmap_reset_clip();
    udeks_vic_bitmap_outline_toggle(
        drag_x, drag_y, drag_width, drag_height);
    udeks_vic_bitmap_outline_toggle(
        drag_x, drag_y, new_width, new_height);
    drag_width = new_width;
    drag_height = new_height;
    increment_counter(22u);
}

static void finish_drag(void)
{
    register struct udeks_window *window;
    unsigned char handle;

    handle = dragging_handle;
    window = window_by_handle(handle);
    if (window == 0) {
        dragging_handle = UDEKS_WINDOW_NONE;
        return;
    }
    udeks_vic_bitmap_reset_clip();
    udeks_vic_bitmap_outline_toggle(
        drag_x, drag_y, drag_width, drag_height);
    damage_set(window);
    window->x = drag_x;
    window->y = drag_y;
    window->width = drag_width;
    window->height = drag_height;
    damage_add(window);
    dragging_handle = UDEKS_WINDOW_NONE;
    if ((drag_mode & CACHED_MOVE) != 0) {
        cache_paint_image(handle);
    } else {
        drag_mode = 0;
        compose_damage(UDEKS_WINDOW_NONE);
    }
    udeks_pointer_resynchronize();
    increment_counter(26u);
}

unsigned char udeks_window_manager_start(void)
{
    unsigned char index;

    for (index = 0; index < UDEKS_WINDOW_STATUS_SIZE; ++index) {
        STATUS_BYTE(index) = 0;
    }
    STATUS_BYTE(0) = 'W';
    STATUS_BYTE(1) = 'M';
    STATUS_BYTE(2) = 'G';
    STATUS_BYTE(3) = 'R';
    STATUS_BYTE(4) = 1;
    STATUS_BYTE(5) = UDEKS_WINDOW_READY;
    udeks_window_manager_reset();
    return UDEKS_WINDOW_OK;
}

void udeks_window_manager_reset(void)
{
    unsigned char index;

    cache_invalidate();

    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        windows[index].active = 0;
    }
    active_count = 0;
    focused_handle = UDEKS_WINDOW_NONE;
    click_handle = 0;
    dragging_handle = UDEKS_WINDOW_NONE;
    drag_mode = 0;
    previous_buttons = 0;
    publish_state();
}

unsigned char udeks_window_manager_stop(void)
{
    udeks_window_manager_reset();
    return UDEKS_WINDOW_OK;
}

unsigned char udeks_window_create(
    unsigned char owner, unsigned char surface, unsigned char flags,
    unsigned int x, unsigned char y, unsigned int width,
    unsigned char height, const unsigned char *title,
    udeks_window_paint_fn paint, udeks_window_close_fn close)
{
    unsigned char index;
    register struct udeks_window *window;

    if (width < 16u || width > UDEKS_VIC_WIDTH ||
        height <= UDEKS_WINDOW_TITLE_HEIGHT + 4u ||
        x > UDEKS_VIC_WIDTH - width ||
        (unsigned int)y + height > UDEKS_VIC_HEIGHT ||
        surface != UDEKS_WINDOW_SURFACE_BITMAP) {
        return UDEKS_WINDOW_NONE;
    }
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        if (windows[index].active == 0) {
            break;
        }
    }
    if (index == UDEKS_WINDOW_MAX) {
        return UDEKS_WINDOW_NONE;
    }
    window = &windows[index];
    window->active = 1;
    window->owner = owner;
    window->surface = surface;
    window->flags = (unsigned char)((flags & 0x0Fu) | UDEKS_WINDOW_FLAG_VISIBLE |
        UDEKS_WINDOW_FLAG_RESIZABLE);
    if (flags & UDEKS_WINDOW_FLAG_FIXED_SIZE) window->flags &= ~UDEKS_WINDOW_FLAG_RESIZABLE;
    window->x = x;
    window->y = y;
    window->width = width;
    window->height = height;
    window->z = (unsigned char)(active_count + 1u);
    window->title = title;
    window->paint = paint;
    window->close = close;
    ++active_count;
    focused_handle = (unsigned char)(index + 1u);
    increment_counter(16u);
    publish_state();
    damage_set(window);
    compose_damage(UDEKS_WINDOW_NONE);
    return focused_handle;
}

unsigned char udeks_window_destroy(unsigned char handle)
{
    register struct udeks_window *window;
    udeks_window_close_fn close;
    unsigned char index;
    unsigned char old_z;

    window = window_by_handle(handle);
    if (window == 0) {
        return UDEKS_WINDOW_INVALID;
    }
    close = window->close;
    old_z = window->z;
    damage_set(window);
    if (dragging_handle == handle) {
        udeks_vic_bitmap_reset_clip();
        udeks_vic_bitmap_outline_toggle(
            drag_x, drag_y, drag_width, drag_height);
        dragging_handle = UDEKS_WINDOW_NONE;
        drag_mode = 0;
    }
    window->active = 0;
    --active_count;
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        if (windows[index].active != 0 && windows[index].z > old_z) {
            --windows[index].z;
        }
    }
    focused_handle = top_window();
    click_handle = 0;
    compose_damage(UDEKS_WINDOW_NONE);
    increment_counter(18u);
    publish_state();
    if (close != 0) {
        close(handle);
    }
    return UDEKS_WINDOW_OK;
}

unsigned char udeks_window_repaint(unsigned char handle)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0) {
        return UDEKS_WINDOW_INVALID;
    }
    if (dragging_handle != UDEKS_WINDOW_NONE ||
        cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING) {
        return UDEKS_WINDOW_OK;
    }
    damage_set(window);
    if (cache_phase == UDEKS_CACHE_READY && handle != cache_owner) {
        /* Updating a lower window does not change the top cached image.
         * Recompose its background and restore pixels, not app vertices. */
        window = window_by_handle(cache_owner);
        /* A top retained image can hide all of a lower damage rectangle,
         * or leave just its upper strip. Repair that strip without touching
         * the retained pixels. Complex intersections keep the paste path. */
        if (damage_left >= window->x &&
            damage_right <= window->x + window->width &&
            damage_bottom <= window->y + window->height) {
            cache_phase = 0x82u; /* Frontend repair busy; banked image READY. */
            if (damage_bottom > window->y) damage_bottom = window->y;
            if (damage_top < damage_bottom) {
                drag_mode = CACHED_MOVE;
                compose_damage(cache_owner);
                drag_mode = 0;
            }
            /* An entirely hidden client still acknowledges its update.
             * A zero clip makes its callback drawing harmless and prevents
             * repeated requests (e.g. every clock poll after a minute tick). */
            window = window_by_handle(handle);
            if (window->paint != 0 &&
                damage_bottom <= damage_top + UDEKS_WINDOW_TITLE_HEIGHT + 1u) {
                window->flags &= (unsigned char)~IMAGE_COMPLETE;
                udeks_vic_bitmap_set_clip(0, 0, 0, 0);
                window->paint(handle);
                udeks_vic_bitmap_reset_clip();
            }
            cache_phase = UDEKS_CACHE_READY;
        } else cache_paint_image(cache_owner);
    } else compose_damage(UDEKS_WINDOW_NONE);
    return UDEKS_WINDOW_OK;
}

unsigned char udeks_window_get_geometry(
    unsigned char handle, unsigned int *x, unsigned char *y,
    unsigned int *width, unsigned char *height)
{
    register struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0) {
        return UDEKS_WINDOW_INVALID;
    }
    *x = dragging_handle == handle ? drag_x : window->x;
    *y = dragging_handle == handle ? drag_y : window->y;
    *width = dragging_handle == handle ? drag_width : window->width;
    *height = dragging_handle == handle ? drag_height : window->height;
    return UDEKS_WINDOW_OK;
}

unsigned char udeks_window_is_dragging(unsigned char handle)
{
    return handle != UDEKS_WINDOW_NONE && dragging_handle == handle ? 1u : 0u;
}

unsigned char udeks_window_is_focused(unsigned char handle)
{
    return handle != UDEKS_WINDOW_NONE && focused_handle == handle ? 1u : 0u;
}

unsigned char udeks_window_manager_poll(void)
{
    unsigned int pointer_x;
    unsigned char pointer_y;
    unsigned char buttons;
    unsigned char pressed;
    unsigned char handle;
    unsigned char raised;
    register struct udeks_window *window;

    if (udeks_vic_graphics_is_active() == 0) {
        return UDEKS_WINDOW_OK;
    }
    if (cache_accept_state < 0x80u) cache_accept_poll();
    if (dragging_handle == UDEKS_WINDOW_NONE &&
        (cache_phase == UDEKS_CACHE_CAPTURING || cache_phase == UDEKS_CACHE_PASTING)) {
        unsigned char phase = cache_phase;
        unsigned char budget = 4;
        do {
            /* Each STEP releases its MMU/runtime/IRQ lease before the next.
             * Commit dirty pages once per bounded batch, not once per row. */
            if (cache_step() != UDEKS_CACHE_OK) {
                window = window_by_handle(cache_owner);
                if (window != 0) {
                    damage_set(window);
                    compose_damage(UDEKS_WINDOW_NONE);
                }
                break;
            }
        } while (--budget != 0 && cache_phase == phase &&
            (phase != UDEKS_CACHE_PASTING || (CACHE_ROW_OFFSET & 7u) != 7u));
        /* Keep the four-row input budget. Finish a physical eight-scanline
         * bitmap band before committing its pages; always flush final/error. */
        if (phase == UDEKS_CACHE_PASTING &&
            (cache_phase != UDEKS_CACHE_PASTING || (CACHE_ROW_OFFSET & 7u) == 7u))
            udeks_vic_bitmap_commit();
    }
    /* Finish a paste before processing a new click. Pointer motion and
     * console/task polling remain active; a release is not swallowed. */
    if (cache_phase == UDEKS_CACHE_PASTING) return UDEKS_WINDOW_OK;
    pointer_x = udeks_pointer_x() - POINTER_X_BIAS;
    pointer_y = (unsigned char)(udeks_pointer_y() - POINTER_Y_BIAS);
    buttons = udeks_pointer_buttons();
    pressed = (unsigned char)(buttons & ACTION_BUTTONS);
    if (pressed != 0 && previous_buttons == 0) {
        click_handle = 0;
        handle = top_window_at(pointer_x, pointer_y);
        window = window_by_handle(handle);
        if (window != 0) {
            focused_handle = handle;
            raised = raise_window(handle);
            if (close_hit(pointer_x, pointer_y, window) != 0) {
                increment_counter(28u);
                previous_buttons = pressed;
                udeks_window_destroy(handle);
                publish_state();
                return UDEKS_WINDOW_OK;
            }
            if (resize_hit(pointer_x, pointer_y, window) != 0) {
                begin_drag(
                    handle, pointer_x, pointer_y, DRAG_RESIZE);
            } else if (title_hit(pointer_x, pointer_y, window) != 0) {
                begin_drag(handle, pointer_x, pointer_y, DRAG_MOVE);
            } else {
                if (pointer_x > window->x && pointer_x < window->x + window->width - 1u &&
                    pointer_y >= window->y + UDEKS_WINDOW_TITLE_HEIGHT &&
                    pointer_y < window->y + window->height - 1u) {
                    pending_click.x = pointer_x - window->x;
                    pending_click.y = pointer_y - window->y;
                    click_handle = handle;
                }
                if (raised != 0) {
                    damage_set(window);
                    compose_damage(UDEKS_WINDOW_NONE);
                }
            }
        } else {
            focused_handle = UDEKS_WINDOW_NONE;
        }
    }
    if (pressed == 0 && dragging_handle != UDEKS_WINDOW_NONE) {
        finish_drag();
    } else if (pressed != 0 && dragging_handle != UDEKS_WINDOW_NONE) {
        if (drag_mode == DRAG_RESIZE) {
            resize_drag(pointer_x, pointer_y);
        } else {
            move_drag(pointer_x, pointer_y);
        }
    }
    previous_buttons = pressed;
    publish_state();
    return UDEKS_WINDOW_OK;
}
