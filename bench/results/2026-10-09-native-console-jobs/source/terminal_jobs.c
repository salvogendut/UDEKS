/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <assert.h>
#include <string.h>
#include "udeks/root_console.h"
#include "udeks/root_terminal.h"
#include "udeks/line_editor.h"
#include "udeks/keyboard.h"
#include "udeks/task_request.h"

unsigned char terminal_test_memory[65536];
static unsigned char pending, character, scan;
unsigned char udeks_keyboard_event_get(struct udeks_key_event *event)
{
    if (!pending) return UDEKS_KEYBOARD_EMPTY;
    pending=0;
    event->type=UDEKS_KEY_EVENT_PRESS;
    event->scan_code=scan; event->character=character; event->modifiers=0;
    return UDEKS_KEYBOARD_OK;
}
unsigned char udeks_shell_interrupt_foreground(void) { return 0; }
unsigned char udeks_console_refresh_root(void) { return 0; }

static void key(unsigned char s, unsigned char c)
{
    scan=s; character=c; pending=1;
    assert(udeks_root_terminal_poll()==0);
}
static void output(unsigned char count)
{
    terminal_test_memory[UDEKS_TASK_REQUEST_BASE+UDEKS_TREQ_COUNT]=count;
    udeks_root_terminal_write_request();
}
int main(void)
{
    unsigned char row, length, i, pass, editor, column;
    unsigned char draft[55], saved[65], submitted[55];
    for (row=0;row<21;++row) for (length=0;length<=54;++length) {
        udeks_root_console_reset();
        udeks_line_editor_initialize();
        assert(!udeks_root_console_set_cursor(0,row,0));
        assert(!udeks_root_terminal_prompt());
        for (i=0;i<length;++i) { draft[i]='A'+i%26; key(255,draft[i]); }
        draft[length]=0;
        for (i=0;i<length/2;++i) key(UDEKS_KEY_SCAN_CURSOR_LEFT,0);
        column=udeks_root_console_cursor_column();
        memcpy(saved,udeks_root_console_row(row),65);
        output(0);
        assert(udeks_root_console_cursor_row()==row);
        assert(!memcmp(saved,udeks_root_console_row(row),65));
        /* Multiple full requests force wraps and scrolls. Include control
         * characters and a formfeed without letting them erase the editor. */
        for (pass=0;pass<8;++pass) {
            for (i=0;i<24;++i)
                terminal_test_memory[UDEKS_TASK_REQUEST_BASE+UDEKS_TREQ_PAYLOAD+i]='0'+i%10;
            if (pass==4) terminal_test_memory[UDEKS_TASK_REQUEST_BASE+UDEKS_TREQ_PAYLOAD]='\f';
            if (pass==6) terminal_test_memory[UDEKS_TASK_REQUEST_BASE+UDEKS_TREQ_PAYLOAD]='\n';
            output(24);
            editor=row?row:1;
            assert(udeks_root_console_cursor_row()==editor);
            assert(udeks_root_console_cursor_column()==column);
            assert(udeks_root_console_cursor_visible());
            assert(!memcmp(saved,udeks_root_console_row(editor),65));
            assert(udeks_line_editor_length()==length);
            assert(udeks_line_editor_cursor()==length-length/2);
            assert(!strcmp((const char *)udeks_line_editor_text(),(const char *)draft));
        }
        key(255,'\n');
        assert(udeks_line_editor_submission_ready());
        assert(udeks_line_editor_get_line(submitted,sizeof(submitted))==0);
        assert(!strcmp((const char *)submitted,(const char *)draft));
    }
    return 0;
}
