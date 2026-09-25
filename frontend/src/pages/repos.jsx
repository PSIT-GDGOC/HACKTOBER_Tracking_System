/**
 * Repository Hub — repositories discovered from issue/PR rows; each repo renders
 * Overview / Pull Requests / Commits tabs (GET /dashboard/repository/{id}).
 * Also hosts the cross-repo Pull Requests and Commits pages.
 */
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, discoverRepositories } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData, useDebounced } from "@/lib/hooks";
import { compact, PLATFORM_LABEL, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  EmptyState, ErrorState, LinkButton, LoadingBlock, Pagination, Panel,
  SectionHeading, StatCard, StatusBadge, Tabs,
} from "@/components/ui";
import { CommitRow, FilterBar, PRCard, RepoCard, SplitBar } from "@/components/domain";
import { useDrawers } from "@/components/drawers";

/* ================================================================== */
/*  Repository Hub (list + per-repo tabs)                              */
/* ================================================================== */

export function Repositories() {
  const { repoId } = useParams();
  const [repos, setRepos] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const drawers = useDrawers();

  useEffect(() => {
    discoverRepositories()
      .then(setRepos)
      .catch((e) => setLoadError(e?.detail || e?.message || "Could not load repositories"));
  }, []);

  const repo = repos?.find((r) => String(r.id) === String(repoId));

  return (
    <>
      <PageHeader
        eyebrow="Repositories"
        title={repo ? repo.name : "Program repositories"}
        subtitle={
          repo
            ? `${PLATFORM_LABEL[repo.platform] ?? repo.platform} · ${repo.github_repo_url}`
            : "Two codebases, one leaderboard. Issues, PRs and commits sync from GitHub via webhooks."
        }
        actions={
          repo ? (
            <a
              href={repo.github_repo_url}
              target="_blank"
              rel="noreferrer"
              className="border-[3px] border-ink bg-ink px-4 py-2.5 font-display text-sm font-bold uppercase text-paper shadow-[4px_4px_0_0_#101010] hover:-translate-y-0.5"
            >
              GitHub ↗
            </a>
          ) : undefined
        }
      />

      {!repoId && (
        <>
          {loadError && <ErrorState message={loadError} onRetry={() => discoverRepositories().then(setRepos)} />}
          {!repos && <LoadingBlock rows={4} label="Loading repositories" />}
          {repos && repos.length === 0 && (
            <EmptyState
              title="No repositories discovered yet"
              body="Repositories appear once issues are synced from GitHub. Ask a maintainer to run POST /issues/sync."
            />
          )}
          <div className="grid min-w-0 gap-5 md:grid-cols-2">
            {repos?.map((r) => <RepoCard key={r.id} repo={r} />)}
          </div>
        </>
      )}

      {repoId && repo && <RepoHub repo={repo} />}
      {repoId && !repo && repos && (
        <EmptyState title="Repository not found" body="Pick a repository from the hub." action={<LinkButton to="/dashboard/repos" variant="blue">← Repository hub</LinkButton>} />
      )}
      {drawers.drawerElements}
    </>
  );
}

function RepoHub({ repo }) {
  const [tab, setTab] = useState("overview");
  const dash = useData(() => api.repositoryDashboard(repo.id), [repo.id], { pollMs: 60000 });
  const drawers = useDrawers();

  const prs = useData(
    () => api.pullRequests({ repo_id: repo.id, limit: 50 }),
    [repo.id, tab === "prs"],
    { enabled: tab === "prs" },
  );
  const commits = useData(
    () => api.commits({ repo_id: repo.id, limit: 50 }),
    [repo.id, tab === "commits"],
    { enabled: tab === "commits" },
  );
  const issues = useData(
    () => api.issues({ repo_id: repo.id, limit: 50 }),
    [repo.id, tab === "overview"],
    { enabled: tab === "overview" },
  );

  const d = dash.data;

  return (
    <>
      {!d && dash.loading && <LoadingBlock rows={5} label="Loading repository stats" />}
      {!d && dash.error && <ErrorState message={dash.error} onRetry={dash.refetch} />}

      {d && (
        <>
          <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Open issues" value={d.open_issues} sub={`${d.total_issues} synced total`} tone="blue" />
            <StatCard label="Pull requests" value={d.total_prs} sub={`${d.merged_prs} merged · ${d.open_prs} open`} tone="red" />
            <StatCard label="Commits" value={compact(d.total_commits)} sub="via push webhook events" tone="purple" />
            <StatCard label="Contributors" value={d.unique_contributors_count} sub={`${d.claimed_issues} issues in progress`} tone="green" />
          </div>

          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { key: "overview", label: "Overview" },
              { key: "prs", label: "Pull requests", count: prs.data?.total },
              { key: "commits", label: "Commits", count: commits.data?.total },
            ]}
          />

          <div className="mt-5 grid gap-6 lg:grid-cols-[1.5fr_0.5fr]">
            <div className="min-w-0">
              {tab === "overview" && (
                <div className="space-y-4">
                  <Panel className="p-5">
                    <SectionHeading
                      title="Issue breakdown"
                      subtitle="Open vs claimed vs closed — sync health at a glance."
                    />
                    <SplitBar
                      opened={d.open_issues}
                      merged={d.total_issues - d.open_issues - d.closed_issues}
                    />
                    <div className="mt-4 grid grid-cols-3 gap-3">
                      {[
                        ["Open", d.open_issues, "bg-ggreen-light"],
                        ["In progress", d.claimed_issues, "bg-gblue-light"],
                        ["Closed", d.closed_issues, "bg-paper-3"],
                      ].map(([l, v, tone]) => (
                        <div key={l} className={`border-2 border-ink ${tone} p-3`}>
                          <p className="font-display text-2xl font-extrabold leading-none">{v}</p>
                          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">{l}</p>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  {(issues.data?.items || []).length > 0 && (
                    <Panel className="p-5">
                      <SectionHeading
                        title="Issues in this repo"
                        action={<Link to="/dashboard/issues" className="font-mono text-[11px] font-bold uppercase underline">explorer →</Link>}
                      />
                      <div className="space-y-2">
                        {(issues.data?.items || []).slice(0, 8).map((i) => (
                          <button
                            key={i.id}
                            onClick={() => drawers.openIssue(i.id)}
                            className="flex w-full items-center justify-between gap-3 border-b-2 border-dashed border-paper-3 py-2 text-left last:border-0 hover:bg-gyellow-light"
                          >
                            <span className="min-w-0 truncate text-sm font-bold">
                              <span className="font-mono text-ink-soft">#{i.github_issue_id}</span> {i.title}
                            </span>
                            <StatusBadge status={i.status} />
                          </button>
                        ))}
                      </div>
                    </Panel>
                  )}
                </div>
              )}

              {tab === "prs" && (
                prs.loading ? <LoadingBlock rows={5} />
                : prs.error ? <ErrorState message={prs.error} onRetry={prs.refetch} />
                : (prs.data?.items || []).length === 0 ? <EmptyState title="No pull requests yet" body="PRs appear here as the webhook auto-links them." />
                : <div className="space-y-3">{prs.data.items.map((p) => <PRCard key={p.id} pr={p} />)}</div>
              )}

              {tab === "commits" && (
                commits.loading ? <LoadingBlock rows={5} />
                : commits.error ? <ErrorState message={commits.error} onRetry={commits.refetch} />
                : (commits.data?.items || []).length === 0 ? <EmptyState title="No commits recorded" />
                : <Panel className="p-5">{commits.data.items.map((c, i) => <CommitRow key={i} commit={c} />)}</Panel>
              )}
            </div>

            <div className="min-w-0 space-y-6">
              <Panel className="p-5">
                <SectionHeading title="PR flow" />
                <SplitBar opened={d.open_prs} merged={d.merged_prs} />
              </Panel>
              <Panel className="p-5">
                <SectionHeading title="Repository" />
                <p className="break-all font-mono text-[11px] text-ink-soft">{d.repository.github_repo_url}</p>
                <p className="mt-2 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
                  platform · {PLATFORM_LABEL[d.repository.platform] ?? d.repository.platform}
                </p>
              </Panel>
            </div>
          </div>
        </>
      )}
      {drawers.drawerElements}
    </>
  );
}

/* ================================================================== */
/*  Pull requests (global list)                                        */
/* ================================================================== */

const PAGE = 20;

export function PullRequests() {
  const [params, setParams] = useSearchParams();
  const drawers = useDrawers();
  const [filters, setFilters] = useState({
    status: params.get("status") ?? "",
    search: "",
    skip: 0,
  });

  useEffect(() => {
    const open = params.get("open");
    if (open) {
      drawers.openPr(open);
      const next = new URLSearchParams(params);
      next.delete("open");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const q = useData(
    () => api.pullRequests({
      status: filters.status || undefined,
      skip: filters.skip,
      limit: PAGE,
    }),
    [filters],
    { pollMs: 30000 },
  );

  const total = q.data?.total ?? 0;
  const page = Math.floor(filters.skip / PAGE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE));

  const groups = [
    {
      label: "State", value: filters.status || "all", onChange: (v) => set("status", v === "all" ? "" : v),
      options: [
        { value: "all", label: "Any" }, { value: "open", label: "Open" }, { value: "merged", label: "Merged" },
        { value: "closed", label: "Closed" }, { value: "draft", label: "Draft" },
      ],
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Repositories"
        title="Pull requests"
        subtitle="Auto-linked to claims by GitHub username through the webhook sync engine."
        sticker={`${total} PRs`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />
      <div className="mb-5">
        <FilterBar groups={groups} count={total} onReset={() => setFilters({ status: "", search: "", skip: 0 })} />
      </div>
      {q.loading && <LoadingBlock rows={5} />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && (q.data.items || []).length === 0 && <EmptyState title="No pull requests found" body="Try clearing the filters." />}
      <div className="space-y-3">
        {(q.data?.items || []).map((p) => <PRCard key={p.id} pr={p} />)}
      </div>
      {q.data && totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPage={(p) => setFilters((f) => ({ ...f, skip: (p - 1) * PAGE }))} />
      )}
      {drawers.drawerElements}
    </>
  );
}

/* ================================================================== */
/*  Commits feed                                                       */
/* ================================================================== */

export function Commits() {
  const [params] = useSearchParams();
  const [repoId, setRepoId] = useState("");
  const [repos, setRepos] = useState([]);
  const [skip, setSkip] = useState(0);
  const LIMIT = 20;

  useEffect(() => {
    discoverRepositories().then(setRepos).catch(() => {});
  }, []);

  const q = useData(
    () => api.commits({ repo_id: repoId || undefined, skip, limit: LIMIT }),
    [repoId, skip],
    { pollMs: 30000 },
  );

  const total = q.data?.total ?? 0;
  const page = Math.floor(skip / LIMIT) + 1;
  const totalPages = Math.max(1, Math.ceil(total / LIMIT));

  const groups = [
    {
      label: "Repository", value: repoId || "all", onChange: (v) => { setRepoId(v === "all" ? "" : v); setSkip(0); },
      options: [
        { value: "all", label: "All repos" },
        ...repos.map((r) => ({ value: String(r.id), label: r.name })),
      ],
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Repositories"
        title="Commit feed"
        subtitle="Every push event that reached the webhook receiver, newest first."
        sticker={`${total} commits`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />
      <div className="mb-5">
        <FilterBar groups={groups} count={total} />
      </div>
      {q.loading && <LoadingBlock rows={6} />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && (q.data.items || []).length === 0 && <EmptyState title="No commits match" />}
      {q.data && (q.data.items || []).length > 0 && (
        <Panel className="p-5">{q.data.items.map((c, i) => <CommitRow key={i} commit={c} />)}</Panel>
      )}
      {q.data && totalPages > 1 && (
        <Pagination page={page} totalPages={totalPages} onPage={(p) => setSkip((p - 1) * LIMIT)} />
      )}
    </>
  );
}
