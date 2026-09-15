"""End-to-end test verifying photo/file attachments extracted from KML
(both ``PhotoOverlay`` elements and ``Placemark`` ``description``-embedded
photos) are written into the geoh5 workspace as ``Points`` objects with
the image bytes attached via ``FilenameData``, and that every attachment
ends up with a unique, meaningful geoh5 object name.
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

        # Object name combines the placemark's own name with its attached
        # file's name (see photo_overlay._build_attachment_name).
        assert "Field Photo Station - photo2" in points_by_name
        filename_children = [
            child for child in points_by_name["Field Photo Station - photo2"]
            if isinstance(child, FilenameData)
        ]
        assert len(filename_children) == 1
        assert filename_children[0].values == "photo2.jpg"

        # A placemark with only a marker-pin Style icon (no attached
        # photo) must not show up as its own entry under "Photos" at all.
        assert not any(name.startswith("Marker Only Station") for name in points_by_name)


def test_photo_overlay_with_missing_image_creates_point_without_file(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        points_by_name = _photo_points_by_name(workspace)

        assert "Photo Missing Image - missing" in points_by_name
        filename_children = [
            child for child in points_by_name["Photo Missing Image - missing"]
            if isinstance(child, FilenameData)
        ]
        assert filename_children == []


def test_photo_object_names_are_unique_within_photos_group(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    """Even when the placemark-name+file-name combination is not itself
    unique (e.g. two different placemarks both named "Image" attaching
    the same photo file), every ``Points`` object created under a
    ``Photos`` group must still get a unique name, matching how geoh5py/
    Geoscience Analyst de-duplicate sibling names elsewhere (e.g.
    ``add_file``)."""
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        photos_group = next(
            obj for obj in workspace.groups if getattr(obj, "name", None) == "Photos"
        )
        names = [child.name for child in photos_group.children]

        assert len(names) == len(set(names))
        # The two placemarks named "Image" attaching the same file both
        # start out wanting the exact same name and must be disambiguated.
        assert "Image - photo1" in names
        assert any(name != "Image - photo1" and name.startswith("Image - photo1") for name in names)
