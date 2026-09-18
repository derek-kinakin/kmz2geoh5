"""Builders for small, hand-crafted synthetic KML/KMZ fixtures used by the
test suite to exercise edge cases (nested folders, missing attributes,
PhotoOverlay with a missing image, mixed geometry types, etc.).

Fixtures are generated programmatically (rather than committed as binary
``.kmz`` blobs) so their exact contents are easy to review and adjust
alongside the tests that use them.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

_KML_NS = "http://www.opengis.net/kml/2.2"

# Placeholder "photo" bytes used to exercise the PhotoOverlay file-attachment
# path in tests. Content does not need to be a valid image for the purposes
# of exercising add_file()/FilenameData round-tripping.
_TINY_JPEG_BYTES = b"\xff\xd8\xff\xe0FAKE-JPEG-BYTES-FOR-TESTING\xff\xd9"


def build_kml() -> str:
    """Return a KML document exercising the edge cases the test suite
    covers: nested folders, a mix of geometry types, ExtendedData, missing
    attributes, and PhotoOverlay placemarks (one with a resolvable image,
    one referencing an image that is not bundled in the archive)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <name>Synthetic Fixture</name>
    <Folder>
      <name>Stations</name>
      <Placemark>
        <name>Station A</name>
        <ExtendedData>
          <Data name="sample_id"><value>S-001</value></Data>
          <Data name="grade_pct"><value>4.2</value></Data>
        </ExtendedData>
        <Point><coordinates>-115.0,51.0,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Station B</name>
        <Point><coordinates>-115.001,51.001,0</coordinates></Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Traverse</name>
      <Placemark>
        <name>Line 1</name>
        <LineString>
          <coordinates>-115.01,51.01,0 -115.011,51.012,0 -115.012,51.013,0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>Boundary</name>
      <Placemark>
        <name>Claim 1</name>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                -115.02,51.02,0 -115.021,51.02,0 -115.021,51.021,0 -115.02,51.021,0 -115.02,51.02,0
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
    <Folder>
      <name>FieldPhotos</name>
      <Placemark>
        <name>Field Photo Station</name>
        <Style>
          <IconStyle>
            <Icon><href>icons/marker.png</href></Icon>
          </IconStyle>
        </Style>
        <description><![CDATA[<img src="photos/photo2.jpg" height="300" />]]>Outcrop photo</description>
        <Point><coordinates>-115.07,51.07,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Marker Only Station</name>
        <Style>
          <IconStyle>
            <Icon><href>icons/marker.png</href></Icon>
          </IconStyle>
        </Style>
        <Point><coordinates>-115.071,51.071,0</coordinates></Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Mixed</name>
      <Placemark>
        <name>Mixed Point</name>
        <Point><coordinates>-115.03,51.03,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Mixed Line</name>
        <LineString>
          <coordinates>-115.031,51.031,0 -115.032,51.032,0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>Region</name>
      <Folder>
        <name>SubRegion</name>
        <Placemark>
          <name>Nested Point</name>
          <Point><coordinates>-115.04,51.04,0</coordinates></Point>
        </Placemark>
      </Folder>
    </Folder>
    <Folder>
      <name>DK 1</name>
      <Placemark>
        <name>DK 1</name>
        <Point><coordinates>-115.09,51.09,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Note</name>
        <description>Parallel structures on north wall</description>
        <Point><coordinates>-115.0901,51.0901,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>Image</name>
        <description><![CDATA[<img src="photos/locality_photo.jpg" height="300" />]]>Outcrop overview</description>
        <Point><coordinates>-115.0902,51.0902,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>35°</name>
        <description>35° / 245°&#10;RHY&#10;Bedding&#10;&#10;&#10;Declination: -4.99°</description>
        <Point><coordinates>-115.0903,51.0903,0</coordinates></Point>
      </Placemark>
      <Placemark>
        <name>68°</name>
        <description>68° / 205°&#10;QMD&#10;Joint&#10;&#10;&#10;Declination: -4.99°</description>
        <Point><coordinates>-115.0904,51.0904,0</coordinates></Point>
      </Placemark>
    </Folder>
    <PhotoOverlay>
      <name>Photo With Image</name>
      <Icon><href>photos/photo1.jpg</href></Icon>
      <Point><coordinates>-115.05,51.05,0</coordinates></Point>
    </PhotoOverlay>
    <PhotoOverlay>
      <name>Photo Missing Image</name>
      <Icon><href>photos/missing.jpg</href></Icon>
      <Point><coordinates>-115.06,51.06,0</coordinates></Point>
    </PhotoOverlay>
    <Placemark>
      <name>Image</name>
      <description><![CDATA[<img src="photos/photo1.jpg" height="300" />]]>Duplicate name 1</description>
      <Point><coordinates>-115.08,51.08,0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Image</name>
      <description><![CDATA[<img src="photos/photo1.jpg" height="300" />]]>Duplicate name 2</description>
      <Point><coordinates>-115.081,51.081,0</coordinates></Point>
    </Placemark>
  </Document>
</kml>
"""


def write_synthetic_kmz(path: Path) -> Path:
    """Write the synthetic fixture KML (plus its bundled photos, matching
    the "Photo With Image" and "Field Photo Station" placemarks) to a
    ``.kmz`` file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w") as kmz:
        kmz.writestr("doc.kml", build_kml())
        kmz.writestr("photos/photo1.jpg", _TINY_JPEG_BYTES)
        kmz.writestr("photos/photo2.jpg", _TINY_JPEG_BYTES)
        kmz.writestr("photos/locality_photo.jpg", _TINY_JPEG_BYTES)
    return path


def build_elevation_kml() -> str:
    """Return a KML document exercising 3D (elevation-bearing) geometry:
    a point, a line, and a polygon, each with non-zero ``z`` coordinates,
    plus points covering the ``altitudeMode`` variants (``absolute``,
    ``relativeToGround``, ``clampToGround``, and no ``altitudeMode`` tag at
    all, which defaults to ``clampToGround`` per the KML spec)."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="{_KML_NS}">
  <Document>
    <name>Elevation Fixture</name>
    <Folder>
      <name>Points</name>
      <Placemark>
        <name>Absolute Point</name>
        <Point>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>-115.0,51.0,1500.0</coordinates>
        </Point>
      </Placemark>
      <Placemark>
        <name>RelativeToGround Point</name>
        <Point>
          <altitudeMode>relativeToGround</altitudeMode>
          <coordinates>-115.001,51.001,50.0</coordinates>
        </Point>
      </Placemark>
      <Placemark>
        <name>ClampToGround Point With Z</name>
        <Point>
          <altitudeMode>clampToGround</altitudeMode>
          <coordinates>-115.002,51.002,9999.0</coordinates>
        </Point>
      </Placemark>
      <Placemark>
        <name>No AltitudeMode With Z</name>
        <Point>
          <coordinates>-115.003,51.003,1234.0</coordinates>
        </Point>
      </Placemark>
      <Placemark>
        <name>No Z At All</name>
        <Point>
          <coordinates>-115.004,51.004</coordinates>
        </Point>
      </Placemark>
    </Folder>
    <Folder>
      <name>Lines</name>
      <Placemark>
        <name>Absolute Line</name>
        <LineString>
          <altitudeMode>absolute</altitudeMode>
          <coordinates>-115.01,51.01,100.0 -115.011,51.011,200.0</coordinates>
        </LineString>
      </Placemark>
    </Folder>
    <Folder>
      <name>Polygons</name>
      <Placemark>
        <name>Absolute Polygon</name>
        <Polygon>
          <altitudeMode>absolute</altitudeMode>
          <outerBoundaryIs>
            <LinearRing>
              <coordinates>
                -115.02,51.02,300 -115.021,51.02,300 -115.021,51.021,310 -115.02,51.021,310 -115.02,51.02,300
              </coordinates>
            </LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </Placemark>
    </Folder>
  </Document>
</kml>
"""


def write_elevation_kmz(path: Path) -> Path:
    """Write the 3D/elevation fixture KML to a ``.kmz`` file at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w") as kmz:
        kmz.writestr("doc.kml", build_elevation_kml())
    return path
