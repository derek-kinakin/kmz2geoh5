"""Top-level conversion API: KMZ -> geoh5."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from geoh5py.workspace import Workspace
from shapely.geometry import Point

from kmz2geoh5 import crs
from kmz2geoh5.geoh5_writer import GroupCache, write_layer, write_photos
from kmz2geoh5.kmz_reader import parse_folder_paths, read_kmz
from kmz2geoh5.photo_overlay import extract_photo_placemarks


def convert(kmz_path: str | Path, geoh5_path: str | Path, epsg: int) -> Path:
    """Convert a KMZ file into a geoh5 workspace.

    :param kmz_path: Path to the source ``.kmz`` file.
    :param geoh5_path: Path to the ``.geoh5`` file to create (overwritten
        if it already exists).
    :param epsg: EPSG code of the target projected coordinate reference
        system that all geometry should be reprojected into. KML/KMZ
        source coordinates are always WGS84 geographic (EPSG:4326); no
        auto-detection of the target CRS is performed, so this must be
        supplied explicitly by the caller (e.g. ``26911`` for UTM Zone
        11N / NAD83).
    :returns: Path to the written ``.geoh5`` file.
    """
    target_crs = crs.validate_epsg(epsg)

    kmz_path = Path(kmz_path)
    geoh5_path = Path(geoh5_path)

    document = read_kmz(kmz_path)
    folder_paths = parse_folder_paths(document.kml_bytes)
    photos = extract_photo_placemarks(document.kml_bytes)

    if geoh5_path.exists():
        geoh5_path.unlink()

    with Workspace(geoh5_path) as workspace:
        workspace.root.metadata = {
            "source_kmz": str(kmz_path.name),
            "target_epsg": epsg,
        }
        workspace.root.coordinate_reference_system = {
            "Code": f"EPSG:{epsg}",
            "Name": target_crs.name,
        }
        workspace.root.add_comment(
            f"Converted from '{kmz_path.name}' to EPSG:{epsg} ({target_crs.name}) "
            "by kmz2geoh5.",
            author="kmz2geoh5",
        )

        group_cache = GroupCache(workspace)

        for layer_name, gdf in document.layers.items():
            projected = crs.reproject(gdf, epsg)
            folder_path = folder_paths.get(layer_name, layer_name)
            parent = group_cache.get(folder_path)
            write_layer(workspace, parent, layer_name, projected)

        if photos:
            photo_points = gpd.GeoDataFrame(
                geometry=[Point(p.longitude, p.latitude, p.altitude) for p in photos],
                crs="EPSG:4326",
            )
            projected_photos = crs.reproject(photo_points, epsg)
            projected_coords = np.array(
                [[pt.x, pt.y, pt.z if pt.has_z else 0.0] for pt in projected_photos.geometry]
            )
            write_photos(
                workspace,
                group_cache,
                photos,
                projected_coords,
                document.namelist,
                document.read_archive_member,
            )

    return geoh5_path
