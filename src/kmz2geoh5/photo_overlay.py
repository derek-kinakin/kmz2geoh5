"""Extraction of geotagged photos/attachments from KML ``PhotoOverlay``
elements and regular ``Placemark`` file attachments that GeoPandas/GDAL's
KML driver does not expose as geometry attributes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from xml.etree import ElementTree as ET

from kmz2geoh5.kmz_reader import _local_tag

# Matches <img ... src="...">, used to find photos embedded in a
# Placemark's HTML `description` (the pattern Google Earth/Google Maps
# uses when a user attaches a photo to a placemark rather than using it as
# a custom marker icon).
_IMG_SRC_RE = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)

# Matches <a ... href="...">, used to find plain file links (photos, PDFs,
# etc.) embedded in a Placemark's `description`.
_ANCHOR_HREF_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']+)["\']', re.IGNORECASE)

# Any absolute URL scheme (http://, https://, mailto:, etc.) or in-page
# anchor -- these are not files bundled inside the KMZ archive, so they
# are not candidate attachments.
_ABSOLUTE_REF_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:|^#")


@dataclass
class PhotoPlacemark:
    """A single geotagged photo/file attachment found in a KML document.

    :param name: Placemark/PhotoOverlay name (suffixed with an index if a
        single placemark has more than one attachment).
    :param longitude: Longitude in decimal degrees (WGS84).
    :param latitude: Latitude in decimal degrees (WGS84).
    :param altitude: Altitude in metres, if present (else 0.0).
    :param href: Path of the referenced file inside the KMZ archive,
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


def _direct_icon_href(element: ET.Element) -> str | None:
    """Return the ``href`` of an ``<Icon>`` that is a *direct* child of
    ``element`` (as used by ``PhotoOverlay``), ignoring any ``<Icon>``
    nested inside a ``<Style>``/``<IconStyle>`` -- the latter only
    defines the placemark's *marker pin* graphic, not an attached photo,
    and must not be mistaken for one.
    """
    icon = _find_child(element, "Icon")
    href_el = _find_child(icon, "href") if icon is not None else None
    return href_el.text.strip() if href_el is not None and href_el.text else None


def _description_attachment_hrefs(element: ET.Element) -> list[str]:
    """Find file references embedded in a Placemark's ``description`` HTML
    (``<img src="...">`` and ``<a href="...">``), which is how photos
    attached to a placemark (rather than used as its marker icon) are
    represented by Google Earth/Google Maps KMZ exports.

    Only relative references (i.e. files bundled inside the KMZ archive)
    are returned; absolute URLs (``http://``, ``mailto:``, ...) and
    in-page anchors (``#...``) are ignored.
    """
    description_el = _find_child(element, "description")
    if description_el is None or not description_el.text:
        return []

    text = description_el.text
    hrefs: list[str] = []
    for pattern in (_IMG_SRC_RE, _ANCHOR_HREF_RE):
        for match in pattern.finditer(text):
            href = unescape(match.group(1)).strip()
            if href and not _ABSOLUTE_REF_RE.match(href) and href not in hrefs:
                hrefs.append(href)
    return hrefs


def extract_photo_placemarks(kml_bytes: bytes) -> list[PhotoPlacemark]:
    """Find every geotagged photo/file attachment in a KML document.

    Handles three KML patterns:

    - ``<PhotoOverlay>`` elements, which carry a ``<point><coordinates>``
      and a direct ``<Icon><href>`` to the image.
    - Plain ``<Placemark>`` elements with a direct (non-``Style``)
      ``<Icon><href>``, an uncommon but valid pattern for attaching an
      image directly.
    - Plain ``<Placemark>`` elements whose ``description`` HTML embeds
      one or more ``<img src="...">``/``<a href="...">`` references to a
      file bundled in the KMZ -- the common pattern used when a photo (or
      other file) is attached to a placemark via Google Earth/Google
      Maps, as opposed to a ``<Style>``/``<IconStyle>``/``<Icon>``, which
      only customizes the placemark's *marker pin* and is not an
      attachment.

    A placemark may have more than one attachment (e.g. several photos
    embedded in its description); each becomes its own
    :class:`PhotoPlacemark` entry, sharing the placemark's location, with
    the name suffixed by an index when there is more than one.

    Placemarks without a resolvable point location, or without any
    attachment, are skipped (attachment-less placemarks are handled by the
    GeoPandas layer read instead).

    :param kml_bytes: Raw bytes of a KML document.
    :returns: List of :class:`PhotoPlacemark` found in the document.
    """
    root = ET.fromstring(kml_bytes)
    photos: list[PhotoPlacemark] = []

    for element in root.iter():
        tag = _local_tag(element)
        if tag not in ("PhotoOverlay", "Placemark"):
            continue

        hrefs: list[str] = []
        direct_href = _direct_icon_href(element)
        if direct_href is not None:
            hrefs.append(direct_href)
        if tag == "Placemark":
            hrefs.extend(
                href for href in _description_attachment_hrefs(element) if href not in hrefs
            )

        if tag == "Placemark" and not hrefs:
            # No attached photo/file; not a photo placemark, so it is left
            # for the GeoPandas layer read to handle as ordinary geometry.
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

        for href in hrefs or [None]:
            entry_name = name if len(hrefs) <= 1 else f"{name} ({hrefs.index(href) + 1})"
            photos.append(
                PhotoPlacemark(name=entry_name, longitude=lon, latitude=lat, altitude=alt, href=href)
            )

    return photos


def resolve_photo_bytes(namelist: list[str], href: str) -> str | None:
    """Resolve a ``PhotoOverlay``/``Icon`` ``href`` against a KMZ archive's
    member names, returning the matching archive member name (suitable for
    :meth:`kmz2geoh5.kmz_reader.KmzDocument.read_archive_member`)
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
