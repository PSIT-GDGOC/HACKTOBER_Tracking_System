/**
 * Time parsing, formatting, and single shared 30s ticker.
 *
 * Rules:
 * - Naive strings (and date-only strings) are treated as UTC.
 * - Strings with 'Z' or offset parse as-is.
 * - formatAbsolute uses Intl.DateTimeFormat in device timezone (no hardcoded zone).
 * - formatRelative handles small clock skew (never negative or in the future).
 * - Shared ticker lifecycle with useSyncExternalStore.
 */

const HAS_TIMEZONE_REGEX = /(?:Z|[+-]\d{2}:?\d{2})$/i;
const DATE_ONLY_REGEX = /^\d{4}-\d{2}-\d{2}$/;

/**
 * Parses an API timestamp string into a Date object.
 * Naive strings (without offset or Z) are interpreted as UTC.
 */
export function parseApiDate(input) {
  if (!input) return null;
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input;
  if (typeof input === "number") {
    const d = new Date(input);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  const str = String(input).trim();
  if (!str) return null;

  // Date-only string "YYYY-MM-DD" -> parse as UTC midnight
  if (DATE_ONLY_REGEX.test(str)) {
    const d = new Date(`${str}T00:00:00Z`);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // If already has timezone offset or 'Z', parse as-is
  if (HAS_TIMEZONE_REGEX.test(str)) {
    const d = new Date(str);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  // Naive datetime from FastAPI/SQLAlchemy (e.g. "2026-09-29T18:00:00") -> treat as UTC
  const d = new Date(`${str}Z`);
  return Number.isNaN(d.getTime()) ? new Date(str) : d;
}

/**
 * Format a date as an absolute string using the device timezone via Intl.DateTimeFormat.
 * NEVER hardcodes a timezone or locale.
 */
export function formatAbsolute(input, options = {}) {
  const d = parseApiDate(input);
  if (!d) return "—";

  try {
    const defaultOptions = {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      ...options,
    };
    return new Intl.DateTimeFormat(undefined, defaultOptions).format(d);
  } catch {
    return d.toLocaleString();
  }
}

/**
 * Format a date as relative time:
 * - <45s: "just now"
 * - <60m: "Xm ago"
 * - <24h: "Xh ago"
 * - <30d: "Xd ago"
 * - >=30d: absolute date (e.g. "15 Sep 2026")
 * Handles clock skew gracefully (never "in the future" or negative for minor skew).
 */
export function formatRelative(input, now = Date.now()) {
  const d = parseApiDate(input);
  if (!d) return "—";

  const nowMs = typeof now === "number" ? now : parseApiDate(now)?.getTime() || Date.now();
  const diffMs = nowMs - d.getTime();

  // Small clock skew handling: if in future up to 60s or past under 45s
  if (diffMs < 45000) {
    return "just now";
  }

  const minuteMs = 60 * 1000;
  const hourMs = 60 * minuteMs;
  const dayMs = 24 * hourMs;
  const monthMs = 30 * dayMs;

  if (diffMs < hourMs) {
    const m = Math.max(1, Math.floor(diffMs / minuteMs));
    return `${m}m ago`;
  }

  if (diffMs < dayMs) {
    const h = Math.max(1, Math.floor(diffMs / hourMs));
    return `${h}h ago`;
  }

  if (diffMs < monthMs) {
    const days = Math.max(1, Math.floor(diffMs / dayMs));
    return `${days}d ago`;
  }

  // For older dates, return formatted absolute date
  return formatAbsolute(d, { day: "2-digit", month: "short", year: "numeric" });
}

/* ------------------------------------------------------------------ */
/*  Shared 30s ticker using useSyncExternalStore pattern               */
/* ------------------------------------------------------------------ */

const listeners = new Set();
let tickerTimerId = null;
let currentTimestamp = Date.now();

function onTick() {
  currentTimestamp = Date.now();
  listeners.forEach((cb) => {
    try {
      cb();
    } catch {}
  });
}

function startTicker() {
  if (typeof window !== "undefined" && !tickerTimerId) {
    tickerTimerId = setInterval(onTick, 30000);
  }
}

function stopTicker() {
  if (tickerTimerId) {
    clearInterval(tickerTimerId);
    tickerTimerId = null;
  }
}

export function subscribeTimeTicker(listener) {
  listeners.add(listener);
  if (listeners.size === 1) {
    startTicker();
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      stopTicker();
    }
  };
}

export function getTimeSnapshot() {
  return currentTimestamp;
}
