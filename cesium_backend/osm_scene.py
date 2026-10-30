"""Read a small, cached real-world scene from OpenStreetMap via Overpass.

Only explicitly mapped point vegetation becomes an individual GLB model.  That
matters: a ``natural=tree`` node represents the physical trunk location, not a
randomly generated position.  Buildings and water are returned as their mapped
footprints for local Cesium rendering.
"""

from __future__ import annotations

import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as element_tree
from dataclasses import dataclass
from typing import Any, Final

import numpy
import rasterio
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.windows import Window, from_bounds


OVERPASS_ENDPOINTS: Final[tuple[str, ...]] = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
OSM_MAP_ENDPOINT: Final[str] = "https://api.openstreetmap.org/api/0.6/map"
OSM_MAP_RADIUS_LIMIT_M: Final[float] = 750.0
MAX_RADIUS_M: Final[float] = 2_200.0
MAX_TREES: Final[int] = 1_500
MAX_BUILDINGS: Final[int] = 1_800
MAX_WATER_AREAS: Final[int] = 80
MAX_GRASS_AREAS: Final[int] = 100
MAX_FOREST_AREAS: Final[int] = 100
MAX_WORLDCOVER_TREES: Final[int] = 1_500
CACHE_SECONDS: Final[float] = 30.0 * 60.0
WORLDCOVER_ROOT: Final[str] = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"


@dataclass(frozen=True, slots=True)
class CacheEntry:
    created_at: float
    payload: dict[str, object]


class OSMSceneService:
    """Bounded, in-memory Overpass client for one local simulator instance."""

    def __init__(self, endpoints: tuple[str, ...] = OVERPASS_ENDPOINTS) -> None:
        self.endpoints = endpoints
        self._cache: dict[tuple[int, int, int], CacheEntry] = {}
        self._far_cache: dict[tuple[int, int, int, int], tuple[float, dict[str, object]]] = {}
        self._lock = threading.Lock()

    def scene(self, latitude: float, longitude: float, radius_m: float = 1_800.0, fresh: bool = False) -> dict[str, object]:
        radius_m = max(150.0, min(float(radius_m), MAX_RADIUS_M))
        cache_key = (round(latitude * 2_000), round(longitude * 2_000), round(radius_m / 100))
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(cache_key)
        if cached and not fresh and now - cached.created_at < CACHE_SECONDS:
            return cached.payload

        raw = self._fetch(latitude, longitude, radius_m)
        payload = parse_osm_scene(raw, latitude, longitude, radius_m)
        runway_exclusions = airport_exclusions(raw)
        # OSM forest polygons are incomplete in many countries. ESA WorldCover
        # supplies a global 10 m Tree Cover class, streamed as a small COG
        # window around the aircraft. It does not use satellite-color guessing.
        try:
            worldcover = worldcover_tree_points(latitude, longitude, radius_m, runway_exclusions)
        except (OSError, TimeoutError, ValueError, RasterioIOError):
            worldcover = None
        if worldcover is not None:
            payload["vegetation"] = list(payload["vegetation"]) + worldcover
            # When WorldCover is online it replaces procedural forest fills.
            # This prevents a tagged strip from becoming a dense fake tree row.
            payload["forest"] = []
            payload["source"] = "ESA WorldCover 2021 + OpenStreetMap"
        counts = payload.get("counts")
        if isinstance(counts, dict):
            counts["worldcover_tree_cover"] = len(worldcover or [])
            counts["airport_exclusion_zones"] = len(runway_exclusions)
        with self._lock:
            self._cache[cache_key] = CacheEntry(now, payload)
        return payload

    def far_trees(self, latitude: float, longitude: float, radius_m: float = 9_000.0, max_points: int = 25_000) -> dict[str, object]:
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

    def _fetch(self, latitude: float, longitude: float, radius_m: float) -> dict[str, Any]:
        query = build_overpass_query(latitude, longitude, radius_m)
        body = urllib.parse.urlencode({"data": query}).encode("utf-8")
        last_error: Exception | None = None
        # The main API is reliable for our small flight-local rectangle.  It is
        # intentionally first so a slow or overloaded Overpass mirror never
        # holds the cockpit on a loading screen.
        try:
            return self._fetch_osm_map(latitude, longitude, min(radius_m, OSM_MAP_RADIUS_LIMIT_M))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, element_tree.ParseError) as exc:
            last_error = exc
        for endpoint in self.endpoints:
            request = urllib.request.Request(
                endpoint,
                data=body,
                headers={"User-Agent": "skyline-vector-local-scene/1.0", "Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                with urllib.request.urlopen(request, timeout=28) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
        raise RuntimeError("All configured real-world map sources were unavailable") from last_error

    @staticmethod
    def _fetch_osm_map(latitude: float, longitude: float, radius_m: float) -> dict[str, Any]:
        """Use OSM's main map API when an Overpass mirror is unavailable.

        The main API provides complete node/way geometry but is deliberately
        limited to a small flight-local rectangle to respect its usage policy.
        """
        north_delta = radius_m / 111_320.0
        east_delta = radius_m / (111_320.0 * max(0.15, math.cos(math.radians(latitude))))
        bounds = (longitude - east_delta, latitude - north_delta, longitude + east_delta, latitude + north_delta)
        url = f"{OSM_MAP_ENDPOINT}?bbox={','.join(f'{value:.7f}' for value in bounds)}"
        request = urllib.request.Request(url, headers={"User-Agent": "skyline-vector-local-scene/1.0"})
        with urllib.request.urlopen(request, timeout=28) as response:
            return _osm_xml_to_overpass(response.read())


def worldcover_tree_points(
    latitude: float,
    longitude: float,
    radius_m: float,
    exclusions: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Stream ESA WorldCover Tree Cover cells near the aircraft.

    WorldCover class ``10`` is Tree Cover. Rasterio uses HTTP range requests on
    the public Cloud-Optimized GeoTIFFs, so this reads a small local window
    rather than downloading a global raster.
    """
    north_delta = radius_m / 111_320.0
    east_delta = radius_m / (111_320.0 * max(0.15, math.cos(math.radians(latitude))))
    west, east = longitude - east_delta, longitude + east_delta
    south, north = latitude - north_delta, latitude + north_delta
    candidates: list[tuple[float, float, float]] = []
    opened_any_tile = False
    options = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_TIMEOUT": "18",
        "GDAL_HTTP_MAX_RETRY": "1",
    }
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
                    classes = dataset.read(1, window=window)
                    rows, columns = numpy.where(classes == 10)
                    transform = dataset.window_transform(window)
                    for row, column in zip(rows.tolist(), columns.tolist(), strict=True):
                        offset_x = 0.2 + 0.6 * _stable_fraction(row, column, 19)
                        offset_y = 0.2 + 0.6 * _stable_fraction(row, column, 73)
                        sample_lon = transform.c + (column + offset_x) * transform.a
                        sample_lat = transform.f + (row + offset_y) * transform.e
                        if _inside_airport(sample_lat, sample_lon, exclusions):
                            continue
                        # Sort on a stable pseudo-random value so the cap stays
                        # evenly spread across the whole local WorldCover window.
                        # Bias the cap toward the aircraft: nearby forest is dense, the far edge thins out.
                        metres_x = (sample_lon - longitude) * 111_320.0 * max(0.15, math.cos(math.radians(latitude)))
                        metres_y = (sample_lat - latitude) * 111_320.0
                        distance_fraction = min(1.5, math.hypot(metres_x, metres_y) / max(radius_m, 1.0))
                        random_fraction = _stable_rank(sample_lat, sample_lon) / 0x7FFFFFFF
                        candidates.append((random_fraction * (0.3 + distance_fraction), sample_lat, sample_lon))
            except RasterioIOError:
                continue
    if not opened_any_tile:
        raise RasterioIOError("No ESA WorldCover tile was available")
    candidates.sort(key=lambda item: item[0])
    return [
        {
            "id": f"esa-worldcover-tree-{round(sample_lat, 6)}-{round(sample_lon, 6)}-{index}",
            "kind": "tree",
            "lat": round(sample_lat, 7),
            "lon": round(sample_lon, 7),
            "source": "esa_worldcover_2021_tree_cover",
            "leaf_type": "broadleaved",
        }
        for index, (_, sample_lat, sample_lon) in enumerate(candidates[:MAX_WORLDCOVER_TREES])
    ]


def airport_exclusions(raw: dict[str, Any]) -> list[dict[str, object]]:
    """Read airport grounds, runways, and taxiways as no-tree zones."""
    exclusions: list[dict[str, object]] = []
    for element in raw.get("elements", []):
        tags = element.get("tags") or {}
        kind = tags.get("aeroway")
        if kind not in {"aerodrome", "runway", "taxiway"}:
            continue
        geometry = _ring(element.get("geometry"))
        if len(geometry) >= 2:
            exclusions.append({"kind": kind, "geometry": geometry})
    return exclusions


def _worldcover_tile_origins(west: float, south: float, east: float, north: float) -> list[tuple[int, int]]:
    """Return the 3x3 degree COG tile origins that touch a local extent."""
    if west < -180.0 or east > 180.0:
        # WorldCover COGs are still read on both sides of the date line.
        west = max(-180.0, west)
        east = min(180.0, east)
    first_lat = max(-90, math.floor(south / 3.0) * 3)
    last_lat = min(87, math.floor(north / 3.0) * 3)
    first_lon = max(-180, math.floor(west / 3.0) * 3)
    last_lon = min(177, math.floor(east / 3.0) * 3)
    return [(tile_lat, tile_lon) for tile_lat in range(first_lat, last_lat + 1, 3) for tile_lon in range(first_lon, last_lon + 1, 3)]


def _worldcover_filename(tile_lat: int, tile_lon: int) -> str:
    lat = f"N{tile_lat:02d}" if tile_lat >= 0 else f"S{abs(tile_lat):02d}"
    lon = f"E{tile_lon:03d}" if tile_lon >= 0 else f"W{abs(tile_lon):03d}"
    return f"ESA_WorldCover_10m_2021_v200_{lat}{lon}_Map.tif"


def _stable_fraction(row: int, column: int, salt: int) -> float:
    value = (row * 73_856_093) ^ (column * 19_349_663) ^ salt
    return (value & 0xFFFF) / 0xFFFF


def _stable_rank(latitude: float, longitude: float) -> int:
    return (int((latitude + 90.0) * 10_000_000) * 1_103_515_245 ^ int((longitude + 180.0) * 10_000_000)) & 0x7FFFFFFF


def _inside_airport(latitude: float, longitude: float, exclusions: list[dict[str, object]]) -> bool:
    point = [longitude, latitude]
    for zone in exclusions:
        geometry = zone["geometry"]
        if not isinstance(geometry, list):
            continue
        if len(geometry) >= 3 and _point_inside_polygon(point, geometry):
            return True
        width_m = 70.0 if zone.get("kind") == "runway" else 28.0
        for index in range(len(geometry) - 1):
            if _distance_to_segment_m(point, geometry[index], geometry[index + 1]) <= width_m:
                return True
    return False


def _point_inside_polygon(point: list[float], polygon: list[list[float]]) -> bool:
    inside = False
    for index, current in enumerate(polygon):
        previous = polygon[index - 1]
        crosses = (current[1] > point[1]) != (previous[1] > point[1])
        if crosses and point[0] < (previous[0] - current[0]) * (point[1] - current[1]) / (previous[1] - current[1]) + current[0]:
            inside = not inside
    return inside


def _distance_to_segment_m(point: list[float], start: list[float], end: list[float]) -> float:
    latitude_scale = 111_320.0
    longitude_scale = latitude_scale * math.cos(math.radians(point[1]))
    point_x, point_y = point[0] * longitude_scale, point[1] * latitude_scale
    start_x, start_y = start[0] * longitude_scale, start[1] * latitude_scale
    end_x, end_y = end[0] * longitude_scale, end[1] * latitude_scale
    delta_x, delta_y = end_x - start_x, end_y - start_y
    length_sq = delta_x * delta_x + delta_y * delta_y
    if length_sq == 0:
        return math.hypot(point_x - start_x, point_y - start_y)
    factor = max(0.0, min(1.0, ((point_x - start_x) * delta_x + (point_y - start_y) * delta_y) / length_sq))
    return math.hypot(point_x - (start_x + factor * delta_x), point_y - (start_y + factor * delta_y))


def build_overpass_query(latitude: float, longitude: float, radius_m: float) -> str:
    """Return a radius-bounded query that excludes arbitrary procedural cover."""
    return f"""
[out:json][timeout:25];
(
  node(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[natural~\"^(tree|shrub|rock)$\"];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[building];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[natural=water];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[waterway=riverbank];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[landuse~\"^(grass|meadow)$\"];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[natural~\"^(grassland|scrub)$\"];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[leisure=park];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[landuse=forest];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[natural=wood];
  way(around:{radius_m:.0f},{latitude:.6f},{longitude:.6f})[aeroway~"^(aerodrome|runway|taxiway)$"];
);
out body geom;
""".strip()


def parse_osm_scene(raw: dict[str, Any], center_lat: float, center_lon: float, radius_m: float) -> dict[str, object]:
    """Normalize Overpass JSON into a deliberately small browser payload."""
    vegetation: list[dict[str, object]] = []
    buildings: list[dict[str, object]] = []
    water: list[dict[str, object]] = []
    grass: list[dict[str, object]] = []
    forest: list[dict[str, object]] = []
    for element in raw.get("elements", []):
        tags = element.get("tags") or {}
        kind = tags.get("natural")
        if element.get("type") == "node" and kind in {"tree", "shrub", "rock"}:
            latitude, longitude = _coordinates(element)
            if latitude is None or longitude is None:
                continue
            vegetation.append(
                {
                    "id": f"osm-{element.get('id')}",
                    "kind": kind,
                    "lat": latitude,
                    "lon": longitude,
                    "height_m": _parse_distance(tags.get("height") or tags.get("est_height")),
                    "crown_diameter_m": _parse_distance(tags.get("diameter_crown")),
                    "leaf_type": tags.get("leaf_type", ""),
                    "leaf_cycle": tags.get("leaf_cycle", ""),
                    "genus": tags.get("genus", ""),
                    "species": tags.get("species", ""),
                }
            )
            continue

        geometry = _ring(element.get("geometry"))
        if len(geometry) < 3:
            continue
        if element.get("type") == "way" and "building" in tags:
            latitude, longitude = _centroid(geometry)
            buildings.append(
                {
                    "id": f"osm-building-{element.get('id')}",
                    "name": tags.get("name", tags.get("building", "Building")),
                    "footprint": geometry,
                    "height_m": _building_height(tags),
                    "min_height_m": _parse_distance(tags.get("min_height")) or 0.0,
                    "lat": latitude,
                    "lon": longitude,
                }
            )
        elif element.get("type") == "way" and (kind == "water" or tags.get("waterway") == "riverbank"):
            water.append({"id": f"osm-water-{element.get('id')}", "footprint": geometry, "name": tags.get("name", "Mapped water")})
        elif element.get("type") == "way" and _is_grass(tags):
            grass.append({"id": f"osm-grass-{element.get('id')}", "footprint": geometry, "name": tags.get("name", "Mapped grass")})
        elif element.get("type") == "way" and _is_forest(tags):
            forest.append({"id": f"osm-forest-{element.get('id')}", "footprint": geometry, "name": tags.get("name", "Mapped forest")})

    vegetation.sort(key=lambda item: _distance_sq(center_lat, center_lon, float(item["lat"]), float(item["lon"])))
    buildings.sort(key=lambda item: _distance_sq(center_lat, center_lon, float(item["lat"]), float(item["lon"])))
    water.sort(key=lambda item: -_polygon_area_hint(item["footprint"]))
    grass.sort(key=lambda item: -_polygon_area_hint(item["footprint"]))
    forest.sort(key=lambda item: -_polygon_area_hint(item["footprint"]))
    return {
        "source": "OpenStreetMap via Overpass API",
        "center": {"lat": center_lat, "lon": center_lon},
        "radius_m": radius_m,
        "vegetation": vegetation[:MAX_TREES],
        "buildings": buildings[:MAX_BUILDINGS],
        "water": water[:MAX_WATER_AREAS],
        "grass": grass[:MAX_GRASS_AREAS],
        "forest": forest[:MAX_FOREST_AREAS],
        "counts": {"vegetation": len(vegetation), "buildings": len(buildings), "water": len(water), "grass": len(grass), "forest": len(forest)},
    }


def _osm_xml_to_overpass(xml_data: bytes) -> dict[str, Any]:
    """Convert only the OSM XML fields required by ``parse_osm_scene``."""
    root = element_tree.fromstring(xml_data)
    node_positions: dict[str, tuple[float, float]] = {}
    elements: list[dict[str, Any]] = []
    for node in root.findall("node"):
        try:
            node_positions[node.attrib["id"]] = (float(node.attrib["lat"]), float(node.attrib["lon"]))
        except (KeyError, ValueError):
            continue
        tags = _xml_tags(node)
        if tags.get("natural") in {"tree", "shrub", "rock"}:
            latitude, longitude = node_positions[node.attrib["id"]]
            elements.append({"type": "node", "id": node.attrib["id"], "lat": latitude, "lon": longitude, "tags": tags})
    for way in root.findall("way"):
        tags = _xml_tags(way)
        if "building" not in tags and tags.get("natural") != "water" and tags.get("waterway") != "riverbank" and not _is_grass(tags) and not _is_forest(tags) and tags.get("aeroway") not in {"aerodrome", "runway", "taxiway"}:
            continue
        geometry = []
        for node_ref in way.findall("nd"):
            position = node_positions.get(node_ref.attrib.get("ref", ""))
            if position is not None:
                geometry.append({"lat": position[0], "lon": position[1]})
        elements.append({"type": "way", "id": way.attrib.get("id", ""), "tags": tags, "geometry": geometry})
    return {"elements": elements}


def _xml_tags(element: element_tree.Element) -> dict[str, str]:
    return {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag") if "k" in tag.attrib and "v" in tag.attrib}


def _is_grass(tags: dict[str, str]) -> bool:
    return tags.get("landuse") in {"grass", "meadow"} or tags.get("natural") in {"grassland", "scrub"} or tags.get("leisure") == "park"


def _is_forest(tags: dict[str, str]) -> bool:
    return tags.get("landuse") == "forest" or tags.get("natural") == "wood"


def _coordinates(element: dict[str, Any]) -> tuple[float | None, float | None]:
    try:
        return float(element["lat"]), float(element["lon"])
    except (KeyError, TypeError, ValueError):
        return None, None


def _ring(raw_geometry: Any) -> list[list[float]]:
    if not isinstance(raw_geometry, list):
        return []
    ring: list[list[float]] = []
    for point in raw_geometry:
        try:
            ring.append([round(float(point["lon"]), 7), round(float(point["lat"]), 7)])
        except (KeyError, TypeError, ValueError):
            continue
    if len(ring) > 3 and ring[0] == ring[-1]:
        ring.pop()
    return ring


def _centroid(ring: list[list[float]]) -> tuple[float, float]:
    return sum(point[1] for point in ring) / len(ring), sum(point[0] for point in ring) / len(ring)


def _parse_distance(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace(",", ".")
    try:
        if text.endswith("ft"):
            return round(float(text.removesuffix("ft").strip()) * 0.3048, 2)
        if text.endswith("m"):
            text = text.removesuffix("m").strip()
        return round(float(text), 2)
    except ValueError:
        return None


def _building_height(tags: dict[str, str]) -> float:
    explicit = _parse_distance(tags.get("height"))
    if explicit is not None and explicit > 0:
        return min(explicit, 900.0)
    try:
        levels = float(tags.get("building:levels", ""))
        if levels > 0:
            return min(levels * 3.2 + 1.5, 900.0)
    except ValueError:
        pass
    return 9.0


def _distance_sq(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    north = (latitude_a - latitude_b) * 111_320.0
    east = (longitude_a - longitude_b) * 111_320.0 * math.cos(math.radians(latitude_a))
    return north * north + east * east


def _polygon_area_hint(ring: object) -> float:
    if not isinstance(ring, list) or len(ring) < 3:
        return 0.0
    points = ring
    return abs(sum(points[index][0] * points[(index + 1) % len(points)][1] - points[(index + 1) % len(points)][0] * points[index][1] for index in range(len(points))))


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
