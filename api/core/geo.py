"""Coarse location: coordinates in, a district name out. Coordinates are never stored.

shared/districts.csv holds approximate demo centre points (nearest centre wins).
Upgrade path: point-in-polygon with official district boundaries.
"""
import csv
import math
from functools import lru_cache

from django.conf import settings

# Rough box around Uganda; anything outside is ignored.
LAT_RANGE, LON_RANGE = (-1.6, 4.3), (29.4, 35.1)


@lru_cache
def districts():
    with (settings.SHARED_DIR / "districts.csv").open(encoding="utf8") as f:
        return [(r["district"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]


def nearest_district(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
        return None
    return min(districts(), key=lambda d: math.hypot(d[1] - lat, (d[2] - lon) * math.cos(math.radians(lat))))[0]


def district_by_name(name):
    name = (name or "").strip().lower()
    for d, _, _ in districts():
        if d.lower() == name:
            return d
    return None


def centre(name):
    for d, lat, lon in districts():
        if d == name:
            return lat, lon
    return None
