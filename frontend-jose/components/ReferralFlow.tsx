"use client";

import { useState } from "react";
import { Check, ShieldCheck } from "lucide-react";
import {
  ApiError,
  api,
  writeDemoSession,
  type Professional,
  type ReferralCreateResponse,
} from "@/lib/api";

type Step = "consent" | "profile" | "submitted";

const INTERESTS = [
  "Walks",
  "Photography",
  "Parks",
  "Coffee",
  "Museums",
  "Board games",
  "Gardening",
  "Cooking",
  "Library events",
  "Volunteering",
];

const AVOIDANCES = [
  "Alcohol",
  "Loud places",
  "Late evenings",
  "Large groups",
  "Long travel",
];

const ACCESSIBILITY = [
  "Step-free route",
  "Seating available",
  "Quiet environment",
  "Host present",
  "Clear meeting point",
];

interface Props {
  professional: Professional;
}

export function ReferralFlow({ professional }: Props) {
  const [step, setStep] = useState<Step>("consent");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState<ReferralCreateResponse | null>(
    null
  );

  // Resident profile state
  const [first_name, setFirstName] = useState("Sofia");
  const [email, setEmail] = useState("sofia@example.nl");
  const [neighborhood, setNeighborhood] = useState("Oud-West");
  const [comfort, setComfort] = useState("small_group_low_pressure");
  const [groupMin, setGroupMin] = useState(3);
  const [groupMax, setGroupMax] = useState(6);
  const [interests, setInterests] = useState<string[]>(["Photography", "Parks"]);
  const [avoidances, setAvoidances] = useState<string[]>(["Alcohol"]);
  const [accessibility, setAccessibility] = useState<string[]>([]);
  const [captureMethod, setCaptureMethod] = useState<
    "in_consult" | "self_completion"
  >("in_consult");
  const [referralReason, setReferralReason] = useState(
    "Feels isolated, recently widowed"
  );

  function toggle(list: string[], v: string, set: (v: string[]) => void) {
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  }

  async function submit() {
    setError(null);
    try {
      const res = await api.createReferral({
        professional_id: professional.id,
        profile: {
          first_name,
          email,
          preferred_language: "nl",
          city: professional.city ?? "Amsterdam",
          social_comfort: comfort,
          preferred_group_size_min: groupMin,
          preferred_group_size_max: groupMax,
          cost_sensitivity: "free_or_low_cost",
          neighborhood,
          interests: interests.map((s) => s.toLowerCase()),
          accessibility_needs: accessibility,
          avoidances: avoidances.map((s) => s.toLowerCase()),
        },
        capture_method: captureMethod,
        referral_reason: referralReason,
      });
      setSubmitted(res);
      writeDemoSession({
        resident_id: res.resident.id,
        resident_first_name: res.resident.first_name,
        referral_id: res.referral.id,
      });
      setStep("submitted");
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(String(err));
    }
  }

  if (step === "consent") {
    return (
      <ConsentScreen
        onAccept={() => setStep("profile")}
        captureMethod={captureMethod}
        onCaptureMethod={setCaptureMethod}
      />
    );
  }

  if (step === "submitted" && submitted) {
    return (
      <section className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-soft)]">
        <div className="flex items-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[color-mix(in_oklab,var(--sage)_35%,white)]">
            <Check size={18} strokeWidth={1.8} />
          </span>
          <div>
            <p className="text-base font-medium">Referral submitted.</p>
            <p className="text-sm text-muted-foreground">
              The welzijnscoach will reach out to {submitted.resident.first_name}{" "}
              this week.
            </p>
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <DlRow term="Resident" value={submitted.resident.first_name} />
          <DlRow term="Neighborhood" value={submitted.resident.neighborhood ?? "—"} />
          <DlRow
            term="Consent text"
            value={submitted.consent.consent_text_version}
          />
          <DlRow term="Capture" value={submitted.consent.capture_method} />
          <DlRow term="Status" value={submitted.referral.status} />
          <DlRow
            term="Scopes"
            value={`${submitted.consent.scopes.length} active`}
          />
        </dl>
        <button
          onClick={() => {
            setSubmitted(null);
            setStep("consent");
          }}
          className="mt-5 rounded-full border border-border bg-card px-4 py-2 text-sm hover:bg-secondary"
        >
          Start a new referral
        </button>
      </section>
    );
  }

  // Step: profile
  return (
    <section className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-soft)]">
      <header className="mb-4 space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Track B · 90-second profile
        </p>
        <h2 className="text-xl font-medium">Lightweight social profile</h2>
        <p className="text-sm text-muted-foreground">
          No diagnoses. No medication. No clinical notes.
        </p>
      </header>

      <div className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="First name">
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={first_name}
              onChange={(e) => setFirstName(e.target.value)}
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>
          <Field label="Neighborhood">
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={neighborhood}
              onChange={(e) => setNeighborhood(e.target.value)}
            />
          </Field>
          <Field label="Social comfort">
            <select
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={comfort}
              onChange={(e) => setComfort(e.target.value)}
            >
              <option value="very_gentle">Very gentle</option>
              <option value="small_group_low_pressure">
                Calm · small group
              </option>
              <option value="open_to_trying">Open to trying</option>
              <option value="more_social">More social</option>
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Group size · min">
            <input
              type="number"
              min={1}
              max={20}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={groupMin}
              onChange={(e) => setGroupMin(Number(e.target.value))}
            />
          </Field>
          <Field label="Group size · max">
            <input
              type="number"
              min={1}
              max={20}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              value={groupMax}
              onChange={(e) => setGroupMax(Number(e.target.value))}
            />
          </Field>
        </div>

        <PillGroup
          label="Interests"
          options={INTERESTS}
          selected={interests}
          onToggle={(v) => toggle(interests, v, setInterests)}
        />
        <PillGroup
          label="Things to avoid"
          options={AVOIDANCES}
          selected={avoidances}
          onToggle={(v) => toggle(avoidances, v, setAvoidances)}
        />
        <PillGroup
          label="Accessibility needs"
          options={ACCESSIBILITY}
          selected={accessibility}
          onToggle={(v) => toggle(accessibility, v, setAccessibility)}
        />

        <Field label="Referral reason (not clinical)">
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={referralReason}
            onChange={(e) => setReferralReason(e.target.value)}
          />
        </Field>

        {error && (
          <p className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            onClick={() => setStep("consent")}
            className="rounded-full border border-border bg-card px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
          >
            Back
          </button>
          <button
            onClick={submit}
            className="inline-flex items-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-5 py-2.5 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
          >
            <ShieldCheck size={14} strokeWidth={1.8} />
            Submit referral to welzijnscoach
          </button>
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function PillGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: string[];
  selected: string[];
  onToggle: (v: string) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = selected.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onToggle(opt)}
              className={
                "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                (active
                  ? "bg-[color-mix(in_oklab,var(--mist)_35%,white)] text-foreground"
                  : "border border-border bg-background text-muted-foreground hover:text-foreground")
              }
            >
              {active && <Check size={12} strokeWidth={2} />} {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ConsentScreen({
  onAccept,
  captureMethod,
  onCaptureMethod,
}: {
  onAccept: () => void;
  captureMethod: "in_consult" | "self_completion";
  onCaptureMethod: (m: "in_consult" | "self_completion") => void;
}) {
  return (
    <section className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-soft)]">
      <div className="mx-auto max-w-md space-y-4">
        <header>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            CivicCircles · Toestemming
          </p>
          <h2 className="mt-1 text-[22px] font-medium leading-tight">
            Toestemming
            <br />
            om door te verwijzen
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Je huisarts wil je doorverwijzen naar CivicCircles. We helpen je
            rustig een kleine activiteit in de buurt te vinden.
          </p>
        </header>

        <div className="rounded-2xl border border-border bg-card p-4 text-sm">
          <p className="font-medium">Wat we delen</p>
          <ul className="mt-2 space-y-1.5 text-muted-foreground">
            <li>✓ je interesses en beschikbaarheid</li>
            <li>✓ je buurt en reisafstand</li>
            <li>✓ je voorkeuren voor groep en tempo</li>
          </ul>
        </div>

        <div className="rounded-2xl bg-[color-mix(in_oklab,var(--peach)_30%,white)] p-4 text-sm">
          Geen diagnoses. Geen medicatie. Geen dossier.
        </div>

        <fieldset className="rounded-2xl border border-border bg-secondary/50 p-3 text-xs">
          <legend className="px-1 text-muted-foreground">Capture method</legend>
          <div className="mt-1 flex flex-wrap gap-2">
            <CaptureChoice
              value="in_consult"
              current={captureMethod}
              onSelect={onCaptureMethod}
              label="In consult"
            />
            <CaptureChoice
              value="self_completion"
              current={captureMethod}
              onSelect={onCaptureMethod}
              label="Self-completion link"
            />
          </div>
        </fieldset>

        <button
          onClick={onAccept}
          className="w-full rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
        >
          Ja, ik geef toestemming
        </button>
        <button
          onClick={onAccept}
          className="w-full rounded-full px-4 py-2 text-sm text-muted-foreground hover:text-foreground"
        >
          Liever niet · geen probleem
        </button>

        <p className="pt-2 text-xs text-muted-foreground">
          You can withdraw your consent at any time. Functionaris
          Gegevensbescherming contact in the practice's privacy policy. AVG art.
          6(1)(a) and 9(2)(a).
        </p>
      </div>
    </section>
  );
}

function CaptureChoice({
  value,
  current,
  onSelect,
  label,
}: {
  value: "in_consult" | "self_completion";
  current: string;
  onSelect: (v: "in_consult" | "self_completion") => void;
  label: string;
}) {
  const active = value === current;
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      className={
        "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
        (active
          ? "bg-[color-mix(in_oklab,var(--sage)_40%,white)] text-foreground"
          : "border border-border bg-card text-muted-foreground")
      }
    >
      {label}
    </button>
  );
}

function DlRow({ term, value }: { term: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-secondary/40 px-3 py-2">
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">
        {term}
      </dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
