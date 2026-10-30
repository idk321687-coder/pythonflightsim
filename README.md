# Skyline Vector

A Python-served Cesium flight simulator using the local GLB aircraft and ecosystem assets in this repository.

## Run

```powershell
python -m pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:8000`.

## Desktop game window

On Windows, run this instead to launch Skyline Vector in its own WebView2 game
window, without browser tabs or address bars:

```powershell
python desktop_game.py
```

The desktop window uses its own local server at port 8001, so it can be open
at the same time as the normal development page on port 8000.

The desktop build still uses Cesium's WebGL renderer, because that is the
renderer that provides the satellite globe, terrain, and Cesium 3D Buildings.
It is a desktop window rather than a Chrome tab; it is not a total rewrite into
a separate native 3D engine.

## Included world systems

- Cesium globe with Esri World Imagery satellite basemap, controllable local GLB aircraft, and Python telemetry publishing.
- A bundled OurAirports world index with 72,000+ active airports. The browser only requests the current camera rectangle, so it does not load the full global dataset at once.
- ICAO, IATA, airport-name, and municipality search with repositioning for a new departure area.
- Worldwide ESA WorldCover 2021 streaming: only the 10 m Tree Cover class is turned into local GLB tree placements around the aircraft. The game uses HTTP range requests against the public COGs, so it reads a small local window rather than downloading the global dataset. OSM aerodrome, runway, and taxiway geometry are hard no-tree zones.
- An exact-position OpenStreetMap scene loader: `natural=tree`, shrub, and rock nodes are placed as the included local GLB models at their mapped coordinates. Mapped water and building footprints are rendered at their real outlines.
- Locally extruded OSM building footprints, using mapped `height` or `building:levels` when available.
- A GLB grass-tuft layer placed only inside mapped grass, meadow, grassland, scrub, or park polygons (capped at 750 tufts for browser performance).

## Optional Cesium ion enhancements

Set the scoped browser token in `.env`:

```js
CESIUM_ION_TOKEN="your_browser_token";
```

The server reads it at startup and supplies it only as runtime browser configuration. That enables Cesium World Terrain, water masks, terrain lighting, and the globally streamed Cesium OSM Buildings tileset. Without it, the simulator still runs with satellite imagery and local OSM-footprint building extrusions.

The UI's **LOAD REAL SCENE** control refreshes the small flight-local area around the aircraft. It will not substitute random vegetation for places where OSM has no individually mapped vegetation. Satellite imagery still shows the real canopy in those places; individual 3D trees appear only where a real feature coordinate exists in the source data.

## Asset credit

`static/models/grass_tuft.glb` is an MIT-licensed grass clump from the [Dark Strands](https://github.com/VictorZakharov/dark-strands) ez-tree demo. It is embedded-texture GLB content and is used locally; its placement is limited to real mapped grass cover.

The worldwide tree-cover layer uses ESA WorldCover 2021 v200 (Tree Cover class, 10 m): © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data 2021 processed by ESA WorldCover consortium.

## Controls

- Arrow keys: pitch and bank
- W / S: throttle
- P: pause or resume
- C: toggle chase camera
- R: regrow the current biome

## Data refresh

The airport data is committed under `static/data/airports.csv`. To refresh it from the public OurAirports export, run:

```powershell
python tools/sync_airports.py
```

## Verification

```powershell
python -m unittest discover -s tests -v
```
