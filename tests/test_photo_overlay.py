"""Tests for extraction of geotagged photo/file attachments from KML.

Covers the three patterns :func:`extract_photo_placemarks` must handle:
``PhotoOverlay`` elements, plain ``Placemark`` elements with a direct
``Icon`` reference, and (most importantly) plain ``Placemark`` elements
that attach a photo via an ``<img>``/``<a>`` reference embedded in their
``description`` HTML -- while making sure a placemark's ``Style``/
``IconStyle``/``Icon`` (its marker pin graphic) is never mistaken for an
attached photo. Also covers the resulting attachment ``name``, which
combines the placemark's own name with its attached file's name so
attachments remain distinguishable (and geoh5-name-unique) even when
many placemarks share the same generic name.
"""

from __future__ import annotations

from pathlib import Path

from kmz2geoh5.kmz_reader import read_kmz
from kmz2geoh5.photo_overlay import extract_photo_placemarks


def test_photo_overlay_and_description_attachments_found(synthetic_kmz: Path) -> None:
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    by_placemark_name = {photo.placemark_name: photo.href for photo in photos}

    assert by_placemark_name["Photo With Image"] == "photos/photo1.jpg"
    assert by_placemark_name["Photo Missing Image"] == "photos/missing.jpg"
    assert by_placemark_name["Field Photo Station"] == "photos/photo2.jpg"


def test_attachment_name_incorporates_placemark_and_file_name(synthetic_kmz: Path) -> None:
    """The built ``name`` should combine the placemark's own name with its
    attached file's name, so it stays distinct/meaningful even when many
    placemarks share the same generic placemark name."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    names = {photo.placemark_name: photo.name for photo in photos}

    assert names["Photo With Image"] == "Photo With Image - photo1"
    assert names["Field Photo Station"] == "Field Photo Station - photo2"


def test_marker_style_icon_is_not_mistaken_for_a_photo(synthetic_kmz: Path) -> None:
    """A placemark that only sets a custom marker pin via
    ``Style``/``IconStyle``/``Icon`` (and has no ``description``-embedded
    photo) must not appear in the extracted photo list at all."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    placemark_names = {photo.placemark_name for photo in photos}

    assert "Marker Only Station" not in placemark_names


def test_marker_style_icon_href_not_used_as_attachment(synthetic_kmz: Path) -> None:
    """Even for a placemark that *does* have a real photo attachment, the
    marker style's icon href must not leak in as a second (bogus)
    attachment."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    hrefs = [photo.href for photo in photos if photo.placemark_name == "Field Photo Station"]

    assert hrefs == ["photos/photo2.jpg"]


def test_folder_path_reflects_enclosing_kml_folder(synthetic_kmz: Path) -> None:
    """Each photo should record the ``/``-joined path of KML ``<Folder>``
    names enclosing its placemark, so it can later be nested under that
    same folder/station's geoh5 group, e.g. a photo attached inside
    ``<Folder><name>FieldPhotos</name>`` gets ``folder_path="FieldPhotos"``.
    Placemarks/PhotoOverlays with no enclosing ``<Folder>`` get
    ``folder_path=None``."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    folder_paths = {photo.placemark_name: photo.folder_path for photo in photos}

    assert folder_paths["Field Photo Station"] == "FieldPhotos"
    assert folder_paths["Photo With Image"] is None
    assert folder_paths["Photo Missing Image"] is None
