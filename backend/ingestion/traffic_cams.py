"""Fetches snapshots from public DOT traffic camera feeds."""

import httpx
from datetime import datetime

# Public Caltrans traffic camera snapshot URLs
CAMERA_FEEDS: dict[str, dict] = {
    "I-405_LAX": {
        "url": "https://cwwp2.dot.ca.gov/data/d7/cctv/image/i405-lax/i405-lax.jpg",
        "lat": 33.9425,
        "lon": -118.4081,
        "heading": 0,
        "fov_degrees": 90,
    },
    "I-5_Downtown": {
        "url": "https://cwwp2.dot.ca.gov/data/d7/cctv/image/i5-downtown/i5-downtown.jpg",
        "lat": 34.0522,
        "lon": -118.2437,
        "heading": 0,
        "fov_degrees": 90,
    },
}


async def capture_frame(camera_id: str) -> dict:
    """Downloads a single JPEG frame from a public traffic camera."""
    cam = CAMERA_FEEDS[camera_id]
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(cam["url"])
        resp.raise_for_status()
        return {
            "camera_id": camera_id,
            "image_bytes": resp.content,
            "lat": cam["lat"],
            "lon": cam["lon"],
            "heading": cam.get("heading", 0),
            "fov_degrees": cam.get("fov_degrees", 90),
            "captured_at": datetime.utcnow().isoformat(),
        }
