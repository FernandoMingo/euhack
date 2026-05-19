"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Leaf, LogIn, Mail } from "lucide-react";
import { ApiError, api, writeDemoSession } from "@/lib/api";

export default function ResidentLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const resident = await api.loginResident(email.trim());
      writeDemoSession({
        resident_id: resident.id,
        resident_first_name: resident.first_name,
      });
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 404
            ? "We couldn't find a CivicCircles account for that email. Ask your huisarts to refer you first."
            : err.message
        );
      } else {
        setError(String(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] max-w-md flex-col justify-center px-4 py-8 sm:px-6">
      <section className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-soft)]">
        <div className="mb-6 flex items-center gap-2 text-sm font-medium">
          <span
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border bg-[color-mix(in_oklab,var(--sage)_30%,white)]"
            aria-hidden
          >
            <Leaf size={16} strokeWidth={1.8} />
          </span>
          CivicCircles
        </div>

        <header className="space-y-1.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Resident sign-in
          </p>
          <h1 className="text-[24px] font-medium leading-tight">
            Welcome back.
          </h1>
          <p className="text-sm text-muted-foreground">
            Use the email your huisarts entered when they referred you. We'll
            send your invitations there and you'll find them in this inbox.
          </p>
        </header>

        <form className="mt-5 space-y-4" onSubmit={submit}>
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Email
            </span>
            <div className="relative">
              <Mail
                size={14}
                strokeWidth={1.8}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <input
                type="email"
                required
                autoFocus
                inputMode="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="sofia@example.nl"
                className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </label>

          {error && (
            <p className="rounded-2xl bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-5 py-3 text-sm font-medium hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)] disabled:opacity-60"
          >
            <LogIn size={14} strokeWidth={1.8} />
            {busy ? "Signing in…" : "Sign in"}
          </button>

          <p className="pt-2 text-xs text-muted-foreground">
            No password. This prototype uses email-based recognition; production
            adds DigiD or a magic-link. Your data is scoped to your account
            only.
          </p>
        </form>
      </section>
    </div>
  );
}
