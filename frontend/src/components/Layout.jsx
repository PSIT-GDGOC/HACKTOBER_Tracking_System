import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/utils/cn";
import { api, DEMO_MODE, tokenStore } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData, useDebounced } from "@/lib/hooks";
import { timeAgo } from "@/lib/format";
import { Avatar, Badge, Button, Field, GdgMark, Input, Modal, Panel, StatusBadge, Sticker, Toggle } from "./ui";
import { NotificationRow } from "./domain";

const NAV = [
  {
    title: "Overview", roles: ["student", "maintainer", "admin"],
    items: [
      { to: "/dashboard", label: "Dashboard", icon: "◱" },
      { to: "/dashboard/leaderboard", label: "Leaderboard", icon: "★" },
    ],
  },
  {
    title: "Contribute", roles: ["student", "maintainer", "admin"],
    items: [
      { to: "/dashboard/issues", label: "Issue explorer", icon: "⌗" },
      { to: "/dashboard/repos", label: "Repository hub", icon: "▤" },
      { to: "/dashboard/pulls", label: "Pull requests", icon: "⑂" },
      { to: "/dashboard/commits", label: "Commits", icon: "◧" },
    ],
  },
  {
    title: "My account", roles: ["student", "maintainer", "admin"],
    items: [
      { to: "/dashboard/profile", label: "My profile", icon: "✎" },
    ],
  },
  {
    title: "Maintainer", roles: ["maintainer", "admin"],
    items: [
      { to: "/dashboard/maintainer", label: "Review", icon: "✓" },
    ],
  },
  {
    title: "Admin", roles: ["admin"],
    items: [
      { to: "/dashboard/admin", label: "Admin console", icon: "◧" },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Command-palette global search (⌘K / Ctrl-K, not a page)            */
/* ------------------------------------------------------------------ */

const SEARCH_KEYS = ["issues", "pull_requests", "contributors", "repositories", "commits"];
const SEARCH_LABEL = {
  issues: "Issues", pull_requests: "Pull requests", contributors: "Contributors",
  repositories: "Repositories", commits: "Commits",
};

function CommandPalette({ open, onClose }) {
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 250);
  const nav = useNavigate();
  const state = useData(() => api.search(dq), [dq], { enabled: open && dq.trim().length > 1 });
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 30);
    else setQ("");
  }, [open]);

  const go = (to) => {
    onClose();
    nav(to);
  };

  const r = state.data;
  return (
    <Modal open={open} onClose={onClose} title="Global search">
      <input
        ref={inputRef}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search issues, PRs, contributors, commits…"
        className="w-full border-[3px] border-ink bg-white px-3 py-2.5 font-sans text-sm focus:outline-none focus:shadow-[4px_4px_0_0_#4285F4]"
      />
      <div className="mt-3 max-h-[50vh] overflow-y-auto">
        {state.loading && <p className="p-2 font-mono text-xs uppercase text-ink-soft">Searching…</p>}
        {r && SEARCH_KEYS.map((key) => {
          const items = r[key] || [];
          if (!items.length) return null;
          return (
            <div key={key} className="mb-2">
              <p className="mb-1 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">{SEARCH_LABEL[key]}</p>
              {items.map((it, i) => (
                <button
                  key={i}
                  onClick={() =>
                    go(
                      key === "issues" ? `/dashboard/issues?open=${it.id}`
                      : key === "pull_requests" ? `/dashboard/pulls?open=${it.id}`
                      : key === "contributors" ? `/dashboard/profile/${it.id}`
                      : key === "repositories" ? `/dashboard/repos/${it.id}`
                      : "/dashboard/commits",
                    )
                  }
                  className="block w-full truncate border-b border-dashed border-paper-3 py-1.5 text-left text-sm last:border-0 hover:bg-gyellow-light"
                >
                  <span className="mr-2 font-mono text-[11px] text-ink-soft">
                    {key === "commits" ? String(it.github_commit_sha).slice(0, 7) : key === "issues" ? `#${it.github_issue_id}` : key === "pull_requests" ? `#${it.github_pr_id}` : ""}
                  </span>
                  {it.title || it.name || it.message}
                </button>
              ))}
            </div>
          );
        })}
        {r && SEARCH_KEYS.every((k) => !(r[k] || []).length) && (
          <p className="p-2 font-mono text-xs text-ink-soft">No matches. Try a different term.</p>
        )}
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/*  Notifications dropdown (panel, not a page)                         */
/* ------------------------------------------------------------------ */

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const state = useData(() => api.notifications({ limit: 10 }), [], { pollMs: 45000 });
  const unread = state.data?.unread_count ?? 0;
  const box = useRef(null);

  useEffect(() => {
    const onDoc = (e) => {
      if (box.current && !box.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="relative" ref={box}>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        className="relative flex h-10 w-10 items-center justify-center border-[3px] border-ink bg-white text-lg shadow-[3px_3px_0_0_#101010] hover:bg-gyellow-light"
      >
        🔔
        {unread > 0 && (
          <span className="absolute -right-2 -top-2 flex h-5 min-w-5 items-center justify-center border-2 border-ink bg-gred px-1 font-mono text-[10px] font-bold text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <Panel className="absolute right-0 top-12 z-50 w-[min(94vw,380px)] p-0 shadow-[8px_8px_0_0_#101010]">
          <div className="flex items-center justify-between border-b-[3px] border-ink bg-gyellow px-3 py-2">
            <p className="font-display text-sm font-extrabold uppercase">Notifications</p>
            <button
              onClick={() => api.markAllNotificationsRead().then(() => state.refetch())}
              className="border-2 border-ink bg-white px-2 py-0.5 font-mono text-[10px] font-bold uppercase hover:bg-ggreen-light"
            >
              Mark all read
            </button>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {state.loading && <p className="p-4 font-mono text-xs uppercase">Loading…</p>}
            {state.error && <p className="p-4 font-mono text-xs text-gred">{state.error}</p>}
            {state.data?.items?.slice(0, 8).map((n) => (
              <NotificationRow key={n.id} n={n} onRead={(id) => api.markNotificationRead(id).then(() => state.refetch())} />
            ))}
            {state.data && state.data.items.length === 0 && (
              <p className="p-4 font-mono text-xs text-ink-soft">No notifications yet — claims, reviews and merges will land here.</p>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Settings modal (from the account menu, not a page)                 */
/* ------------------------------------------------------------------ */

function SettingsModal({ open, onClose }) {
  const { user, logout, refreshUser } = useAuth();
  const [github, setGithub] = useState("");
  const [flash, setFlash] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open && user) setGithub(user.github_username ?? "");
  }, [open, user]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.updateMyProfile({ github_username: github.trim() });
      await refreshUser();
      setFlash("Profile saved.");
    } catch (err) {
      setFlash(err?.detail || "Could not save.");
    } finally {
      setSaving(false);
      setTimeout(() => setFlash(null), 2500);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Settings">
      <div className="space-y-5">
        <div>
          <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">Account</p>
          <dl className="space-y-1.5">
            {[
              ["Name", user?.name ?? "—"],
              ["Roll number", user?.psit_roll_no ?? "—"],
              ["Email", user?.email ?? "—"],
              ["Role", user?.role ?? "—"],
              ["Verified", user?.verified ? `yes · ${user.verification_method ?? ""}` : "no"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4 border-b border-dashed border-paper-3 pb-1">
                <dt className="font-mono text-[10px] uppercase text-ink-soft">{k}</dt>
                <dd className="text-right font-display text-sm font-bold">{v}</dd>
              </div>
            ))}
          </dl>
        </div>

        <form onSubmit={save} className="space-y-3">
          <Field label="GitHub username" hint="required for PR auto-linking">
            <Input value={github} onChange={(e) => setGithub(e.target.value)} placeholder="octocat" />
          </Field>
          <div className="flex items-center gap-3">
            <Button type="submit" variant="green" loading={saving}>Save</Button>
            {flash && <span className="font-mono text-[11px] font-bold">{flash}</span>}
          </div>
        </form>

        <div className="border-t-2 border-dashed border-paper-3 pt-4">
          <Toggle
            label="Connected to live API"
            description={DEMO_MODE
              ? "No VITE_API_BASE_URL set — set it in .env to point at the FastAPI backend."
              : "Requests go to the FastAPI backend with your Bearer token."}
            checked={!DEMO_MODE}
            onChange={() => {}}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <span className="font-mono text-[10px] uppercase text-ink-soft">
              token {tokenStore.get() ? "present" : "none"}
            </span>
            <Button variant="red" size="sm" onClick={() => { logout(); onClose(); }}>Sign out</Button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/*  AppShell                                                           */
/* ------------------------------------------------------------------ */

export function AppShell() {
  const { user } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setNavOpen(false);
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const sections = NAV.filter((s) => user && s.roles.includes(user.role));

  return (
    <div className="min-h-screen bg-paper grid-paper">
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* top bar */}
      <header className="sticky top-0 z-40 border-b-[3px] border-ink bg-white">
        <div className="mx-auto flex max-w-[1500px] items-center gap-3 px-3 py-2.5 sm:px-5">
          <button
            onClick={() => setNavOpen((o) => !o)}
            aria-label="Toggle navigation"
            className="flex h-10 w-10 shrink-0 items-center justify-center border-[3px] border-ink bg-gyellow text-lg shadow-[3px_3px_0_0_#101010] lg:hidden"
          >
            {navOpen ? "✕" : "≡"}
          </button>
          <Link to="/dashboard" className="flex shrink-0 items-center gap-2">
            <GdgMark size={30} />
            <span className="font-display text-xl font-extrabold tracking-tight">
              <span className="text-gblue">G</span><span className="text-gred">D</span><span className="text-gyellow">G</span>
            </span>
            <span className="hidden font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-ink-soft sm:inline">
              Hacktoberfest
            </span>
          </Link>
          <button
            onClick={() => setPaletteOpen(true)}
            className="ml-4 hidden items-center gap-2 border-[3px] border-ink bg-white px-3 py-2 font-mono text-[11px] font-bold uppercase text-ink-soft shadow-[3px_3px_0_0_#101010] hover:bg-gyellow-light md:flex"
          >
            ⌕ Search everything <kbd className="border-2 border-ink bg-paper-2 px-1.5 py-0.5 text-[10px]">⌘K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-2">
            <Badge tone={DEMO_MODE ? "yellow" : "green"} dot className="hidden sm:inline-flex">
              {DEMO_MODE ? "api not set" : "live api"}
            </Badge>
            <NotificationBell />
            <button
              onClick={() => setSettingsOpen(true)}
              className="hidden items-center gap-2 border-[3px] border-ink bg-white px-2 py-1.5 shadow-[3px_3px_0_0_#101010] hover:bg-gyellow-light sm:flex"
            >
              <Avatar name={user?.name} size={24} />
              <span className="leading-tight">
                <span className="block font-display text-xs font-bold">{(user?.name || "").split(" ")[0]}</span>
                <span className="block font-mono text-[9px] uppercase text-ink-soft">{user?.role}</span>
              </span>
            </button>
            <Button size="sm" variant="red" className="sm:hidden" onClick={() => setSettingsOpen(true)}>⚙</Button>
          </div>
        </div>
        <div className="border-t-2 border-dashed border-paper-3 px-3 py-2 md:hidden">
          <button
            onClick={() => setPaletteOpen(true)}
            className="w-full border-[3px] border-ink bg-white px-3 py-2 text-left font-mono text-[11px] font-bold uppercase text-ink-soft"
          >
            ⌕ Search everything…
          </button>
        </div>
      </header>

      <div className="mx-auto flex min-w-0 max-w-[1500px]">
        {/* sidebar */}
        <aside
          className={cn(
            "fixed inset-y-0 left-0 z-50 w-[272px] shrink-0 overflow-y-auto border-r-[3px] border-ink bg-white pt-3 transition-transform lg:sticky lg:top-[61px] lg:z-0 lg:h-[calc(100vh-61px)] lg:translate-x-0",
            navOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <div className="flex items-center justify-between px-3 pb-3 lg:hidden">
            <span className="font-display text-lg font-extrabold">
              <span className="text-gblue">G</span><span className="text-gred">D</span><span className="text-gyellow">G</span>
            </span>
            <button onClick={() => setNavOpen(false)} className="border-2 border-ink px-2 font-bold">✕</button>
          </div>
          {user && (
            <div className="mx-3 mb-3 flex items-center gap-2.5 border-[3px] border-ink bg-paper-2/60 p-2.5">
              <Avatar name={user.name} size={38} />
              <div className="min-w-0 leading-tight">
                <p className="truncate font-display text-sm font-extrabold">{user.name}</p>
                <p className="font-mono text-[10px] text-ink-soft">{user.psit_roll_no}</p>
                <StatusBadge status={user.verified ? user.verification_method ?? "verified" : "pending review"} className="mt-1" />
              </div>
            </div>
          )}
          <nav className="px-3 pb-6">
            {sections.map((s) => (
              <div key={s.title} className="mb-4">
                <p className="mb-1.5 px-1 font-mono text-[10px] font-bold uppercase tracking-[0.16em] text-ink-soft">{s.title}</p>
                {s.items.map((it) => (
                  <NavLink
                    key={it.to}
                    to={it.to}
                    end={it.to === "/dashboard" || it.to === "/dashboard/admin"}
                    className={({ isActive }) =>
                      cn(
                        "mb-1 flex items-center gap-2.5 border-2 border-transparent px-2 py-1.5 font-display text-sm font-bold transition-all",
                        isActive
                          ? "border-ink bg-ink text-gyellow shadow-[3px_3px_0_0_#101010]"
                          : "hover:border-ink hover:bg-gyellow-light",
                      )
                    }
                  >
                    <span className="w-4 text-center">{it.icon}</span>
                    <span className="truncate">{it.label}</span>
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
          <div className="px-3 pb-6">
            <Sticker tone="blue" rotate="-1">polling · 30s</Sticker>
          </div>
        </aside>

        {navOpen && <div className="fixed inset-0 z-40 bg-ink/50 lg:hidden" onClick={() => setNavOpen(false)} />}

        {/* content */}
        <main className="min-w-0 flex-1 px-4 py-7 sm:px-8 sm:py-9">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, actions, sticker }) {
  return (
    <div className="mb-8 border-b-[3px] border-ink pb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <p className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-ink-soft">
            {eyebrow}
          </p>
          <h1 className="font-display text-2xl font-extrabold uppercase leading-tight tracking-tight sm:text-3xl">
            {title}
            {sticker && (
              <span className="ml-3 inline-block align-middle">
                <Sticker tone="yellow" rotate="-2">{sticker}</Sticker>
              </span>
            )}
          </h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-ink-soft">{subtitle}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </div>
  );
}

export function UpdatedPill({ lastUpdated }) {
  if (!lastUpdated) return null;
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] font-bold uppercase tracking-wider text-ink-soft">
      <span className="h-2 w-2 animate-pulse rounded-full bg-ggreen" />
      synced {timeAgo(new Date(lastUpdated).toISOString())}
    </span>
  );
}
