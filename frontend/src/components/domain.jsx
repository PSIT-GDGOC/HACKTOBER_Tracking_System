import { useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";
import {
  ACTIVITY_ICON, CONTRIBUTION_FLOW, PLATFORM_LABEL, activityText, difficultyIcon,
  difficultyTone, pointsFor, statusLabel, timeAgo,
} from "@/lib/format";
import { githubIssueUrl, githubPrUrl } from "@/lib/api";
import {
  Avatar, Badge, Button, Chip, Panel, ProgressBar, Skeleton, StatusBadge,
} from "./ui";

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

export function ClaimButton({ status, points, onClaim, onRelease, pending, disabled, hint }) {
  if (status === "open")
    return (
      <div className="space-y-1.5">
        <Button variant="green" onClick={onClaim} loading={pending} disabled={disabled}>
          ⚑ Claim for {points} pts
        </Button>
        {hint && <p className="font-mono text-[10px] text-ink-soft">{hint}</p>}
      </div>
    );
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone="blue" dot>Claimed</Badge>
      {onRelease && (
        <Button variant="red" size="sm" onClick={onRelease} loading={pending}>
          Release claim
        </Button>
      )}
    </div>
  );
}

export function IssueCard({ issue, onClaim, pending, compact }) {
  const diff = difficultyTone[issue.difficulty] ?? difficultyTone.easy;
  const pts = pointsFor(issue);
  const platform = issue.repository?.platform;
  return (
    <Panel hover className="flex h-full flex-col p-4">
      <div className="mb-2.5 flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="border-2 border-ink bg-paper-2 px-2 py-0.5 font-mono text-[10px] font-bold uppercase">
            {platform ? PLATFORM_LABEL[platform] ?? platform : "issue"}
          </span>
          <span className={cn("border-2 border-ink px-2 py-0.5 font-mono text-[10px] font-bold uppercase", diff.bg)}>
            {difficultyIcon[issue.difficulty]} {issue.difficulty}
          </span>
          <StatusBadge status={issue.status} />
        </div>
        <span className="shrink-0 border-2 border-ink bg-gyellow px-2 py-0.5 font-mono text-[11px] font-bold">+{pts}</span>
      </div>

      <button
        onClick={() => window.dispatchEvent(new CustomEvent("open-issue-drawer", { detail: issue.id }))}
        className="group text-left"
      >
        <h3 className="break-words font-display text-base font-extrabold leading-snug tracking-tight group-hover:underline group-hover:decoration-gblue group-hover:decoration-2 group-hover:underline-offset-2">
          <span className="font-mono text-ink-soft">#{issue.github_issue_id}</span> {issue.title}
        </h3>
      </button>

      {!compact && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {issue.category && <Badge tone="paper">{issue.category}</Badge>}
          {(issue.tech_tags || []).slice(0, 3).map((t) => (
            <Badge key={t} tone="paper">{t}</Badge>
          ))}
          {(issue.tech_tags || []).length > 3 && <Badge tone="paper">+{issue.tech_tags.length - 3}</Badge>}
          <span className="ml-1 font-mono text-[11px] text-ink-soft">{timeAgo(issue.updated_at)}</span>
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
          <span className="font-mono text-[11px] text-ink-soft">unclaimed · first come, first served</span>
        )}
        {onClaim && (
          <ClaimButton
            status={issue.status}
            points={pts}
            pending={pending}
            onClaim={() => onClaim(issue)}
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
              <button
                onClick={() => window.dispatchEvent(new CustomEvent("open-issue-drawer", { detail: pr.linked_issue.id }))}
              >
                <Badge tone="blue">#{pr.linked_issue.github_issue_id}</Badge>
              </button>
            )}
          </div>
          <button onClick={() => window.dispatchEvent(new CustomEvent("open-pr-drawer", { detail: pr.id }))} className="group block text-left">
            <h3 className="break-words font-display text-base font-extrabold leading-snug tracking-tight group-hover:underline group-hover:decoration-gred group-hover:decoration-2 group-hover:underline-offset-2">
              <span className="font-mono text-ink-soft">#{pr.github_pr_id}</span> {pr.title}
            </h3>
          </button>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px]">
            {pr.user && <span className="font-bold">@{pr.user.github_username ?? pr.user.name}</span>}
            <span className="text-ink-soft">{timeAgo(pr.updated_at)}</span>
          </div>
        </div>
        {showContributor && pr.user && (
          <div className="flex shrink-0 items-center gap-2">
            <Avatar name={pr.user.name} size={34} />
            <div className="hidden leading-tight sm:block">
              <p className="font-display text-xs font-bold">{pr.user.name}</p>
              <p className="font-mono text-[10px] text-ink-soft">@{pr.user.github_username ?? "—"}</p>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/*  CommitRow                                                          */
/* ------------------------------------------------------------------ */

export function CommitRow({ commit }) {
  return (
    <div className="flex flex-col gap-2 border-b-2 border-dashed border-paper-3 py-3 last:border-0 sm:flex-row sm:items-center sm:gap-4">
      <a
        href={commit.repository ? `${commit.repository.github_repo_url.replace(/\/$/, "")}/commit/${commit.github_commit_sha}` : "#"}
        target="_blank"
        rel="noreferrer"
        className="shrink-0 border-2 border-ink bg-paper-2 px-2 py-1 text-center font-mono text-[11px] font-bold hover:bg-gyellow-light"
      >
        {String(commit.github_commit_sha || "").slice(0, 7)}
      </a>
      <p className="min-w-0 flex-1 break-words font-mono text-sm">{commit.message}</p>
      <div className="flex shrink-0 items-center gap-3 font-mono text-[11px]">
        {commit.user && <span className="font-bold">@{commit.user.github_username ?? commit.user.name}</span>}
        {commit.pr_id && <span className="text-ink-soft">PR #{commit.pr_id}</span>}
        <span className="text-ink-soft">{timeAgo(commit.committed_at)}</span>
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
            <span className="font-mono text-[10px] text-ink-soft">{timeAgo(e.timestamp)}</span>
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
  return (
    <Panel className="overflow-hidden">
      <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <StatusBadge status={c.status} />
            <StatusBadge status={c.validation_status} />
            {issue?.difficulty && (
              <Badge tone="yellow">+{pointsFor(issue.difficulty)} pts</Badge>
            )}
          </div>
          {issue && (
            <button
              onClick={() => window.dispatchEvent(new CustomEvent("open-issue-drawer", { detail: issue.id }))}
              className="block text-left"
            >
              <h3 className="break-words font-display text-base font-extrabold leading-snug hover:underline">
                <span className="font-mono text-ink-soft">#{issue.github_issue_id}</span> {issue.title}
              </h3>
            </button>
          )}
          <p className="mt-1.5 font-mono text-[11px] text-ink-soft">
            updated {timeAgo(c.updated_at)}
            {pr && <> · PR #{pr.github_pr_id} ({pr.status})</>}
          </p>
        </div>
        <div className="shrink-0 sm:text-right">
          <StateMachineStrip current={c.status} />
          {expandable && (c.timeline_json?.length > 0) && (
            <button
              onClick={() => setOpen((o) => !o)}
              className="mt-2 font-mono text-[11px] font-bold uppercase underline decoration-dotted"
            >
              {open ? "Hide timeline ▲" : "View timeline ▼"}
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className="border-t-[3px] border-ink bg-paper-2/40 p-4">
          <Timeline events={c.timeline_json} />
        </div>
      )}
    </Panel>
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
          {item.type?.replace(/_/g, " ")} · {timeAgo(item.created_at)}
        </p>
      </div>
    </div>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

/** Backend notification payload: { title?, message?, pr_id?, issue_id? ... } */
export function NotificationRow({ n, onRead }) {
  const p = n.payload || {};
  const tone =
    String(n.type).includes("merged") ? "bg-ggreen-light"
    : String(n.type).includes("review") ? "bg-gyellow-light"
    : "bg-white";
  return (
    <div className={cn("flex items-start gap-3 border-b-2 border-dashed border-paper-3 p-4 last:border-0", !n.read && tone)}>
      {!n.read && <span className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-gblue" />}
      <div className="min-w-0 flex-1">
        <p className="font-display text-sm font-extrabold">{p.title || statusLabel(n.type)}</p>
        <p className="mt-0.5 text-sm text-ink-soft">{p.message || p.detail || ""}</p>
        <p className="mt-1.5 font-mono text-[10px] uppercase tracking-wider text-ink-soft">
          {String(n.type).replace(/_/g, " ")} · {timeAgo(n.created_at)}
        </p>
      </div>
      {!n.read && (
        <button
          onClick={() => onRead(n.id)}
          className="shrink-0 border-2 border-ink bg-ink px-2 py-1 font-mono text-[10px] font-bold uppercase text-paper hover:bg-ggreen"
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
