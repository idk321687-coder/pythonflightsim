"""Runway lookup used to place the aircraft on a real runway threshold.

Backed by the OurAirports runways.csv export (tools/sync_runways.py).  Every
usable runway yields one entry per direction, longest runways first, each with
a start position a little inboard of the pavement edge and the true heading.
"""

from __future__ import annotations

import csv
import math
from functools import cached_property
from pathlib import Path
from typing import Any


FEET_TO_METERS = 0.3048
EARTH_RADIUS_M = 6_371_008.8
START_OFFSET_M = 15.0  # keeps the whole aircraft on the pavement at the start of the roll
MIN_RUNWAY_M = 120.0


def _as_float(value: str | None) -> float | None:
    try:
        return float(value.strip()) if value and value.strip() else None
    except ValueError:
        return None


def destination(latitude: float, longitude: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
    angular = distance_m / EARTH_RADIUS_M
    theta = math.radians(bearing_deg)
    phi1, lambda1 = math.radians(latitude), math.radians(longitude)
    phi2 = math.asin(math.sin(phi1) * math.cos(angular) + math.cos(phi1) * math.sin(angular) * math.cos(theta))
    lambda2 = lambda1 + math.atan2(
        math.sin(theta) * math.sin(angular) * math.cos(phi1),
        math.cos(angular) - math.sin(phi1) * math.sin(phi2),
    )
    return math.degrees(phi2), (math.degrees(lambda2) + 540.0) % 360.0 - 180.0


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta = math.radians(lon2 - lon1)
    y = math.sin(delta) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((phi2 - phi1) / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _read_end(row: dict[str, str], side: str) -> dict[str, Any]:
    latitude = _as_float(row.get(f"{side}_latitude_deg"))
    longitude = _as_float(row.get(f"{side}_longitude_deg"))
    return {
        "ident": (row.get(f"{side}_ident") or "").strip(),
        "point": (latitude, longitude) if latitude is not None and longitude is not None else None,
        "heading": _as_float(row.get(f"{side}_heading_degT")),
    }


def runway_ends(row: dict[str, str]) -> list[dict[str, object]]:
    """Return one entry per usable direction of a runways.csv row."""
    if (row.get("closed") or "0").strip() not in {"", "0"}:
        return []
    surface = (row.get("surface") or "").strip().upper()
    if "WATER" in surface:
        return []
    ends = {side: _read_end(row, side) for side in ("le", "he")}
    length_m = (_as_float(row.get("length_ft")) or 0.0) * FEET_TO_METERS
    width_m = (_as_float(row.get("width_ft")) or 0.0) * FEET_TO_METERS or 30.0
    le_point, he_point = ends["le"]["point"], ends["he"]["point"]
    if le_point and he_point:
        # Surveyed end coordinates are more trustworthy than the declared headings.
        length_m = distance_m(*le_point, *he_point)
        ends["le"]["heading"] = bearing(*le_point, *he_point)
        ends["he"]["heading"] = bearing(*he_point, *le_point)
    elif le_point or he_point:
        known, other = ("le", "he") if le_point else ("he", "le")
        heading = ends[known]["heading"]
        if heading is None or length_m <= 0:
            return []
        ends[other]["point"] = destination(*ends[known]["point"], heading, length_m)
        ends[other]["heading"] = (heading + 180.0) % 360.0
    else:
        return []
    if length_m < MIN_RUNWAY_M:
        return []

    result: list[dict[str, object]] = []
    for side in ("le", "he"):
        end = ends[side]
        latitude, longitude = end["point"]
        heading = float(end["heading"])
        start_lat, start_lon = destination(latitude, longitude, heading, START_OFFSET_M)
        ident = end["ident"] or f"{(int(round(heading / 10.0)) % 36) or 36:02d}"
        result.append(
            {
                "ident": ident,
                "lat": round(start_lat, 7),
                "lon": round(start_lon, 7),
                "heading_deg": round(heading, 1),
                "length_m": round(length_m),
                "width_m": round(width_m),
                "surface": surface,
            }
        )
    return result


class RunwayIndex:
    """Lazy in-memory runway index keyed by airport ident."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path

    @cached_property
    def _by_airport(self) -> dict[str, list[dict[str, str]]]:
        if not self.csv_path.is_file():
            raise FileNotFoundError(
                f"Runway dataset not found at {self.csv_path}. Run tools/sync_runways.py to install it."
            )
        grouped: dict[str, list[dict[str, str]]] = {}
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                ident = (row.get("airport_ident") or "").strip().upper()
                if ident:
                    grouped.setdefault(ident, []).append(row)
        return grouped

    def for_airport(self, ident: str) -> list[dict[str, object]]:
        ends: list[dict[str, object]] = []
        for row in self._by_airport.get(ident.strip().upper(), []):
            ends.extend(runway_ends(row))
        ends.sort(key=lambda end: -float(end["length_m"]))
        return ends
