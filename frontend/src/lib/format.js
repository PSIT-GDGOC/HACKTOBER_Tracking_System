/**
 * Formatting helpers for the backend's data shapes.
 */
import { POINTS_BY_DIFFICULTY } from "./api";

/* ------------------------------ time ------------------------------ */

export function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const abs = Math.abs(diff);
  const future = diff < 0;
  if (abs < 60000) return future ? "in <1m" : "just now";
  if (abs < 3600000) return fmt(abs / 60000, "m", future);
  if (abs < 86400000) return fmt(abs / 3600000, "h", future);
  if (abs < 2592000000) return fmt(abs / 86400000, "d", future);
  return fmt(abs / 2592000000, "mo", future);
}

const fmt = (v, u, future) => {
  const n = Math.round(v);
  return future ? `in ${n}${u}` : `${n}${u} ago`;
};

export function fullDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

/* ------------------------------ numbers ------------------------------ */

export const nfmt = (n) =>
  n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `${n}`;

export const compact = (n) => Number(n ?? 0).toLocaleString("en-IN");

/* ------------------------------ badges ------------------------------ */

const TONE = { bg: "bg-paper-3", text: "text-ink", border: "border-ink" };

export const difficultyTone = {
  easy: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  medium: { bg: "bg-gyellow-light", text: "text-ink", border: "border-ink" },
  hard: { bg: "bg-gred-light", text: "text-ink", border: "border-ink" },
};

export const difficultyIcon = { easy: "●", medium: "●●", hard: "●●●" };

export const pointsFor = (issueOrDifficulty) =>
  POINTS_BY_DIFFICULTY[
    typeof issueOrDifficulty === "string" ? issueOrDifficulty : issueOrDifficulty?.difficulty
  ] ?? 20;

const STATUS_TONE = {
  /* issue + contribution + PR + review statuses */
  claimed: { bg: "bg-gblue-light", text: "text-ink", border: "border-ink" },
  in_progress: { bg: "bg-gblue-light", text: "text-ink", border: "border-ink" },
  pr_submitted: { bg: "bg-gpurple-light", text: "text-ink", border: "border-ink" },
  under_review: { bg: "bg-gyellow-light", text: "text-ink", border: "border-ink" },
  changes_requested: { bg: "bg-gred-light", text: "text-ink", border: "border-ink" },
  accepted: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  merged: { bg: "bg-ggreen", text: "text-white", border: "border-ink" },
  open: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  closed: { bg: "bg-paper-3", text: "text-ink", border: "border-ink" },
  draft: { bg: "bg-paper-3", text: "text-ink", border: "border-ink" },
  /* validation */
  valid: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  pending: { bg: "bg-gyellow-light", text: "text-ink", border: "border-ink" },
  rejected: { bg: "bg-gred-light", text: "text-ink", border: "border-ink" },
  duplicate: { bg: "bg-gpurple-light", text: "text-ink", border: "border-ink" },
  invalid: { bg: "bg-paper-3", text: "text-ink", border: "border-ink" },
  /* reviews */
  approved: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  commented: { bg: "bg-gblue-light", text: "text-ink", border: "border-ink" },
  dismissed: { bg: "bg-paper-3", text: "text-ink", border: "border-ink" },
  pending_review: { bg: "bg-gyellow-light", text: "text-ink", border: "border-ink" },
  /* claims */
  active: { bg: "bg-gblue-light", text: "text-ink", border: "border-ink" },
  released: { bg: "bg-paper-3", text: "text-ink", border: "border-ink" },
  expired: { bg: "bg-gred-light", text: "text-ink", border: "border-ink" },
  completed: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  /* accounts */
  student: { bg: "bg-gblue-light", text: "text-ink", border: "border-ink" },
  maintainer: { bg: "bg-gpurple-light", text: "text-ink", border: "border-ink" },
  admin: { bg: "bg-ink", text: "text-paper", border: "border-ink" },
  auto_verified: { bg: "bg-ggreen-light", text: "text-ink", border: "border-ink" },
  manual: { bg: "bg-gyellow-light", text: "text-ink", border: "border-ink" },
};

export const statusTone = (s) => STATUS_TONE[s] ?? TONE;

export const statusLabel = (s) =>
  String(s ?? "—").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/* ------------------------------ misc ------------------------------ */

export const PLATFORM_LABEL = { web: "Web App", android: "Android App" };

export const CONTRIBUTION_FLOW = [
  "claimed", "in_progress", "pr_submitted", "under_review", "changes_requested", "accepted", "merged",
];

export const ACTIVITY_ICON = {
  claim_created: "📌",
  claim_released: "↩",
  pr_opened: "🔀",
  pr_merged: "🎉",
  review_submitted: "🔍",
  pr_review: "🔍",
  contribution_moderated: "⚑",
  issue_opened: "🆕",
};

/** Human copy for the activity feed description fallback. */
export const activityText = (item) => {
  if (item.description) return item.description;
  const who = item.actor?.name || item.actor?.github_username || "Someone";
  return `${who} · ${String(item.type || "activity").replace(/_/g, " ")}`;
};
