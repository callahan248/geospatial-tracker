"""Fetches live aircraft state vectors from the OpenSky Network REST API."""

import httpx
from backend.config import BBOX, OPENSKY_USERNAME, OPENSKY_PASSWORD
from backend.models.schemas import AircraftPosition

OPENSKY_URL = "https://opensky-network.org/api/states/all"


async def fetch_aircraft(bbox: dict | None = None) -> list[AircraftPosition]:
    """
    Fetches all live aircraft positions from OpenSky.
    bbox: {"lamin": 45.0, "lomin": -125.0, "lamax": 50.0, "lomax": -115.0}
    Rate limit: 5 req/10s (anonymous), 1 req/5s (authenticated)
    """
    min_lon, min_lat, max_lon, max_lat = BBOX
    params = bbox or {
        "lamin": min_lat,
        "lomin": min_lon,
        "lamax": max_lat,
        "lomax": max_lon,
    }
    auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD) if OPENSKY_USERNAME else None

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(OPENSKY_URL, params=params, auth=auth)
        resp.raise_for_status()
        data = resp.json()

    aircraft: list[AircraftPosition] = []
    for state in data.get("states") or []:
        aircraft.append(AircraftPosition(
            icao24=state[0],
            callsign=(state[1] or "").strip(),
            origin_country=state[2] or "",
            longitude=state[5],
            latitude=state[6],
            altitude=state[7],
            velocity=state[9],
            heading=state[10],
            vertical_rate=state[11],
            on_ground=bool(state[8]),
            last_contact=state[4],
        ))

    return aircraft
