import curses


def main(stdscr):
    win = stdscr.derwin(10, 25, 0, 0)
    while True:
        win.erase()
        stdscr.erase()

        win.box()

        stdscr.refresh()
        win.refresh()

        key = stdscr.getch()
        h, w = win.getmaxyx()
        y, x = win.getbegyx()
        ph, pw = stdscr.getmaxyx()
        if key == curses.KEY_DOWN and y + 1 + h < ph:
            win.mvderwin(y + 1, x)
            win.mvwin(y + 1, x)
        elif key == curses.KEY_UP and y - 1 >= 0:
            win.mvderwin(y - 1, x)
            win.mvwin(y - 1, x)
        elif key == curses.KEY_LEFT and x - 1 >= 0:
            win.mvderwin(y, x - 1)
            win.mvwin(y, x - 1)
        elif key == curses.KEY_RIGHT and x + 1 + w < pw:
            win.mvderwin(y, x + 1)
            win.mvwin(y, x + 1)


if __name__ == "__main__":
    curses.wrapper(main)
