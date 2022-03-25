import curses
import curses.textpad

from collections import namedtuple
import os
import time

import locale
import logging

from pyfiglet import Figlet
import ueberzug.lib.v0 as ueberzug


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


lorem1 = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
         "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
         " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet."
lorem2 = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
        "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
        " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet." \
        " Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
        "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
        " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet." \
        " Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
        "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
        " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet." \
        " Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore " \
        "et dolore magna aliquyam erat, sed diam voluptua. At vero eos et accusam et justo duo dolores et ea rebum." \
        " Stet clita kasd gubergren, no sea takimata sanctus est Lorem ipsum dolor sit amet."
sampletext = "The red fox jumpes over the lazy dog. asjdkfl jalsdf"

texts = [lorem1, sampletext]
texts = [sampletext]

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
        if len(current_lst) + len(word)+1+1 >= width:
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
    def __init__(self, scr: curses.window, txtlst=sampletext):
        self.scr = scr
        curses.use_default_colors()
        curses.init_pair(1, -1, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        self.C_NORMAL = curses.color_pair(1)
        self.C_GREEN = curses.color_pair(2)
        self.C_RED = curses.color_pair(3)
        self.scr.erase()  # or scr.clear()

        self.text = txtlst[0]
        self.texts = txtlst
        self.typed = []
        self.errors = 0
        self.start = time.time()
        # Windows
        self.textwin = None
        self.wpmwin = None
        self.errwin = None
        self.setsize()
        assert isinstance(self.textwin, curses.window)
        self.draw()

    @property
    def maxx(self):
        maxx = self.scr.getmaxyx()[1]
        # -1 so len(range(-0-,maxx) = max -2
        return maxx -1

    def wpm(self):
        """ Get current wpm by len of self.typed and time since self.start"""
        # let's say a word is ~4 letters
        delta = time.time() - self.start
        charpersec = len(self.typed)/delta
        wpm = (charpersec * 60)/4
        return f"WPM:{int(wpm):>3}"

    def err(self):
        """ Get current error percentage by len of self.typed and self.errors"""
        if len(self.typed) == 0:
            percent = 0
        else:
            percent = self.errors / len(self.typed)
        if percent > 1:
            percent = 1
        percent = int(percent*100)
        return f"ERR:{percent:>3}%"

    def setsize(self):
        self.scr.erase()
        self.scr.clear()
        # How many lines are needed
        texty = len(textlst(self.text, self.maxx))
        #print(textlst(self.text, self.maxx))
        #print(textlst(self.text, texty))
        # Line length is max linelength as generated by textlst func.
        textx = max(len(x) for x in textlst(self.text, self.maxx))

        self._win_xy = namedtuple("s_win_xy", ["nlines", "ncols", "begin_y", "begin_x"])
        self.textwin_xy = self._win_xy(
            nlines=texty+2,  # extra space for border
            ncols=textx+2,  # extra space for border
            begin_y=0,
            begin_x=(self.maxx-textx)//2
        )
        logger.debug(f"Textlst:{textlst(self.text, self.maxx)}")
        logger.debug(f"self.maxx:{self.maxx}, textx:{textx}, texty:{texty} textwin_xy = {self.textwin_xy}")
        self.wpmwin_xy = self._win_xy(
            nlines=3,
            ncols=9,
            begin_y=self.textwin_xy.begin_y+self.textwin_xy.nlines+1,
            begin_x=self.textwin_xy.begin_x+3
        )
        self.errwin_xy = self._win_xy(
            nlines=3,
            ncols=10,
            begin_y=self.wpmwin_xy.begin_y,
            begin_x=self.textwin_xy.begin_x+self.textwin_xy.ncols - (10+3)                                #self.wpmwin_xy.begin_x+self.wpmwin_xy.ncols+2
        )

        self.textwin = self.scr.subwin(*self.textwin_xy)
        self.textwin.keypad(True) # allow capturing esc sequences!
        self.wpmwin = self.scr.subwin(*self.wpmwin_xy)
        self.errwin = self.scr.subwin(*self.errwin_xy)
        logger.debug(f"Created subwindows")
        self.textwin.box()
        self.wpmwin.box()
        self.errwin.box()
        self.scr.refresh()
        self.draw()
        return

    def draw(self):
        assert isinstance(self.textwin, curses.window)
        assert isinstance(self.wpmwin, curses.window)
        # y, x = self.textwin.getyx()
        # origin is 1,1 (because of border)
        txtlst = textlst(self.text, self.textwin_xy.ncols)
        logger.debug(f"txtlst:{txtlst}")
        for i, line in enumerate(txtlst):
            self.textwin.addstr(i+1,1,''.join(line))
        self.wpmwin.addstr(1,1,self.wpm(), curses.A_BOLD)
        self.wpmwin.noutrefresh()  # mark for refresh
        self.errwin.addstr(1,1,self.err(), curses.A_BOLD)
        self.errwin.noutrefresh()
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
        #self.wpmwin.addstr(1,1,self.wpm())
        #self.wpmwin.refresh()
        return

    @ueberzug.Canvas()
    def run(self, canvas):
        assert isinstance(self.textwin, curses.window)
        logger.info(f"starting run")

        f = Figlet(font='basic')
        warnwin = self.scr.subwin(9,9,2,self.maxx//2-4)
        warnwin.addstr(0,0,f.renderText('3'))
        warnwin.refresh()
        time.sleep(1)
        warnwin = self.scr.subwin(9,9,2,self.maxx//2-4)
        warnwin.addstr(0,0,f.renderText('2'))
        warnwin.refresh()
        time.sleep(1)
        warnwin = self.scr.subwin(9,9,2,self.maxx//2-4)
        warnwin.addstr(0,0,f.renderText('  1'))
        warnwin.refresh()
        time.sleep(1)
        self.start = time.time()

        for textsnip in self.texts:
            self.text = textsnip
            self.setsize()

            while True:
                # we use get_wch to be able to handle unicode
                try:
                    # set halfdelay, aka timeout mode and reset immediately after
                    curses.halfdelay(5)
                    inp_char = self.textwin.get_wch()
                    curses.nocbreak()
                    curses.cbreak()
                except curses.error:
                    # this updates wpm
                    self.draw()
                    continue
                # inp_char is int if function key, else unicode
                inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
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
                elif inp_key in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]:
                    pass
                elif inp_key == 10:
                    # enter
                    pass
                elif inp_key == 27:
                    # ESC key
                    logger.debug(f"Got esc event inp_char,inp_key{inp_char,inp_key},{curses.ungetch(inp_char)}")
                    break
                elif inp_key == curses.KEY_BACKSPACE or inp_key == 127 or str(inp_char) == "^?":
                    # elif inp_key in [curses.KEY_BACKSPACE, '\b', '\x7f']:
                    if len(self.typed) != 0:
                        # self.errors += 1
                        self.typed.pop()
                        y, x = self.textwin.getyx()
                        self.textwin.move(y, x - 1)
                        self.draw()
                else:
                    # Accept keys if text not already full
                    if len(self.typed) < sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)]):
                        logger.info(f"appending {inp_char} to typed")
                        self.typed.append(inp_char)

                        typedstr = "".join(self.typed)
                        orgstr = ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)])
                        errors = 0 if typedstr[-1] == orgstr[len(typedstr) - 1] else 1
                        self.errors += errors
                        self.draw()

                    else:
                        # just for debugging, should never happen
                        logger.debug(f"sum = {sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)])};;;{textlst(self.text, self.textwin_xy.ncols)}")
                        typedstr = "".join(self.typed)
                        orgstr = ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)])
                        logger.debug(f"typed:{typedstr}|")
                        logger.debug(f"orgin:{orgstr}|\n")

                # if correct
                #if "".join(self.typed) == ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)]):
                # if length is full
                if len(self.typed) >= sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)]):
                    self.textwin.border(*"*" * 8)
                    self.draw()
                    # reset after input
                    self.textwin.get_wch()

                    # demo = canvas.create_placement('demo', x=3, y=1, width=20)
                    # demo.path = '/home/lks/Akten/Sig.png'
                    # demo.visibility = ueberzug.Visibility.VISIBLE
                    # time.sleep(10)
                    # demo.visibility = ueberzug.Visibility.INVISIBLE

                    self.textwin.border()
                    self.typed = []
                    self.draw()
                    break

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
        myscr = MainScreen(stdscr, texts)
        myscr.run()
    finally:
        if stdscr is not None:
            curses.nocbreak()
            curses.echo()
            curses.endwin()


def test_textlist():
    widths = range(11, 44)
    e = None
    try:
        txtlst = textlst(lorem1, 3)
    except Exception as ex:
        e = ex
    assert isinstance(e,Exception)

    for w in widths:
        txtlst = textlst(lorem1, w)
        txtlst = [''.join(x) for x in txtlst]
        length = max([len(x) for x in txtlst])
        if length > w:
            print(f"width:{w}, actual:{length}, {txtlst}\n")




if __name__ == "__main__":
    # locale.setlocale(locale.LC_ALL, "")
    logger.info(f"TERM={os.environ['TERM']}")

    test_textlist()
    print(f"all tested")
    time.sleep(1)

    main()

