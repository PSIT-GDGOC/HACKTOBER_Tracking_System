import React from "react";

export function EventEndedBanner({ className = "" }) {
  return (
    <div
      role="banner"
      aria-label="Event Concluded Announcement"
      className={`relative z-50 border-b-[3px] border-ink bg-gyellow px-3 py-2 text-ink shadow-[0_2px_0_0_#101010] ${className}`}
    >
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-2.5 px-2">
        <div className="flex items-center gap-2 font-display text-xs sm:text-sm font-extrabold uppercase tracking-tight">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center border-2 border-ink bg-ink text-white text-[11px]">
            🏁
          </span>
          <span>
            Hacktoberfest 2026 has concluded! All issue claiming, PR tracking, and scores are finalized.
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="hidden font-mono text-[10px] font-bold uppercase text-ink/75 sm:inline">
            Official Chapter Website:
          </span>
          <a
            href="https://gdgoc-community-website.vercel.app/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 border-[2px] border-ink bg-white px-3 py-1 font-display text-xs font-bold uppercase text-ink shadow-[2px_2px_0_0_#101010] transition-transform hover:-translate-y-0.5 hover:bg-paper-2 active:translate-x-0.5 active:translate-y-0.5 focus-visible:ring-2 focus-visible:ring-gblue"
          >
            <span>Visit GDGoC Main Website</span>
            <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </div>
  );
}

export default EventEndedBanner;
