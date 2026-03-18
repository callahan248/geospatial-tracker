"""Runtime control state — read by broadcast_loop, written by REST endpoints."""

from dataclasses import dataclass, field
from backend.config import BBOX, AIRCRAFT_POLL_INTERVAL


@dataclass
class ControlState:
    """Mutable settings that remote-control endpoints can read and write."""

    interval: int = AIRCRAFT_POLL_INTERVAL  # seconds between broadcast cycles
    sources: dict[str, bool] = field(
        default_factory=lambda: {"aircraft": True, "cameras": True}
    )
    bbox: list[float] = field(default_factory=lambda: list(BBOX))


# Shared singleton — imported by main.py and control endpoints
state = ControlState()
