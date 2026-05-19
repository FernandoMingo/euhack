"use client";

import { useState } from "react";
import { ApiError, api, type Professional } from "@/lib/api";

interface Props {
  onApproved: (p: Professional) => void;
}

export function ProfessionalSignup({ onApproved }: Props) {
  const [full_name, setFullName] = useState("Dr. Anna Vermeer");
  const [role, setRole] = useState("huisarts");
  const [email, setEmail] = useState("anna@oudwest-praktijk.nl");
  const [agb_code, setAgbCode] = useState("01024587");
  const [big_number, setBigNumber] = useState("12345678");
  const [organization, setOrganization] = useState(
    "Huisartsenpraktijk Oud-West"
  );
  const [city, setCity] = useState("Amsterdam");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const bigRequired = ["huisarts", "psycholoog", "psychotherapeut"].includes(
    role
  );

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.signupProfessional({
        full_name,
        role,
        email,
        agb_code,
        big_number: bigRequired ? big_number : null,
        organization,
        city,
        qualification_hint: role,
      });
      onApproved(res.professional);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Field label="Full name">
        <input
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          value={full_name}
          onChange={(e) => setFullName(e.target.value)}
          required
        />
      </Field>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Role">
          <select
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          >
            <option value="huisarts">Huisarts</option>
            <option value="poh-ggz">POH-GGZ</option>
            <option value="psycholoog">Psycholoog</option>
            <option value="psychotherapeut">Psychotherapeut</option>
            <option value="welzijnscoach">Welzijnscoach</option>
            <option value="doktersassistent">Doktersassistent</option>
          </select>
        </Field>
        <Field label="City">
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          />
        </Field>
      </div>
      <Field label="Email">
        <input
          type="email"
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </Field>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Personal AGB code (8 digits)">
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono"
            value={agb_code}
            onChange={(e) => setAgbCode(e.target.value)}
            maxLength={8}
            minLength={8}
            required
          />
        </Field>
        <Field
          label={`BIG number${bigRequired ? " (required)" : " (optional)"}`}
        >
          <input
            className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm font-mono"
            value={big_number}
            onChange={(e) => setBigNumber(e.target.value)}
            disabled={!bigRequired}
            required={bigRequired}
          />
        </Field>
      </div>
      <Field label="Organization">
        <input
          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
          value={organization}
          onChange={(e) => setOrganization(e.target.value)}
        />
      </Field>
      {error && (
        <p className="rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={submitting}
        className="inline-flex w-full items-center justify-center rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium transition-colors hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-60"
      >
        {submitting ? "Verifying with Vektis & CIBG…" : "Verify and activate seat"}
      </button>
    </form>
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
