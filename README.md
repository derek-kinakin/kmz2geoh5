# clino_kmz_to_geoh5

Convert Google Earth **KMZ** files into Geoscience Analyst **geoh5**
workspaces.

Points, lines, and polygons from KML `Placemark` geometry are reprojected
from WGS84 (as stored in KML) into a user-specified projected coordinate
system (e.g. UTM) and written into a `.geoh5` workspace using `geoh5py`.
KML folder hierarchy is preserved as nested groups, `ExtendedData`/
`description` attributes are mapped to per-object data, and geotagged
`PhotoOverlay` photos are attached as files on their corresponding point
locations.

See [`PLAN.md`](PLAN.md) for the full design/implementation plan.

## Development setup

This project uses a dedicated conda/mamba environment because
`geopandas`/`fiona`/`GDAL`/`pyproj` are far more reliable to install as
conda-forge binaries than as pip wheels on Windows.

```powershell
# Create the environment (from the repo root)
mamba env create -f environment.yml

# Activate it before running anything else
mamba activate clino-kmz-to-geoh5

# Run tests via Hatch (uses this same active environment)
hatch run test
```

If `mamba` is not available, substitute `conda` for the same commands.

## Usage

```python
from clino_kmz_to_geoh5 import convert

convert("station_data.kmz", "station_data.geoh5", epsg=26911)
```

## Status

Early development. See [`PLAN.md`](PLAN.md) for scope and roadmap.
