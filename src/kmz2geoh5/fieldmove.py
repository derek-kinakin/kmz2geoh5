"""FieldMove Clino "locality" enrichment.

FieldMove Clino (a field-geology data-capture app; the source of this
library's real-world example KMZ) exports each field station as a KML
``<Folder>`` containing:

- a "locality placemark" whose ``<name>`` matches the folder's own name
  (the station location itself),
- zero or more placemarks named ``"Note"`` (free-text field observations),
- zero or more placemarks named ``"Image"`` (geotagged photos -- already
  fully handled by :mod:`kmz2geoh5.photo_overlay`), and
- zero or more structural-plane placemarks. Unlike ``Note``/``Image``,
  these are *not* named ``"Plane"``: their ``<name>`` is just the dip
  value with a trailing degree sign (e.g. ``"51°"``), and their
  ``description`` starts with a ``"{dip}° / {dip direction}°"`` line,
  e.g.::

      51° / 022°
      RHY
      Joint


      Declination: -4.99°

  (lithology code and structural-feature type on the following two
  lines, when present, then a blank line, then a magnetic declination
  reading). Detection therefore keys off this ``description`` pattern
  rather than the placemark's ``<name>``.

This module detects that pattern on a per-folder GeoDataFrame (as already
read by :mod:`kmz2geoh5.kmz_reader`) and splits it into role-based
subsets, so the generic KMZ conversion pipeline (:func:`write_layer
<kmz2geoh5.geoh5_writer.write_layer>`) is completely untouched for KMZs
that don't follow this convention, while FieldMove Clino output gets
richer geoh5 structure -- a dedicated ``Notes`` object and a dedicated
``Planes`` object with proper numeric ``Dip``/``Dip Direction`` data
instead of everything landing as one flat, undifferentiated ``Points``
object per station.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from kmz2geoh5.descriptions import clean_description_html

_NAME_COLUMN = "Name"
_DESCRIPTION_COLUMN = "description"

#: Role identifiers for a locality folder's non-station placemarks.
ROLE_NOTE = "note"
ROLE_IMAGE = "image"
ROLE_PLANE = "plane"

# Case-insensitive placemark <name> values recognized as a specific role
# by name alone. "photo" is accepted as a synonym for "image" since it is
# a common alternative label for the same kind of attachment placemark.
# Structural-plane placemarks are *not* matched by name (see module
# docstring) -- they are detected from their description text instead,
# via `is_plane_description` below.
_ROLE_BY_NAME = {
    "note": ROLE_NOTE,
    "image": ROLE_IMAGE,
    "photo": ROLE_IMAGE,
}

# First line of a structural-plane placemark's description: dip and dip
# direction, each written as a bare number followed by a degree sign
# (e.g. "51° / 022°"). Matched against the raw (or HTML-cleaned)
# description text's first line.
_DIP_DIP_DIRECTION_RE = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*°?\s*/\s*(-?\d+(?:\.\d+)?)\s*°?\s*$"
)

# "Declination: -4.99°" reading, appended by FieldMove Clino after a
# blank line following the plane's optional lithology/structure-type
# lines.
_DECLINATION_RE = re.compile(r"^declination:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass
class LocalitySplit:
    """Result of splitting a KML folder's GeoDataFrame into FieldMove
    Clino roles.

    :param locality: GeoDataFrame (0 or 1 rows) for the folder's own
        locality placemark (the station location itself).
    :param notes: GeoDataFrame of ``"Note"`` placemarks (may be empty).
    :param planes: GeoDataFrame of structural-plane placemarks, enriched
        with parsed ``Dip``/``Dip Direction``/``Declination``/
        ``Lithology``/``Structure Type`` columns (may be empty).
    :param other: GeoDataFrame of any remaining rows -- excludes
        ``"Image"`` rows, which are fully handled separately by
        :mod:`kmz2geoh5.photo_overlay`/
        :func:`kmz2geoh5.geoh5_writer.write_photos`.
    """

    locality: pd.DataFrame
    notes: pd.DataFrame
    planes: pd.DataFrame
    other: pd.DataFrame


def parse_plane_description(text: str) -> dict:
    """Parse a structural-plane placemark's description into its
    component fields.

    :param text: Plain text (e.g. the output of
        :func:`kmz2geoh5.descriptions.clean_description_html`), whose
        first non-empty line must match the ``"{dip}° / {dip
        direction}°"`` pattern -- check with :func:`is_plane_description`
        (or rely on this function returning ``{}`` when it doesn't
        match).
    :returns: Mapping with ``"Dip"`` and ``"Dip Direction"`` (floats)
        always present if the first line matches; ``"Declination"``
        (float) if a ``"Declination: ..."`` line is present; and, from
        any remaining non-blank lines (FieldMove Clino emits a lithology
        code then a structural-feature type, e.g. ``"RHY"``/``"Joint"``),
        ``"Lithology"`` and ``"Structure Type"`` (both strings) if
        exactly two such lines are present, or just ``"Structure Type"``
        if only one is. Returns ``{}`` if the first line doesn't match.
    """
    lines = text.splitlines()
    if not lines:
        return {}

    first_match = _DIP_DIP_DIRECTION_RE.match(lines[0])
    if not first_match:
        return {}

    fields: dict = {
        "Dip": float(first_match.group(1)),
        "Dip Direction": float(first_match.group(2)),
    }

    detail_lines: list[str] = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        declination_match = _DECLINATION_RE.match(line)
        if declination_match:
            fields["Declination"] = float(declination_match.group(1))
            continue
        detail_lines.append(line)

    if len(detail_lines) == 1:
        fields["Structure Type"] = detail_lines[0]
    elif len(detail_lines) >= 2:
        fields["Lithology"] = detail_lines[0]
        fields["Structure Type"] = detail_lines[1]

    return fields


def is_plane_description(description) -> bool:
    """Return whether a placemark's raw ``description`` value matches
    the FieldMove Clino structural-plane pattern (see module docstring):
    its first non-empty line reads ``"{dip}° / {dip direction}°"``.

    :param description: Raw ``description`` cell value (may be ``None``/
        ``NaN``, as pandas represents a missing string).
    """
    if not isinstance(description, str) or not description:
        return False
    return bool(parse_plane_description(clean_description_html(description)))


def is_locality_layer(layer_name: str, gdf: pd.DataFrame) -> bool:
    """Detect whether ``gdf`` (a KML folder's features) follows the
    FieldMove Clino "locality" convention: one placemark named the same
    as its enclosing folder (the station location itself), alongside at
    least one placemark named ``"Note"``/``"Image"``/``"Photo"``, or one
    structural-plane placemark (see :func:`is_plane_description`).

    :param layer_name: The KML folder's own name.
    :param gdf: GeoDataFrame of that folder's features, as read by
        :func:`kmz2geoh5.kmz_reader.read_kmz`.
    :returns: ``True`` if this folder matches the FieldMove Clino
        locality pattern. Generic KMZs (with no ``Name`` column, or no
        placemark matching the folder name plus a role child) return
        ``False`` and are left to the existing generic pipeline.
    """
    if _NAME_COLUMN not in gdf.columns or gdf.empty:
        return False
    names = gdf[_NAME_COLUMN].astype(str)
    has_locality_placemark = (names == layer_name).any()
    if not has_locality_placemark:
        return False

    has_named_role_child = names.str.lower().isin(_ROLE_BY_NAME).any()
    if has_named_role_child:
        return True

    descriptions = gdf[_DESCRIPTION_COLUMN] if _DESCRIPTION_COLUMN in gdf.columns else []
    return any(is_plane_description(d) for d in descriptions)


def _enrich_planes(gdf: pd.DataFrame) -> pd.DataFrame:
    """Parse each plane row's ``description`` into structured
    ``Dip``/``Dip Direction``/``Declination``/``Lithology``/``Structure
    Type`` columns, in addition to (not instead of) the original
    ``description`` column (still attached as a geoh5 ``Comments`` entry,
    see :func:`kmz2geoh5.geoh5_writer.add_feature_comments`)."""
    gdf = gdf.copy()
    descriptions = (
        gdf[_DESCRIPTION_COLUMN] if _DESCRIPTION_COLUMN in gdf.columns else pd.Series([None] * len(gdf))
    )
    parsed_rows = [parse_plane_description(clean_description_html(d)) for d in descriptions]

    all_keys = {key for row in parsed_rows for key in row}
    numeric_keys = {"Dip", "Dip Direction", "Declination"}
    for key in all_keys:
        if key in numeric_keys:
            gdf[key] = [row.get(key, float("nan")) for row in parsed_rows]
        else:
            gdf[key] = [row.get(key, "") for row in parsed_rows]
    return gdf


def split_locality_layer(layer_name: str, gdf: pd.DataFrame) -> LocalitySplit:
    """Split a locality-layer GeoDataFrame (see :func:`is_locality_layer`)
    into its FieldMove Clino roles.

    ``"Image"``/``"Photo"`` rows are dropped entirely from the split --
    geotagged photo attachments are already fully extracted and written
    by :mod:`kmz2geoh5.photo_overlay`/
    :func:`kmz2geoh5.geoh5_writer.write_photos`, so keeping them here
    would duplicate that placemark as a second, file-less point.

    :param layer_name: The KML folder's own name (used to identify the
        locality placemark row).
    :param gdf: GeoDataFrame of the folder's features.
    :returns: The role-partitioned :class:`LocalitySplit`.
    """
    names = gdf[_NAME_COLUMN].astype(str)
    lower_names = names.str.lower()
    descriptions = gdf[_DESCRIPTION_COLUMN] if _DESCRIPTION_COLUMN in gdf.columns else pd.Series(
        [None] * len(gdf), index=gdf.index
    )

    locality_mask = names == layer_name
    note_mask = lower_names == ROLE_NOTE
    image_mask = lower_names.isin(("image", "photo"))
    plane_mask = descriptions.apply(is_plane_description) & ~locality_mask
    other_mask = ~(locality_mask | note_mask | image_mask | plane_mask)

    planes = gdf[plane_mask]
    if not planes.empty:
        planes = _enrich_planes(planes)

    return LocalitySplit(
        locality=gdf[locality_mask],
        notes=gdf[note_mask],
        planes=planes,
        other=gdf[other_mask],
    )
