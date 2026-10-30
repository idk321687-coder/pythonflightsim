import re, io, sys
text = io.open("hello.html", "r", encoding="utf-8", errors="replace").read()
pattern, before, after = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 1
for m in list(re.finditer(pattern, text))[:limit]:
    s = max(0, m.start() - before)
    print("=== %s @ %d" % (pattern, m.start()))
    print(text[s:m.start() + after])
