from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cesium_backend.runways import RunwayIndex


HEADER = "id,airport_ref,airport_ident,length_ft,width_ft,surface,lighted,closed,le_ident,le_latitude_deg,le_longitude_deg,le_elevation_ft,le_heading_degT,le_displaced_threshold_ft,he_ident,he_latitude_deg,he_longitude_deg,he_elevation_ft,he_heading_degT,he_displaced_threshold_ft"
CSV = "\n".join(
    [
        HEADER,
        "1,1,KTST,9000,150,ASP,1,0,18,10.0,20.0,,180,,36,9.97,20.0,,0,",
        "2,1,KTST,4000,100,GRS,0,1,09,,,,,,27,,,,,",
        "3,1,KTST,5000,75,WATER,0,0,,,,,,,,,,,,",
        "4,2,KTS3,6000,100,ASP,0,0,09,0.0,0.0,,90,,,,,,,",
        "5,3,KTS4,6000,100,ASP,0,0,09,,,,,,,,,,,",
        "",
    ]
)


class RunwayIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        path = Path(self.temp_dir.name) / "runways.csv"
        path.write_text(CSV, encoding="utf-8")
        self.index = RunwayIndex(path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_closed_and_water_runways_are_skipped(self) -> None:
        ends = self.index.for_airport("ktst")
        self.assertEqual([end["ident"] for end in ends], ["18", "36"])

    def test_headings_and_start_positions_follow_the_runway(self) -> None:
        south, north = self.index.for_airport("KTST")
        self.assertAlmostEqual(south["heading_deg"], 180.0, delta=0.5)
        self.assertAlmostEqual(north["heading_deg"], 0.0, delta=0.5)
        # Starts 15 m inboard of the 18 threshold, heading south.
        self.assertLess(south["lat"], 10.0)
        self.assertAlmostEqual(south["lat"], 10.0 - 15.0 / 111_195.0, places=5)

    def test_missing_far_end_is_derived_from_heading_and_length(self) -> None:
        ends = self.index.for_airport("KTS3")
        self.assertEqual(len(ends), 2)
        self.assertAlmostEqual(ends[0]["length_m"], 1829, delta=2)
        self.assertAlmostEqual(ends[1]["heading_deg"], 270.0, delta=0.5)

    def test_runway_without_coordinates_is_ignored(self) -> None:
        self.assertEqual(self.index.for_airport("KTS4"), [])
        self.assertEqual(self.index.for_airport("NONE"), [])


if __name__ == "__main__":
    unittest.main()
