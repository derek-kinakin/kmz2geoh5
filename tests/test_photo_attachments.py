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


def _find_photos_group(workspace: Workspace, folder_path: str | None = None):
    """Find the ``Photos`` group nested under the given ``folder_path``
    (e.g. ``"FieldPhotos"``), or the top-level ``Photos`` group directly
    under the workspace root if ``folder_path`` is ``None``. Each distinct
    enclosing folder gets its own ``Photos`` group (see
    :func:`kmz2geoh5.geoh5_writer.write_photos`), so a bare name lookup is
    not enough once more than one exists.
    """
    expected_parent_names = folder_path.split("/") if folder_path else []

    def _parent_names(entity) -> list[str]:
        names = []
        parent = entity.parent
        while parent is not None and parent is not workspace.root:
            names.append(parent.name)
            parent = parent.parent
        return list(reversed(names))

    for obj in workspace.groups:
        if getattr(obj, "name", None) == "Photos" and _parent_names(obj) == expected_parent_names:
            return obj
    raise AssertionError(f"No 'Photos' group found for folder_path={folder_path!r}")


def _photo_points_by_name(workspace: Workspace, folder_path: str | None = None) -> dict[str, list]:
    photos_group = _find_photos_group(workspace, folder_path)
    return {child.name: list(child.children) for child in photos_group.children}


def test_description_embedded_photo_is_written_with_file(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        # "Field Photo Station" is nested inside the "FieldPhotos" KML
        # folder, so its photo attachment must be nested under
        # "FieldPhotos/Photos", not a flat top-level "Photos" group.
        points_by_name = _photo_points_by_name(workspace, folder_path="FieldPhotos")

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
        # "Photo Missing Image" is a top-level PhotoOverlay (not inside any
        # KML Folder), so it lands in the top-level "Photos" group.
        points_by_name = _photo_points_by_name(workspace, folder_path=None)

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
        # Both duplicate-named "Image" placemarks are top-level (not
        # inside any Folder), so they share the top-level "Photos" group.
        photos_group = _find_photos_group(workspace, folder_path=None)
        names = [child.name for child in photos_group.children]

        assert len(names) == len(set(names))
        # The two placemarks named "Image" attaching the same file both
        # start out wanting the exact same name and must be disambiguated.
        assert "Image - photo1" in names
        assert any(name != "Image - photo1" and name.startswith("Image - photo1") for name in names)


def test_photo_nested_under_enclosing_folder_group(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    """A photo attached inside a named KML folder/station should be
    nested under that same station's geoh5 group (reusing the group
    already created for the folder's ordinary geometry), rather than a
    single flat top-level "Photos" group for the whole document."""
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        field_photos_group = next(
            obj for obj in workspace.groups if getattr(obj, "name", None) == "FieldPhotos"
        )
        photos_subgroup = next(
            child for child in field_photos_group.children if child.name == "Photos"
        )
        assert "Field Photo Station - photo2" in [c.name for c in photos_subgroup.children]

        # The document-level PhotoOverlay/duplicate-named placemarks have
        # no enclosing folder, so they must NOT end up under
        # "FieldPhotos/Photos".
        assert "Photo With Image - photo1" not in [c.name for c in photos_subgroup.children]
