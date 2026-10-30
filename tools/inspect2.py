import re, io
text = io.open("hello.html", "r", encoding="utf-8", errors="replace").read()
print("LEN", len(text))
def show(pattern, before=80, after=700, limit=2):
    for m in list(re.finditer(pattern, text))[:limit]:
        s = max(0, m.start() - before)
        print("=== %s @ %d" % (pattern, m.start()))
        print(text[s:m.start() + after])
show(r"function beginFlight", 0, 900)
show(r"function stepFlight|function updateFlight|function physics|function simulate", 0, 2600)
show(r"aircraft\s*=\s*viewer\.entities", 0, 900)
show(r"function toggleBuildings", 0, 700)
show(r"ionBuildingsTileset", 0, 300, 1)
show(r"function refreshAirports", 0, 900)
show(r"const flight\s*=|flight\s*=\s*\{", 0, 700)
show(r"id=\"start|class=\"start|id=\"intro|id=\"loading", 0, 1200)
show(r"baseLayer|ImageryLayer|UrlTemplateImageryProvider", 80, 400, 4)
show(r"function setFollow", 0, 500)
