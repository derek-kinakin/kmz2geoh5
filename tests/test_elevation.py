"""Tests verifying elevation (z-coordinate) data from KML points, lines,
and polygons is carried through the full conversion pipeline into geoh5.

KML/KMZ coordinates may include a third (altitude) component. Per the KML
spec, whether that value represents true elevation depends on
``altitudeMode``: ``absolute``/``relativeToGround`` altitudes are
meaningful, while ``clampToGround`` (the default when no ``altitudeMode``
is given) means Google Earth ignores the raw value and clamps the feature
to terrain. This library always carries through whatever raw z-value is
present in the source KML, regardless of ``altitudeMode`` -- it does not
attempt to resolve "true" ground elevation via an external DEM, and does
not zero out z-values under clampToGround. These tests confirm that
raw-z-passthrough behaviour end-to-end.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from geoh5py.workspace import Workspace

from kmz2geoh5 import convert

# EPSG:26911 = NAD83 / UTM zone 11N, a projected CRS whose 2D transform does
# not touch the z coordinate, so any change in z after conversion would
# indicate a bug in this library rather than an artifact of reprojection.
_TARGET_EPSG = 26911


def _vertices_by_object_name(workspace: Workspace, name: str) -> np.ndarray:
    """Look up vertices for the named *object* (not group) in the
    workspace. Folder names and object names can collide in this fixture
    (a folder with a single geometry type is named after that folder), so
    we search ``list_objects_name`` rather than the ambiguous
    ``get_entity``, which may resolve to the same-named group instead."""
    matches = [uid for uid, obj_name in workspace.list_objects_name.items() if obj_name == name]
    assert matches, f"No object named {name!r} found in workspace"
    entity = workspace.get_entity(matches[0])[0]
    return np.asarray(entity.vertices)


def test_point_elevation_preserved(elevation_kmz: Path, tmp_path: Path) -> None:
    geoh5_path = convert(elevation_kmz, tmp_path / "elevation.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        vertices = _vertices_by_object_name(workspace, "Points")

        matches = [
            uid for uid, obj_name in workspace.list_objects_name.items() if obj_name == "Points"
        ]
        entity = workspace.get_entity(matches[0])[0]
        names = list(entity.get_data("Name")[0].values)

        elevation_by_name = dict(zip(names, vertices[:, 2]))

    assert elevation_by_name["Absolute Point"] == pytest.approx(1500.0)
    assert elevation_by_name["RelativeToGround Point"] == pytest.approx(50.0)
    assert elevation_by_name["ClampToGround Point With Z"] == pytest.approx(9999.0)
    assert elevation_by_name["No AltitudeMode With Z"] == pytest.approx(1234.0)
    assert elevation_by_name["No Z At All"] == pytest.approx(0.0)


def test_line_elevation_preserved(elevation_kmz: Path, tmp_path: Path) -> None:
    geoh5_path = convert(elevation_kmz, tmp_path / "elevation.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        vertices = _vertices_by_object_name(workspace, "Lines")

    assert vertices.shape == (2, 3)
    assert sorted(vertices[:, 2].tolist()) == pytest.approx([100.0, 200.0])


def test_polygon_elevation_preserved(elevation_kmz: Path, tmp_path: Path) -> None:
    geoh5_path = convert(elevation_kmz, tmp_path / "elevation.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        vertices = _vertices_by_object_name(workspace, "Polygons")

    # Exterior ring of the polygon fixture has 5 vertices (closed ring) with
    # z alternating between 300 and 310.
    assert vertices.shape == (5, 3)
    assert set(np.round(vertices[:, 2]).tolist()) == {300.0, 310.0}
