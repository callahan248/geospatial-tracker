# Geospatial Tracker — CLAUDE.md

A real-time geospatial tracking system that fuses live aircraft ADS-B data,
traffic camera feeds (analyzed by Google Gemini Vision), and satellite imagery
into a single Mapbox GL map. The backend broadcasts a unified GeoJSON
FeatureCollection over WebSocket every 10 seconds.

## Repository Layout

```
geospatial-tracker/
├── backend/                    # Python / FastAPI service
│   ├── __init__.py             # Empty — makes backend importable as a package
│   ├── main.py                 # FastAPI app, WebSocket hub, broadcast loop
│   ├── config.py               # Env var loading (dotenv)
│   ├── requirements.txt
│   ├── Dockerfile              # python:3.12-slim; CMD uvicorn main:app (WORKDIR=/app)
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── gemini_client.py    # Google Gemini 2.0 Flash vision wrapper
│   │   └── panoptic.py         # Orchestrates ingestion → detection → GeoJSON
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── opensky.py          # OpenSky Network REST API client (aircraft)
│   │   ├── traffic_cams.py     # Caltrans DOT camera JPEG snapshots
│   │   └── satellite.py        # Sentinel-2 / Planet Labs stubs (NOT implemented)
│   └── models/
│       ├── __init__.py
│       └── schemas.py          # Pydantic v2 models: AircraftPosition, Detection, DetectionResponse
├── frontend/                   # React + TypeScript + Vite
│   ├── index.html              # Vite entry point
│   ├── src/
│   │   ├── main.tsx            # ReactDOM.createRoot entry
│   │   ├── App.tsx             # Root — renders <LiveMap />
│   │   ├── components/
│   │   │   ├── LiveMap.tsx     # Main map component; WebSocket + Mapbox integration
│   │   │   ├── PlaneLayer.tsx  # GeoJSON layer for aircraft (unused by LiveMap currently)
│   │   │   ├── VehicleLayer.tsx# GeoJSON layer for vehicles (unused by LiveMap currently)
│   │   │   └── CameraPanel.tsx # Sidebar for camera detection results (unused currently)
│   │   └── hooks/
│   │       └── useWebSocket.ts # Auto-reconnecting WebSocket hook (unused by LiveMap currently)
│   ├── vite.config.ts          # Proxies /ws → ws://localhost:8000; envDir: ".."
│   ├── tsconfig.json
│   ├── package.json            # mapbox-gl ^3.3, react ^18.3, typescript ^5.4
│   └── Dockerfile              # node:20-slim; CMD npm run dev -- --host
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
                                    Mapbox GL JS v3 (dark-v11 style)
```

### Backend (`backend/`)

- **`main.py`**: FastAPI app with a single WebSocket endpoint `/ws/live` and a
  background `broadcast_loop` that fires every 10 seconds (hardcoded
  `asyncio.sleep(10)`). A `/health` GET endpoint returns `{"status": "ok"}`.
  Uses the deprecated `@app.on_event("startup")` decorator to start the loop.
- **`config.py`**: Loads all configuration from environment variables via
  `python-dotenv`. All API keys and polling intervals live here. `BBOX` is
  parsed into `list[float]` — `[min_lon, min_lat, max_lon, max_lat]`.
- **`analysis/panoptic.py`**: The orchestrator. Holds a module-level
  `_gemini: GeminiClient | None = None` singleton, lazily initialized by
  `_get_gemini()`. Calls `fetch_aircraft()` first, then `capture_frame()` for
  each key in `CAMERA_FEEDS`, collects frames, and sends all frames to
  `GeminiClient.analyze_frame` in parallel via `asyncio.gather`. Assembles a
  single GeoJSON FeatureCollection.
- **`analysis/gemini_client.py`**: Wraps `google-genai` (`from google import genai`).
  `analyze_frame` is declared `async def` but calls `self._client.models.generate_content()`
  **synchronously** — this blocks the event loop on each camera frame. The
  response parser strips markdown fences (```` ```json ```` etc.) before JSON
  parsing, then validates via `DetectionResponse`. Returns `[]` on any error.
- **`ingestion/opensky.py`**: Calls `https://opensky-network.org/api/states/all`
  with bounding-box params from `BBOX` config. `fetch_aircraft(bbox=None)` accepts
  an optional dict override (`{"lamin":…, "lomin":…, "lamax":…, "lomax":…}`).
  Maps the positional state vector array (by index) to `AircraftPosition` models.
- **`ingestion/traffic_cams.py`**: Downloads JPEG snapshots from public Caltrans
  camera URLs. `CAMERA_FEEDS` dict has two LA-area entries: `I-405_LAX` and
  `I-5_Downtown`. Each entry holds `url`, `lat`, `lon`, `heading`, `fov_degrees`.
  `capture_frame(camera_id)` returns a dict with `camera_id`, `image_bytes`,
  `lat`, `lon`, `heading`, `fov_degrees`, `captured_at`.
- **`ingestion/satellite.py`**: **Stub only — both `_fetch_sentinel_tile()` and
  `_fetch_planet_tile()` raise `NotImplementedError`.** Also imports
  `SatelliteTile` from `schemas.py`, which is **not yet defined** there — this
  module will cause an `ImportError` if imported directly.

### Frontend (`frontend/`)

- **`LiveMap.tsx`**: Initializes a Mapbox GL v3 map centered on Los Angeles
  (`[-118.25, 34.05]`, zoom 10), adds a single `"detections"` GeoJSON source
  with two layers (`"aircraft-layer"`, `"vehicle-layer"`), and connects directly
  to `ws://localhost:8000/ws/live`. On each WebSocket message it calls
  `source.setData(geojson)` and updates a `stats` state (`{aircraft, vehicles}`)
  displayed in a HUD overlay. Aircraft are colored by altitude using a
  `"circle-color"` interpolate expression (`#00ff88` → `#ffaa00` → `#ff0044`).
- **`PlaneLayer.tsx`**: Standalone layer component that manages a `"planes"`
  GeoJSON source and `"planes-layer"` circle layer (color `#00d4ff`). Uses a
  `sourceAdded` ref to avoid duplicate `addSource` calls. **Not wired into
  `LiveMap.tsx`** — uses different source/layer IDs than `LiveMap`.
- **`VehicleLayer.tsx`**: Standalone layer component for a `"vehicles"` GeoJSON
  source and `"vehicles-layer"` circle layer (color `#ff9900`). Also uses a
  `sourceAdded` ref. **Not wired into `LiveMap.tsx`** — source/layer IDs differ.
- **`CameraPanel.tsx`**: Sidebar rendering camera `Detection[]` where each item
  has `{source_id, source_type, vehicles: [{id, vehicle_type}]}`. **This
  `Detection` type does not match the backend's detection schema** or the GeoJSON
  properties emitted by `panoptic.py`. Requires reconciliation before use.
- **`useWebSocket.ts`**: Auto-reconnecting hook (3 s retry on close). Returns the
  latest parsed `WsMessage | null`, typed as `{type: "aircraft"|"detections"|"error", data?, message?, source?}`.
  **This `WsMessage` type does not match the backend output** (which is a raw
  GeoJSON FeatureCollection, not a typed wrapper). The hook is unused by
  `LiveMap.tsx`, which manages its own WebSocket inline.

## Data Models

### Backend Pydantic Models (`backend/models/schemas.py`)

**`AircraftPosition`**

| Field | Type | Notes |
|---|---|---|
| `icao24` | str | ICAO 24-bit address |
| `callsign` | str | Default `""` |
| `origin_country` | str | Default `""` |
| `longitude` | Optional[float] | None if unknown |
| `latitude` | Optional[float] | None if unknown |
| `altitude` | Optional[float] | Meters barometric |
| `velocity` | Optional[float] | m/s ground speed |
| `heading` | Optional[float] | Degrees from north |
| `vertical_rate` | Optional[float] | m/s |
| `on_ground` | bool | Default `False` |
| `last_contact` | Optional[int] | Unix epoch |

**`Detection`**

| Field | Type | Notes |
|---|---|---|
| `category` | str | `"vehicle"`, `"aircraft"`, `"pedestrian"`, `"infrastructure"`, etc. |
| `estimated_lat` | float | ge=-90, le=90 |
| `estimated_lon` | float | ge=-180, le=180 |
| `confidence` | float | ge=0, le=1 |
| `bounding_box` | Optional[list[float]] | `[x1, y1, x2, y2]` pixel coords |
| `attributes` | dict | e.g. color, direction, estimated_speed |

**`DetectionResponse`**: wraps `list[Detection]` — used to validate Gemini output.

### GeoJSON Contract

All backend-to-frontend data is a **GeoJSON `FeatureCollection`**. Each feature
`properties` object contains:

**Aircraft features** (source: OpenSky):

| Property | Type | Description |
|---|---|---|
| `category` | string | Always `"aircraft"` |
| `callsign` | string | ICAO callsign |
| `altitude` | float\|null | Meters barometric |
| `velocity` | float\|null | m/s ground speed |
| `heading` | float\|null | Degrees from north |
| `on_ground` | bool | Whether aircraft is on ground |
| `source` | string | Always `"opensky"` |

**Camera detection features** (source: Gemini):

| Property | Type | Description |
|---|---|---|
| `category` | string | `"vehicles"`, `"pedestrians"`, `"aircraft"`, `"infrastructure"`, etc. |
| `confidence` | float | 0–1 |
| `attributes` | dict | Extra properties (color, direction, speed) |
| `source` | string | `"camera:<camera_id>"` e.g. `"camera:I-405_LAX"` |
| `source_model` | string | Always `"gemini-2.0-flash"` |

Note: camera features omit `bounding_box` in GeoJSON properties (pixel coords
are not meaningful in GeoJSON). Aircraft features skip the `confidence` field.

## Environment Variables

Create a `.env` file in the **project root** (`geospatial-tracker/.env`). Both
the backend and frontend read from this file (backend via `python-dotenv`,
frontend via Vite's `envDir: ".."` setting in `vite.config.ts`).

> **Note**: There is no `.env.example` file in the repository — create `.env`
> directly from the template below.

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
AIRCRAFT_POLL_INTERVAL=10     # seconds (read but not used — loop always sleeps 10s)
CAMERA_POLL_INTERVAL=5        # seconds (read but not used by broadcast_loop)
SATELLITE_POLL_INTERVAL=60    # seconds (read but not used)

# Bounding box [min_lon, min_lat, max_lon, max_lat]
# Default is Denver area; camera feeds are currently LA-based (mismatch — see Known Issues)
BBOX=-105.5,39.5,-104.5,40.2
```

## Development Workflows

### Docker Compose (recommended)

```bash
# From project root — create .env from the template above first
docker compose up --build
```

- Backend: http://localhost:8000 (uvicorn + `--reload` via compose override)
- Frontend: http://localhost:5173 (Vite dev server)

**Important**: `docker-compose.yml` mounts `./backend:/app` and runs
`uvicorn main:app` (not `backend.main:app`) because the container's WORKDIR
is `/app` (i.e., directly inside the `backend/` directory). The `backend.*`
import path is only needed when running from the project root.

### Local (no Docker)

**Backend**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Run as a package from the project root so `backend.*` imports resolve:

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
npm run build      # tsc && vite build → dist/
npm run lint       # eslint src --ext ts,tsx
```

TypeScript is strict (`strict: true`, `noUnusedLocals`, `noUnusedParameters`,
`noFallthroughCasesInSwitch`). Fix all type errors before committing.

> **Note**: There is no ESLint config file (`.eslintrc.*`) or `eslint` package
> in `devDependencies`. The `npm run lint` script will fail until ESLint is
> added. Either add it or remove the lint script if not needed.

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
- Use the `_get_gemini()` lazy singleton pattern (as in `panoptic.py`) rather
  than constructing `GeminiClient` at module import time, to avoid failing on
  import when `GEMINI_API_KEY` is absent.

### TypeScript / React (frontend)

- **React 18.3** with function components and hooks only — no class components.
- **Strict TypeScript** (`ES2020` target, `moduleResolution: bundler`).
- Mapbox GL sources and layers are managed imperatively inside `useEffect`.
  Use `sourceAdded` refs (as in `PlaneLayer`, `VehicleLayer`) to avoid
  re-adding sources on re-renders.
- Map layer components (`PlaneLayer`, `VehicleLayer`) return `null` — they are
  purely side-effectful map layer managers, not visual React elements.
- GeoJSON data flows: backend GeoJSON → WebSocket → `source.setData()` —
  do not convert to React state unnecessarily.
- Inline styles are used throughout (no CSS framework); keep styling consistent
  with the dark terminal aesthetic (`#1a1a2e`, `#00d4ff`, `#00ff88` palette).
- `VITE_MAPBOX_TOKEN` must be prefixed with `VITE_` to be exposed to the
  browser bundle.

## Known Issues & TODOs

1. **`satellite.py` is broken**: Imports `SatelliteTile` from `schemas.py`,
   which doesn't exist. Both fetch functions raise `NotImplementedError`. Do
   not import this module until it is implemented.

2. **BBOX / camera region mismatch**: The default `BBOX` env var targets Denver
   (`-105.5,39.5,-104.5,40.2`) but the Caltrans camera feeds are in Los Angeles.
   Set `BBOX=-118.6,33.7,-117.9,34.3` for LA or update the camera feed list.

3. **`useWebSocket` type mismatch**: `useWebSocket.ts` expects messages shaped as
   `{type, data, message, source}`, but the backend emits raw GeoJSON
   `FeatureCollection` objects. The hook is currently unused — before wiring it
   in, either update the hook's `WsMessage` type or wrap backend output in the
   expected envelope.

4. **`CameraPanel` type mismatch**: `CameraPanel.tsx`'s `Detection` type
   (`{source_id, source_type, vehicles: [{id, vehicle_type}]}`) does not match
   the Gemini detection GeoJSON feature properties. Reconcile before wiring in.

5. **`PlaneLayer`/`VehicleLayer` source naming conflicts**: `PlaneLayer` uses
   source `"planes"` and layer `"planes-layer"`. `VehicleLayer` uses `"vehicles"`
   and `"vehicles-layer"`. `LiveMap.tsx` uses a single `"detections"` source
   with layers `"aircraft-layer"` and `"vehicle-layer"`. These are incompatible
   as-is — integrating the standalone components requires choosing one scheme.

6. **`GeminiClient.analyze_frame` blocks the event loop**: The method is declared
   `async def` but calls `self._client.models.generate_content()` synchronously.
   This will block the asyncio event loop for the duration of the Gemini API
   call. Wrap in `asyncio.to_thread()` or use the async SDK variant when
   available.

7. **Unused env vars in `broadcast_loop`**: `AIRCRAFT_POLL_INTERVAL`,
   `CAMERA_POLL_INTERVAL`, and `SATELLITE_POLL_INTERVAL` are read from env but
   `broadcast_loop` always sleeps 10 seconds regardless.

8. **No authentication on WebSocket**: `/ws/live` is open to any origin.
   `CORSMiddleware` is set to `allow_origins=["*"]`.

9. **`@app.on_event("startup")` is deprecated** in newer FastAPI. Migrate to
   `lifespan` context manager when upgrading FastAPI.

10. **No `.env.example` file**: The repo does not include a template env file.
    Add one at `geospatial-tracker/.env.example` to aid onboarding.

11. **No ESLint config**: `npm run lint` will fail — there is no `.eslintrc.*`
    file and `eslint` is absent from `devDependencies`.

## API Reference

### WebSocket: `ws://localhost:8000/ws/live`

Emits a raw GeoJSON `FeatureCollection` every ~10 seconds. The client should
send keep-alive pings (any text) to maintain the connection; the server calls
`await ws.receive_text()` in a loop to detect disconnects.

### HTTP: `GET /health`

Returns `{"status": "ok"}` when the backend is running.

## External Services

| Service | Purpose | Auth |
|---------|---------|------|
| OpenSky Network | Live aircraft state vectors | Optional (username/password) |
| Caltrans DOT CCTV | Traffic camera JPEG snapshots | None (public) |
| Google Gemini 2.0 Flash | Panoptic vision detection | `GEMINI_API_KEY` |
| Mapbox GL JS v3 | Map tiles and rendering | `VITE_MAPBOX_TOKEN` |
| Planet Labs (stub) | Satellite imagery | `PLANET_API_KEY` |
| Sentinel Hub (stub) | Sentinel-2 satellite imagery | Client ID + Secret |

## Key Dependencies

| Package | Version | Notes |
|---------|---------|-------|
| fastapi | >=0.111.0 | Python web framework |
| uvicorn[standard] | >=0.30.0 | ASGI server |
| httpx | >=0.27.0 | Async HTTP client |
| pydantic | >=2.7.0 | v2 data validation |
| python-dotenv | >=1.0.1 | Env var loading |
| google-genai | >=1.0.0 | Gemini API (`from google import genai`) |
| websockets | >=12.0 | WebSocket support for uvicorn |
| mapbox-gl | ^3.3.0 | Frontend map rendering |
| react / react-dom | ^18.3.1 | Frontend UI |
| typescript | ^5.4.5 | Frontend type checking |
| vite | ^5.3.1 | Frontend build tool |
