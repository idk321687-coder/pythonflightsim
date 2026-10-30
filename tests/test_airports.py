from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cesium_backend.airports import AirportIndex


CSV = """id,ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,iata_code\n1,KSEA,large_airport,Seattle Tacoma International Airport,47.449,-122.309,433,US,US-WA,Seattle,SEA\n2,NZAA,large_airport,Auckland International Airport,-37.008,174.792,23,NZ,NZ-AUK,Auckland,AKL\n3,TEST,closed,Closed Field,10,10,,US,US-CA,,\n"""


class AirportIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "airports.csv"
        self.path.write_text(CSV, encoding="utf-8")
        self.index = AirportIndex(self.path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_closed_airports_are_excluded(self) -> None:
        self.assertEqual(self.index.status()["airports"], 2)

    def test_query_handles_date_line_rectangles(self) -> None:
        airports = self.index.query_bbox(170, -45, -170, -30)
        self.assertEqual([airport["ident"] for airport in airports], ["NZAA"])

    def test_search_prioritizes_exact_ident(self) -> None:
        airports = self.index.search("KSEA")
        self.assertEqual(airports[0]["name"], "Seattle Tacoma International Airport")


if __name__ == "__main__":
    unittest.main()
