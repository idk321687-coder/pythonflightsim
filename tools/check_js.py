import io, re, subprocess
text = io.open("hello.html", "r", encoding="utf-8", errors="replace").read()
scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", text, re.S)
print("inline scripts:", len(scripts))
code = max(scripts, key=len)
io.open("tools/_hello_check.js", "w", encoding="utf-8").write(code)
r = subprocess.run(["node", "--check", "tools/_hello_check.js"], capture_output=True, text=True)
print("node exit", r.returncode)
print(r.stderr[:1500])
for key in ["farTrees", "loadFarTrees", "esaKept"]:
    print(key, text.count(key))
