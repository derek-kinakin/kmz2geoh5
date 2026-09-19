# kmz2geoh5

Convert Google Earth **KMZ** files into Geoscience Analyst **geoh5**
workspaces.

## Overview

Points, lines, and polygons from KML and KMZ files can be reprojected
from WGS84 (as stored in KML/KMZ) into a user-specified projected coordinate
system (e.g. UTM) and written into a `.geoh5` workspace using `geoh5py`.

## FieldMove Clino Specific Features

KMZ files exported from the mobile app 'FieldMove Clino' are recognized and provided extra treatment:

* The KML folder hierarchy is preserved as nested groups, `ExtendedData` attributes are mapped to per-object data.
* each placemark's `description` text (HTML markup stripped) is attached as a geoh5 `Comments` entry on its geoh5 object (one comment per source placemark, attributed by name via the comment's `Author` field).
* Photos/files are attached to placemarks — whether geotagged `PhotoOverlay` overlays or photos linked in a placemark's `description` (e.g. field photos attached via Google Earth/Google Maps)
* Photos are attached as files on their corresponding point locations, nested under a `Photos` sub-group of the same enclosing KML folder/station as the rest of that folder's geometry (e.g. photos for astation named "DK 16" end up under "DK 16/Photos").
* Discontinuity (fault, joint, plane) measurements are recognized and imported as seperate entites with the orientation data fields added.

## Installation

Install the latest development version directly from GitHub:

```powershell
pip install "kmz2geoh5 @ git+https://github.com/derek-kinakin/kmz2geoh5.git"
```

To install a specific release once version tags are available, append the tag
to the repository URL:

```powershell
pip install "kmz2geoh5 @ git+https://github.com/derek-kinakin/kmz2geoh5.git@v0.1.0"
```

## Usage

```python
from kmz2geoh5 import convert

convert("station_data.kmz", "station_data.geoh5", epsg=26911)
```

## Status

Early development.
