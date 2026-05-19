export type Resident = {
  id: string;
  first_name: string;
  email: string;
  preferred_language: string;
  approx_location: string;
  location_radius_km: number;
  interests: string[];
  activity_preferences: string[];
  availability: string[];
  social_comfort: string;
  preferred_group_size: { min: number; max: number };
  accessibility_needs: string[];
  cost_sensitivity: string;
  avoid: string[];
  companion_pass_allowed: boolean;
  status: string;
  consent_scopes: string[];
  preference_note?: string;
};

export type Activity = {
  id: string;
  title: string;
  activity_type: string;
  date_time_label: string;
  availability_label: string;
  location: { name: string; address: string; lat: number; lng: number };
  group_size: number;
  pace: string;
  intensity: string;
  host: string;
  cost: string;
  cost_amount: number;
  accessibility: string[];
  alcohol_free: boolean;
  tags: string[];
  status: string;
  why_fit: string;
};

export type Invitation = {
  id: string;
  resident_id: string;
  activity_id: string;
  status: "sent" | "accepted" | "declined";
  companion_pass_available: boolean;
  activity: Activity;
};

export type RevealAttendee = {
  first_name: string;
  short_bio: string;
  conversation_starter: string;
};

export type Reveal = {
  activity_id: string;
  locked: boolean;
  attendees: RevealAttendee[];
};

export type Referral = {
  resident: Resident;
  created_by: {
    id: string;
    name: string;
    role: string;
    organization: string;
    city: string;
    verification_status: string;
    email: string;
  };
};

export type Proposal = {
  id: string;
  activity_id: string;
  title: string;
  status: string;
  generated_summary: string;
  human_approval_status: string;
  ranking_score: number;
  alternative_notes: Record<string, string>;
  activity: Activity;
};

export type MatchingGraph = {
  circle_id: string;
  activity_id: string;
  compatibility_signals: string[];
  nodes: { id: string; label: string; kind: "resident" | "activity" }[];
  edges: { from: string; to: string; signals: string[] }[];
  privacy_note: string;
};

export type Audit = {
  activity_id: string;
  activity_title: string;
  items: { id: string; label: string; status: string; detail: string }[];
};

export type Ranking = {
  ranked_activities: {
    activity_id: string;
    title: string;
    score: number;
    component_scores: Record<string, number>;
    hard_constraints_passed: string[];
    hard_constraints_failed: string[];
    reasons_ranked_lower: string[];
  }[];
  weights: Record<string, number>;
};

export type Explanation = {
  recommended_group: string[];
  recommended_activity: string;
  top_positive_signals: string[];
  hard_constraints_passed: string[];
  alternative_activities_considered: { activity_id: string; title: string; score: number }[];
  reasons_alternatives_ranked_lower: { activity_id: string; reasons: string[] }[];
  human_approval_status: string;
  component_scores: Record<string, number>;
  weights: Record<string, number>;
  guardrail: string;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  me: () => request<Resident>("/api/resident/me"),
  invitations: () => request<Invitation[]>("/api/resident/invitations"),
  accept: (id: string) => request<Invitation>(`/api/invitations/${id}/accept`, { method: "POST" }),
  decline: (id: string) => request<Invitation>(`/api/invitations/${id}/decline`, { method: "POST" }),
  checkIn: (activityId: string) => request<{ checked_in: boolean }>(`/api/activities/${activityId}/check-in`, { method: "POST" }),
  reveal: (activityId: string) => request<Reveal>(`/api/activities/${activityId}/circle-reveal`),
  feedback: (activityId: string, body: { felt_after: string; would_do_similar_again: string; preference_adjustment?: string }) =>
    request(`/api/activities/${activityId}/feedback`, { method: "POST", body: JSON.stringify(body) }),
  referrals: () => request<Referral[]>("/api/professionals/referrals"),
  patchPreferences: (residentId: string, preferences: Partial<Resident>) =>
    request<{ resident: Resident; applied: Record<string, unknown> }>(`/api/residents/${residentId}/preferences`, {
      method: "PATCH",
      body: JSON.stringify({ preferences })
    }),
  proposals: () => request<Proposal[]>("/api/operator/proposals"),
  proposal: (id: string) => request<Proposal>(`/api/operator/proposals/${id}`),
  approve: (id: string) => request<Proposal>(`/api/operator/proposals/${id}/approve`, { method: "POST" }),
  reject: (id: string) => request<Proposal>(`/api/operator/proposals/${id}/reject`, { method: "POST" }),
  graph: (circleId = "circle_photo_walk") => request<MatchingGraph>(`/api/operator/matching-graph/${circleId}`),
  audit: (activityId: string) => request<Audit>(`/api/operator/audit/${activityId}`),
  rankActivities: () => request<Ranking>("/api/ai/rank-activities", { method: "POST", body: JSON.stringify({ circle_id: "circle_photo_walk" }) }),
  explainMatch: (activityId: string) =>
    request<Explanation>("/api/ai/explain-match", { method: "POST", body: JSON.stringify({ activity_id: activityId }) })
};
