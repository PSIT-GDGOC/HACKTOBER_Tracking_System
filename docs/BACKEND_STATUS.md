# Backend Status & Contract Review

## Requested Backend Changes

The following gaps and discrepancies between backend implementation and frontend contract were observed during frontend defect resolution (Defects D1–D7). Frontend workarounds and fallbacks are active in `fix/frontend-claims-time-deeplinks`.

### 1. Duplicate Contribution Records on Claim Mutations
- **Component**: `backend/app/services/issue_service.py` (`claim_issue`)
- **Evidence**: Repeated claim requests for the same issue ID create new rows in the `contributions` table rather than returning the existing active claim or performing an idempotent upsert on `(user_id, issue_id)`. This caused multiple contribution cards to appear for a single issue on the user timeline.
- **Frontend Fallback**: Implemented pure `dedupeByIssue` and `upsertByIssue` in `frontend/src/lib/contributions.js` (newest `updated_at` wins, active claims take precedence over duplicate historical entries).
- **Requested Fix**: Add a unique constraint or check `existing_claim` in `claim_issue` to prevent inserting duplicate `Contribution` rows for the same user and issue.

---

### 2. Missing Structured IDs (`repo_id`, `issue_id`) in Notifications
- **Component**: `backend/app/services/notification_service.py` / `webhook_service.py`
- **Evidence**: Notification payloads for PR review events contain descriptive text (e.g., `"Review submitted on PR #12 for issue #45"`) but omit structured identifiers `repo_id`, `issue_id`, and `pr_id` in the JSON response model.
- **Frontend Fallback**: Marked notification as read and closed popover without navigating when IDs are missing (strictly avoiding regex parsing of untrusted text strings per security rules).
- **Requested Fix**: Include `repo_id: Optional[int]`, `issue_id: Optional[int]`, and `pr_id: Optional[int]` in the `NotificationResponse` schema and payload.

---

### 3. Naive ISO Timestamps Without Timezone Offset
- **Component**: Pydantic serialization / SQLAlchemy UTC datetime columns
- **Evidence**: Endpoints returning timestamps (`created_at`, `updated_at`, `claimed_at`) return naive strings such as `"2026-09-29T12:00:00"` instead of ISO 8601 with timezone (`"2026-09-29T12:00:00Z"`). Standard browser `Date.parse()` interprets naive ISO strings as local device time, causing incorrect "6h ago" calculations in UTC+5:30 (IST).
- **Frontend Fallback**: Created `parseApiDate` in `frontend/src/lib/time.js` that appends `Z` to naive ISO timestamp strings and treats date-only strings as UTC.
- **Requested Fix**: Ensure all datetime fields in FastAPI/Pydantic serializers are timezone-aware and serialized with a trailing `Z` or `+00:00`.

---

### 4. Unclaim Mutation Does Not Invalidate Contribution Status
- **Component**: `backend/app/services/issue_service.py` (`unclaim_issue:L626`)
- **Evidence**: Releasing or unclaiming an issue leaves or marks the contribution record in a `"released"` state, but the record is still returned in `/contributions/my` and counted in naive total stats queries.
- **Frontend Fallback**: Excluded `released` status records from active timeline status tabs and contribution status counts in `computeContributionCounts`.
- **Requested Fix**: Soft-delete or properly reset contribution records upon unclaiming, or update the dashboard aggregation queries to filter out `status = 'released'`.

---

### 5. Stats Cards vs. Contribution Items Discrepancy
- **Component**: `backend/app/api/endpoints/dashboard.py` (`GET /dashboard/student`)
- **Evidence**: `GET /dashboard/student` computes summary counts (`active_claims_count`, `valid_contributions_count`) via raw table counts that count duplicate claims and released issues, causing counter discrepancies with the deduped contribution list.
- **Frontend Fallback**: Kept backend-provided `StatCard` values intact on overview while deriving timeline tab badge counts strictly from deduped items.
- **Requested Fix**: Harmonize dashboard summary counter queries to match deduplicated active contribution criteria.
