from __future__ import annotations

import unittest
from math import isclose

from cesium_backend.coordinates import FlightState, ecef_to_geodetic, flight_state_to_cesium_pose


class CoordinateTransformTests(unittest.TestCase):
    def test_wgs84_round_trip(self) -> None:
        state = FlightState(
            roll_deg=35.0,
            pitch_deg=89.999,
            yaw_deg=270.0,
            latitude_deg=45.0,
            longitude_deg=-73.0,
            altitude_m=2500.0,
        )
        pose = flight_state_to_cesium_pose(state)
        latitude, longitude, altitude = ecef_to_geodetic(pose.ecef_m)
        self.assertAlmostEqual(latitude, state.latitude_deg, places=8)
        self.assertAlmostEqual(longitude, state.longitude_deg, places=8)
        self.assertAlmostEqual(altitude, state.altitude_m, places=4)

    def test_quaternion_is_normalized_at_polar_position(self) -> None:
        state = FlightState(-170.0, -89.999, 123.0, -80.0, 179.0, 0.0)
        quaternion = flight_state_to_cesium_pose(state).orientation_ecef
        norm_squared = sum(value * value for value in (quaternion.w, quaternion.x, quaternion.y, quaternion.z))
        self.assertTrue(isclose(norm_squared, 1.0, rel_tol=0.0, abs_tol=1.0e-12))

    def test_invalid_geodetic_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            flight_state_to_cesium_pose(FlightState(0.0, 0.0, 0.0, 91.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
