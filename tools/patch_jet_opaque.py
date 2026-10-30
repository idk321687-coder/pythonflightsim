"""Make every material of the player jet explicitly opaque (the canopy was alpha 0.95)."""

import json
import shutil
import struct
import sys
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "static" / "models" / "supersonic_jet.glb"
data = path.read_bytes()
magic, version, _total = struct.unpack("<4sII", data[:12])
json_len, json_type = struct.unpack("<II", data[12:20])
assert json_type == 0x4E4F534A, "first chunk is not JSON"
doc = json.loads(data[20:20 + json_len])
changed = False
for material in doc.get("materials", []):
    pbr = material.setdefault("pbrMetallicRoughness", {})
    base = pbr.get("baseColorFactor")
    if base and base[3] != 1.0:
        base[3] = 1.0
        changed = True
    if material.get("alphaMode") != "OPAQUE":
        material["alphaMode"] = "OPAQUE"
        changed = True
if not changed:
    print("jet already opaque")
    sys.exit(0)
body = json.dumps(doc, separators=(",", ":")).encode("utf-8")
body += b" " * (-len(body) % 4)
rest = data[20 + json_len:]
out = struct.pack("<4sII", magic, version, 12 + 8 + len(body) + len(rest)) + struct.pack("<II", len(body), json_type) + body + rest
shutil.copy(path, path.with_suffix(".glb.bak"))
path.write_bytes(out)
print("jet materials set to OPAQUE")
