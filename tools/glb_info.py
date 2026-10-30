import io, json, struct, sys, glob
for path in sys.argv[1:]:
    data = io.open(path, "rb").read()
    length = struct.unpack("<I", data[12:16])[0]
    doc = json.loads(data[20:20 + length].decode("utf-8"))
    mats = [(m.get("name"), m.get("alphaMode", "OPAQUE"), m.get("doubleSided", False)) for m in doc.get("materials", [])]
    print(path, "materials:", mats, "extensions:", doc.get("extensionsUsed"))
