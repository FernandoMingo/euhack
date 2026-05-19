"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, CircleDot, ShieldCheck, Sparkles, X } from "lucide-react";
import { Audit, Explanation, LegacyProposal, MatchingGraph, Ranking, api } from "@/lib/api";

export function OperatorDashboard() {
  const [proposals, setProposals] = useState<LegacyProposal[]>([]);
  const [graph, setGraph] = useState<MatchingGraph | null>(null);
  const [audit, setAudit] = useState<Audit | null>(null);
  const [ranking, setRanking] = useState<Ranking | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const proposalRows = await api.proposals();
      const main = proposalRows[0];
      setProposals(proposalRows);
      const [graphData, auditData, rankingData, explanationData] = await Promise.all([
        api.graph(),
        api.audit(main.activity_id),
        api.rankActivities(),
        api.explainMatch(main.activity_id)
      ]);
      setGraph(graphData);
      setAudit(auditData);
      setRanking(rankingData);
      setExplanation(explanationData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load operator dashboard");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const proposal = proposals[0];

  async function decide(action: "approve" | "reject") {
    if (!proposal) return;
    try {
      const updated = action === "approve" ? await api.approve(proposal.id) : await api.reject(proposal.id);
      setProposals((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setExplanation(await api.explainMatch(updated.activity_id));
      setAudit(await api.audit(updated.activity_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Decision failed");
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6 text-foreground sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <header className="mb-6 flex flex-col gap-4 rounded-3xl border border-border bg-card/95 p-5 shadow-float sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Operator console</p>
            <h1 className="mt-1 text-[28px] font-medium leading-tight text-foreground">Activity approval</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Anonymous matching, transparent ranking, and safety checks. Resident app stays separate at `/`.
            </p>
          </div>
          <span className="inline-flex w-fit items-center gap-2 rounded-full bg-secondary px-3 py-2 text-xs font-medium text-muted-foreground">
            <ShieldCheck className="h-4 w-4" strokeWidth={1.6} />
            Human approval required
          </span>
        </header>

        {error ? <p className="mb-4 rounded-2xl border border-border bg-card px-4 py-3 text-sm text-muted-foreground shadow-soft">{error}</p> : null}

        <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <Chip tone="sage">AI-generated proposal</Chip>
            <h2 className="mt-3 text-[22px] font-medium leading-tight text-foreground">{proposal?.title ?? "Calm Photography Walk"}</h2>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">{proposal?.generated_summary}</p>
            <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
              <Fact label="Status" value={proposal?.human_approval_status ?? "pending"} />
              <Fact label="Score" value={String(proposal?.ranking_score ?? 94)} />
              <Fact label="Location" value={proposal?.activity.location.name ?? "Vondelpark"} />
              <Fact label="Time" value={proposal?.activity.date_time_label ?? "Saturday 10:30"} />
            </div>
            <div className="mt-5 grid grid-cols-2 gap-2">
              <button
                className="flex items-center justify-center gap-2 rounded-2xl bg-[color-mix(in_oklab,var(--sage)_55%,white)] px-4 py-3 text-sm font-medium text-foreground shadow-soft transition hover:bg-[color-mix(in_oklab,var(--sage)_65%,white)]"
                onClick={() => decide("approve")}
              >
                <Check className="h-4 w-4" strokeWidth={1.8} />
                Approve
              </button>
              <button
                className="flex items-center justify-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-sm font-medium text-muted-foreground transition hover:bg-secondary hover:text-foreground"
                onClick={() => decide("reject")}
              >
                <X className="h-4 w-4" strokeWidth={1.8} />
                Reject
              </button>
            </div>
          </section>

          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-medium text-foreground">Anonymous matching graph</h2>
                <p className="mt-1 text-sm text-muted-foreground">No public profiles, no people browsing.</p>
              </div>
              <Chip>No social ranking</Chip>
            </div>
            {graph ? <GraphView graph={graph} /> : <p className="text-sm text-muted-foreground">Loading graph...</p>}
          </section>
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <h2 className="text-base font-medium text-foreground">Activity ranking</h2>
            <RankingTable ranking={ranking} />
          </section>
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <h2 className="text-base font-medium text-foreground">Safety/privacy audit</h2>
            <AuditList audit={audit} />
          </section>
        </div>

        <section className="mt-5 rounded-3xl border border-border bg-card p-5 shadow-soft">
          <h2 className="text-base font-medium text-foreground">Match explanation</h2>
          {explanation ? <ExplanationView explanation={explanation} /> : <p className="mt-3 text-sm text-muted-foreground">Loading explanation...</p>}
        </section>
      </div>
    </main>
  );
}

function Chip({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "sage" | "mist" | "peach" }) {
  const tones: Record<string, string> = {
    default: "bg-secondary text-muted-foreground",
    sage: "bg-[color-mix(in_oklab,var(--sage)_28%,white)] text-foreground",
    mist: "bg-[color-mix(in_oklab,var(--mist)_28%,white)] text-foreground",
    peach: "bg-[color-mix(in_oklab,var(--peach)_30%,white)] text-foreground"
  };
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background/60 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

function GraphView({ graph }: { graph: MatchingGraph }) {
  const positions = useMemo(() => {
    const residentNodes = graph.nodes.filter((node) => node.kind === "resident");
    const center = { x: 50, y: 50 };
    return Object.fromEntries([
      [graph.activity_id, center],
      ...residentNodes.map((node, index) => {
        const angle = (Math.PI * 2 * index) / residentNodes.length - Math.PI / 2;
        return [node.id, { x: 50 + Math.cos(angle) * 34, y: 50 + Math.sin(angle) * 34 }];
      })
    ]);
  }, [graph]);

  return (
    <div>
      <div className="relative h-80 rounded-3xl border border-border bg-background/60">
        <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
          {graph.edges.map((edge) => {
            const from = positions[edge.from];
            const to = positions[edge.to];
            if (!from || !to) return null;
            return <line key={`${edge.from}-${edge.to}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke="#A9BFA8" strokeWidth="0.35" />;
          })}
        </svg>
        {graph.nodes.map((node) => {
          const pos = positions[node.kind === "activity" ? graph.activity_id : node.id];
          if (!pos) return null;
          return (
            <div
              key={node.id}
              className={`absolute flex h-16 w-28 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-2xl border px-3 text-center text-sm shadow-soft ${
                node.kind === "activity"
                  ? "border-border bg-[color-mix(in_oklab,var(--peach)_30%,white)] text-foreground"
                  : "border-border bg-card text-muted-foreground"
              }`}
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
            >
              {node.label}
            </div>
          );
        })}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {graph.compatibility_signals.map((signal) => (
          <div key={signal} className="flex items-center gap-2 rounded-2xl border border-border bg-background/60 px-3 py-2 text-sm text-muted-foreground">
            <CircleDot className="h-3.5 w-3.5 text-foreground" strokeWidth={1.6} />
            {signal}
          </div>
        ))}
      </div>
    </div>
  );
}

function RankingTable({ ranking }: { ranking: Ranking | null }) {
  if (!ranking) return <p className="mt-3 text-sm text-muted-foreground">Loading ranking...</p>;
  return (
    <div className="mt-4 overflow-hidden rounded-2xl border border-border">
      <table className="w-full border-collapse text-left text-sm">
        <thead className="bg-secondary text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-3 py-3 font-medium">Activity</th>
            <th className="px-3 py-3 font-medium">Score</th>
            <th className="px-3 py-3 font-medium">Lower if</th>
          </tr>
        </thead>
        <tbody>
          {ranking.ranked_activities.map((row) => (
            <tr key={row.activity_id} className="border-t border-border bg-background/40">
              <td className="px-3 py-3 font-medium text-foreground">{row.title}</td>
              <td className="px-3 py-3 text-muted-foreground">{row.score}</td>
              <td className="px-3 py-3 text-muted-foreground">{row.reasons_ranked_lower.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditList({ audit }: { audit: Audit | null }) {
  if (!audit) return <p className="mt-3 text-sm text-muted-foreground">Loading audit...</p>;
  return (
    <div className="mt-4 space-y-3">
      {audit.items.map((item) => (
        <article key={item.id} className="rounded-2xl border border-border bg-background/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-foreground">{item.label}</p>
            <Chip tone={item.status === "passed" ? "sage" : "peach"}>{item.status}</Chip>
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.detail}</p>
        </article>
      ))}
    </div>
  );
}

function ExplanationView({ explanation }: { explanation: Explanation }) {
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-3">
      <div className="rounded-2xl border border-border bg-background/60 p-4">
        <p className="text-xs text-muted-foreground">Recommended activity</p>
        <p className="mt-1 font-medium text-foreground">{explanation.recommended_activity}</p>
        <p className="mt-3 text-sm text-muted-foreground">{explanation.guardrail}</p>
      </div>
      <div className="rounded-2xl border border-border bg-background/60 p-4">
        <p className="text-xs text-muted-foreground">Recommended group</p>
        <p className="mt-1 text-sm font-medium text-foreground">{explanation.recommended_group.join(", ")}</p>
      </div>
      <div className="rounded-2xl border border-border bg-background/60 p-4">
        <p className="text-xs text-muted-foreground">Human approval status</p>
        <p className="mt-1 inline-flex items-center gap-2 font-medium text-foreground">
          <Sparkles className="h-4 w-4" strokeWidth={1.6} />
          {explanation.human_approval_status}
        </p>
      </div>
    </div>
  );
}
