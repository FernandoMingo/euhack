"use client";

import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { Layers, Layers3, MapPin } from "lucide-react";
import { MAPBOX_TOKEN } from "@/lib/api";
import type { DemoEvent } from "@/lib/demoEvents";

mapboxgl.accessToken = MAPBOX_TOKEN;

interface MapViewProps {
  events: DemoEvent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function MapView({ events, selectedId, onSelect }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Record<string, mapboxgl.Marker>>({});
  const [mode, setMode] = useState<"2D" | "3D">("2D");
  const [available, setAvailable] = useState<boolean>(Boolean(MAPBOX_TOKEN));

  useEffect(() => {
    if (!containerRef.current || !MAPBOX_TOKEN) {
      setAvailable(false);
      return;
    }
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: [4.4777, 51.9244],
      zoom: 12.4,
      attributionControl: false,
    });
    mapRef.current = map;

    map.on("load", () => {
      // Resize once tiles are ready so the canvas matches its container
      // even if dimensions were uncertain when init ran.
      map.resize();
      for (const event of events) {
        const el = document.createElement("div");
        el.className = "cc-pin";
        el.innerHTML =
          '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 6-9 12-9 12s-9-6-9-12a9 9 0 0118 0z"/><circle cx="12" cy="10" r="2.5"/></svg>';
        el.addEventListener("click", () => onSelect(event.id));
        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([event.longitude, event.latitude])
          .addTo(map);
        markersRef.current[event.id] = marker;
      }
    });

    // Resize on window changes too — flex parent dimensions can change.
    const handleResize = () => map.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Center map on the selected event
  useEffect(() => {
    if (!selectedId || !mapRef.current) return;
    const event = events.find((e) => e.id === selectedId);
    if (!event) return;
    mapRef.current.easeTo({
      center: [event.longitude, event.latitude],
      zoom: 13.6,
      duration: 800,
    });
  }, [selectedId, events]);

  // 2D / 3D toggle
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.easeTo({
      pitch: mode === "3D" ? 55 : 0,
      bearing: mode === "3D" ? -10 : 0,
      duration: 800,
    });
    const layerId = "cc-3d-buildings";
    if (mode === "3D" && !map.getLayer(layerId)) {
      map.addLayer({
        id: layerId,
        type: "fill-extrusion",
        source: "composite",
        "source-layer": "building",
        minzoom: 12,
        paint: {
          "fill-extrusion-color": "#E8E2D6",
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": ["get", "min_height"],
          "fill-extrusion-opacity": 0.7,
        },
      });
    } else if (mode === "2D" && map.getLayer(layerId)) {
      map.removeLayer(layerId);
    }
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
