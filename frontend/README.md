# GDG on Campus PSIT ΓÇö Contribution Program Frontend

Neo-brutalist, Google-branded frontend for the GDG on Campus PSIT **Open Source Sprint**.
Every page is data-driven through a single typed API client, so the FastAPI backend can be
dropped in without touching a component.

---

## 0. Campus access gate (PSIT Kanpur only)

Before anyone can reach `/signup` or `/login` they must clear the campus verification gate at
`#/gate`. It asks a handful of questions only a PSIT Kanpur student would know ΓÇö the city, the
campus town (Bhauti), the fest (IGNITIA), the affiliating university (AKTU), and what PSIT
stands for.

- **Pass mark:** 4 of the active questions (`REQUIRED_TO_PASS`).
- **Attempt limit:** 3 failed submissions, then a 30-minute lockout per browser.
- **Validity:** passing is remembered in `sessionStorage` for the browser session, keyed to
  `GATE_VERSION`. Bump that constant to force everyone through again.
- **Enforcement:** `/login` and `/signup` are wrapped in `<RequireCampus>`, so hitting them
  directly (or linking from anywhere) still redirects to the gate.

### Editing the questions

Everything lives in **`src/lib/campusGate.ts`** ΓÇö one array called `CAMPUS_QUESTIONS`.

```ts
{
  id: "ignitia-2026-guest",
  type: "choice",                       // "choice" | "text"
  prompt: "Which celebrity was scheduled to perform at IGNITIA 2026?",
  options: ["ΓÇª", "ΓÇª", "ΓÇª", "ΓÇª"],
  correct: 0,                           // index of the right option
  enabled: false,                       // ΓåÉ flip to true once the answer is confirmed
}
```

For free-text questions use `keywordGroups` instead of `correct`. Each inner array is a group of
accepted aliases, **every group must match**, and any alias within a group satisfies it:

```ts
keywordGroups: [
  ["pranveer", "pranveer singh"],  // group 1
  ["institute", "college"],        // group 2
]
```

Matching is deliberately forgiving ΓÇö case, punctuation and accents are stripped, and words of
5+ letters match within a Levenshtein distance of 2.

**Two questions ship disabled on purpose** (`adminAnswerRequired: true`): the *protest reason*
and the *IGNITIA 2026 guest*. Their answers depend on current campus events that change every
year, so a stale hardcoded answer could lock out the whole campus. Fill in the real answer, then
set `enabled: true`.

> ΓÜá∩╕Å **This gate is a UX filter, not a security control.** Anything client-side can be bypassed
> with DevTools. Real identity enforcement stays with the ERP verification on the backend ΓÇö
> keep both.

---

## 1. Connecting the backend

```bash
# .env.local  (Vite)
VITE_API_BASE_URL=https://gdg-psit-api.onrender.com
```

That's it. When the variable is present the client switches from its in-memory demo adapter to
`fetch`, attaching `Authorization: Bearer <jwt>` from `localStorage` on every request.
When it's absent the app runs on seeded demo data so the UI is fully explorable.

Tokens are stored under `gdg_psit_access_token`; the signed-in roll under `gdg_psit_roll`.

### Swapping in generated types

`src/lib/types.ts` mirrors the backend schema by hand. Once the backend publishes
`/openapi.json`:

```bash
npx openapi-typescript https://<api>/openapi.json -o src/lib/schema.d.ts
```

ΓÇªthen re-export the generated `components["schemas"]` types from `src/lib/types.ts`.
Pages never import network shapes directly ΓÇö they only consume the `api` object ΓÇö so nothing
else changes.

---

## 2. Folder map

```
src/
Γö£ΓöÇ App.tsx                  # routing + role-based protected routes
Γö£ΓöÇ index.css                # design tokens (Google palette) + brutalist utilities
Γö£ΓöÇ lib/
Γöé  Γö£ΓöÇ api.ts                # THE network layer ΓÇö endpoint map + demo adapter
Γöé  Γö£ΓöÇ types.ts              # shared contract types (swap for generated schemas)
Γöé  Γö£ΓöÇ auth.tsx              # AuthProvider, useAuth, <RequireRole roles={[...]}>
Γöé  Γö£ΓöÇ hooks.ts              # useData / useMutation / useDebounced / useHeartbeat
Γöé  Γö£ΓöÇ format.ts             # timeAgo, status tones, labels
Γöé  ΓööΓöÇ mock.ts               # seeded demo data (repos, issues, PRs, commits, people)
Γö£ΓöÇ components/
Γöé  Γö£ΓöÇ ui.tsx                # Button, Panel, Badge, StatusBadge, StatCard, FilterBarΓÇª
Γöé  Γö£ΓöÇ domain.tsx            # IssueCard, PRCard, CommitRow, Timeline, ClaimButtonΓÇª
Γöé  ΓööΓöÇ Layout.tsx            # AppShell (sidebar/topbar/search/notifications), PageHeader
ΓööΓöÇ pages/
   Γö£ΓöÇ Landing.tsx           # event intro + CTA
   Γö£ΓöÇ auth.tsx              # signup ΓåÆ ERP ΓåÆ OTP ΓåÆ GitHub ΓåÆ pending approval ΓåÆ login
   Γö£ΓöÇ student.tsx           # dashboard, my contributions, profile edit, public profile
   Γö£ΓöÇ issues.tsx            # issue explorer (filters) + issue detail (claim/release)
   Γö£ΓöÇ repos.tsx             # repos, repo dashboard, PR list, PR detail, commit feed
   Γö£ΓöÇ engage.tsx            # leaderboard, notifications, activity feed, global search
   Γö£ΓöÇ staff.tsx             # review queue, reviewed history, admin dashboard,
   Γöé                        # participant management, moderation
   ΓööΓöÇ misc.tsx              # settings, 404, 403
```

Routes live under `#/dashboard/...` behind `<RequireRole>`; onboarding and marketing pages are public.

---

## 3. Endpoint contract the UI expects

| Method | Path |
| --- | --- |
| POST | `/auth/signup` ┬╖ `/auth/erp/verify` ┬╖ `/auth/otp/verify` ┬╖ `/auth/login` ┬╖ `/auth/logout` |
| GET | `/auth/me` ┬╖ `/auth/github/url` |
| GET | `/issues?repo&difficulty&tech&category&status&search&page&page_size` |
| GET | `/issues/{idOrNumber}` ΓåÆ `{ issue, contribution }` |
| POST | `/issues/{id}/claim` ┬╖ `/issues/{id}/release` (atomic, 409 on race) |
| GET | `/pulls?repo&contributor&status&validation&search&page` |
| GET | `/pulls/{number}` ΓåÆ `{ pull_request, commits, contribution }` |
| POST | `/pulls/{number}/review` `{ verdict, note }` |
| GET | `/commits?repo&contributor&search&page` |
| GET | `/contributions/me` ┬╖ `/contributions/{roll}` |
| GET | `/dashboard/student` ┬╖ `/dashboard/maintainer/queue` ┬╖ `/dashboard/maintainer/history` ┬╖ `/dashboard/admin` |
| GET | `/repos` ┬╖ `/repos/{key}` |
| GET/PATCH | `/profiles/me` ┬╖ `GET /profiles/{rollOrId}` |
| GET | `/leaderboard?search&scope` ┬╖ `/activity?kind&repo` ┬╖ `/search?q=` |
| GET/POST | `/notifications` ┬╖ `/notifications/{id}/read` ┬╖ `/notifications/read-all` |
| GET | `/admin/participants?search&status&role` |
| POST | `/participants/{id}/approve|reject|resend-otp|role` ┬╖ `/moderation/{id}/resolve` |
| GET/PATCH | `/settings` ┬╖ `POST /settings/github/unlink` |

Errors should be `{ "detail": "human readable message" }` with a real HTTP status ΓÇö the client
surfaces `detail` straight into the error states on every page.

### Contribution state machine

`claimed ΓåÆ in_progress ΓåÆ pr_submitted ΓåÆ under_review ΓåÆ changes_requested ΓåÆ accepted ΓåÆ merged`
(+ `released`), with validation status `valid | pending | rejected | duplicate | invalid`.
The `<StateMachineStrip>` and `<Timeline>` components render exactly this order.

---

## 4. Conventions worth keeping

- **Every data-driven page** renders a loading, empty and error state through `useData()`.
- **Polling = real-time.** Pass `{ pollMs }` to `useData`; feeds flash a "synced Xs ago" pill.
- **Mutations** go through `useMutation` and always `refetch()` the owning query.
- **Role guards** are client-side (`RequireRole`) *and* enforced by backend middleware.
- **Design tokens** are the four Google brand colours (`gblue/gred/gyellow/ggreen`) on a cream
  `paper` base with 3px ink borders and hard offset shadows ΓÇö no radius, no gradients.

## 5. Local development

```bash
npm install
npm run dev     # http://localhost:5173
npm run build   # single-file production bundle in dist/
```

Use the **role switcher** at the bottom of the sidebar (demo mode only) to inspect the student,
maintainer and admin experiences without creating three accounts.
