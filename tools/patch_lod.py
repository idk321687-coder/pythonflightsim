import io

def patch(path, pairs):
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    nl = "\r\n" if "\r\n" in text else "\n"
    for old, new in pairs:
        old = old.replace("\n", nl)
        if text.count(old) != 1:
            raise SystemExit("expected exactly one match in %s for: %s (found %d)" % (path, old[:70], text.count(old)))
        text = text.replace(old, new.replace("\n", nl))
    with io.open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)

FAR_FUNC = '''

FAR_MAX_RADIUS_M: Final[float] = 12_000.0
FAR_MAX_POINTS: Final[int] = 30_000
FAR_TARGET_PIXELS: Final[int] = 480


def worldcover_far_tree_points(latitude: float, longitude: float, radius_m: float, max_points: int) -> list[float]:
    """Return a decimated, wide-area set of tree-cover points as a flat [lon, lat, ...] list.

    The window is read at reduced resolution (COG overviews), so a 9 km radius
    costs about the same as a small full-resolution window.
    """
    north_delta = radius_m / 111_320.0
    east_delta = radius_m / (111_320.0 * max(0.15, math.cos(math.radians(latitude))))
    west, east = longitude - east_delta, longitude + east_delta
    south, north = latitude - north_delta, latitude + north_delta
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_TIMEOUT": "25",
        "GDAL_HTTP_MAX_RETRY": "1",
    }
    chunks: list[numpy.ndarray] = []
    opened_any_tile = False
    with rasterio.Env(**options):
        for tile_lat, tile_lon in _worldcover_tile_origins(west, south, east, north):
            url = f"{WORLDCOVER_ROOT}/{_worldcover_filename(tile_lat, tile_lon)}"
            try:
                with rasterio.open(url) as dataset:
                    opened_any_tile = True
                    read_west = max(west, float(dataset.bounds.left))
                    read_east = min(east, float(dataset.bounds.right))
                    read_south = max(south, float(dataset.bounds.bottom))
                    read_north = min(north, float(dataset.bounds.top))
                    if read_west >= read_east or read_south >= read_north:
                        continue
                    window = from_bounds(read_west, read_south, read_east, read_north, dataset.transform)
                    window = window.round_offsets().round_lengths().intersection(Window(0, 0, dataset.width, dataset.height))
                    if window.width <= 0 or window.height <= 0:
                        continue
                    scale = min(1.0, FAR_TARGET_PIXELS / max(window.width, window.height))
                    out_width = max(1, int(window.width * scale))
                    out_height = max(1, int(window.height * scale))
                    classes = dataset.read(1, window=window, out_shape=(out_height, out_width), resampling=Resampling.nearest)
                    rows, columns = numpy.nonzero(classes == 10)
                    if rows.size == 0:
                        continue
                    rows = rows.astype(numpy.int64)
                    columns = columns.astype(numpy.int64)
                    transform = dataset.window_transform(window)
                    step_x = window.width / out_width
                    step_y = window.height / out_height
                    jitter_x = 0.15 + 0.7 * (((rows * 73_856_093) ^ (columns * 19_349_663) ^ 19) & 0xFFFF) / 0xFFFF
                    jitter_y = 0.15 + 0.7 * (((rows * 73_856_093) ^ (columns * 19_349_663) ^ 73) & 0xFFFF) / 0xFFFF
                    lons = transform.c + (columns + jitter_x) * step_x * transform.a
                    lats = transform.f + (rows + jitter_y) * step_y * transform.e
                    chunks.append(numpy.stack((lons, lats), axis=1))
            except RasterioIOError:
                continue
    if not opened_any_tile:
        raise RasterioIOError("No ESA WorldCover tile was available")
    if not chunks:
        return []
    points = numpy.concatenate(chunks)
    if len(points) > max_points:
        rng = numpy.random.default_rng(int(abs(latitude) * 1000) ^ int(abs(longitude) * 1000))
        points = points[rng.choice(len(points), size=max_points, replace=False)]
    return numpy.round(points, 5).ravel().tolist()
'''

FAR_METHOD = '''    def far_trees(self, latitude: float, longitude: float, radius_m: float = 9_000.0, max_points: int = 25_000) -> dict[str, object]:
        radius_m = max(1_000.0, min(float(radius_m), FAR_MAX_RADIUS_M))
        max_points = max(1_000, min(int(max_points), FAR_MAX_POINTS))
        key = (round(latitude * 100), round(longitude * 100), round(radius_m / 500), max_points)
        now = time.monotonic()
        with self._lock:
            cached = self._far_cache.get(key)
        if cached and now - cached[0] < CACHE_SECONDS:
            return cached[1]
        try:
            points = worldcover_far_tree_points(latitude, longitude, radius_m, max_points)
        except (OSError, TimeoutError, ValueError, RasterioIOError):
            return {"source": "unavailable", "available": False, "points": []}
        payload: dict[str, object] = {"source": "ESA WorldCover 2021 (decimated)", "available": True, "points": points}
        with self._lock:
            if len(self._far_cache) >= 8:
                oldest = min(self._far_cache, key=lambda item: self._far_cache[item][0])
                del self._far_cache[oldest]
            self._far_cache[key] = (now, payload)
        return payload

    def _fetch(self, latitude: float, longitude: float, radius_m: float) -> dict[str, Any]:'''

with io.open("cesium_backend/osm_scene.py", "r", encoding="utf-8", newline="") as handle:
    src = handle.read()
nl = "\r\n" if "\r\n" in src else "\n"
if "def worldcover_far_tree_points" not in src:
    with io.open("cesium_backend/osm_scene.py", "a", encoding="utf-8", newline="") as handle:
        handle.write(FAR_FUNC.replace("\n", nl))

patch("cesium_backend/osm_scene.py", [
    ("from rasterio.errors import RasterioIOError", "from rasterio.enums import Resampling\nfrom rasterio.errors import RasterioIOError"),
    ("MAX_WORLDCOVER_TREES: Final[int] = 6_000", "MAX_WORLDCOVER_TREES: Final[int] = 1_500"),
    ("        self._lock = threading.Lock()", "        self._far_cache: dict[tuple[int, int, int, int], tuple[float, dict[str, object]]] = {}\n        self._lock = threading.Lock()"),
    ("    def _fetch(self, latitude: float, longitude: float, radius_m: float) -> dict[str, Any]:", FAR_METHOD),
])

patch("cesium_backend/app.py", [
    ("from .osm_scene import MAX_RADIUS_M, OSMSceneService", "from .osm_scene import FAR_MAX_POINTS, FAR_MAX_RADIUS_M, MAX_RADIUS_M, OSMSceneService"),
    ("\n    return app\n", '''
    @app.get("/api/far-trees")
    async def far_trees(
        lat: float = Query(..., ge=-90.0, le=90.0),
        lon: float = Query(..., ge=-180.0, le=180.0),
        radius_m: float = Query(9000.0, ge=1000.0, le=FAR_MAX_RADIUS_M),
        max_points: int = Query(25000, ge=1000, le=FAR_MAX_POINTS),
    ) -> dict[str, object]:
        try:
            return await asyncio.to_thread(osm_scene.far_trees, lat, lon, radius_m, max_points)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not retrieve distant tree cover") from exc

    return app
'''),
])

NEAR_FILTER = (
    "let treeCount=0,esaKept=0;for(const item of scene.vegetation){"
    "if(item.source==='esa_worldcover_2021_tree_cover'){"
    "const dm=Math.hypot((item.lat-flight.lat)*111320,(item.lon-flight.lon)*111320*Math.cos(radians(flight.lat)));"
    "if(esaKept>=900||dm>450)continue;esaKept++;}"
    "const model=treeModelFor(item);if(!model)continue;"
)
FAR_JS = (
    "viewer.clock.onTick.addEventListener(()=>{if(flight.started&&!sceneIsLoading&&sceneDistance(sceneCenter,flight)>500)loadRealWorldScene();});"
    "\n    const farTrees=viewer.scene.primitives.add(new Cesium.BillboardCollection({scene:viewer.scene}));"
    "const farTreeImage=(()=>{const c=document.createElement('canvas');c.width=64;c.height=80;const g=c.getContext('2d');"
    "g.fillStyle='#4a3a28';g.fillRect(29,56,6,22);"
    "for(const b of [[32,26,22,'#2f5d2a'],[22,38,16,'#3a6e32'],[42,38,16,'#2b5326'],[32,40,18,'#356a30']]){g.fillStyle=b[3];g.beginPath();g.arc(b[0],b[1],b[2],0,Math.PI*2);g.fill();}"
    "return c.toDataURL('image/png');})();"
    "let farCenter=null,farLoading=false;"
    "async function loadFarTrees(){if(farLoading)return;farLoading=true;farCenter={lat:flight.lat,lon:flight.lon};"
    "try{const q=new URLSearchParams({lat:flight.lat.toFixed(5),lon:flight.lon.toFixed(5),radius_m:'9000',max_points:'25000'});"
    "const r=await fetch(`/api/far-trees?${q}`);if(!r.ok)return;const data=await r.json(),pts=data.points||[];"
    "const flat=viewer.scene.terrainProvider instanceof Cesium.EllipsoidTerrainProvider,"
    "hr=flat?Cesium.HeightReference.NONE:Cesium.HeightReference.CLAMP_TO_GROUND,cosLat=Math.cos(radians(flight.lat));"
    "farTrees.removeAll();"
    "for(let i=0;i+1<pts.length;i+=2){const lon=pts[i],lat=pts[i+1];"
    "if(Math.hypot((lat-flight.lat)*111320,(lon-flight.lon)*111320*cosLat)<450)continue;"
    "farTrees.add({position:Cesium.Cartesian3.fromDegrees(lon,lat,0),image:farTreeImage,width:30,height:38,sizeInMeters:true,"
    "verticalOrigin:Cesium.VerticalOrigin.BOTTOM,heightReference:hr});}"
    "}catch(_){}finally{farLoading=false;}}"
    "viewer.clock.onTick.addEventListener(()=>{if(!farLoading&&(!farCenter||sceneDistance(farCenter,flight)>2000))loadFarTrees();});"
)

patch("hello.html", [
    ("let treeCount=0;for(const item of scene.vegetation){const model=treeModelFor(item);if(!model)continue;", NEAR_FILTER),
    ("?4500:10000)", "?1500:10000)"),
    ("viewer.clock.onTick.addEventListener(()=>{if(flight.started&&!sceneIsLoading&&sceneDistance(sceneCenter,flight)>500)loadRealWorldScene();});", FAR_JS),
])
print("patched")
