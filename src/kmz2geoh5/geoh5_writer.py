"""Build a geoh5py Workspace from parsed/reprojected KMZ data.

Group and object hierarchy:

- One nested ``geoh5py`` ``ContainerGroup`` per KML folder path (see
  :func:`kmz2geoh5.kmz_reader.parse_folder_paths`).
- One object per geometry type present in a folder/layer: a ``Points``
  object for point features, a ``Curve`` for line features. Polygon
  features are also written as a ``Curve`` describing each polygon's
  exterior boundary ring (closed polyline); full triangulated ``Surface``
  meshes are not built in v1, since that would require triangulating
  arbitrary (possibly concave) polygons, which is out of scope for a
  faithful geometry conversion.
- One single-vertex ``Points`` object per geotagged photo/file attachment,
  with the file attached via ``add_file``, grouped under a ``Photos``
  sub-group nested inside its enclosing KML folder/station's own group
  (e.g. a photo attached inside ``<Folder><name>DK 16</name>`` ends up at
  ``DK 16/Photos``), so photos remain associated with the same named
  placemark/station group as the rest of that folder's geometry. Photos
  with no enclosing folder fall back to a top-level ``Photos`` group.
"""

from __future__ import annotations

import numpy as np
from geoh5py.groups import ContainerGroup, Group
from geoh5py.objects import Curve, Points
from geoh5py.shared.utils import find_unique_name
from geoh5py.workspace import Workspace

from kmz2geoh5.attributes import build_data_dict
from kmz2geoh5.photo_overlay import PhotoPlacemark, resolve_photo_bytes


class GroupCache:
    """Creates (and reuses) nested geoh5py Groups for ``"/"``-separated
    folder paths, e.g. ``"Top/Middle/Leaf"``."""

    def __init__(self, workspace: Workspace):
        self._workspace = workspace
        self._groups: dict[str, Group] = {}

    def get(self, path: str | None) -> Group | None:
        if not path:
            return None
        if path in self._groups:
            return self._groups[path]

        parts = path.split("/")
        parent = None
        built = ""
        for part in parts:
            built = f"{built}/{part}" if built else part
            if built in self._groups:
                parent = self._groups[built]
                continue
            group = ContainerGroup.create(self._workspace, name=part, parent=parent)
            self._groups[built] = group
            parent = group
        return parent


def _line_cells(part_lengths: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Build a Curve's ``cells`` (vertex index pairs) and ``parts`` arrays
    from the vertex count of each individual line/ring."""
    cells = []
    parts = []
    offset = 0
    for part_id, length in enumerate(part_lengths):
        for i in range(length - 1):
            cells.append([offset + i, offset + i + 1])
        parts.extend([part_id] * length)
        offset += length
    return np.array(cells, dtype=np.int32), np.array(parts, dtype=np.int32)


def _points_vertices(geometry_series) -> np.ndarray:
    # Points within the same layer may be a mix of 2D and 3D (e.g. some
    # placemarks specify an altitude and others don't), so z must be
    # checked per-point rather than assuming uniform dimensionality across
    # the whole series.
    return np.array(
        [[p.x, p.y, p.z if p.has_z else 0.0] for p in geometry_series]
    )


def write_points(workspace: Workspace, parent: Group | None, name: str, gdf) -> Points:
    """Create a geoh5py ``Points`` object from a GeoDataFrame of Point
    geometries, with all non-geometry columns mapped to vertex data."""
    vertices = _points_vertices(gdf.geometry)
    points = Points.create(workspace, vertices=vertices, name=name, parent=parent)
    data = build_data_dict(gdf)
    if data:
        points.add_data(data)
    return points


def write_lines(workspace: Workspace, parent: Group | None, name: str, gdf) -> Curve:
    """Create a geoh5py ``Curve`` object from a GeoDataFrame of LineString
    (or MultiLineString) geometries."""
    all_coords: list[np.ndarray] = []
    part_lengths: list[int] = []
    row_indices: list[int] = []

    for row_idx, geometry in enumerate(gdf.geometry):
        line_strings = geometry.geoms if geometry.geom_type == "MultiLineString" else [geometry]
        for line in line_strings:
            coords = np.asarray(line.coords)
            if coords.shape[1] == 2:
                coords = np.column_stack([coords, np.zeros(len(coords))])
            all_coords.append(coords)
            part_lengths.append(len(coords))
            row_indices.append(row_idx)

    vertices = np.vstack(all_coords)
    cells, parts = _line_cells(part_lengths)
    curve = Curve.create(
        workspace, vertices=vertices, cells=cells, parts=parts, name=name, parent=parent
    )
    # Attribute data is per-feature (per row of the source GeoDataFrame),
    # but Curve data must be per-vertex; broadcast each feature's
    # attributes across all vertices belonging to that feature/part.
    per_vertex_gdf = gdf.iloc[row_indices].reset_index(drop=True)
    expanded_gdf = per_vertex_gdf.loc[per_vertex_gdf.index.repeat(part_lengths)].reset_index(
        drop=True
    )
    data = build_data_dict(expanded_gdf)
    if data:
        curve.add_data(data)
    return curve


def write_polygons(workspace: Workspace, parent: Group | None, name: str, gdf) -> Curve:
    """Create a geoh5py ``Curve`` describing the exterior boundary ring of
    each Polygon (or MultiPolygon) geometry in ``gdf``."""
    all_coords: list[np.ndarray] = []
    part_lengths: list[int] = []
    row_indices: list[int] = []

    for row_idx, geometry in enumerate(gdf.geometry):
        polygons = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
        for polygon in polygons:
            coords = np.asarray(polygon.exterior.coords)
            if coords.shape[1] == 2:
                coords = np.column_stack([coords, np.zeros(len(coords))])
            all_coords.append(coords)
            part_lengths.append(len(coords))
            row_indices.append(row_idx)

    vertices = np.vstack(all_coords)
    cells, parts = _line_cells(part_lengths)
    curve = Curve.create(
        workspace, vertices=vertices, cells=cells, parts=parts, name=name, parent=parent
    )
    per_vertex_gdf = gdf.iloc[row_indices].reset_index(drop=True)
    expanded_gdf = per_vertex_gdf.loc[per_vertex_gdf.index.repeat(part_lengths)].reset_index(
        drop=True
    )
    data = build_data_dict(expanded_gdf)
    if data:
        curve.add_data(data)
    return curve


_GEOMETRY_WRITERS = {
    "Point": write_points,
    "MultiPoint": write_points,
    "LineString": write_lines,
    "MultiLineString": write_lines,
    "Polygon": write_polygons,
    "MultiPolygon": write_polygons,
}

_SUFFIX_BY_KIND = {
    "Point": "Points",
    "MultiPoint": "Points",
    "LineString": "Lines",
    "MultiLineString": "Lines",
    "Polygon": "Polygons",
    "MultiPolygon": "Polygons",
}


def write_layer(workspace: Workspace, parent: Group | None, layer_name: str, gdf) -> list:
    """Write one KML layer (folder) of features to geoh5py, splitting the
    layer's features by geometry type into one object per type.

    :returns: List of the geoh5py objects created for this layer.
    """
    objects = []
    geom_types = gdf.geometry.geom_type.unique()
    for geom_type in geom_types:
        writer = _GEOMETRY_WRITERS.get(geom_type)
        if writer is None:
            continue
        subset = gdf[gdf.geometry.geom_type == geom_type]
        suffix = _SUFFIX_BY_KIND[geom_type]
        name = f"{layer_name} {suffix}" if len(geom_types) > 1 else layer_name
        objects.append(writer(workspace, parent, name, subset))
    return objects


def write_photos(
    workspace: Workspace,
    group_cache: GroupCache,
    photos: list[PhotoPlacemark],
    projected_coords: np.ndarray,
    namelist: list[str],
    read_member,
) -> list[Points]:
    """Create one single-vertex Points object per geotagged photo, with the
    photo image attached as a file.

    Each photo is nested under a ``Photos`` sub-group of its own enclosing
    KML folder/station (``photo.folder_path``, e.g. ``"DK 16"``), reusing
    the same geoh5py group already created for that folder's ordinary
    geometry (see :func:`write_layer`) via ``group_cache`` -- so a photo
    attached to a placemark inside a named station folder ends up nested
    under that station's group rather than a single flat top-level
    ``Photos`` group for the entire document. Photos with no enclosing
    folder (``folder_path`` is ``None``) fall back to a top-level
    ``Photos`` group under the workspace root.

    :param workspace: Target geoh5py Workspace.
    :param group_cache: :class:`GroupCache` used to resolve/create each
        ``Photos`` sub-group.
    :param photos: Photo placemarks extracted from the KML document.
    :param projected_coords: Array, shape ``(len(photos), 3)``, of each
        photo's location already reprojected into the target CRS (x, y,
        altitude) -- photo locations are WGS84 in the source KML and must
        be reprojected the same way as all other geometry before being
        written to geoh5.
    :param namelist: Names of every entry in the KMZ archive, used to
        resolve each photo's ``href`` to an archive member.
    :param read_member: Callable ``(archive_member_name) -> bytes`` used to
        read the photo's image bytes out of the KMZ archive.
    """
    if not photos:
        return []

    # Group photos by their enclosing folder/station so each group of
    # siblings gets its own `Photos` sub-group and its own name-uniqueness
    # scope, while otherwise preserving each photo's original order.
    grouped: dict[str | None, list[tuple[PhotoPlacemark, np.ndarray]]] = {}
    for photo, coords in zip(photos, projected_coords):
        grouped.setdefault(photo.folder_path, []).append((photo, coords))

    created = []
    for folder_path, entries in grouped.items():
        photos_group_path = f"{folder_path}/Photos" if folder_path else "Photos"
        photos_group = group_cache.get(photos_group_path)

        # Photo names already combine the parent placemark's name with
        # its attached file name (see
        # `photo_overlay._build_attachment_name`), but that alone does
        # not guarantee uniqueness (e.g. two placemarks referencing the
        # same file, or several photos with no resolvable file name at
        # all). geoh5py does not enforce sibling name uniqueness for
        # objects on its own, and Geoscience Analyst silently renames
        # (and warns about) duplicate names on load, so de-duplicate
        # here against this Photos group's existing/previously-created
        # children before each Points object is created.
        sibling_names = [child.name for child in photos_group.children]

        for photo, coords in entries:
            unique_name = find_unique_name(photo.name, sibling_names)
            sibling_names.append(unique_name)
            point = Points.create(
                workspace,
                vertices=np.array([coords]),
                name=unique_name,
                parent=photos_group,
            )
            if photo.href:
                member_name = resolve_photo_bytes(namelist, photo.href)
                if member_name:
                    point.add_file(
                        read_member(member_name), name=member_name.rsplit("/", 1)[-1]
                    )
            created.append(point)
    return created
