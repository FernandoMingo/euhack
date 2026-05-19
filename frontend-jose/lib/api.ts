/**
 * Typed client for the CivicCircles backend that lives in `backend/app/api/`.
 * Endpoints mirror what we built in app/api/routers/*.py.
 *
 * The mapbox token + base URL come from .env.local.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(rest.headers ?? {}),
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    cache: "no-store",
    ...rest,
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ---------- Types (kept loose; mirror schemas.py) ----------

export type VerificationStatus = "pending" | "approved" | "rejected";

export interface Professional {
  id: string;
  full_name: string;
  role: string;
  organization: string | null;
  city: string | null;
  email: string;
  verification_status: VerificationStatus;
  agb_code: string | null;
  big_number: string | null;
  qualification: string | null;
  onderneming_agb_code: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProfessionalSignupRequest {
  full_name: string;
  role: string;
  email: string;
  agb_code: string;
  big_number?: string | null;
  kvk_number?: string | null;
  organization?: string | null;
  city?: string | null;
  qualification_hint?: string | null;
}

export interface ProfessionalSignupResponse {
  professional: Professional;
  verification: {
    id: string;
    professional_id: string;
    outcome: "passed" | "failed";
    failure_reason: string | null;
    created_at: string;
  };
}

export interface Resident {
  id: string;
  first_name: string;
  email: string;
  preferred_language: string;
  city: string;
  neighborhood: string | null;
  location_radius_km: number;
  social_comfort: string;
  preferred_group_size_min: number;
  preferred_group_size_max: number;
  cost_sensitivity: string;
  status: "active" | "paused" | "withdrawn";
  created_at: string;
  updated_at: string;
}

export type ConsentScope =
  | "create_social_profile"
  | "use_profile_for_activity_matching"
  | "send_activity_invitations"
  | "share_limited_status_with_professional"
  | "internal_peer_ratings";

export interface ConsentRecord {
  id: string;
  resident_id: string;
  professional_id: string;
  status: "active" | "revoked";
  granted_at: string;
  consent_text_version: string;
  consent_locale: string;
  capture_method: "in_consult" | "self_completion";
  scopes: ConsentScope[];
}

export interface Referral {
  id: string;
  resident_id: string;
  professional_id: string;
  referral_reason: string | null;
  status: "submitted" | "accepted" | "closed";
  created_at: string;
}

export interface AvailabilityWindow {
  weekday: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
  start_time_local: string;
  end_time_local: string;
}

export interface ResidentProfilePayload {
  first_name: string;
  email: string;
  preferred_language: string;
  city: string;
  social_comfort: string;
  preferred_group_size_min: number;
  preferred_group_size_max: number;
  cost_sensitivity: string;
  neighborhood?: string | null;
  location_radius_km?: number;
  interests?: string[];
  activities?: string[];
  accessibility_needs?: string[];
  availability?: AvailabilityWindow[];
  avoidances?: string[];
}

export interface ReferralCreateResponse {
  resident: Resident;
  consent: ConsentRecord;
  referral: Referral;
}

export interface ActivityTemplate {
  id: string;
  code: string;
  title: string;
  description: string;
  family: string;
  typical_duration_minutes: number;
  typical_group_size_min: number;
  typical_group_size_max: number;
  typical_cost_band: "free" | "low" | "medium" | "high";
  social_energy: "low" | "medium" | "high";
  setting: "indoor" | "outdoor" | "mixed";
  intensity: "still" | "light" | "active" | "vigorous";
  noise_level: "quiet" | "moderate" | "loud";
  structure: "guided" | "self_paced" | "mixed";
  risk_level: "low" | "medium" | "high";
  tags: string[];
}

export interface Activity {
  id: string;
  title: string;
  activity_type: string;
  venue_id: string;
  host_id: string | null;
  start_at: string;
  end_at: string;
  capacity: number;
  cost_cents: number;
  risk_level: "low" | "medium" | "high";
  approval_status: "draft" | "proposed" | "approved" | "rejected";
}

export interface Venue {
  id: string;
  name: string;
  address: string;
  city: string;
  lat: number | null;
  lng: number | null;
}

// ---------- API surface ----------

export const api = {
  // Health
  health: () => request<{ status: string }>("/healthz"),

  // Professionals
  signupProfessional: (body: ProfessionalSignupRequest) =>
    request<ProfessionalSignupResponse>("/api/professionals/signup", {
      method: "POST",
      json: body,
    }),
  listProfessionals: (status?: VerificationStatus) =>
    request<Professional[]>(
      "/api/professionals" + (status ? `?verification_status=${status}` : "")
    ),
  getProfessional: (id: string) =>
    request<Professional>(`/api/professionals/${id}`),
  listReferralsForProfessional: (id: string) =>
    request<Referral[]>(`/api/professionals/${id}/referrals`),

  // Referrals
  createReferral: (body: {
    professional_id: string;
    profile: ResidentProfilePayload;
    consent_scopes?: ConsentScope[];
    consent_text_version?: string;
    consent_locale?: string;
    capture_method?: "in_consult" | "self_completion";
    referral_reason?: string | null;
  }) =>
    request<ReferralCreateResponse>("/api/referrals", {
      method: "POST",
      json: body,
    }),
  updateReferralStatus: (
    id: string,
    status: "submitted" | "accepted" | "closed"
  ) =>
    request<Referral>(`/api/referrals/${id}/status`, {
      method: "PATCH",
      json: { status },
    }),

  // Residents
  listResidents: (status?: "active" | "paused" | "withdrawn") =>
    request<Resident[]>(
      "/api/residents" + (status ? `?status=${status}` : "")
    ),
  getResident: (id: string) => request<Resident>(`/api/residents/${id}`),
  listResidentConsents: (id: string) =>
    request<ConsentRecord[]>(`/api/residents/${id}/consents`),
  loginResident: (email: string) =>
    request<Resident>("/api/residents/login", {
      method: "POST",
      json: { email },
    }),

  // Templates
  listTemplates: (family?: string) =>
    request<ActivityTemplate[]>(
      "/api/templates" + (family ? `?family=${family}` : "")
    ),
  listTemplateFamilies: () => request<string[]>("/api/templates/families"),
  getTemplate: (code: string) =>
    request<ActivityTemplate>(`/api/templates/${code}`),

  // Activities
  createVenue: (body: {
    name: string;
    address: string;
    city: string;
    lat?: number;
    lng?: number;
  }) =>
    request<Venue>("/api/venues", { method: "POST", json: body }),
  createActivity: (body: {
    title: string;
    activity_type: string;
    venue_id: string;
    start_at: string;
    end_at: string;
    capacity: number;
    risk_level: "low" | "medium" | "high";
    approval_status: "draft" | "proposed" | "approved" | "rejected";
    host_id?: string;
    cost_cents?: number;
  }) =>
    request<Activity>("/api/activities", { method: "POST", json: body }),
  getActivity: (id: string) =>
    request<Activity>(`/api/activities/${id}`),

  // Invitations
  createInvitation: (body: {
    circle_id: string;
    activity_id: string;
    resident_id: string;
    status?: "sent" | "accepted" | "declined" | "expired";
  }) =>
    request<{ id: string; status: string; companion_pass_used: boolean }>(
      "/api/invitations",
      { method: "POST", json: body }
    ),
  acceptInvitation: (
    id: string,
    opts?: { companion_pass_used?: boolean; resident_id?: string }
  ) =>
    request<{ id: string; status: string; companion_pass_used: boolean }>(
      `/api/invitations/${id}/accept`,
      {
        method: "POST",
        json: {
          companion_pass_used: opts?.companion_pass_used ?? false,
          resident_id: opts?.resident_id,
        },
      }
    ),
  declineInvitation: (id: string, opts?: { resident_id?: string }) =>
    request<{ id: string; status: string }>(
      `/api/invitations/${id}/decline`,
      {
        method: "POST",
        json: { resident_id: opts?.resident_id },
      }
    ),

  // Consents
  getConsent: (id: string) => request<ConsentRecord>(`/api/consents/${id}`),
  revokeConsent: (id: string) =>
    request<ConsentRecord>(`/api/consents/${id}/revoke`, { method: "POST" }),

  // Operator
  createMatchingRun: (body: {
    run_type: "activity_ranking" | "circle_matching" | "re_recommendation";
    model_version: string;
    score_algorithm: string;
  }) =>
    request<{ id: string }>("/api/operator/matching-runs", {
      method: "POST",
      json: body,
    }),
  listMatchingCandidates: (runId: string, limit = 10) =>
    request<
      Array<{
        id: string;
        rank_position: number;
        total_score: number;
        hard_constraints_passed: boolean;
        resident_id: string | null;
        activity_id: string | null;
        circle_id: string | null;
      }>
    >(`/api/operator/matching-runs/${runId}/candidates?limit=${limit}`),

  // Demo orchestration (see backend/app/api/routers/demo.py)
  operatorInbox: () => request<OperatorInbox>("/api/demo/operator/inbox"),
  orchestrateReferral: (referralId: string, body?: { operator_id?: string; preferred_template_code?: string | null }) =>
    request<Proposal>(`/api/demo/operator/referrals/${referralId}/orchestrate`, {
      method: "POST",
      json: body ?? {},
    }),
  approveProposal: (circleId: string, body?: { operator_id?: string; reason?: string | null }) =>
    request<DemoInvitation[]>(`/api/demo/operator/circles/${circleId}/approve`, {
      method: "POST",
      json: body ?? {},
    }),
  rejectProposal: (circleId: string, body?: { operator_id?: string; reason?: string | null }) =>
    request<Proposal>(`/api/demo/operator/circles/${circleId}/reject`, {
      method: "POST",
      json: body ?? {},
    }),
  residentInbox: (residentId: string) =>
    request<ResidentInbox>(
      `/api/demo/residents/${residentId}/invitations`
    ),
  createNearbyActivities: (
    residentId: string,
    body: { lat: number; lng: number; count?: number }
  ) =>
    request<ResidentInbox>(
      `/api/demo/residents/${residentId}/nearby-activities`,
      { method: "POST", json: body }
    ),
  residentInboxItems: (residentId: string) =>
    request<ResidentInboxItem[]>(
      `/api/demo/residents/${residentId}/inbox`
    ),
  markInboxItemRead: (residentId: string, itemId: string) =>
    request<ResidentInboxItem>(
      `/api/residents/${residentId}/inbox/${itemId}/read`,
      { method: "POST" }
    ),
  archiveInboxItem: (residentId: string, itemId: string) =>
    request<ResidentInboxItem>(
      `/api/residents/${residentId}/inbox/${itemId}/archive`,
      { method: "POST" }
    ),
  checkIn: (activityId: string, residentId: string) =>
    request<{ checked_in: boolean; activity_id: string; resident_id: string }>(
      `/api/demo/activities/${activityId}/check-in`,
      { method: "POST", json: { resident_id: residentId } }
    ),
  circleReveal: (activityId: string, residentId: string) =>
    request<CircleReveal>(
      `/api/demo/activities/${activityId}/circle-reveal?resident_id=${encodeURIComponent(residentId)}`
    ),
  submitReflection: (
    activityId: string,
    body: {
      resident_id: string;
      felt_after?: "worse" | "same" | "better" | null;
      would_repeat?: boolean | null;
      notes?: string | null;
    }
  ) =>
    request<{ saved: boolean; feedback_id: string }>(
      `/api/demo/activities/${activityId}/reflection`,
      { method: "POST", json: body }
    ),
  professionalDashboard: (professionalId: string) =>
    request<ProfessionalDashboard>(
      `/api/demo/professionals/${professionalId}/dashboard`
    ),
};

// ---------- Demo response shapes (match backend/app/api/routers/demo.py) ----------

export interface DemoVenue {
  id: string;
  name: string;
  address: string;
  city: string;
  lat: number | null;
  lng: number | null;
}

export interface DemoHost {
  id: string;
  full_name: string;
  host_type: string;
}

export interface DemoActivity {
  id: string;
  title: string;
  activity_type: string;
  start_at: string;
  end_at: string;
  capacity: number;
  cost_cents: number;
  risk_level: string;
  approval_status: string;
  venue: DemoVenue;
  host: DemoHost | null;
}

export interface ResidentSummary {
  id: string;
  first_name: string;
  neighborhood: string | null;
  social_comfort: string;
  preferred_group_size_min: number;
  preferred_group_size_max: number;
}

export interface ProfessionalSummary {
  id: string;
  full_name: string;
  role: string;
  organization: string | null;
  city: string | null;
  verification_status: string;
}

export interface PendingReferral {
  referral_id: string;
  referral_reason: string | null;
  created_at: string;
  resident: ResidentSummary;
  professional: ProfessionalSummary;
  consent_text_version: string;
}

export interface Proposal {
  circle_id: string;
  activity: DemoActivity;
  template_code: string;
  template_title: string;
  fit_score: number | null;
  shared_interests: string[];
  shared_availability: string[];
  members: ResidentSummary[];
  summary_text: string;
  consent_text_version: string;
}

export interface OperatorInbox {
  pending_referrals: PendingReferral[];
  proposals: Proposal[];
  consent_text_version: string;
}

export interface DemoInvitation {
  id: string;
  status: "sent" | "accepted" | "declined" | "expired";
  activity_id: string;
  circle_id: string;
  activity: DemoActivity;
  template_code: string | null;
  fit_score: number | null;
  members: ResidentSummary[];
}

export interface ResidentInbox {
  resident: ResidentSummary;
  invitations: DemoInvitation[];
}

export type InboxItemStatus = "unread" | "read" | "archived";

export interface ResidentInboxItem {
  id: string;
  resident_id: string;
  invitation_id: string | null;
  activity_id: string | null;
  circle_id: string | null;
  item_type: "activity_invitation";
  title: string;
  body: string;
  status: InboxItemStatus;
  metadata: {
    activity_title?: string;
    activity_start_at?: string;
    activity_end_at?: string;
    venue_name?: string;
    venue_address?: string;
    venue_city?: string;
    [key: string]: unknown;
  };
  created_at: string;
  updated_at: string;
  read_at: string | null;
  archived_at: string | null;
}

export interface RevealAttendee {
  first_name: string;
  common_ground: string[];
  conversation_starter: string;
}

export interface CircleReveal {
  activity_id: string;
  locked: boolean;
  attendees: RevealAttendee[];
}

export interface ProfessionalDashboard {
  professional: ProfessionalSummary;
  referrals: PendingReferral[];
}

// ---------- Demo session (localStorage) ----------

const STORAGE_KEY = "cc.demo.session.v1";

export interface DemoSession {
  professional_id?: string;
  professional_name?: string;
  resident_id?: string;
  resident_first_name?: string;
  referral_id?: string;
  circle_id?: string;
  activity_id?: string;
  invitation_id?: string;
}

export function readDemoSession(): DemoSession {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as DemoSession) : {};
  } catch {
    return {};
  }
}

export function writeDemoSession(patch: Partial<DemoSession>): DemoSession {
  if (typeof window === "undefined") return patch as DemoSession;
  const next = { ...readDemoSession(), ...patch };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  return next;
}

export function resetDemoSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

// ---------- Mapbox helper ----------

export const MAPBOX_TOKEN =
  process.env.NEXT_PUBLIC_MAPBOX_TOKEN ??
  "pk.eyJ1IjoiamtvbmtsZXdza2kiLCJhIjoiY21wNjloYTN3MG5lbTJ3c2E5MXU4YXkycSJ9.-vyo9RLZNXPEyebVGBi_vg";
