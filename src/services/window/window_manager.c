/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "udeks/pointer.h"
#include "udeks/vic_graphics.h"
#include "udeks/window.h"

#define STATUS_BYTE(offset) \
    (*(volatile unsigned char *)(UDEKS_WINDOW_STATUS_BASE + (offset)))

#define POINTER_X_BIAS       12u
#define POINTER_Y_BIAS       40u
#define ACTION_BUTTONS       0x05u
#define DRAG_MOVE            1u
#define DRAG_RESIZE          2u
#define MINIMUM_WIDTH        48u
#define MINIMUM_HEIGHT       48u

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

static void publish_state(void)
{
    struct udeks_window *window;

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
    unsigned int x, unsigned char y, const struct udeks_window *window)
{
    return x >= window->x && x < window->x + window->width &&
        y >= window->y && y < (unsigned char)(window->y + window->height);
}

static void damage_set(const struct udeks_window *window)
{
    damage_left = window->x;
    damage_top = window->y;
    damage_right = window->x + window->width;
    damage_bottom = (unsigned char)(window->y + window->height);
}

static void damage_add(const struct udeks_window *window)
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
    right = x + width < damage_right ? x + width : damage_right;
    bottom = (unsigned char)(y + height) < damage_bottom ?
        (unsigned char)(y + height) : damage_bottom;
    if (left >= right || top >= bottom) {
        return 0;
    }
    udeks_vic_bitmap_set_clip(left, top, right - left, bottom - top);
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

static void draw_title(const struct udeks_window *window)
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

static void draw_chrome(const struct udeks_window *window)
{
    int close_x;
    int right;
    int bottom;

    udeks_vic_bitmap_rectangle(
        window->x, window->y, window->width, window->height,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_rectangle(
        window->x + 2, window->y + 2,
        window->width - 4, window->height - 4,
        UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        window->x + 2, window->y + UDEKS_WINDOW_TITLE_HEIGHT,
        window->x + window->width - 3,
        window->y + UDEKS_WINDOW_TITLE_HEIGHT,
        UDEKS_VIC_COLOR_BLACK);
    draw_title(window);
    if ((window->flags & UDEKS_WINDOW_FLAG_CLOSABLE) != 0) {
        close_x = (int)(window->x + window->width) - 12;
        udeks_vic_bitmap_rectangle(
            close_x, window->y + 3, 8, 8, UDEKS_VIC_COLOR_BLACK);
        udeks_vic_bitmap_line(
            close_x + 2, window->y + 5,
            close_x + 5, window->y + 8, UDEKS_VIC_COLOR_BLACK);
        udeks_vic_bitmap_line(
            close_x + 5, window->y + 5,
            close_x + 2, window->y + 8, UDEKS_VIC_COLOR_BLACK);
    }
    if ((window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) == 0) {
        return;
    }
    right = window->x + window->width - 5;
    bottom = window->y + window->height - 5;
    udeks_vic_bitmap_line(
        right - 6, bottom, right, bottom - 6, UDEKS_VIC_COLOR_BLACK);
    udeks_vic_bitmap_line(
        right - 3, bottom, right, bottom - 3, UDEKS_VIC_COLOR_BLACK);
}

static unsigned char paint_window_damage(unsigned char handle);

unsigned char udeks_window_begin_paint(unsigned char handle)
{
    struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0 || dragging_handle != UDEKS_WINDOW_NONE ||
        window->z != active_count) {
        return UDEKS_WINDOW_INVALID;
    }
    udeks_vic_bitmap_set_clip(
        window->x + 3, window->y + UDEKS_WINDOW_TITLE_HEIGHT + 1,
        window->width - 6,
        window->height - UDEKS_WINDOW_TITLE_HEIGHT - 4);
    return UDEKS_WINDOW_OK;
}

void udeks_window_end_paint(void)
{
    udeks_vic_bitmap_reset_clip();
}

static unsigned char paint_window_damage(unsigned char handle)
{
    struct udeks_window *window;

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
    for (rank = 1u; rank <= active_count; ++rank) {
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
    struct udeks_window *window;

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
    unsigned int x, unsigned char y, const struct udeks_window *window)
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
    unsigned int x, unsigned char y, const struct udeks_window *window)
{
    return (window->flags & UDEKS_WINDOW_FLAG_MOVABLE) != 0 &&
        x >= window->x && x < window->x + window->width &&
        y >= window->y && y < window->y + UDEKS_WINDOW_TITLE_HEIGHT;
}

static unsigned char resize_hit(
    unsigned int x, unsigned char y, const struct udeks_window *window)
{
    return (window->flags & UDEKS_WINDOW_FLAG_RESIZABLE) != 0 &&
        x >= window->x + window->width - 10u &&
        y >= window->y + window->height - 10u;
}

static void begin_drag(
    unsigned char handle, unsigned int pointer_x, unsigned char pointer_y,
    unsigned char mode)
{
    struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0) {
        return;
    }
    dragging_handle = handle;
    drag_mode = mode;
    drag_pointer_x = pointer_x - window->x;
    drag_pointer_y = (unsigned char)(pointer_y - window->y);
    drag_x = window->x;
    drag_y = window->y;
    drag_width = window->width;
    drag_height = window->height;
    damage_set(window);
    compose_damage(handle);
    udeks_vic_bitmap_outline_toggle(
        drag_x, drag_y, window->width, window->height);
    increment_counter(24u);
}

static void move_drag(unsigned int pointer_x, unsigned char pointer_y)
{
    struct udeks_window *window;
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
    struct udeks_window *window;
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
    drag_mode = 0;
    compose_damage(UDEKS_WINDOW_NONE);
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
    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        windows[index].active = 0;
    }
    active_count = 0;
    focused_handle = UDEKS_WINDOW_NONE;
    dragging_handle = UDEKS_WINDOW_NONE;
    drag_mode = 0;
    previous_buttons = 0;
    publish_state();
    return UDEKS_WINDOW_OK;
}

void udeks_window_manager_reset(void)
{
    unsigned char index;

    for (index = 0; index < UDEKS_WINDOW_MAX; ++index) {
        windows[index].active = 0;
    }
    active_count = 0;
    focused_handle = UDEKS_WINDOW_NONE;
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
    struct udeks_window *window;

    if (width < 16u || height <= UDEKS_WINDOW_TITLE_HEIGHT + 4u ||
        x + width > UDEKS_VIC_WIDTH ||
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
    window->flags = (unsigned char)(flags | UDEKS_WINDOW_FLAG_VISIBLE |
        UDEKS_WINDOW_FLAG_RESIZABLE);
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
    struct udeks_window *window;
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
    struct udeks_window *window;

    window = window_by_handle(handle);
    if (window == 0) {
        return UDEKS_WINDOW_INVALID;
    }
    if (dragging_handle != UDEKS_WINDOW_NONE) {
        return UDEKS_WINDOW_OK;
    }
    damage_set(window);
    compose_damage(UDEKS_WINDOW_NONE);
    return UDEKS_WINDOW_OK;
}

unsigned char udeks_window_get_geometry(
    unsigned char handle, unsigned int *x, unsigned char *y,
    unsigned int *width, unsigned char *height)
{
    struct udeks_window *window;

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
    struct udeks_window *window;

    if (udeks_vic_graphics_is_active() == 0) {
        return UDEKS_WINDOW_OK;
    }
    pointer_x = udeks_pointer_x() - POINTER_X_BIAS;
    pointer_y = (unsigned char)(udeks_pointer_y() - POINTER_Y_BIAS);
    buttons = udeks_pointer_buttons();
    pressed = (unsigned char)(buttons & ACTION_BUTTONS);
    if (pressed != 0 && previous_buttons == 0) {
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
            } else if (raised != 0) {
                damage_set(window);
                compose_damage(UDEKS_WINDOW_NONE);
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
