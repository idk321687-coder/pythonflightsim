import re, io
text = io.open("hello.html", "r", encoding="utf-8", errors="replace").read()
def show(pattern, before=60, after=900, limit=1):
    for m in list(re.finditer(pattern, text))[:limit]:
        s = max(0, m.start() - before)
        print("=== %s @ %d" % (pattern, m.start()))
        print(text[s:m.start() + after])
show(r'id="welcome"', 100, 1800)
show(r"const flight=|let flight=|flight=\{", 20, 600)
show(r"function flightPosition", 0, 600)
show(r"function flightOrientation", 0, 500)
show(r"addImageryProvider|ImageryLayer\.|baseLayer\.|UrlTemplateImageryProvider|ArcGis", 150, 500, 3)
show(r"POSITIONED", 700, 200)
show(r"function footprintPositions", 0, 100)
show(r"hasIon", 0, 400)
show(r"<style>", 0, 200)
show(r"\.hidden", 0, 200)
show(r"id=\"airport-search", 0, 500)
