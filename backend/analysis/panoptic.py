"""Orchestrates ingestion + Gemini analysis into a unified GeoJSON payload."""

import asyncio
from backend.analysis.gemini_client import GeminiClient
from backend.ingestion.traffic_cams import capture_frame, CAMERA_FEEDS
from backend.ingestion.opensky import fetch_aircraft

_gemini: GeminiClient | None = None


def _get_gemini() -> GeminiClient:
    global _gemini
    if _gemini is None:
        _gemini = GeminiClient()
    return _gemini


async def run_detection_cycle(
    sources: dict[str, bool] | None = None,
    bbox: list[float] | None = None,
) -> dict:
    """
    One full detection cycle:
    1. Pull aircraft data from OpenSky (structured API — no vision needed)
    2. Capture frames from all traffic cameras
    3. Send each frame to Gemini for panoptic detection
    4. Merge all results into a single GeoJSON FeatureCollection

    Args:
        sources: Which sources to enable, e.g. {"aircraft": True, "cameras": False}.
                 Defaults to both enabled.
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat] for aircraft fetch.
              Defaults to config BBOX.
    """
    if sources is None:
        sources = {"aircraft": True, "cameras": True}

    features: list[dict] = []

    # Aircraft data is already structured — no Gemini needed
    if sources.get("aircraft", True):
        opensky_bbox: dict | None = None
        if bbox is not None:
            min_lon, min_lat, max_lon, max_lat = bbox
            opensky_bbox = {
                "lamin": min_lat,
                "lomin": min_lon,
                "lamax": max_lat,
                "lomax": max_lon,
            }
        aircraft = await fetch_aircraft(bbox=opensky_bbox)
        for ac in aircraft:
            if ac.latitude is not None and ac.longitude is not None:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [ac.longitude, ac.latitude]},
                    "properties": {
                        "category": "aircraft",
                        "callsign": ac.callsign,
                        "altitude": ac.altitude,
                        "velocity": ac.velocity,
                        "heading": ac.heading,
                        "on_ground": ac.on_ground,
                        "source": "opensky",
                    },
                })

    # Traffic cam analysis — capture all frames first, then analyze in parallel
    if sources.get("cameras", True):
        frames: list[dict] = []
        for cam_id in CAMERA_FEEDS:
            try:
                frame = await capture_frame(cam_id)
                frames.append(frame)
            except Exception as exc:
                print(f"Camera {cam_id} capture failed: {exc}")

        camera_tasks = [
            _get_gemini().analyze_frame(
                image_bytes=f["image_bytes"],
                camera_lat=f["lat"],
                camera_lon=f["lon"],
                camera_heading=f.get("heading", 0),
                fov_degrees=f.get("fov_degrees", 90),
            )
            for f in frames
        ]
        all_detections = await asyncio.gather(*camera_tasks, return_exceptions=True)

        # Gemini camera detection features
        for frame, detections in zip(frames, all_detections):
            if isinstance(detections, Exception):
                print(f"Gemini analysis failed for {frame['camera_id']}: {detections}")
                continue
            for det in detections:
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [det.estimated_lon, det.estimated_lat],
                    },
                    "properties": {
                        "category": det.category,
                        "confidence": det.confidence,
                        "attributes": det.attributes,
                        "source": f"camera:{frame['camera_id']}",
                        "source_model": "gemini-2.0-flash",
                    },
                })

    return {"type": "FeatureCollection", "features": features}
