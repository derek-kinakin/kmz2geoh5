# kmz2geoh5 — Implementation Plan

## Problem

Field geology data is collected/organized in Google Earth KMZ files (station
points, traverse/boundary lines and polygons, geotagged field photos). This
needs to be converted into Geoscience Analyst `.geoh5` workspaces, with
coordinates reprojected from WGS84 geographic (as stored in KML) into a
user-specified projected CRS (e.g. UTM), preserving folder organization,
attribute data, and attached photos.

## Approach

Build an installable Python library (`kmz2geoh5`), managed with
Hatch, using GeoPandas (backed by Fiona/GDAL's KML driver) to read KML
geometry + attributes, GeoPandas'/pyproj's `.to_crs()` for reprojection to a
user-supplied EPSG code, and `geoh5py` to write the resulting objects/groups
into a `.geoh5` workspace. A secondary lightweight XML pass (`xml.etree`)
handles KML constructs that GDAL's KML driver does not expose well —
specifically `PhotoOverlay` elements and folder/layer hierarchy — so photo
attachments and group nesting are preserved even if GeoPandas layer support
differs across GDAL versions. Library API only for v1; a CLI can be added
later as a thin wrapper.

## 1. Repository & File Structure

- Initialize git in `E:\My Drive\09 Dev\kmz2geoh5`.
- Create a dedicated **conda/mamba environment** for development (name:
  `kmz2geoh5`), defined in an `environment.yml` committed to the
  repo, using **conda-forge** for the binary-heavy geospatial stack (GDAL,
  Fiona, PROJ) so we avoid pip-on-Windows wheel/binary issues:
  ```yaml
  name: kmz2geoh5
  channels:
    - conda-forge
  dependencies:
    - python=3.12
    - gdal
    - fiona
    - geopandas
    - pyproj
    - pandas
    - numpy
    - hatch
    - pytest
    - pip
    - pip:
        - geoh5py   # installed via pip inside the conda env (not on conda-forge)
  ```
  Create it with `mamba env create -f environment.yml` (falling back to
  `conda env create -f environment.yml` if needed), activate it, and run
  all Hatch/pytest commands from inside that environment. Hatch is used
  for project structure/tasks/build metadata, but relies on the conda env
  (rather than Hatch's own isolated venv) to supply GDAL/Fiona/pyproj
  binaries — document this in the README so contributors always
  `conda activate kmz2geoh5` (or `mamba activate ...`) before
  running `hatch run ...`.
- Use Hatch (`hatch new`/`hatch-init` equivalent) to scaffold a src-layout
  package:
  ```
  kmz2geoh5/
    environment.yml            # conda/mamba dev environment (GDAL/Fiona/geopandas/pyproj/hatch/pytest)
    pyproject.toml            # Hatch build backend, metadata, dependencies
    README.md
    LICENSE
    .gitignore
    src/
      kmz2geoh5/
        __init__.py
        kmz_reader.py         # unzip KMZ, load KML via GeoPandas, manual XML pass
        photo_overlay.py       # PhotoOverlay + geotagged-photo extraction
        crs.py                 # reprojection helpers (GeoPandas/pyproj)
        attributes.py          # ExtendedData/attribute -> geoh5py Data mapping
        geoh5_writer.py         # build geoh5py Workspace/Groups/Objects
        convert.py              # top-level convert(kmz_path, geoh5_path, epsg) API
    tests/
      fixtures/
        synthetic/             # small hand-built KML/KMZ edge-case fixtures
      test_kmz_reader.py
      test_crs.py
      test_attributes.py
      test_geoh5_writer.py
      test_convert.py
    example_code/               # existing prototypes, kept for reference
    example_data/                # existing sample KMZs, used as pytest fixtures
  ```
- `pyproject.toml`: Hatch build backend, project metadata, Python `>=3.12`
  requirement, dependency list (below), Hatch environment(s) for test/lint.
- Keep existing `example_data/` KMZs and `example_code/` prototypes in place;
  reference them from tests rather than duplicating.

## 2. Key Supporting Python Libraries

| Purpose | Library |
|---|---|
| Development environment | `conda`/`mamba` (conda-forge channel) — provisions GDAL/Fiona/PROJ binaries |
| Packaging/build | `hatch` (build backend + task runner, run from inside the conda env) |
| KML/KMZ geometry + attribute reading | `geopandas` (using `fiona`'s KML/LIBKML driver under the hood) |
| Reprojection (WGS84 → user EPSG) | `geopandas.GeoDataFrame.to_crs()` / `pyproj` |
| Manual KML XML pass (PhotoOverlay, folder hierarchy) | `xml.etree.ElementTree` (stdlib) |
| KMZ archive handling | `zipfile` (stdlib) |
| Geoscience Analyst workspace I/O | `geoh5py` |
| Tabular/array handling | `pandas`, `numpy` |
| Testing | `pytest` |

Notes/assumptions to verify during setup: confirm the installed GDAL/Fiona
build includes KML (OGRKML) or LIBKML driver support; if LIBKML isn't
available, fall back to GDAL's default `KML` driver, which is sufficient for
Placemark geometry + ExtendedData but not for `PhotoOverlay` (handled by the
manual XML pass regardless).

## 3. Conversion Workflow

1. **Unzip KMZ** → locate and extract the root KML document (usually
   `doc.kml`, but read `namelist()` and identify the top-level `.kml`
   rather than hardcoding the name); also extract embedded photo assets
   referenced by `PhotoOverlay`/`Icon/href`.
2. **Parse geometry + attributes via GeoPandas**: read the extracted KML
   into one or more GeoDataFrames (points, lines, polygons), preserving
   the KML `Folder` each feature belongs to and any `ExtendedData`/`Schema`
   fields or `description` HTML as attribute columns.
3. **Manual XML pass** over the same KML for constructs GeoPandas/Fiona
   won't surface as geometry rows:
   - `PhotoOverlay` elements → photo placemark name, lat/lon/altitude,
     and the referenced image filename inside the KMZ.
   - Plain `Placemark` elements with photos/files attached via an
     `<img>`/`<a>` reference embedded in their `description` HTML (the
     pattern used by Google Earth/Google Maps when a user attaches a
     photo to a placemark) → same name/lat/lon/altitude/filename
     extraction as `PhotoOverlay`. A placemark's `Style`/`IconStyle`/
     `Icon` (its marker pin graphic) is deliberately *not* treated as an
     attachment — only `description`-embedded references (or a rare
     direct, non-`Style` `Icon/href` on the placemark itself) count.
   - Folder hierarchy (nested `<Folder>` names) → target geoh5py Group
     hierarchy, in case GeoPandas layer-per-folder behavior is
     incomplete/unavailable.
4. **Reproject** each GeoDataFrame from its source CRS (EPSG:4326, as
   declared by KML) to the user-specified target EPSG using
   `GeoDataFrame.to_crs(epsg=...)`.
5. **Build geoh5py structures**:
   - Open/create a `geoh5py.workspace.Workspace` at the output path.
   - Recreate the KML folder hierarchy as nested `geoh5py.groups.Group`
     objects.
   - Within each folder-group, create one geoh5py object per geometry
     type present (`Points`, `Curve` for lines, `Curve`/`Surface` for
     polygons), populated with the reprojected coordinates.
   - Map each attribute column to geoh5py `Data` on that object (numeric
     → float/int data, text → text data), per-vertex/per-feature as
     appropriate.
   - For photo placemarks: match each `PhotoOverlay`/attachment entry to
     the nearest enclosing KML `Folder` (its `folder_path`, tracked
     during the same manual XML pass used for extraction), create/reuse
     a `Photos` sub-group nested under that folder's own geoh5py group
     (or a top-level `Photos` group if the placemark has no enclosing
     folder) via the same group-path cache used for ordinary geometry,
     and create a `Points` object for each photo location, calling
     `add_file()` (or the appropriate geoh5py file-association API) to
     attach the extracted image bytes. This keeps a folder's photos
     (e.g. "DK 16") nested alongside that folder's other geometry,
     rather than pooled into one flat top-level `Photos` group for the
     whole document. Each `Points` object is named by combining the
     parent placemark's own name with its attached file's name (since
     photo placemarks are frequently all named the same generic thing,
     e.g. "Image", by Google Earth/Google Maps), with a final
     de-duplication pass against sibling names within its own `Photos`
     group (mirroring how geoh5py de-duplicates sibling `Data`/
     `FilenameData` names) so every object has a unique name and
     Geoscience Analyst never needs to silently rename anything (with a
     warning) on load.
6. **Save and close** the Workspace.

Top-level API: `convert(kmz_path, geoh5_path, epsg) -> Path` in
`convert.py`, composing the steps above; each step also exposed as its own
function/module for unit testing and reuse.

## 4. Expected KMZ Data Types (v1 scope)

- **Points** — field stations, sample locations, waypoints (standard
  `Placemark`/`Point`).
- **Lines** — traverses, contacts (`Placemark`/`LineString`).
- **Polygons** — claim boundaries, geology polygons (`Placemark`/`Polygon`).
- **Geotagged photos / linked attachments** — `PhotoOverlay` placemarks,
  and plain `Placemark`s with a photo (or other file) attached via a
  `description`-embedded `<img>`/`<a>` reference (as opposed to a
  `Style`/`IconStyle`/`Icon` marker pin, which is never treated as an
  attachment), attached as files on their corresponding point location in
  geoh5. A placemark may have more than one attachment.
- **Attributes** — `ExtendedData`/`Schema` fields and `description` text on
  any placemark, mapped to geoh5py `Data`.
- Out of scope for v1 (explicitly deferred): building `Drillhole` objects
  from collar placemarks (existing prototype in
  `kmz2geoh5.py` kept as reference for a future iteration),
  `GroundOverlay`/image-drape overlays, `NetworkLink`/`Tour` elements,
  and KML styling (icons/colors) beyond what's needed to locate photos.

## 5. Reprojection Handling

- KML/KMZ coordinates are always WGS84 geographic (EPSG:4326) per the KML
  spec — no CRS auto-detection needed on the input side.
- The target CRS is **always explicitly supplied by the caller** as an EPSG
  code (e.g., `26911` for UTM Zone 11N/NAD83) — no auto-detection of UTM
  zone from geometry extent.
- Reprojection performed via `GeoDataFrame.to_crs(epsg=target_epsg)`
  (pyproj-backed) on each GeoDataFrame (points/lines/polygons) before
  building geoh5py objects, so geoh5py always receives coordinates already
  in the target projected CRS.
- Validate the target EPSG code up front (e.g., via `pyproj.CRS.from_epsg`)
  and raise a clear error before any conversion work if invalid.
- Store the target EPSG/CRS metadata on the geoh5py Workspace (e.g., as a
  comment/metadata field) so downstream users know the projection used.
- **Elevation (z-coordinate) handling**: KML coordinates may carry a third
  (altitude) value. This library always passes through whatever raw
  z-value is present in the source geometry -- for points, lines, and
  polygons alike -- unchanged by reprojection (a 2D-to-2D UTM transform
  does not alter z). No attempt is made to interpret KML's
  `altitudeMode` (`absolute`/`relativeToGround`/`clampToGround`) or to
  resolve "true" ground elevation via an external DEM: even under
  `clampToGround` (the default when no `altitudeMode` is given, under
  which Google Earth itself ignores the stored altitude and visually
  clamps the feature to terrain), the raw z-value is still carried
  through as-is. Placemarks with no z-value at all default to `z=0`.
  Geometry within a single KML layer may freely mix 2D and 3D features;
  each vertex's z is resolved independently rather than assumed uniform
  across a layer.

## 6. Testing

- `pytest`, using:
  - The real example KMZ in `example_data/` (`OT Oct 2024.kmz`) as an
    integration fixture — verifying end-to-end `convert()` produces a
    valid `.geoh5` with expected object counts. (`Ekati_2024_field.kmz`
    was removed from the repo — at ~560MB with dozens of embedded photos
    it made conversions far too slow for iterative testing on this
    Drive-synced checkout; it is not needed since `OT Oct 2024.kmz`
    already exercises points/folders/attributes.)
  - Small synthetic KML/KMZ fixtures under `tests/fixtures/synthetic/` for
    targeted edge cases: nested folders, missing `ExtendedData`, a
    `PhotoOverlay` with a missing image, mixed geometry types in one
    folder, invalid EPSG code.
- Hatch-managed test environment/script (`hatch run test`) wired into
  `pyproject.toml`, run from inside the `kmz2geoh5` conda/mamba
  environment (activate it first so GDAL/Fiona/pyproj binaries resolve
  correctly).

## Notes / Open Items to Revisit During Implementation

- Confirm actual GDAL/Fiona KML driver behavior on this machine (layer
  splitting per folder, ExtendedData exposure) before finalizing the
  GeoPandas parsing code — adjust the "manual XML pass" scope accordingly.
- Confirm geoh5py's exact API for attaching arbitrary files to `Points`
  vertices (`add_file` is used for `Drillhole` in the prototype; verify
  equivalent support for `Points`).
