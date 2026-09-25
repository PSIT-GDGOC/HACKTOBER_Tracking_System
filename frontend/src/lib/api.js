/**
 * ---------------------------------------------------------------------------
 *  API client layer — the ONLY place that talks to the network.
 * ---------------------------------------------------------------------------
 *  Plain JavaScript (no TypeScript) per the project README.
 *  Paths and payload shapes mirror the FastAPI backend in `backendd/` exactly:
 *
 *    POST /auth/signup              { name, email, psit_roll_no }
 *    POST /auth/login               { identifier } → { access_token, user }
 *    GET  /auth/me
 *    POST /auth/verify-id           { psit_roll_no, id_card_image_base64, qr_token?, portal_snapshot? }
 *    GET  /auth/pending-verifications                    (admin)
 *    POST /auth/verify-manual/{id}  { action, reason }  (admin)
 *    GET  /auth/github/login        → { oauth_url, client_id, redirect_uri }
 *    POST /auth/github/link         { github_username, github_id? }
 *
 *    GET  /issues?repo_id&difficulty&tech_tag&category&status&search&skip&limit
 *    GET  /issues/{id}              POST /issues/{id}/claim   POST /issues/{id}/unclaim
 *    GET  /pull-requests?repo_id&user_id&github_username&status&skip&limit   /pull-requests/{id}
 *    GET  /commits?repo_id&user_id&github_username&pr_id&issue_id&skip&limit
 *    GET  /contributions?status&validation_status&skip&limit
 *    GET  /contributions/my         GET /contributions/{user_id}
 *    PATCH /contributions/{id}/validation { validation_status, note }
 *    PATCH /contributions/{id}/status?new_status=&detail=
 *    GET  /dashboard/student|maintainer|repository/{id}|admin
 *    GET  /users/me   PATCH /users/me { name?, github_username? }   GET /users/{id}
 *    GET  /leaderboard?repo_id&platform&page&per_page
 *    GET  /notifications?unread_only&limit&offset
 *    PATCH /notifications/{id}/read     POST /notifications/read-all
 *    GET  /activity?type&actor_id&target_type&limit&offset
 *    GET  /search?q&category&limit
 *    GET  /health
 * ---------------------------------------------------------------------------
 */

export const API_BASE_URL =
  (import.meta.env && import.meta.env.VITE_API_BASE_URL) || "";

export const DEMO_MODE = API_BASE_URL === "";

const TOKEN_KEY = "gdgoc_access_token";
const EXPIRY_KEY = "gdgoc_token_expiry";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t, expiresInSec) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(EXPIRY_KEY, String(Date.now() + (expiresInSec || 0) * 1000));
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRY_KEY);
  },
  expiresAt: () => Number(localStorage.getItem(EXPIRY_KEY) || 0),
  isExpired: () => {
    const at = tokenStore.expiresAt();
    return at > 0 && Date.now() > at;
  },
};

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.detail = detail || `Request failed (${status})`;
  }
}

/* ------------------------------------------------------------------ */
/*  core fetch pipeline                                                */
/* ------------------------------------------------------------------ */

async function request(path, { method = "GET", body, headers } = {}) {
  const token = tokenStore.get();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token && !tokenStore.isExpired() ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers || {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;
  const text = await res.text();
  const payload = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : Array.isArray(payload?.detail)
          ? payload.detail.map((d) => d.msg || JSON.stringify(d)).join(", ")
          : res.statusText || "Unexpected error";
    // A rejected token shouldn't keep the app in a broken state.
    if (res.status === 401 && token) tokenStore.clear();
    throw new ApiError(res.status, detail);
  }
  return payload;
}

function safeJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

/** Build "?a=1&b=x" from an object, skipping empty values. */
export function qs(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "" && v !== "all") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/* ------------------------------------------------------------------ */
/*  public surface — mirrors the FastAPI routers                       */
/* ------------------------------------------------------------------ */

export const api = {
  health: () => request("/health"),

  /* ---- auth & verification (Aditya's module) ---- */
  signup: (body) => request("/auth/signup", { method: "POST", body }), // { name, email, psit_roll_no }
  login: (body) => request("/auth/login", { method: "POST", body }), // { identifier }
  me: () => request("/auth/me"),
  verifyId: (body) => request("/auth/verify-id", { method: "POST", body }),
  pendingVerifications: (params = {}) =>
    request(`/auth/pending-verifications${qs({ skip: 0, limit: 100, ...params })}`),
  verifyManual: (studentId, body) =>
    request(`/auth/verify-manual/${studentId}`, { method: "POST", body }), // { action, reason? }
  githubLoginUrl: () => request("/auth/github/login"),
  linkGithub: (body) => request("/auth/github/link", { method: "POST", body }), // { github_username, github_id? }

  /* ---- issues (Abu's module) ---- */
  issues: (params = {}) =>
    request(`/issues${qs({ skip: 0, limit: 50, ...params })}`),
  issue: (id) => request(`/issues/${id}`),
  claimIssue: (id) => request(`/issues/${id}/claim`, { method: "POST", body: {} }),
  unclaimIssue: (id) => request(`/issues/${id}/unclaim`, { method: "POST", body: {} }),

  /* ---- pull requests & commits ---- */
  pullRequests: (params = {}) =>
    request(`/pull-requests${qs({ skip: 0, limit: 50, ...params })}`),
  pullRequest: (id) => request(`/pull-requests/${id}`),
  commits: (params = {}) => request(`/commits${qs({ skip: 0, limit: 50, ...params })}`),

  /* ---- contributions ---- */
  contributions: (params = {}) => request(`/contributions${qs({ limit: 50, ...params })}`),
  myContributions: () => request("/contributions/my"),
  userContributions: (userId) => request(`/contributions/${userId}`),
  setContributionValidation: (id, body) =>
    request(`/contributions/${id}/validation`, { method: "PATCH", body }), // { validation_status, note? }

  /* ---- dashboards ---- */
  studentDashboard: () => request("/dashboard/student"),
  maintainerDashboard: () => request("/dashboard/maintainer"),
  repositoryDashboard: (repoId) => request(`/dashboard/repository/${repoId}`),
  adminDashboard: () => request("/dashboard/admin"),

  /* ---- users / profiles ---- */
  myProfile: () => request("/users/me"),
  updateMyProfile: (body) => request("/users/me", { method: "PATCH", body }), // { name?, github_username? }
  publicProfile: (userId) => request(`/users/${userId}`),

  /* ---- engagement ---- */
  leaderboard: (params = {}) => request(`/leaderboard${qs({ page: 1, per_page: 20, ...params })}`),
  notifications: (params = {}) => request(`/notifications${qs({ limit: 20, ...params })}`),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: "PATCH" }),
  markAllNotificationsRead: () => request("/notifications/read-all", { method: "POST", body: {} }),
  activity: (params = {}) => request(`/activity${qs({ limit: 20, ...params })}`),

  /* ---- search ---- */
  search: (q, params = {}) => request(`/search${qs({ q, limit: 10, ...params })}`),
};

/* ------------------------------------------------------------------ */
/*  small shared helpers                                               */
/* ------------------------------------------------------------------ */

/** GitHub PR / issue URLs are derived from the repository brief + GitHub ids. */
export const githubIssueUrl = (repoBrief, issue) =>
  repoBrief?.github_repo_url
    ? `${repoBrief.github_repo_url.replace(/\/$/, "")}/issues/${issue.github_issue_id}`
    : null;

export const githubPrUrl = (repoBrief, pr) =>
  repoBrief?.github_repo_url
    ? `${repoBrief.github_repo_url.replace(/\/$/, "")}/pull/${pr.github_pr_id}`
    : null;

/**
 * The backend has no dedicated "list repositories" endpoint; repositories are
 * discovered from the `repository` brief embedded in issue / PR / commit rows.
 * Returns [{ id, name, platform, github_repo_url }].
 */
export async function discoverRepositories() {
  const data = await api.issues({ limit: 100 });
  const seen = new Map();
  (data?.items || []).forEach((i) => {
    if (i.repository && !seen.has(i.repository.id)) seen.set(i.repository.id, i.repository);
  });
  return Array.from(seen.values());
}

/** Points awarded per difficulty — same weights the leaderboard query uses. */
export const POINTS_BY_DIFFICULTY = { easy: 20, medium: 40, hard: 80 };

export const pointsFor = (issue) =>
  POINTS_BY_DIFFICULTY[issue?.difficulty] ?? 20;
