"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
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
  Sparkles,
  UserCheck,
  Users,
  Wallet,
  X
} from "lucide-react";
import { Activity, Invitation, Reveal, Resident, api } from "@/lib/api";

type MapMode = "2D" | "3D";

const MAPBOX_TOKEN =
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ||
  "pk.eyJ1IjoiamtvbmtsZXdza2kiLCJhIjoiY21wNjloYTN3MG5lbTJ3c2E5MXU4YXkycSJ9.-vyo9RLZNXPEyebVGBi_vg";

export function ResidentMapExperience() {
  const [resident, setResident] = useState<Resident | null>(null);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [selected, setSelected] = useState<Invitation | null>(null);
  const [mode, setMode] = useState<MapMode>("2D");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [reveal, setReveal] = useState<Reveal | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [me, invites] = await Promise.all([api.me(), api.invitations()]);
      setResident(me);
      setInvitations(invites);
      setSelected((current) => current ?? invites[0] ?? null);
      if (invites[0]) {
        setReveal(await api.reveal(invites[0].activity_id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load demo");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function choose(invitation: Invitation) {
    setSelected(invitation);
    setSheetOpen(true);
    setReveal(await api.reveal(invitation.activity_id));
  }

  async function mutate(action: "accept" | "decline" | "check-in") {
    if (!selected) return;
    setBusy(action);
    setError(null);
    try {
      if (action === "accept") {
        const updated = await api.accept(selected.id);
        setSelected(updated);
      }
      if (action === "decline") {
        const updated = await api.decline(selected.id);
        setSelected(updated);
      }
      if (action === "check-in") {
        await api.checkIn(selected.activity_id);
        setReveal(await api.reveal(selected.activity_id));
      }
      setInvitations(await api.invitations());
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
        <MapStage invitations={invitations} selected={selected} mode={mode} onSelect={choose} />
      </div>

      <div className="pointer-events-none absolute left-0 right-0 top-0 z-20 p-4 lg:right-[440px] lg:p-6">
        <div className="mx-auto max-w-md space-y-2 lg:mx-0 lg:max-w-sm">
          <div className="pointer-events-auto rounded-3xl border border-border bg-card/95 px-5 py-4 shadow-float backdrop-blur">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Good {greeting}</p>
            <p className="mt-1 text-[15px] font-medium text-foreground">
              {resident?.first_name ?? "Sofia"} has a gentle invitation nearby
            </p>
            <p className="mt-1 text-xs text-muted-foreground">No rush today.</p>
          </div>
          <div className="pointer-events-auto flex justify-center lg:justify-start">
            <Chip tone="sage">Small group · Hosted · No pressure</Chip>
          </div>
          {error ? (
            <div className="pointer-events-auto rounded-2xl border border-border bg-card/95 px-4 py-3 text-sm text-muted-foreground shadow-soft">
              {error}
            </div>
          ) : null}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-20 right-4 z-20 lg:bottom-6 lg:right-[464px]">
        <div className="pointer-events-auto flex items-center rounded-full border border-border bg-card/95 p-1 shadow-float backdrop-blur">
          {(["2D", "3D"] as const).map((item) => (
            <button
              key={item}
              className={`flex h-10 items-center gap-2 rounded-full px-3 text-xs font-medium transition ${
                mode === item ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
              onClick={() => setMode(item)}
            >
              {item === "3D" ? <Layers3 className="h-3.5 w-3.5" strokeWidth={1.8} /> : <Layers className="h-3.5 w-3.5" strokeWidth={1.8} />}
              {item}
            </button>
          ))}
        </div>
      </div>

      <aside className="absolute bottom-0 right-0 top-0 hidden w-[440px] flex-col overflow-y-auto border-l border-border bg-card p-6 pb-24 lg:flex">
        {selected ? (
          <InvitationCard
            invitation={selected}
            reveal={reveal}
            busy={busy}
            onAccept={() => mutate("accept")}
            onDecline={() => mutate("decline")}
            onCheckIn={() => mutate("check-in")}
          />
        ) : (
          <div className="m-auto max-w-xs text-center">
            <p className="text-base font-medium text-foreground">A gentle option nearby</p>
            <p className="mt-2 text-sm text-muted-foreground">Tap a pin on the map to see Sofia&apos;s calm invitation.</p>
          </div>
        )}
      </aside>

      <MobileSheet open={sheetOpen && !!selected} onClose={() => setSheetOpen(false)}>
        {selected ? (
          <InvitationCard
            invitation={selected}
            reveal={reveal}
            busy={busy}
            onAccept={() => mutate("accept")}
            onDecline={() => mutate("decline")}
            onCheckIn={() => mutate("check-in")}
          />
        ) : null}
      </MobileSheet>

      <ResidentTabs />
    </div>
  );
}

function MapStage({
  invitations,
  selected,
  mode,
  onSelect
}: {
  invitations: Invitation[];
  selected: Invitation | null;
  mode: MapMode;
  onSelect: (invitation: Invitation) => void;
}) {
  return <MapboxMap invitations={invitations} selected={selected} mode={mode} onSelect={onSelect} token={MAPBOX_TOKEN} />;
}

function MapboxMap({
  invitations,
  selected,
  mode,
  onSelect,
  token
}: {
  invitations: Invitation[];
  selected: Invitation | null;
  mode: MapMode;
  onSelect: (invitation: Invitation) => void;
  token: string;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
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
        zoom: 13.6,
        pitch: 0,
        attributionControl: false
      });
      mapRef.current = map;
      map.on("load", () => setMapReady(true));
    });

    return () => {
      mounted = false;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [token]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    let cancelled = false;

    import("mapbox-gl").then((mapboxgl) => {
      if (cancelled) return;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = invitations.map((invitation) => {
        const el = document.createElement("button");
        el.className = "cc-pin";
        el.title = invitation.activity.title;
        el.innerHTML =
          '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/></svg>';
        el.addEventListener("click", (event) => {
          event.stopPropagation();
          onSelect(invitation);
        });
        return new mapboxgl.default.Marker({ element: el })
          .setLngLat([invitation.activity.location.lng, invitation.activity.location.lat])
          .addTo(map);
      });
    });

    return () => {
      cancelled = true;
    };
  }, [invitations, onSelect, mapReady]);

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
                "fill-extrusion-opacity": 0.7
              }
            });
          } catch {
            /* Mapbox style may not expose composite source yet. */
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
    map.easeTo({
      center: [selected.activity.location.lng, selected.activity.location.lat],
      zoom: 14,
      duration: 800
    });
  }, [selected]);

  return <div ref={ref} className="h-full w-full bg-secondary/40" />;
}

function InvitationCard({
  invitation,
  reveal,
  busy,
  onAccept,
  onDecline,
  onCheckIn
}: {
  invitation: Invitation;
  reveal: Reveal | null;
  busy: string | null;
  onAccept: () => void;
  onDecline: () => void;
  onCheckIn: () => void;
}) {
  const activity = invitation.activity;
  const joined = invitation.status === "accepted";
  const declined = invitation.status === "declined";
  const rows = [
    [Clock, `${activity.date_time_label}`],
    [MapPin, activity.location.name],
    [Users, `${activity.group_size} people`],
    [Footprints, `Pace · ${activity.pace}`],
    [UserCheck, `Host · ${activity.host}`],
    [Wallet, activity.cost],
    [Accessibility, "Step-free route"]
  ] as const;

  return (
    <div className="space-y-5">
      <header className="space-y-2 pr-10">
        <Chip tone="sage">Photography walk</Chip>
        <h2 className="text-[22px] font-medium leading-tight text-foreground">{activity.title}</h2>
        <p className="text-sm text-muted-foreground">A calm hosted route through Vondelpark with small shared prompts.</p>
      </header>

      <dl className="grid grid-cols-1 gap-3 rounded-2xl border border-border bg-background/60 p-4 text-sm sm:grid-cols-2">
        {rows.map(([Icon, label], index) => (
          <Row key={label} icon={<Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" strokeWidth={1.6} />} className={index === rows.length - 1 ? "sm:col-span-2" : ""}>
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
          Sofia can arrive quietly, meet Mara near the entrance, and follow a low-pressure walk. No browsing people. No chat.
        </p>
      </section>

      <div className="flex flex-wrap gap-1.5">
        <Chip tone="sage">Host present</Chip>
        <Chip tone="mist">Small group</Chip>
        <Chip tone="peach">No prep needed</Chip>
        <Chip>Companion Pass</Chip>
      </div>

      {joined ? (
        <div className="rounded-2xl border border-border bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] p-4 text-sm">
          <p className="font-medium text-foreground">You&apos;re in.</p>
          <p className="mt-1 text-muted-foreground">We&apos;ll keep attendee details hidden until check-in.</p>
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
            disabled={busy !== null}
            className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition hover:bg-secondary"
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

      <CircleReveal reveal={reveal} onCheckIn={onCheckIn} checkedIn={!!reveal && !reveal.locked} busy={busy} />

      {reveal && !reveal.locked ? (
        <Link
          href="/reflection"
          className="flex items-center justify-center rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition hover:bg-secondary"
        >
          Post-event reflection
        </Link>
      ) : null}

      <p className="text-center text-xs text-muted-foreground">Attendee cards unlock only after check-in.</p>
    </div>
  );
}

function CircleReveal({
  reveal,
  checkedIn,
  busy,
  onCheckIn
}: {
  reveal: Reveal | null;
  checkedIn: boolean;
  busy: string | null;
  onCheckIn: () => void;
}) {
  return (
    <section className="space-y-5 rounded-2xl border border-border bg-background/60 p-5">
      <header>
        <h3 className="text-base font-medium text-foreground">Your circle is forming</h3>
        <p className="mt-1 text-sm text-muted-foreground">5 people confirmed · A host will meet everyone near the entrance.</p>
      </header>

      <div className="flex flex-wrap gap-1.5">
        <Chip tone="sage">
          <Sparkles className="h-3 w-3" strokeWidth={1.8} /> Photography
        </Chip>
        <Chip tone="mist">Parks</Chip>
        <Chip tone="peach">Coffee</Chip>
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
                Tap check in to simulate Sofia arriving at Vondelpark.
              </li>
            </ul>
            <button
              onClick={onCheckIn}
              disabled={busy !== null}
              className="mt-4 w-full rounded-2xl border border-border bg-secondary/70 px-4 py-2.5 text-sm font-medium text-foreground transition hover:bg-secondary"
            >
              Simulate check-in
            </button>
          </>
        ) : (
          <div className="space-y-3">
            {reveal.attendees.map((attendee) => (
              <div key={attendee.first_name} className="rounded-2xl border border-border bg-background/60 p-4">
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

function Chip({
  children,
  tone = "default"
}: {
  children: ReactNode;
  tone?: "default" | "sage" | "mist" | "peach";
}) {
  const tones: Record<string, string> = {
    default: "bg-secondary text-muted-foreground",
    sage: "bg-[color-mix(in_oklab,var(--sage)_28%,white)] text-foreground",
    mist: "bg-[color-mix(in_oklab,var(--mist)_28%,white)] text-foreground",
    peach: "bg-[color-mix(in_oklab,var(--peach)_30%,white)] text-foreground"
  };
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

function Row({ icon, children, className = "" }: { icon: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`flex items-start gap-2.5 ${className}`}>
      {icon}
      <span className="text-foreground/80">{children}</span>
    </div>
  );
}

function MobileSheet({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <div className={`fixed inset-0 z-50 transition lg:hidden ${open ? "pointer-events-auto" : "pointer-events-none"}`} aria-hidden={!open}>
      <div onClick={onClose} className={`absolute inset-0 bg-foreground/10 transition-opacity duration-300 ${open ? "opacity-100" : "opacity-0"}`} />
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

function ResidentTabs() {
  const tabs = [
    { href: "/", label: "Map", icon: Map },
    { href: "/reflection", label: "Reflect", icon: CalendarDays }
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
      </ul>
    </nav>
  );
}
