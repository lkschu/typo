llst1 = [
    ["abc", " ", "def", " ", "ga"],
    ["xyz", " ", "que", " ", "oas", " ", "ao"],
    ["aoi"],
]
clst1 = [c for c in "abc def gaxyz que oas aoaoi"]
clst2 = [c for c in "abc fed aaxyz que oas aoaoi"]
ctrue = "v"
cfalse = "x"


def correct(llst, clst):
    check = []
    lx, ly = 0, 0
    currentline = "".join(llst[ly])
    for char in clst:
        if len(currentline) <= lx:
            lx, ly = 0, ly + 1
            currentline = "".join(llst[ly])
        if char == currentline[lx]:
            check.append(ctrue)
        else:
            check.append(cfalse)
        lx += 1
    return check


print(correct(llst1, clst1))
print(correct(llst1, clst2))
