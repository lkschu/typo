from __future__ import annotations
from collections import namedtuple
from re import sub
from typing import Type, List, NamedTuple, Union, Optional

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

from dataclasses import dataclass, asdict, replace

# from pyfiglet import Figlet


border_chars = namedtuple(
    "border_chars", ["left", "right", "top", "bottom", "topleft", "topright", "bottomleft", "bottomright"]
)
window_spacing = namedtuple("window_spacing", ["left", "right", "top", "bottom"])
window_spacing.__annotations__ = { "left":int, "right":int , "top":int, "bottom":int}
# Used for wpm,accuracy etc.; one of each: horizontal and vertical spacing must be set
window_dimensions = namedtuple("window_dimensions", ["active", "nlines", "ncols", "window_spacing"])
window_information = namedtuple("window_information", ["window", "callback"])

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


teststring = 'Mr. Stubb," said I, turning to that worthy, who, buttoned up in his oil-jacket, was now calmly smoking his pipe in the rain; "Mr. Stubb, I think I have heard you say that of all whalemen you ever met, our chief mate, Mr. Starbuck, is by far the most careful and prudent.\nI suppose then, that going plump on a flying whale with your sail set in a foggy squall is the height of a whaleman\'s discretion?'
teststring += "\n\n" + teststring


VALID_INPUTS: str = "abcdefghijklmnopqrstuvwxyz"
VALID_INPUTS += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
VALID_INPUTS += " "
VALID_INPUTS += "1234567890"
VALID_INPUTS += "äüöÄÜÖß"
VALID_INPUTS += ",.;:><?"
VALID_INPUTS += "§~_+=-`€°!@#$%^&*()[]{}/\\'\""
VALID_INPUTS += "\n\t"

S_SPACE = "_"
S_RETURN = "⏎"
S_RETURN = ""
S_TAB = "↹"

B_DOUBLE = ("║", "║", "═", "═", "╔", "╗", "╚", "╝")

REPLACEMENTS = {"\n": S_RETURN, "\t": S_TAB}
BORDER_MARGIN = window_spacing(left=4, right=4, top=5, bottom=6)
BORDER_PADDING = window_spacing(left=1, right=1, top=1, bottom=1)
WPM_WINDOW = window_dimensions(active=True, nlines=3, ncols=9, window_spacing=window_spacing(None, 1, 1, None))
ACC_WINDOW = window_dimensions(active=True, nlines=3, ncols=9, window_spacing=window_spacing(None, 1, None, 1))


CHARACTERS_PER_WORD = 5

WINDOWS_TO_REFRESH = {}


class TypoError:  # {{{
    """stores typos"""

    def __init__(self, char: str, tipped: str, corrected: bool) -> None:
        self.char = char
        self.tipped = tipped
        self.corrected = corrected

    def __str__(self) -> str:
        return f"TypoError: should be {repr(self.char)} but is {repr(self.tipped)}. Was corrected: {self.corrected}"


# }}}


class SessionTextObject:  # {{{
    """data modell for the text in one session. includes the 'normal' guide text as well as typed input"""

    def __init__(self, text: str) -> None:
        self.raw_text = text
        self.replacements = REPLACEMENTS

        self.typed = []  # simple char buffer
        self.corrected_errors = []

    def replace(self, s: str) -> str:
        """handle default keys for the replacements dict"""
        return s if s not in self.replacements.keys() else self.replacements[s]

    def display_mode(self) -> str:
        """replace some symbols (like newline) for displaying in terminal"""
        buf = self.raw_text
        for k, v in self.replacements.items():
            buf = buf.replace(k, v)
        return buf

    def get_accuracy(self) -> float:
        """return accuracy of typed characters"""
        complete = self.get_typed_chars(256, correct=True, typos=True)
        complete = [x for c in complete for x in c]
        correct = self.get_typed_chars(256, correct=True, typos=False)
        correct = [x for c in correct for x in c]
        count = 0
        # Compare all typed characters to the wrongly typed ones
        for a, c in zip(complete, correct):
            if a == c:
                count += 1  # this one is correct
        return (count / (len(complete) + len(self.corrected_errors))) * 100 if len(complete) > 0 else 100.0

    def get_typed_chars(self, width, correct: bool = True, typos: bool = True) -> List[List[str]]:
        """format typed chars in the same way as"""
        formated_chars = []
        last_index = 0
        # TODO: this should also be performed by the same function as for raw_text
        buf = self.typed
        get_guide_chars = self.get_guide_chars(width)
        for i, c in enumerate(buf):
            buf[i] = self.replace(c)
        # TODO: fix for replacing one char with multiple chars: concat inner lists
        buf = [c for x in buf for c in x]

        # iterate through all characters in buffer and compare with get_guide_chars
        for nline, l in enumerate(get_guide_chars):
            if len(buf[last_index:]) > len(l):
                # to_append = [c for c in buf[last_index:last_index+len(l)]]
                to_append = []
                for i, c in enumerate(buf[last_index : last_index + len(l)]):
                    # check if correct, and if correct/typos should be returned
                    if c == get_guide_chars[nline][i]:
                        if correct:
                            to_append.append(c)
                        else:
                            to_append.append("")
                    else:
                        if typos:
                            to_append.append(c)
                        else:
                            to_append.append("")
                formated_chars.append(to_append)
                last_index = last_index + len(l)
            else:
                to_append = []
                for i, c in enumerate(buf[last_index:]):
                    # check if correct, and if correct/typos should be returned
                    if c == get_guide_chars[nline][i]:
                        if correct:
                            to_append.append(c)
                        else:
                            to_append.append("")
                    else:
                        if typos:
                            to_append.append(c)
                        else:
                            to_append.append("")
                formated_chars.append(to_append)
                last_index = len(buf)
        return formated_chars

    def type_char(self, c: str):
        """type one character"""
        if len(c) != 1:
            raise ValueError("Expected char in put, aka string with length 1!")
        self.typed.append(c)

    def type_backspace(self):
        """remove on character"""
        if len(self.typed) >= 1:
            # Get both character buffer, find correct position and compare char; 1024 is just a random number
            typed_chars = self.get_typed_chars(1024)
            l = len([sublist for sublist in typed_chars if sublist != []]) - 1
            c = len([x for x in typed_chars[l] if x != ""]) - 1
            c_typed = typed_chars[l][c]
            c_actual = self.get_guide_chars(1024)[l][c]
            if c_typed != c_actual:
                self.corrected_errors.append(TypoError(char=c_actual, tipped=c_typed, corrected=True))
                logger.info(f"Created TypoErro: {self.corrected_errors[-1]}")
            self.typed.pop()

    def get_guide_chars(self, width: int) -> List[List[str]]:
        """fill a string with spaces and linebreaks so it fits into the given width"""
        """returns list of text, splitted into lines not longer than width"""

        # TODO: iterate through complete string as a char buffer
        # buf = self.display_mode()
        # lines = []
        # last_valid_break = 0
        # last_word_break = 0
        # for i,c in enumerate(buf):
        #     if c == self.replace("\n"):
        #         line = buf[last_valid_break:i+1]
        #         last_valid_break = i+1
        #         last_word_break = last_valid_break
        #         if len(line) > width:
        #             raise ValueError(f"line too long: {line}")
        #         else:
        #             lines.append(line)
        #     else:

        tmp_lst = self.display_mode().split(self.replace(" "))
        # also split at newline character
        l = []
        for w in tmp_lst:
            if self.replace("\n") in w:
                w_l = w.split(self.replace("\n"))
                w_l = [u + self.replace("\n") for u in w_l[:-1]] + [w_l[-1]]
                l.extend(w_l)
            else:
                l.append(w)
        tmp_lst = l

        # logger.debug(tmp_lst)
        ret_lst = []
        current_lst = []

        for i, word in enumerate(tmp_lst):

            if len(word) > width or (len(word) + 1 > width and len(tmp_lst) > 1):
                # this word (and 1 space) doesn't fit at all if there are at least 2 words there must be place for 1 space
                raise ValueError(f"Can't fit <{word}> (plus possible space) in a width of {width}!")

            # check if we have a newline in the last added part, mind the space
            if len(current_lst) > 1 and (
                current_lst[-1] == self.replace(" ") and current_lst[-2] == self.replace("\n")
            ):
                # Stip space after newline
                ret_lst.append(current_lst[:-1])
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
                current_lst.extend(self.replace(" "))

        if len(current_lst) != 0:
            ret_lst.append(current_lst)
        # logger.debug(ret_lst)
        return ret_lst

    # }}}


def fix_height(
    char_buffer: List[List[str]],
    focus_line: int,
    height: int,
    replace_top: List[str] = None,
    replace_bottom: List[str] = None,
) -> List[List[str]]:
    """Center on line number <line> and trim the rest. If passed replace top/bottom line with symbols like '^^^'/'vvv'"""
    # logger.debug(f"Fixing height: len buffer:{len(char_buffer)}, focus:{focus_line}, height:{height}")
    if height >= len(char_buffer):
        return char_buffer
    if focus_line <= (height - 1) // 2:
        ret = char_buffer[:height]
        if replace_bottom != None:
            ret[height - 1] = replace_bottom
        return ret
    elif focus_line > len(char_buffer) - 1 - (height - (height % 2)) // 2:
        ret = char_buffer[-height:]
        if replace_top != None:
            ret[0] = replace_top
        return ret
    ret = char_buffer[focus_line - (height - 1) // 2 : focus_line + (height - (height % 2)) // 2 + 1]
    if replace_top != None:
        ret[0] = replace_top
    if replace_bottom != None:
        ret[height - 1] = replace_bottom
    return ret


class Session:
    def __init__(self, mainscreen: curses._CursesWindow, text_data: SessionTextObject) -> None:
        self.screen = mainscreen
        self.text = text_data
        self.t_start = time.time()

        self.border = None

        self.wpm_call = lambda: f"{(len(self.text.typed)/CHARACTERS_PER_WORD) / ((time.time()-self.t_start)/60):.1f}"
        self.acc_call = lambda: f"{self.text.get_accuracy():.1f}"
        # TODO: load these values from config
        self.sessionscreen = self.screen.derwin(0, 0)  # init sessionwindow
        self.sessionscreen.keypad(True)  # Fix arrow keys
        self.wpmscreen = None
        self.accscreen = None
        self.draw_session()

    def draw_session(self):
        """completely redraw session, like after a resize"""
        """
        This actually recreates the windows to avoid a bug: When properly handling moving (and resizing), there is some error (possibly bug).
        When one of the smaller sub windows is too close to the right or bottom edge, an error is raised when adding chars.
        When no chars are added the border is refreshed incorrectly and no error is raised.
        This behavior is reproducable with a minimal setup.
        """
        curses.curs_set(0)
        self.screen.erase()
        logger.debug(f"Drawing session window")
        height, width = self.screen.getmaxyx()
        left, right, top, bottom = BORDER_MARGIN
        subwin_height, subwin_width = (height - top - bottom, width - left - right)
        if subwin_height < 6:
            raise ValueError(f"Window to small to start session: {subwin_height,subwin_width}")
        if subwin_width < 40:
            raise ValueError(f"Window to small to start session: {subwin_height,subwin_width}")
        self.sessionscreen = self.screen.subwin(
            subwin_height,
            subwin_width,
            top,
            left,
        )
        self.sessionscreen.border(*self.border) if self.border else self.sessionscreen.border()
        self.sessionscreen.noutrefresh()
        # logger.debug(f"Resize subwindow: maxsize={self.screen.getmaxyx()} actualsize={height-top-bottom,width-left-right}\tborders: left={left}, right={right}, top={top}, bottom={bottom}")
        # TODO: move this routine to the same function as the sessionscreen resize/move routine
        wpm_y = (
            WPM_WINDOW.window_spacing.top
            if WPM_WINDOW.window_spacing.top is not None
            else self.screen.getmaxyx()[0] - WPM_WINDOW.nlines - WPM_WINDOW.window_spacing.bottom
        )
        wpm_x = (
            WPM_WINDOW.window_spacing.left
            if WPM_WINDOW.window_spacing.left is not None
            else self.screen.getmaxyx()[1] - WPM_WINDOW.ncols - WPM_WINDOW.window_spacing.right
        )
        acc_y = (
            ACC_WINDOW.window_spacing.top
            if ACC_WINDOW.window_spacing.top is not None
            else self.screen.getmaxyx()[0] - ACC_WINDOW.nlines - ACC_WINDOW.window_spacing.bottom
        )
        acc_x = (
            ACC_WINDOW.window_spacing.left
            if ACC_WINDOW.window_spacing.left is not None
            else self.screen.getmaxyx()[1] - ACC_WINDOW.ncols - ACC_WINDOW.window_spacing.right
        )
        self.wpmscreen = self.screen.subwin(WPM_WINDOW.nlines, WPM_WINDOW.ncols, wpm_y, wpm_x)
        self.wpmscreen.border()
        self.wpmscreen.noutrefresh()
        self.accscreen = self.screen.subwin(ACC_WINDOW.nlines, ACC_WINDOW.ncols, acc_y, acc_x)
        self.accscreen.border()
        self.accscreen.noutrefresh()
        self.screen.refresh()
        self.draw_characters()
        curses.curs_set(1)

    def draw_characters(self):
        """draw guide text, typos and correctly typed chars in their respective colors"""
        self.sessionscreen.erase()
        self.sessionscreen.border()
        y, x = self.sessionscreen.getmaxyx()
        y -= BORDER_PADDING.top+BORDER_PADDING.bottom
        x -= BORDER_PADDING.left+BORDER_PADDING.right


        # Getting the position of the mouse so we no which line to center on
        typed = self.text.get_typed_chars(width=x - 2, correct=True, typos=True)
        line = len([x for x in typed if x != []]) - 1
        c = len([x for x in typed[line] if x != ""]) + BORDER_PADDING.left

        # Keep track of last printed correct/incorrect char for cursor position
        # +1 are needed to compensate for the border arround the window
        curs_y_base, curs_x_base = (1+BORDER_PADDING.top,1+BORDER_PADDING.left)
        curs_y, curs_x = (1, 1)
        # Print base 'guide' chars
        # FIX: this is ugly as fuck! how do i reformat this?
        guide_chars = fix_height(
            self.text.get_guide_chars(width=x - 2),
            focus_line=line,
            height=y - 2,
            replace_top=[""],
            replace_bottom=["v", "v", "v"],
        )
        for i, l in enumerate(guide_chars):
            self.sessionscreen.addstr(i + curs_y_base, curs_x_base, "".join(l))

        # print correct chars
        correct_chars = fix_height(
            self.text.get_typed_chars(width=x - 2, correct=True),
            focus_line=line,
            height=y - 2,
            replace_top=["^", "^", "^"],
        )
        for iy, l in enumerate(correct_chars, start=BORDER_PADDING.top):
            for ix, c in enumerate(l, start=BORDER_PADDING.left):
                if c:
                    if iy + curs_y_base > curs_y:
                        # INFO: +1 is propably border width?
                        curs_y = iy + 1
                        curs_x = 1
                    curs_x = ix + 2 if ix + 2 > curs_x and iy + 1 >= curs_y else curs_x
                    self.sessionscreen.addch(iy + 1, ix + 1, c, curses.color_pair(2) | curses.A_ITALIC)
        # print typos
        typo_chars = fix_height(self.text.get_typed_chars(width=x - 2, correct=False), focus_line=line, height=y - 2)
        for iy, l in enumerate(typo_chars, start=BORDER_PADDING.top):
            for ix, c in enumerate(l, start=BORDER_PADDING.left):
                if c:
                    if iy + 1 > curs_y:
                        curs_y = iy + 1
                        curs_x = 1
                    curs_x = ix + 2 if ix + 2 > curs_x and iy + 1 >= curs_y else curs_x
                    self.sessionscreen.addch(iy + 1, ix + 1, c, curses.color_pair(3) | curses.A_UNDERLINE)
        self.sessionscreen.noutrefresh()

        # Routine for wpm and accuracy
        # TODO: there is definitely unnecessary redundancy here

        self.wpmscreen.addstr(1, 1, self.wpm_call())
        self.wpmscreen.noutrefresh()
        self.accscreen.addstr(1, 1, self.acc_call())
        self.accscreen.noutrefresh()
        curses.doupdate()
        self.sessionscreen.move(curs_y, curs_x)


def init_main_screen() -> curses._CursesWindow:
    # curses.setupterm('xterm-kitty')
    curses.set_escdelay(5)  # wait 10 msec on esc to distinguish between esc and esc-sequence
    screen = curses.initscr()
    curses.noecho()
    curses.raw()
    curses.cbreak()
    if curses.has_colors():
        curses.start_color()
    # curses.mousemask(curses.BUTTON1_CLICKED)
    screen.keypad(True)
    curses.curs_set(0)

    curses.use_default_colors()
    curses.init_pair(1, -1, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    C_NORMAL = curses.color_pair(1)
    C_GREEN = curses.color_pair(2)
    C_RED = curses.color_pair(3)
    return screen


def main():
    screen = None
    try:
        # curses.setupterm('alacritty')  # no need to set this up!
        logger.info(f"Starting main function")
        logger.info(f"TERM={os.environ['TERM']}")

        screen = init_main_screen()
        text_data = SessionTextObject(teststring)  # init sessiondata
        assert isinstance(screen, curses.window)
        session = Session(screen, text_data)
        start = time.time()

        while True:
            # FIX: this is the input handling, this MUST be compartmentalized!!
            try:
                # set halfdelay, aka timeout mode and reset immediately after
                # timeout is needed, if we block until next input timer can't update
                curses.halfdelay(5)
                inp_char = session.sessionscreen.get_wch()
                curses.nocbreak()
                curses.cbreak()
            except curses.error:
                # this updates wpm
                session.draw_characters()
                continue
            inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
            # curses.KEY_RESIZE get's send when ever the screen resizes
            if inp_key == curses.KEY_RESIZE:
                # redraw screen
                logger.debug("Redraw due to resize")
                session.draw_session()
            elif inp_key == curses.KEY_MOUSE:
                # these can translate to scroll-down and scroll-up, requires mousemask
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
                if inp_key == curses.KEY_UP:
                    logger.debug("Got arrow key: Up")
                elif inp_key == curses.KEY_DOWN:
                    logger.debug("Got arrow key: Down")
                elif inp_key == curses.KEY_LEFT:
                    logger.debug("Got arrow key: Left")
                elif inp_key == curses.KEY_RIGHT:
                    logger.debug("Got arrow key: Right")
            elif inp_key == 27:
                # ESC key
                logger.debug(f"Got esc event inp_char,inp_key{inp_char, inp_key},{curses.ungetch(inp_char)}")
                curses.endwin()
                break
            elif inp_key == curses.KEY_BACKSPACE or inp_key == 127 or str(inp_char) == "^?":
                # elif inp_key in [curses.KEY_BACKSPACE, '\b', '\x7f']:
                text_data.type_backspace()
                session.draw_characters()
            elif inp_char in VALID_INPUTS:
                assert isinstance(inp_char, str)
                text_data.type_char(inp_char)
                session.draw_characters()
            else:
                logger.info(f"Received unknown keypress: {inp_key}, {repr(inp_char)}")

    finally:
        if screen is not None:
            curses.nocbreak()
            curses.echo()
            curses.endwin()


if __name__ == "__main__":
    main()
