type Detection = {
  source_id: string;
  source_type: string;
  vehicles: { id: string; vehicle_type?: string | null }[];
  raw_response?: string | null;
};

type Props = {
  detections: Detection[];
};

/**
 * Sidebar panel showing camera feed detection results.
 */
export function CameraPanel({ detections }: Props) {
  return (
    <aside
      style={{
        width: 280,
        background: "#1a1a2e",
        color: "#e0e0e0",
        overflowY: "auto",
        padding: "1rem",
        fontFamily: "monospace",
        fontSize: 13,
      }}
    >
      <h2 style={{ margin: "0 0 1rem", color: "#00d4ff" }}>Camera Feeds</h2>

      {detections.length === 0 && (
        <p style={{ color: "#888" }}>No detections yet…</p>
      )}

      {detections.map((d) => (
        <div
          key={d.source_id}
          style={{
            marginBottom: "1rem",
            padding: "0.5rem",
            background: "#0f3460",
            borderRadius: 4,
          }}
        >
          <strong>{d.source_id}</strong>
          <div style={{ color: "#aaa", marginTop: 4 }}>
            Vehicles detected: {d.vehicles.length}
          </div>
          {d.vehicles.map((v) => (
            <div key={v.id} style={{ marginLeft: 8, color: "#ccc" }}>
              • {v.vehicle_type ?? "unknown"}
            </div>
          ))}
        </div>
      ))}
    </aside>
  );
}
