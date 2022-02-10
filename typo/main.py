import curses
import curses.textpad

from collections import namedtuple
import os
import time

import locale
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_filehandler = logging.FileHandler(
    'typo.log',
    mode="w",
    delay=False,
)
log_formatter = logging.Formatter(fmt=f"%(asctime)s [%(levelname)-8s] %(message)s", datefmt="[%H:%M:%S]")
log_filehandler.setFormatter(log_formatter)
logger.addHandler(log_filehandler)


lorem = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
        "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
        " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet."
sampletext = "The red fox jumpes over the lazy dog. asjdkfl jalsdf"
print(len(lorem))
S_SPACE = "_"
S_RETURN = "⏎"

B_DOUBLE = ("║", "║", "═", "═", "╔", "╗", "╚", "╝")

# How to 'zip' 2 lists, while alternating values
# # tstr = "asoid j iua ai ji"
# # tstrlst = tstr.split()
# # spaces = [' ' for i in range(len(tstrlst)-1)]
# # for i,v in enumerate(tstrlst):
# #     if len(spaces)>i:
# #         tstrlst.insert((2*i)+1,spaces[i])


# print(make_list_of_fitting_length(sampletext, 9))
# [print("".join(x)) for x in make_list_of_fitting_length(lorem, 40)]
# time.sleep(5)


def textlst(txtstr: str, width: int):
    """ returns list of text, splitted into lines not longer than width """
    tmp_lst = txtstr.split(" ")
    ret_lst = []
    current_lst = []

    for word in tmp_lst:
        if len(word) > width:
            # this word doesn't fit at all
            raise ValueError(f"Can't fit <{word}> in a width of {width}!")
        # +1 for space before, +1 for space after word
        if len(current_lst) + len(word)+1+1 > width:
            # line + word to long -> new line
            ret_lst.append(current_lst)
            current_lst = []

        # if len(current_lst) != 0:
        #     # add spaces between words
        #     current_lst.extend(" ")
        current_lst.extend(word)
        if tmp_lst[-1] != word:
            # add spaces between words and the last word aswell
            current_lst.extend(" ")

    if len(current_lst) != 0:
        ret_lst.append(current_lst)
    return ret_lst


class MainScreen():
    def __init__(self, scr: curses.window, txt=sampletext):
        self.scr = scr
        curses.use_default_colors()
        curses.init_pair(1, -1, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        self.C_NORMAL = curses.color_pair(1)
        self.C_GREEN = curses.color_pair(2)
        self.C_RED = curses.color_pair(3)
        self.scr.erase()  # or scr.clear()

        self.text = txt
        self.typed = []
        self.start = time.time()
        self.textwin = None
        self.wpmwin = None
        self.setsize()
        assert isinstance(self.textwin, curses.window)
        self.draw()

    @property
    def maxx(self):
        maxx = self.scr.getmaxyx()[1]
        return maxx -2

    def wpm(self):
        # let's say a word is ~5 letters
        delta = time.time() - self.start
        charpersec = len(self.typed)/delta
        wpm = (charpersec * 60)//5
        return f"WPM: {int(wpm):<3}"

    def setsize(self):
        self.scr.erase()
        self.scr.clear()
        texty = len(textlst(self.text, self.maxx))
        textx = max(len(x) for x in textlst(self.text, self.maxx))

        self._win_xy = namedtuple("s_win_xy", ["nlines", "ncols", "begin_y", "begin_x"])
        self.textwin_xy = self._win_xy(
            nlines=texty+2,  # extra space for border
            ncols=textx+2,  # extra space for border
            begin_y=3,
            begin_x=(self.maxx-textx)//2
        )
        logger.debug(f"self.maxx:{self.maxx}, textx:{textx}, textwin_xy = {self.textwin_xy}")
        self.wpmwin_xy = self._win_xy(
            nlines=3,
            ncols=10,
            begin_y=self.textwin_xy.begin_y+self.textwin_xy.nlines+1,
            begin_x=self.textwin_xy.begin_x+3
        )

        self.textwin = self.scr.subwin(*self.textwin_xy)
        self.textwin.keypad(True) # allow capturing esc sequences!
        self.wpmwin = self.scr.subwin(*self.wpmwin_xy)
        logger.debug(f"Created subwindow")
        self.textwin.box()
        self.wpmwin.box()
        self.scr.refresh()
        self.draw()
        return

    def draw(self):
        assert isinstance(self.textwin, curses.window)
        assert isinstance(self.wpmwin, curses.window)
        # y, x = self.textwin.getyx()
        # origin is 1,1 (because of border)
        txtlst = textlst(self.text, self.textwin_xy.ncols)
        for i, line in enumerate(txtlst):
            self.textwin.addstr(i+1,1,''.join(line))
        self.textwin.move(1,1)

        llst = txtlst
        clst = self.typed
        lx,ly=0,0
        currentline = ''.join(llst[ly])
        for char in clst:
            if len(currentline) <= lx:
                lx, ly = 0, ly+1
                currentline = ''.join(llst[ly])
            if char == currentline[lx]:
                # Correct char
                self.textwin.addch(ly+1, lx+1, char, self.C_GREEN | curses.A_ITALIC)
            else:
                # Wrong char
                self.textwin.addch(ly+1, lx+1, char, self.C_RED | curses.A_UNDERLINE)
            lx += 1
        self.wpmwin.addstr(1,1,self.wpm())
        self.wpmwin.refresh()
        return

    def run(self):
        assert isinstance(self.textwin, curses.window)
        logger.info(f"starting run")
        curses.halfdelay(5)
        while True:
            # we use get_wch to be able to handle unicode
            try:
                inp_char = self.textwin.get_wch()
            except:
                # this updates wpm
                self.draw()
                continue
            try:
                # inp_char is int if function key, else unicode
                inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
            except Exception as e:
                logger.error(f"Error handling {repr(inp_char)}")
                raise e

            # textwin.addstr(0,0,str(inp_key))
            # textwin.refresh()
            # continue
            logger.info(f"Got keycode {inp_key}, {inp_char}")

            if inp_key == curses.KEY_RESIZE:
                # redraw screen
                self.setsize()
                self.draw()
            elif inp_key == curses.KEY_MOUSE:
                # these can translate to scroll-down and scroll-up
                try:
                    getmouse = curses.getmouse()
                except curses.error:
                    getmouse = None
                logger.debug(f"Got mouse event inp_char,inp_key{inp_char,inp_key}, getmouse: {getmouse}")
            elif inp_key == 10:
                # enter
                pass
            elif inp_key == 27:
                # ESC key
                try:
                    x = curses.getmouse()
                except curses.error:
                    x = None
                logger.debug(f"Got esc event inp_char,inp_key{inp_char,inp_key},{curses.ungetch(inp_char)} getmouse: {x}")
                break
            elif inp_key == curses.KEY_BACKSPACE or inp_key == 127 or str(inp_char) == "^?":
                # elif inp_key in [curses.KEY_BACKSPACE, '\b', '\x7f']:
                if len(self.typed) != 0:
                    self.typed.pop()
                    y, x = self.textwin.getyx()
                    self.textwin.move(y, x - 1)
                    self.draw()
            else:
                # Accept keys if text not already full
                if len(self.typed) < sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)]):
                    logger.info(f"appending {inp_char} to typed")
                    self.typed.append(inp_char)
                    self.draw()
                else:
                    # TODO: Problem
                    logger.debug(f"sum = {sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)])};;;{textlst(self.text, self.textwin_xy.ncols)}")
                    typedstr = "".join(self.typed)
                    orgstr = ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)])
                    logger.debug(f"typed:{typedstr}|")
                    logger.debug(f"orgin:{orgstr}|\n")

            if "".join(self.typed) == ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)]):
                self.textwin.border(*"*" * 8)
                self.draw()
                # reset after input
                self.textwin.get_wch()
                self.textwin.border()
                self.typed = []
                self.draw()

            logger.info(f"At end while loop")
        logger.info(f"Exiting while loop")

#

#


def main():
    stdscr = None
    try:
        # curses.setupterm('alacritty')  # no need to set this up!
        logger.info(f"Starting main function")
        logger.info(f"TERM={os.environ['TERM']}")
        curses.set_escdelay(5)  # wait 10 msec on esc to distinguish between esc and esc-sequence
        stdscr = curses.initscr()
        curses.noecho()
        curses.raw()
        curses.cbreak()
        curses.start_color()
        curses.mousemask(curses.BUTTON1_CLICKED)
        stdscr.keypad(True)
        logger.info(f"stdscr is window? {isinstance(stdscr,curses.window)}")
        myscr = MainScreen(stdscr, lorem)
        myscr.run()
    finally:
        if stdscr is not None:
            curses.nocbreak()
            curses.echo()
            curses.endwin()


def test_textlist():
    widths = range(11,44)
    e = None
    try:
        txtlst = textlst(lorem, 3)
    except Exception as ex:
        e = ex
    assert isinstance(e,Exception)

    for w in widths:
        txtlst = textlst(lorem, w)
        txtlst = [''.join(x) for x in txtlst]
        length = max([len(x) for x in txtlst])
        if length > w:
            print(f"width:{w}, actual:{length}, {txtlst}\n")




if __name__ == "__main__":
    #locale.setlocale(locale.LC_ALL, "")
    logger.info(f"TERM={os.environ['TERM']}")

    test_textlist()
    print(f"all tested")
    time.sleep(1)


    main()


