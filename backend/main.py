"""FastAPI application — WebSocket hub broadcasting live GeoJSON."""

import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.analysis.panoptic import run_detection_cycle

app = FastAPI(title="Geospatial Tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: list[WebSocket] = []


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
    """Runs every 10 seconds — pulls data, analyzes, broadcasts GeoJSON."""
    while True:
        try:
            geojson = await run_detection_cycle()
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
        await asyncio.sleep(10)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(broadcast_loop())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
