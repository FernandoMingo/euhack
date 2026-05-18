"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowLeft, Check } from "lucide-react";
import { api } from "@/lib/api";

const feelings = ["calmer", "same", "more connected", "not for me"];
const repeats = ["yes", "probably", "not sure", "no"];

export function ReflectionForm() {
  const [feltAfter, setFeltAfter] = useState("calmer");
  const [repeat, setRepeat] = useState("probably");
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    try {
      await api.feedback("activity_calm_photo_walk", {
        felt_after: feltAfter,
        would_do_similar_again: repeat,
        preference_adjustment: note || undefined
      });
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save reflection");
    }
  }

  return (
    <div className="mx-auto min-h-[calc(100vh-4rem)] max-w-3xl px-4 py-8 sm:px-6">
      <Link href="/" className="mb-6 inline-flex items-center gap-2 text-sm text-ink/68 hover:text-ink">
        <ArrowLeft size={16} />
        Map
      </Link>
      <section className="rounded-lg border border-line/20 bg-paper/88 p-5 shadow-soft sm:p-7">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-moss">Post-event reflection</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">Calm Photography Walk</h1>

        <div className="mt-7 space-y-7">
          <ChoiceGroup label="How did Sofia feel afterward?" value={feltAfter} options={feelings} onChange={setFeltAfter} />
          <ChoiceGroup label="Would she do something similar again?" value={repeat} options={repeats} onChange={setRepeat} />
          <label className="block">
            <span className="text-sm font-medium text-ink">Optional preference adjustment</span>
            <textarea
              className="mt-2 min-h-28 w-full rounded-lg border border-line/25 bg-white/45 p-3 text-sm outline-none focus:border-moss"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Example: keep walks under 90 minutes"
            />
          </label>
        </div>

        {error ? <p className="mt-4 text-sm text-clay">{error}</p> : null}
        {saved ? (
          <p className="mt-5 inline-flex items-center gap-2 rounded-lg border border-moss/30 bg-sage/70 px-3 py-2 text-sm text-ink">
            <Check size={16} />
            Reflection saved
          </p>
        ) : null}

        <div className="mt-6">
          <button className="tap-target rounded-lg bg-moss px-5 text-sm font-semibold text-white hover:bg-moss/90" onClick={submit}>
            Save reflection
          </button>
        </div>
      </section>
    </div>
  );
}

function ChoiceGroup({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-ink">{label}</legend>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            className={`tap-target rounded-lg border px-4 text-left text-sm capitalize ${
              value === option ? "border-moss bg-sage/80 text-ink" : "border-line/20 bg-white/35 text-ink/72"
            }`}
            onClick={() => onChange(option)}
          >
            {option}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
