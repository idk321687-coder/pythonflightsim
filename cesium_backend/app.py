"""Simulator web application: Cesium client, local models, and world data APIs."""

from __future__ import annotations

import json
import zlib
import asyncio
from pathlib import Path

from fastapi import HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from foliage_and_models import CATALOG_PATH, generate_foliage_ecosystem

from .airports import AirportIndex
from .osm_scene import FAR_MAX_POINTS, FAR_MAX_RADIUS_M, MAX_RADIUS_M, OSMSceneService
from .runtime import cesium_ion_token
from .runways import RunwayIndex
from .telemetry_server import create_app as create_telemetry_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = PROJECT_ROOT / "static"
AIRPORT_CSV = STATIC_DIR / "data" / "airports.csv"
RUNWAY_CSV = STATIC_DIR / "data" / "runways.csv"


def create_app() -> object:
    """Build the local web server without loading airport records until requested."""
    app = create_telemetry_app()
    airports = AirportIndex(AIRPORT_CSV)
    runways = RunwayIndex(RUNWAY_CSV)
    osm_scene = OSMSceneService()
    ion_token = cesium_ion_token(PROJECT_ROOT)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def simulator() -> FileResponse:
        return FileResponse(PROJECT_ROOT / "hello.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> Response:
        return Response(status_code=204)

    @app.get("/api/catalog")
    async def catalog() -> dict[str, object]:
        if not CATALOG_PATH.is_file():
            raise HTTPException(status_code=503, detail="3D model catalog is not available")
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    @app.get("/api/runtime-config")
    async def runtime_config() -> JSONResponse:
        # Cesium ion browser tokens are intentionally sent only at runtime; the
        # checked-in JavaScript and static config stay secret-free. Restrict the
        # token itself to this local URL in Cesium ion's token settings.
        return JSONResponse({"cesiumIonToken": ion_token}, headers={"Cache-Control": "no-store"})

    @app.get("/api/ecosystem")
    async def ecosystem(
        lat: float = Query(..., ge=-90.0, le=90.0),
        lon: float = Query(..., ge=-180.0, le=180.0),
        biome: str = Query("mixed", pattern="^(mixed|alpine|autumn|tropical)$"),
        radius_m: float = Query(2200.0, ge=250.0, le=8000.0),
        count: int = Query(260, ge=10, le=700),
    ) -> dict[str, object]:
        # Stable seed makes repeat visits visually consistent and cache-friendly.
        seed = int((lat + 90.0) * 10_000) ^ int((lon + 180.0) * 10_000) ^ zlib.crc32(biome.encode())
        return generate_foliage_ecosystem(lat, lon, radius_m, count, biome, seed)

    @app.get("/api/airports")
    async def airport_view(
        west: float = Query(..., ge=-180.0, le=180.0),
        south: float = Query(..., ge=-90.0, le=90.0),
        east: float = Query(..., ge=-180.0, le=180.0),
        north: float = Query(..., ge=-90.0, le=90.0),
        limit: int = Query(1600, ge=1, le=4000),
    ) -> dict[str, object]:
        try:
            return {"airports": airports.query_bbox(west, south, east, north, limit)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/airports/search")
    async def airport_search(query: str = Query(..., min_length=1, max_length=80)) -> dict[str, object]:
        try:
            return {"airports": airports.search(query)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/airports/status")
    async def airport_status() -> dict[str, object]:
        try:
            return airports.status()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/airports/{ident}/runways")
    async def airport_runways(ident: str) -> dict[str, object]:
        try:
            return {"ident": ident.upper(), "runways": runways.for_airport(ident)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/real-world-scene")
    async def real_world_scene(
        lat: float = Query(..., ge=-90.0, le=90.0),
        lon: float = Query(..., ge=-180.0, le=180.0),
        radius_m: float = Query(700.0, ge=150.0, le=MAX_RADIUS_M),
        fresh: bool = False,
    ) -> dict[str, object]:
        try:
            return await asyncio.to_thread(osm_scene.scene, lat, lon, radius_m, fresh)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not retrieve mapped OpenStreetMap scene data") from exc

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
