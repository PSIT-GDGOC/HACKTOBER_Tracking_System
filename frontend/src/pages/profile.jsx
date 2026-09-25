/**
 * Profile — one route, view/edit toggle; the same component powers the public
 * contributor profile at /dashboard/profile/{userId}.
 *
 *   GET   /users/me                       → UserProfileResponse (own)
 *   GET   /users/{id}                     → UserPublicProfileResponse (public)
 *   PATCH /users/me  { name?, github_username? }
 *   GET   /contributions/{user_id}        → timeline for the public view
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData, useMutation } from "@/lib/hooks";
import { compact, fullDate, statusLabel, timeAgo } from "@/lib/format";
import { PageHeader, UpdatedPill } from "@/components/Layout";
import {
  Avatar, Badge, Button, EmptyState, ErrorState, Field, Input, LinkButton,
  LoadingBlock, Panel, SectionHeading, StatCard, StatusBadge,
} from "@/components/ui";
import { ContributionCard } from "@/components/domain";

export default function Profile() {
  const { userId } = useParams();
  const { user } = useAuth();
  const isSelf = !userId || (user && String(userId) === String(user.id));
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState(null);
  const [flash, setFlash] = useState(null);

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

  const submit = async (e) => {
    e.preventDefault();
    const res = await save.mutate({
      name: form.name.trim(),
      github_username: form.github_username.trim().replace(/^@/, "") || undefined,
    });
    if (res) {
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
  const contributions = contribs.data?.items || [];
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
              <StatCard label="Contributions" value={compact(p.contributions_count ?? contributions.length)} tone="blue" />
              <StatCard label="Merged PRs" value={compact(mergedCount)} tone="green" />
              <StatCard label="Active claims" value={p.active_claims_count ?? 0} tone="yellow" />
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
            {contribs.data && (
              <>
                <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    ["Total", contribs.data.total_contributions],
                    ["Valid", contribs.data.valid_contributions_count],
                    ["Merged", contribs.data.merged_count],
                    ["In progress", contribs.data.in_progress_count],
                  ].map(([l, v]) => (
                    <div key={l} className="border-2 border-ink bg-paper-2/50 p-3">
                      <p className="font-display text-2xl font-extrabold leading-none">{v}</p>
                      <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">{l}</p>
                    </div>
                  ))}
                </div>
                <div className="space-y-3">
                  {contributions.map((c) => <ContributionCard key={c.id} c={c} expandable={false} />)}
                </div>
              </>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
