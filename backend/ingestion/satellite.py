"""Fetches satellite imagery tiles from Sentinel-2 or Planet Labs."""

import httpx
from backend.config import BBOX, PLANET_API_KEY, SENTINEL_HUB_CLIENT_ID, SENTINEL_HUB_CLIENT_SECRET
from backend.models.schemas import SatelliteTile

PLANET_QUICKSEARCH_URL = "https://api.planet.com/data/v1/quick-search"
SENTINEL_HUB_URL = "https://services.sentinel-hub.com/api/v1/process"


async def fetch_tile(source: str = "sentinel2") -> SatelliteTile | None:
    """
    Fetch a satellite tile for the configured bounding box.

    Args:
        source: "sentinel2" or "planet"

    Returns:
        SatelliteTile with image URL, or None if unavailable.
    """
    if source == "planet":
        return await _fetch_planet_tile()
    return await _fetch_sentinel_tile()


async def _fetch_sentinel_tile() -> SatelliteTile | None:
    """Stub: authenticate and pull latest Sentinel-2 RGB tile."""
    # TODO: implement OAuth token exchange + process API call
    raise NotImplementedError("Sentinel-2 tile fetching not yet implemented")


async def _fetch_planet_tile() -> SatelliteTile | None:
    """Stub: search Planet Labs for most recent scene and return asset URL."""
    if not PLANET_API_KEY:
        raise ValueError("PLANET_API_KEY is not set")
    # TODO: implement Planet Labs quick-search + asset activation
    raise NotImplementedError("Planet Labs tile fetching not yet implemented")
