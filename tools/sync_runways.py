"""Download the OurAirports runway table used to start flights on a real runway."""

from __future__ import annotations

import urllib.request
from pathlib import Path


URL = "https://davidmegginson.github.io/ourairports-data/runways.csv"
TARGET = Path(__file__).resolve().parents[1] / "static" / "data" / "runways.csv"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "skyline-vector-flight-sim/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read()
    TARGET.write_bytes(content)
    print(f"Saved {len(content):,} bytes to {TARGET}")


if __name__ == "__main__":
    main()
