import { useCallback, useEffect, useState } from "react";

interface ControlState {
  interval: number;
  sources: { aircraft: boolean; cameras: boolean };
  bbox: [number, number, number, number];
}

const PANEL_STYLE: React.CSSProperties = {
  position: "absolute",
  bottom: 16,
  right: 16,
  background: "rgba(0,0,0,0.85)",
  color: "#00d4ff",
  padding: "14px 18px",
  borderRadius: 8,
  fontFamily: "monospace",
  fontSize: 13,
  lineHeight: 2,
  minWidth: 220,
  border: "1px solid #00d4ff33",
};

const BTN: React.CSSProperties = {
  background: "none",
  border: "1px solid #00d4ff55",
  color: "#00d4ff",
  fontFamily: "monospace",
  fontSize: 12,
  padding: "2px 8px",
  borderRadius: 4,
  cursor: "pointer",
  marginLeft: 6,
};

const BTN_ON: React.CSSProperties = { ...BTN, borderColor: "#00ff88", color: "#00ff88" };
const BTN_OFF: React.CSSProperties = { ...BTN, borderColor: "#ff004466", color: "#ff0044" };

export default function ControlPanel() {
  const [state, setState] = useState<ControlState | null>(null);
  const [flash, setFlash] = useState("");

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch("/control/state");
      setState(await res.json() as ControlState);
    } catch {
      // backend not yet reachable — retry silently
    }
  }, []);

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  const toggleSource = async (source: "aircraft" | "cameras") => {
    if (!state) return;
    const res = await fetch("/control/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [source]: !state.sources[source] }),
    });
    const data = await res.json() as { sources: ControlState["sources"] };
    setState((prev) => prev ? { ...prev, sources: data.sources } : prev);
  };

  const adjustInterval = async (delta: number) => {
    if (!state) return;
    const res = await fetch("/control/interval", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seconds: state.interval + delta }),
    });
    const data = await res.json() as { interval: number };
    setState((prev) => prev ? { ...prev, interval: data.interval } : prev);
  };

  const triggerCycle = async () => {
    await fetch("/control/trigger", { method: "POST" });
    setFlash("TRIGGERED");
    setTimeout(() => setFlash(""), 1500);
  };

  if (!state) return null;

  return (
    <div style={PANEL_STYLE}>
      <div style={{ color: "#ffffff", fontWeight: "bold", marginBottom: 4, letterSpacing: 1 }}>
        REMOTE CONTROL
      </div>

      <div>
        ✈ AIRCRAFT
        <button
          style={state.sources.aircraft ? BTN_ON : BTN_OFF}
          onClick={() => toggleSource("aircraft")}
        >
          {state.sources.aircraft ? "ON" : "OFF"}
        </button>
      </div>

      <div>
        📷 CAMERAS
        <button
          style={state.sources.cameras ? BTN_ON : BTN_OFF}
          onClick={() => toggleSource("cameras")}
        >
          {state.sources.cameras ? "ON" : "OFF"}
        </button>
      </div>

      <div>
        ⏱ INTERVAL: {state.interval}s
        <button style={BTN} onClick={() => adjustInterval(-5)}>−5</button>
        <button style={BTN} onClick={() => adjustInterval(5)}>+5</button>
      </div>

      <div style={{ marginTop: 6 }}>
        <button
          style={{ ...BTN, marginLeft: 0, borderColor: "#ffaa00", color: "#ffaa00", padding: "4px 12px" }}
          onClick={triggerCycle}
        >
          ⚡ FORCE REFRESH
        </button>
      </div>

      {flash && (
        <div style={{ color: "#00ff88", fontSize: 11, marginTop: 4 }}>{flash}</div>
      )}
    </div>
  );
}
