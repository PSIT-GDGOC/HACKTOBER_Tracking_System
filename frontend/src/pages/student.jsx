/**
 * Student Dashboard — tabs: Overview / My Issues / My Contributions.
 * Data: GET /dashboard/student, GET /contributions/my, issues filtered by active claim.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, pointsFor, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData } from "@/lib/hooks";
import { compact, fullDate, statusLabel, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Avatar, Badge, Button, Callout, EmptyState, ErrorState, LinkButton,
  LoadingBlock, Panel, SectionHeading, StatCard, StatusBadge, Tabs,
} from "@/components/ui";
import { BarChart, ContributionCard, IssueCard, PRCard } from "@/components/domain";
import { useDrawers } from "@/components/drawers";

export default function StudentDashboard() {
  const { user } = useAuth();
  const [tab, setTab] = useState("overview");
  const drawers = useDrawers();

  const dash = useData(() => api.studentDashboard(), [], { pollMs: 60000 });
  const contribs = useData(() => api.myContributions(), [tab === "contributions"], { enabled: tab === "contributions" });
  const myIssues = useData(() => api.issues({ status: "claimed", limit: 100 }), [tab === "my-issues"], { enabled: tab === "my-issues" });

  if (dash.loading && !dash.data)
    return (
      <>
        <PageHeader eyebrow="Student" title={`Welcome back, ${(user?.name || "").split(" ")[0]}`} sticker="loading" />
        <LoadingBlock label="Pulling your dashboard summary" rows={5} />
      </>
    );
  if (dash.error || !dash.data)
    return <ErrorState message={dash.error ?? "No summary available"} onRetry={dash.refetch} />;

  const d = dash.data;
  const myClaimedIssues = (myIssues.data?.items || []).filter(
    (i) => i.active_claim && user && i.active_claim.user_id === user.id,
  );
  const inReview = (contribs.data?.items || []).filter((c) =>
    ["pr_submitted", "under_review", "changes_requested", "accepted"].includes(c.status),
  );

  return (
    <>
      <PageHeader
        eyebrow="Student dashboard"
        title={`${d.name.split(" ")[0]}'s workspace`}
        subtitle={`Open Source Sprint · ${d.verified ? "verified account" : "verification pending"} · synced continuously from GitHub webhooks`}
        sticker={`${d.active_claims_count} active claims`}
        actions={<UpdatedPill lastUpdated={dash.lastUpdated} />}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "my-issues", label: "My issues", count: tab === "my-issues" ? myClaimedIssues.length : undefined },
          { key: "contributions", label: "My contributions", count: contribs.data?.total_contributions },
        ]}
      />

      <div className="mt-6">
        {tab === "overview" && (
          <OverviewTab d={d} inReview={inReview} />
        )}
        {tab === "my-issues" && <MyIssuesTab issues={myClaimedIssues} loading={myIssues.loading} error={myIssues.error} onRetry={myIssues.refetch} />}
        {tab === "contributions" && <ContributionsTab q={contribs} />}
      </div>
      {drawers.drawerElements}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Overview tab                                                       */
/* ------------------------------------------------------------------ */

function OverviewTab({ d, inReview }) {
  const lastClaim = d.active_claims?.[0];
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="min-w-0 space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Active claims" value={d.active_claims_count} sub="locked to you" tone="blue" />
          <StatCard label="PRs submitted" value={d.prs_submitted_count} sub={`${d.prs_merged_count} merged`} tone="green" />
          <StatCard label="Valid contributions" value={d.valid_contributions_count} sub="counted on the leaderboard" tone="yellow" />
          <StatCard label="GitHub" value={d.github_username ? `@${d.github_username}` : "not linked"} sub={d.verified ? "verified" : "verification pending"} tone={d.verified ? "purple" : "red"} />
        </div>

        <Panel className="p-5">
          <SectionHeading
            title="Active claims"
            subtitle="Database-level atomic locks — no two students can hold the same issue."
            action={<Link to="/dashboard/issues" className="font-mono text-[11px] font-bold uppercase underline">explore →</Link>}
          />
          {(d.active_claims || []).length === 0 ? (
            <EmptyState
              title="No active claims"
              body="Pick something from the issue explorer to get started."
              action={<LinkButton to="/dashboard/issues" variant="green">Browse issues</LinkButton>}
            />
          ) : (
            <div className="space-y-3">
              {d.active_claims.map((c) => (
                <div key={c.claim_id} className="flex flex-wrap items-center justify-between gap-3 border-2 border-ink bg-paper-2/40 p-3">
                  <div className="min-w-0">
                    <p className="truncate font-display text-sm font-extrabold">
                      <span className="font-mono text-ink-soft">#{c.issue_id}</span> {c.issue_title}
                    </p>
                    <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
                      {c.repo_name} · {c.difficulty} · +{pointsFor(c.difficulty)} pts · claimed {timeAgo(c.claimed_at)}
                    </p>
                  </div>
                  <StatusBadge status="active" />
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel className="p-5">
          <SectionHeading
            title="Recent pull requests"
            subtitle="Auto-linked to your claims by GitHub username."
          />
          {(d.recent_prs || []).length === 0 ? (
            <EmptyState title="No PRs yet" body="Open a PR referencing your claimed issue — it appears here the moment the webhook lands." />
          ) : (
            <div className="space-y-3">
              {d.recent_prs.map((p) => <PRCard key={p.id} pr={p} showContributor={false} />)}
            </div>
          )}
        </Panel>

        {inReview.length > 0 && (
          <Panel className="p-5">
            <SectionHeading title="In the pipeline" subtitle="Everything between PR submitted and merged." />
            <div className="space-y-3">
              {inReview.slice(0, 4).map((c) => <ContributionCard key={c.id} c={c} expandable={false} />)}
            </div>
          </Panel>
        )}
      </div>

      <div className="min-w-0 space-y-6">
        <Panel className="p-5">
          <SectionHeading title="Contribution mix" subtitle="From your contribution records." />
          <BarChart
            data={[
              { label: "claims", value: d.active_claims_count },
              { label: "PRs", value: d.prs_submitted_count },
              { label: "merged", value: d.prs_merged_count },
              { label: "valid", value: d.valid_contributions_count },
            ]}
          />
        </Panel>

        <Panel className="p-5">
          <SectionHeading title="Latest claim" />
          {lastClaim ? (
            <>
              <p className="font-display text-lg font-extrabold leading-tight">{lastClaim.issue_title}</p>
              <p className="mt-1 font-mono text-[11px] text-ink-soft">{fullDate(lastClaim.claimed_at)}</p>
              <div className="mt-3"><StatusBadge status="active" /></div>
            </>
          ) : (
            <p className="font-mono text-xs text-ink-soft">No active deadlines. Nice and calm.</p>
          )}
        </Panel>

        <Panel className="bg-gblue-light p-5">
          <p className="font-display text-sm font-extrabold uppercase">Maintainer tip</p>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">
            PRs that reference the issue number get auto-linked and reviewed faster than ones that don't.
          </p>
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  My Issues tab                                                      */
/* ------------------------------------------------------------------ */

function MyIssuesTab({ issues, loading, error, onRetry }) {
  const drawers = useDrawers();
  if (loading) return <LoadingBlock rows={5} label="Loading your claimed issues" />;
  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (!issues.length)
    return (
      <EmptyState
        title="You haven't claimed anything yet"
        body="Browse the explorer and lock your first issue."
        action={<LinkButton to="/dashboard/issues" variant="green">Browse issues</LinkButton>}
      />
    );
  return (
    <>
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {issues.map((i) => <IssueCard key={i.id} issue={i} />)}
      </div>
      {drawers.drawerElements}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  My Contributions tab                                               */
/* ------------------------------------------------------------------ */

const TABS = [
  { key: "all", label: "All" },
  { key: "claimed", label: "Claimed" },
  { key: "in_progress", label: "In progress" },
  { key: "pr_submitted", label: "PR submitted" },
  { key: "under_review", label: "Under review" },
  { key: "changes_requested", label: "Changes requested" },
  { key: "accepted", label: "Accepted" },
  { key: "merged", label: "Merged" },
];

function ContributionsTab({ q }) {
  const [filter, setFilter] = useState("all");
  const items = q.data?.items || [];

  const counts = useMemo(() => {
    const c = { all: items.length };
    items.forEach((x) => (c[x.status] = (c[x.status] ?? 0) + 1));
    return c;
  }, [items]);

  const filtered = items.filter((c) => filter === "all" || c.status === filter);

  return (
    <>
      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total claims" value={counts.all ?? 0} tone="blue" />
        <StatCard label="Merged" value={counts.merged ?? 0} tone="green" />
        <StatCard label="Needs your action" value={(counts.changes_requested ?? 0) + (counts.in_progress ?? 0)} sub="reviews or work pending" tone="red" />
        <StatCard label="Valid" value={q.data?.valid_contributions_count ?? 0} sub={`of ${q.data?.total_contributions ?? 0} total`} tone="yellow" />
      </div>

      <div className="no-scrollbar mb-5 flex gap-2 overflow-x-auto border-b-[3px] border-ink pb-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setFilter(t.key)}
            className={`whitespace-nowrap border-2 border-ink px-3.5 py-1.5 font-display text-xs font-bold uppercase tracking-wide ${
              filter === t.key ? "bg-ink text-gyellow shadow-[3px_3px_0_0_#101010]" : "bg-white hover:bg-gyellow-light"
            }`}
          >
            {statusLabel(t.key)}
            {counts[t.key] ? <span className="ml-1.5 font-mono opacity-70">({counts[t.key]})</span> : null}
          </button>
        ))}
      </div>

      {q.loading && <LoadingBlock label="Loading your timeline" rows={4} />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && filtered.length === 0 && (
        <EmptyState
          title={filter === "all" ? "No contributions yet" : `Nothing in "${statusLabel(filter)}"`}
          body="Claim an issue from the explorer to start your timeline. It fills in automatically as webhooks arrive."
          action={<LinkButton to="/dashboard/issues" variant="green">Browse open issues</LinkButton>}
        />
      )}
      <div className="min-w-0 space-y-4">
        {filtered.map((c) => <ContributionCard key={c.id} c={c} />)}
      </div>
    </>
  );
}
