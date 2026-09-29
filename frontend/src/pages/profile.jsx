/**
 * Profile — one route, view/edit toggle; the same component powers the public
 * contributor profile at /dashboard/profile/{userId}.
 *
 *   GET   /users/me                       → UserProfileResponse (own)
 *   GET   /users/{id}                     → UserPublicProfileResponse (public)
 *   PATCH /users/me  { name?, github_username? }
 *   GET   /contributions/{user_id}        → timeline for the public view
 */
import { Suspense, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData, useMutation } from "@/lib/hooks";
import { compact, fullDate, statusLabel } from "@/lib/format";
import { routes, isValidStatus } from "@/lib/routes";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Avatar, Badge, Button, EmptyState, ErrorState, Field, Input, LinkButton,
  LoadingBlock, Panel, SectionHeading, StatCard, StatusBadge,
} from "@/components/ui";
import { ContributionCard } from "@/components/domain";
import { dedupeByIssue, computeContributionCounts } from "@/lib/contributions";
import { cn } from "@/utils/cn";

const STATUS_TABS = [
  { key: "all", label: "All" },
  { key: "claimed", label: "Claimed" },
  { key: "in_progress", label: "In progress" },
  { key: "pr_submitted", label: "PR submitted" },
  { key: "under_review", label: "Under review" },
  { key: "changes_requested", label: "Changes requested" },
  { key: "accepted", label: "Accepted" },
  { key: "merged", label: "Merged" },
];

export function ProfileContent() {
  const { userId } = useParams();
  const { user, refreshUser } = useAuth();
  const isSelf = !userId || (user && String(userId) === String(user.id));
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [flash, setFlash] = useState(null);

  const [searchParams, setSearchParams] = useSearchParams();
  const rawStatus = searchParams.get("status");
  const activeStatus = isValidStatus(rawStatus) ? rawStatus.toLowerCase() : "all";

  useEffect(() => {
    if (rawStatus !== null && !isValidStatus(rawStatus)) {
      searchParams.delete("status");
      setSearchParams(searchParams, { replace: true });
    }
  }, [rawStatus, searchParams, setSearchParams]);

  const q = useData(
    () => (isSelf ? api.myProfile() : api.publicProfile(userId)),
    [isSelf, userId],
  );
  const contribs = useData(
    () => api.userContributions(isSelf ? user.id : userId),
    [isSelf, userId],
    { enabled: !!userId || !!user },
  );
  const save = useMutation(api.updateMyProfile);

  useEffect(() => {
    if (q.data) setForm({ name: q.data.name ?? "", github_username: q.data.github_username ?? "" });
  }, [q.data]);

  const rawContributions = contribs.data?.items || [];
  const contributions = useMemo(() => dedupeByIssue(rawContributions), [rawContributions]);
  const timelineCounts = useMemo(() => computeContributionCounts(contributions), [contributions]);
  const filteredContributions = useMemo(
    () => contributions.filter((c) => activeStatus === "all" || c.status === activeStatus),
    [contributions, activeStatus],
  );

  const submit = async (e) => {
    e.preventDefault();
    const res = await save.mutate({
      name: form.name.trim(),
      github_username: form.github_username.trim().replace(/^@/, "") || undefined,
    });
    if (res) {
      await refreshUser().catch(() => {});
      setEditing(false);
      setFlash("Profile saved ✓");
      setTimeout(() => setFlash(null), 2500);
    }
  };

  if (q.loading && !q.data)
    return <><PageHeader eyebrow="Profile" title="Loading…" /><LoadingBlock rows={6} /></>;
  if (q.error || !q.data)
    return (
      <>
        <PageHeader eyebrow="Profile" title="Not found" />
        <ErrorState message={q.error ?? "Profile unavailable"} onRetry={q.refetch} />
      </>
    );

  const p = q.data;
  const mergedCount = p.merged_prs_count ?? 0;

  return (
    <>
      <PageHeader
        eyebrow={isSelf ? "My account" : "Contributor profile"}
        title={p.name}
        subtitle={
          isSelf
            ? `${p.psit_roll_no} · ${p.email}`
            : `Public contributor profile · joined ${fullDate(p.created_at)}`
        }
        sticker={p.verified ? statusLabel(p.verification_method ?? "verified") : "verification pending"}
        actions={
          isSelf ? (
            <Button variant={editing ? "paper" : "blue"} onClick={() => setEditing((v) => !v)}>
              {editing ? "Cancel" : "✎ Edit profile"}
            </Button>
          ) : undefined
        }
      />

      {flash && (
        <div className="mb-5 border-[3px] border-ink bg-ggreen-light p-3 shadow-[5px_5px_0_0_#101010]">
          <p className="font-mono text-xs">{flash}</p>
        </div>
      )}
      {save.error && <ErrorState message={save.error} />}

      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <div className="min-w-0 space-y-6">
          <Panel className="p-5">
            <div className="flex items-start gap-4">
              <Avatar name={p.name} size={76} />
              <div className="min-w-0">
                <p className="font-display text-xl font-extrabold leading-tight">{p.name}</p>
                <p className="font-mono text-xs text-ink-soft">
                  {p.github_username ? `@${p.github_username}` : "github not linked"}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone={p.verified ? "green" : "yellow"} dot>
                    {p.verified ? `verified · ${statusLabel(p.verification_method ?? "")}` : "pending verification"}
                  </Badge>
                  <StatusBadge status={p.role} />
                </div>
              </div>
            </div>

            {editing ? (
              <form onSubmit={submit} className="mt-5 space-y-4 border-t-2 border-dashed border-paper-3 pt-4">
                <Field label="Full name">
                  <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                </Field>
                <Field label="GitHub username" hint="required for PR auto-linking">
                  <Input
                    value={form.github_username}
                    onChange={(e) => setForm({ ...form, github_username: e.target.value })}
                    className="font-mono"
                  />
                </Field>
                <div className="flex flex-wrap gap-2">
                  <Button type="submit" variant="green" loading={save.pending}>Save changes</Button>
                  <Button type="button" variant="paper" onClick={() => setEditing(false)}>Discard</Button>
                </div>
                <p className="font-mono text-[10px] text-ink-soft">
                  Roll number and email come from signup and can't be edited here.
                </p>
              </form>
            ) : (
              <dl className="mt-5 space-y-1.5 border-t-2 border-dashed border-paper-3 pt-4">
                {[
                  ...(isSelf ? [["Roll number", p.psit_roll_no], ["Email", p.email]] : []),
                  ["GitHub", p.github_username ? `@${p.github_username}` : "not linked"],
                  ["Verified at", p.verified_at ? fullDate(p.verified_at) : "—"],
                  ["Member since", fullDate(p.created_at)],
                ].map(([k, v]) => (
                  <div key={k} className="flex justify-between gap-3">
                    <dt className="font-mono text-[10px] uppercase text-ink-soft">{k}</dt>
                    <dd className="text-right font-mono text-[11px] font-bold">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Panel>

          <Panel className="p-5">
            <SectionHeading title="Stats" subtitle="Computed from webhooks — read-only." />
            <div className="grid grid-cols-2 gap-3">
              <StatCard label="Contributions" value={compact(p.contributions_count ?? contributions.length)} tone="blue" to={isSelf ? routes.profile(undefined, "all") : undefined} />
              <StatCard label="Merged PRs" value={compact(mergedCount)} tone="green" to={isSelf ? routes.profile(undefined, "merged") : undefined} />
              <StatCard label="Active claims" value={p.active_claims_count ?? 0} tone="yellow" to={isSelf ? routes.issues({ status: "claimed" }) : undefined} />
              <StatCard label="Role" value={statusLabel(p.role)} tone="purple" />
            </div>
          </Panel>
        </div>

        <div className="min-w-0 space-y-6">
          <Panel className="p-5">
            <SectionHeading
              title="Contribution timeline"
              subtitle="claimed → in progress → PR → review → merged"
              action={<UpdatedPill lastUpdated={contribs.lastUpdated} />}
            />
            {contribs.loading && <LoadingBlock rows={4} />}
            {contribs.error && <ErrorState message={contribs.error} onRetry={contribs.refetch} />}
            {contribs.data && contributions.length === 0 && (
              <EmptyState
                title="No contributions yet"
                body={isSelf ? "Claim an issue to start your timeline." : "This contributor hasn't claimed an issue yet."}
                action={isSelf ? <LinkButton to="/dashboard/issues" variant="green">Browse issues</LinkButton> : undefined}
              />
            )}
            {contribs.data && contributions.length > 0 && (
              <>
                <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    ["Total", timelineCounts.total, routes.profile(userId, undefined)],
                    ["Valid", timelineCounts.valid, routes.profile(userId, undefined)],
                    ["Merged", timelineCounts.merged, routes.profile(userId, "merged")],
                    ["In progress", timelineCounts.inProgress, routes.profile(userId, "in_progress")],
                  ].map(([l, v, to]) => (
                    <Link
                      key={l}
                      to={to}
                      className="border-2 border-ink bg-paper-2/50 p-3 transition-all hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[3px_3px_0_0_#101010] focus-visible:ring-2 focus-visible:ring-gblue"
                    >
                      <p className="font-display text-2xl font-extrabold leading-none">{v}</p>
                      <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">{l}</p>
                    </Link>
                  ))}
                </div>

                <div className="min-w-0 mb-4">
                  <div
                    role="tablist"
                    aria-label="Profile contribution status tabs"
                    className="no-scrollbar flex gap-2 overflow-x-auto border-b-[3px] border-ink pb-2 scroll-smooth snap-x snap-mandatory"
                  >
                    {STATUS_TABS.map((t) => {
                      const count = timelineCounts.statusCounts[t.key] ?? (t.key === "all" ? timelineCounts.total : 0);
                      const isSelected = activeStatus === t.key;
                      return (
                        <Link
                          key={t.key}
                          role="tab"
                          id={`profile-tab-${t.key}`}
                          aria-selected={isSelected}
                          aria-controls={`profile-tabpanel-${t.key}`}
                          to={routes.profile(userId, t.key === "all" ? undefined : t.key)}
                          className={cn(
                            "shrink-0 whitespace-nowrap snap-start border-2 border-ink px-3.5 py-1.5 font-display text-xs font-bold uppercase tracking-wide transition-all focus-visible:ring-2 focus-visible:ring-gblue",
                            isSelected
                              ? "bg-ink text-gyellow shadow-[3px_3px_0_0_#101010]"
                              : "bg-white hover:bg-gyellow-light",
                          )}
                        >
                          {t.label}
                          {count > 0 ? <span className="ml-1.5 font-mono opacity-70">({count})</span> : null}
                        </Link>
                      );
                    })}
                  </div>
                </div>

                {filteredContributions.length === 0 ? (
                  <EmptyState
                    title={`No items in "${statusLabel(activeStatus)}"`}
                    body={
                      activeStatus === "all"
                        ? "No contributions available."
                        : `No contributions found with status "${statusLabel(activeStatus)}".`
                    }
                    action={
                      <LinkButton to={routes.profile(userId, undefined)} variant="paper">
                        View all contributions
                      </LinkButton>
                    }
                  />
                ) : (
                  <div
                    role="tabpanel"
                    id={`profile-tabpanel-${activeStatus}`}
                    aria-labelledby={`profile-tab-${activeStatus}`}
                    className="space-y-3"
                  >
                    {filteredContributions.map((c) => (
                      <ContributionCard key={c.id} c={c} expandable={false} />
                    ))}
                  </div>
                )}
              </>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}

export default function Profile() {
  return (
    <Suspense fallback={<LoadingBlock rows={6} />}>
      <ProfileContent />
    </Suspense>
  );
}
