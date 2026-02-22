import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN as string;

export default function LiveMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const [stats, setStats] = useState({ aircraft: 0, vehicles: 0 });

  useEffect(() => {
    if (!mapContainer.current) return;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [-118.25, 34.05], // Los Angeles — matches Caltrans feeds
      zoom: 10,
    });

    map.current.on("load", () => {
      // Add empty GeoJSON source — updated via WebSocket
      map.current!.addSource("detections", {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });

      // Aircraft layer — colored by altitude
      map.current!.addLayer({
        id: "aircraft-layer",
        type: "circle",
        source: "detections",
        filter: ["==", ["get", "category"], "aircraft"],
        paint: {
          "circle-radius": 8,
          "circle-color": [
            "interpolate", ["linear"], ["coalesce", ["get", "altitude"], 0],
            0, "#00ff88",
            5000, "#ffaa00",
            12000, "#ff0044",
          ],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });

      // Vehicle layer — smaller dots from camera detections
      map.current!.addLayer({
        id: "vehicle-layer",
        type: "circle",
        source: "detections",
        filter: ["==", ["get", "category"], "vehicles"],
        paint: {
          "circle-radius": 4,
          "circle-color": "#00d4ff",
          "circle-opacity": 0.8,
        },
      });
    });

    // WebSocket connection
    const ws = new WebSocket("ws://localhost:8000/ws/live");

    ws.onmessage = (event) => {
      const geojson = JSON.parse(event.data as string);

      const source = map.current?.getSource("detections") as mapboxgl.GeoJSONSource | undefined;
      if (source) source.setData(geojson);

      const features: { properties: { category: string } }[] = geojson.features || [];
      setStats({
        aircraft: features.filter((f) => f.properties.category === "aircraft").length,
        vehicles: features.filter((f) => f.properties.category === "vehicles").length,
      });
    };

    return () => {
      ws.close();
      map.current?.remove();
    };
  }, []);

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh" }}>
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />

      {/* HUD overlay */}
      <div style={{
        position: "absolute",
        top: 16,
        left: 16,
        background: "rgba(0,0,0,0.8)",
        color: "#00ff88",
        padding: "12px 20px",
        borderRadius: 8,
        fontFamily: "monospace",
        fontSize: 14,
        lineHeight: 1.8,
        pointerEvents: "none",
      }}>
        <div>✈ AIRCRAFT TRACKED: {stats.aircraft}</div>
        <div>🚗 VEHICLES DETECTED: {stats.vehicles}</div>
        <div style={{ fontSize: 10, opacity: 0.6, marginTop: 4 }}>LIVE • 10s refresh</div>
      </div>
    </div>
  );
}
