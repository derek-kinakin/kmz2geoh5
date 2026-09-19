"""End-to-end test verifying FieldMove Clino "locality" folders (a station
placemark plus Note/Image/Plane children, see :mod:`kmz2geoh5.fieldmove`)
are split into a richer geoh5 structure -- a station ``Points`` object, a
dedicated ``Notes`` object, and a dedicated ``Planes`` object with parsed
strike/dip/dip-direction data -- instead of one flat object mixing every
placemark together, while leaving every other (non-locality) folder in
the same document on the existing generic per-geometry-type path.
"""

from __future__ import annotations

from pathlib import Path

from geoh5py.workspace import Workspace

from kmz2geoh5 import convert

_TARGET_EPSG = 26911


def _children_by_name(workspace: Workspace, group_name: str):
    group = next(obj for obj in workspace.groups if getattr(obj, "name", None) == group_name)
    return {child.name: child for child in group.children}


def _comments(entity) -> list[dict]:
    if entity.comments is None:
        return []
    return entity.comments.values["Comments"]


def test_locality_folder_splits_into_station_notes_and_planes(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        children = _children_by_name(workspace, "DK 1")

        # Station point, Notes, and Planes are separate objects rather
        # than one object mixing the locality point with its Note/Plane
        # children.
        assert "DK 1" in children
        assert "DK 1 Notes" in children
        assert "DK 1 Planes" in children

        station_points = children["DK 1"]
        assert station_points.n_vertices == 1

        notes_points = children["DK 1 Notes"]
        assert notes_points.n_vertices == 1
        note_comments = _comments(notes_points)
        assert any(
            "Parallel structures on north wall" in c["Text"] for c in note_comments
        )


def test_locality_folder_excludes_image_placemark_from_generic_objects(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    """"Image" placemarks inside a locality folder are handled entirely
    by the photo-attachment pipeline (a sibling "Photos" sub-group) and
    must not also appear as a bare point on the station/"other" object."""
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        children = _children_by_name(workspace, "DK 1")
        station_points = children["DK 1"]

        # Only the locality/station placemark itself -- the "Image"
        # placemark's point is not duplicated here.
        assert station_points.n_vertices == 1

        photos_group = next(
            child for child in workspace.groups
            if getattr(child, "name", None) == "Photos"
            and getattr(child.parent, "name", None) == "DK 1"
        )
        assert len(list(photos_group.children)) == 1


def test_plane_placemarks_get_parsed_structural_data(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        children = _children_by_name(workspace, "DK 1")
        planes = children["DK 1 Planes"]

        assert planes.n_vertices == 2

        data_by_name = {d.name: d for d in planes.children if hasattr(d, "values")}
        assert set(data_by_name["Dip"].values) == {35.0, 68.0}
        assert set(data_by_name["Dip Direction"].values) == {245.0, 205.0}
        assert set(data_by_name["Lithology"].values) == {"RHY", "QMD"}
        assert set(data_by_name["Structure Type"].values) == {"Bedding", "Joint"}
        assert all(v == -4.99 for v in data_by_name["Declination"].values)


def test_non_locality_folders_are_unaffected(synthetic_kmz: Path, tmp_path: Path) -> None:
    """Folders that don't match the FieldMove Clino locality pattern
    (no placemark named after the folder, or no Note/Image/Plane child)
    must still be written via the existing generic per-geometry-type
    path -- e.g. "Stations" (plain field points, no locality/role
    placemarks) keeps a single flat "Stations" object."""
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        stations = next(obj for obj in workspace.groups if getattr(obj, "name", None) == "Stations")
        stations_points = next(
            obj for obj in stations.children if getattr(obj, "name", None) == "Stations"
        )
        assert stations_points.n_vertices == 2
