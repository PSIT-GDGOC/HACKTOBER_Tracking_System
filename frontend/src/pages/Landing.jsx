/**
 * Landing — public marketing page.
 * Updated for Event Concluded & Standings Locked state.
 */
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useData } from "@/lib/hooks";
import { compact } from "@/lib/format";
import {
  Avatar, Badge, Callout, GdgMark, LinkButton, Marquee, Panel, Skeleton, Sticker, StatCard,
} from "@/components/ui";
import { LeaderboardRow } from "@/components/domain";

function scrollToSection(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const y = el.getBoundingClientRect().top + window.scrollY - 88;
  window.scrollTo({ top: y, behavior: "smooth" });
}

export default function Landing() {
  const { user } = useAuth();
  const lb = useData(() => api.leaderboard({ per_page: 5 }), []);
  const issues = useData(() => api.issues({ limit: 1 }), []);
  const userDash = useData(
    () => (user ? api.studentDashboard() : Promise.resolve(null)),
    [user?.id],
    { enabled: !!user }
  );

  const entries = lb.data?.entries ?? [];
  const totalIssues = issues.data?.total;

  return (
    <div className="min-h-screen bg-paper grid-paper">

      {/* nav */}
      <header className="sticky top-0 z-40 border-b-[3px] border-ink bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2.5">
            <GdgMark size={36} />
            <span className="leading-none">
              <span className="font-display text-2xl font-extrabold tracking-tight">
                <span className="text-gblue">G</span><span className="text-gred">D</span><span className="text-gyellow">G</span>
              </span>
              <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-ink-soft">Hacktoberfest · PSIT</span>
            </span>
          </div>
          <nav className="hidden items-center gap-5 font-display text-sm font-bold uppercase md:flex">
            {["Leaderboard", "How it worked", "FAQ"].map((l) => (
              <button
                key={l}
                onClick={() => scrollToSection(l.toLowerCase().split(" ")[0] === "leaderboard" ? "leaderboard" : l === "How it worked" ? "how" : "faq")}
                className="border-b-[3px] border-transparent pb-0.5 font-display text-sm font-bold uppercase hover:border-gblue hover:text-gblue"
              >
                {l}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2.5">
            <a
              href="https://gdgoc-community-website.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 border-[2px] border-ink bg-gyellow px-3 py-1 font-display text-xs font-bold uppercase text-ink shadow-[2px_2px_0_0_#101010] hover:-translate-y-0.5"
            >
              <span>Main Website</span>
              <span aria-hidden="true">↗</span>
            </a>
            {user ? (
              <LinkButton to="/dashboard" variant="blue" size="sm">Workspace →</LinkButton>
            ) : (
              <>
                <LinkButton to="/login" variant="paper" size="sm">Log in</LinkButton>
                <LinkButton to="/join" variant="blue" size="sm" className="hidden sm:inline-flex">Join</LinkButton>
              </>
            )}
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden border-b-[3px] border-ink">
        <div className="pointer-events-none absolute -right-24 -top-24 hidden h-72 w-72 rotate-12 border-[3px] border-ink bg-gyellow/70 lg:block" />
        <div className="relative mx-auto grid min-w-0 max-w-6xl gap-12 px-4 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:py-24">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <Sticker tone="yellow" rotate="-2">🏁 Hacktoberfest 2026 · Concluded</Sticker>
              <Badge tone="red" dot>Event Ended</Badge>
              <Badge tone="paper">Standings Locked</Badge>
            </div>
            <h1 className="font-display text-[13vw] font-extrabold uppercase leading-[0.86] tracking-tighter sm:text-6xl lg:text-7xl">
              Event
              <span className="relative mx-2 inline-block border-[3px] border-ink bg-gyellow px-3 text-ink shadow-[6px_6px_0_0_#101010]">wrapped</span>
              <br />
              Final
              <span className="ml-2 inline-block border-[3px] border-ink bg-gblue px-3 text-white shadow-[6px_6px_0_0_#101010]">standings</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
              Hacktoberfest 2026 has concluded! All issue claims and contribution scores are now
              permanently frozen. Explore final leaderboard rankings below, or visit the main GDGoC community
              platform for upcoming workshops, hackathons, and activities.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="https://gdgoc-community-website.vercel.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 border-[3px] border-ink bg-ggreen px-6 py-3 font-display text-base font-extrabold uppercase text-ink shadow-[4px_4px_0_0_#101010] transition-transform hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5 focus-visible:ring-2 focus-visible:ring-gblue"
              >
                <span>Visit GDGoC Main Website</span>
                <span aria-hidden="true">→</span>
              </a>
              {user ? (
                <LinkButton to="/dashboard" variant="paper" size="lg">
                  View Full Workspace →
                </LinkButton>
              ) : (
                <LinkButton to="/login" variant="paper" size="lg">
                  Sign in to view stats
                </LinkButton>
              )}
            </div>

            {/* personal stats if signed in */}
            {user && userDash.data && (
              <div className="mt-8 border-[3px] border-ink bg-white p-5 shadow-[5px_5px_0_0_#101010]">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-ink pb-3">
                  <div className="flex items-center gap-2.5">
                    <Avatar name={user.name} size={32} />
                    <div>
                      <p className="font-display text-sm font-extrabold uppercase text-ink">{user.name}</p>
                      <p className="font-mono text-[10px] text-ink-soft">@{user.github_username || user.email}</p>
                    </div>
                  </div>
                  <span className="border-2 border-ink bg-gyellow px-2.5 py-0.5 font-display text-xs font-bold uppercase shadow-[2px_2px_0_0_#101010]">
                    Your Final Record
                  </span>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                  <div className="border-2 border-ink bg-paper p-2">
                    <span className="block font-mono text-[9px] uppercase tracking-wider text-ink-soft">Rank</span>
                    <span className="font-display text-xl font-extrabold text-gblue">#{userDash.data.rank ?? "—"}</span>
                  </div>
                  <div className="border-2 border-ink bg-paper p-2">
                    <span className="block font-mono text-[9px] uppercase tracking-wider text-ink-soft">Final Points</span>
                    <span className="font-display text-xl font-extrabold text-ggreen">{userDash.data.total_points ?? 0}</span>
                  </div>
                  <div className="border-2 border-ink bg-paper p-2">
                    <span className="block font-mono text-[9px] uppercase tracking-wider text-ink-soft">Merged PRs</span>
                    <span className="font-display text-xl font-extrabold text-gyellow">{userDash.data.merged_prs ?? 0}</span>
                  </div>
                </div>
              </div>
            )}

            {!user && (
              <div className="mt-8 flex flex-wrap items-center gap-4">
                <div className="flex -space-x-3">
                  {entries.slice(0, 5).map((e) => (
                    <Avatar key={e.user_id} name={e.name} src={e.avatar_url} size={40} className="ring-4 ring-paper" />
                  ))}
                </div>
                {entries.length > 0 && (
                  <p className="font-mono text-[11px] font-bold uppercase leading-tight text-ink-soft">
                    <span className="text-ggreen">▲ {compact(lb.data?.total ?? entries.length)} verified contributors</span>
                    <br />
                    {compact(entries.reduce((a, e) => a + e.merged_prs, 0))} PRs merged in total
                  </p>
                )}
              </div>
            )}
          </div>

          {/* terminal card / final status */}
          <Panel className="relative self-start bg-ink text-paper">
            <div className="flex items-center gap-2 border-b-[3px] border-paper/30 px-4 py-2.5">
              <span className="h-3 w-3 border-2 border-paper bg-gred" />
              <span className="h-3 w-3 border-2 border-paper bg-gyellow" />
              <span className="h-3 w-3 border-2 border-paper bg-ggreen" />
              <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-paper/60">event_status · locked</span>
            </div>
            <div className="break-all space-y-2 p-4 font-mono text-[11px] leading-relaxed sm:text-xs">
              <p className="text-paper/50">$ gdgoc --status</p>
              <p className="text-gyellow">◆ EVENT_STATE: CONCLUDED</p>
              <p className="text-gblue">◆ ISSUE_CLAIMING: DISABLED</p>
              <p className="text-paper/80">◆ SCORE_CALCULATIONS: FROZEN</p>
              <p className="text-ggreen">◆ FINAL_LEADERBOARD: ARCHIVED</p>
              <div className="my-2 border-t border-paper/20 pt-2 text-paper/60">
                Contributions across all official repositories have been recorded. Thank you to everyone who participated!
              </div>
              <p className="text-gyellow">➜ Next destination: gdgoc-community-website.vercel.app</p>
            </div>
          </Panel>
        </div>
      </section>

      <Marquee items={[
        "🏁 Hacktoberfest 2026 Wrapped", "Scores Frozen", "Leaderboard Finalized",
        "GDGoC PSIT Chapter", "Visit Community Platform: gdgoc-community-website.vercel.app",
      ]} />

      {/* final stats */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total issues" value={totalIssues ?? "—"} sub="event archive" tone="blue" />
          <StatCard label="Ranked students" value={lb.data?.total ?? "—"} sub="final standings" tone="yellow" />
          <StatCard label="Top score" value={entries[0] ? compact(entries[0].total_points) : "—"} sub={entries[0]?.name ?? ""} tone="green" />
          <StatCard label="Total merged PRs" value={entries.length ? compact(entries.reduce((a, e) => a + e.merged_prs, 0)) : "—"} sub="by top contributors" tone="red" />
        </div>
      </section>

      {/* leaderboard */}
      <section id="leaderboard" className="scroll-mt-24 border-y-[3px] border-ink bg-gblue-light py-14">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-soft">Final Standings</p>
              <h2 className="font-display text-4xl font-extrabold uppercase leading-none tracking-tight sm:text-5xl">Top of the class</h2>
            </div>
            <span className="border-[2px] border-ink bg-gyellow px-3 py-1 font-display text-xs font-bold uppercase shadow-[2px_2px_0_0_#101010]">
              🔒 Final Results Archived
            </span>
          </div>
          <Panel className="p-0">
            {lb.loading && <div className="p-6"><Skeleton className="h-40" /></div>}
            {lb.error && <p className="p-6 font-mono text-xs text-ink-soft">Leaderboard unavailable right now — check back soon.</p>}
            {entries.map((e) => <LeaderboardRow key={e.user_id} entry={e} />)}
            {!lb.loading && !lb.error && entries.length === 0 && (
              <p className="p-6 font-mono text-xs text-ink-soft">No ranked contributors found.</p>
            )}
          </Panel>
        </div>
      </section>

      {/* faq */}
      <section id="faq" className="scroll-mt-24 mx-auto max-w-6xl px-4 py-14">
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-soft">Questions</p>
            <h2 className="font-display text-4xl font-extrabold uppercase leading-none tracking-tight">Event Wrap FAQ</h2>
            <div className="mt-6 space-y-3">
              <Callout tone="yellow" title="Has the event ended?">
                Yes! Hacktoberfest 2026 has concluded. All issue claims and point updates are locked and frozen.
              </Callout>
              <Callout tone="blue" title="Can I still claim issues?">
                No, issue claiming has been halted. Any open issues remain visible in the repository for learning purposes, but will not yield Hacktoberfest contest points.
              </Callout>
            </div>
          </div>
          <div className="space-y-3">
            {[
              ["Where can I find upcoming events?", "All future GDGoC PSIT events, study jams, and hackathons are hosted on the official platform at https://gdgoc-community-website.vercel.app/."],
              ["Will my points and merged PRs remain visible?", "Yes! Your student workspace and the final leaderboard will remain accessible as an archive of your contributions."],
              ["How do I get my participation certificate?", "Certificates and badges will be distributed according to the final standings. Check the official GDGoC community site and announcements."],
            ].map(([q, a], i) => (
              <details key={i} className="group border-[3px] border-ink bg-white shadow-[5px_5px_0_0_#101010]">
                <summary className="flex cursor-pointer items-center justify-between gap-3 border-b-0 px-4 py-3 font-display text-sm font-extrabold uppercase marker:hidden">
                  {q}
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center border-2 border-ink bg-gyellow text-xs group-open:bg-gred group-open:text-white">+</span>
                </summary>
                <p className="border-t-[3px] border-dashed border-paper-3 px-4 py-3 text-sm leading-relaxed text-ink-soft">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* cta to gdgoc platform */}
      <section className="border-t-[3px] border-ink bg-ink px-4 py-16 text-paper">
        <div className="mx-auto max-w-4xl text-center">
          <div className="mb-4 inline-flex items-center gap-2 border border-gyellow bg-gyellow/20 px-3 py-1 font-mono text-xs uppercase text-gyellow">
            <span>Official Chapter Hub</span>
          </div>
          <h2 className="font-display text-4xl font-extrabold uppercase leading-[0.9] tracking-tight sm:text-6xl">
            Continue on the<br />
            <span className="text-ggreen">GDGoC Community Platform</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-paper/70">
            Join the core GDGoC community for upcoming cloud study jams, Android sprints, campus events, and ticket registrations.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <a
              href="https://gdgoc-community-website.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 border-[3px] border-paper bg-gyellow px-6 py-3 font-display text-base font-extrabold uppercase text-ink shadow-[4px_4px_0_0_#fff] transition-transform hover:-translate-y-0.5 active:translate-x-0.5 active:translate-y-0.5"
            >
              <span>Explore GDGoC Platform</span>
              <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t-[3px] border-ink bg-paper-2 px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            GDG on Campus PSIT · Pranveer Singh Institute of Technology, Kanpur
          </p>
          <div className="flex flex-wrap items-center gap-4 font-mono text-[10px] uppercase text-ink-soft">
            <a
              href="https://gdgoc-community-website.vercel.app/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-gblue hover:underline"
            >
              GDGoC Community Site ↗
            </a>
            <Link to="/dashboard" className="hover:text-gblue">Dashboard</Link>
            <Link to="/login" className="hover:text-gblue">Log in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
