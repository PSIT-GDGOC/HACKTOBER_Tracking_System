/**
 * Pure helpers for contribution timeline deduplication, upsert, and counter calculations.
 */

export function getIssueId(item) {
  if (!item) return null;
  return item.issue?.id ?? item.issue_id ?? item.id ?? null;
}

export function getUpdatedAtMs(item) {
  if (!item) return 0;
  const iso = item.updated_at || item.created_at;
  if (!iso) return 0;
  // Parse naive or offset strings safely
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/**
 * Checks if a contribution record is considered released or expired.
 */
export function isReleasedOrExpired(item) {
  if (!item) return false;
  if (item.status === "released" || item.status === "expired") {
    return true;
  }
  // Check timeline_json for trailing released/expired event
  if (Array.isArray(item.timeline_json) && item.timeline_json.length > 0) {
    const lastEvent = item.timeline_json[item.timeline_json.length - 1];
    if (lastEvent?.status === "released" || lastEvent?.status === "expired") {
      return true;
    }
  }
  return false;
}

/**
 * Deduplicate contribution items by issue ID.
 * - Key = issueId
 * - Newest updatedAt wins
 * - Excludes released and expired contributions from active tabs/timeline
 * - Sorted newest first
 */
export function dedupeByIssue(items = [], { includeReleased = false } = {}) {
  if (!Array.isArray(items)) return [];

  const map = new Map();

  for (const item of items) {
    if (!item) continue;
    if (!includeReleased && isReleasedOrExpired(item)) {
      continue;
    }

    const issueKey = getIssueId(item);
    if (issueKey === null || issueKey === undefined) {
      continue;
    }

    const key = String(issueKey);
    const existing = map.get(key);

    if (!existing) {
      map.set(key, item);
    } else {
      const existingTime = getUpdatedAtMs(existing);
      const itemTime = getUpdatedAtMs(item);
      if (itemTime >= existingTime) {
        map.set(key, item);
      }
    }
  }

  // Sort newest first
  return Array.from(map.values()).sort((a, b) => getUpdatedAtMs(b) - getUpdatedAtMs(a));
}

/**
 * Upsert an item into an existing deduped contribution list.
 * Never performs a naive [...old, new] append.
 */
export function upsertByIssue(list = [], newItem) {
  if (!newItem) return Array.isArray(list) ? list : [];
  const currentList = Array.isArray(list) ? list : [];
  const issueKey = getIssueId(newItem);

  if (issueKey === null || issueKey === undefined) {
    return currentList;
  }

  const key = String(issueKey);

  // If item is released/expired, remove it from active contributions
  if (isReleasedOrExpired(newItem)) {
    return currentList.filter((item) => String(getIssueId(item)) !== key);
  }

  const idx = currentList.findIndex((item) => String(getIssueId(item)) === key);
  let nextList;

  if (idx >= 0) {
    nextList = [...currentList];
    nextList[idx] = newItem;
  } else {
    nextList = [newItem, ...currentList];
  }

  return nextList.sort((a, b) => getUpdatedAtMs(b) - getUpdatedAtMs(a));
}

/**
 * Compute derived counts from deduped contribution list.
 */
export function computeContributionCounts(dedupedItems = []) {
  const items = Array.isArray(dedupedItems) ? dedupedItems : [];
  const total = items.length;
  let valid = 0;
  let merged = 0;
  let inProgress = 0;
  const statusCounts = { all: total };

  for (const item of items) {
    const status = item.status;
    statusCounts[status] = (statusCounts[status] || 0) + 1;

    if (item.validation_status === "valid" || item.validation_status === "VALID") {
      valid += 1;
    }
    if (status === "merged") {
      merged += 1;
    } else {
      inProgress += 1;
    }
  }

  return {
    total,
    valid,
    merged,
    inProgress,
    statusCounts,
  };
}
