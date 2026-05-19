"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Accessibility,
  CalendarDays,
  Check,
  Clock,
  Heart,
  Lock,
  MapPin,
  Sparkles,
  UserCheck,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { Chip } from "@/components/Chip";
import { Greeting } from "@/components/Greeting";
import { MapView, type MapMarker } from "@/components/MapView";
import { BottomSheet } from "@/components/BottomSheet";
import {
  api,
  readDemoSession,
  writeDemoSession,
  type CircleReveal,
  type DemoInvitation,
  type ResidentInbox,
} from "@/lib/api";

type Step = "browse" | "accepted" | "checked_in" | "reflected";

const AMSTERDAM = { lat: 52.3702, lng: 4.8952 };

export default function ResidentMapPage() {
  const router = useRouter();
  const [residentId, setResidentId] = useState<string | null>(null);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [inbox, setInbox] = useState<ResidentInbox | null>(null);
  const [selected, setSelected] = useState<DemoInvitation | null>(null);
  const [reveal, setReveal] = useState<CircleReveal | null>(null);
  const [step, setStep] = useState<Step>("browse");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(
    null
  );
  // Track whether we've already seeded nearby activities for this session
  // so the call is fired exactly once per page mount even if the geolocate
  // control re-emits the position as the user moves.
  const seededNearbyRef = useState<{ done: boolean }>(() => ({ done: false }))[0];

  useEffect(() => {
    const session = readDemoSession();
    setResidentId(session.resident_id ?? null);
    setSessionChecked(true);
    if (!session.resident_id) {
      router.replace("/login");
    }
  }, [router]);

  const refreshReveal = useCallback(
    async (invitation: DemoInvitation, rid: string) => {
      try {
        const rev = await api.circleReveal(invitation.activity_id, rid);
        setReveal(rev);
        if (!rev.locked) setStep("checked_in");
        else if (invitation.status === "accepted") setStep("accepted");
        else setStep("browse");
      } catch {
        setReveal(null);
      }
    },
    []
  );

  const load = useCallback(
    async (id: string, focusInvitationId?: string) => {
      setError(null);
      try {
        const data = await api.residentInbox(id);
        setInbox(data);
        const target =
          (focusInvitationId &&
            data.invitations.find((i) => i.id === focusInvitationId)) ||
          data.invitations.find(
            (i) => i.id === readDemoSession().invitation_id
          ) ||
          data.invitations[0] ||
          null;
        setSelected(target);
        if (target) {
          await refreshReveal(target, id);
        } else {
          setReveal(null);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [refreshReveal]
  );

  useEffect(() => {
    if (!residentId) return;
    load(residentId);
  }, [residentId, load]);

  const handleUserLocation = useCallback(
    async (loc: { lat: number; lng: number }) => {
      setUserLocation(loc);
      if (!residentId || seededNearbyRef.done) return;
      seededNearbyRef.done = true;
      try {
        await api.createNearbyActivities(residentId, {
          lat: loc.lat,
          lng: loc.lng,
          count: 4,
        });
        await load(residentId);
      } catch (err) {
        // Seeding is best-effort: if the resident pool is empty (only Jose),
        // the backend returns 422 and we just continue with whatever they had.
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [residentId, load, seededNearbyRef]
  );

  const markers: MapMarker[] = useMemo(() => {
    if (!inbox) return [];
    return inbox.invitations
      .filter(
        (i) =>
          i.activity.venue.lat !== null && i.activity.venue.lng !== null
      )
      .map((i) => ({
        id: i.id,
        latitude: i.activity.venue.lat as number,
        longitude: i.activity.venue.lng as number,
        title: i.activity.title,
      }));
  }, [inbox]);

  function handleSelect(id: string) {
    const inv = inbox?.invitations.find((i) => i.id === id);
    if (!inv || !residentId) return;
    setSelected(inv);
    setSheetOpen(true);
    writeDemoSession({ invitation_id: inv.id });
    refreshReveal(inv, residentId);
  }

  async function accept() {
    if (!selected || !residentId) return;
    setBusy("accept");
    setError(null);
    try {
      await api.acceptInvitation(selected.id, { resident_id: residentId });
      writeDemoSession({ invitation_id: selected.id });
      await load(residentId, selected.id);
      setStep("accepted");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function decline() {
    if (!selected || !residentId) return;
    setBusy("decline");
    setError(null);
    try {
      await api.declineInvitation(selected.id, { resident_id: residentId });
      await load(residentId, selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function checkIn() {
    if (!selected || !residentId) return;
    setBusy("checkin");
    setError(null);
    try {
      await api.checkIn(selected.activity_id, residentId);
      await refreshReveal(selected, residentId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  if (!sessionChecked) {
    return null;
  }

  if (!residentId) {
    return <EmptyResident />;
  }

  const invitationCount = inbox?.invitations.length ?? 0;

  const sheetContent =
    selected && step === "reflected" ? (
      <ReflectionCard
        residentId={residentId}
        activityId={selected.activity_id}
        title={selected.activity.title}
      />
    ) : selected ? (
      <InvitationDetail
        invitation={selected}
        residentName={inbox?.resident.first_name ?? "Sofia"}
        step={step}
        reveal={reveal}
        busy={busy}
        error={error}
        onAccept={accept}
        onDecline={decline}
        onCheckIn={checkIn}
        onReflect={() => setStep("reflected")}
      />
    ) : (
      <NoInvitations />
    );

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] w-full">
      <div className="relative flex-1">
        <MapView
          markers={markers}
          selectedId={selected?.id ?? null}
          onSelect={handleSelect}
          fallbackCenter={userLocation ?? AMSTERDAM}
          onUserLocation={handleUserLocation}
        />

        <div className="pointer-events-none absolute left-1/2 top-4 z-10 w-full max-w-md -translate-x-1/2 px-4">
          <div className="pointer-events-auto space-y-2">
            <Greeting
              invitationCount={invitationCount}
              name={inbox?.resident.first_name ?? "Sofia"}
            />
            <Chip tone="sage">Small groups · Hosted · No pressure</Chip>
          </div>
        </div>

        {invitationCount === 0 && (
          <div className="pointer-events-none absolute inset-0 z-0 grid place-items-center">
            <div className="pointer-events-auto m-4 max-w-sm rounded-3xl border border-border bg-card/90 p-5 text-center shadow-[var(--shadow-soft)] backdrop-blur">
              <p className="text-sm font-medium">No invitations yet.</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Once an operator approves a proposed circle, you'll see a calm
                pin appear on the map.
              </p>
              <p className="mt-3 text-xs text-muted-foreground">
                A welzijnscoach will reach out when there's a calm match.
              </p>
            </div>
          </div>
        )}

        <div className="lg:hidden">
          <BottomSheet open={sheetOpen} onClose={() => setSheetOpen(false)}>
            {sheetContent}
          </BottomSheet>
        </div>
      </div>

      <aside className="hidden w-[440px] flex-col overflow-y-auto border-l border-border bg-card p-6 lg:flex">
        {selected ? (
          sheetContent
        ) : (
          <div className="m-auto max-w-xs text-center">
            <p className="text-base font-medium">A few gentle options nearby</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Tap a pin on the map to see a calm invitation. Not this time is
              always okay.
            </p>
          </div>
        )}
      </aside>
    </div>
  );
}

function EmptyResident() {
  return (
    <div className="mx-auto max-w-md space-y-3 px-4 py-12 text-center">
      <Sparkles
        className="mx-auto text-muted-foreground"
        size={28}
        strokeWidth={1.6}
      />
      <h1 className="text-xl font-medium">Welcome to CivicCircles.</h1>
      <p className="text-sm text-muted-foreground">
        Sign in with the email your huisarts used to register you. Your invitations
        will be waiting in your inbox.
      </p>
      <Link
        href="/login"
        className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-2 text-sm font-medium"
      >
        Sign in
      </Link>
    </div>
  );
}

function NoInvitations() {
  return (
    <div className="space-y-3 py-4 text-center">
      <p className="text-sm font-medium">No invitation selected.</p>
      <p className="text-sm text-muted-foreground">
        Tap a pin on the map to open it.
      </p>
    </div>
  );
}

function InvitationDetail({
  invitation,
  residentName,
  step,
  reveal,
  busy,
  error,
  onAccept,
  onDecline,
  onCheckIn,
  onReflect,
}: {
  invitation: DemoInvitation;
  residentName: string;
  step: Step;
  reveal: CircleReveal | null;
  busy: string | null;
  error: string | null;
  onAccept: () => void;
  onDecline: () => void;
  onCheckIn: () => void;
  onReflect: () => void;
}) {
  const start = useMemo(
    () => new Date(invitation.activity.start_at),
    [invitation.activity.start_at]
  );
  const end = useMemo(
    () => new Date(invitation.activity.end_at),
    [invitation.activity.end_at]
  );
  const dateLabel = start.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
  const timeLabel =
    start.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }) +
    " – " +
    end.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  const isDeclined = invitation.status === "declined";

  return (
    <article className="space-y-5 pb-2">
      <header className="space-y-2">
        <Chip tone="sage" icon={<Sparkles size={12} strokeWidth={1.8} />}>
          {invitation.template_code === "photography_walk"
            ? "Outdoor · photography walk"
            : "Calm · small group"}
        </Chip>
        <h2 className="text-[22px] font-medium leading-tight">
          {invitation.activity.title}
        </h2>
        <p className="text-sm text-muted-foreground">
          A small-group walk focused on calm spaces and shared interests.
          Phones welcome. Host meets you at the entrance.
        </p>
      </header>

      {error && (
        <div className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-y-2 rounded-2xl border border-border bg-card p-4 text-sm sm:grid-cols-2 sm:gap-x-6">
        <Row icon={<CalendarDays size={14} strokeWidth={1.8} />} label={dateLabel} />
        <Row icon={<Clock size={14} strokeWidth={1.8} />} label={timeLabel} />
        <Row
          icon={<MapPin size={14} strokeWidth={1.8} />}
          label={`${invitation.activity.venue.name} · ${invitation.activity.venue.city}`}
        />
        <Row
          icon={<Users size={14} strokeWidth={1.8} />}
          label={`${invitation.members.length} people`}
        />
        {invitation.activity.host && (
          <Row
            icon={<UserCheck size={14} strokeWidth={1.8} />}
            label={`Host · ${invitation.activity.host.full_name}`}
          />
        )}
        <Row
          icon={<Wallet size={14} strokeWidth={1.8} />}
          label={invitation.activity.cost_cents === 0 ? "Free" : "€ low cost"}
        />
        <Row
          icon={<Accessibility size={14} strokeWidth={1.8} />}
          label="Step-free route"
          full
        />
      </div>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles size={14} strokeWidth={1.8} className="text-muted-foreground" />
          Why this may fit
        </h3>
        <p className="text-sm text-muted-foreground">
          Hi {residentName}. We picked this because the people in this circle
          share calm pace, small-group comfort, and an interest in photography
          and parks.
        </p>
      </section>

      <div className="flex flex-wrap gap-2">
        <Chip tone="sage" icon={<UserCheck size={12} strokeWidth={1.8} />}>
          Host present
        </Chip>
        <Chip tone="mist">Small group</Chip>
        <Chip tone="peach">No prep needed</Chip>
        <Chip>Step-free</Chip>
      </div>

      {step === "browse" && !isDeclined && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={onAccept}
            disabled={busy === "accept"}
            className="flex items-center justify-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-60"
          >
            <Heart size={14} strokeWidth={1.8} />
            {busy === "accept" ? "Saving…" : "Yes, I'd like to come"}
          </button>
          <button
            type="button"
            onClick={onDecline}
            disabled={busy === "decline"}
            className="flex items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-60"
          >
            <X size={14} strokeWidth={1.8} />
            Not this time
          </button>
        </div>
      )}

      {isDeclined && (
        <div className="rounded-2xl bg-secondary/70 p-4 text-sm">
          <p className="font-medium">That's okay. We'll learn from this.</p>
          <p className="mt-0.5 text-muted-foreground">
            Not this time is always okay.
          </p>
        </div>
      )}

      {step === "accepted" && (
        <CircleForming locked busy={busy} onCheckIn={onCheckIn} attendees={[]} />
      )}

      {step === "checked_in" && reveal && (
        <CircleForming
          locked={false}
          busy={busy}
          onCheckIn={onCheckIn}
          attendees={reveal.attendees}
          onReflect={onReflect}
        />
      )}

      <p className="text-xs text-muted-foreground">
        Your attendee details stay hidden until check-in.
      </p>
    </article>
  );
}

function CircleForming({
  locked,
  busy,
  onCheckIn,
  attendees,
  onReflect,
}: {
  locked: boolean;
  busy: string | null;
  onCheckIn: () => void;
  attendees: {
    first_name: string;
    common_ground: string[];
    conversation_starter: string;
  }[];
  onReflect?: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card p-4">
      <p className="text-sm font-medium">Your circle is forming</p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Shared interests · calm pace · host present
      </p>
      {locked ? (
        <div className="mt-4 rounded-xl bg-secondary/60 p-4 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Lock size={14} strokeWidth={1.8} />
            Attendee cards unlock when you check in at the meeting point.
          </div>
          <button
            type="button"
            onClick={onCheckIn}
            disabled={busy === "checkin"}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-medium disabled:opacity-60"
          >
            <Check size={12} strokeWidth={1.8} />
            {busy === "checkin" ? "Checking in…" : "I've arrived · check me in"}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <Chip tone="sage">Checked in · circle revealed</Chip>
          {attendees.map((p) => (
            <article
              key={p.first_name}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <p className="text-sm font-medium">{p.first_name}</p>
              {p.common_ground.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Common ground · {p.common_ground.join(" · ")}
                </p>
              )}
              <p className="text-xs text-muted-foreground">
                Icebreaker · {p.conversation_starter}
              </p>
            </article>
          ))}
          {attendees.length === 0 && (
            <p className="text-xs text-muted-foreground">
              No other attendees recorded yet.
            </p>
          )}
          {onReflect && (
            <button
              type="button"
              onClick={onReflect}
              className="mt-2 inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--mist)_45%,white)] px-4 py-2.5 text-sm font-medium"
            >
              After the walk · add a reflection
            </button>
          )}
        </div>
      )}
    </section>
  );
}

function ReflectionCard({
  residentId,
  activityId,
  title,
}: {
  residentId: string;
  activityId: string;
  title: string;
}) {
  const [feltAfter, setFeltAfter] = useState<"worse" | "same" | "better">(
    "better"
  );
  const [wouldRepeat, setWouldRepeat] = useState<boolean | null>(true);
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.submitReflection(activityId, {
        resident_id: residentId,
        felt_after: feltAfter,
        would_repeat: wouldRepeat,
        notes: notes || null,
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <article className="space-y-3 pb-2">
        <Chip tone="sage" icon={<Check size={12} strokeWidth={1.8} />}>
          Reflection saved
        </Chip>
        <h2 className="text-xl font-medium">
          One Saturday morning you didn't spend alone.
        </h2>
        <p className="text-sm text-muted-foreground">
          That's the metric this pilot measures. Thank you for sharing.
        </p>
      </article>
    );
  }

  return (
    <article className="space-y-4 pb-2">
      <header>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Post-event reflection
        </p>
        <h2 className="text-xl font-medium">{title}</h2>
      </header>

      {error && (
        <div className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          How did you feel after?
        </legend>
        <div className="flex flex-wrap gap-2">
          {(["better", "same", "worse"] as const).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => setFeltAfter(v)}
              className={
                "rounded-full px-3 py-1.5 text-xs font-medium " +
                (feltAfter === v
                  ? "bg-[color-mix(in_oklab,var(--sage)_45%,white)]"
                  : "border border-border bg-card text-muted-foreground")
              }
            >
              {v === "better" ? "calmer" : v === "same" ? "same" : "not for me"}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Would you do something similar again?
        </legend>
        <div className="flex flex-wrap gap-2">
          {[
            { v: true, label: "yes" },
            { v: false, label: "no" },
          ].map((opt) => (
            <button
              key={String(opt.v)}
              type="button"
              onClick={() => setWouldRepeat(opt.v)}
              className={
                "rounded-full px-3 py-1.5 text-xs font-medium " +
                (wouldRepeat === opt.v
                  ? "bg-[color-mix(in_oklab,var(--mist)_45%,white)]"
                  : "border border-border bg-card text-muted-foreground")
              }
            >
              {opt.label}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          One line (optional)
        </span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          placeholder="One sentence is enough."
          className="w-full rounded-2xl border border-border bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </label>

      <button
        type="button"
        onClick={save}
        disabled={busy}
        className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-5 py-2.5 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-60"
      >
        <Check size={14} strokeWidth={1.8} />
        {busy ? "Saving…" : "Save reflection"}
      </button>
    </article>
  );
}

function Row({
  icon,
  label,
  full,
}: {
  icon: React.ReactNode;
  label: string;
  full?: boolean;
}) {
  return (
    <div
      className={
        "flex items-center gap-2 text-muted-foreground " +
        (full ? "sm:col-span-2" : "")
      }
    >
      <span aria-hidden>{icon}</span>
      <span>{label}</span>
    </div>
  );
}
