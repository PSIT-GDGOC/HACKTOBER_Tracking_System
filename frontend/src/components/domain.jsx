import { useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";
import {
  ACTIVITY_ICON, CONTRIBUTION_FLOW, PLATFORM_LABEL, activityText, difficultyIcon,
  difficultyTone, pointsFor, statusLabel,
} from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { githubIssueUrl, githubPrUrl } from "@/lib/api";
import { routes } from "@/lib/routes";
import {
  Avatar, Badge, Button, Chip, Panel, ProgressBar, Skeleton, StatusBadge,
} from "./ui";
import { RelativeTime } from "./RelativeTime";

/* ------------------------------------------------------------------ */
/*  FilterBar                                                          */
/* ------------------------------------------------------------------ */

export function FilterBar({
  groups, search, onSearch, searchPlaceholder = "Search…", onReset, count,
}) {
  const [open, setOpen] = useState(false);
  const active = groups.filter((g) => g.value !== "all").length;

  return (
    <Panel className="p-3 sm:p-4">
      <div className="flex flex-wrap items-center gap-2">
        {onSearch && (
          <div className="relative min-w-[180px] flex-1">
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-sm">⌕</span>
            <input
              value={search ?? ""}
              onChange={(e) => onSearch(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full border-[3px] border-ink bg-paper-2/40 py-2 pl-8 pr-3 font-sans text-sm placeholder:text-ink-soft/60 focus:bg-white focus:outline-none focus:shadow-[4px_4px_0_0_#4285F4]"
            />
          </div>
        )}
        {groups.length > 0 && (
          <Button size="sm" variant={active ? "yellow" : "paper"} onClick={() => setOpen((o) => !o)}>
            Filters{active ? ` · ${active}` : ""} {open ? "▴" : "▾"}
          </Button>
        )}
        {onReset && (active > 0 || (search ?? "") !== "") && (
          <Button size="sm" variant="paper" onClick={onReset}>Clear</Button>
        )}
        {count !== undefined && (
          <span className="ml-auto font-mono text-[11px] font-bold uppercase text-ink-soft">
            {count} result{count === 1 ? "" : "s"}
          </span>
        )}
      </div>
      {open && (
        <div className="mt-4 grid gap-x-8 gap-y-4 border-t-2 border-dashed border-paper-3 pt-4">
          {groups.map((g) => (
            <div key={g.label}>
              <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">{g.label}</p>
              <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
                {g.options.map((o) => (
                  <Chip key={o.value} active={g.value === o.value} onClick={() => g.onChange(o.value)}>
                    {o.label}
                  </Chip>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/*  IssueCard + ClaimButton                                            */
/* ------------------------------------------------------------------ */

export function ClaimButton({
  status,
  points,
  onClaim,
  onRelease,
  pending,
  disabled,
  hint,
  isMine,
  claimedByName,
}) {
  if (isMine) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="blue" dot>CLAIMED BY YOU</Badge>
        {onRelease && (
          <Button
            variant="red"
            size="sm"
            onClick={onRelease}
            loading={pending}
            disabled={disabled || pending}
          >
            Release claim
          </Button>
        )}
      </div>
    );
  }

  if (claimedByName || status === "claimed") {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="blue" dot>
          CLAIMED BY {claimedByName ?? "ANOTHER USER"}
        </Badge>
      </div>
    );
  }

  if (status === "open") {
    return (
      <div className="space-y-1.5">
        <Button
          variant="green"
          onClick={onClaim}
          loading={pending}
          disabled={disabled || pending}
        >
          ⚑ Claim Issue
        </Button>
        {hint && <p className="font-mono text-[10px] text-ink-soft">{hint}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="paper">{statusLabel(status)}</Badge>
    </div>
  );
}

export function IssueCard({ issue, onClaim, onRelease, pending, compact }) {
  const { user } = useAuth();
  const repoName = issue.repository?.name;
  const isMine = !!(
    issue.active_claim &&
    user &&
    String(issue.active_claim.user_id) === String(user.id)
  );
  const claimedByName = issue.active_claim?.user?.name;

  return (
    <Panel hover className="flex h-full flex-col p-4">
      <div className="mb-2.5 flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          {repoName && (
            <span className="border-2 border-ink bg-gyellow px-2 py-0.5 font-mono text-[10px] font-bold uppercase">
              {repoName}
            </span>
          )}
          <StatusBadge status={issue.status} />
        </div>
      </div>

      <Link
        to={routes.issue(issue.id)}
        className="group block text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gblue"
      >
        <h3 className="break-words font-display text-base font-extrabold leading-snug tracking-tight group-hover:underline group-hover:decoration-gblue group-hover:decoration-2 group-hover:underline-offset-2">
          <span className="font-mono text-ink-soft">#{issue.github_issue_id}</span> {issue.title}
        </h3>
      </Link>

      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[11px] text-ink-soft">
            <RelativeTime date={issue.updated_at} prefix="updated " />
          </span>
        </div>
      )}

      <div className="mt-auto flex items-end justify-between gap-3 pt-4">
        {issue.active_claim?.user ? (
          <div className="flex items-center gap-2">
            <Avatar name={issue.active_claim.user.name} size={28} />
            <div className="leading-tight">
              <p className="font-display text-xs font-bold">{issue.active_claim.user.name}</p>
              <p className="font-mono text-[10px] text-ink-soft">{issue.active_claim.user.psit_roll_no}</p>
            </div>
          </div>
        ) : (
          <span className="font-mono text-[11px] text-ink-soft">unclaimed</span>
        )}
        {onClaim && (
          <ClaimButton
            status={issue.status}
            points={pointsFor(issue.difficulty)}
            pending={pending}
            disabled={pending || (issue.active_claim && !isMine)}
            isMine={isMine}
            claimedByName={claimedByName}
            onClaim={() => onClaim(issue)}
            onRelease={onRelease ? () => onRelease(issue) : undefined}
          />
        )}
      </div>
    </Panel>
  );
}

export function IssueCardSkeleton() {
  return (
    <Panel className="h-full p-4">
      <div className="mb-3 flex gap-2">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
      </div>
      <Skeleton className="h-5 w-full" />
      <Skeleton className="mt-2 h-5 w-3/4" />
      <div className="mt-4 flex justify-between">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-9 w-28" />
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/*  PRCard                                                             */
/* ------------------------------------------------------------------ */

export function PRCard({ pr, showContributor = true }) {
  const stateTone =
    pr.status === "merged" ? "bg-ggreen text-white"
    : pr.status === "open" ? "bg-gblue text-white"
    : pr.status === "draft" ? "bg-gyellow text-ink"
    : "bg-paper-3 text-ink";
  const platform = pr.repository?.platform;
  const prGithubUrl = githubPrUrl(pr.repository, pr);

  return (
    <Panel hover className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className={cn("border-2 border-ink px-2 py-0.5 font-mono text-[10px] font-bold uppercase", stateTone)}>
              {pr.status}
            </span>
            {platform && (
              <span className="border-2 border-ink bg-paper-2 px-2 py-0.5 font-mono text-[10px] font-bold uppercase">
                {PLATFORM_LABEL[platform] ?? platform}
              </span>
            )}
            {pr.linked_issue && (
              <Link
                to={routes.issue(pr.linked_issue.id)}
                className="inline-block transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gblue"
              >
                <Badge tone="blue">Linked Issue #{pr.linked_issue.github_issue_id}</Badge>
              </Link>
            )}
            {prGithubUrl && (
              <a
                href={prGithubUrl}
                target="_blank"
                rel="noreferrer"
                className="font-mono text-[10px] font-bold uppercase text-gblue underline decoration-dotted hover:text-ink"
              >
                GitHub PR ↗
              </a>
            )}
          </div>
          <button onClick={() => window.dispatchEvent(new CustomEvent("open-pr-drawer", { detail: pr.id }))} className="group block text-left">
            <h3 className="break-words font-display text-base font-extrabold leading-snug tracking-tight group-hover:underline group-hover:decoration-gred group-hover:decoration-2 group-hover:underline-offset-2">
              <span className="font-mono text-ink-soft">#{pr.github_pr_id}</span> {pr.title}
            </h3>
          </button>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
            {pr.user ? (
              <Link to={`/dashboard/profile/${pr.user.id}`} className="font-bold text-ink hover:underline decoration-gblue">
                @{pr.user.github_username ?? pr.user.name} ({pr.user.name})
              </Link>
            ) : (
              <span className="text-ink-soft">GitHub Contributor</span>
            )}
            <span className="text-ink-soft">
              <RelativeTime date={pr.updated_at} prefix="updated " />
            </span>
          </div>
        </div>
        {showContributor && pr.user && (
          <Link to={`/dashboard/profile/${pr.user.id}`} className="flex shrink-0 items-center gap-2 hover:opacity-80">
            <Avatar name={pr.user.name} size={34} />
            <div className="hidden leading-tight sm:block">
              <p className="font-display text-xs font-bold">{pr.user.name}</p>
              <p className="font-mono text-[10px] text-ink-soft">@{pr.user.github_username ?? "—"}</p>
            </div>
          </Link>
        )}
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/*  CommitRow                                                          */
/* ------------------------------------------------------------------ */

export function CommitRow({ commit }) {
  const commitUrl = commit.repository
    ? `${commit.repository.github_repo_url.replace(/\/$/, "")}/commit/${commit.github_commit_sha}`
    : null;

  return (
    <div className="flex flex-col gap-2 border-b-2 border-dashed border-paper-3 py-3 last:border-0 sm:flex-row sm:items-center sm:gap-4">
      <div className="flex items-center gap-2 shrink-0">
        {commit.user ? (
          <Link to={`/dashboard/profile/${commit.user.id}`} title={`View ${commit.user.name}'s profile`}>
            <Avatar name={commit.user.name} size={28} />
          </Link>
        ) : (
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-paper-3 font-mono text-xs font-bold border-2 border-ink">
            ⚙
          </span>
        )}
        {commitUrl ? (
          <a
            href={commitUrl}
            target="_blank"
            rel="noreferrer"
            className="border-2 border-ink bg-paper-2 px-2 py-1 text-center font-mono text-[11px] font-bold hover:bg-gyellow-light"
            title="View commit on GitHub"
          >
            {String(commit.github_commit_sha || "").slice(0, 7)} ↗
          </a>
        ) : (
          <span className="border-2 border-ink bg-paper-2 px-2 py-1 text-center font-mono text-[11px] font-bold">
            {String(commit.github_commit_sha || "").slice(0, 7)}
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <p className="break-words font-mono text-sm font-bold text-ink">{commit.message}</p>
        {commit.repository && (
          <p className="font-mono text-[10px] uppercase text-ink-soft">
            {commit.repository.name}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3 font-mono text-[11px]">
        {commit.user ? (
          <Link
            to={`/dashboard/profile/${commit.user.id}`}
            className="font-bold text-ink hover:underline decoration-gblue"
          >
            @{commit.user.github_username ?? commit.user.name}
          </Link>
        ) : (
          <span className="text-ink-soft">GitHub User</span>
        )}
        {commit.pr_id && (
          <span className="border border-ink bg-gyellow/30 px-1.5 py-0.5 text-[10px] font-bold">
            PR #{commit.pr_id}
          </span>
        )}
        <span className="text-ink-soft">
          <RelativeTime date={commit.committed_at} />
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Timeline (contribution timeline_json)                              */
/* ------------------------------------------------------------------ */

const EVENT_TONE = {
  claimed: "bg-gblue", in_progress: "bg-gblue", pr_submitted: "bg-gpurple",
  under_review: "bg-gyellow", changes_requested: "bg-gred", accepted: "bg-ggreen",
  merged: "bg-ggreen", released: "bg-paper-3",
};

export function Timeline({ events }) {
  if (!events?.length) return <p className="font-mono text-xs text-ink-soft">No events recorded yet.</p>;
  return (
    <ol className="relative ml-3 border-l-[3px] border-ink pl-6">
      {events.map((e, i) => (
        <li key={i} className="relative pb-6 last:pb-0">
          <span
            className={cn(
              "absolute -left-[34px] top-0.5 flex h-5 w-5 items-center justify-center rounded-full border-[3px] border-ink",
              EVENT_TONE[e.status] ?? "bg-paper-3",
            )}
          />
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display text-sm font-extrabold uppercase tracking-tight">{statusLabel(e.status)}</p>
            <span className="font-mono text-[10px] text-ink-soft">
              <RelativeTime date={e.timestamp} />
            </span>
          </div>
          {e.detail && <p className="mt-0.5 text-sm text-ink-soft">{e.detail}</p>}
          <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-ink-soft/70">
            ↳ step {i + 1}/{events.length}
          </p>
        </li>
      ))}
    </ol>
  );
}

/* ------------------------------------------------------------------ */
/*  Contribution state machine strip                                   */
/* ------------------------------------------------------------------ */

export function StateMachineStrip({ current }) {
  const activeIdx = CONTRIBUTION_FLOW.indexOf(current);
  return (
    <div className="no-scrollbar flex gap-1.5 overflow-x-auto pb-1">
      {CONTRIBUTION_FLOW.map((s, i) => (
        <div
          key={s}
          className={cn(
            "shrink-0 whitespace-nowrap border-2 border-ink px-2 py-1 font-mono text-[9px] font-bold uppercase tracking-wider",
            i < activeIdx ? "bg-ggreen-light" : i === activeIdx ? "bg-ink text-paper" : "bg-paper-2 opacity-60",
          )}
        >
          {s.replace(/_/g, " ")}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Contribution card                                                  */
/* ------------------------------------------------------------------ */

export function ContributionCard({ c, expandable = true }) {
  const [open, setOpen] = useState(false);
  const issue = c.issue;
  const pr = c.pull_request;
  const issueId = issue?.id ?? c.issue_id;
  const issueUrl = issueId ? routes.issue(issueId) : "/dashboard/issues";
  const issueNum = issue?.github_issue_id ?? issue?.number ?? c.issue_id;
  const issueTitle = issue?.title || "Untitled Issue";

  return (
    <div className="border-[3px] border-ink bg-white shadow-[5px_5px_0_0_#101010] transition-all hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[7px_7px_0_0_#101010]">
      <Link
        to={issueUrl}
        className="group block p-4 focus-visible:ring-2 focus-visible:ring-gblue focus-visible:outline-none"
      >
        {/* Header row: flex flex-wrap items-center gap-x-2 gap-y-1.5 with chips shrink-0 whitespace-nowrap and relative time pushed right */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
          <StatusBadge status={c.status} className="shrink-0 whitespace-nowrap" />
          <StatusBadge status={c.validation_status} className="shrink-0 whitespace-nowrap" />
          {issue?.difficulty && (
            <Badge tone="yellow" className="shrink-0 whitespace-nowrap">
              +{pointsFor(issue.difficulty)} pts
            </Badge>
          )}
          <span className="ml-auto font-mono text-[11px] text-ink-soft shrink-0 whitespace-nowrap">
            <RelativeTime date={c.updated_at} prefix="updated " />
          </span>
        </div>

        {/* Title below in ONE flowing paragraph with min-w-0 break-words, issue number inline before the title */}
        <p className="mt-2 min-w-0 break-words font-display text-base font-extrabold leading-snug tracking-tight text-ink group-hover:underline group-hover:decoration-gblue group-hover:decoration-2">
          {issueNum && <span className="font-mono text-ink-soft mr-1.5">#{issueNum}</span>}
          {issueTitle}
        </p>

        {pr && (
          <p className="mt-1.5 font-mono text-[11px] text-ink-soft">
            PR #{pr.github_pr_id || pr.number || pr.id} ({pr.status})
          </p>
        )}
      </Link>

      <div className="border-t-2 border-dashed border-paper-3 px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 min-w-0">
        <div className="min-w-0 flex-1 overflow-x-auto no-scrollbar">
          <StateMachineStrip current={c.status} />
        </div>
        {expandable && Array.isArray(c.timeline_json) && c.timeline_json.length > 0 && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setOpen((o) => !o);
            }}
            className="shrink-0 font-mono text-[11px] font-bold uppercase underline decoration-dotted hover:text-gblue"
          >
            {open ? "Hide timeline ▲" : "View timeline ▼"}
          </button>
        )}
      </div>

      {open && (
        <div className="border-t-[3px] border-ink bg-paper-2/40 p-4">
          <Timeline events={c.timeline_json} />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Activity + notification rows                                       */
/* ------------------------------------------------------------------ */

export function ActivityRow({ item }) {
  const to =
    item.target?.type === "issue" ? `/dashboard/issues?open=${item.target.id}`
    : item.target?.type === "pull_request" ? `/dashboard/pulls?open=${item.target.id}`
    : item.target?.type === "repository" ? `/dashboard/repos/${item.target.id}`
    : null;
  const body = (
    <div className="flex items-start gap-3 border-b-2 border-dashed border-paper-3 py-3 last:border-0">
      <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center border-2 border-ink bg-white text-sm">
        {ACTIVITY_ICON[item.type] ?? "•"}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm leading-snug">{activityText(item)}</p>
        {item.target?.title && (
          <p className="mt-0.5 truncate font-display text-xs font-bold">{item.target.title}</p>
        )}
        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
          {item.type?.replace(/_/g, " ")} · <RelativeTime date={item.created_at} />
        </p>
      </div>
    </div>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

/** Backend notification payload: { title?, message?, pr_id?, issue_id? ... } */
export function NotificationRow({ n, onRead, onClick }) {
  const p = n.payload || {};
  const tone =
    String(n.type).includes("merged") ? "bg-ggreen-light"
    : String(n.type).includes("review") ? "bg-gyellow-light"
    : "bg-white";
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onClick && onClick(n)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick && onClick(n);
        }
      }}
      className={cn(
        "flex cursor-pointer items-start gap-3 border-b-2 border-dashed border-paper-3 p-4 transition-colors last:border-0 hover:bg-gyellow-light/70 focus-visible:ring-2 focus-visible:ring-gblue focus-visible:outline-none",
        !n.read && tone,
      )}
    >
      {!n.read && <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-gblue" aria-label="Unread" />}
      <div className="min-w-0 flex-1">
        <p className="font-display text-sm font-extrabold">{p.title || statusLabel(n.type)}</p>
        <p className="mt-0.5 text-sm text-ink-soft">{p.message || p.detail || ""}</p>
        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
          {String(n.type).replace(/_/g, " ")} · <RelativeTime date={n.created_at} />
        </p>
      </div>
      {!n.read && onRead && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRead(n.id);
          }}
          className="shrink-0 border-2 border-ink bg-ink px-2 py-1 font-mono text-[10px] font-bold uppercase text-paper hover:bg-ggreen focus-visible:ring-2 focus-visible:ring-gblue"
          aria-label="Mark as read"
        >
          Read
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Leaderboard row                                                    */
/* ------------------------------------------------------------------ */

export function LeaderboardRow({ entry, me = false }) {
  const tone = entry.rank === 1 ? "bg-gyellow" : entry.rank === 2 ? "bg-paper-3" : entry.rank === 3 ? "bg-gred-light" : "bg-white";
  return (
    <Link to={`/dashboard/profile/${entry.user_id}`} className="block">
      <div className={cn("flex items-center gap-3 border-b-2 border-dashed border-paper-3 px-3 py-3 transition-colors last:border-0 hover:bg-gyellow-light sm:gap-4", tone, me && "bg-gblue-light hover:bg-gblue-light")}>
        <span className="w-7 shrink-0 text-center font-display text-base font-extrabold">{entry.rank}</span>
        <Avatar name={entry.name} src={entry.avatar_url} size={38} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-display text-sm font-extrabold">
            {entry.name} {me && <span className="font-mono text-[10px] uppercase text-gblue">· you</span>}
          </p>
          <p className="truncate font-mono text-[10px] text-ink-soft">
            @{entry.github_username ?? "—"} · {entry.merged_prs} merged · {entry.valid_contributions} valid
          </p>
        </div>
        <div className="hidden shrink-0 gap-4 font-mono text-[11px] sm:flex">
          <span title="Claimed issues"><b className="text-gblue">{entry.claimed_issues}</b> claims</span>
        </div>
        <span className="shrink-0 border-2 border-ink bg-ink px-2.5 py-1 font-mono text-xs font-bold text-gyellow">
          {entry.total_points}
        </span>
      </div>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/*  Repo card (from a RepositoryBrief)                                 */
/* ------------------------------------------------------------------ */

export function RepoCard({ repo }) {
  return (
    <Panel hover className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="inline-block border-2 border-ink bg-gblue px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-white">
            {PLATFORM_LABEL[repo.platform] ?? repo.platform}
          </span>
          <h3 className="mt-2 font-display text-lg font-extrabold tracking-tight">{repo.name}</h3>
        </div>
      </div>
      <a
        href={repo.github_repo_url}
        target="_blank"
        rel="noreferrer"
        className="mt-1 break-all font-mono text-[11px] text-ink-soft underline decoration-dotted"
      >
        {repo.github_repo_url}
      </a>
      <div className="mt-auto pt-4">
        <Link
          to={`/dashboard/repos/${repo.id}`}
          className="inline-block border-2 border-ink bg-gblue px-3 py-1.5 font-display text-xs font-bold uppercase text-white shadow-[3px_3px_0_0_#101010] hover:-translate-y-0.5"
        >
          Open dashboard →
        </Link>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/*  Mini bar chart (dashboards)                                        */
/* ------------------------------------------------------------------ */

export function BarChart({ data }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="flex h-40 items-end gap-2 border-b-[3px] border-ink pb-0">
      {data.map((d, i) => (
        <div key={d.label} className="flex flex-1 flex-col items-center gap-1.5">
          <span className="font-mono text-[10px] font-bold">{d.value}</span>
          <div
            style={{ height: `${(d.value / max) * 100}%`, minHeight: 4 }}
            className={cn("w-full border-2 border-ink border-b-0", ["bg-gblue", "bg-gred", "bg-gyellow", "bg-ggreen", "bg-gpurple"][i % 5])}
          />
          <span className="font-mono text-[10px] uppercase text-ink-soft">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

export function SplitBar({ opened, merged }) {
  const total = Math.max(opened + merged, 1);
  return (
    <div>
      <div className="flex h-6 w-full overflow-hidden border-[3px] border-ink">
        <div className="bg-gblue" style={{ width: `${(opened / total) * 100}%` }} />
        <div className="bg-ggreen" style={{ width: `${(merged / total) * 100}%` }} />
      </div>
      <div className="mt-2 flex justify-between font-mono text-[10px] font-bold uppercase">
        <span>■ {opened} opened</span>
        <span>■ {merged} merged</span>
      </div>
    </div>
  );
}
