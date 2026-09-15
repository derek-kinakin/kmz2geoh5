"""End-to-end test verifying photo/file attachments extracted from KML
(both ``PhotoOverlay`` elements and ``Placemark`` ``description``-embedded
photos) are written into the geoh5 workspace as ``Points`` objects with
the image bytes attached via ``FilenameData``.
"""

from __future__ import annotations

from pathlib import Path

from geoh5py.data import FilenameData
from geoh5py.workspace import Workspace

from kmz2geoh5 import convert

_TARGET_EPSG = 26911


def _photo_points_by_name(workspace: Workspace) -> dict[str, list]:
    photos_group = next(
        obj for obj in workspace.groups if getattr(obj, "name", None) == "Photos"
    )
    return {child.name: list(child.children) for child in photos_group.children}


def test_description_embedded_photo_is_written_with_file(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        points_by_name = _photo_points_by_name(workspace)

        assert "Field Photo Station" in points_by_name
        filename_children = [
            child for child in points_by_name["Field Photo Station"]
            if isinstance(child, FilenameData)
        ]
        assert len(filename_children) == 1
        assert filename_children[0].values == "photo2.jpg"

        # A placemark with only a marker-pin Style icon (no attached
        # photo) must not show up as its own entry under "Photos" at all.
        assert "Marker Only Station" not in points_by_name


def test_photo_overlay_with_missing_image_creates_point_without_file(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        points_by_name = _photo_points_by_name(workspace)

        assert "Photo Missing Image" in points_by_name
        filename_children = [
            child for child in points_by_name["Photo Missing Image"]
            if isinstance(child, FilenameData)
        ]
        assert filename_children == []
