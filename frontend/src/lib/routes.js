/**
 * Internal route helpers and query parameter validators.
 * Navigation targets must ONLY be constructed through these typed helpers.
 */

export const ALLOWED_CONTRIBUTION_STATUSES = [
  "all",
  "claimed",
  "in_progress",
  "pr_submitted",
  "under_review",
  "changes_requested",
  "accepted",
  "merged",
];

const ISSUE_ID_REGEX = /^[0-9]{1,20}$/;

export function isValidIssueId(id) {
  if (id === null || id === undefined) return false;
  return ISSUE_ID_REGEX.test(String(id).trim());
}

export function isValidStatus(status) {
  if (!status) return false;
  return ALLOWED_CONTRIBUTION_STATUSES.includes(String(status).trim().toLowerCase());
}

export const routes = {
  dashboard: () => "/dashboard",
  studentDashboard: (tab, status) => {
    const sp = new URLSearchParams();
    if (tab) sp.set("tab", tab);
    if (status && status !== "all" && isValidStatus(status)) sp.set("status", status);
    const qs = sp.toString();
    return qs ? `/dashboard?${qs}` : "/dashboard";
  },
  issues: (params = {}) => {
    const sp = new URLSearchParams();
    if (params.issue && isValidIssueId(params.issue)) sp.set("issue", String(params.issue));
    if (params.repo_id && /^[0-9]{1,20}$/.test(String(params.repo_id))) sp.set("repo_id", String(params.repo_id));
    if (params.search && typeof params.search === "string") {
      const clean = params.search.trim().slice(0, 100);
      if (clean) sp.set("search", clean);
    }
    const qs = sp.toString();
    return qs ? `/dashboard/issues?${qs}` : "/dashboard/issues";
  },
  issue: (id) => {
    if (!isValidIssueId(id)) return "/dashboard/issues";
    return `/dashboard/issues?issue=${id}`;
  },
  repositories: () => "/dashboard/repos",
  repository: (id) => {
    if (!id || !/^[0-9]{1,20}$/.test(String(id))) return "/dashboard/repos";
    return `/dashboard/repos/${id}`;
  },
  pullRequests: (params = {}) => {
    const sp = new URLSearchParams();
    if (params.repo_id) sp.set("repo_id", String(params.repo_id));
    if (params.status) sp.set("status", String(params.status));
    const qs = sp.toString();
    return qs ? `/dashboard/pulls?${qs}` : "/dashboard/pulls";
  },
  pullRequest: (id) => {
    if (!id) return "/dashboard/pulls";
    return `/dashboard/pulls?open=${id}`;
  },
  commits: (params = {}) => {
    const sp = new URLSearchParams();
    if (params.repo_id) sp.set("repo_id", String(params.repo_id));
    const qs = sp.toString();
    return qs ? `/dashboard/commits?${qs}` : "/dashboard/commits";
  },
  profile: (userId, status) => {
    if (userId) return `/dashboard/profile/${userId}`;
    const sp = new URLSearchParams();
    if (status && status !== "all" && isValidStatus(status)) {
      sp.set("status", status);
    }
    const qs = sp.toString();
    return qs ? `/dashboard/profile?${qs}` : "/dashboard/profile";
  },
  leaderboard: () => "/dashboard/leaderboard",
  landing: () => "/",
  login: () => "/login",
  join: () => "/join",
};
