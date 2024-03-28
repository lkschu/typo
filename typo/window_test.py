import curses
import time





def init():
    curses.set_escdelay(5)  # wait 10 msec on esc to distinguish between esc and esc-sequence
    screen = curses.initscr()
    curses.noecho()
    curses.raw()
    curses.cbreak()
    if curses.has_colors():
        curses.start_color()
    screen.keypad(True)
    curses.curs_set(0)
    curses.use_default_colors()
    return screen

def draw_windows(screen: curses.window, win_center: curses.window,win_left: curses.window,win_right: curses.window):
    screen.erase()
    win_center.erase()
    win_right.erase()
    win_left.erase()
    y,x = screen.getmaxyx()
    #curses.resizeterm(y,x)
    win_center.resize(y-5-6,x-4-4) # center window should keep 4 char space to left/right and 5/6 to top/bottom
    win_center.mvwin(5,4)
    win_right.mvwin(0,x-3)
    win_left.mvwin(0,0)
    win_center.clear()
    win_left.clear()
    win_right.clear()
    screen.clear()
    screen.noutrefresh()
    win_center.border()
    win_center.noutrefresh()
    curses.doupdate()
    win_right.border()
    win_right.addch(1,1,'R')
    win_right.noutrefresh()
    win_left.border()
    win_left.addch(1,1,'L')
    win_left.noutrefresh()
    curses.doupdate()

def recreate_windows(screen:curses.window,win_center:curses.window,win_left:curses.window,win_right:curses.window):
    screen.erase()
    y,x = screen.getmaxyx()
    win_center = screen.subwin(y-5-6,x-4-4,5,4)
    win_center.border()
    win_center.noutrefresh()
    win_right = screen.subwin(3,3,0,x-3)
    win_right.border()
    win_right.noutrefresh()
    win_left = screen.subwin(3,3,0,0)
    win_left.border()
    win_left.noutrefresh()
    win_center.addstr(1,1,"asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf")
    win_right.addch(1,1,'R')
    win_left.addch(1,1,'L')
    screen.refresh()

    return (screen,win_center,win_left,win_right)



if __name__ == "__main__":
    screen = init()
    y,x = screen.getmaxyx()
    win_center = screen.subwin(y-5-6,x-4-4,5,4)
    win_center.border()
    win_right = screen.subwin(3,3,0,x-3)
    win_right.border()
    win_left = screen.subwin(3,3,0,0)
    win_left.border()
    screen.refresh()
    screen,win_center,win_right,win_left = recreate_windows(screen,win_center,win_left,win_right)

    # while True:
    #     time.sleep(0.001)
    #     draw_windows(screen,win_center,win_left,win_right)

    while True:
        try:
            # set halfdelay, aka timeout mode and reset immediately after
            # timeout is needed, if we block until next input timer can't update
            curses.halfdelay(5)
            inp_char = screen.get_wch()
            curses.nocbreak()
            curses.cbreak()
        except curses.error:
            # this updates wpm
            continue
        inp_key = ord(inp_char) if isinstance(inp_char, str) else inp_char
        if inp_key == curses.KEY_RESIZE:
            # redraw screen
            #draw_windows(screen,win_center,win_left,win_right)
            screen, win_center, win_left,win_right = recreate_windows(screen,win_center,win_left,win_right)
    time.sleep(2)
