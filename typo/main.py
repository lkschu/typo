import curses
import curses.textpad

from collections import namedtuple
import os
import time

import locale

locale.setlocale(locale.LC_ALL, '')

sampletext = "The red fox jumpes over the lazy dog. asjdkfl jalsdf"
S_SPACE = '_'
S_RETURN = '⏎'

B_DOUBLE = ('║', '║', '═', '═', '╔', '╗', '╚', '╝')


def per_sentence(scr):
    pass

def main(scr):
    # INIT
    assert isinstance(scr, curses.window)
    curses.use_default_colors()
    curses.init_pair(1, -1, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    C_NORMAL = curses.color_pair(1)
    C_GREEN = curses.color_pair(2)
    C_RED = curses.color_pair(3)

    scr.erase()  # or scr.clear()

    # editwin = curses.newwin(5,30, 2,1)
    # curses.textpad.rectangle(scr, 1,0, 1+5+1, 1+30+1)
    # scr.refresh()
    # box = curses.textpad.Textbox(editwin)
    # # Let the user edit until Esc=27 or Ctrl-G is struck.
    # box.edit(lambda inp_x : 7 if (inp_x == 27) else inp_x)
    # box.gather()

    s_win_xy = namedtuple('s_win_xy', ['nlines', 'ncols', 'begin_y', 'begin_x'])
    textwin_xy = s_win_xy(nlines=3, ncols=len(sampletext) + 2, begin_y=3, begin_x=5)
    textwin = scr.subwin(*textwin_xy)
    textwin.box()
    def origin(): return textwin_xy.nlines // 2, 1
    textwin.addstr(*origin(), sampletext)
    textwin.move(*origin())

    typed = []


    def draw():
            y,x = textwin.getyx()
            textwin.addstr(*origin(), sampletext)
            textwin.move(*origin())
            for i,t in enumerate(typed):
                if sampletext[i] == t:
                    textwin.addstr(t, C_GREEN | curses.A_ITALIC)
                else:
                    textwin.addstr(t, C_RED | curses.A_UNDERLINE)

            scr.refresh()


    # main loop
    while True:
        # we use get_wch to be able to handle unicode
        inp_char = textwin.get_wch()
        # inp_chat is int if function key, else unicode
        inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char

        # textwin.addstr(0,0,str(inp_key))
        # textwin.refresh()
        # continue

        if inp_key == curses.KEY_RESIZE:
            # redraw screen
            break
        elif inp_key == 66 or inp_key == 65:
            # these translate to scroll-down and scroll-up
            pass
        elif inp_key == 10:
            # enter
            pass
        elif inp_key == 27:
            # ESC key
            break
        elif inp_key == curses.KEY_BACKSPACE or inp_key == 127 or str(inp_char) == '^?':
            # elif inp_key in [curses.KEY_BACKSPACE, '\b', '\x7f']:
            if len(typed) != 0:
                typed.pop()
                y,x = textwin.getyx()
                textwin.move(y,x-1)
                draw()
        else:
            # Accept keys if text not already full
            if len(typed) < len(sampletext):
                typed.append(inp_char)
                draw()


        if ''.join(typed) == sampletext:
            textwin.border(*'*' * 8)
            draw()
            # reset after input
            textwin.get_wch()
            textwin.border()
            typed = []
            draw()


if __name__ == "__main__":
    # print(os.environ['TERM'])
    # time.sleep(1)

    curses.wrapper(main)
else:
    curses.wrapper(main)

