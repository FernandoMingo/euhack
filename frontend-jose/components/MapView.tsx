"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Layers, Layers3, MapPin } from "lucide-react";
import { MAPBOX_TOKEN } from "@/lib/api";

mapboxgl.accessToken = MAPBOX_TOKEN;

export interface MapMarker {
  id: string;
  latitude: number;
  longitude: number;
  title?: string;
}

interface MapViewProps {
  markers: MapMarker[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Map center fallback when no markers are present. Defaults to central Amsterdam. */
  fallbackCenter?: { lat: number; lng: number };
  /** Zoom level when fitting to a single selected marker. */
  zoom?: number;
}

const AMSTERDAM = { lat: 52.3702, lng: 4.8952 };

export function MapView({
  markers,
  selectedId,
  onSelect,
  fallbackCenter = AMSTERDAM,
  zoom = 13.6,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Record<string, mapboxgl.Marker>>({});
  const onSelectRef = useRef(onSelect);
  const [mode, setMode] = useState<"2D" | "3D">("2D");
  const [available, setAvailable] = useState<boolean>(Boolean(MAPBOX_TOKEN));

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (!containerRef.current || !MAPBOX_TOKEN) {
      setAvailable(false);
      return;
    }
    const initial =
      markers[0] ?? { latitude: fallbackCenter.lat, longitude: fallbackCenter.lng };
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [initial.longitude, initial.latitude],
      zoom: 12.4,
      attributionControl: false,
    });
    mapRef.current = map;
    map.on("load", () => map.resize());

    const handleResize = () => map.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
    // Init once. Marker updates handled by separate effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync markers when the prop changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const apply = () => {
      const nextIds = new Set(markers.map((m) => m.id));
      for (const [id, existing] of Object.entries(markersRef.current)) {
        if (!nextIds.has(id)) {
          existing.remove();
          delete markersRef.current[id];
        }
      }
      for (const marker of markers) {
        if (markersRef.current[marker.id]) {
          markersRef.current[marker.id].setLngLat([
            marker.longitude,
            marker.latitude,
          ]);
          continue;
        }
        const el = document.createElement("div");
        el.className = "cc-pin";
        el.innerHTML =
          '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 6-9 12-9 12s-9-6-9-12a9 9 0 0118 0z"/><circle cx="12" cy="10" r="2.5"/></svg>';
        el.addEventListener("click", () => onSelectRef.current(marker.id));
        const mb = new mapboxgl.Marker({ element: el })
          .setLngLat([marker.longitude, marker.latitude])
          .addTo(map);
        markersRef.current[marker.id] = mb;
      }
    };

    if (map.loaded()) apply();
    else map.once("load", apply);
  }, [markers]);

  // Center map on selected marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedId) return;
    const target = markers.find((m) => m.id === selectedId);
    if (!target) return;
    map.easeTo({
      center: [target.longitude, target.latitude],
      zoom,
      duration: 800,
    });
  }, [selectedId, markers, zoom]);

  // 2D / 3D toggle
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const targetZoom = Math.max(map.getZoom(), 15.5);
    map.easeTo({
      pitch: mode === "3D" ? 55 : 0,
      bearing: mode === "3D" ? -10 : 0,
      zoom: mode === "3D" ? targetZoom : Math.min(map.getZoom(), 13),
      duration: 800,
    });
    const layerId = "cc-3d-buildings";
    const toggleBuildings = () => {
      if (mode === "3D" && !map.getLayer(layerId)) {
        // Insert below symbol/label layers so street names stay readable on top.
        const layers = map.getStyle()?.layers ?? [];
        const labelLayerId = layers.find(
          (l) => l.type === "symbol" && (l.layout as Record<string, unknown> | undefined)?.["text-field"]
        )?.id;
        map.addLayer(
          {
            id: layerId,
            type: "fill-extrusion",
            source: "composite",
            "source-layer": "building",
            filter: ["==", ["get", "extrude"], "true"],
            minzoom: 15,
            paint: {
              "fill-extrusion-color": "#D9D2C1",
              "fill-extrusion-height": [
                "interpolate",
                ["linear"],
                ["zoom"],
                15,
                0,
                15.05,
                ["get", "height"],
              ],
              "fill-extrusion-base": [
                "interpolate",
                ["linear"],
                ["zoom"],
                15,
                0,
                15.05,
                ["get", "min_height"],
              ],
              "fill-extrusion-opacity": 0.85,
            },
          },
          labelLayerId
        );
      } else if (mode === "2D" && map.getLayer(layerId)) {
        map.removeLayer(layerId);
      }
    };
    if (map.loaded()) toggleBuildings();
    else map.once("load", toggleBuildings);
  }, [mode]);

  if (!available) {
    return (
      <div className="grid h-full w-full place-items-center bg-secondary/40 p-6">
        <div className="max-w-sm rounded-3xl border border-border bg-card p-6 text-center shadow-[var(--shadow-soft)]">
          <MapPin className="mx-auto mb-3 text-muted-foreground" size={28} />
          <p className="text-sm font-medium">Map unavailable right now.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Your invitations are still safe below.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full" style={{ minHeight: "300px" }}>
      <div
        ref={containerRef}
        className="absolute inset-0"
        style={{ width: "100%", height: "100%" }}
      />
      <button
        type="button"
        onClick={() => setMode((m) => (m === "2D" ? "3D" : "2D"))}
        className="absolute bottom-4 right-4 flex items-center gap-1.5 rounded-full border border-border bg-card/90 px-3 py-2 text-xs font-medium shadow-[var(--shadow-soft)] backdrop-blur hover:bg-card"
      >
        {mode === "2D" ? (
          <Layers3 size={14} strokeWidth={1.8} />
        ) : (
          <Layers size={14} strokeWidth={1.8} />
        )}
        {mode === "2D" ? "3D" : "2D"}
      </button>
    </div>
  );
}
