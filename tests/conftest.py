"""Shared pytest fixtures: synthetic KMZ generation and paths to the real
example KMZ files used as integration fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.synthetic.builder import write_elevation_kmz, write_synthetic_kmz

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DATA_DIR = REPO_ROOT / "example_data"


@pytest.fixture
def synthetic_kmz(tmp_path: Path) -> Path:
    """A small, hand-crafted KMZ exercising nested folders, mixed geometry
    types, ExtendedData (present/absent), and PhotoOverlay placemarks (one
    with a resolvable bundled image, one with a missing image)."""
    return write_synthetic_kmz(tmp_path / "synthetic.kmz")


@pytest.fixture
def elevation_kmz(tmp_path: Path) -> Path:
    """A small, hand-crafted KMZ with 3D (elevation-bearing) point, line,
    and polygon geometry, covering all four ``altitudeMode`` variants."""
    return write_elevation_kmz(tmp_path / "elevation.kmz")


@pytest.fixture
def example_kmz_ot() -> Path:
    """The real 'OT Oct 2024.kmz' example file bundled in the repository."""
    path = EXAMPLE_DATA_DIR / "OT Oct 2024.kmz"
    if not path.is_file():
        pytest.skip(f"Example KMZ not found: {path}")
    return path
