from __future__ import annotations
from typing import Type

import curses
import curses.textpad

from enum import Enum, auto

from collections import namedtuple
import os
import time
from datetime import timedelta
from typing import Text
import yaml

import locale
import logging

from dataclasses import dataclass, asdict

from pyfiglet import Figlet


# Default logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_filehandler = logging.FileHandler(
    "typo.log",
    mode="w",
    delay=False,
)
log_formatter = logging.Formatter(fmt=f"%(asctime)s [%(levelname)-8s] %(message)s", datefmt="[%H:%M:%S]")
log_filehandler.setFormatter(log_formatter)
logger.handlers.clear()
logger.addHandler(log_filehandler)


teststring = "Mr. Stubb,\" said I, turning to that worthy, who, buttoned up in his oil-jacket, was now calmly smoking his pipe in the rain; \"Mr. Stubb, I think I have heard you say that of all whalemen you ever met, our chief mate, Mr. Starbuck, is by far the most careful and prudent.\nI suppose then, that going plump on a flying whale with your sail set in a foggy squall is the height of a whaleman's discretion?"



S_SPACE = "_"
S_RETURN = "⏎"

B_DOUBLE = ("║", "║", "═", "═", "╔", "╗", "╚", "╝")


def textlst(txtstr: str, width: int):
    """returns list of text, splitted into lines not longer than width"""
    tmp_lst = txtstr.split(" ")
    ret_lst = []
    current_lst = []

    for i, word in enumerate(tmp_lst):

        if len(word) > width or (len(word) + 1 > width and len(tmp_lst) > 1):
            # this word (and 1 space) doesn't fit at all if there are at least 2 words there must be place for 1 space
            raise ValueError(f"Can't fit <{word}> (plus possible space) in a width of {width}!")

        # if it's the last word we need no space at the end
        # +1 for space after word
        if (len(current_lst) + len(word) + 1 > width and i + 1 != len(tmp_lst)) or (
            len(current_lst) + len(word) > width and i + 1 == len(tmp_lst)
        ):
            # line + word to long -> new line
            ret_lst.append(current_lst)
            current_lst = []

        current_lst.extend(word)
        if tmp_lst[-1] != word:
            # add spaces between words and the last word aswell
            current_lst.extend(" ")

    if len(current_lst) != 0:
        ret_lst.append(current_lst)
    return ret_lst


def make_ascii(string):
    """ replace non-ascii elements like quotation marks with their ascii counterparts """
    # wrong chars : —,‘,’,“,”
    if type(string) is not str:
        raise TypeError(f"Expected string, got {type(string)}")
    replace = {"—": "-", "‘": "'", "’": "'", "“": '"', "”": '"'}
    c_list = []
    for c in string:
        if c in replace.keys():
            c_list.append(replace[c])
        else:
            c_list.append(c)
    ret_str = "".join(c_list)
    if ret_str.isascii():
        return ret_str

def shorten_if_too_long(string: str, max_len: int) -> str:
    " shorten a given string if it's too long "
    if max_len <= 0:
        raise ValueError("String length must be bigger than 0!")
    if len(string) <= max_len:
        return string
    return f"{string[:max_len-1]}…"


@dataclass
class TypoChapter:
    title: str
    sections: list[str]
    options: dict

    @classmethod
    def from_dict(cls, chapter_dict: dict):
        try:
            if "options" in chapter_dict.keys():
                options = chapter_dict["options"]
            else:
                options = {}

            return TypoChapter(title=chapter_dict["title"], sections=chapter_dict["sections"], options=options)
        except BaseException as e:
            raise ValueError(
                f"Can't create chapter from chapter_dict! Type title {chapter_dict.get('title', None)}; "
                f"Type sections {chapter_dict.get('sections', None)}"
            ) from e


class Modus(Enum):
    # TODO: do we really need this???
    MENU = auto()
    SUMMARY = auto()
    SESSION = auto()


class MainScreen:
    def __init__(self, scr: curses.window, txtlst):
        self.scr = scr

        # Config
        curses.use_default_colors()
        curses.init_pair(1, -1, -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_RED, -1)
        self.C_NORMAL = curses.color_pair(1)
        self.C_GREEN = curses.color_pair(2)
        self.C_RED = curses.color_pair(3)


        self.scr.erase()  # or scr.clear()

        self.modus = Modus.MENU
        self.modus = Modus.SESSION

        self.text = txtlst[0]
        self.texts = txtlst
        # TODO maybe give typed lists for sections like this [[chars from sec1], [chars from sec2]]
        self.typed = []
        self.typed_sum = 0  # save carry over when new section starts
        self.err_lst = []
        self.start = time.time()

        self.choice = 0  # current choice when in option menu mode
        self.scroll = 0

        # TODO: encapsulate all (texts/text, section) in chapter class?
        self.chapter = TypoChapter(title="", sections=[], options={})  # keeps track of current chapter
        self.section = (
            0,
            0,
        )  # tuple (current,max) to keep track of sections in chapter

        # TODO: this is also rediculous
        # Windows
        self.textwin = None  # main window in center with box
        self.titlewin = None  # Title for session
        self.progresswin = None  # progress status for session
        self.wpmwin = None  # current wpm in session
        self.errwin = None  # current error percentage in session
        self.setsize()
        self.draw()

    @property
    def maxx(self) -> int:
        """Max width for text, so decoration is not included"""
        maxx = self.scr.getmaxyx()[1]
        return maxx - 2

    @property
    def maxy(self) -> int:
        """Max height for text, so decoration is not included"""
        maxy = self.scr.getmaxyx()[0]
        return maxy - 2

    @property
    def errors(self) -> int:
        """Gives sum of errors"""
        return len(self.err_lst)

    def make_menu(self, option_lst: list[str], current: int = 0) -> int:
        """
        makes a menu out of a list of options, centers on given index.
        return index number or -1 if exit
        """

        # IDEA:
        # ^^^   <- marks the first line in window if there are earlier lines
        # 3. asldkfj
        # 4. asdflasjdf
        # vvv   <- there are more options below

        oldmodus = self.modus
        self.modus = Modus.MENU
        curses.curs_set(0)

        # shape tmp_lst # TODO: why is this a closure
        def shape(option_list):
            # add numbers to each option
            tmp_lst = [f"{i}.) {line}\n" for i, line in enumerate(option_list)]
            # trim to visible part # TODO: wtf is self.scroll?!
            tmp_lst = tmp_lst[self.scroll : min(self.scroll + self.maxy, self.scroll + len(tmp_lst))]
            # Trim lines that are too long, padd lines that are too short
            for i, line in enumerate(tmp_lst):
                if len(line) > self.maxx + 1:
                    line = f"{line[:self.maxx - 4]}...\n"
                    tmp_lst[i] = line
                # not neccessarily needed
                elif len(line) < self.maxx + 1:
                    line = f"{line[:-1]:<{self.maxx}}\n"
                    tmp_lst[i] = line
            # Add ^ / v marker
            if self.scroll > 0:
                tmp_lst[0] = f"{' ^^^':<{self.maxx}}\n"
            if len(option_lst) - self.scroll > len(tmp_lst):
                tmp_lst[-1] = f"{' vvv':<{self.maxx}}\n"
            self.text = "".join(tmp_lst)[:-1]

        shape(option_lst)
        self.setsize()

        assert isinstance(self.textwin, curses.window)

        while True:
            inp_char = self.textwin.get_wch()
            shape(option_lst)

            # inp_char is int if function key, else unicode
            inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
            logger.info(f"Got keycode {inp_key}, {inp_char}")

            if inp_key == curses.KEY_RESIZE:
                # redraw screen
                self.setsize()
                self.draw()
            elif inp_key == curses.KEY_UP:
                if self.choice > 0:
                    self.choice -= 1
                if self.choice == 0 and self.scroll > 0:
                    self.scroll -= 1
                self.setsize()
                self.draw()
            elif inp_key == curses.KEY_DOWN:
                if self.choice < len(self.text.split("\n")) - 1:
                    self.choice += 1
                if self.choice == len(self.text.split("\n")) - 1 and len(option_lst) - self.scroll > len(
                    self.text.split("\n")
                ):
                    self.scroll += 1
                self.setsize()
                self.draw()
            elif inp_key in [10, curses.KEY_RIGHT]:
                # enter
                break
            elif inp_key in [27, curses.KEY_LEFT]:
                self.choice = -1
                # ESC key
                break

        curses.curs_set(2)
        self.modus = oldmodus
        self.text = ""
        logger.info(f"Exiting menu with {option_lst[self.choice+self.scroll]}")
        return self.choice + self.scroll

    def wpm(self) -> float:
        """Get current wpm by len of self.typed and time since self.start"""
        # let's say a word is ~4 letters
        delta = time.time() - self.start
        charpersec = (len(self.typed) + self.typed_sum) / delta
        wpm = (charpersec * 60) / 4
        return wpm

    def err(self) -> int:
        """Get current error percentage by len of self.typed and self.errors"""
        if len(self.typed) + self.typed_sum == 0:
            percent = 0
        else:
            percent = self.errors / (len(self.typed) + self.typed_sum)
        if percent > 1:
            percent = 1
        percent = int(percent * 100)
        return percent

    def setsize(self):
        """
        Determine the needed size of textwin and possible subwindows, calls draw at the end
        """
        self.scr.erase()
        self.scr.clear()

        # Line length is max linelength as generated by textlst func.
        textx = max(len(x) for x in textlst(self.text, self.maxx))
        # How many lines are needed
        texty = len(textlst(self.text, self.maxx))

        self._win_xy = namedtuple("s_win_xy", ["nlines", "ncols", "begin_y", "begin_x"])

        if self.modus == Modus.SESSION:
            self.textwin_xy = self._win_xy(
                nlines=texty + 2,  # extra space for border
                ncols=textx + 2,  # extra space for border
                begin_y=3,
                begin_x=(self.maxx - textx) // 2,
            )
        else:
            # Handle text in 'display' mode. So normal strings, including \n can be printed
            assert isinstance(self.text, str)
            toprint = self.text.split("\n")
            texty = min(len(toprint), self.maxy)
            textx = min(max(len(line) for line in toprint), self.maxx)
            self.textwin_xy = self._win_xy(
                nlines=texty + 2,  # extra space for border
                ncols=textx + 2,  # extra space for border
                begin_y=0,
                begin_x=(self.maxx - textx) // 2,
            )

        self.textwin = self.scr.subwin(*self.textwin_xy)
        self.textwin.keypad(True)  # allow capturing esc sequences!

        if self.modus == Modus.SESSION:
            logger.debug(f"Textlst:{textlst(self.text, self.maxx)}")
            logger.debug(f"self.maxx:{self.maxx}, textx:{textx}, texty:{texty} textwin_xy = {self.textwin_xy}")
            self.titlewin_xy = self._win_xy(
                nlines=3,
                ncols=20,
                begin_y=self.textwin_xy.begin_y - 3,
                begin_x=self.textwin_xy.begin_x + 3,  # 3 is for space
            )
            self.progresswin_xy = self._win_xy(
                nlines=3,
                ncols=7,  # |xy/xy|
                begin_y=self.titlewin_xy.begin_y,
                begin_x=self.titlewin_xy.begin_x
                + self.textwin_xy.ncols
                - (10 + 3),  # self.wpmwin_xy.begin_x+self.wpmwin_xy.ncols+2
            )
            self.wpmwin_xy = self._win_xy(
                nlines=3,
                ncols=9,
                begin_y=self.textwin_xy.begin_y + self.textwin_xy.nlines + 1,
                begin_x=self.textwin_xy.begin_x + 3,
            )
            self.errwin_xy = self._win_xy(
                nlines=3,
                ncols=10,
                begin_y=self.wpmwin_xy.begin_y,
                begin_x=self.textwin_xy.begin_x
                + self.textwin_xy.ncols
                - (10 + 3),  # self.wpmwin_xy.begin_x+self.wpmwin_xy.ncols+2
            )
            self.titlewin = self.scr.subwin(*self.titlewin_xy)
            self.titlewin.box()
            self.progresswin = self.scr.subwin(*self.progresswin_xy)
            self.progresswin.box()
            self.wpmwin = self.scr.subwin(*self.wpmwin_xy)
            self.wpmwin.box()
            self.errwin = self.scr.subwin(*self.errwin_xy)
            self.errwin.box()
            logger.debug(f"Created subwindows")
        self.textwin.box()
        self.scr.refresh()
        self.draw()
        return

    def draw(self):
        if self.modus == Modus.SESSION:
            assert isinstance(self.titlewin, curses.window)
            assert isinstance(self.progresswin, curses.window)
            assert isinstance(self.textwin, curses.window)
            assert isinstance(self.wpmwin, curses.window)
            assert isinstance(self.errwin, curses.window)
            # origin is 1,1 (because of border)

            txtlst = textlst(self.text, self.maxx)
            for i, line in enumerate(txtlst):
                self.textwin.addstr(i + 1, 1, "".join(line))

            max_lenth = self.titlewin_xy.ncols - 2
            if len(self.chapter.title) <= max_lenth:
                chapter = self.chapter.title
            else:
                chapter = f"{self.chapter.title[:max_lenth-2]}.."
            logger.debug(f"Chapter: {chapter}")
            self.titlewin.addstr(1, 1, chapter)
            self.titlewin.noutrefresh()
            self.progresswin.addstr(1, 1, f"{self.section[0]}/{self.section[1]}")
            self.progresswin.noutrefresh()
            self.wpmwin.addstr(1, 1, f"WPM:{int(self.wpm()):>3}", curses.A_BOLD)
            self.wpmwin.noutrefresh()  # mark for refresh
            self.errwin.addstr(1, 1, f"ERR:{self.err():>3}%", curses.A_BOLD)
            self.errwin.noutrefresh()

            self.textwin.move(1, 1)

            llst = txtlst
            clst = self.typed
            lx, ly = 0, 0
            currentline = "".join(llst[ly])
            for char in clst:
                if len(currentline) <= lx:
                    lx, ly = 0, ly + 1
                    currentline = "".join(llst[ly])
                if char == currentline[lx]:
                    # Correct char
                    self.textwin.addch(ly + 1, lx + 1, char, self.C_GREEN | curses.A_ITALIC)
                else:
                    # Wrong char
                    self.textwin.addch(ly + 1, lx + 1, char, self.C_RED | curses.A_UNDERLINE)
                lx += 1
        else:
            assert isinstance(self.textwin, curses.window)
            self.textwin.move(1, 1)

            self.textwin.refresh()
            self.textwin.redrawwin()
            self.textwin.box()
            assert isinstance(self.text, str)

            for i, line in enumerate(self.text.split("\n")):
                if self.modus == Modus.MENU and i == self.choice:
                    self.textwin.addnstr(i + 1, 1, line, self.maxx, curses.A_REVERSE)
                else:
                    self.textwin.addnstr(i + 1, 1, line, self.maxx)

            self.textwin.redrawwin()
            self.textwin.refresh()
        return

    def run(self):
        # Test menuShikoku
        curses.curs_set(0)
        path = "./res"
        menu = sorted([x for x in os.listdir(path) if os.path.isfile(os.path.join(path, x))])
        for i, m in enumerate(menu):
            with open(os.path.join(path, m), "r") as f:
                menu[i] = TypoChapter.from_dict(yaml.safe_load(f))

        x = self.make_menu([m.title for m in menu])
        logger.info(f"Menu result: {x}, {menu}")
        chap1 = menu[x]
        assert isinstance(chap1, TypoChapter)
        self.texts = chap1.sections
        self.chapter = chap1
        self.make_session()
        self.make_summary()

    def make_summary(self):
        assert isinstance(self.textwin, curses.window)
        self.modus = Modus.SUMMARY
        curses.flushinp()
        hours, minutes, sec = str(timedelta(seconds=time.time() - self.start)).split(":")
        hours = "" if hours == "0" or hours == "00" else f"{hours} hours, "
        minutes = "" if minutes == "0" or minutes == "00" else f"{minutes} minutes and "
        sec = sec.split(".")[0] + "." + sec.split(".")[1][0]
        sec = "" if sec == "0" or sec == "00" else f"{sec} sec"
        self.text = (
            f"Typed {self.typed_sum} characters in {hours}{minutes}{sec}."
            f"\nWPM: {self.wpm():.2f}"
            f"\nTyping errors: {self.err():>3}%."
            f"\nAll errors: {self.err_lst}"
        )
        logger.info(self.text)
        self.setsize()
        self.textwin.get_wch()

    def make_session(self):
        assert isinstance(self.textwin, curses.window)
        logger.info(f"starting session")

        self.scr.clear()
        self.scr.refresh()

        curses.curs_set(0)
        f = Figlet(font="basic")

        # Countdown
        warnwin = self.scr.subwin(9, 9, 2, self.maxx // 2 - 4)
        warnwin.addstr(0, 0, f.renderText("2"))
        warnwin.refresh()
        time.sleep(0.5)
        warnwin = self.scr.subwin(9, 9, 2, self.maxx // 2 - 4)
        warnwin.addstr(0, 0, f.renderText("  1"))
        warnwin.refresh()
        time.sleep(0.75)
        self.start = time.time()
        curses.curs_set(2)

        for i, section in enumerate(self.texts):
            self.section = (i + 1, len(self.texts))
            self.text = section
            self.setsize()

            while True:
                # TODO:Character handling looks waaaay to wild!

                # we use get_wch to be able to handle unicode
                try:
                    # set halfdelay, aka timeout mode and reset immediately after
                    # timeout is needed, if we block until next input timer can't update
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

                # curses.KEY_RESIZE get's send when ever the screen resizes
                if inp_key == curses.KEY_RESIZE:
                    # redraw screen
                    logger.debug("Redraw due to resize")
                    self.setsize()
                    self.draw()
                elif inp_key == curses.KEY_MOUSE:
                    # these can translate to scroll-down and scroll-up
                    try:
                        getmouse = curses.getmouse()
                    except curses.error:
                        getmouse = None
                    logger.debug(f"Got mouse event inp_char,inp_key{inp_char, inp_key}, getmouse: {getmouse}")
                elif inp_key in [
                    curses.KEY_UP,
                    curses.KEY_DOWN,
                    curses.KEY_LEFT,
                    curses.KEY_RIGHT,
                ]:
                    pass
                elif inp_key == 10:
                    # enter
                    pass
                elif inp_key == 27:
                    # ESC key
                    logger.debug(f"Got esc event inp_char,inp_key{inp_char, inp_key},{curses.ungetch(inp_char)}")
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
                        orgstr = "".join(["".join(line) for line in textlst(self.text, self.textwin_xy.ncols)])

                        if typedstr[-1] == orgstr[len(typedstr) - 1]:
                            # correct
                            logger.debug(f"Registered correct key {inp_char}")
                        else:
                            # incorrect
                            logger.debug(f"Registered wrong key {inp_char}")
                            self.err_lst.append(inp_char)
                        self.draw()

                    else:
                        # just for debugging, should never happen
                        logger.debug(
                            f"sum = {sum([len(x) for x in textlst(self.text, self.textwin_xy.ncols)])};;;{textlst(self.text, self.textwin_xy.ncols)}"
                        )
                        typedstr = "".join(self.typed)
                        orgstr = "".join(["".join(line) for line in textlst(self.text, self.textwin_xy.ncols)])
                        logger.debug(f"typed:{typedstr}|")
                        logger.debug(f"orgin:{orgstr}|\n")

                # if correct
                # if "".join(self.typed) == ''.join([''.join(line) for line in textlst(self.text, self.textwin_xy.ncols)]):
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

                    logger.debug(
                        f"Finished sec. {section}: Typed:{len(self.typed)}, WPM:{int(self.wpm())}, err:{self.err()}%, errors:{self.err_lst}"
                    )
                    self.textwin.border()
                    self.typed_sum += len(self.typed)
                    self.typed = []
                    self.draw()
                    break

            logger.info(f"At end while loop")
        logger.info(f"Exiting while loop")


#

#
class TextSessionObject():
    def __init__(self,text:str) -> None:
        self.raw_text = text
        self.replacements = { '\n':f'{S_RETURN}' }

    def replace(self,s:str):
        """ handle default keys for the replacements dict """
        return s if s not in self.replacements.keys() else self.replacements[s]

    def display_mode(self) -> str:
        """ replace some symbols (like newline) for displaying in terminal """
        buf = self.raw_text
        for k,v in self.replacements.items():
            buf = buf.replace(k,v)
        return buf

    def format_text(self,width:int) -> str:
        """ fill a string with spaces and linebreaks so it fits into the given width """
        """returns list of text, splitted into lines not longer than width"""
        tmp_lst = self.display_mode().split(self.replace(" "))
        ret_lst = []
        current_lst = []

        for i, word in enumerate(tmp_lst):

            if len(word) > width or (len(word) + 1 > width and len(tmp_lst) > 1):
                # this word (and 1 space) doesn't fit at all if there are at least 2 words there must be place for 1 space
                raise ValueError(f"Can't fit <{word}> (plus possible space) in a width of {width}!")

            # check if we have a newline in the last added part
            if len(current_lst) > 0 and current_lst[-1][-1] == self.replace("\n"):
                logger.debug(f"Current list: {current_lst}\n {current_lst[-1][-1]}")
                ret_lst.append(current_lst)
                current_lst = []


            # if it's the last word we need no space at the end
            # +1 for space after word
            if (len(current_lst) + len(word) + 1 > width and i + 1 != len(tmp_lst)) or (
                len(current_lst) + len(word) > width and i + 1 == len(tmp_lst)
            ):
                # line + word to long -> new line
                ret_lst.append(current_lst)
                current_lst = []

            current_lst.extend(word)
            if tmp_lst[-1] != word:
                # add spaces between words and the last word aswell
                current_lst.extend(" ")

        if len(current_lst) != 0:
            ret_lst.append(current_lst)
        for x in ret_lst:
            logger.debug(f"{x}\n")
        ret_lst = ["".join(x) for x in ret_lst]
        return "\n".join(ret_lst)


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
        logger.info(f"stdscr is window? {isinstance(stdscr, curses.window)}")
        #myscr = MainScreen(stdscr, ["x"])
        #myscr.run()
        curses.curs_set(0)
        logger.info(f"stdscr: {stdscr.getmaxyx()}")
        subwin = stdscr.subwin(0,0)
        logger.info(f"subwin: {subwin.getmaxyx()}")
        ttt = TextSessionObject(teststring)
        subwin.addstr(0,0, ttt.format_text(subwin.getmaxyx()[1]))
        stdscr.refresh()
        time.sleep(5)
    finally:
        if stdscr is not None:
            curses.nocbreak()
            curses.echo()
            curses.endwin()


# def test_textlist():
#     widths = range(11, 44)
#     e = None
#     try:
#         txtlst = textlst(lorem1, 3)
#     except Exception as ex:
#         e = ex
#     assert isinstance(e, Exception)
#
#     for w in widths:
#         txtlst = textlst(lorem1, w)
#         txtlst = ["".join(x) for x in txtlst]
#         length = max([len(x) for x in txtlst])
#         if length > w:
#             print(f"width:{w}, actual:{length}, {txtlst}\n")


if __name__ == "__main__":
    # locale.setlocale(locale.LC_ALL, "")
    logger.info(f"TERM={os.environ['TERM']}")
    print(f"$TERM: {os.environ['TERM']}")

    main()
