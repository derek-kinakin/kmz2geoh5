"""Mapping of KML placemark attributes (``ExtendedData``/``description``/
standard fields as surfaced by GeoPandas) onto geoh5py ``Data`` entries.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Association value used for all attribute data created by this library:
# one value per feature/vertex on the object.
_VERTEX = "VERTEX"


def build_data_dict(gdf, exclude: tuple[str, ...] = ("geometry",)) -> dict:
    """Convert a GeoDataFrame's attribute columns into a geoh5py
    ``add_data`` payload.

    Numeric columns become float/int data; anything else (text, mixed,
    booleans, dates) is coerced to string and stored as text data. Missing
    values are represented as ``NaN`` for numeric columns and as empty
    strings for text columns, since geoh5py data arrays cannot contain
    ``None``.

    :param gdf: GeoDataFrame (or plain DataFrame) whose non-geometry
        columns should be mapped to geoh5py data.
    :param exclude: Column names to skip (defaults to just ``geometry``).
    :returns: Dict suitable for passing to
        ``geoh5py.objects.ObjectBase.add_data``, keyed by column name.
    """
    data: dict = {}
    for column in gdf.columns:
        if column in exclude:
            continue

        series = gdf[column]

        if pd.api.types.is_bool_dtype(series):
            values = series.fillna(False).to_numpy(dtype=bool)
            data[column] = {"values": values, "association": _VERTEX}
        elif pd.api.types.is_numeric_dtype(series):
            values = series.to_numpy(dtype=float)
            data[column] = {"values": values, "association": _VERTEX}
        else:
            values = series.fillna("").astype(str).to_numpy(dtype=object)
            data[column] = {
                "values": values,
                "association": _VERTEX,
                "type": "TEXT",
            }

    return data
