"use client";

import { useState } from "react";
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
  UserPlus,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { Chip } from "@/components/Chip";
import type { DemoEvent } from "@/lib/demoEvents";

type JoinedState = "none" | "joined" | "declined";

interface InvitationCardProps {
  event: DemoEvent;
}

export function InvitationCard({ event }: InvitationCardProps) {
  const [joined, setJoined] = useState<JoinedState>("none");
  const [checkedIn, setCheckedIn] = useState(false);
  const [companionOpen, setCompanionOpen] = useState(false);
  const [companionCreated, setCompanionCreated] = useState(false);

  return (
    <article className="space-y-5 pb-2">
      <header className="space-y-2">
        <Chip tone="sage" icon={<Sparkles size={12} strokeWidth={1.8} />}>
          {event.type}
        </Chip>
        <h2 className="text-[22px] font-medium leading-tight">{event.title}</h2>
        <p className="text-sm text-muted-foreground">{event.description}</p>
      </header>

      <div className="grid grid-cols-1 gap-y-2 rounded-2xl border border-border bg-card p-4 text-sm sm:grid-cols-2 sm:gap-x-6">
        <Row icon={<CalendarDays size={14} strokeWidth={1.8} />} label={event.dateLabel} />
        <Row icon={<Clock size={14} strokeWidth={1.8} />} label={event.timeLabel} />
        <Row icon={<MapPin size={14} strokeWidth={1.8} />} label={event.location} />
        <Row icon={<Users size={14} strokeWidth={1.8} />} label={`${event.groupSize} people`} />
        <Row icon={<UserCheck size={14} strokeWidth={1.8} />} label={`Host · ${event.host}`} />
        <Row icon={<Wallet size={14} strokeWidth={1.8} />} label={event.cost} />
        <Row
          icon={<Accessibility size={14} strokeWidth={1.8} />}
          label={event.accessibility}
          full
        />
      </div>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium">
          <Sparkles size={14} strokeWidth={1.8} className="text-muted-foreground" />
          Why this may fit
        </h3>
        <p className="text-sm text-muted-foreground">{event.whyFit}</p>
      </section>

      <section className="rounded-2xl bg-secondary/60 p-4 text-sm">
        <p className="font-medium">What to expect</p>
        <p className="mt-1 text-muted-foreground">{event.whatToExpect}</p>
      </section>

      <div className="flex flex-wrap gap-2">
        <Chip tone="sage" icon={<UserCheck size={12} strokeWidth={1.8} />}>
          Host present
        </Chip>
        <Chip tone="mist">Small group</Chip>
        <Chip tone="peach">No prep needed</Chip>
        <Chip>Step-free</Chip>
      </div>

      {joined === "none" && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button
            onClick={() => setJoined("joined")}
            className="flex items-center justify-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium transition-colors hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
          >
            <Heart size={14} strokeWidth={1.8} /> Join
          </button>
          <button
            onClick={() => setCompanionOpen(true)}
            className="flex items-center justify-center gap-2 rounded-full border border-border bg-card px-4 py-3 text-sm font-medium hover:bg-secondary/60"
          >
            <UserPlus size={14} strokeWidth={1.8} /> Bring a friend
          </button>
          <button
            onClick={() => setJoined("declined")}
            className="flex items-center justify-center gap-2 rounded-full px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground"
          >
            <X size={14} strokeWidth={1.8} /> Not this time
          </button>
        </div>
      )}

      {joined === "joined" && (
        <div className="rounded-2xl bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] p-4 text-sm">
          <p className="font-medium">You're in.</p>
          <p className="mt-0.5 text-muted-foreground">
            We'll remind you gently before it starts.
          </p>
        </div>
      )}

      {joined === "declined" && (
        <div className="rounded-2xl bg-secondary/70 p-4 text-sm">
          <p className="font-medium">That's okay. We'll learn from this.</p>
          <p className="mt-0.5 text-muted-foreground">
            Not this time is always okay.
          </p>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Your attendee details stay hidden until check-in.
      </p>

      {joined === "joined" && (
        <CommonGround
          checkedIn={checkedIn}
          onCheckIn={() => setCheckedIn(true)}
        />
      )}

      {companionOpen && (
        <CompanionPass
          created={companionCreated}
          onCreate={() => setCompanionCreated(true)}
          onClose={() => {
            setCompanionOpen(false);
            setCompanionCreated(false);
          }}
        />
      )}
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
        "flex items-center gap-2 text-muted-foreground " + (full ? "sm:col-span-2" : "")
      }
    >
      <span aria-hidden>{icon}</span>
      <span>{label}</span>
    </div>
  );
}

function CommonGround({
  checkedIn,
  onCheckIn,
}: {
  checkedIn: boolean;
  onCheckIn: () => void;
}) {
  return (
    <section className="rounded-2xl border border-border bg-card p-4">
      <p className="text-sm font-medium">Your circle is forming</p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        5 confirmed · shared interests · calm pace · host present
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Chip tone="sage">Photography</Chip>
        <Chip tone="mist">Parks</Chip>
        <Chip tone="peach">Coffee</Chip>
      </div>
      {!checkedIn ? (
        <div className="mt-4 rounded-xl bg-secondary/60 p-4 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Lock size={14} strokeWidth={1.8} />
            Attendee cards unlock when you check in at the meeting point.
          </div>
          <button
            onClick={onCheckIn}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2 text-xs font-medium"
          >
            <Check size={12} strokeWidth={1.8} />
            Simulate check-in
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <Chip tone="sage">Checked in</Chip>
          {[
            {
              name: "Maya",
              bio: "Enjoys film photography, quiet cafés, and city walks.",
              common: "Photography · Parks",
              ice: "Ask me about my favourite photo spot.",
            },
            {
              name: "Ravi",
              bio: "Recent newcomer to Rotterdam. Likes museums and slow mornings.",
              common: "Coffee · Calm pace",
              ice: "Ask me what I'm hoping to discover here.",
            },
            {
              name: "Lin",
              bio: "Library regular, prefers small groups, dog owner.",
              common: "Small groups · Parks",
              ice: "Ask me about local walking routes.",
            },
          ].map((p) => (
            <article
              key={p.name}
              className="rounded-2xl border border-border bg-card p-4"
            >
              <p className="text-sm font-medium">{p.name}</p>
              <p className="mt-1 text-sm text-muted-foreground">{p.bio}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Common ground · {p.common}
              </p>
              <p className="text-xs text-muted-foreground">
                Icebreaker · {p.ice}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function CompanionPass({
  created,
  onCreate,
  onClose,
}: {
  created: boolean;
  onCreate: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-[60] grid place-items-center bg-foreground/15 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-3xl border border-border bg-card p-5 shadow-[var(--shadow-float)]"
      >
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[color-mix(in_oklab,var(--peach)_30%,white)]">
          <UserPlus size={20} strokeWidth={1.7} />
        </div>
        <h3 className="mt-3 text-xl font-medium">Companion Pass</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          You can bring one person you trust. They'll only see the event
          details.
        </p>
        {!created ? (
          <button
            onClick={onCreate}
            className="mt-4 w-full rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
          >
            Create companion pass
          </button>
        ) : (
          <div className="mt-4 rounded-2xl bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] p-4 text-sm">
            <p className="font-medium">Companion pass created.</p>
            <p className="mt-1 text-muted-foreground">
              Share it whenever you're ready — no rush.
            </p>
          </div>
        )}
        <button
          onClick={onClose}
          className="mt-3 w-full rounded-full px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          Close
        </button>
      </div>
    </div>
  );
}
