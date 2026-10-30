"""Register the /api/airports/{ident}/runways endpoint in cesium_backend/app.py (idempotent)."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "cesium_backend" / "app.py"
text = path.read_text(encoding="utf-8")
if "RunwayIndex" in text:
    print("app.py already patched")
    raise SystemExit(0)

def replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, f"anchor not found exactly once: {old!r}"
    return source.replace(old, new)

text = replace_once(text, "from .runtime import cesium_ion_token\n", "from .runtime import cesium_ion_token\nfrom .runways import RunwayIndex\n")
text = replace_once(text, 'AIRPORT_CSV = STATIC_DIR / "data" / "airports.csv"\n', 'AIRPORT_CSV = STATIC_DIR / "data" / "airports.csv"\nRUNWAY_CSV = STATIC_DIR / "data" / "runways.csv"\n')
text = replace_once(text, "    airports = AirportIndex(AIRPORT_CSV)\n", "    airports = AirportIndex(AIRPORT_CSV)\n    runways = RunwayIndex(RUNWAY_CSV)\n")
endpoint = '''    @app.get("/api/airports/{ident}/runways")
    async def airport_runways(ident: str) -> dict[str, object]:
        try:
            return {"ident": ident.upper(), "runways": runways.for_airport(ident)}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

'''
text = replace_once(text, '    @app.get("/api/real-world-scene")', endpoint + '    @app.get("/api/real-world-scene")')
path.write_text(text, encoding="utf-8")
print("app.py patched")
