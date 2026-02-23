# Geospatial Tracker — CLAUDE.md

A real-time geospatial tracking system that fuses live aircraft ADS-B data,
traffic camera feeds (analyzed by Google Gemini Vision), and satellite imagery
into a single Mapbox GL map. The backend broadcasts a unified GeoJSON
FeatureCollection over WebSocket every 10 seconds.

## Repository Layout

```
geospatial-tracker/
├── backend/                    # Python / FastAPI service
│   ├── main.py                 # FastAPI app, WebSocket hub, broadcast loop
│   ├── config.py               # Env var loading (dotenv)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── analysis/
│   │   ├── gemini_client.py    # Google Gemini 2.0 Flash vision wrapper
│   │   └── panoptic.py         # Orchestrates ingestion → detection → GeoJSON
│   ├── ingestion/
│   │   ├── opensky.py          # OpenSky Network REST API client (aircraft)
│   │   ├── traffic_cams.py     # Caltrans DOT camera JPEG snapshots
│   │   └── satellite.py        # Sentinel-2 / Planet Labs stubs (NOT implemented)
│   └── models/
│       └── schemas.py          # Pydantic v2 models: AircraftPosition, Detection, DetectionResponse
├── frontend/                   # React + TypeScript + Vite
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx             # Root — renders <LiveMap />
│   │   ├── components/
│   │   │   ├── LiveMap.tsx     # Main map component; WebSocket + Mapbox integration
│   │   │   ├── PlaneLayer.tsx  # GeoJSON layer for aircraft (unused by LiveMap currently)
│   │   │   ├── VehicleLayer.tsx# GeoJSON layer for vehicles (unused by LiveMap currently)
│   │   │   └── CameraPanel.tsx # Sidebar for camera detection results (unused currently)
│   │   └── hooks/
│   │       └── useWebSocket.ts # Auto-reconnecting WebSocket hook (unused by LiveMap currently)
│   ├── vite.config.ts          # Proxies /ws → ws://localhost:8000
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml          # Orchestrates backend (8000) + frontend (5173)
├── .gitignore
└── CLAUDE.md
```

## Architecture

### Data Flow

```
OpenSky REST API ──────────────────────────────────────┐
                                                        │
Caltrans DOT JPEGs → Gemini 2.0 Flash (panoptic) ─────┤
                                                        ▼
                                            panoptic.run_detection_cycle()
                                                        │
                                            GeoJSON FeatureCollection
                                                        │
                                  FastAPI WebSocket (/ws/live)
                                                        │
                                    broadcast to all connected clients
                                                        │
                                        React LiveMap.tsx
                                                        │
                                    Mapbox GL JS (dark-v11 style)
```

### Backend (`backend/`)

- **`main.py`**: FastAPI app with a single WebSocket endpoint `/ws/live` and a
  background `broadcast_loop` that fires every 10 seconds. A `/health` GET
  endpoint is also provided for Docker health checks.
- **`config.py`**: Loads all configuration from environment variables via
  `python-dotenv`. All API keys and polling intervals live here.
- **`analysis/panoptic.py`**: The orchestrator. Calls `fetch_aircraft()` for
  structured aircraft data (no vision needed), then `capture_frame()` for each
  configured camera, sends frames to Gemini in parallel via `asyncio.gather`,
  and assembles a single GeoJSON FeatureCollection.
- **`analysis/gemini_client.py`**: Wraps `google-genai`. Sends a system prompt
  instructing Gemini to return structured JSON detections with lat/lon
  estimates derived from camera metadata (position, heading, FOV).
- **`ingestion/opensky.py`**: Calls `https://opensky-network.org/api/states/all`
  with bounding-box params. Maps the positional state vector array to
  `AircraftPosition` Pydantic models.
- **`ingestion/traffic_cams.py`**: Downloads JPEG snapshots from public Caltrans
  camera URLs. Currently configured with two LA-area feeds: `I-405_LAX` and
  `I-5_Downtown`.
- **`ingestion/satellite.py`**: **Stub only — both `_fetch_sentinel_tile()` and
  `_fetch_planet_tile()` raise `NotImplementedError`.** Also imports
  `SatelliteTile` from `schemas.py`, which is not yet defined there — this
  module will cause an `ImportError` if imported directly.

### Frontend (`frontend/`)

- **`LiveMap.tsx`**: Initialises a Mapbox GL map centered on Los Angeles
  (matching the Caltrans camera feeds), adds two layers (`aircraft-layer`,
  `vehicle-layer`), and connects directly to `ws://localhost:8000/ws/live`.
  On each WebSocket message it calls `source.setData(geojson)` to update the
  map in place.
- **`PlaneLayer.tsx`, `VehicleLayer.tsx`, `CameraPanel.tsx`**: Standalone
  reusable components that exist but are **not currently wired into `App.tsx`
  or `LiveMap.tsx`**. They are intended for a refactor that separates map
  layer management from the main component.
- **`useWebSocket.ts`**: Auto-reconnecting hook (3 s retry). Also currently
  unused by `LiveMap.tsx`, which manages its own WebSocket inline.

## Environment Variables

Create a `.env` file in the **project root** (`geospatial-tracker/.env`). Both
the backend and frontend read from this file (backend via `python-dotenv`,
frontend via Vite's `envDir: ".."` setting).

```dotenv
# ── Required ───────────────────────────────────────────────────────────────
GEMINI_API_KEY=your_google_gemini_api_key
VITE_MAPBOX_TOKEN=your_mapbox_public_token

# ── Optional: OpenSky auth (increases rate limit from 5 req/10s to 1 req/5s)
OPENSKY_USERNAME=
OPENSKY_PASSWORD=

# ── Optional: Satellite imagery (backend/ingestion/satellite.py — stubs only)
PLANET_API_KEY=
SENTINEL_HUB_CLIENT_ID=
SENTINEL_HUB_CLIENT_SECRET=

# ── Tuning ─────────────────────────────────────────────────────────────────
AIRCRAFT_POLL_INTERVAL=10     # seconds
CAMERA_POLL_INTERVAL=5        # seconds (not yet used by broadcast_loop)
SATELLITE_POLL_INTERVAL=60    # seconds (not yet used)

# Bounding box [min_lon, min_lat, max_lon, max_lat]
# Default is Denver area; camera feeds are currently LA-based (mismatch — see Known Issues)
BBOX=-105.5,39.5,-104.5,40.2
```

## Development Workflows

### Docker Compose (recommended)

```bash
# From project root
cp .env.example .env   # fill in keys
docker compose up --build
```

- Backend: http://localhost:8000 (uvicorn + `--reload`)
- Frontend: http://localhost:5173 (Vite dev server)

### Local (no Docker)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The app must be run as a module from the project root so that `backend.*`
imports resolve correctly:

```bash
# From geospatial-tracker/ (project root)
uvicorn backend.main:app --reload --port 8000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev        # Vite dev server on :5173; /ws proxied to :8000
```

### Frontend Build & Type-Check

```bash
cd frontend
npm run build      # tsc + vite build → dist/
npm run lint       # eslint src --ext ts,tsx
```

TypeScript is strict (`strict: true`, `noUnusedLocals`, `noUnusedParameters`).
Fix all type errors before committing.

## Key Conventions

### Python (backend)

- **Python 3.12**; type annotations on every function signature.
- **Pydantic v2** for all data models. Keep models in `backend/models/schemas.py`.
- **Async throughout**: all I/O functions are `async def`; use `httpx.AsyncClient`.
- `config.py` is the single source of truth for configuration — never hardcode
  keys or intervals elsewhere.
- Errors in ingestion or analysis are caught and logged with `print(...)` so
  a single failed camera does not kill the broadcast cycle.
- The Gemini response parser strips markdown fences (```` ```json ```` etc.)
  before parsing; keep this robustness if modifying `gemini_client.py`.
- `backend/__init__.py` is empty — required for the package to be importable
  as `backend.*` from the project root.

### TypeScript / React (frontend)

- **React 18** with function components and hooks only — no class components.
- **Strict TypeScript** (`ES2020` target, `moduleResolution: bundler`).
- Mapbox GL sources and layers are managed imperatively inside `useEffect`.
  Use `sourceAdded` refs to avoid re-adding sources on re-renders.
- Map layer components (`PlaneLayer`, `VehicleLayer`) return `null` — they are
  purely side-effectful map layer managers, not visual React elements.
- GeoJSON data flows: backend GeoJSON → WebSocket → `source.setData()` —
  do not convert to React state unnecessarily.
- Inline styles are used throughout (no CSS framework); keep styling consistent
  with the dark terminal aesthetic (`#1a1a2e`, `#00d4ff`, `#00ff88` palette).
- `VITE_MAPBOX_TOKEN` must be prefixed with `VITE_` to be exposed to the
  browser bundle.

### GeoJSON Contract

All backend-to-frontend data is a **GeoJSON `FeatureCollection`**. Each feature
`properties` object must include at minimum:

| Property    | Type   | Description                                        |
|-------------|--------|----------------------------------------------------|
| `category`  | string | `"aircraft"`, `"vehicles"`, `"pedestrians"`, etc. |
| `source`    | string | `"opensky"` or `"camera:<camera_id>"`              |
| `confidence`| float  | 0–1 (camera detections only)                       |

Aircraft features also include: `callsign`, `altitude`, `velocity`, `heading`,
`on_ground`.

## Known Issues & TODOs

1. **`satellite.py` is broken**: It imports `SatelliteTile` from `schemas.py`,
   which doesn't exist. Both fetch functions raise `NotImplementedError`. Do
   not import this module until it is implemented.

2. **BBOX / camera region mismatch**: The default `BBOX` env var targets Denver
   (`-105.5,39.5,-104.5,40.2`) but the Caltrans camera feeds are in Los Angeles.
   Either align `BBOX` to LA or update the camera feed list to match.

3. **`useWebSocket` hook is unused**: `LiveMap.tsx` manages its own WebSocket
   inline. The `PlaneLayer`, `VehicleLayer`, and `CameraPanel` components are
   also unused. A planned refactor should wire these together.

4. **`CAMERA_POLL_INTERVAL` / `SATELLITE_POLL_INTERVAL`** are read from env but
   not used — `broadcast_loop` always sleeps 10 seconds regardless.

5. **No authentication on WebSocket**: `/ws/live` is open to any origin.
   `CORSMiddleware` is set to `allow_origins=["*"]`.

6. **`@app.on_event("startup")` is deprecated** in newer FastAPI. Migrate to
   `lifespan` context manager when upgrading FastAPI.

## API Reference

### WebSocket: `ws://localhost:8000/ws/live`

Emits a GeoJSON `FeatureCollection` every ~10 seconds. The client should send
keep-alive pings (any text) to maintain the connection.

### HTTP: `GET /health`

Returns `{"status": "ok"}` when the backend is running.

## External Services

| Service | Purpose | Auth |
|---------|---------|------|
| OpenSky Network | Live aircraft state vectors | Optional (username/password) |
| Caltrans DOT CCTV | Traffic camera JPEG snapshots | None (public) |
| Google Gemini 2.0 Flash | Panoptic vision detection | `GEMINI_API_KEY` |
| Mapbox GL JS | Map tiles and rendering | `VITE_MAPBOX_TOKEN` |
| Planet Labs (stub) | Satellite imagery | `PLANET_API_KEY` |
| Sentinel Hub (stub) | Sentinel-2 satellite imagery | Client ID + Secret |
