"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Save } from "lucide-react";
import { Referral, Resident, api } from "@/lib/api";

export function ProfessionalDashboard() {
  const [referrals, setReferrals] = useState<Referral[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.referrals().then(setReferrals).catch((err) => setError(err instanceof Error ? err.message : "Unable to load referrals"));
  }, []);

  const sofia = referrals.find((item) => item.resident.id === "resident_sofia") ?? referrals[0];
  const resident = sofia?.resident;

  useEffect(() => {
    if (!resident) return;
    setDraft({
      interests: resident.interests.join(", "),
      activity_preferences: resident.activity_preferences.join(", "),
      availability: resident.availability.join(", "),
      accessibility_needs: resident.accessibility_needs.join(", "),
      avoid: resident.avoid.join(", "),
      location_radius_km: String(resident.location_radius_km),
      social_comfort: resident.social_comfort,
      cost_sensitivity: resident.cost_sensitivity,
      preference_note: resident.preference_note ?? ""
    });
  }, [resident]);

  const fields = useMemo(() => (resident ? profileRows(resident) : []), [resident]);

  async function save() {
    if (!resident) return;
    setError(null);
    setSaved(false);
    const preferences: Partial<Resident> = {
      interests: split(draft.interests),
      activity_preferences: split(draft.activity_preferences),
      availability: split(draft.availability),
      accessibility_needs: split(draft.accessibility_needs),
      avoid: split(draft.avoid),
      location_radius_km: Number(draft.location_radius_km) || resident.location_radius_km,
      social_comfort: draft.social_comfort,
      cost_sensitivity: draft.cost_sensitivity,
      preference_note: draft.preference_note
    };
    try {
      const updated = await api.patchPreferences(resident.id, preferences);
      setReferrals((items) =>
        items.map((item) => (item.resident.id === resident.id ? { ...item, resident: updated.resident } : item))
      );
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save preferences");
    }
  }

  if (!resident) {
    return <div className="mx-auto max-w-5xl px-4 py-8 text-sm text-ink/65">Loading profile...</div>;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
      <div className="mb-6">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-moss">Professional dashboard</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Sofia’s lightweight profile</h1>
        <p className="mt-2 text-sm text-ink/65">
          Created by {sofia.created_by.name}, {sofia.created_by.role} · {sofia.created_by.organization}
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_420px]">
        <section className="rounded-lg border border-line/20 bg-paper/88 p-5 shadow-soft">
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map(([label, value]) => (
              <div key={label} className="rounded-lg border border-line/15 bg-white/35 p-4">
                <p className="text-xs text-ink/52">{label}</p>
                <p className="mt-1 text-sm font-medium leading-6 text-ink">{value}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-line/20 bg-paper/88 p-5 shadow-soft">
          <h2 className="text-lg font-semibold text-ink">Edit preferences</h2>
          <div className="mt-4 space-y-4">
            <Input label="Location radius km" value={draft.location_radius_km} onChange={(value) => setDraft({ ...draft, location_radius_km: value })} />
            <Input label="Interests" value={draft.interests} onChange={(value) => setDraft({ ...draft, interests: value })} />
            <Input label="Activity preferences" value={draft.activity_preferences} onChange={(value) => setDraft({ ...draft, activity_preferences: value })} />
            <Input label="Availability" value={draft.availability} onChange={(value) => setDraft({ ...draft, availability: value })} />
            <Input label="Accessibility needs" value={draft.accessibility_needs} onChange={(value) => setDraft({ ...draft, accessibility_needs: value })} />
            <Input label="Avoid list" value={draft.avoid} onChange={(value) => setDraft({ ...draft, avoid: value })} />
            <Input label="Social comfort" value={draft.social_comfort} onChange={(value) => setDraft({ ...draft, social_comfort: value })} />
            <Input label="Cost sensitivity" value={draft.cost_sensitivity} onChange={(value) => setDraft({ ...draft, cost_sensitivity: value })} />
            <Input label="Preference note" value={draft.preference_note} onChange={(value) => setDraft({ ...draft, preference_note: value })} />
          </div>
          {error ? <p className="mt-4 text-sm text-clay">{error}</p> : null}
          {saved ? (
            <p className="mt-4 inline-flex items-center gap-2 text-sm text-moss">
              <Check size={16} />
              Saved
            </p>
          ) : null}
          <button className="tap-target mt-5 inline-flex items-center gap-2 rounded-lg bg-moss px-4 text-sm font-semibold text-white" onClick={save}>
            <Save size={16} />
            Save
          </button>
        </section>
      </div>
    </div>
  );
}

function profileRows(resident: Resident): [string, string][] {
  return [
    ["First name", resident.first_name],
    ["Preferred language", resident.preferred_language],
    ["Approximate location", resident.approx_location],
    ["Location radius", `${resident.location_radius_km} km`],
    ["Interests", resident.interests.join(", ")],
    ["Activity preferences", resident.activity_preferences.join(", ")],
    ["Availability", resident.availability.join(", ")],
    ["Social comfort", resident.social_comfort],
    ["Preferred group size", `${resident.preferred_group_size.min}-${resident.preferred_group_size.max}`],
    ["Accessibility needs", resident.accessibility_needs.join(", ")],
    ["Cost sensitivity", resident.cost_sensitivity],
    ["Avoid list", resident.avoid.join(", ")],
    ["Consent scopes", resident.consent_scopes.join(", ")]
  ];
}

function split(value = "") {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function Input({ label, value, onChange }: { label: string; value?: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-ink/65">{label}</span>
      <input
        className="mt-1 h-11 w-full rounded-lg border border-line/25 bg-white/45 px-3 text-sm outline-none focus:border-moss"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
