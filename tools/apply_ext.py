"""Inject tools/flight_ext.js into hello.html's simulator closure (safe to re-run)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "hello.html"
EXT = ROOT / "tools" / "flight_ext.js"
BEGIN = "/* >>> SKYLINE_EXT_BEGIN */"
END = "/* <<< SKYLINE_EXT_END */"
ANCHOR = "\n  })();\n  </script>"

BUILDING_OLD = r"""for(const item of scene.buildings){buildingSource.entities.add({id:item.id,name:item.name,polygon:{hierarchy:footprintPositions(item.footprint),height:0,extrudedHeight:item.height_m,perPositionHeight:false,heightReference:Cesium.HeightReference.CLAMP_TO_GROUND,extrudedHeightReference:Cesium.HeightReference.RELATIVE_TO_GROUND,material:Cesium.Color.fromCssColorString('#8ca4ae').withAlpha(.72),outline:false}});}"""
BUILDING_NEW = "for(const item of scene.buildings){window.skylineAddBuilding(item);}"
PLANE_OLD = "minimumPixelSize:48,maximumScale:240,runAnimations:true,incrementallyLoadTextures:true}"
PLANE_NEW = "minimumPixelSize:48,maximumScale:240,runAnimations:true,incrementallyLoadTextures:true,color:Cesium.Color.WHITE}"

text = HTML.read_text(encoding="utf-8")
if BEGIN in text:
    start = text.index(BEGIN)
    end = text.index(END) + len(END)
    text = text[:start].rstrip("\n") + text[end:]
if BUILDING_OLD in text:
    text = text.replace(BUILDING_OLD, BUILDING_NEW, 1)
elif BUILDING_NEW not in text:
    raise SystemExit("building loop not found; hello.html changed unexpectedly")
if PLANE_OLD in text:
    text = text.replace(PLANE_OLD, PLANE_NEW, 1)
assert text.count(ANCHOR) == 1, "closing anchor not found exactly once"
block = f"\n{BEGIN}\n{EXT.read_text(encoding='utf-8')}\n{END}"
text = text.replace(ANCHOR, block + ANCHOR, 1)
HTML.write_text(text, encoding="utf-8")
print("hello.html updated")
