"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Accessibility,
  CalendarDays,
  Check,
  Clock,
  Footprints,
  Heart,
  Layers,
  Layers3,
  Lock,
  Map,
  MapPin,
  Navigation,
  Sparkles,
  User,
  UserCheck,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { CatalogOption, Invitation, PreferenceCatalog, Reveal, Resident } from "@/lib/api";

type MapMode = "2D" | "3D";

const MAPBOX_TOKEN =
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

const NEARBY_INVITATION_ID = "inv-sofia-act-demo-near-me";

function devLog(message: string, details?: unknown) {
  if (process.env.NODE_ENV === "development") {
    console.log(`[CivicCircles] ${message}`, details ?? "");
  }
}

function devWarn(message: string, details?: unknown) {
  if (process.env.NODE_ENV === "development") {
    console.warn(`[CivicCircles] ${message}`, details ?? "");
  }
}

function hasValidCoordinates(invitation: Invitation): boolean {
  const location = invitation.activity?.location;
  return Number.isFinite(location?.lat) && Number.isFinite(location?.lng);
}

function distanceMeters(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371000;
  const toRad = (v: number) => (v * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function ResidentMapExperience() {
  const [resident, setResident] = useState<Resident | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [selected, setSelected] = useState<Invitation | null>(null);
  const [mode, setMode] = useState<MapMode>("2D");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [catalog, setCatalog] = useState<PreferenceCatalog | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [initialUserLocation, setInitialUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locationDenied, setLocationDenied] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const hasCreatedNearbyActivityRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const [me, invites, preferenceCatalog] = await Promise.all([
        api.me(),
        api.invitations(),
        api.catalogPreferences(),
      ]);
      const validCount = invites.filter(hasValidCoordinates).length;
      devLog("invitations loaded", { count: invites.length, validCoordinateMarkers: validCount });
      invites.forEach((invitation) => {
        if (!hasValidCoordinates(invitation)) {
          devWarn("invitation missing/invalid coordinates", {
            id: invitation.id,
            activity_id: invitation.activity_id,
            location: invitation.activity?.location,
          });
        }
      });
      setResident(me);
      setCatalog(preferenceCatalog);
      setInvitations(invites);
      setSelected((current) => {
        if (current?.id === NEARBY_INVITATION_ID && !invites.some((item) => item.id === current.id)) {
          return current;
        }
        return (current ? invites.find((item) => item.id === current.id) : null) ?? invites[0] ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load demo");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (typeof navigator !== "undefined" && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const location = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(location);
          setInitialUserLocation((current) => current ?? location);
          if (hasCreatedNearbyActivityRef.current) return;
          hasCreatedNearbyActivityRef.current = true;
          try {
            const nearby = await api.createNearbyActivity(location.lat, location.lng);
            devLog("nearby demo activity created/reused", {
              invitation_id: nearby.id,
              location: nearby.activity.location,
            });
            const fresh = await api.invitations();
            devLog("invitations loaded after nearby activity", {
              count: fresh.length,
              validCoordinateMarkers: fresh.filter(hasValidCoordinates).length,
            });
            setInvitations(fresh);
            setSelected(fresh.find((item) => item.id === nearby.id) ?? nearby);
            setSheetOpen(true);
          } catch (err) {
            devWarn("nearby demo activity failed", err instanceof Error ? err.message : err);
          }
        },
        () => setLocationDenied(true),
        { timeout: 8000 }
      );
    } else {
      setLocationDenied(true);
    }
  }, []);

  const distanceToActivity = useMemo(() => {
    if (!userLocation || !selected) return null;
    const { lat, lng } = selected.activity.location;
    return distanceMeters(userLocation.lat, userLocation.lng, lat, lng);
  }, [userLocation, selected]);

  const canCheckIn =
    selected?.status === "accepted" &&
    userLocation !== null &&
    distanceToActivity !== null &&
    distanceToActivity <= 50;

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    devLog("selected invitation", selected.id);
    api.reveal(selected.activity_id)
      .then((nextReveal) => {
        if (!cancelled) setReveal(nextReveal);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load circle reveal");
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const choose = useCallback((invitation: Invitation) => {
    setSelected(invitation);
    setSheetOpen(true);
  }, []);

  async function mutate(action: "accept" | "decline" | "check-in") {
    if (!selected) return;
    if (action === "check-in" && !canCheckIn) return;
    setBusy(action);
    setError(null);
    try {
      if (action === "accept") await api.accept(selected.id);
      if (action === "decline") await api.decline(selected.id);
      if (action === "check-in") {
        await api.checkIn(selected.activity_id);
        setReveal(await api.reveal(selected.activity_id));
      }
      const fresh = await api.invitations();
      setInvitations(fresh);
      const updated = fresh.find((i) => i.id === selected.id) ?? selected;
      setSelected(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    return hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
  }, []);

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden bg-background">
      <div className="absolute inset-0 lg:right-[440px]">
        <MapStage
          invitations={invitations}
          selected={selected}
          mode={mode}
          onSelect={choose}
          userLocation={userLocation}
        />
      </div>

      {/* Top overlay */}
      <div className="pointer-events-none absolute left-0 right-0 top-0 z-20 p-4 lg:right-[440px] lg:p-6">
        <div className="mx-auto max-w-md space-y-2 lg:mx-0 lg:max-w-sm">
          <div className="pointer-events-auto flex items-start gap-2">
            <div className="flex-1 rounded-3xl border border-border bg-card/95 px-5 py-4 shadow-float backdrop-blur">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Good {greeting}
              </p>
              <p className="mt-1 text-[15px] font-medium text-foreground">
                {resident?.first_name ?? "Sofia"} has a gentle invitation nearby
              </p>
              <p className="mt-1 text-xs text-muted-foreground">No rush today.</p>
            </div>
            <button
              onClick={() => setProfileOpen(true)}
              className="pointer-events-auto mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-border bg-card/95 shadow-float backdrop-blur transition hover:bg-secondary"
              aria-label="Open profile"
            >
              <User className="h-5 w-5 text-muted-foreground" strokeWidth={1.6} />
            </button>
          </div>
          <div className="pointer-events-auto flex justify-center lg:justify-start">
            <Chip tone="sage">Small group · Hosted · No pressure</Chip>
          </div>
          {locationDenied && !initialUserLocation && (
            <div className="pointer-events-auto rounded-2xl border border-border bg-card/95 px-4 py-3 text-sm text-muted-foreground shadow-soft">
              Location is off. You can still browse invitations, but check-in unlocks near the
              meeting point.
            </div>
          )}
          {error ? (
            <div className="pointer-events-auto rounded-2xl border border-border bg-card/95 px-4 py-3 text-sm text-muted-foreground shadow-soft">
              {error}
            </div>
          ) : null}
        </div>
      </div>

      {/* 2D/3D toggle */}
      <div className="pointer-events-none absolute bottom-20 right-4 z-20 lg:bottom-6 lg:right-[464px]">
        <div className="pointer-events-auto flex items-center rounded-full border border-border bg-card/95 p-1 shadow-float backdrop-blur">
          {(["2D", "3D"] as const).map((item) => (
            <button
              key={item}
              className={`flex h-10 items-center gap-2 rounded-full px-3 text-xs font-medium transition ${
                mode === item
                  ? "bg-secondary text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setMode(item)}
            >
              {item === "3D" ? (
                <Layers3 className="h-3.5 w-3.5" strokeWidth={1.8} />
              ) : (
                <Layers className="h-3.5 w-3.5" strokeWidth={1.8} />
              )}
              {item}
            </button>
          ))}
        </div>
      </div>

      {/* Desktop sidebar */}
      <aside className="absolute bottom-0 right-0 top-0 hidden w-[440px] flex-col overflow-y-auto border-l border-border bg-card p-6 pb-24 lg:flex">
        {selected ? (
          <InvitationCard
            invitation={selected}
            reveal={reveal}
            busy={busy}
            canCheckIn={canCheckIn}
            distanceToActivity={distanceToActivity}
            onAccept={() => mutate("accept")}
            onDecline={() => mutate("decline")}
            onCheckIn={() => mutate("check-in")}
            hasUserLocation={userLocation !== null}
          />
        ) : (
          <div className="m-auto max-w-xs text-center">
            <p className="text-base font-medium text-foreground">A gentle option nearby</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Tap a pin on the map to see Sofia&apos;s calm invitation.
            </p>
          </div>
        )}
      </aside>

      {/* Mobile sheet */}
      <MobileSheet open={sheetOpen && !!selected} onClose={() => setSheetOpen(false)}>
        {selected ? (
          <InvitationCard
            invitation={selected}
            reveal={reveal}
            busy={busy}
            canCheckIn={canCheckIn}
            distanceToActivity={distanceToActivity}
            onAccept={() => mutate("accept")}
            onDecline={() => mutate("decline")}
            onCheckIn={() => mutate("check-in")}
            hasUserLocation={userLocation !== null}
          />
        ) : null}
      </MobileSheet>

      {/* Profile panel */}
      {profileOpen && resident && (
        <ProfilePanel
          resident={resident}
          catalog={catalog}
          onClose={() => setProfileOpen(false)}
          onSaved={(updatedResident) => {
            setResident(updatedResident);
            load();
          }}
        />
      )}

      <ResidentTabs onProfileClick={() => setProfileOpen(true)} />
    </div>
  );
}

// ── Map ────────────────────────────────────────────────────────────────────

function MapStage({
  invitations,
  selected,
  mode,
  onSelect,
  userLocation,
}: {
  invitations: Invitation[];
  selected: Invitation | null;
  mode: MapMode;
  onSelect: (invitation: Invitation) => void;
  userLocation: { lat: number; lng: number } | null;
}) {
  if (!MAPBOX_TOKEN) {
    return (
      <FallbackMap
        invitations={invitations}
        selected={selected}
        mode={mode}
        onSelect={onSelect}
        userLocation={userLocation}
      />
    );
  }
  return (
    <MapboxMap
      invitations={invitations}
      selected={selected}
      mode={mode}
      onSelect={onSelect}
      token={MAPBOX_TOKEN}
      userLocation={userLocation}
    />
  );
}

function activityIcon(type: string): string {
  const icons: Record<string, string> = {
    walk: `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="5" r="1"/><path d="m9 20 3-6 2 2 3-8"/><path d="M6.5 17.5 8 19l2-1"/></svg>`,
    museum: `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="9" width="18" height="12" rx="1"/><path d="M3 9 12 3l9 6"/><line x1="9" y1="21" x2="9" y2="9"/><line x1="15" y1="21" x2="15" y2="9"/></svg>`,
    social: `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  };
  return (
    icons[type] ||
    `<svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>`
  );
}

function MapboxMap({
  invitations,
  selected,
  mode,
  onSelect,
  token,
  userLocation,
}: {
  invitations: Invitation[];
  selected: Invitation | null;
  mode: MapMode;
  onSelect: (invitation: Invitation) => void;
  token: string;
  userLocation: { lat: number; lng: number } | null;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const userMarkerRef = useRef<any>(null);
  const didInitialFitRef = useRef(false);
  const didSkipInitialSelectionRef = useRef(false);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    if (!document.querySelector('link[data-mapbox-css="true"]')) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "https://api.mapbox.com/mapbox-gl-js/v3.7.0/mapbox-gl.css";
      link.dataset.mapboxCss = "true";
      document.head.appendChild(link);
    }
    if (!ref.current || mapRef.current) return;
    let mounted = true;

    import("mapbox-gl").then((mapboxgl) => {
      if (!mounted || !ref.current) return;
      mapboxgl.default.accessToken = token;
      const map = new mapboxgl.default.Map({
        container: ref.current,
        style: "mapbox://styles/mapbox/light-v11",
        center: [4.8686, 52.3579],
        zoom: 13.2,
        pitch: 0,
        attributionControl: false,
      });
      mapRef.current = map;
      map.on("load", () => setMapReady(true));
    });

    return () => {
      mounted = false;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [token]);

  // activity markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    let cancelled = false;

    import("mapbox-gl").then((mapboxgl) => {
      if (cancelled) return;
      markersRef.current.forEach((m) => m.remove());
      const validInvitations = invitations.filter((invitation) => {
        const valid = hasValidCoordinates(invitation);
        if (!valid) {
          devWarn("skip malformed marker", {
            id: invitation.id,
            location: invitation.activity?.location,
          });
        }
        return valid;
      });
      devLog("map markers rendered", { count: validInvitations.length });
      markersRef.current = validInvitations.map((invitation) => {
        const isSelected = selected?.id === invitation.id;
        const root = document.createElement("div");
        root.className = "cc-map-marker-root";
        root.style.zIndex = isSelected ? "5" : "1";

        const button = document.createElement("button");
        button.type = "button";
        button.title = invitation.activity.title;
        button.setAttribute("aria-label", invitation.activity.title);
        button.className = `cc-map-marker-inner${isSelected ? " selected" : ""}`;
        button.innerHTML = activityIcon(invitation.activity.activity_type);
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          onSelect(invitation);
        });
        root.appendChild(button);

        return new mapboxgl.default.Marker({ element: root, anchor: "bottom" })
          .setLngLat([invitation.activity.location.lng, invitation.activity.location.lat])
          .addTo(map);
      });
    });

    return () => {
      cancelled = true;
    };
  }, [invitations, selected, onSelect, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || didInitialFitRef.current) return;
    const coords = invitations
      .filter(hasValidCoordinates)
      .map((invitation) => [invitation.activity.location.lng, invitation.activity.location.lat] as [number, number]);
    if (coords.length === 0) return;
    didInitialFitRef.current = true;
    import("mapbox-gl").then((mapboxgl) => {
      const bounds = new mapboxgl.default.LngLatBounds(coords[0], coords[0]);
      coords.slice(1).forEach((coord) => bounds.extend(coord));
      map.fitBounds(bounds, { padding: { top: 160, bottom: 180, left: 80, right: 80 }, maxZoom: 13.2, duration: 600 });
    });
  }, [invitations, mapReady]);

  // user location marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !userLocation) return;
    let cancelled = false;

    import("mapbox-gl").then((mapboxgl) => {
      if (cancelled) return;
      userMarkerRef.current?.remove();
      const el = document.createElement("div");
      el.className = "cc-user-marker";
      userMarkerRef.current = new mapboxgl.default.Marker({ element: el, anchor: "center" })
        .setLngLat([userLocation.lng, userLocation.lat])
        .addTo(map);
    });

    return () => {
      cancelled = true;
      userMarkerRef.current?.remove();
      userMarkerRef.current = null;
    };
  }, [userLocation, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (mode === "3D") {
      map.easeTo({ pitch: 55, bearing: -10, duration: 800 });
      const addBuildings = () => {
        if (!map.getLayer("cc-3d-buildings")) {
          try {
            map.addLayer({
              id: "cc-3d-buildings",
              source: "composite",
              "source-layer": "building",
              type: "fill-extrusion",
              minzoom: 12,
              paint: {
                "fill-extrusion-color": "#E8E2D6",
                "fill-extrusion-height": ["get", "height"],
                "fill-extrusion-base": ["get", "min_height"],
                "fill-extrusion-opacity": 0.7,
              },
            });
          } catch {
            /* style may not expose composite yet */
          }
        }
      };
      if (map.isStyleLoaded()) addBuildings();
      else map.once("load", addBuildings);
    } else {
      map.easeTo({ pitch: 0, bearing: 0, duration: 800 });
      if (map.getLayer("cc-3d-buildings")) map.removeLayer("cc-3d-buildings");
    }
  }, [mode]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;
    if (!didSkipInitialSelectionRef.current && selected.id !== NEARBY_INVITATION_ID) {
      didSkipInitialSelectionRef.current = true;
      return;
    }
    didSkipInitialSelectionRef.current = true;
    if (selected.id === NEARBY_INVITATION_ID) {
      didInitialFitRef.current = true;
    }
    map.easeTo({
      center: [selected.activity.location.lng, selected.activity.location.lat],
      zoom: selected.id === NEARBY_INVITATION_ID ? 15 : 14,
      duration: 800,
    });
  }, [selected, mapReady]);

  return <div ref={ref} className="h-full w-full bg-secondary/40" />;
}

function FallbackMap({
  invitations,
  selected,
  mode,
  onSelect,
  userLocation,
}: {
  invitations: Invitation[];
  selected: Invitation | null;
  mode: MapMode;
  onSelect: (invitation: Invitation) => void;
  userLocation: { lat: number; lng: number } | null;
}) {
  const validInvitations = invitations.filter(hasValidCoordinates);
  const points = [
    ...validInvitations.map((invitation) => invitation.activity.location),
    ...(userLocation ? [userLocation] : []),
  ];
  const fallbackBounds = points.length
    ? {
        minLat: Math.min(...points.map((point) => point.lat)),
        maxLat: Math.max(...points.map((point) => point.lat)),
        minLng: Math.min(...points.map((point) => point.lng)),
        maxLng: Math.max(...points.map((point) => point.lng)),
      }
    : { minLat: 52.34, maxLat: 52.39, minLng: 4.84, maxLng: 4.92 };

  const project = (lat: number, lng: number) => {
    const latSpan = Math.max(fallbackBounds.maxLat - fallbackBounds.minLat, 0.01);
    const lngSpan = Math.max(fallbackBounds.maxLng - fallbackBounds.minLng, 0.01);
    return {
      left: `${12 + ((lng - fallbackBounds.minLng) / lngSpan) * 76}%`,
      top: `${82 - ((lat - fallbackBounds.minLat) / latSpan) * 64}%`,
    };
  };

  return (
    <div className={`relative h-full w-full overflow-hidden bg-[#ebe5d8] paper-line ${mode === "3D" ? "map-3d" : ""}`}>
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div className="absolute left-[8%] top-[26%] h-px w-[84%] rotate-[-8deg] bg-foreground/20" />
        <div className="absolute left-[18%] top-[12%] h-[82%] w-px rotate-[18deg] bg-foreground/15" />
        <div className="absolute left-[6%] top-[62%] h-px w-[86%] rotate-[5deg] bg-foreground/15" />
        <div className="absolute left-[62%] top-[6%] h-[88%] w-px rotate-[-12deg] bg-foreground/10" />
        <div className="absolute left-[24%] top-[30%] h-40 w-52 rounded-[42%] border border-foreground/10 bg-[color-mix(in_oklab,var(--sage)_18%,white)]" />
        <div className="absolute right-[12%] top-[18%] h-36 w-44 rounded-[45%] border border-foreground/10 bg-[color-mix(in_oklab,var(--mist)_16%,white)]" />
      </div>

      {validInvitations.map((invitation) => {
        const position = project(invitation.activity.location.lat, invitation.activity.location.lng);
        return (
          <div
            key={invitation.id}
            className="cc-fallback-marker-root"
            style={{ left: position.left, top: position.top, zIndex: selected?.id === invitation.id ? 5 : 1 }}
          >
            <button
              type="button"
              title={invitation.activity.title}
              className={`cc-map-marker-inner${selected?.id === invitation.id ? " selected" : ""}`}
              onClick={() => onSelect(invitation)}
              dangerouslySetInnerHTML={{ __html: activityIcon(invitation.activity.activity_type) }}
            />
          </div>
        );
      })}

      {userLocation ? (
        <div className="cc-fallback-user-marker" style={project(userLocation.lat, userLocation.lng)} />
      ) : null}
    </div>
  );
}

// ── Invitation card ────────────────────────────────────────────────────────

function InvitationCard({
  invitation,
  reveal,
  busy,
  canCheckIn,
  distanceToActivity,
  onAccept,
  onDecline,
  onCheckIn,
  hasUserLocation,
}: {
  invitation: Invitation;
  reveal: Reveal | null;
  busy: string | null;
  canCheckIn: boolean;
  distanceToActivity: number | null;
  onAccept: () => void;
  onDecline: () => void;
  onCheckIn: () => void;
  hasUserLocation: boolean;
}) {
  const activity = invitation.activity;
  const joined = invitation.status === "accepted";
  const declined = invitation.status === "declined";

  const rows = [
    [Clock, activity.date_time_label || "Saturday morning"],
    [MapPin, activity.location.name],
    [Users, `${activity.group_size} people`],
    [Footprints, `Pace · ${activity.pace}`],
    [UserCheck, `Host · ${activity.host}`],
    [Wallet, activity.cost],
    ...(activity.accessibility?.includes("step_free_route")
      ? [[Accessibility, "Step-free route"] as const]
      : []),
  ] as const;

  const proximityText =
    !hasUserLocation
      ? "Location unavailable. Check-in unlocks when your location is available near the meeting point."
      : distanceToActivity !== null && distanceToActivity <= 50
        ? "You're close enough to check in."
        : `${Math.round(distanceToActivity ?? 0)}m away · Circle Reveal unlocks within 50m.`;

  return (
    <div className="space-y-5">
      <header className="space-y-2 pr-10">
        <Chip tone="sage">{activity.activity_type}</Chip>
        <h2 className="text-[22px] font-medium leading-tight text-foreground">{activity.title}</h2>
        <p className="text-sm text-muted-foreground">
          A calm hosted activity with a small group.
        </p>
      </header>

      <dl className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-background/60 p-4 text-sm sm:grid-cols-2">
        {rows.map(([Icon, label], index) => (
          <Row
            key={String(label)}
            icon={<Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" strokeWidth={1.6} />}
            className={index === rows.length - 1 && rows.length % 2 !== 0 ? "sm:col-span-2" : ""}
          >
            {label}
          </Row>
        ))}
      </dl>

      <section className="space-y-2">
        <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Sparkles className="h-4 w-4 text-muted-foreground" strokeWidth={1.6} />
          Why this may fit
        </h3>
        <p className="text-sm text-muted-foreground">{activity.why_fit}</p>
      </section>

      <section className="space-y-2 rounded-2xl bg-secondary/60 p-4">
        <h3 className="text-sm font-medium text-foreground">What to expect</h3>
        <p className="text-sm text-muted-foreground">
          Sofia can arrive quietly, meet the host near the entrance, and take part at her own pace.
          No browsing people. No pressure.
        </p>
      </section>

      <div className="flex flex-wrap gap-1.5">
        <Chip tone="sage">Host present</Chip>
        <Chip tone="mist">Small group</Chip>
        <Chip tone="peach">No prep needed</Chip>
        {activity.accessibility?.includes("step_free_route") && <Chip>Step-free</Chip>}
      </div>

      {/* Action area */}
      {joined ? (
        <div className="space-y-3 rounded-2xl border border-border bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] p-4 text-sm">
          <div>
            <p className="font-medium text-foreground">You&apos;re in.</p>
            <p className="mt-1 text-muted-foreground">Attendee details stay hidden until check-in.</p>
          </div>
          <button
            onClick={onCheckIn}
            disabled={busy !== null || !canCheckIn}
            className="w-full rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition hover:bg-secondary disabled:opacity-40"
          >
            Check in
          </button>
        </div>
      ) : declined ? (
        <div className="rounded-2xl border border-border bg-secondary/60 p-4 text-sm">
          <p className="font-medium text-foreground">That&apos;s okay.</p>
          <p className="mt-1 text-muted-foreground">Not this time is always okay.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button
            onClick={onAccept}
            disabled={busy !== null}
            className="flex items-center justify-center gap-2 rounded-2xl bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium text-foreground shadow-soft transition hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
          >
            <Heart className="h-4 w-4" strokeWidth={1.8} />
            Join
          </button>
          <button
            onClick={onCheckIn}
            disabled={busy !== null || !canCheckIn}
            title={canCheckIn ? "Check in" : "Accept invitation and get within 50m first"}
            className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition hover:bg-secondary disabled:opacity-40"
          >
            <Check className="h-4 w-4" strokeWidth={1.8} />
            Check in
          </button>
          <button
            onClick={onDecline}
            disabled={busy !== null}
            className="flex items-center justify-center gap-2 rounded-2xl px-4 py-3 text-sm font-medium text-muted-foreground transition hover:bg-secondary"
          >
            <X className="h-4 w-4" strokeWidth={1.8} />
            Not this time
          </button>
        </div>
      )}

      {/* Proximity status */}
      <div className="rounded-2xl border border-border bg-background/40 px-4 py-3">
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Navigation className="h-3.5 w-3.5 shrink-0" strokeWidth={1.6} />
          {proximityText}
        </p>
      </div>

      <CircleReveal
        reveal={reveal}
        checkedIn={!!reveal && !reveal.locked}
        busy={busy}
        canCheckIn={canCheckIn}
        onCheckIn={onCheckIn}
      />

      {reveal && !reveal.locked ? (
        <Link
          href="/reflection"
          className="flex items-center justify-center rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition hover:bg-secondary"
        >
          Post-event reflection
        </Link>
      ) : null}

      <p className="text-center text-xs text-muted-foreground">
        Attendee cards unlock only after check-in.
      </p>
    </div>
  );
}

// ── Circle reveal ──────────────────────────────────────────────────────────

function CircleReveal({
  reveal,
  checkedIn,
  busy,
  canCheckIn,
  onCheckIn,
}: {
  reveal: Reveal | null;
  checkedIn: boolean;
  busy: string | null;
  canCheckIn: boolean;
  onCheckIn: () => void;
}) {
  return (
    <section className="space-y-5 rounded-2xl border border-border bg-background/60 p-5">
      <header>
        <h3 className="text-base font-medium text-foreground">Your circle is forming</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          A host will meet everyone near the entrance.
        </p>
      </header>

      <div className="flex flex-wrap gap-1.5">
        <Chip tone="sage">
          <Sparkles className="h-3 w-3" strokeWidth={1.8} /> Calm
        </Chip>
        <Chip tone="mist">Small group</Chip>
        <Chip tone="peach">No pressure</Chip>
      </div>

      <div className="rounded-2xl bg-card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Lock className="h-4 w-4 text-muted-foreground" strokeWidth={1.6} />
            Circle Reveal
          </h4>
          {checkedIn ? <Chip tone="sage">Checked in</Chip> : null}
        </div>

        {!reveal || reveal.locked ? (
          <>
            <ul className="space-y-1.5 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <UserCheck className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.6} />
                Attendee cards stay locked before arrival.
              </li>
              <li className="flex items-start gap-2">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.6} />
                Check in within 50m of the meeting point to reveal your circle.
              </li>
            </ul>
            <button
              onClick={onCheckIn}
              disabled={busy !== null || !canCheckIn}
              className="mt-4 w-full rounded-2xl border border-border bg-secondary/70 px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-secondary"
            >
              {canCheckIn ? "Check in now" : "Check in unlocks within 50m"}
            </button>
          </>
        ) : (
          <div className="space-y-3">
            {reveal.attendees.map((attendee) => (
              <div
                key={attendee.first_name}
                className="rounded-2xl border border-border bg-background/60 p-4"
              >
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-full bg-[color-mix(in_oklab,var(--mist)_30%,white)] text-sm font-medium text-foreground">
                    {attendee.first_name[0]}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">{attendee.first_name}</p>
                    <p className="text-xs text-muted-foreground">{attendee.short_bio}</p>
                  </div>
                </div>
                <div className="mt-3 text-xs">
                  <p className="text-muted-foreground">
                    <span className="text-foreground/80">Icebreaker · </span>
                    {attendee.conversation_starter}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Profile panel ──────────────────────────────────────────────────────────

function ProfilePanel({
  resident,
  catalog,
  onClose,
  onSaved,
}: {
  resident: Resident;
  catalog: PreferenceCatalog | null;
  onClose: () => void;
  onSaved: (resident: Resident) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [contactOpen, setContactOpen] = useState(false);

  const [interests, setInterests] = useState<string[]>(resident.interests ?? []);
  const [activityPrefs, setActivityPrefs] = useState<string[]>(resident.activity_preferences ?? []);
  const [accessibilityNeeds, setAccessibilityNeeds] = useState<string[]>(
    resident.accessibility_needs ?? []
  );
  const [avoid, setAvoid] = useState<string[]>(resident.avoid ?? []);
  const [availability, setAvailability] = useState<string[]>(resident.availability ?? []);
  const [socialComfort, setSocialComfort] = useState(resident.social_comfort ?? "");
  const [costSensitivity, setCostSensitivity] = useState(resident.cost_sensitivity ?? "");
  const [groupMin, setGroupMin] = useState(
    resident.preferred_group_size?.min ?? resident.preferred_group_size_min ?? 3
  );
  const [groupMax, setGroupMax] = useState(
    resident.preferred_group_size?.max ?? resident.preferred_group_size_max ?? 6
  );

  async function save() {
    setSaving(true);
    setSaveError(null);
    setSaveMessage(null);
    try {
      const response = await api.patchPreferences(resident.id, {
        interests,
        activity_preferences: activityPrefs,
        accessibility_needs: accessibilityNeeds,
        avoid,
        availability,
        social_comfort: socialComfort,
        cost_sensitivity: costSensitivity,
        preferred_group_size_min: groupMin,
        preferred_group_size_max: groupMax,
      });
      devLog("preference save response", response);
      setSaveMessage("Preferences saved.");
      onSaved(response.resident);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-foreground/15" onClick={onClose} />
      <aside className="relative ml-auto flex h-full w-full max-w-lg flex-col overflow-y-auto bg-card shadow-float">
        <div className="flex items-center justify-between border-b border-border px-6 py-4">
          <h2 className="text-base font-medium text-foreground">Your Profile</h2>
          <button
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-border text-muted-foreground transition hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-6 px-6 py-5 pb-24">
          {/* Locked identity fields */}
          <section className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Identity &amp; Referral
            </h3>
            <div className="rounded-2xl border border-border bg-background/60 p-4 space-y-3">
              <LockedField label="Name" value={resident.first_name} />
              <LockedField label="Email" value={resident.email} />
              <LockedField
                label="Location"
                value={resident.approx_location || resident.city || ""}
              />
              {resident.referred_by && (
                <LockedField label="Referred by" value={resident.referred_by} />
              )}
              {!!resident.consent_scopes?.length && (
                <LockedField label="Consents" value={resident.consent_scopes.join(", ")} />
              )}
              <div className="pt-1">
                <p className="text-xs text-muted-foreground">Need to change this?</p>
                <button
                  onClick={() => setContactOpen(true)}
                  className="mt-1 inline-flex items-center gap-1.5 rounded-xl border border-border bg-card/80 px-3 py-2 text-xs font-medium text-foreground transition hover:bg-secondary"
                >
                  Contact a trusted referral
                </button>
              </div>
            </div>
          </section>

          {/* Editable preferences */}
          <section className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Your Preferences
            </h3>

            {!catalog ? (
              <p className="rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
                Loading catalog options...
              </p>
            ) : null}

            <OptionGroup
              label="Interests"
              options={catalog?.interests ?? []}
              values={interests}
              onChange={setInterests}
            />

            <OptionGroup
              label="Preferred Activities"
              options={catalog?.activity_types ?? []}
              values={activityPrefs}
              onChange={setActivityPrefs}
              tall
            />

            <OptionGroup
              label="Accessibility Needs"
              options={catalog?.accessibility_needs ?? []}
              values={accessibilityNeeds}
              onChange={setAccessibilityNeeds}
            />

            <OptionGroup
              label="Availability"
              options={catalog?.availability ?? []}
              values={availability}
              onChange={setAvailability}
            />

            <OptionGroup
              label="Avoid"
              options={catalog?.avoid ?? []}
              values={avoid}
              onChange={setAvoid}
            />

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Social comfort</label>
              <select
                value={socialComfort}
                onChange={(e) => setSocialComfort(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                {(catalog?.social_comfort ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Cost sensitivity</label>
              <select
                value={costSensitivity}
                onChange={(e) => setCostSensitivity(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                {(catalog?.cost_sensitivity ?? []).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Min group size</label>
                <input
                  type="number"
                  min={1}
                  max={groupMax}
                  value={groupMin}
                  onChange={(e) => setGroupMin(Number(e.target.value))}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Max group size</label>
                <input
                  type="number"
                  min={groupMin}
                  max={30}
                  value={groupMax}
                  onChange={(e) => setGroupMax(Number(e.target.value))}
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
            </div>
          </section>

          {saveError && (
            <p className="rounded-xl border border-border bg-background/60 px-4 py-3 text-sm text-muted-foreground">
              {saveError}
            </p>
          )}

          {saveMessage && (
            <p className="rounded-xl border border-border bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] px-4 py-3 text-sm text-foreground">
              {saveMessage}
            </p>
          )}

          <button
            onClick={save}
            disabled={saving || !catalog}
            className="w-full rounded-2xl bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium text-foreground shadow-soft transition hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save preferences"}
          </button>
        </div>
      </aside>

      {contactOpen && (
        <div className="absolute inset-0 z-10 flex items-center justify-center p-6">
          <div className="w-full max-w-sm rounded-3xl border border-border bg-card p-6 shadow-float">
            <h3 className="text-base font-medium text-foreground">Contact a trusted referral</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Your trusted referral can help update identity or referral details.
            </p>
            <button
              onClick={() => setContactOpen(false)}
              className="mt-4 w-full rounded-2xl border border-border bg-secondary/70 px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-secondary"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function LockedField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-sm text-foreground/50">{value}</p>
    </div>
  );
}

function OptionGroup({
  label,
  options,
  values,
  onChange,
  tall = false,
}: {
  label: string;
  options: CatalogOption[];
  values: string[];
  onChange: (values: string[]) => void;
  tall?: boolean;
}) {
  const selected = new Set(values);
  const toggle = (value: string) => {
    onChange(selected.has(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-foreground">{label}</label>
      <div
        className={`flex flex-wrap gap-1.5 overflow-y-auto rounded-2xl border border-border bg-background/50 p-2 ${
          tall ? "max-h-56" : "max-h-36"
        }`}
      >
        {options.length ? (
          options.map((option) => {
            const active = selected.has(option.value);
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => toggle(option.value)}
                className={`min-h-10 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  active
                    ? "border-foreground/40 bg-[color-mix(in_oklab,var(--sage)_30%,white)] text-foreground"
                    : "border-border bg-card/70 text-muted-foreground hover:bg-secondary"
                }`}
              >
                {option.label}
              </button>
            );
          })
        ) : (
          <p className="px-2 py-2 text-xs text-muted-foreground">Catalog options unavailable.</p>
        )}
      </div>
    </div>
  );
}

// ── Shared UI ──────────────────────────────────────────────────────────────

function Chip({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "sage" | "mist" | "peach";
}) {
  const tones: Record<string, string> = {
    default: "bg-secondary text-muted-foreground",
    sage: "bg-[color-mix(in_oklab,var(--sage)_28%,white)] text-foreground",
    mist: "bg-[color-mix(in_oklab,var(--mist)_28%,white)] text-foreground",
    peach: "bg-[color-mix(in_oklab,var(--peach)_30%,white)] text-foreground",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function Row({
  icon,
  children,
  className = "",
}: {
  icon: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-start gap-2.5 ${className}`}>
      {icon}
      <span className="text-foreground/80">{children}</span>
    </div>
  );
}

function MobileSheet({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div
      className={`fixed inset-0 z-50 transition lg:hidden ${
        open ? "pointer-events-auto" : "pointer-events-none"
      }`}
      aria-hidden={!open}
    >
      <div
        onClick={onClose}
        className={`absolute inset-0 bg-foreground/10 transition-opacity duration-300 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      />
      <div
        className={`absolute bottom-0 left-0 right-0 mx-auto max-h-[88vh] w-full max-w-xl overflow-y-auto rounded-t-[28px] border border-b-0 border-border bg-card p-5 pb-24 shadow-float transition-transform duration-300 ${
          open ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-border" />
        <button
          onClick={onClose}
          className="absolute right-4 top-4 grid h-9 w-9 place-items-center rounded-full border border-border bg-card text-muted-foreground transition hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
        {children}
      </div>
    </div>
  );
}

function ResidentTabs({ onProfileClick }: { onProfileClick: () => void }) {
  const tabs = [
    { href: "/", label: "Map", icon: Map },
    { href: "/reflection", label: "Reflect", icon: CalendarDays },
  ] as const;

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-card/95 backdrop-blur lg:bottom-6 lg:left-6 lg:right-auto lg:w-auto lg:rounded-full lg:border lg:shadow-float">
      <ul className="mx-auto flex max-w-md items-stretch justify-around px-2 py-1.5 lg:max-w-none lg:gap-2 lg:px-3 lg:py-2">
        {tabs.map(({ href, label, icon: Icon }) => (
          <li key={href} className="flex-1 lg:flex-none">
            <Link
              href={href}
              className="flex flex-col items-center gap-0.5 rounded-2xl px-3 py-2 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground lg:flex-row lg:gap-2 lg:text-sm"
            >
              <Icon className="h-5 w-5" strokeWidth={1.6} />
              <span>{label}</span>
            </Link>
          </li>
        ))}
        <li className="flex-1 lg:flex-none">
          <button
            onClick={onProfileClick}
            className="flex w-full flex-col items-center gap-0.5 rounded-2xl px-3 py-2 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground lg:flex-row lg:gap-2 lg:text-sm"
          >
            <User className="h-5 w-5" strokeWidth={1.6} />
            <span>Profile</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
