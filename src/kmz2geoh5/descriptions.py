"""Cleanup of KML ``description`` HTML for use as geoh5 ``Comments``.

KML placemark ``description`` fields are free-form HTML: Google Earth/
Google Maps commonly embed a ``<img>``/``<a>`` photo attachment (see
:mod:`kmz2geoh5.photo_overlay`) alongside, or instead of, plain prose. This
module strips that markup down to the prose alone, so it can be attached to
geoh5 entities as a human-readable comment rather than raw HTML.
"""

from __future__ import annotations

import re
from html import unescape

# <img ...> tags are dropped entirely -- the photo itself is extracted and
# attached separately (see kmz2geoh5.photo_overlay), so keeping an <img> tag
# (or its absence of visible text) in the comment would add nothing.
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)

# <br> (and <br/>, <br />) become a newline.
_BR_TAG_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

# Any other HTML tag (opening, closing, or self-closing) is stripped, but
# its inner text (e.g. an <a href="...">Link text</a> anchor) is kept.
_OTHER_TAG_RE = re.compile(r"<[^>]+>")

# Three or more consecutive newlines (left behind once tags are stripped)
# collapse down to a single blank line.
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def clean_description_html(text) -> str:
    """Strip photo/anchor markup and other HTML tags out of a KML
    ``description`` value, returning plain, human-readable text suitable
    for a geoh5 comment.

    :param text: Raw ``description`` value (HTML, possibly ``None`` or,
        as pandas/GeoPandas represents a missing string cell, ``NaN``).
    :returns: Cleaned plain text, or ``""`` if ``text`` is empty/missing
        or nothing meaningful remains after stripping markup (e.g. a
        description containing only an ``<img>`` tag).
    """
    if not isinstance(text, str) or not text:
        return ""

    cleaned = _IMG_TAG_RE.sub("", text)
    cleaned = _BR_TAG_RE.sub("\n", cleaned)
    cleaned = _OTHER_TAG_RE.sub("", cleaned)
    cleaned = unescape(cleaned)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    return cleaned.strip()
