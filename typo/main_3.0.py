from __future__ import annotations
from collections import namedtuple
from dataclasses import dataclass, asdict
from re import sub
from typing import Type, List, NamedTuple, Union, Optional
from textwrap import wrap

import random

import curses
import curses.textpad


from enum import Enum, auto

from collections import namedtuple
import os
import time
from datetime import timedelta
from typing import Text
import yaml
from pathlib import Path

import locale
import logging

from dataclasses import dataclass, asdict, replace

# from pyfiglet import Figlet


@dataclass(frozen=True)
class WindowSpacing:
    left: Optional[int | None]
    right: Optional[int | None]
    top: Optional[int | None]
    bottom: Optional[int | None]

    def __iter__(self):
        return iter((self.left, self.right, self.top, self.bottom))


@dataclass(frozen=True)
class WindowDimensions:
    """Used for wpm,accuracy etc.; one of each: horizontal and vertical spacing must be set"""

    active: bool
    nlines: int
    ncols: int
    window_spacing: WindowSpacing


# deprecated
# @dataclass(frozen=True)
# class BorderChars:
#     left: Optional[str | None]
#     right: Optional[str | None]
#     top: Optional[str | None]
#     bottom: Optional[str | None]
#     topleft: Optional[str | None]
#     topright: Optional[str | None]
#     bottomleft: Optional[str | None]
#     bottomright: Optional[str | None]


@dataclass(frozen=True)
class ColorScheme:
    def __init__(
        self,
        fg: tuple[int, int],
        correct: tuple[int, int],
        wrong: tuple[int, int],
        border: tuple[int, int],
        accent: tuple[int, int],
    ) -> None:
        curses.use_default_colors()
        curses.init_pair(1, *fg)
        curses.init_pair(2, *correct)
        curses.init_pair(3, *wrong)
        curses.init_pair(4, *border)
        curses.init_pair(5, *accent)

    @property
    def fg(self):
        return curses.color_pair(1)

    @property
    def correct(self):
        return curses.color_pair(2)

    @property
    def wrong(self):
        return curses.color_pair(3)

    @property
    def border(self):
        return curses.color_pair(4)

    @property
    def accent(self):
        return curses.color_pair(5)

    @classmethod
    def default(cls):
        return ColorScheme(
            fg=(-1, -1),  # default
            correct=(curses.COLOR_GREEN, -1),
            wrong=(curses.COLOR_RED, -1),
            border=(-1, -1),
            accent=(curses.COLOR_YELLOW, -1),
        )


@dataclass()
class SessionSettings:
    VALID_INPUTS: str
    S_SPACE: str
    S_RETURN: str
    S_TAB: str
    BORDER_MARGIN: WindowSpacing
    BORDER_PADDING: WindowSpacing
    WPM_WINDOW: WindowDimensions
    ACC_WINDOW: WindowDimensions
    COLOR_SCHEME: Optional[ColorScheme]
    MAX_WIDTH: int

    @property
    def replacements(self):
        return {"\n": self.S_RETURN, "\t": self.S_TAB + "·" * 3}

    @classmethod
    def default(cls):
        valid_inputs = "abcdefghijklmnopqrstuvwxyz"
        valid_inputs += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        valid_inputs += " "
        valid_inputs += "1234567890"
        valid_inputs += "äüöÄÜÖß"
        valid_inputs += ",.;:><?"
        valid_inputs += "§~_+=-`€°!@#$%^&*()[]{}|/\\'\""
        valid_inputs += "\n\t"
        border_margin = WindowSpacing(left=4, right=4, top=5, bottom=6)
        border_padding = WindowSpacing(left=3, right=3, top=1, bottom=1)
        wpm_window = WindowDimensions(active=True, nlines=3, ncols=9, window_spacing=WindowSpacing(left=None, right=1, top=1, bottom=None))
        acc_window = WindowDimensions(active=True, nlines=3, ncols=9, window_spacing=WindowSpacing(left=None, right=1, top=None, bottom=1))

        return SessionSettings(
            VALID_INPUTS=valid_inputs,
            S_SPACE="_",
            S_RETURN="⏎",
            S_TAB="↹",
            BORDER_MARGIN=border_margin,
            BORDER_PADDING=border_padding,
            WPM_WINDOW=wpm_window,
            ACC_WINDOW=acc_window,
            COLOR_SCHEME=None,  # TODO: not none
            MAX_WIDTH=120,
        )


CONFIG = SessionSettings.default()

# window_information = namedtuple("window_information", ["window", "callback"])

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


teststring = 'Mr. Stubb," said I, turning to that worthy, who, buttoned up in his oil-jacket, was now calmly smoking his pipe in the rain; '
teststring += '"Mr. Stubb, I think I have heard you say that of all whalemen you ever met, our chief mate, Mr. Starbuck, is by far the most careful and prudent.'
# teststring += '\nI suppose then, that going plump on a flying whale with your sail set in a foggy squall is the height of a whaleman\'s discretion?'
# teststring += "\n\n" + teststring


B_DOUBLE = ("║", "║", "═", "═", "╔", "╗", "╚", "╝")


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
        self.replacements = CONFIG.replacements

        self.typed = []  # simple char buffer
        self.corrected_errors = []

    def is_complete(self):
        if len(self.typed) == len(self.raw_text):
            return True
        else:
            return False

    def replace(self, s: str) -> str:
        """handle default keys for the replacements dict"""
        return s if s not in self.replacements.keys() else self.replacements[s]

    def display_mode(self) -> str:
        """replace some symbols (like newline) for displaying in terminal"""
        buf = self.raw_text
        for k, v in self.replacements.items():
            buf = buf.replace(k, v)
        return buf

    def completed_chars(self) -> List[str]:
        complete = self.get_typed_chars(256, correct=True, typos=True)
        complete = [x for c in complete for x in c]
        return complete

    def correct_chars(self) -> List[str]:
        correct = self.get_typed_chars(256, correct=True, typos=False)
        correct = [x for c in correct for x in c]
        return correct

    def get_accuracy(self) -> float:
        """return accuracy of typed characters"""
        complete = self.completed_chars()
        correct = self.correct_chars()
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
            if len(current_lst) > 1 and (current_lst[-1] == self.replace(" ") and current_lst[-2] == self.replace("\n")):
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


class ConfigConformScreenWrp:
    def __init__(self, parent: curses._CursesWindow, config: SessionSettings) -> None:
        self.parent = parent
        self.config = config
        height, width = parent.getmaxyx()
        left, right, top, bottom = config.BORDER_MARGIN
        subwin_height, subwin_width = (height - top - bottom, width - left - right)
        if subwin_height < 6:
            raise ValueError(f"Window to small to start session: {subwin_height,subwin_width}")
        if subwin_width < 40:
            raise ValueError(f"Window to small to start session: {subwin_height,subwin_width}")
        self.screen = parent.subwin(
            subwin_height,
            subwin_width,
            top,
            left,
        )
        self.screen.attrset(config.COLOR_SCHEME.border)
        self.screen.border()
        self.screen.attrset(config.COLOR_SCHEME.fg)

    def redraw_border(self):
        self.screen.erase()
        self.screen.attrset(self.config.COLOR_SCHEME.border)
        self.screen.border()
        self.screen.attrset(self.config.COLOR_SCHEME.fg)

    def getoffsetyx(self):
        y = self.config.BORDER_PADDING.top + 1
        x = self.config.BORDER_PADDING.left + 1
        return y, x

    def getmaxyx(self):
        y, x = self.screen.getmaxyx()
        y -= self.config.BORDER_PADDING.top + self.config.BORDER_PADDING.bottom
        x -= self.config.BORDER_PADDING.left + self.config.BORDER_PADDING.right
        return y, x

    def addstr(self, s: str, i: int = 0, attr: int = 0):
        y, x = self.getoffsetyx()
        self.screen.addstr(y + i, x, s, attr)


# def config_conform_sessionscreen(parent: curses._CursesWindow):


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


@dataclass()
class SessionOptions:
    RandomShuffle: bool

    @staticmethod
    def load_from_dict(d) -> SessionOptions:
        return SessionOptions(RandomShuffle=d["RandomShuffle"])


@dataclass()
class SessionFileRepr:
    """Representation of a session, is read from file"""

    title: str
    options: SessionOptions
    sections: List[str]

    @staticmethod
    def load_from_file(path) -> SessionFileRepr:
        r = yaml.safe_load(Path(path).read_text())
        # TODO: any input validation
        srepr = SessionFileRepr(title=r["title"], options=SessionOptions.load_from_dict(r["options"]), sections=r["sections"])
        if srepr.options.RandomShuffle:
            random.shuffle(srepr.sections)
        return srepr


class Session:
    def __init__(self, mainscreen: curses._CursesWindow, sessionrepr: SessionFileRepr) -> None:
        self.screen = mainscreen
        self.sessionrepr = sessionrepr
        self.section_nr = 0
        self.text = SessionTextObject(sessionrepr.sections[self.section_nr])
        self.len_typed_carryover = 0
        self.acc_typed_carryover = []
        self.t_start = time.time()

        self.border = None

        self.wpm_call = lambda: f"{self.calc_wpm():.1f}"
        self.acc_call = lambda: f"{self.calc_acc():.1f}"
        # self.sessionscreen = self.screen.derwin(0, 0)  # init sessionwindow
        self.sessionscreen = ConfigConformScreenWrp(mainscreen, CONFIG)
        self.sessionscreen.screen.keypad(True)  # Fix arrow keys
        self.wpmscreen = None
        self.accscreen = None
        self.draw_session()

    def calc_wpm(self) -> float:
        sum_typed = self.len_typed_carryover + len(self.text.typed)
        return (sum_typed / CHARACTERS_PER_WORD) / ((time.time() - self.t_start) / 60)

    def calc_acc(self) -> float:
        # TODO: is this really the correct calculation?
        curr_len = len(self.text.completed_chars())
        curr_len = max([curr_len, 1])
        sum_len = curr_len
        avg_acc = self.text.get_accuracy() * curr_len
        for a, l in self.acc_typed_carryover:
            sum_len += l
            avg_acc += a * l
        return avg_acc / sum_len

    def is_complete(self):
        return self.text.is_complete()

    def type_backspace(self):
        self.text.type_backspace()

    def type_char(self, c):
        self.text.type_char(c)

    def next_section(self):
        # TODO: save accuracy and wpm from self.text for later
        self.section_nr += 1
        if len(self.sessionrepr.sections) <= self.section_nr:
            raise ValueError(f"DONE\nrepr{ len(self.sessionrepr.sections) } \t nr {self.section_nr}\n{self.sessionrepr.sections}")
        len_typed = len(self.text.completed_chars())
        self.len_typed_carryover += len_typed
        self.acc_typed_carryover.append((self.text.get_accuracy(), len_typed))
        self.text = SessionTextObject(self.sessionrepr.sections[self.section_nr])

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
        self.sessionscreen = ConfigConformScreenWrp(parent=self.screen, config=CONFIG)

        # TODO: move this routine to the same function as the sessionscreen resize/move routine
        assert isinstance(CONFIG.WPM_WINDOW.window_spacing.bottom, int)
        assert isinstance(CONFIG.WPM_WINDOW.window_spacing.right, int)
        assert isinstance(CONFIG.ACC_WINDOW.window_spacing.bottom, int)
        assert isinstance(CONFIG.ACC_WINDOW.window_spacing.right, int)
        assert isinstance(CONFIG.COLOR_SCHEME, ColorScheme)
        wpm_y = (
            CONFIG.WPM_WINDOW.window_spacing.top
            if CONFIG.WPM_WINDOW.window_spacing.top is not None
            else self.screen.getmaxyx()[0] - CONFIG.WPM_WINDOW.nlines - CONFIG.WPM_WINDOW.window_spacing.bottom
        )
        wpm_x = (
            CONFIG.WPM_WINDOW.window_spacing.left
            if CONFIG.WPM_WINDOW.window_spacing.left is not None
            else self.screen.getmaxyx()[1] - CONFIG.WPM_WINDOW.ncols - CONFIG.WPM_WINDOW.window_spacing.right
        )
        acc_y = (
            CONFIG.ACC_WINDOW.window_spacing.top
            if CONFIG.ACC_WINDOW.window_spacing.top is not None
            else self.screen.getmaxyx()[0] - CONFIG.ACC_WINDOW.nlines - CONFIG.ACC_WINDOW.window_spacing.bottom
        )
        acc_x = (
            CONFIG.ACC_WINDOW.window_spacing.left
            if CONFIG.ACC_WINDOW.window_spacing.left is not None
            else self.screen.getmaxyx()[1] - CONFIG.ACC_WINDOW.ncols - CONFIG.ACC_WINDOW.window_spacing.right
        )
        self.wpmscreen = self.screen.subwin(CONFIG.WPM_WINDOW.nlines, CONFIG.WPM_WINDOW.ncols, wpm_y, wpm_x)
        self.wpmscreen.attrset(CONFIG.COLOR_SCHEME.accent)
        self.wpmscreen.border()
        self.wpmscreen.noutrefresh()
        self.wpmscreen.attrset(CONFIG.COLOR_SCHEME.fg)
        self.accscreen = self.screen.subwin(CONFIG.ACC_WINDOW.nlines, CONFIG.ACC_WINDOW.ncols, acc_y, acc_x)
        self.accscreen.attrset(CONFIG.COLOR_SCHEME.accent)
        self.accscreen.border()
        self.accscreen.noutrefresh()
        self.accscreen.attrset(CONFIG.COLOR_SCHEME.fg)
        self.screen.refresh()
        self.draw_characters()
        curses.curs_set(1)

    def draw_characters(self):
        """draw guide text, typos and correctly typed chars in their respective colors"""
        self.sessionscreen.redraw_border()
        y, x = self.sessionscreen.getmaxyx()

        # Getting the position of the mouse so we know which line to center on
        typed = self.text.get_typed_chars(width=x - 2, correct=True, typos=True)
        line = len([x for x in typed if x != []]) - 1
        c = len([x for x in typed[line] if x != ""]) + CONFIG.BORDER_PADDING.left

        # Keep track of last printed correct/incorrect char for cursor position
        # +1 are needed to compensate for the border arround the window
        curs_y_base, curs_x_base = (1 + CONFIG.BORDER_PADDING.top, 1 + CONFIG.BORDER_PADDING.left)
        curs_y, curs_x = (1 + CONFIG.BORDER_PADDING.top, 1 + CONFIG.BORDER_PADDING.left)

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
            self.sessionscreen.screen.addstr(i + curs_y_base, curs_x_base, "".join(l))

        # print correct chars
        correct_chars = fix_height(
            self.text.get_typed_chars(width=x - 2, correct=True),
            focus_line=line,
            height=y - 2,
            replace_top=["^", "^", "^"],
        )
        for iy, l in enumerate(correct_chars, start=CONFIG.BORDER_PADDING.top):
            for ix, c in enumerate(l, start=CONFIG.BORDER_PADDING.left):
                if c:
                    if iy + curs_y_base > curs_y:
                        # INFO: +1 is propably border width?
                        curs_y = iy + 1
                        curs_x = 1
                    curs_x = ix + 2 if ix + 2 > curs_x and iy + 1 >= curs_y else curs_x
                    self.sessionscreen.screen.addch(iy + 1, ix + 1, c, CONFIG.COLOR_SCHEME.correct | curses.A_ITALIC)

        # print typos
        typo_chars = fix_height(self.text.get_typed_chars(width=x - 2, correct=False), focus_line=line, height=y - 2)
        for iy, l in enumerate(typo_chars, start=CONFIG.BORDER_PADDING.top):
            for ix, c in enumerate(l, start=CONFIG.BORDER_PADDING.left):
                if c:
                    if iy + 1 > curs_y:
                        curs_y = iy + 1
                        curs_x = 1
                    curs_x = ix + 2 if ix + 2 > curs_x and iy + 1 >= curs_y else curs_x
                    self.sessionscreen.screen.addch(iy + 1, ix + 1, c, CONFIG.COLOR_SCHEME.wrong | curses.A_UNDERLINE)
        self.sessionscreen.screen.noutrefresh()

        # Routine for wpm and accuracy
        # TODO: there is definitely unnecessary redundancy here

        self.wpmscreen.addstr(1, 1, self.wpm_call())
        self.wpmscreen.noutrefresh()
        self.accscreen.addstr(1, 1, self.acc_call())
        self.accscreen.noutrefresh()
        curses.doupdate()
        self.sessionscreen.screen.move(curs_y, curs_x)


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

    CONFIG.COLOR_SCHEME = ColorScheme.default()
    return screen


def sessionloop(session: Session):

    while True:
        # FIX: this is the input handling, this MUST be compartmentalized!!
        try:
            # set halfdelay, aka timeout mode and reset immediately after
            # timeout is needed, if we block until next input timer can't update
            curses.halfdelay(5)
            inp_char = session.sessionscreen.screen.get_wch()
            curses.nocbreak()
            curses.cbreak()
        except curses.error:
            # this updates wpm
            session.draw_characters()
            continue
        inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
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
            session.type_backspace()
            session.draw_characters()
        elif inp_char in CONFIG.VALID_INPUTS:
            assert isinstance(inp_char, str)
            session.type_char(inp_char)
            if session.is_complete():
                logger.info("Completed xyz")
                session.next_section()
            session.draw_characters()
        else:
            logger.info(f"Received unknown keypress: {inp_key}, {repr(inp_char)}")


def make_menu(parent: curses._CursesWindow, menu_content: List[str]):
    derwin = ConfigConformScreenWrp(parent, CONFIG)
    derwin.addstr("Test")
    parent.noutrefresh()
    parent.refresh()
    derwin.screen.noutrefresh()
    derwin.screen.refresh()
    curses.doupdate()
    time.sleep(5)


def make_grid(parent: curses._CursesWindow, width: int, height: int):
    y, x = parent.getmaxyx()
    if width > x or height > y:
        raise ValueError("Error")
    pos_x = 0
    pos_y = 1

    # redraw all
    while True:
        parent.clear()
        y, x = parent.getmaxyx()

        for p_x in range(pos_x * (x // width), (pos_x + 1) * (x // width)):
            for p_y in range(pos_y * (y // height), (pos_y + 1) * (y // height)):
                parent.addstr(p_y, p_x, "X")
        parent.noutrefresh()
        parent.refresh()

        inp_char = parent.get_wch()
        inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
        curses.nocbreak()
        curses.cbreak()
        if inp_key == curses.KEY_RESIZE:
            continue
        elif inp_key == curses.KEY_DOWN:
            if pos_y < height - 1:
                pos_y += 1
        elif inp_key == curses.KEY_UP:
            if pos_y > 0:
                pos_y -= 1
        elif inp_key == curses.KEY_RIGHT:
            if pos_x < width - 1:
                pos_x += 1
        elif inp_key == curses.KEY_LEFT:
            if pos_x > 0:
                pos_x -= 1


class ViewportGrid:
    def __init__(self, parent: curses._CursesWindow, cell_width: int, cell_height: int, content) -> None:
        assert len(content) > 0
        assert len(content[0]) > 0
        assert all([len(content[0]) == len(content[i]) for i in range(len(content))])  # all elements have equal length
        self.parent = parent
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.content = content
        self.cells_y = len(content)
        self.cells_x = len(content[0])
        if any([x < 1 for x in [self.cell_width, self.cell_height, self.cells_y, self.cells_x]]):
            raise ValueError("Error")

        self.view_max_y, self.view_max_x = parent.getmaxyx()
        self.view_cells_max_y = self.view_max_y // cell_height
        self.view_cells_max_x = self.view_max_x // cell_width

        # top left coordinates of viewport
        self.pos_x = 0
        self.pos_y = 0
        # "cursor" but actually cell numbers
        self.cursor_x = 0
        self.cursor_y = 0
        self.CURSOR_SPACING = 2  # keep border of cells around selected

        self.char_buffer = [[" "] * cell_width * self.cells_x for _ in range(cell_height * self.cells_y)]  # [y][x]
        return

    def refresh_dimensions(self):
        self.view_max_y, self.view_max_x = self.parent.getmaxyx()
        self.view_cells_max_y = self.view_max_y // self.cell_height
        self.view_cells_max_x = self.view_max_x // self.cell_width

    def make_char_buffer(self):
        # create char buffer
        i = 0
        start = time.time()
        logger.debug(f"buffersize:{len(self.char_buffer),len(self.char_buffer[0])}")
        for y in range(self.cells_y):
            for x in range(self.cells_x):
                y_ = y * self.cell_height
                x_ = x * self.cell_width

                content = self.content[y][x]

                # if i % 2 == 0:
                #     content = f"{i}_________________________________________________________________"  # TODO: give content as param
                # else:
                #     content = f"{i}XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # TODO: give content as param

                # prepare content for each cell
                content = wrap(content, self.cell_width)[: self.cell_height]

                # walk through all chars in content, break on oversteping cell limits
                for l_idx in range(self.cell_height):
                    if l_idx >= len(content):
                        # logger.debug(f"break:{l_idx} > len({content})={len(content)}")
                        break
                    for c_idx in range(self.cell_width):
                        if c_idx >= len(content[l_idx]):
                            # logger.debug(f"break:{c_idx} > len({content[l_idx]})={len(content[l_idx])}")
                            break
                        self.char_buffer[y_ + l_idx][x_ + c_idx] = content[l_idx][c_idx]
                i += 1

        logger.info(f"Took {time.time()-start}s")
        # char_buffer_str = "\n".join(["".join(e) for e in char_buffer])
        return

    def next_x_cell_border(self, x_pos: int) -> int:
        ret = 0
        while ret <= x_pos:
            ret += self.cell_width
        return ret

    def next_y_cell_border(self, y_pos: int) -> int:
        ret = 0
        while ret <= y_pos:
            ret += self.cell_height
        return ret

    def draw_char_buffer(self):
        # draw char buffer
        for view_y in range(self.view_max_y - 1):
            if view_y + self.pos_y >= len(self.char_buffer):
                break
            view_x = 0
            current_cell_y = (view_y + self.pos_y) // self.cell_height
            while view_x < self.view_max_x:
                # find next cell border from current position
                current_cell_x = (view_x + self.pos_x) // self.cell_width
                cborder_x = self.next_x_cell_border(view_x + self.pos_x)
                if cborder_x >= self.view_max_x + self.pos_x + self.cell_width:
                    break
                if cborder_x >= self.view_max_x + self.pos_x:
                    cborder_x = self.view_max_x + self.pos_x
                insert_str = "".join(self.char_buffer[view_y + self.pos_y][view_x + self.pos_x : cborder_x])
                if self.cursor_x == current_cell_x and self.cursor_y == current_cell_y:
                    attr = curses.A_STANDOUT
                else:
                    attr = 0
                # logger.debug(f"Trying to add at pos({view_y,view_x}), charbufferpos({view_y+pos_y,view_x+pos_x}) str of len {len(insert_str)}: \"{insert_str}\"")
                try:
                    self.parent.addstr(view_y, view_x, insert_str, attr)
                except curses.error as e:
                    logger.warn(f"Error when adding str len({len(insert_str)}) at pos ({view_y,view_x})")
                    raise e
                assert cborder_x - self.pos_x > view_x
                view_x = cborder_x - self.pos_x
            self.parent.noutrefresh()
            self.parent.refresh()
        return

    def pos_x_change(self, cursor_move: int):
        if cursor_move < -1 or cursor_move > 1:
            return ValueError(f"Can only move by one!")
        if self.cursor_x == self.cells_x:
            return
        # partial cells
        overflow = self.view_max_x - self.view_cells_max_x * self.cell_width

        current_cell_relative_to_view = self.cursor_x - self.pos_x // self.cell_width
        logger.debug(f"Relative cursor(x):{current_cell_relative_to_view}")
        assert current_cell_relative_to_view <= self.view_cells_max_x
        assert current_cell_relative_to_view >= 0

        if cursor_move == 1:
            if current_cell_relative_to_view + self.CURSOR_SPACING >= self.view_cells_max_x:
                # if not all cells fit in the viewport:
                if self.cells_x * self.cell_width - self.view_max_x > 0:
                    self.pos_x = ((self.cursor_x - self.view_cells_max_x) + self.CURSOR_SPACING) * self.cell_width + overflow
                    self.pos_x = min([self.pos_x, self.cells_x * self.cell_width - self.view_max_x])
                else:
                    self.pos_x = 0
                logger.debug(f"Moving viewport({cursor_move}): cursor:{self.cursor_y,self.cursor_x}, new pos_x:{self.pos_x}")
        else:
            if current_cell_relative_to_view - self.CURSOR_SPACING <= 0:
                self.pos_x = (self.cursor_x - self.CURSOR_SPACING) * self.cell_width
                self.pos_x = max([self.pos_x, 0])
                logger.debug(f"Moving viewport({cursor_move}): cursor:{self.cursor_y,self.cursor_x}, new pos_x:{self.pos_x}")

        assert self.pos_x >= 0
        assert self.pos_x < self.cells_x * self.cell_width

    def pos_y_change(self, cursor_move: int):
        if cursor_move < -1 or cursor_move > 1:
            return ValueError(f"Can only move by one!")
        if self.cursor_y == self.cells_y:
            return
        # partial cells
        overflow = self.view_max_y - self.view_cells_max_y * self.cell_height

        current_cell_relative_to_view = self.cursor_y - self.pos_y // self.cell_height
        logger.debug(f"Relative cursor(y):{current_cell_relative_to_view}")
        assert current_cell_relative_to_view <= self.view_cells_max_y
        assert current_cell_relative_to_view >= 0

        if cursor_move == 1:
            if current_cell_relative_to_view + self.CURSOR_SPACING >= self.view_cells_max_y:
                self.pos_y = ((self.cursor_y - self.view_cells_max_y) + self.CURSOR_SPACING) * self.cell_height + overflow
                self.pos_y = min(self.pos_y, self.cells_y * self.cell_height - self.view_max_y)
                logger.debug(f"Moving viewport({cursor_move}): cursor:{self.cursor_y,self.cursor_x}, new pos_y:{self.pos_y}")
        else:
            if current_cell_relative_to_view - self.CURSOR_SPACING <= 0:
                self.pos_y = (self.cursor_y - self.CURSOR_SPACING) * self.cell_height
                self.pos_y = max([self.pos_y, 0])
                logger.debug(f"Moving viewport({cursor_move}): cursor:{self.cursor_y,self.cursor_x}, new pos_y:{self.pos_y}")

        assert self.pos_y >= 0
        assert self.pos_y < self.cells_y * self.cell_height

    def make_viewport_grid(self) -> tuple[int, int]:
        # redraw all
        while True:
            self.parent.clear()
            self.refresh_dimensions()
            logger.debug(f"Screen size: {self.view_max_y,self.view_max_x}")

            self.make_char_buffer()

            self.draw_char_buffer()

            inp_char = self.parent.get_wch()
            inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
            curses.nocbreak()
            curses.cbreak()
            if inp_key == curses.KEY_RESIZE:
                continue
            elif inp_char == "\n":
                break
            elif inp_key == curses.KEY_DOWN:
                if self.cursor_y + 1 < self.cells_y:
                    self.cursor_y += 1
                    self.pos_y_change(1)
            elif inp_key == curses.KEY_UP:
                if self.cursor_y > 0:
                    self.cursor_y -= 1
                    self.pos_y_change(-1)
            elif inp_key == curses.KEY_RIGHT:
                if self.cursor_x + 1 < self.cells_x:
                    self.cursor_x += 1
                    self.pos_x_change(1)
            elif inp_key == curses.KEY_LEFT:
                if self.cursor_x > 0:
                    self.cursor_x -= 1
                    self.pos_x_change(-1)
        return (self.cursor_y, self.cursor_x)


def session_validate(fpath) -> bool:
    return fpath.endswith("yaml") or fpath.endswith("yml")


def main():
    screen = None
    try:
        # curses.setupterm('alacritty')  # no need to set this up!
        logger.info(f"Starting main function")
        logger.info(f"TERM={os.environ['TERM']}")

        screen = init_main_screen()
        assert isinstance(screen, curses.window)

        # make_menu(screen,["1","2","3"])

        # make_grid(screen,15,15)
        # y, x = ViewportGrid(screen, cell_width=9, cell_height=3, cells_y=24, cells_x=21).make_viewport_grid()
        content = [["A"], ["B"], ["C"], ["DDDDDDDDDDDDDDDDDDDDDDDDDD"]]
        content = [[0] * 21] * 32
        content = [[d] for d in os.listdir("./typo/res/")]
        content = []
        basepath = "./typo/res/"
        for p in os.listdir(basepath):
            if os.path.isdir(f"{basepath}/{p}"):
                content.extend([[os.path.abspath(f"{basepath}/{p}/{f}")] for f in os.listdir(f"{basepath}/{p}") if session_validate(f)])
            elif session_validate(p):
                content.append([os.path.abspath(f"{basepath}/{p}")])

        y, x = ViewportGrid(screen, cell_width=128, cell_height=1, content=content).make_viewport_grid()
        logger.critical(f"Got {y,x}")
        # ViewportGrid(screen,cell_width=7,cell_height=3,cells_y=12,cells_x=17).make_viewport_grid()

        testpath = content[y][x]

        session_repr = SessionFileRepr.load_from_file(testpath)
        logger.info(f"Screen size: {screen.getmaxyx()}")
        session = Session(screen, session_repr)
        sessionloop(session)

    finally:
        if screen is not None:
            curses.nocbreak()
            curses.echo()
            curses.endwin()


if __name__ == "__main__":
    main()
