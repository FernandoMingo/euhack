"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  Footprints,
  MapPin,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { Chip } from "@/components/Chip";
import {
  api,
  readDemoSession,
  writeDemoSession,
  type DemoInvitation,
  type OperatorInbox,
  type PendingReferral,
  type Proposal,
} from "@/lib/api";

export default function OperatorPage() {
  const [inbox, setInbox] = useState<OperatorInbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [justSent, setJustSent] = useState<DemoInvitation[] | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setInbox(await api.operatorInbox());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const consentVersion =
    inbox?.consent_text_version ??
    inbox?.proposals[0]?.consent_text_version ??
    "v1.0-nl-2026-05";

  async function runMatching(referral: PendingReferral) {
    setBusy("match:" + referral.referral_id);
    setError(null);
    setJustSent(null);
    try {
      const proposal = await api.orchestrateReferral(referral.referral_id, {
        preferred_template_code: "photography_walk",
      });
      writeDemoSession({
        referral_id: referral.referral_id,
        resident_id: referral.resident.id,
        resident_first_name: referral.resident.first_name,
        circle_id: proposal.circle_id,
        activity_id: proposal.activity.id,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function approve(proposal: Proposal) {
    setBusy("approve:" + proposal.circle_id);
    setError(null);
    try {
      const invitations = await api.approveProposal(proposal.circle_id, {
        operator_id: "operator_demo",
      });
      const sofia = readDemoSession().resident_id;
      const sofiaInvite =
        invitations.find((i) => i && sofia && i.activity_id === proposal.activity.id) ??
        invitations[0];
      if (sofiaInvite) {
        writeDemoSession({
          invitation_id: sofiaInvite.id,
          activity_id: sofiaInvite.activity_id,
          circle_id: sofiaInvite.circle_id,
        });
      }
      setJustSent(invitations);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function reject(proposal: Proposal) {
    setBusy("reject:" + proposal.circle_id);
    setError(null);
    try {
      await api.rejectProposal(proposal.circle_id, {
        operator_id: "operator_demo",
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  const proposals = inbox?.proposals ?? [];
  const pending = inbox?.pending_referrals ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Operator · municipal dashboard
        </p>
        <h1 className="text-[26px] font-medium leading-tight">
          AI proposes. You approve.
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          The transparent layer between matching and a public invitation. Every
          decision logs against consent text{" "}
          <span className="rounded bg-secondary px-1 py-0.5 font-mono text-xs">
            {consentVersion}
          </span>
          . AI never publishes alone.
        </p>
      </header>

      {error && (
        <div className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {justSent && justSent.length > 0 && (
        <div className="rounded-2xl bg-[color-mix(in_oklab,var(--sage)_18%,var(--card))] p-4 text-sm">
          <p className="font-medium">
            Approved · {justSent.length} invitation
            {justSent.length === 1 ? "" : "s"} dispatched.
          </p>
          <p className="mt-0.5 text-muted-foreground">
            Open <span className="font-mono">/login</span> and sign in as that
            resident to see the invitation land in their inbox.
          </p>
        </div>
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          icon={<Users size={16} strokeWidth={1.8} />}
          label="Pending referrals"
          value={String(pending.length)}
          tone="default"
        />
        <Stat
          icon={<Sparkles size={16} strokeWidth={1.8} />}
          label="Proposals to review"
          value={String(proposals.length)}
          tone="sage"
        />
        <Stat
          icon={<UserCheck size={16} strokeWidth={1.8} />}
          label="Operator in the loop"
          value="Required"
          tone="mist"
        />
        <Stat
          icon={<ShieldCheck size={16} strokeWidth={1.8} />}
          label="Pilot consent text"
          value={consentVersion}
          tone="peach"
        />
      </section>

      {proposals.length > 0 && (
        <Panel
          title="AI-generated proposals"
          subtitle="Click Approve to dispatch invitations. Click Reject to send the matching engine back."
        >
          <div className="space-y-4">
            {proposals.map((p) => (
              <ProposalCard
                key={p.circle_id}
                proposal={p}
                busy={busy}
                onApprove={() => approve(p)}
                onReject={() => reject(p)}
              />
            ))}
          </div>
        </Panel>
      )}

      <Panel
        title="Pending referrals"
        subtitle="Submitted by trusted professionals. Run matching to see a proposed circle."
      >
        {pending.length === 0 ? (
          <Empty
            text="No pending referrals."
            hint="Submit one from /staff/professional to see matching run."
          />
        ) : (
          <ul className="divide-y divide-border">
            {pending.map((r) => (
              <li
                key={r.referral_id}
                className="flex flex-wrap items-start justify-between gap-3 py-3"
              >
                <div>
                  <p className="text-sm font-medium">
                    {r.resident.first_name}{" "}
                    <span className="text-xs font-normal text-muted-foreground">
                      · {r.resident.neighborhood ?? "Amsterdam"} · group{" "}
                      {r.resident.preferred_group_size_min}–
                      {r.resident.preferred_group_size_max}
                    </span>
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Referred by {r.professional.full_name} ({r.professional.role})
                  </p>
                  {r.referral_reason && (
                    <p className="mt-1 text-xs italic text-muted-foreground">
                      "{r.referral_reason}"
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  disabled={busy === "match:" + r.referral_id}
                  onClick={() => runMatching(r)}
                  className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--mist)_45%,white)] px-4 py-2 text-xs font-medium disabled:opacity-60"
                >
                  <Sparkles size={12} strokeWidth={1.8} />
                  {busy === "match:" + r.referral_id
                    ? "Running matching…"
                    : "Run matching"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <section className="rounded-3xl border border-border bg-secondary/50 p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Audit trail · privacy guardrails
        </p>
        <ul className="mt-3 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          <Bullet>
            Every match decision logs against consent text {consentVersion}.
          </Bullet>
          <Bullet>
            No clinical data flows through matching. Only the lightweight
            social profile.
          </Bullet>
          <Bullet>
            Peer ratings stay internal-only, never resident-visible.
          </Bullet>
          <Bullet>
            EU AI Act: limited-risk system. Human-in-the-loop on every
            invitation.
          </Bullet>
        </ul>
      </section>
    </div>
  );
}

function ProposalCard({
  proposal,
  busy,
  onApprove,
  onReject,
}: {
  proposal: Proposal;
  busy: string | null;
  onApprove: () => void;
  onReject: () => void;
}) {
  const start = useMemo(
    () => new Date(proposal.activity.start_at),
    [proposal.activity.start_at]
  );
  const dateLabel = start.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "short",
  });
  const timeLabel = start.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  return (
    <article className="rounded-3xl border border-border bg-card p-5 shadow-[var(--shadow-soft)]">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <Chip tone="sage" icon={<Sparkles size={12} strokeWidth={1.8} />}>
            AI-generated proposal
          </Chip>
          <h3 className="text-[20px] font-medium leading-tight">
            {proposal.template_title || proposal.activity.title}
          </h3>
          <p className="text-sm text-muted-foreground">
            {proposal.summary_text}
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Fit score
          </p>
          <p className="text-lg font-medium">
            {proposal.fit_score?.toFixed(2) ?? "—"}
          </p>
        </div>
      </header>

      <div className="mt-4 grid grid-cols-1 gap-2 rounded-2xl border border-border bg-secondary/40 p-4 text-sm sm:grid-cols-2">
        <Row icon={<CalendarDays size={14} strokeWidth={1.8} />} label={dateLabel} />
        <Row icon={<Clock size={14} strokeWidth={1.8} />} label={timeLabel} />
        <Row
          icon={<MapPin size={14} strokeWidth={1.8} />}
          label={`${proposal.activity.venue.name} · ${proposal.activity.venue.city}`}
        />
        <Row
          icon={<Users size={14} strokeWidth={1.8} />}
          label={`${proposal.members.length} of ${proposal.activity.capacity} residents`}
        />
        {proposal.activity.host && (
          <Row
            icon={<UserCheck size={14} strokeWidth={1.8} />}
            label={`Host · ${proposal.activity.host.full_name}`}
          />
        )}
        <Row
          icon={<Footprints size={14} strokeWidth={1.8} />}
          label="Step-free route"
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Anonymous circle
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {proposal.members.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2">
                <span>{m.first_name}</span>
                <span className="text-xs text-muted-foreground">
                  group {m.preferred_group_size_min}–{m.preferred_group_size_max}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Shared signals
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {proposal.shared_interests.length === 0 && (
              <span className="text-xs italic text-muted-foreground">
                None recorded
              </span>
            )}
            {proposal.shared_interests.map((tag) => (
              <Chip key={"i-" + tag} tone="mist">
                {tag}
              </Chip>
            ))}
            {proposal.shared_availability.map((tag) => (
              <Chip key={"a-" + tag}>{tag}</Chip>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Consent text {proposal.consent_text_version}
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy === "approve:" + proposal.circle_id}
          onClick={onApprove}
          className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-5 py-2.5 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-60"
        >
          <CheckCircle2 size={14} strokeWidth={1.8} />
          {busy === "approve:" + proposal.circle_id
            ? "Sending invitations…"
            : "Approve · send invitations"}
        </button>
        <button
          type="button"
          disabled={busy === "reject:" + proposal.circle_id}
          onClick={onReject}
          className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2.5 text-sm font-medium text-muted-foreground hover:text-foreground disabled:opacity-60"
        >
          <X size={14} strokeWidth={1.8} />
          Reject
        </button>
      </div>
    </article>
  );
}

function Stat({
  icon,
  label,
  value,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: "sage" | "mist" | "peach" | "default";
}) {
  const bg =
    tone === "sage"
      ? "bg-[color-mix(in_oklab,var(--sage)_25%,white)]"
      : tone === "mist"
        ? "bg-[color-mix(in_oklab,var(--mist)_25%,white)]"
        : tone === "peach"
          ? "bg-[color-mix(in_oklab,var(--peach)_25%,white)]"
          : "bg-card";
  return (
    <div
      className={`rounded-2xl border border-border ${bg} p-4 shadow-[var(--shadow-soft)]`}
    >
      <div className="mb-1 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="text-base font-medium">{value}</p>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-border bg-card p-5 shadow-[var(--shadow-soft)]">
      <header className="mb-3 space-y-0.5">
        <h2 className="text-sm font-medium">{title}</h2>
        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}
      </header>
      {children}
    </section>
  );
}

function Empty({ text, hint }: { text: string; hint?: string }) {
  return (
    <div className="rounded-2xl bg-secondary/40 px-4 py-6 text-center text-sm text-muted-foreground">
      <p>{text}</p>
      {hint && <p className="mt-1 text-xs italic">{hint}</p>}
    </div>
  );
}

function Row({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2 text-muted-foreground">
      <span aria-hidden>{icon}</span>
      <span>{label}</span>
    </div>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <CheckCircle2
        size={16}
        strokeWidth={1.8}
        className="mt-0.5 shrink-0 text-muted-foreground"
      />
      <span>{children}</span>
    </li>
  );
}
