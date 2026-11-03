"""Readable qualification facts for Italy L:P. No purchase scoring, no sender input."""
from typing import Any, Dict, Optional

# Text Search returns at most 10 photos per place, so this is a floor, not a count.
MIN_GOOGLE_PHOTOS = 5
# Not stored, so a reopened business can still be collected by a later search.
SKIPPED_STATUSES = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}


def describe_site(website: str, signals: Optional[Dict[str, Any]]) -> str:
    if not website:
        return "nessun sito"
    if signals is None:
        return "sito non analizzato"
    if not signals.get("fetched"):
        return "sito non raggiungibile"
    parts = []
    if signals["social"]:
        parts.append("social: " + "+".join(signals["social"]))
    parts.append("galleria" if signals["showcase"] else "senza galleria")
    parts.append("video" if signals["video"] else "senza video")
    parts.append("%d %s" % (signals["images"], "immagine" if signals["images"] == 1 else "immagini"))
    return " · ".join(parts)


def hooks(website: str, signals: Optional[Dict[str, Any]], google_photos: Optional[int]) -> str:
    """Video & Slide: photos already exist on Google, but no gallery or video presents them."""
    tags = []
    # An unreachable site is unknown, not a poor presentation.
    presents_poorly = not website or bool(signals and signals.get("fetched")
                                          and not signals["showcase"] and not signals["video"])
    if (google_photos or 0) >= MIN_GOOGLE_PHOTOS and presents_poorly:
        tags.append("foto da valorizzare")
    if not website:
        tags.append("senza sito")
    return " · ".join(tags)
