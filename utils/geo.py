"""Geolocation helpers – haversine distance and item annotation."""
import math


def haversine_km(lat1, lon1, lat2, lon2):
    """Return great-circle distance in km between two points, rounded to 1 decimal."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)


def attach_distances(items, lat, lng):
    """Set item.distance_km on each item. None when coords are missing (sorted last)."""
    for item in items:
        if lat is not None and lng is not None and item.lat is not None and item.lng is not None:
            item.distance_km = haversine_km(lat, lng, item.lat, item.lng)
        else:
            item.distance_km = None
    return items
