"""Configuration: loads env vars for API keys and polling intervals."""

import os
from dotenv import load_dotenv

load_dotenv()

# Gemini Vision API
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# OpenSky Network (optional auth for higher rate limits)
OPENSKY_USERNAME: str = os.getenv("OPENSKY_USERNAME", "")
OPENSKY_PASSWORD: str = os.getenv("OPENSKY_PASSWORD", "")

# Satellite / Planet Labs
PLANET_API_KEY: str = os.getenv("PLANET_API_KEY", "")
SENTINEL_HUB_CLIENT_ID: str = os.getenv("SENTINEL_HUB_CLIENT_ID", "")
SENTINEL_HUB_CLIENT_SECRET: str = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "")

# Polling intervals (seconds)
AIRCRAFT_POLL_INTERVAL: int = int(os.getenv("AIRCRAFT_POLL_INTERVAL", "10"))
CAMERA_POLL_INTERVAL: int = int(os.getenv("CAMERA_POLL_INTERVAL", "5"))
SATELLITE_POLL_INTERVAL: int = int(os.getenv("SATELLITE_POLL_INTERVAL", "60"))

# Bounding box for area of interest [min_lon, min_lat, max_lon, max_lat]
BBOX: list[float] = [
    float(x)
    for x in os.getenv("BBOX", "-105.5,39.5,-104.5,40.2").split(",")
]
