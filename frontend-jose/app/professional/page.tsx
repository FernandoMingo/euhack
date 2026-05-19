"use client";

import { useState } from "react";
import { ProfessionalSignup } from "@/components/ProfessionalSignup";
import { ReferralFlow } from "@/components/ReferralFlow";
import { Chip } from "@/components/Chip";
import { Stethoscope, UserCheck } from "lucide-react";
import { writeDemoSession, type Professional } from "@/lib/api";

export default function ProfessionalPage() {
  const [professional, setProfessional] = useState<Professional | null>(null);

  function handleApproved(p: Professional) {
    setProfessional(p);
    writeDemoSession({
      professional_id: p.id,
      professional_name: p.full_name,
    });
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-6 space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Professional · welzijn op recept
        </p>
        <h1 className="text-[26px] font-medium leading-tight">
          Refer a resident to CivicCircles
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          The 90-second moment during a consult. Verify your practice once, then
          create a lightweight social profile together with the resident under
          explicit consent.
        </p>
      </header>

      {!professional ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="rounded-3xl border border-border bg-card p-6 shadow-[var(--shadow-soft)]">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[color-mix(in_oklab,var(--mist)_30%,white)]">
                <Stethoscope size={16} strokeWidth={1.8} />
              </span>
              Track A · sign your practice in
            </div>
            <ProfessionalSignup onApproved={handleApproved} />
          </section>

          <section className="rounded-3xl border border-border bg-secondary/50 p-6">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              What happens behind the scenes
            </p>
            <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
              <li>
                <span className="font-medium text-foreground">Vektis AGB</span> —
                your 8-digit personal AGB confirms you're an active care
                provider.
              </li>
              <li>
                <span className="font-medium text-foreground">CIBG BIG</span> —
                for huisarts / psycholoog / psychotherapeut, BIG-nummer is
                required. POH-GGZ / welzijnscoach are accepted without one.
              </li>
              <li>
                <span className="font-medium text-foreground">KvK</span> —
                onderneming AGB is derived from your personal AGB and the
                practice is added to your account.
              </li>
              <li className="pt-2 text-xs italic">
                Verification is stubbed in this prototype. Any 8-digit AGB
                starting with <code className="text-foreground">01</code>,{" "}
                <code className="text-foreground">91</code> or{" "}
                <code className="text-foreground">94</code> passes.
              </li>
            </ul>
          </section>
        </div>
      ) : (
        <div className="space-y-4">
          <section className="rounded-3xl border border-border bg-card p-5 shadow-[var(--shadow-soft)]">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{professional.full_name}</p>
                <p className="text-xs text-muted-foreground">
                  {professional.qualification ?? professional.role} · AGB{" "}
                  {professional.agb_code} ·{" "}
                  {professional.organization ?? "Practice"}
                </p>
              </div>
              <Chip
                tone="sage"
                icon={<UserCheck size={12} strokeWidth={1.8} />}
              >
                Verified
              </Chip>
            </div>
          </section>

          <ReferralFlow professional={professional} />
        </div>
      )}
    </div>
  );
}
