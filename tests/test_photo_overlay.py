"""Tests for extraction of geotagged photo/file attachments from KML.

Covers the three patterns :func:`extract_photo_placemarks` must handle:
``PhotoOverlay`` elements, plain ``Placemark`` elements with a direct
``Icon`` reference, and (most importantly) plain ``Placemark`` elements
that attach a photo via an ``<img>``/``<a>`` reference embedded in their
``description`` HTML -- while making sure a placemark's ``Style``/
``IconStyle``/``Icon`` (its marker pin graphic) is never mistaken for an
attached photo.
"""

from __future__ import annotations

from pathlib import Path

from kmz2geoh5.kmz_reader import read_kmz
from kmz2geoh5.photo_overlay import extract_photo_placemarks


def test_photo_overlay_and_description_attachments_found(synthetic_kmz: Path) -> None:
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    by_name = {photo.name: photo.href for photo in photos}

    assert by_name["Photo With Image"] == "photos/photo1.jpg"
    assert by_name["Photo Missing Image"] == "photos/missing.jpg"
    assert by_name["Field Photo Station"] == "photos/photo2.jpg"


def test_marker_style_icon_is_not_mistaken_for_a_photo(synthetic_kmz: Path) -> None:
    """A placemark that only sets a custom marker pin via
    ``Style``/``IconStyle``/``Icon`` (and has no ``description``-embedded
    photo) must not appear in the extracted photo list at all."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    names = {photo.name for photo in photos}

    assert "Marker Only Station" not in names


def test_marker_style_icon_href_not_used_as_attachment(synthetic_kmz: Path) -> None:
    """Even for a placemark that *does* have a real photo attachment, the
    marker style's icon href must not leak in as a second (bogus)
    attachment."""
    document = read_kmz(synthetic_kmz)
    photos = extract_photo_placemarks(document.kml_bytes)
    hrefs = [photo.href for photo in photos if photo.name == "Field Photo Station"]

    assert hrefs == ["photos/photo2.jpg"]
