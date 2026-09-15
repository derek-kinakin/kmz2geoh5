"""
Example script using the 'clino_kmz_to_geoh5' library.

"""

from pathlib import Path

# Import dev version of library
import clino_kmz_to_geoh5 as ck2g

# KMZ file path
KMZ_PATH = r"C:\Users\dkinakin\OneDrive - BGC Engineering Inc\DK SFdS_2026-09-08.kmz"
EPSG = 26712

# Script
kmz = Path(KMZ_PATH)
geoh5_path = kmz.with_suffix(".geoh5")
geoh5 = ck2g.convert(kmz, epsg=EPSG, geoh5_path=geoh5_path)
