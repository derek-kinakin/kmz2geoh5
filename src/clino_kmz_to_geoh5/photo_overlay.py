"""Extraction of geotagged photos from KML ``PhotoOverlay`` (and similar)
placemarks that GeoPandas/GDAL's KML driver does not expose as geometry.
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from clino_kmz_to_geoh5.kmz_reader import _local_tag


@dataclass
class PhotoPlacemark:
    """A single geotagged photo found in a KML document.

    :param name: Placemark/PhotoOverlay name.
    :param longitude: Longitude in decimal degrees (WGS84).
    :param latitude: Latitude in decimal degrees (WGS84).
    :param altitude: Altitude in metres, if present (else 0.0).
    :param href: Path of the referenced image file inside the KMZ archive,
        relative to the KML document, if one could be resolved.
    """

    name: str
    longitude: float
    latitude: float
    altitude: float
    href: str | None


def _find_child(element: ET.Element, tag: str) -> ET.Element | None:
    for child in element:
        if _local_tag(child) == tag:
            return child
    return None


def _find_descendant(element: ET.Element, tag: str) -> ET.Element | None:
    for descendant in element.iter():
        if _local_tag(descendant) == tag:
            return descendant
    return None


def _parse_coordinates(text: str) -> tuple[float, float, float]:
    parts = [p for p in text.strip().split(",")]
    lon = float(parts[0])
    lat = float(parts[1])
    alt = float(parts[2]) if len(parts) > 2 and parts[2] != "" else 0.0
    return lon, lat, alt


def extract_photo_placemarks(kml_bytes: bytes) -> list[PhotoPlacemark]:
    """Find every geotagged photo placemark in a KML document.

    Handles two KML patterns:

    - ``<PhotoOverlay>`` elements, which carry a ``<point><coordinates>``
      and an ``<Icon><href>`` to the image.
    - Plain ``<Placemark>`` elements whose ``<Point>`` has an associated
      ``<Icon><href>`` (or a ``description`` embedding an ``<img>`` tag)
      pointing at an image file bundled in the KMZ.

    Placemarks without a resolvable point location are skipped.

    :param kml_bytes: Raw bytes of a KML document.
    :returns: List of :class:`PhotoPlacemark` found in the document.
    """
    root = ET.fromstring(kml_bytes)
    photos: list[PhotoPlacemark] = []

    for element in root.iter():
        tag = _local_tag(element)
        if tag not in ("PhotoOverlay", "Placemark"):
            continue

        icon = _find_descendant(element, "Icon")
        href_el = _find_child(icon, "href") if icon is not None else None
        href = href_el.text.strip() if href_el is not None and href_el.text else None

        if tag == "Placemark" and href is None:
            # Not a photo placemark; skip (handled by GeoPandas layer read).
            continue

        point = _find_descendant(element, "Point")
        if point is None:
            continue
        coords_el = _find_child(point, "coordinates")
        if coords_el is None or not coords_el.text:
            continue

        name_el = _find_child(element, "name")
        name = name_el.text.strip() if name_el is not None and name_el.text else "photo"

        lon, lat, alt = _parse_coordinates(coords_el.text)
        photos.append(
            PhotoPlacemark(name=name, longitude=lon, latitude=lat, altitude=alt, href=href)
        )

    return photos


def resolve_photo_bytes(namelist: list[str], href: str) -> str | None:
    """Resolve a ``PhotoOverlay``/``Icon`` ``href`` against a KMZ archive's
    member names, returning the matching archive member name (suitable for
    :meth:`clino_kmz_to_geoh5.kmz_reader.KmzDocument.read_archive_member`)
    or ``None`` if no match is found.

    KML ``href`` values are relative paths (e.g. ``images/IMG_0001.jpg``)
    that may or may not match the archive member name exactly depending on
    how the KMZ was packaged, so we also try a filename-only match.
    """
    if href in namelist:
        return href

    href_name = href.rsplit("/", 1)[-1]
    for member in namelist:
        if member.rsplit("/", 1)[-1] == href_name:
            return member
    return None
