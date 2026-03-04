"""FastAPI application — WebSocket hub broadcasting live GeoJSON."""

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.analysis.panoptic import run_detection_cycle
from backend import control

app = FastAPI(title="Geospatial Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: list[WebSocket] = []

# Set when a manual trigger is requested; cleared after each broadcast
_trigger = asyncio.Event()


@app.websocket("/ws/live")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive ping/pong
    except WebSocketDisconnect:
        connected_clients.remove(ws)


async def broadcast_loop() -> None:
    """Runs every N seconds (or on manual trigger) — pulls data, analyzes, broadcasts GeoJSON."""
    while True:
        try:
            geojson = await run_detection_cycle(
                sources=control.state.sources,
                bbox=control.state.bbox,
            )
            payload = json.dumps(geojson)
            dead: list[WebSocket] = []
            for client in connected_clients.copy():
                try:
                    await client.send_text(payload)
                except Exception:
                    dead.append(client)
            for client in dead:
                connected_clients.remove(client)
        except Exception as exc:
            print(f"Broadcast cycle error: {exc}")

        # Sleep for the configured interval, but wake early on manual trigger
        try:
            await asyncio.wait_for(_trigger.wait(), timeout=control.state.interval)
            _trigger.clear()
        except asyncio.TimeoutError:
            pass


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(broadcast_loop())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Control endpoints ──────────────────────────────────────────────────────

@app.get("/control/state")
async def get_state() -> dict:
    return {
        "interval": control.state.interval,
        "sources": control.state.sources,
        "bbox": control.state.bbox,
    }


class IntervalRequest(BaseModel):
    seconds: int


@app.post("/control/interval")
async def set_interval(req: IntervalRequest) -> dict:
    control.state.interval = max(5, min(300, req.seconds))
    return {"interval": control.state.interval}


class SourcesRequest(BaseModel):
    aircraft: bool | None = None
    cameras: bool | None = None


@app.post("/control/sources")
async def set_sources(req: SourcesRequest) -> dict:
    if req.aircraft is not None:
        control.state.sources["aircraft"] = req.aircraft
    if req.cameras is not None:
        control.state.sources["cameras"] = req.cameras
    return {"sources": control.state.sources}


class BboxRequest(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


@app.post("/control/bbox")
async def set_bbox(req: BboxRequest) -> dict:
    control.state.bbox = [req.min_lon, req.min_lat, req.max_lon, req.max_lat]
    return {"bbox": control.state.bbox}


@app.post("/control/trigger")
async def trigger_cycle() -> dict:
    """Force an immediate detection cycle without waiting for the interval."""
    _trigger.set()
    return {"triggered": True}
