import curses


def foo(scr):
    assert isinstance(scr, curses.window)
    scr.box()
    scrx = scr.getmaxyx()[1]
    scr2 = scr.subwin(5, 5, 4, (scrx - 4) // 2)
    scr2.box()
    scr.refresh()

    while True:
        ch = scr.getch()
        if ch == curses.KEY_RESIZE:
            scr.clear()
            scr.box()
            scrx = scr.getmaxyx()[1]
            scr2 = scr.subwin(5, 5, 4, (scrx - 4) // 2)
            scr2.box()
            scr.refresh()


if __name__ == "__main__":
    curses.wrapper(foo)
