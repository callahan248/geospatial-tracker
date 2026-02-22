"""Wraps the Google Generative AI vision API for panoptic object detection."""

import json
import base64
from google import genai
from google.genai import types
from backend.config import GEMINI_API_KEY
from backend.models.schemas import Detection, DetectionResponse

PANOPTIC_SYSTEM_PROMPT = """You are an advanced geospatial analyst model.
Analyze the provided image and detect ALL visible objects in these categories:
- vehicles (cars, trucks, buses, motorcycles)
- aircraft (planes, helicopters)
- pedestrians
- infrastructure (bridges, intersections)

For each detected object, return:
1. category (string)
2. estimated_lat and estimated_lon (float) — infer from camera metadata provided
3. confidence (float, 0-1)
4. bounding_box (optional, [x1, y1, x2, y2] in pixel coords)
5. attributes (color, direction, estimated_speed if moving)

Return ONLY valid JSON. No markdown. No explanation.
Format: {"detections": [...]}"""


class GeminiClient:
    """Thin wrapper around google-genai for panoptic vision-based detection."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=GEMINI_API_KEY)

    async def analyze_frame(
        self,
        image_bytes: bytes,
        camera_lat: float,
        camera_lon: float,
        camera_heading: float = 0,
        fov_degrees: float = 90,
    ) -> list[Detection]:
        """
        Sends a camera frame to Gemini for panoptic detection.
        Camera metadata helps Gemini estimate real-world coordinates.
        """
        context = (
            f"Camera metadata:\n"
            f"- Position: ({camera_lat}, {camera_lon})\n"
            f"- Heading: {camera_heading}° from North\n"
            f"- Field of view: {fov_degrees}°\n"
            f"- Image type: Traffic camera JPEG snapshot\n\n"
            f"Use this metadata to estimate real-world lat/lon for each detected object."
        )

        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

        response = self._client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[PANOPTIC_SYSTEM_PROMPT, context, image_part],
        )

        raw = response.text or "{}"
        # Strip markdown fences if present
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            data = json.loads(raw)
            validated = DetectionResponse(
                detections=data if isinstance(data, list) else data.get("detections", [])
            )
            return validated.detections
        except Exception:
            return []
