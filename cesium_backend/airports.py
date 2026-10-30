"""Local, queryable index over the OurAirports worldwide airport dataset.

The simulator never sends the full airport CSV to the browser.  A flight view
only receives the airports within its camera rectangle, while the complete
offline dataset remains available for search and route planning.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Iterable


AIRPORT_TYPES = frozenset({"large_airport", "medium_airport", "small_airport", "seaplane_base", "heliport"})
TYPE_PRIORITY = {
    "large_airport": 0,
    "medium_airport": 1,
    "small_airport": 2,
    "seaplane_base": 3,
    "heliport": 4,
}


@dataclass(frozen=True, slots=True)
class Airport:
    """The browser-facing subset of a record in airports.csv."""

    ident: str
    airport_type: str
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_ft: float | None
    country: str
    region: str
    municipality: str
    iata_code: str

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Airport | None":
        airport_type = (row.get("type") or "").strip()
        if airport_type not in AIRPORT_TYPES:
            return None
        try:
            latitude = float(row["latitude_deg"])
            longitude = float(row["longitude_deg"])
        except (KeyError, TypeError, ValueError):
            return None
        elevation = _as_float(row.get("elevation_ft"))
        return cls(
            ident=(row.get("ident") or "").strip(),
            airport_type=airport_type,
            name=(row.get("name") or "Unnamed airport").strip(),
            latitude_deg=latitude,
            longitude_deg=longitude,
            elevation_ft=elevation,
            country=(row.get("iso_country") or "").strip(),
            region=(row.get("iso_region") or "").strip(),
            municipality=(row.get("municipality") or "").strip(),
            iata_code=(row.get("iata_code") or "").strip(),
        )

    def payload(self) -> dict[str, object]:
        return {
            "ident": self.ident,
            "type": self.airport_type,
            "name": self.name,
            "lat": self.latitude_deg,
            "lon": self.longitude_deg,
            "elevation_ft": self.elevation_ft,
            "country": self.country,
            "region": self.region,
            "municipality": self.municipality,
            "iata": self.iata_code,
        }


def _as_float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


class AirportIndex:
    """Lazy, in-memory index suitable for a single local simulator server."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path

    @cached_property
    def airports(self) -> tuple[Airport, ...]:
        if not self.csv_path.is_file():
            raise FileNotFoundError(
                f"Airport dataset not found at {self.csv_path}. Run tools/sync_airports.py to install it."
            )
        with self.csv_path.open("r", encoding="utf-8", newline="") as handle:
            records = (Airport.from_row(row) for row in csv.DictReader(handle))
            return tuple(record for record in records if record is not None)

    def query_bbox(
        self,
        west: float,
        south: float,
        east: float,
        north: float,
        limit: int = 1600,
    ) -> list[dict[str, object]]:
        """Return airports in a WGS84 rectangle, correctly handling the date line."""
        west, east = _clamp_longitude(west), _clamp_longitude(east)
        south, north = sorted((_clamp_latitude(south), _clamp_latitude(north)))
        if west <= east:
            longitude_matches = lambda lon: west <= lon <= east
        else:
            longitude_matches = lambda lon: lon >= west or lon <= east

        matches = (
            airport
            for airport in self.airports
            if south <= airport.latitude_deg <= north and longitude_matches(airport.longitude_deg)
        )
        ranked = sorted(matches, key=lambda airport: (TYPE_PRIORITY[airport.airport_type], airport.name.casefold()))
        return [airport.payload() for airport in ranked[:max(1, min(limit, 4000))]]

    def search(self, query: str, limit: int = 12) -> list[dict[str, object]]:
        needle = query.strip().casefold()
        if not needle:
            return []

        def score(airport: Airport) -> tuple[int, int, str] | None:
            fields = (airport.ident, airport.iata_code, airport.name, airport.municipality)
            exact = any(field.casefold() == needle for field in fields if field)
            prefix = any(field.casefold().startswith(needle) for field in fields if field)
            contains = any(needle in field.casefold() for field in fields if field)
            if not contains:
                return None
            return (0 if exact else 1 if prefix else 2, TYPE_PRIORITY[airport.airport_type], airport.name.casefold())

        found: list[tuple[tuple[int, int, str], Airport]] = []
        for airport in self.airports:
            airport_score = score(airport)
            if airport_score is not None:
                found.append((airport_score, airport))
        found.sort(key=lambda item: item[0])
        return [airport.payload() for _, airport in found[:max(1, min(limit, 50))]]

    def status(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for airport in self.airports:
            counts[airport.airport_type] = counts.get(airport.airport_type, 0) + 1
        return {"airports": len(self.airports), "by_type": counts, "source": self.csv_path.name}


def _clamp_latitude(value: float) -> float:
    return max(-90.0, min(90.0, float(value)))


def _clamp_longitude(value: float) -> float:
    longitude = float(value)
    while longitude < -180.0:
        longitude += 360.0
    while longitude > 180.0:
        longitude -= 360.0
    return longitude
