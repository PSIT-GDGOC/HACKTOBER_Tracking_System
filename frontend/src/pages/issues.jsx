/**
 * Issue Explorer — filterable list backed by GET /issues (server-side filters),
 * detail opens in a slide-over drawer (not a separate route).
 */
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useData } from "@/lib/hooks";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Button, EmptyState, ErrorState, LoadingBlock, Pagination, Panel, StatCard, Tabs,
} from "@/components/ui";
import { FilterBar, IssueCard, IssueCardSkeleton } from "@/components/domain";
import { useDrawers } from "@/components/drawers";
import { compact, pointsFor } from "@/lib/format";

const PAGE_SIZE = 12;

const REPO_OPTIONS_PLACEHOLDER = [{ value: "all", label: "Any repo" }];

export default function IssueExplorer() {
  const [params, setParams] = useSearchParams();
  const drawers = useDrawers();
  const [filters, setFilters] = useState({
    repo_id: params.get("repo_id") ?? "",
    difficulty: params.get("difficulty") ?? "",
    category: params.get("category") ?? "",
    tech_tag: params.get("tech_tag") ?? "",
    status: params.get("status") ?? "",
    search: params.get("search") ?? "",
    skip: 0,
  });
  const [repos, setRepos] = useState([]);

  /** Deep links like /dashboard/issues?status=claimed update filters in place. */
  useEffect(() => {
    setFilters((f) => ({
      ...f,
      repo_id: params.get("repo_id") ?? f.repo_id,
      difficulty: params.get("difficulty") ?? f.difficulty,
      category: params.get("category") ?? f.category,
      status: params.get("status") ?? f.status,
      search: params.get("search") ?? f.search,
      skip: 0,
    }));
  }, [params]);

  /** ?open={issueId} deep link — opens the detail drawer. */
  useEffect(() => {
    const open = params.get("open");
    if (open) {
      drawers.openIssue(open);
      const next = new URLSearchParams(params);
      next.delete("open");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  /** Repository options come from issue rows (no dedicated repos endpoint). */
  useEffect(() => {
    api.issues({ limit: 100 }).then((data) => {
      const seen = new Map();
      (data?.items || []).forEach((i) => {
        if (i.repository && !seen.has(i.repository.id)) seen.set(i.repository.id, i.repository);
      });
      setRepos(Array.from(seen.values()));
    }).catch(() => {});
  }, []);

  const q = useData(
    () =>
      api.issues({
        repo_id: filters.repo_id || undefined,
        difficulty: filters.difficulty || undefined,
        category: filters.category || undefined,
        tech_tag: filters.tech_tag || undefined,
        status: filters.status || undefined,
        search: filters.search || undefined,
        skip: filters.skip,
        limit: PAGE_SIZE,
      }),
    [filters],
    { pollMs: 45000 },
  );

  const data = q.data;
  const total = data?.total ?? 0;
  const page = Math.floor(filters.skip / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const setParam = (k, v) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  const set = (k, v) => setFilters((f) => ({ ...f, [k]: v, skip: 0 }));

  const groups = [
    {
      label: "Repository",
      value: filters.repo_id || "all",
      onChange: (v) => set("repo_id", v === "all" ? "" : v),
      options: [
        ...REPO_OPTIONS_PLACEHOLDER,
        ...repos.map((r) => ({ value: String(r.id), label: r.name })),
      ],
    },
    {
      label: "Difficulty",
      value: filters.difficulty || "all",
      onChange: (v) => set("difficulty", v === "all" ? "" : v),
      options: [
        { value: "all", label: "Any" },
        { value: "easy", label: "● Easy" },
        { value: "medium", label: "●● Medium" },
        { value: "hard", label: "●●● Hard" },
      ],
    },
    {
      label: "Status",
      value: filters.status || "all",
      onChange: (v) => set("status", v === "all" ? "" : v),
      options: [
        { value: "all", label: "Any" },
        { value: "open", label: "Open" },
        { value: "claimed", label: "Claimed" },
        { value: "in_progress", label: "In progress" },
        { value: "closed", label: "Closed" },
      ],
    },
  ];

  const items = data?.items || [];
  const openNow = items.filter((i) => i.status === "open").length;
  const pointsOnPage = items.reduce((a, i) => a + pointsFor(i), 0);

  return (
    <>
      <PageHeader
        eyebrow="Contribute"
        title="Issue Explorer"
        subtitle="Synced from both official repositories. Filters run server-side; claims are locked atomically so no two students can work the same issue."
        sticker={`${total} issues`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />

      <div className="mb-5">
        <FilterBar
          groups={groups}
          search={filters.search}
          onSearch={(v) => {
            set("search", v);
            setParam("search", v);
          }}
          searchPlaceholder="Search issue titles and descriptions…"
          onReset={() => {
            setParams(new URLSearchParams(), { replace: true });
            setFilters({ repo_id: "", difficulty: "", category: "", tech_tag: "", status: "", search: "", skip: 0 });
          }}
          count={total}
        />
      </div>

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard label="Open on this page" value={openNow} sub="claimable immediately" tone="green" />
        <StatCard label="Showing" value={`${items.length} of ${compact(total)}`} sub={`page ${page} of ${totalPages}`} tone="blue" />
        <StatCard label="Points on page" value={compact(pointsOnPage)} sub="if you merged all of them" tone="yellow" />
      </div>

      {q.loading && (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <IssueCardSkeleton key={i} />)}
        </div>
      )}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {data && items.length === 0 && (
        <EmptyState
          title="No issues match those filters"
          body="Try widening the difficulty or clearing the search — new issues land every week during the sprint."
          action={
            <Button variant="paper" onClick={() => { setParams(new URLSearchParams(), { replace: true }); setFilters({ repo_id: "", difficulty: "", category: "", tech_tag: "", status: "", search: "", skip: 0 }); }}>
              Clear all filters
            </Button>
          }
        />
      )}

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((i) => (
          <IssueCard key={i.id} issue={i} />
        ))}
      </div>

      {data && totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPage={(p) => setFilters((f) => ({ ...f, skip: (p - 1) * PAGE_SIZE }))}
        />
      )}

      {drawers.drawerElements}
    </>
  );
}
