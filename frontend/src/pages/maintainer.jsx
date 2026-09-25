/**
 * Maintainer Review — tabs: Queue / History.
 * Data: GET /dashboard/maintainer → { review_queue, recently_reviewed, ... }
 */
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData } from "@/lib/hooks";
import { statusLabel, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  EmptyState, ErrorState, LoadingBlock, Panel, SectionHeading, StatCard,
  StatusBadge, Tabs, Textarea, Button, Modal, Field, Callout,
} from "@/components/ui";
import { useDrawers } from "@/components/drawers";

export default function MaintainerReview() {
  const { user } = useAuth();
  const [tab, setTab] = useState("queue");
  const q = useData(() => api.maintainerDashboard(), [], { pollMs: 25000 });
  const drawers = useDrawers();

  if (q.loading && !q.data) return <LoadingBlock rows={6} label="Loading review queue" />;
  if (q.error || !q.data) return <ErrorState message={q.error ?? "Dashboard unavailable"} onRetry={q.refetch} />;

  const d = q.data;

  return (
    <>
      <PageHeader
        eyebrow="Maintainer"
        title="Review"
        subtitle="Pull requests awaiting a verdict, plus everything you've already reviewed."
        sticker={`${d.pending_reviews_count} waiting`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "queue", label: "Queue", count: d.review_queue?.length },
          { key: "history", label: "History", count: d.recently_reviewed?.length },
        ]}
      />

      <div className="mt-6">
        {tab === "queue" ? <QueueTab d={d} /> : <HistoryTab d={d} />}
      </div>
      {drawers.drawerElements}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Queue tab                                                          */
/* ------------------------------------------------------------------ */

function QueueTab({ d }) {
  const drawers = useDrawers();
  const [active, setActive] = useState(null);
  const [note, setNote] = useState("");
  const [flash, setFlash] = useState(null);

  const items = d.review_queue || [];

  return (
    <>
      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Pending" value={d.pending_reviews_count} sub="no review yet" tone="red" />
        <StatCard label="Approved" value={d.approved_prs_count} sub="latest review approved" tone="green" />
        <StatCard label="Changes requested" value={d.changes_requested_count} sub="waiting on contributors" tone="yellow" />
        <StatCard label="In queue" value={items.length} sub="open PRs total" tone="blue" />
      </div>

      {flash && (
        <div className="mb-5 border-[3px] border-ink bg-ggreen-light p-4 shadow-[5px_5px_0_0_#101010]">
          <p className="font-mono text-xs">{flash}</p>
        </div>
      )}

      {items.length === 0 && (
        <EmptyState title="Queue is empty" body="Every submitted PR has a verdict. Go touch grass." />
      )}

      <div className="min-w-0 space-y-4">
        {items.map((item) => (
          <Panel key={item.pr_id} className="p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={item.status} />
                  <StatusBadge status={item.review_status ?? "pending_review"} />
                  <Badge tone="paper">{item.repo_name}</Badge>
                </div>
                <button
                  onClick={() => drawers.openPr(item.pr_id)}
                  className="text-left font-display text-lg font-extrabold leading-snug hover:underline"
                >
                  <span className="font-mono text-ink-soft">#{item.github_pr_id}</span> {item.title}
                </button>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px]">
                  <span className="font-bold">{item.contributor_name}</span>
                  {item.github_username && <span className="text-ink-soft">@{item.github_username}</span>}
                  <span className="text-ink-soft">submitted {timeAgo(item.created_at)}</span>
                  {item.contributor_roll_no && <span className="text-ink-soft">{item.contributor_roll_no}</span>}
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button size="sm" variant="paper" onClick={() => { setActive(item); setNote(""); }}>Review</Button>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      <ReviewModal
        active={active}
        onClose={() => setActive(null)}
        note={note}
        setNote={setNote}
        onDone={(msg) => { setFlash(msg); setActive(null); }}
      />
      {drawers.drawerElements}
    </>
  );
}

/**
 * The backend exposes review writes through the webhook path and contribution
 * status transitions (PATCH /contributions/{id}/status). For the maintainer UI
 * we surface the PR drawer for full context; direct review submissions arrive
 * from GitHub. This modal explains the flow instead of faking an endpoint.
 */
function ReviewModal({ active, onClose, note, setNote, onDone }) {
  if (!active) return null;
  return (
    <Modal open onClose={onClose} title={`Review PR #${active.github_pr_id}`}>
      <div className="min-w-0 space-y-4">
        <div className="border-[3px] border-ink bg-paper-2/50 p-3">
          <p className="font-display text-sm font-extrabold">{active.title}</p>
          <p className="mt-1 font-mono text-[11px] text-ink-soft">
            {active.contributor_name} · {active.repo_name} · submitted {timeAgo(active.created_at)}
          </p>
        </div>
        <Callout tone="blue" title="Reviews come from GitHub">
          Reviews are recorded by the webhook sync engine when a maintainer submits a
          <b> pull_request_review</b> event on GitHub — the platform mirrors that state here and
          advances the contribution pipeline automatically.
        </Callout>
        <Field label="Local note" hint="not sent to GitHub">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Keep your own notes on this PR…" />
        </Field>
        <Button variant="green" onClick={() => onDone(`Noted. The PR stays in your queue until the GitHub review lands.`)}>
          Save note &amp; close
        </Button>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/*  History tab                                                        */
/* ------------------------------------------------------------------ */

function HistoryTab({ d }) {
  const rows = d.recently_reviewed || [];
  const drawers = useDrawers();

  if (!rows.length)
    return <EmptyState title="No reviews recorded yet" body="Submit a review on GitHub and it appears here." />;

  return (
    <>
      <div className="space-y-3">
        {rows.map((r) => (
        <Panel key={r.review_id} className="p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                <StatusBadge status={r.status} />
                <Badge tone="paper">PR #{r.pr_id}</Badge>
              </div>
              <button
                onClick={() => drawers.openPr(r.pr_id)}
                className="text-left font-display text-base font-extrabold hover:underline"
              >
                {r.pr_title}
              </button>
              {r.comment && <p className="mt-1 text-sm text-ink-soft">“{r.comment}”</p>}
              <p className="mt-1 font-mono text-[11px] text-ink-soft">
                reviewed {timeAgo(r.reviewed_at)}
              </p>
            </div>
          </div>
        </Panel>
        ))}
        </div>
        {drawers.drawerElements}
      </>
  );
}
