"""Shared pytest fixtures: synthetic KMZ generation for the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.synthetic.builder import write_elevation_kmz, write_synthetic_kmz


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
