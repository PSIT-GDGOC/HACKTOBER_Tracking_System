/**
 * Shared slide-over drawers for issue and PR details, plus a `useDrawers` hook.
 * Domain cards (IssueCard / PRCard / ContributionCard) dispatch
 * "open-issue-drawer" / "open-pr-drawer" window events; pages drop in
 * `useDrawers()` and render `drawerElements`.
 */
import { useCallback, useEffect, useState } from "react";
import { api, githubIssueUrl, githubPrUrl, pointsFor } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData, useMutation } from "@/lib/hooks";
import { fullDate, statusLabel, timeAgo } from "@/lib/format";
import { cn } from "@/utils/cn";
import { Badge, Button, Drawer, EmptyState, LoadingBlock, Panel, StatusBadge } from "./ui";

export function useDrawers() {
  const [issueId, setIssueId] = useState(null);
  const [prId, setPrId] = useState(null);

  useEffect(() => {
    const onIssue = (e) => openIssue(e.detail);
    const onPr = (e) => openPr(e.detail);
    window.addEventListener("open-issue-drawer", onIssue);
    window.addEventListener("open-pr-drawer", onPr);
    return () => {
      window.removeEventListener("open-issue-drawer", onIssue);
      window.removeEventListener("open-pr-drawer", onPr);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openIssue = useCallback((id) => {
    setPrId(null);
    setIssueId(id || null);
  }, []);
  const openPr = useCallback((id) => {
    setIssueId(null);
    setPrId(id || null);
  }, []);

  const drawerElements = (
    <>
      {issueId && <IssueDrawer issueId={issueId} onClose={() => setIssueId(null)} onOpenPr={openPr} />}
      {prId && <PRDrawer prId={prId} onClose={() => setPrId(null)} onOpenIssue={openIssue} />}
    </>
  );

  return { openIssue, openPr, drawerElements };
}

/* ------------------------------------------------------------------ */
/*  Issue detail drawer                                                */
/* ------------------------------------------------------------------ */

export function IssueDrawer({ issueId, onClose, onOpenPr }) {
  const { user } = useAuth();
  const q = useData(() => api.issue(issueId), [issueId]);
  const claim = useMutation(api.claimIssue);
  const unclaim = useMutation(api.unclaimIssue);
  const [flash, setFlash] = useState(null);

  const issue = q.data;
  const isMine = !!(issue?.active_claim && user && issue.active_claim.user_id === user.id);
  const canModerate = user?.role === "maintainer" || user?.role === "admin";

  const doClaim = async () => {
    const res = await claim.mutate(issueId);
    if (res) {
      setFlash(`Claim locked — you own this issue now. The claim is atomic, so nobody else can take it.`);
      q.refetch();
    } else if (claim.error) {
      setFlash(claim.error);
    }
  };

  const doRelease = async () => {
    const res = await unclaim.mutate(issueId);
    if (res) {
      setFlash(res.message || "Claim released.");
      q.refetch();
    } else if (unclaim.error) {
      setFlash(unclaim.error);
    }
  };

  return (
    <Drawer open onClose={onClose} title={issue ? `Issue #${issue.github_issue_id}` : "Issue"}>
      {q.loading && <LoadingBlock rows={5} label="Loading issue" />}
      {q.error && (
        <EmptyState title="Issue unavailable" body={q.error} action={<Button variant="paper" onClick={q.refetch}>Retry</Button>} />
      )}
      {issue && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-1.5">
            <StatusBadge status={issue.status} />
            <Badge tone="yellow">{issue.difficulty} · +{pointsFor(issue)} pts</Badge>
            {issue.category && <Badge tone="paper">{issue.category}</Badge>}
            {(issue.tech_tags || []).map((t) => (
              <Badge key={t} tone="paper">{t}</Badge>
            ))}
          </div>

          <h2 className="font-display text-xl font-extrabold leading-tight tracking-tight">{issue.title}</h2>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-soft">
            <span>opened {timeAgo(issue.created_at)}</span>
            <span>updated {timeAgo(issue.updated_at)}</span>
            {issue.repository && (
              <a
                href={githubIssueUrl(issue.repository, issue) ?? issue.repository.github_repo_url}
                target="_blank"
                rel="noreferrer"
                className="underline decoration-dotted"
              >
                view on GitHub ↗
              </a>
            )}
          </div>

          {issue.description && (
            <Panel className="p-4">
              <p className="mb-1 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">Description</p>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-soft">{issue.description}</p>
            </Panel>
          )}

          {(issue.labels || []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {issue.labels.map((l) => (
                <span key={l} className="border-2 border-ink bg-paper-2 px-2 py-0.5 font-mono text-[10px] font-bold">
                  {l}
                </span>
              ))}
            </div>
          )}

          {flash && (
            <div className="border-[3px] border-ink bg-gblue-light p-3">
              <p className="font-mono text-xs">{flash}</p>
            </div>
          )}

          <Panel className="p-4">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">Claim</p>
            {issue.status === "open" ? (
              <div className="mt-2">
                <Button variant="green" onClick={doClaim} loading={claim.pending}>
                  ⚑ Claim for {pointsFor(issue)} pts
                </Button>
                <p className="mt-2 font-mono text-[10px] text-ink-soft">
                  Claims are locked atomically with a database constraint — two students can never hold the same issue.
                </p>
              </div>
            ) : issue.active_claim ? (
              <div className="mt-2 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue" dot>
                    claimed by {issue.active_claim.user?.name ?? "a student"}
                  </Badge>
                  {issue.active_claim.user?.github_username && (
                    <span className="font-mono text-[10px] text-ink-soft">@{issue.active_claim.user.github_username}</span>
                  )}
                  <span className="font-mono text-[10px] text-ink-soft">{timeAgo(issue.active_claim.claimed_at)}</span>
                </div>
                {(isMine || canModerate) && (
                  <Button variant="red" size="sm" onClick={doRelease} loading={unclaim.pending}>
                    Release claim
                  </Button>
                )}
              </div>
            ) : (
              <p className="mt-2 font-mono text-xs text-ink-soft">{statusLabel(issue.status)} — not claimable right now.</p>
            )}
          </Panel>
        </div>
      )}
    </Drawer>
  );
}

/* ------------------------------------------------------------------ */
/*  PR detail drawer                                                   */
/* ------------------------------------------------------------------ */

export function PRDrawer({ prId, onClose, onOpenIssue }) {
  const q = useData(() => api.pullRequest(prId), [prId]);
  const pr = q.data;

  return (
    <Drawer open onClose={onClose} title={pr ? `PR #${pr.github_pr_id}` : "Pull request"}>
      {q.loading && <LoadingBlock rows={5} label="Loading pull request" />}
      {q.error && (
        <EmptyState title="PR unavailable" body={q.error} action={<Button variant="paper" onClick={q.refetch}>Retry</Button>} />
      )}
      {pr && (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-1.5">
            <StatusBadge status={pr.status} />
            {pr.repository && <Badge tone="paper">{pr.repository.name}</Badge>}
            <span className="font-mono text-[10px] text-ink-soft">{timeAgo(pr.created_at)}</span>
          </div>

          <h2 className="font-display text-xl font-extrabold leading-tight tracking-tight">{pr.title}</h2>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-soft">
            {pr.user && (
              <span>
                author <b className="text-ink">{pr.user.name}</b>
                {pr.user.github_username ? ` (@${pr.user.github_username})` : ""}
              </span>
            )}
            {pr.reviewer && <span>reviewer <b className="text-ink">{pr.reviewer.name}</b></span>}
          </div>

          {pr.repository && (
            <a
              href={githubPrUrl(pr.repository, pr) ?? pr.repository.github_repo_url}
              target="_blank"
              rel="noreferrer"
              className="inline-block border-2 border-ink bg-ink px-3 py-1.5 font-display text-xs font-bold uppercase text-paper shadow-[3px_3px_0_0_#101010] hover:-translate-y-0.5"
            >
              Open on GitHub ↗
            </a>
          )}

          {pr.linked_issue && (
            <Panel className="p-4">
              <p className="mb-1 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">Linked issue</p>
              <button
                onClick={() => onOpenIssue?.(pr.linked_issue.id)}
                className="text-left font-display text-sm font-bold underline decoration-gblue decoration-2 underline-offset-2"
              >
                #{pr.linked_issue.github_issue_id} — {pr.linked_issue.title}
              </button>
            </Panel>
          )}

          <Panel className="p-4">
            <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">
              Reviews ({(pr.reviews || []).length})
            </p>
            {(pr.reviews || []).length === 0 && (
              <p className="font-mono text-xs text-ink-soft">
                No reviews yet — reviews land here automatically from GitHub webhook events.
              </p>
            )}
            <div className="space-y-3">
              {(pr.reviews || []).map((r) => (
                <div key={r.id} className="border-b-2 border-dashed border-paper-3 pb-3 last:border-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={r.status} />
                    <span className="font-mono text-[10px] text-ink-soft">
                      {r.reviewer_name ? `by ${r.reviewer_name} · ` : ""}
                      {fullDate(r.reviewed_at)}
                    </span>
                  </div>
                  {r.comment && <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{r.comment}</p>}
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </Drawer>
  );
}
