"""Typed planning primitives for converting local GLBs into Cesium 3D Tiles."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal


LOD: Final[tuple[tuple[int, int], ...]] = ((0, 12000), (1, 4500), (2, 1200), (3, 250))
TileKind = Literal["aircraft", "foliage", "structure", "wildlife"]


@dataclass(frozen=True, slots=True)
class LodTarget:
    level: int
    max_screen_error_px: int
    max_triangles: int
    texture_max_dimension: int


LOD_TARGETS: Final[tuple[LodTarget, ...]] = (
    LodTarget(0, 2, 180_000, 2048),
    LodTarget(1, 8, 80_000, 1024),
    LodTarget(2, 24, 24_000, 512),
    LodTarget(3, 64, 6_000, 256),
)


@dataclass(frozen=True, slots=True)
class AssetJob:
    source: Path
    output_root: Path
    kind: TileKind
    targets: tuple[LodTarget, ...] = LOD_TARGETS

    def output_tileset(self) -> Path:
        return self.output_root / self.source.stem / "tileset.json"


def discover_jobs(models_dir: Path, output_root: Path, catalog_path: Path) -> tuple[AssetJob, ...]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    jobs: list[AssetJob] = []
    for group, records in catalog.items():
        kind: TileKind = "foliage" if group == "foliage" else "aircraft" if group == "aircraft" else "structure"
        for record in records:
            source = models_dir / record["filename"]
            if source.is_file():
                jobs.append(AssetJob(source, output_root, kind))
    return tuple(jobs)


def build_command(job: AssetJob, converter: str = "gltf-pipeline") -> list[str]:
    """Build one deterministic conversion command; execute in a bounded worker pool."""
    output = job.output_root / job.source.stem
    return [converter, "-i", str(job.source), "-o", str(output / "lod0.glb"), "-d"]


def run_job(job: AssetJob, converter: str = "gltf-pipeline") -> None:
    job.output_root.mkdir(parents=True, exist_ok=True)
    command = build_command(job, converter)
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=180)

