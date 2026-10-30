"""Numerically stable flight-state to Cesium WGS84/ECEF transforms.

Conventions:
* Angles are degrees at the public boundary.
* Body axes are X-forward, Y-right, Z-down (航空/NED body convention).
* Heading is clockwise from true north, pitch is nose-up, and roll is
  positive right-wing-down.
* Position is geodetic WGS84 latitude/longitude/ellipsoidal height.

The Euler angles are accepted because that is the simulator's telemetry
contract, but all orientation composition and frame conversion uses quaternions.
No Euler angle is reconstructed during the transform, so the transform itself
does not introduce a gimbal-lock singularity.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin, sqrt
from typing import Final


WGS84_A: Final[float] = 6_378_137.0
WGS84_F: Final[float] = 1.0 / 298.257223563
WGS84_E2: Final[float] = WGS84_F * (2.0 - WGS84_F)
_EPSILON: Final[float] = 1.0e-12


@dataclass(frozen=True, slots=True)
class Vector3:
    x: float
    y: float
    z: float

    def __add__(self, other: Vector3) -> Vector3:
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Vector3) -> Vector3:
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> Vector3:
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    def dot(self, other: Vector3) -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: Vector3) -> Vector3:
        return Vector3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def norm(self) -> float:
        return sqrt(self.dot(self))

    def normalized(self) -> Vector3:
        length = self.norm()
        if length <= _EPSILON:
            raise ValueError("Cannot normalize a zero-length vector")
        return self * (1.0 / length)


@dataclass(frozen=True, slots=True)
class Quaternion:
    """Hamilton quaternion in (w, x, y, z) order."""

    w: float
    x: float
    y: float
    z: float

    def __mul__(self, other: Quaternion) -> Quaternion:
        return Quaternion(
            self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z,
            self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y,
            self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x,
            self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w,
        )

    def normalized(self) -> Quaternion:
        length = sqrt(self.w * self.w + self.x * self.x + self.y * self.y + self.z * self.z)
        if length <= _EPSILON:
            raise ValueError("Cannot normalize a zero-length quaternion")
        return Quaternion(self.w / length, self.x / length, self.y / length, self.z / length)

    def conjugate(self) -> Quaternion:
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def rotate(self, vector: Vector3) -> Vector3:
        pure = Quaternion(0.0, vector.x, vector.y, vector.z)
        rotated = self * pure * self.conjugate()
        return Vector3(rotated.x, rotated.y, rotated.z)

    @staticmethod
    def from_axis_angle(axis: Vector3, angle_rad: float) -> Quaternion:
        unit_axis = axis.normalized()
        half_angle = angle_rad * 0.5
        scale = sin(half_angle)
        return Quaternion(cos(half_angle), unit_axis.x * scale, unit_axis.y * scale, unit_axis.z * scale)


@dataclass(frozen=True, slots=True)
class FlightState:
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    latitude_deg: float
    longitude_deg: float
    altitude_m: float

    def validate(self) -> None:
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError(f"latitude out of range: {self.latitude_deg}")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError(f"longitude out of range: {self.longitude_deg}")
        if self.altitude_m < -WGS84_A:
            raise ValueError(f"altitude is below the valid ellipsoid range: {self.altitude_m}")


@dataclass(frozen=True, slots=True)
class CesiumPose:
    ecef_m: Vector3
    orientation_ecef: Quaternion

    def as_payload(self) -> dict[str, tuple[float, ...]]:
        return {
            "position_ecef_m": (self.ecef_m.x, self.ecef_m.y, self.ecef_m.z),
            "orientation_ecef_wxyz": (
                self.orientation_ecef.w,
                self.orientation_ecef.x,
                self.orientation_ecef.y,
                self.orientation_ecef.z,
            ),
        }


def geodetic_to_ecef(latitude_deg: float, longitude_deg: float, altitude_m: float) -> Vector3:
    """Map WGS84 geodetic coordinates to Cesium's Earth-fixed Cartesian frame."""
    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    sin_latitude = sin(latitude)
    cos_latitude = cos(latitude)
    radius = WGS84_A / sqrt(1.0 - WGS84_E2 * sin_latitude * sin_latitude)
    return Vector3(
        (radius + altitude_m) * cos_latitude * cos(longitude),
        (radius + altitude_m) * cos_latitude * sin(longitude),
        (radius * (1.0 - WGS84_E2) + altitude_m) * sin_latitude,
    )


def _enu_axes(latitude_deg: float, longitude_deg: float) -> tuple[Vector3, Vector3, Vector3]:
    """Return orthonormal ECEF east, north, up axes at a geodetic location."""
    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    east = Vector3(-sin(longitude), cos(longitude), 0.0)
    north = Vector3(-sin(latitude) * cos(longitude), -sin(latitude) * sin(longitude), cos(latitude))
    up = Vector3(cos(latitude) * cos(longitude), cos(latitude) * sin(longitude), sin(latitude))
    return east, north, up


def _quaternion_from_basis(forward: Vector3, right: Vector3, down: Vector3) -> Quaternion:
    """Convert body basis vectors expressed in ECEF into a body-to-ECEF quaternion."""
    # Columns are body X/Y/Z expressed in ECEF. This branch form is stable
    # across all rotations, including near 180-degree attitudes.
    m00, m01, m02 = forward.x, right.x, down.x
    m10, m11, m12 = forward.y, right.y, down.y
    m20, m21, m22 = forward.z, right.z, down.z
    trace = m00 + m11 + m22
    if trace > 0.0:
        scale = 0.5 / sqrt(trace + 1.0)
        result = Quaternion(0.25 / scale, (m21 - m12) * scale, (m02 - m20) * scale, (m10 - m01) * scale)
    elif m00 > m11 and m00 > m22:
        scale = 2.0 * sqrt(max(_EPSILON, 1.0 + m00 - m11 - m22))
        result = Quaternion((m21 - m12) / scale, 0.25 * scale, (m01 + m10) / scale, (m02 + m20) / scale)
    elif m11 > m22:
        scale = 2.0 * sqrt(max(_EPSILON, 1.0 + m11 - m00 - m22))
        result = Quaternion((m02 - m20) / scale, (m01 + m10) / scale, 0.25 * scale, (m12 + m21) / scale)
    else:
        scale = 2.0 * sqrt(max(_EPSILON, 1.0 + m22 - m00 - m11))
        result = Quaternion((m10 - m01) / scale, (m02 + m20) / scale, (m12 + m21) / scale, 0.25 * scale)
    return result.normalized()


def flight_state_to_cesium_pose(state: FlightState) -> CesiumPose:
    """Return an ECEF position and body orientation suitable for Cesium."""
    state.validate()
    ecef = geodetic_to_ecef(state.latitude_deg, state.longitude_deg, state.altitude_m)
    east, north, up = _enu_axes(state.latitude_deg, state.longitude_deg)

    # Compose intrinsic aerospace rotations with quaternions. The initial local
    # body basis is X-forward=north, Y-right=east, Z-down=-up.
    yaw_q = Quaternion.from_axis_angle(up, radians(state.yaw_deg))
    forward_yaw = yaw_q.rotate(north)
    right_yaw = yaw_q.rotate(east)
    pitch_q = Quaternion.from_axis_angle(right_yaw, radians(state.pitch_deg))
    forward_pitch = pitch_q.rotate(forward_yaw)
    down_pitch = pitch_q.rotate(up * -1.0)
    roll_q = Quaternion.from_axis_angle(forward_pitch, radians(state.roll_deg))
    forward = forward_pitch.normalized()
    right = roll_q.rotate(right_yaw).normalized()
    down = roll_q.rotate(down_pitch).normalized()
    orientation = _quaternion_from_basis(forward, right, down)
    return CesiumPose(ecef_m=ecef, orientation_ecef=orientation)


def ecef_to_geodetic(ecef: Vector3) -> tuple[float, float, float]:
    """Convert ECEF back to geodetic coordinates for round-trip tests."""
    longitude = atan2(ecef.y, ecef.x)
    distance = hypot(ecef.x, ecef.y)
    latitude = atan2(ecef.z, distance * (1.0 - WGS84_E2))
    for _ in range(8):
        sin_latitude = sin(latitude)
        radius = WGS84_A / sqrt(1.0 - WGS84_E2 * sin_latitude * sin_latitude)
        altitude = distance / max(_EPSILON, cos(latitude)) - radius
        latitude = atan2(ecef.z, distance * (1.0 - WGS84_E2 * radius / (radius + altitude)))
    sin_latitude = sin(latitude)
    radius = WGS84_A / sqrt(1.0 - WGS84_E2 * sin_latitude * sin_latitude)
    altitude = distance / max(_EPSILON, cos(latitude)) - radius
    return degrees(latitude), degrees(longitude), altitude
