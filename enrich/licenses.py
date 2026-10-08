"""Which image licenses the app may show, normalised to a short label.

Allowed (decided 2026-10-07): public domain / CC0, CC BY, CC BY-SA, and the NonCommercial variants
CC BY-NC and CC BY-NC-SA, always shown with credit. NoDerivatives licenses are excluded because the
app shows resized thumbnails. Anything unrecognised ("Usage Conditions Apply", fair use, missing) is
excluded.
"""

import re

ALLOWED = {"CC0", "Public domain", "CC BY", "CC BY-SA", "CC BY-NC", "CC BY-NC-SA"}

_CC_URL = re.compile(r"creativecommons\.org/licenses/([a-z-]+)/([\d.]+)?", re.IGNORECASE)
_CC_TEXT = re.compile(r"^\s*cc[\s-]*(by(?:[\s-]*(?:nc|sa|nd))*)(?:[\s-]*([\d.]+))?", re.IGNORECASE)
# GBIF's own names for the three licenses an occurrence record can have (download archives use them)
_GBIF_NAMES = {"CC0_1_0": "CC0", "CC_BY_4_0": "CC BY 4.0", "CC_BY_NC_4_0": "CC BY-NC 4.0"}


def normalise_license(value: str | None) -> str | None:
    """A short label like "CC BY-SA 4.0" or "CC0" from a license URL or name, or None if unknown."""
    if not value:
        return None
    text = value.strip()
    if text in _GBIF_NAMES:
        return _GBIF_NAMES[text]
    lowered = text.lower()
    if "publicdomain/zero" in lowered or re.match(r"^\s*cc[\s-]*0", lowered):
        return "CC0"
    if "publicdomain/mark" in lowered or lowered in {"public domain", "pd"} or lowered.startswith("public domain"):
        return "Public domain"
    match = _CC_URL.search(text) or _CC_TEXT.match(text)
    if not match:
        return None
    parts = [p for p in re.split(r"[\s-]+", match.group(1).upper()) if p]
    label = "CC " + "-".join(parts)
    version = match.group(2)
    return f"{label} {version}" if version else label


def is_allowed(label: str | None) -> bool:
    if not label:
        return False
    base = re.sub(r"\s[\d.]+$", "", label)
    return base in ALLOWED
