import { useSyncExternalStore } from "react";
import {
  parseApiDate,
  formatAbsolute,
  formatRelative,
  subscribeTimeTicker,
  getTimeSnapshot,
} from "@/lib/time";

/**
 * Universal RelativeTime component.
 * Driven by a single shared 30s external ticker (useSyncExternalStore)
 * with automatic subscribe/unsubscribe lifecycle.
 */
export function RelativeTime({ date, prefix = "", suffix = "", className }) {
  const now = useSyncExternalStore(subscribeTimeTicker, getTimeSnapshot, getTimeSnapshot);
  const parsed = parseApiDate(date);

  if (!parsed) {
    return <span className={className}>—</span>;
  }

  const iso = parsed.toISOString();
  const absoluteTitle = formatAbsolute(parsed);
  const relativeText = formatRelative(parsed, now);

  return (
    <time
      dateTime={iso}
      title={absoluteTitle}
      suppressHydrationWarning
      className={className}
    >
      {prefix}{relativeText}{suffix}
    </time>
  );
}

export default RelativeTime;
