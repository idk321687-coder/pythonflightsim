import re, io
text = io.open("hello.html", "r", encoding="utf-8", errors="replace").read()
print("TAGS:", re.findall(r'<(?:script|link)[^>]*(?:src|href)="[^"]*"', text))
for key in ["sceneCenter", "sceneIsLoading", "const flight", "let flight", "function clamp", "function sceneDistance", "function setStatus", "requestRenderMode", "maximumScreenSpaceError", "scene.fog", "function updatePlane", "const ui="]:
    for m in list(re.finditer(re.escape(key), text))[:2]:
        s = max(0, m.start() - 60)
        print("---", key, "@", m.start())
        print(text[s:m.start() + 260].replace("\n", " "))
