"""Low-level KML/KMZ parsing helpers shared across the library.

This module centralizes the two ways this library reads a KMZ archive:

1. Via GeoPandas (backed by GDAL's LIBKML/KML driver), which produces one
   GeoDataFrame ("layer") per top-level KML ``Folder``, including geometry
   and any ``ExtendedData``/``Schema``/``description`` attributes.
2. Via a lightweight ``xml.etree.ElementTree`` pass over the raw KML
   document, used only for constructs GDAL's KML driver does not expose as
   layers/attributes: nested ``Folder`` hierarchy and ``PhotoOverlay``
   elements.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import geopandas as gpd

# GeoPandas/GDAL driver used to read KML/KMZ. LIBKML gives more complete
# folder/attribute support than GDAL's plain KML driver where available.
_KML_DRIVER = "LIBKML"

# CRS that KML coordinates are always stored in (per the KML/OGC spec).
KML_CRS = "EPSG:4326"


@dataclass
class KmzDocument:
    """In-memory representation of a KMZ file's contents.

    :param path: Path to the source KMZ file.
    :param namelist: Names of every entry in the KMZ zip archive.
    :param kml_bytes: Raw bytes of the root KML document inside the KMZ.
    :param layers: Mapping of KML top-level folder/layer name to the
        GeoDataFrame of features found in that layer (EPSG:4326).
    """

    path: Path
    namelist: list[str] = field(default_factory=list)
    kml_bytes: bytes = b""
    layers: dict[str, gpd.GeoDataFrame] = field(default_factory=dict)

    def read_archive_member(self, name: str) -> bytes:
        """Read the raw bytes of an arbitrary member of the KMZ archive
        (e.g. an embedded photo referenced by a ``PhotoOverlay``)."""
        with zipfile.ZipFile(self.path) as kmz:
            return kmz.read(name)


def _find_root_kml_name(namelist: list[str]) -> str:
    """Identify the root KML document inside a KMZ archive's namelist.

    KMZ files conventionally store the root document as ``doc.kml``, but
    this is not guaranteed, so we look for any top-level ``.kml`` file
    (preferring one literally named ``doc.kml`` if present) rather than
    hardcoding the name.
    """
    kml_names = [n for n in namelist if n.lower().endswith(".kml")]
    if not kml_names:
        raise ValueError("No .kml document found inside the KMZ archive.")

    # Prefer a top-level (no directory separator) entry, and "doc.kml" if present.
    top_level = [n for n in kml_names if "/" not in n and "\\" not in n]
    candidates = top_level or kml_names
    for name in candidates:
        if Path(name).name.lower() == "doc.kml":
            return name
    return candidates[0]


def read_kmz(kmz_path: str | Path) -> KmzDocument:
    """Unzip a KMZ file and load its geometry/attributes via GeoPandas.

    :param kmz_path: Path to the ``.kmz`` file to read.
    :returns: A :class:`KmzDocument` with the raw KML bytes, the KMZ
        archive's member names, and one GeoDataFrame per KML layer
        (top-level folder), all in EPSG:4326.
    """
    kmz_path = Path(kmz_path)
    if not kmz_path.is_file():
        raise FileNotFoundError(f"KMZ file not found: {kmz_path}")

    with zipfile.ZipFile(kmz_path) as kmz:
        namelist = kmz.namelist()
        root_kml_name = _find_root_kml_name(namelist)
        kml_bytes = kmz.read(root_kml_name)

    layers: dict[str, gpd.GeoDataFrame] = {}
    layer_info = gpd.list_layers(kmz_path)
    layer_names = list(layer_info["name"])

    if not layer_names:
        # Some KMZ/KML documents with a single, unnamed folder still parse
        # as a single default layer; fall back to a plain read.
        gdf = gpd.read_file(kmz_path, driver=_KML_DRIVER)
        if not gdf.empty:
            layers["Placemarks"] = gdf
    else:
        for layer_name in layer_names:
            gdf = gpd.read_file(kmz_path, driver=_KML_DRIVER, layer=layer_name)
            if not gdf.empty:
                layers[layer_name] = gdf

    return KmzDocument(
        path=kmz_path,
        namelist=namelist,
        kml_bytes=kml_bytes,
        layers=layers,
    )


def _local_tag(element: ET.Element) -> str:
    """Return an XML element's tag name without its namespace prefix."""
    tag = element.tag
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def parse_folder_paths(kml_bytes: bytes) -> dict[str, str]:
    """Walk the nested ``<Folder>`` hierarchy of a KML document.

    :param kml_bytes: Raw bytes of a KML document.
    :returns: Mapping of each folder's own (leaf) name to its full path
        from the document root, using ``"/"`` as a separator, e.g.
        ``{"Leaf": "Top/Middle/Leaf"}``. Only folders with a ``<name>``
        are included. If two folders share the same leaf name, the last
        one encountered wins (KML documents in this library's target use
        case are not expected to have ambiguous folder names).
    """
    root = ET.fromstring(kml_bytes)
    paths: dict[str, str] = {}

    def _walk(element: ET.Element, ancestors: list[str]) -> None:
        for child in element:
            if _local_tag(child) != "Folder":
                # Recurse through non-Folder containers (Document, kml) too,
                # since folders can be nested inside a <Document>.
                _walk(child, ancestors)
                continue

            # ElementTree doesn't support namespace-agnostic XPath
            # (local-name()), so find the <name> child manually.
            name_text = None
            for sub in child:
                if _local_tag(sub) == "name" and sub.text:
                    name_text = sub.text.strip()
                    break

            if name_text:
                new_ancestors = ancestors + [name_text]
                paths[name_text] = "/".join(new_ancestors)
            else:
                new_ancestors = ancestors

            _walk(child, new_ancestors)

    _walk(root, [])
    return paths
