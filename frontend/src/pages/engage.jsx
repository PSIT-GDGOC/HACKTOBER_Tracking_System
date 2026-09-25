/**
 * Engagement — Leaderboard page + Activity feed panel (embedded in dashboards,
 * not a standalone route, per the consolidated IA).
 */
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData } from "@/lib/hooks";
import { compact, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Avatar, Badge, Button, EmptyState, ErrorState, LoadingBlock, Panel,
  SectionHeading, StatCard, Tabs,
} from "@/components/ui";
import { ActivityRow, LeaderboardRow } from "@/components/domain";
import { useDebounced } from "@/lib/hooks";
import { FilterBar } from "@/components/domain";

/* ================================================================== */
/*  Leaderboard                                                        */
/* ================================================================== */

export function Leaderboard() {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [platform, setPlatform] = useState("");
  const [page, setPage] = useState(1);
  const PER_PAGE = 20;
  const ds = useDebounced(search, 300);

  /** The backend ranks by points; we filter client-side by name/handle. */
  const q = useData(
    () => api.leaderboard({ page, per_page: PER_PAGE, platform: platform || undefined }),
    [page, platform],
    { pollMs: 60000 },
  );

  const entries = (q.data?.entries || []).filter((e) => {
    if (!ds.trim()) return true;
    const s = ds.toLowerCase();
    return (
      (e.name || "").toLowerCase().includes(s) ||
      (e.github_username || "").toLowerCase().includes(s)
    );
  });
  const total = q.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));
  const myEntry = entries.find((e) => user && e.user_id === user.id);

  return (
    <>
      <PageHeader
        eyebrow="Community"
        title="Leaderboard"
        subtitle="One indexed Postgres query — no cache layer, no separate data store. Points land the moment a contribution is accepted."
        sticker={myEntry ? `you're #${myEntry.rank}` : `${total} ranked`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Your rank" value={myEntry ? `#${myEntry.rank}` : "—"} sub={myEntry ? `${compact(myEntry.total_points)} points` : "claim an issue to rank"} tone="yellow" />
        <StatCard label="Leader" value={entries[0]?.name?.split(" ")[0] ?? "—"} sub={entries[0] ? `${compact(entries[0].total_points)} pts` : ""} tone="green" />
        <StatCard label="Ranked students" value={compact(total)} sub={`page ${page} of ${totalPages}`} tone="blue" />
        <StatCard label="Merged PRs" value={compact(entries.reduce((a, e) => a + e.merged_prs, 0))} sub="on this page" tone="red" />
      </div>

      <div className="mb-5">
        <Tabs
          value={platform}
          onChange={(v) => { setPlatform(v === "all" ? "" : v); setPage(1); }}
          tabs={[
            { key: "all", label: "All repos" },
            { key: "web", label: "Web App" },
            { key: "android", label: "Android App" },
          ]}
        />
      </div>

      <div className="mb-5">
        <FilterBar
          groups={[]}
          search={search}
          onSearch={setSearch}
          searchPlaceholder="Search name or GitHub handle…"
          count={entries.length}
        />
      </div>

      {q.loading && <LoadingBlock rows={8} />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {!q.loading && !q.error && entries.length === 0 && (
        <EmptyState title="No contributors match" body="Try a different name or handle." />
      )}

      {entries.length > 0 && (
        <>
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            {[entries[1], entries[0], entries[2]].filter(Boolean).map((e) => {
              const place = e.rank;
              const height = place === 1 ? "" : place === 2 ? "sm:mt-6" : "sm:mt-8";
              const colors = place === 1 ? "bg-gyellow" : place === 2 ? "bg-paper-3" : "bg-gred-light";
              return (
                <Panel key={e.user_id} className={`${colors} ${height} p-5 text-center`}>
                  <p className="font-display text-5xl leading-none">{place === 1 ? "🥇" : place === 2 ? "🥈" : "🥉"}</p>
                  <div className="mt-3 flex flex-col items-center gap-2">
                    <span className="mx-auto block">
                      <Avatar name={e.name} src={e.avatar_url} size={56} />
                    </span>
                    <span className="font-display text-base font-extrabold leading-tight">{e.name}</span>
                    <span className="font-mono text-[10px] text-ink-soft">@{e.github_username ?? "—"}</span>
                  </div>
                  <p className="mt-3 font-display text-3xl font-extrabold leading-none">{compact(e.total_points)}</p>
                  <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">points · {e.merged_prs} merged</p>
                </Panel>
              );
            })}
          </div>
          <Panel className="p-0">
            {entries.map((e) => <LeaderboardRow key={e.user_id} entry={e} me={user && e.user_id === user.id} />)}
          </Panel>
          {totalPages > 1 && (
            <div className="mt-5 flex justify-center gap-2">
              <Button size="sm" variant="paper" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Prev</Button>
              <span className="border-2 border-ink bg-white px-3 py-1.5 font-mono text-[11px] font-bold">page {page} / {totalPages}</span>
              <Button size="sm" variant="paper" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next →</Button>
            </div>
          )}
        </>
      )}
    </>
  );
}

/* ================================================================== */
/*  Activity feed panel (embedded in dashboards)                        */
/* ================================================================== */

export function ActivityPanel({ limit = 12, title = "Activity feed" }) {
  const q = useData(() => api.activity({ limit }), [], { pollMs: 20000 });
  return (
    <Panel className="p-5">
      <SectionHeading
        title={title}
        subtitle="Global event stream — claims, PRs, reviews and merges."
        action={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />
      {q.loading && <LoadingBlock rows={5} label="Loading activity" />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && (q.data.items || []).length === 0 && (
        <EmptyState title="Nothing here yet" body="Events appear the moment students start claiming and shipping." />
      )}
      <div>
        {(q.data?.items || []).map((a) => <ActivityRow key={a.id} item={a} />)}
      </div>
    </Panel>
  );
}
