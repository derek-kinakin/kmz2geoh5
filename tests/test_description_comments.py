"""Tests verifying KML ``description`` text is attached to geoh5 entities
as ``Comments`` (rather than duplicated as a raw-HTML data channel), for
both ordinary geometry features and photo/file attachments."""

from __future__ import annotations

from pathlib import Path

from geoh5py.workspace import Workspace

from kmz2geoh5 import convert
from kmz2geoh5.descriptions import clean_description_html

_TARGET_EPSG = 26911


def _comments(entity) -> list[dict]:
    if entity.comments is None:
        return []
    return entity.comments.values["Comments"]


def test_description_html_is_cleaned() -> None:
    raw = '<img src="photos/photo2.jpg" height="300" />Outcrop photo<br/>Second line'
    assert clean_description_html(raw) == "Outcrop photo\nSecond line"
    assert clean_description_html('<img src="x.jpg"/>') == ""
    assert clean_description_html(None) == ""
    assert clean_description_html(float("nan")) == ""


def test_feature_description_becomes_comment_on_layer_object(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        field_photos_group = next(
            obj for obj in workspace.groups if getattr(obj, "name", None) == "FieldPhotos"
        )
        field_photos_points = next(
            child for child in field_photos_group.children if child.name == "FieldPhotos"
        )
        comments = _comments(field_photos_points)

        assert any(c["Text"] == "Outcrop photo" for c in comments)
        assert any(c["Author"] == "Field Photo Station" for c in comments)
        # A placemark with no description at all ("Marker Only Station")
        # must not add an empty/blank comment.
        assert not any(c["Text"] == "" for c in comments)

        # Raw HTML must never leak into a comment's text.
        assert not any("<img" in c["Text"] for c in comments)


def test_description_not_duplicated_as_data_channel(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        field_photos_group = next(
            obj for obj in workspace.groups if getattr(obj, "name", None) == "FieldPhotos"
        )
        field_photos_points = next(
            child for child in field_photos_group.children if child.name == "FieldPhotos"
        )
        data_names = [
            child.name
            for child in field_photos_points.children
            if getattr(child, "name", None) not in ("UserComments",)
        ]
        assert "description" not in data_names


def test_photo_description_becomes_comment_on_photo_point(
    synthetic_kmz: Path, tmp_path: Path
) -> None:
    geoh5_path = convert(synthetic_kmz, tmp_path / "synthetic.geoh5", epsg=_TARGET_EPSG)

    with Workspace(geoh5_path) as workspace:
        field_photos_group = next(
            obj for obj in workspace.groups if getattr(obj, "name", None) == "FieldPhotos"
        )
        photos_subgroup = next(
            child for child in field_photos_group.children if child.name == "Photos"
        )
        photo_point = next(
            child
            for child in photos_subgroup.children
            if child.name == "Field Photo Station - photo2"
        )
        comments = _comments(photo_point)
        assert any(c["Text"] == "Outcrop photo" for c in comments)
        assert any(c["Author"] == "Field Photo Station" for c in comments)
