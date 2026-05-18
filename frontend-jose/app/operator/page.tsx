"use client";

import { useEffect, useState } from "react";
import {
  Activity as ActivityIcon,
  CheckCircle2,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Users,
} from "lucide-react";
import { Chip } from "@/components/Chip";
import { api, type ActivityTemplate, type Professional, type Resident } from "@/lib/api";

export default function OperatorPage() {
  const [residents, setResidents] = useState<Resident[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [templates, setTemplates] = useState<ActivityTemplate[]>([]);
  const [families, setFamilies] = useState<string[]>([]);
  const [familyFilter, setFamilyFilter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [r, p, fams] = await Promise.all([
          api.listResidents(),
          api.listProfessionals(),
          api.listTemplateFamilies(),
        ]);
        if (!alive) return;
        setResidents(r);
        setProfessionals(p);
        setFamilies(fams);
      } catch (err) {
        if (alive) setError(String(err));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .listTemplates(familyFilter ?? undefined)
      .then((t) => alive && setTemplates(t))
      .catch(() => alive && setTemplates([]));
    return () => {
      alive = false;
    };
  }, [familyFilter]);

  const approved = professionals.filter(
    (p) => p.verification_status === "approved"
  );

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
          The transparent layer between matching and a public invitation.
          Verified professionals, consented residents, the activity catalog, and
          the audit trail.
        </p>
      </header>

      {error && (
        <div className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat
          icon={<Users size={16} strokeWidth={1.8} />}
          label="Consented residents"
          value={loading ? "…" : String(residents.length)}
          tone="sage"
        />
        <Stat
          icon={<UserCheck size={16} strokeWidth={1.8} />}
          label="Approved professionals"
          value={loading ? "…" : `${approved.length} / ${professionals.length}`}
          tone="mist"
        />
        <Stat
          icon={<ActivityIcon size={16} strokeWidth={1.8} />}
          label="Activity templates"
          value={loading ? "…" : String(templates.length)}
          tone="peach"
        />
        <Stat
          icon={<ShieldCheck size={16} strokeWidth={1.8} />}
          label="Pilot consent text"
          value="v1.0-nl-2026-05"
          tone="default"
        />
      </section>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel
          title="Professionals"
          subtitle="Verified seats consume Vektis AGB + CIBG BIG nightly."
        >
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : professionals.length === 0 ? (
            <Empty
              text="No professionals signed up yet."
              hint="Use the Professional tab to add one."
            />
          ) : (
            <ul className="divide-y divide-border">
              {professionals.map((p) => (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-3"
                >
                  <div>
                    <p className="text-sm font-medium">{p.full_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.qualification ?? p.role} · {p.organization ?? "—"} ·
                      AGB {p.agb_code ?? "—"}
                    </p>
                  </div>
                  <Chip
                    tone={
                      p.verification_status === "approved"
                        ? "sage"
                        : p.verification_status === "rejected"
                          ? "peach"
                          : "default"
                    }
                  >
                    {p.verification_status}
                  </Chip>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          title="Residents"
          subtitle="Profiles created with explicit consent. No clinical data attached."
        >
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : residents.length === 0 ? (
            <Empty
              text="No residents yet."
              hint="Submit a referral from the Professional tab."
            />
          ) : (
            <ul className="divide-y divide-border">
              {residents.map((r) => (
                <li
                  key={r.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-3"
                >
                  <div>
                    <p className="text-sm font-medium">{r.first_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {r.neighborhood ?? r.city} · group {r.preferred_group_size_min}–
                      {r.preferred_group_size_max} · {r.social_comfort}
                    </p>
                  </div>
                  <Chip
                    tone={r.status === "active" ? "sage" : "default"}
                  >
                    {r.status}
                  </Chip>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Activity catalog"
        subtitle="The candidate space for matching. Fer's vectorizer turns these into feature vectors."
      >
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setFamilyFilter(null)}
            className={
              "rounded-full px-3 py-1 text-xs font-medium " +
              (familyFilter === null
                ? "bg-[color-mix(in_oklab,var(--sage)_45%,white)]"
                : "border border-border bg-card text-muted-foreground")
            }
          >
            All families
          </button>
          {families.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFamilyFilter(f)}
              className={
                "rounded-full px-3 py-1 text-xs font-medium " +
                (familyFilter === f
                  ? "bg-[color-mix(in_oklab,var(--sage)_45%,white)]"
                  : "border border-border bg-card text-muted-foreground")
              }
            >
              {f}
            </button>
          ))}
        </div>
        {templates.length === 0 ? (
          <Empty
            text="No templates yet."
            hint="Run the seeder: python backend/scripts/seed_activity_catalog.py"
          />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {templates.slice(0, 24).map((t) => (
              <article
                key={t.id}
                className="rounded-2xl border border-border bg-card p-4"
              >
                <p className="text-sm font-medium">{t.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t.family} · {t.typical_duration_minutes}m · group{" "}
                  {t.typical_group_size_min}–{t.typical_group_size_max}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Chip
                    tone={
                      t.typical_cost_band === "free"
                        ? "sage"
                        : t.typical_cost_band === "low"
                          ? "mist"
                          : "peach"
                    }
                  >
                    {t.typical_cost_band}
                  </Chip>
                  <Chip>{t.social_energy}</Chip>
                  <Chip>{t.setting}</Chip>
                </div>
              </article>
            ))}
          </div>
        )}
        {templates.length > 24 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Showing 24 of {templates.length}. Use family filter to narrow.
          </p>
        )}
      </Panel>

      <section className="rounded-3xl border border-border bg-secondary/50 p-6">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Privacy guardrails
        </p>
        <ul className="mt-3 grid grid-cols-1 gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          <li className="flex items-start gap-2">
            <CheckCircle2 size={16} strokeWidth={1.8} className="mt-0.5" />
            <span>No clinical data flows through the matching layer.</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 size={16} strokeWidth={1.8} className="mt-0.5" />
            <span>Peer ratings are internal-only, never resident-visible.</span>
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle2 size={16} strokeWidth={1.8} className="mt-0.5" />
            <span>
              Every consent is versioned (text + locale + capture method).
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Sparkles size={16} strokeWidth={1.8} className="mt-0.5" />
            <span>
              AI proposes. You approve. AI never publishes an activity alone.
            </span>
          </li>
        </ul>
      </section>
    </div>
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
      <p className="text-xl font-medium">{value}</p>
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
