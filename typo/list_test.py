liste = list(range(8))


def fix_height(l, h, pos, top=None, bottom=None):
    if pos <= (h - 1) // 2:
        ret = l[:h]
        if bottom:
            ret[h - 1] = bottom
        return ret
    elif pos > len(l) - 1 - (h - (h % 2)) // 2:
        ret = l[-h:]
        if top:
            ret[0] = top
        return ret
    ret = l[pos - (h - 1) // 2 : pos + (h - (h % 2)) // 2 + 1]
    if top:
        ret[0] = top
    if bottom:
        ret[h - 1] = bottom
    return ret


if __name__ == "__main__":
    for i in range(8):
        [print(l) for l in fix_height([str(x) for x in liste], 5, i)]
        print("")
