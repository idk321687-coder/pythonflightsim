import io

def patch(path, pairs):
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        if text.count(old) != 1:
            raise SystemExit("expected exactly one match in %s for: %s (found %d)" % (path, old[:70], text.count(old)))
        text = text.replace(old, new.replace("\n", nl))
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)

ind = " " * 24
patch("cesium_backend/osm_scene.py", [
    ("MAX_WORLDCOVER_TREES: Final[int] = 2_500", "MAX_WORLDCOVER_TREES: Final[int] = 6_000"),
    ("candidates: list[tuple[int, float, float]] = []", "candidates: list[tuple[float, float, float]] = []"),
    (
        "candidates.append((_stable_rank(sample_lat, sample_lon), sample_lat, sample_lon))",
        "# Bias the cap toward the aircraft: nearby forest is dense, the far edge thins out.\n"
        + ind + "metres_x = (sample_lon - longitude) * 111_320.0 * max(0.15, math.cos(math.radians(latitude)))\n"
        + ind + "metres_y = (sample_lat - latitude) * 111_320.0\n"
        + ind + "distance_fraction = min(1.5, math.hypot(metres_x, metres_y) / max(radius_m, 1.0))\n"
        + ind + "random_fraction = _stable_rank(sample_lat, sample_lon) / 0x7FFFFFFF\n"
        + ind + "candidates.append((random_fraction * (0.3 + distance_fraction), sample_lat, sample_lon))",
    ),
])

patch("hello.html", [
    (
        "distanceDisplayCondition:new Cesium.DistanceDisplayCondition(0,10000)}});treeCount++;}for(const area of scene.forest)",
        "distanceDisplayCondition:new Cesium.DistanceDisplayCondition(0,item.source==='esa_worldcover_2021_tree_cover'?4500:10000)}});treeCount++;}for(const area of scene.forest)",
    ),
])
print("patched")
