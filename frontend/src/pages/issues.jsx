/**
 * Issue Explorer — clean, direct list of open issues.
 * FilterBar and stat cards removed for a simple, accurate repository workflow.
 */
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useData } from "@/lib/hooks";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Button, EmptyState, ErrorState, LoadingBlock, Pagination, Panel,
} from "@/components/ui";
import { IssueCard, IssueCardSkeleton } from "@/components/domain";
import { useDrawers } from "@/components/drawers";

const PAGE_SIZE = 12;

export function IssueExplorerContent() {
  const [params, setParams] = useSearchParams();
  const drawers = useDrawers();
  const [repoId, setRepoId] = useState(params.get("repo_id") ?? "");
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [skip, setSkip] = useState(0);

  const [repos, setRepos] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState(null);

  useEffect(() => {
    setRepoId(params.get("repo_id") ?? "");
    setSearch(params.get("search") ?? "");
    setSkip(0);
  }, [params]);

  useEffect(() => {
    const open = params.get("open");
    if (open) {
      drawers.openIssue(open);
      const next = new URLSearchParams(params);
      next.delete("open");
      setParams(next, { replace: true });
    }
  }, [params]);

  useEffect(() => {
    api.repositories().then((list) => {
      if (Array.isArray(list) && list.length > 0) setRepos(list);
    }).catch(() => {});
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await api.syncIssues(repoId || undefined);
      q.refetch();
      api.repositories().then((list) => { if (Array.isArray(list)) setRepos(list); });
      setSyncMsg(res?.message ? `${res.message} (${res.synced_count || 0} synced)` : "GitHub issues synced.");
    } catch (e) {
      setSyncMsg(e?.detail || e?.message || "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  const q = useData(
    () =>
      api.issues({
        repo_id: repoId || undefined,
        search: search || undefined,
        skip,
        limit: PAGE_SIZE,
      }),
    [repoId, search, skip],
    { pollMs: 45000 },
  );

  const data = q.data;
  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const activeRepo = repos.find((r) => String(r.id) === String(repoId));

  return (
    <>
      <PageHeader
        eyebrow="Contribute"
        title={activeRepo ? `Issues · ${activeRepo.name}` : "Issue Explorer"}
        subtitle={activeRepo ? `Showing all open issues for ${activeRepo.name}` : "Explore all open issues across your repositories."}
        sticker={`${total} issues`}
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleSync}
              disabled={syncing}
              className="border-2 border-ink bg-gyellow px-3 py-1.5 font-mono text-xs font-bold uppercase shadow-[2px_2px_0_0_#101010] hover:-translate-y-0.5 disabled:opacity-50"
            >
              {syncing ? "Syncing..." : "Sync from GitHub ↻"}
            </button>
            <UpdatedPill lastUpdated={q.lastUpdated} />
          </div>
        }
      />

      {syncMsg && (
        <div className="mb-4 border-2 border-ink bg-gyellow-light p-3 font-mono text-xs font-bold">
          {syncMsg}
        </div>
      )}

      {/* Clean search bar */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 font-mono text-sm text-ink-soft">⌕</span>
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setSkip(0);
              const next = new URLSearchParams(params);
              if (e.target.value) next.set("search", e.target.value);
              else next.delete("search");
              setParams(next, { replace: true });
            }}
            placeholder="Search issues by title..."
            className="w-full border-[3px] border-ink bg-white py-2.5 pl-9 pr-4 font-sans text-sm shadow-[3px_3px_0_0_#101010] focus:outline-none"
          />
        </div>
        {repoId && (
          <button
            onClick={() => {
              setRepoId("");
              const next = new URLSearchParams(params);
              next.delete("repo_id");
              setParams(next, { replace: true });
            }}
            className="border-2 border-ink bg-paper-2 px-3 py-2 font-mono text-xs font-bold uppercase hover:bg-gyellow-light"
          >
            Show all repos ✕
          </button>
        )}
      </div>

      {q.loading && (
        <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => <IssueCardSkeleton key={i} />)}
        </div>
      )}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {data && (data.items || []).length === 0 && (
        <EmptyState
          title="No issues available"
          body={activeRepo ? `No open issues found for ${activeRepo.name}.` : "There are currently no open issues in the platform."}
          action={
            <Button
              variant="paper"
              onClick={() => {
                setSearch("");
                setRepoId("");
                setParams(new URLSearchParams(), { replace: true });
              }}
            >
              Clear search
            </Button>
          }
        />
      )}

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {(data?.items || []).map((i) => (
          <IssueCard key={i.id} issue={i} />
        ))}
      </div>

      {data && totalPages > 1 && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPage={(p) => setSkip((p - 1) * PAGE_SIZE)}
        />
      )}

      {drawers.drawerElements}
    </>
  );
}

export default function IssueExplorer() {
  return (
    <Suspense fallback={<LoadingBlock rows={6} />}>
      <IssueExplorerContent />
    </Suspense>
  );
}
