import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";

type Vehicle = {
  id: string;
  latitude: number;
  longitude: number;
  vehicle_type?: string | null;
};

type Props = {
  map: mapboxgl.Map | null;
  vehicles: Vehicle[];
};

/**
 * Renders detected vehicle markers from camera/satellite detections.
 */
export function VehicleLayer({ map, vehicles }: Props) {
  const sourceAdded = useRef(false);

  useEffect(() => {
    if (!map) return;

    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: vehicles.map((v) => ({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [v.longitude, v.latitude],
        },
        properties: {
          id: v.id,
          vehicle_type: v.vehicle_type ?? "unknown",
        },
      })),
    };

    if (!sourceAdded.current) {
      map.addSource("vehicles", { type: "geojson", data: geojson });
      map.addLayer({
        id: "vehicles-layer",
        type: "circle",
        source: "vehicles",
        paint: {
          "circle-radius": 5,
          "circle-color": "#ff9900",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
      sourceAdded.current = true;
    } else {
      (map.getSource("vehicles") as mapboxgl.GeoJSONSource).setData(geojson);
    }
  }, [map, vehicles]);

  return null;
}
