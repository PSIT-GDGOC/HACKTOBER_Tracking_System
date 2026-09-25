/**
 * Admin Console — tabs: Overview / Participants / Moderation.
 * Data:
 *   GET  /dashboard/admin                       (event-wide stats)
 *   GET  /auth/pending-verifications            (manual ID-review queue)
 *   POST /auth/verify-manual/{student_id}       (approve / reject)
 *   GET  /contributions?validation_status=…     (moderation workload)
 *   PATCH /contributions/{id}/validation        (valid / duplicate / invalid / rejected)
 */
import { useState } from "react";
import { api } from "@/lib/api";
import { useData, useMutation } from "@/lib/hooks";
import { compact, fullDate, statusLabel, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Avatar, Badge, Button, Callout, EmptyState, ErrorState, Field, Input, LinkButton,
  LoadingBlock, Modal, Panel, SectionHeading, StatCard, StatusBadge, Tabs, Textarea,
} from "@/components/ui";
import { ActivityPanel } from "./engage";

export default function AdminConsole() {
  const [tab, setTab] = useState("overview");
  const q = useData(() => api.adminDashboard(), [], { pollMs: 60000 });

  if (q.loading && !q.data) return <><PageHeader eyebrow="Admin" title="Admin console" /><LoadingBlock rows={6} /></>;
  if (q.error || !q.data) return <ErrorState message={q.error ?? "Overview unavailable"} onRetry={q.refetch} />;

  const d = q.data;

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="Admin console"
        subtitle="Event-wide stats, the manual verification queue, and contribution moderation."
        sticker={`${d.total_registered_students} students`}
        actions={<UpdatedPill lastUpdated={q.lastUpdated} />}
      />

      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "participants", label: "Participants" },
          { key: "moderation", label: "Moderation" },
        ]}
      />

      <div className="mt-6">
        {tab === "overview" && <OverviewTab d={d} />}
        {tab === "participants" && <ParticipantsTab />}
        {tab === "moderation" && <ModerationTab />}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Overview                                                           */
/* ------------------------------------------------------------------ */

function OverviewTab({ d }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr]">
      <div className="min-w-0 space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Registered students" value={d.total_registered_students} sub={`${d.verified_students} verified`} tone="blue" />
          <StatCard label="Active claims" value={d.active_claims} sub={`${d.total_issues} issues · ${d.open_issues} open`} tone="yellow" />
          <StatCard label="PRs merged" value={d.total_prs_merged} sub={`of ${d.total_prs_submitted} submitted`} tone="green" />
          <StatCard label="Pending validations" value={d.pending_validations_count} sub="need a maintainer verdict" tone="red" />
        </div>

        <Panel className="p-5">
          <SectionHeading title="Repositories" subtitle="Sync health per official repo." />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead>
                <tr className="border-b-[3px] border-ink">
                  {["Repo", "Platform", "Issues", "PRs", "Commits"].map((h) => (
                    <th key={h} className="pb-2 font-mono text-[10px] uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(d.repositories_overview || []).map((r) => (
                  <tr key={r.id} className="border-b-2 border-dashed border-paper-3 last:border-0">
                    <td className="py-2.5 font-display text-sm font-bold">{r.name}</td>
                    <td className="font-mono text-xs">{statusLabel(r.platform)}</td>
                    <td className="font-mono text-xs">{r.issues_count}</td>
                    <td className="font-mono text-xs">{r.prs_count}</td>
                    <td className="font-mono text-xs">{compact(r.commits_count)}</td>
                  </tr>
                ))}
                {(d.repositories_overview || []).length === 0 && (
                  <tr><td colSpan={5} className="py-4 font-mono text-xs text-ink-soft">No repositories registered yet.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>

        <ActivityPanel title="Recent activity" limit={8} />
      </div>

      <div className="min-w-0 space-y-6">
        <Panel className="p-5">
          <SectionHeading title="Verification funnel" />
          <div className="space-y-3">
            {[
              ["Registered", d.total_registered_students, "bg-gblue"],
              ["Verified", d.verified_students, "bg-ggreen"],
              ["Pending manual review", d.pending_manual_review_students, "bg-gyellow"],
            ].map(([label, value, tone]) => (
              <div key={label}>
                <div className="mb-1 flex justify-between font-mono text-[10px] font-bold uppercase">
                  <span>{label}</span>
                  <span>{value}</span>
                </div>
                <div className="h-4 border-2 border-ink bg-paper-2">
                  <div className={`h-full ${tone}`} style={{ width: `${Math.min(100, (value / Math.max(d.total_registered_students, 1)) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel className="p-5">
          <SectionHeading title="Needs your action" />
          <div className="space-y-2">
            <LinkButton to="/dashboard/admin" variant="red" className="w-full">
              {d.pending_manual_review_students} pending ID verification
            </LinkButton>
            <LinkButton to="/dashboard/admin" variant="yellow" className="w-full">
              {d.pending_validations_count} contributions to validate
            </LinkButton>
          </div>
          <p className="mt-3 text-xs leading-relaxed text-ink-soft">
            Open the <b>Participants</b> tab for the manual verification queue, or the
            <b> Moderation</b> tab to validate contributions.
          </p>
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Participants (verification queue)                                  */
/* ------------------------------------------------------------------ */

function ParticipantsTab() {
  const [search, setSearch] = useState("");
  const q = useData(() => api.pendingVerifications({ limit: 100 }), [], { pollMs: 45000 });
  const act = useMutation(api.verifyManual);
  const [flash, setFlash] = useState(null);
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");

  const items = (q.data || []).filter((s) => {
    if (!search.trim()) return true;
    const t = search.toLowerCase();
    return (
      (s.name || "").toLowerCase().includes(t) ||
      (s.psit_roll_no || "").toLowerCase().includes(t) ||
      (s.email || "").toLowerCase().includes(t)
    );
  });

  const run = async (student, action, note) => {
    const res = await act.mutate(student.id, { action, reason: note || undefined });
    if (res) {
      setFlash(`${student.name} ${action === "approve" ? "approved ✓" : "rejected"} — verification method ${res.verification_method ?? "—"}`);
      setRejecting(null);
      q.refetch();
    } else if (act.error) {
      setFlash(act.error);
    }
  };

  return (
    <>
      {flash && (
        <div className="mb-5 border-[3px] border-ink bg-ggreen-light p-4 shadow-[5px_5px_0_0_#101010]">
          <p className="font-mono text-xs">{flash}</p>
        </div>
      )}

      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="In manual queue" value={items.length} sub="uploaded an ID, needs a human" tone="red" />
        <StatCard label="With portal data" value={items.filter((s) => s.portal_snapshot_json).length} sub="QR decoded but unmatched" tone="yellow" />
        <StatCard label="ID uploaded" value={items.filter((s) => s.id_card_image_url).length} sub="image in private storage" tone="blue" />
        <StatCard label="Total accounts" value={q.data?.length ?? 0} sub="unverified students" tone="purple" />
      </div>

      <div className="mb-5">
        <Callout tone="yellow" title="Manual review fallback">
          These students uploaded an ID card the QR/portal check couldn't auto-verify (unreadable
          code, name mismatch, or an unreachable portal). Approve or reject by hand — approving marks
          the account verified with method <b>manual</b>.
        </Callout>
      </div>

      <div className="mb-5">
        <Field label="Search">
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, roll number or email…" />
        </Field>
      </div>

      {q.loading && <LoadingBlock rows={5} label="Loading verification queue" />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && items.length === 0 && (
        <EmptyState title="Queue is clear" body="No students waiting for manual verification." />
      )}

      <div className="min-w-0 space-y-4">
        {items.map((s) => (
          <Panel key={s.id} className="p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <Avatar name={s.name} size={44} />
                <div className="min-w-0">
                  <p className="font-display text-base font-extrabold">{s.name}</p>
                  <p className="font-mono text-[11px] text-ink-soft">
                    {s.psit_roll_no} · {s.email}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    <Badge tone={s.id_card_image_url ? "green" : "red"}>ID {s.id_card_image_url ? "uploaded" : "missing"}</Badge>
                    {s.portal_snapshot_json && <Badge tone="blue" dot>portal data</Badge>}
                    <span className="font-mono text-[10px] text-ink-soft">joined {timeAgo(s.created_at)}</span>
                  </div>
                  {s.portal_snapshot_json && (
                    <p className="mt-2 font-mono text-[10px] text-ink-soft">
                      portal: {JSON.stringify(s.portal_snapshot_json).slice(0, 120)}…
                    </p>
                  )}
                </div>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button size="sm" variant="green" loading={act.pending} onClick={() => run(s, "approve")}>✓ Approve</Button>
                <Button size="sm" variant="red" onClick={() => setRejecting(s)}>✕ Reject</Button>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      <Modal open={!!rejecting} onClose={() => setRejecting(null)} title={rejecting ? `Reject ${rejecting.name}` : ""}>
        {rejecting && (
          <div className="space-y-4">
            <Field label="Reason" hint="optional, stored with the decision">
              <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. portal record doesn't match the uploaded ID" />
            </Field>
            <div className="flex gap-2">
              <Button variant="red" loading={act.pending} onClick={() => run(rejecting, "reject", reason)}>Confirm rejection</Button>
              <Button variant="paper" onClick={() => setRejecting(null)}>Cancel</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Moderation (contribution validation)                               */
/* ------------------------------------------------------------------ */

const VALIDATIONS = ["pending", "valid", "rejected", "duplicate", "invalid"];

function ModerationTab() {
  const [filter, setFilter] = useState("pending");
  const [flash, setFlash] = useState(null);
  const [note, setNote] = useState("");
  const [active, setActive] = useState(null);
  const q = useData(
    () => api.contributions({ validation_status: filter || undefined, limit: 50 }),
    [filter],
    { pollMs: 45000 },
  );
  const setValidation = useMutation(api.setContributionValidation);

  const run = async (c, validation_status, withNote = false) => {
    if (withNote) {
      setActive(c);
      return;
    }
    const res = await setValidation.mutate(c.id, { validation_status, note: undefined });
    if (res) {
      setFlash(`${statusLabel(validation_status)} recorded on contribution #${c.id}`);
      q.refetch();
    } else if (setValidation.error) {
      setFlash(setValidation.error);
    }
  };

  const runWithNote = async () => {
    const res = await setValidation.mutate(active.id, { validation_status: "rejected", note });
    if (res) {
      setFlash(`Rejected contribution #${active.id} with note.`);
      setActive(null);
      setNote("");
      q.refetch();
    } else if (setValidation.error) {
      setFlash(setValidation.error);
    }
  };

  const items = q.data || [];

  return (
    <>
      {flash && (
        <div className="mb-5 border-[3px] border-ink bg-ggreen-light p-4 shadow-[5px_5px_0_0_#101010]">
          <p className="font-mono text-xs">{flash}</p>
        </div>
      )}

      <div className="mb-5">
        <Callout tone="red" title="Moderation model">
          The duplicate detector and webhook engine mark contributions <b>pending</b> by default.
          A human decides the final validation status — nothing is auto-rejected.
        </Callout>
      </div>

      <div className="no-scrollbar mb-5 flex gap-2 overflow-x-auto border-b-[3px] border-ink pb-2">
        {VALIDATIONS.map((v) => (
          <button
            key={v}
            onClick={() => setFilter(v)}
            className={`whitespace-nowrap border-2 border-ink px-3.5 py-1.5 font-display text-xs font-bold uppercase tracking-wide ${
              filter === v ? "bg-ink text-gyellow shadow-[3px_3px_0_0_#101010]" : "bg-white hover:bg-gyellow-light"
            }`}
          >
            {statusLabel(v)}
          </button>
        ))}
      </div>

      {q.loading && <LoadingBlock rows={5} label="Loading contributions" />}
      {q.error && <ErrorState message={q.error} onRetry={q.refetch} />}
      {q.data && items.length === 0 && (
        <EmptyState title={`Nothing marked ${statusLabel(filter)}`} body="Switch tabs to see other buckets." />
      )}

      <div className="min-w-0 space-y-4">
        {items.map((c) => (
          <Panel key={c.id} className="p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={c.status} />
                  <StatusBadge status={c.validation_status} />
                  {c.issue && <Badge tone="paper">issue #{c.issue.github_issue_id}</Badge>}
                  {c.pull_request && <Badge tone="paper">PR #{c.pull_request.github_pr_id}</Badge>}
                </div>
                <p className="font-display text-base font-extrabold leading-snug">
                  {c.issue?.title ?? `Contribution #${c.id}`}
                </p>
                <p className="mt-1 font-mono text-[11px] text-ink-soft">
                  {c.user ? `${c.user.name} (${c.user.psit_roll_no})` : `user #${c.user_id}`}
                  {" · "}{timeAgo(c.updated_at)}
                  {c.timeline_json?.length ? ` · ${c.timeline_json.length} timeline events` : ""}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button size="sm" variant="green" loading={setValidation.pending} onClick={() => run(c, "valid")}>✓ Valid</Button>
                <Button size="sm" variant="yellow" loading={setValidation.pending} onClick={() => run(c, "duplicate")}>⚑ Duplicate</Button>
                <Button size="sm" variant="red" onClick={() => run(c, null, true)}>✕ Reject…</Button>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      <Modal open={!!active} onClose={() => setActive(null)} title={active ? `Reject contribution #${active.id}` : ""}>
        {active && (
          <div className="space-y-4">
            <Field label="Note" hint="stored on the contribution">
              <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Why is this contribution rejected?" />
            </Field>
            <div className="flex gap-2">
              <Button variant="red" loading={setValidation.pending} onClick={runWithNote}>Confirm rejection</Button>
              <Button variant="paper" onClick={() => setActive(null)}>Cancel</Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
