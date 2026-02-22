import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";

type Aircraft = {
  icao24: string;
  callsign?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  heading?: number | null;
};

type Props = {
  map: mapboxgl.Map | null;
  aircraft: Aircraft[];
};

/**
 * Renders aircraft markers on the Mapbox map using a GeoJSON source.
 * Updates the source data whenever the aircraft list changes.
 */
export function PlaneLayer({ map, aircraft }: Props) {
  const sourceAdded = useRef(false);

  useEffect(() => {
    if (!map) return;

    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: aircraft
        .filter((a) => a.latitude != null && a.longitude != null)
        .map((a) => ({
          type: "Feature",
          geometry: {
            type: "Point",
            coordinates: [a.longitude!, a.latitude!],
          },
          properties: {
            icao24: a.icao24,
            callsign: a.callsign ?? "",
            heading: a.heading ?? 0,
          },
        })),
    };

    if (!sourceAdded.current) {
      map.addSource("planes", { type: "geojson", data: geojson });
      map.addLayer({
        id: "planes-layer",
        type: "circle",
        source: "planes",
        paint: {
          "circle-radius": 6,
          "circle-color": "#00d4ff",
          "circle-stroke-width": 1,
          "circle-stroke-color": "#ffffff",
        },
      });
      sourceAdded.current = true;
    } else {
      (map.getSource("planes") as mapboxgl.GeoJSONSource).setData(geojson);
    }
  }, [map, aircraft]);

  return null;
}
