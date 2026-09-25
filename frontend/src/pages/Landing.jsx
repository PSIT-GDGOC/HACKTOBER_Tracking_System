/**
 * Landing — public marketing page. Live data comes from the leaderboard and
 * issue explorer endpoints; everything else is static copy aligned with the
 * ID-card/QR verification flow (no ERP/OTP, no campus gate).
 */
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
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

const STEPS = [
  { n: "01", title: "Sign up with your roll number", body: "Name, email and your official PSIT roll number — that's all we need to create a pending account.", color: "bg-gblue" },
  { n: "02", title: "Upload your ID card", body: "The backend decodes the QR on your PSIT ID and cross-checks the portal record server-side.", color: "bg-gred" },
  { n: "03", title: "Connect GitHub & claim an issue", body: "Atomic claim-lock: one student per issue. Claims are matched to your GitHub username.", color: "bg-gyellow" },
  { n: "04", title: "Ship a pull request", body: "Webhooks stream your PRs, reviews and commits back into your contribution timeline automatically.", color: "bg-ggreen" },
];

export default function Landing() {
  const lb = useData(() => api.leaderboard({ per_page: 5 }), []);
  const issues = useData(() => api.issues({ status: "open", limit: 1 }), []);

  const entries = lb.data?.entries ?? [];
  const openIssues = issues.data?.total;

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
            {["How it works", "Leaderboard", "FAQ"].map((l) => (
              <button
                key={l}
                onClick={() => scrollToSection(l.toLowerCase().split(" ")[0] === "leaderboard" ? "leaderboard" : l === "How it works" ? "how" : "faq")}
                className="border-b-[3px] border-transparent pb-0.5 font-display text-sm font-bold uppercase hover:border-gblue hover:text-gblue"
              >
                {l}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <LinkButton to="/login" variant="paper" size="sm">Log in</LinkButton>
            <LinkButton to="/join" variant="blue" size="sm" className="hidden sm:inline-flex">Join program</LinkButton>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative overflow-hidden border-b-[3px] border-ink">
        <div className="pointer-events-none absolute -right-24 -top-24 hidden h-72 w-72 rotate-12 border-[3px] border-ink bg-gyellow/70 lg:block" />
        <div className="relative mx-auto grid min-w-0 max-w-6xl gap-12 px-4 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:py-24">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <Sticker tone="red" rotate="-2">GDGOC Hacktoberfest</Sticker>
              <Badge tone="paper" dot>PSIT students only</Badge>
            </div>
            <h1 className="font-display text-[13vw] font-extrabold uppercase leading-[0.86] tracking-tighter sm:text-6xl lg:text-7xl">
              Ship real
              <span className="relative mx-2 inline-block border-[3px] border-ink bg-gblue px-3 text-white shadow-[6px_6px_0_0_#101010]">code</span>
              <br />
              get real
              <span className="ml-2 inline-block border-[3px] border-ink bg-gyellow px-3 shadow-[6px_6px_0_0_#101010]">points</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
              Claim issues from GDGOC's official Web and Android repositories, open pull requests, and
              watch your work flow through reviews, merges and the live leaderboard — all tracked
              automatically by GitHub webhooks.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <LinkButton to="/join" variant="green" size="lg">Start contributing →</LinkButton>
              <LinkButton to="/login" variant="paper" size="lg">I have an account</LinkButton>
            </div>
            <p className="mt-4 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">
              🛡️ verified PSIT students only · ID card + QR verification
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <div className="flex -space-x-3">
                {entries.slice(0, 5).map((e) => (
                  <Avatar key={e.user_id} name={e.name} src={e.avatar_url} size={40} className="ring-4 ring-paper" />
                ))}
              </div>
              {entries.length > 0 && (
                <p className="font-mono text-[11px] font-bold uppercase leading-tight text-ink-soft">
                  <span className="text-ggreen">▲ {compact(lb.data?.total ?? entries.length)} students</span> already shipping
                  <br />
                  {compact(entries.reduce((a, e) => a + e.merged_prs, 0))} PRs merged by the top five
                </p>
              )}
            </div>
          </div>

          {/* terminal card */}
          <Panel className="relative self-start bg-ink text-paper">
            <div className="flex items-center gap-2 border-b-[3px] border-paper/30 px-4 py-2.5">
              <span className="h-3 w-3 border-2 border-paper bg-gred" />
              <span className="h-3 w-3 border-2 border-paper bg-gyellow" />
              <span className="h-3 w-3 border-2 border-paper bg-ggreen" />
              <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-paper/60">webhook · /webhooks/github</span>
            </div>
            <div className="break-all space-y-1.5 p-4 font-mono text-[11px] leading-relaxed sm:text-xs">
              <p className="text-paper/50">$ gdgoc --listen</p>
              {[
                ["claim", "#101 locked by @aarav-sharma", "text-gyellow"],
                ["pull_request", "#312 opened → auto-linked to claim", "text-gblue"],
                ["push", "a1d8e5 6 files · @aarav-sharma", "text-paper"],
                ["review", "changes requested · @maintainer", "text-gyellow"],
                ["pull_request", "#316 merged · points credited", "text-ggreen"],
                ["claim", "#208 locked by @kartik", "text-gyellow"],
              ].map(([ev, msg, tone], i) => (
                <p key={i} className="animate-rise" style={{ animationDelay: `${i * 90}ms` }}>
                  <span className="text-paper/40">{String(i + 1).padStart(2, "0")} </span>
                  <span className={tone}>◆ {ev.padEnd(14, " ")}</span>
                  <span className="text-paper/80">{msg}</span>
                </p>
              ))}
              <p className="text-ggreen">▊ webhook_jobs drained by pg_cron — no celery, no redis</p>
            </div>
          </Panel>
        </div>
      </section>

      <Marquee items={[
        "ID card + QR verification", "atomic claim locking", "github webhooks",
        "auto-linked pull requests", "postgres-backed leaderboard", "no redis · no celery",
      ]} />

      {/* live stats */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Open issues" value={openIssues ?? "—"} sub="claimable right now" tone="blue" />
          <StatCard label="Ranked students" value={lb.data?.total ?? "—"} sub="live leaderboard" tone="yellow" />
          <StatCard label="Top score" value={entries[0] ? compact(entries[0].total_points) : "—"} sub={entries[0]?.name ?? ""} tone="green" />
          <StatCard label="Merged PRs" value={entries.length ? compact(entries.reduce((a, e) => a + e.merged_prs, 0)) : "—"} sub="by the top five" tone="red" />
        </div>
      </section>

      {/* how it works */}
      <section id="how" className="scroll-mt-24 border-y-[3px] border-ink bg-white py-14">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-soft">How it works</p>
              <h2 className="font-display text-4xl font-extrabold uppercase leading-none tracking-tight sm:text-5xl">
                Four steps to your<br />first merged PR
              </h2>
            </div>
            <Sticker tone="purple" rotate="2">discover → claim → ship → merge</Sticker>
          </div>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <Panel key={s.n} hover className="relative flex h-full flex-col p-5">
                <span className={`absolute -top-4 -left-3 flex h-12 w-12 items-center justify-center border-[3px] border-ink font-display text-lg font-extrabold shadow-[4px_4px_0_0_#101010] ${s.color}`}>
                  {s.n}
                </span>
                <h3 className="mt-6 font-display text-lg font-extrabold uppercase leading-tight tracking-tight">{s.title}</h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-ink-soft">{s.body}</p>
                <div className="mt-4 h-2 w-full border-2 border-ink bg-paper-2">
                  <div className={`h-full ${s.color}`} style={{ width: `${Number(s.n) * 25}%` }} />
                </div>
              </Panel>
            ))}
          </div>
        </div>
      </section>

      {/* leaderboard */}
      <section id="leaderboard" className="scroll-mt-24 border-y-[3px] border-ink bg-gblue-light py-14">
        <div className="mx-auto max-w-6xl px-4">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-soft">Leaderboard</p>
              <h2 className="font-display text-4xl font-extrabold uppercase leading-none tracking-tight sm:text-5xl">Top of the class</h2>
            </div>
            <LinkButton to="/login" variant="ink" size="md">Log in to compete →</LinkButton>
          </div>
          <Panel className="p-0">
            {lb.loading && <div className="p-6"><Skeleton className="h-40" /></div>}
            {lb.error && <p className="p-6 font-mono text-xs text-ink-soft">Leaderboard unavailable right now — check back soon.</p>}
            {entries.map((e) => <LeaderboardRow key={e.user_id} entry={e} />)}
            {!lb.loading && !lb.error && entries.length === 0 && (
              <p className="p-6 font-mono text-xs text-ink-soft">No ranked contributors yet — be the first.</p>
            )}
          </Panel>
        </div>
      </section>

      {/* faq */}
      <section id="faq" className="scroll-mt-24 mx-auto max-w-6xl px-4 py-14">
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-ink-soft">Questions</p>
            <h2 className="font-display text-4xl font-extrabold uppercase leading-none tracking-tight">Before you ask</h2>
            <div className="mt-6 space-y-3">
              <Callout tone="blue" title="Who can join?">
                Any verified PSIT student. Verification happens by uploading a photo of your PSIT ID
                card — the backend scans the QR and cross-checks the portal record.
              </Callout>
              <Callout tone="yellow" title="What if the QR check fails?">
                Blur, glare or a name mismatch routes you to manual admin approval instead of rejection.
                You'll land on a pending screen and can keep browsing issues meanwhile.
              </Callout>
            </div>
          </div>
          <div className="space-y-3">
            {[
              ["How are points calculated?", "Points are weighted by issue difficulty in the leaderboard query: easy 20, medium 40, hard 80. They credit when a contribution is accepted or merged."],
              ["How many issues can I hold at once?", "The backend enforces a per-student cap on active claims. Release a claim if you can't finish — it goes straight back into the open pool."],
              ["Can two students claim the same issue?", "No. Claims are locked with a database-level unique constraint on active claims — the second claim attempt fails atomically."],
              ["Can I work with a friend?", "One claim per issue. Pair-program on your fork if you like, but the PR author gets the points — that's what the webhook matches on."],
              ["My PR isn't showing up?", "PRs are auto-linked by GitHub username. Make sure you linked the right account during signup — you can update it from your profile."],
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

      {/* cta */}
      <section className="border-t-[3px] border-ink bg-ink px-4 py-16 text-paper">
        <div className="mx-auto max-w-4xl text-center">
          <h2 className="font-display text-4xl font-extrabold uppercase leading-[0.9] tracking-tight sm:text-6xl">
            Your first PR is<br />
            <span className="text-ggreen">one claim away</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-paper/70">
            Verify with your ID card, link GitHub, and pick an issue that matches your stack. The rest
            is automatic.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <LinkButton to="/join" variant="yellow" size="lg">Create account</LinkButton>
            <LinkButton to="/login" variant="paper" size="lg">I already have one</LinkButton>
          </div>
        </div>
      </section>

      <footer className="border-t-[3px] border-ink bg-paper-2 px-4 py-8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
            GDG on Campus PSIT · Pranveer Singh Institute of Technology, Kanpur
          </p>
          <div className="flex flex-wrap gap-3 font-mono text-[10px] uppercase text-ink-soft">
            <Link to="/join" className="hover:text-gblue">Join</Link>
            <Link to="/login" className="hover:text-gblue">Log in</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
