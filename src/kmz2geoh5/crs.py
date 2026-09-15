"""CRS validation and reprojection helpers.

KML/KMZ coordinates are always stored in WGS84 geographic coordinates
(EPSG:4326) per the KML specification, so no CRS auto-detection is needed
on the input side. The target CRS must always be supplied explicitly by
the caller as an EPSG code (e.g. a UTM zone), which is validated up front
so conversion fails fast with a clear error rather than partway through.
"""

from __future__ import annotations

import geopandas as gpd
import pyproj

from kmz2geoh5.kmz_reader import KML_CRS


def validate_epsg(epsg: int) -> pyproj.CRS:
    """Validate that ``epsg`` is a usable target coordinate reference system.

    :param epsg: EPSG code of the target projected CRS.
    :returns: The resolved :class:`pyproj.CRS`.
    :raises ValueError: If ``epsg`` does not resolve to a valid CRS.
    """
    try:
        return pyproj.CRS.from_epsg(epsg)
    except pyproj.exceptions.CRSError as exc:
        raise ValueError(f"Invalid target EPSG code: {epsg!r} ({exc})") from exc


def reproject(gdf: gpd.GeoDataFrame, epsg: int) -> gpd.GeoDataFrame:
    """Reproject a GeoDataFrame from WGS84 (KML's native CRS) to ``epsg``.

    :param gdf: GeoDataFrame as read from KML (assumed EPSG:4326; if no CRS
        is set, EPSG:4326 is assumed and assigned before reprojecting).
    :param epsg: Target EPSG code, already validated via :func:`validate_epsg`.
    :returns: A new GeoDataFrame with geometry reprojected to ``epsg``.
    """
    if gdf.crs is None:
        gdf = gdf.set_crs(KML_CRS)
    return gdf.to_crs(epsg=epsg)
