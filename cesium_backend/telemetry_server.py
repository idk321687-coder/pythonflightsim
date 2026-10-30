"""Async FastAPI/WebSocket telemetry bridge with bounded latest-state queues."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Final, Protocol

from .coordinates import FlightState, flight_state_to_cesium_pose


TELEMETRY_HZ: Final[int] = 60
MAX_CLIENT_QUEUE: Final[int] = 2
MAX_BACKOFF_SECONDS: Final[float] = 8.0


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    STREAMING = "streaming"
    BACKING_OFF = "backing_off"


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    sequence: int
    monotonic_ns: int
    state: FlightState

    def payload(self) -> dict[str, object]:
        pose = flight_state_to_cesium_pose(self.state)
        return {
            "type": "telemetry",
            "sequence": self.sequence,
            "timestamp_monotonic_ns": self.monotonic_ns,
            "flight": asdict(self.state),
            **pose.as_payload(),
        }


class WebSocketLike(Protocol):
    async def send_json(self, data: object) -> None: ...


class LatestTelemetry:
    """Single-writer/latest-value store; stale frames are intentionally dropped."""

    def __init__(self) -> None:
        self._sample: TelemetrySample | None = None
        self._sequence = 0
        self._condition = asyncio.Condition()

    async def publish(self, state: FlightState) -> None:
        async with self._condition:
            self._sequence += 1
            self._sample = TelemetrySample(self._sequence, time.monotonic_ns(), state)
            self._condition.notify_all()

    async def wait_for_newer(self, sequence: int) -> TelemetrySample:
        async with self._condition:
            await self._condition.wait_for(lambda: self._sample is not None and self._sample.sequence > sequence)
            assert self._sample is not None
            return self._sample


class BackoffStateMachine:
    def __init__(self) -> None:
        self.state = ConnectionState.DISCONNECTED
        self._attempt = 0

    def connected(self) -> None:
        self._attempt = 0
        self.state = ConnectionState.STREAMING

    def dropped(self) -> float:
        self._attempt += 1
        self.state = ConnectionState.BACKING_OFF
        return min(MAX_BACKOFF_SECONDS, 0.25 * (2.0 ** (self._attempt - 1)))

    def retrying(self) -> None:
        self.state = ConnectionState.CONNECTING


async def stream_client(websocket: WebSocketLike, telemetry: LatestTelemetry) -> None:
    """Send only the newest sample; a slow browser cannot block the physics loop."""
    sequence = 0
    while True:
        sample = await telemetry.wait_for_newer(sequence)
        sequence = sample.sequence
        await websocket.send_json(sample.payload())


def create_app() -> object:
    """Create the app lazily so coordinate tests do not require FastAPI installed."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect

    app = FastAPI(title="Skyline Vector Telemetry", version="1.0")
    telemetry = LatestTelemetry()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/telemetry")
    async def publish_telemetry(state: FlightState) -> dict[str, int]:
        await telemetry.publish(state)
        return {"sequence": telemetry._sequence}

    @app.websocket("/ws/telemetry")
    async def telemetry_socket(websocket: WebSocket) -> None:
        await websocket.accept()
        backoff = BackoffStateMachine()
        backoff.connected()
        try:
            await stream_client(websocket, telemetry)
        except WebSocketDisconnect:
            delay = backoff.dropped()
            await asyncio.sleep(delay)
        finally:
            backoff.state = ConnectionState.DISCONNECTED

    return app
