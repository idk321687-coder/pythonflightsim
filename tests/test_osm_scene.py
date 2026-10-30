from __future__ import annotations

import unittest

from cesium_backend.osm_scene import _inside_airport, _osm_xml_to_overpass, _worldcover_filename, _worldcover_tile_origins, build_overpass_query, parse_osm_scene


FIXTURE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 47.0, "lon": -122.0, "tags": {"natural": "tree", "height": "12 m", "genus": "Quercus"}},
        {"type": "way", "id": 2, "tags": {"building": "yes", "building:levels": "4"}, "geometry": [{"lat": 47.0, "lon": -122.0}, {"lat": 47.0, "lon": -121.9999}, {"lat": 47.0001, "lon": -121.9999}, {"lat": 47.0, "lon": -122.0}]},
        {"type": "way", "id": 3, "tags": {"natural": "water", "name": "Mapped Lake"}, "geometry": [{"lat": 47.0, "lon": -122.0}, {"lat": 47.0, "lon": -121.9998}, {"lat": 47.0002, "lon": -121.9998}, {"lat": 47.0, "lon": -122.0}]},
        {"type": "way", "id": 4, "tags": {"natural": "wood", "name": "Mapped Forest"}, "geometry": [{"lat": 47.0, "lon": -122.0}, {"lat": 47.0, "lon": -121.9995}, {"lat": 47.0005, "lon": -121.9995}, {"lat": 47.0, "lon": -122.0}]},
    ]
}


class OSMSceneTests(unittest.TestCase):
    def test_query_is_bounded_and_uses_exact_tree_tags(self) -> None:
        query = build_overpass_query(47.0, -122.0, 1000)
        self.assertIn('node(around:1000,47.000000,-122.000000)[natural~"^(tree|shrub|rock)$"]', query)

    def test_parser_preserves_mapped_coordinates_and_footprints(self) -> None:
        scene = parse_osm_scene(FIXTURE, 47.0, -122.0, 1000)
        tree = scene["vegetation"][0]
        self.assertEqual((tree["lat"], tree["lon"]), (47.0, -122.0))
        self.assertEqual(tree["height_m"], 12.0)
        self.assertEqual(scene["buildings"][0]["height_m"], 14.3)
        self.assertEqual(scene["water"][0]["name"], "Mapped Lake")
        self.assertEqual(scene["forest"][0]["name"], "Mapped Forest")

    def test_main_osm_api_xml_fallback_keeps_way_geometry(self) -> None:
        xml = b'''<osm><node id="1" lat="47.0" lon="-122.0"><tag k="natural" v="tree"/></node><node id="2" lat="47.0" lon="-121.9"/><node id="3" lat="47.1" lon="-121.9"/><way id="7"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/><tag k="building" v="yes"/></way></osm>'''
        raw = _osm_xml_to_overpass(xml)
        scene = parse_osm_scene(raw, 47.0, -122.0, 1000)
        self.assertEqual(len(scene["vegetation"]), 1)
        self.assertEqual(len(scene["buildings"][0]["footprint"]), 3)

    def test_worldcover_names_tiles_by_their_three_degree_lower_left_corner(self) -> None:
        self.assertEqual(_worldcover_filename(39, -87), "ESA_WorldCover_10m_2021_v200_N39W087_Map.tif")
        self.assertEqual(_worldcover_tile_origins(-84.68, 39.04, -84.65, 39.06), [(39, -87)])

    def test_airport_exclusions_keep_tree_points_off_runways(self) -> None:
        runway = [{"kind": "runway", "geometry": [[-84.67, 39.04], [-84.66, 39.04]]}]
        self.assertTrue(_inside_airport(39.0401, -84.665, runway))
        self.assertFalse(_inside_airport(39.043, -84.665, runway))


if __name__ == "__main__":
    unittest.main()
