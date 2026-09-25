import { useState } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/utils/cn";
import { statusLabel, statusTone } from "@/lib/format";
import gdgLogo from "@/assets/gdg-logo.png";

/* ------------------------------------------------------------------ */
/*  brand                                                              */
/* ------------------------------------------------------------------ */

const LETTERS = [
  ["G", "text-gblue"], ["D", "text-gred"], ["G", "text-gyellow"],
];

/** Official GDG code-brackets mark — transparent cutout, no white plate. */
const LOGO_ASPECT = 209 / 119;

export function GdgMark({ size = 34, className }) {
  const height = size;
  const width = Math.round(size * LOGO_ASPECT);
  return (
    <img
      src={gdgLogo}
      alt=""
      width={width}
      height={height}
      aria-hidden
      className={cn("shrink-0 object-contain", className)}
      draggable={false}
    />
  );
}

export function GoogleWordmark({ className }) {
  return (
    <span className={cn("font-display font-extrabold leading-none tracking-tight", className)}>
      {LETTERS.map(([ch, color], i) => (
        <span key={i} className={color}>{ch}</span>
      ))}
    </span>
  );
}

export function BrandLockup({ compact = false }) {
  return (
    <Link to="/" className="group flex items-center gap-2.5">
      <GdgMark size={compact ? 30 : 36} />
      <span className="leading-none">
        <GoogleWordmark className={compact ? "text-xl" : "text-2xl"} />
        <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-ink-soft">
          on Campus · PSIT
        </span>
      </span>
    </Link>
  );
}

/* ------------------------------------------------------------------ */
/*  primitives                                                         */
/* ------------------------------------------------------------------ */

const VARIANT = {
  blue: "bg-gblue text-white", red: "bg-gred text-white", yellow: "bg-gyellow text-ink",
  green: "bg-ggreen text-white", ink: "bg-ink text-paper", purple: "bg-gpurple text-white",
  paper: "bg-white text-ink",
};

export function Button({
  variant = "ink", size = "md", className, children, loading, ...rest
}) {
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2.5 text-sm", lg: "px-6 py-3.5 text-base" };
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 border-[3px] border-ink font-display font-bold uppercase tracking-wide",
        "shadow-[4px_4px_0_0_#101010] transition-all duration-100",
        "hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_#101010]",
        "active:translate-x-[3px] active:translate-y-[3px] active:shadow-none",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0",
        sizes[size], VARIANT[variant], className,
      )}
    >
      {loading && (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}

export function LinkButton({
  to, variant = "ink", size = "md", className, children,
}) {
  const sizes = { sm: "px-3 py-1.5 text-xs", md: "px-4 py-2.5 text-sm", lg: "px-6 py-3.5 text-base" };
  return (
    <Link
      to={to}
      className={cn(
        "inline-flex items-center justify-center gap-2 border-[3px] border-ink font-display font-bold uppercase tracking-wide",
        "shadow-[4px_4px_0_0_#101010] transition-all duration-100",
        "hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_#101010]",
        "active:translate-x-[3px] active:translate-y-[3px] active:shadow-none",
        sizes[size], VARIANT[variant], className,
      )}
    >
      {children}
    </Link>
  );
}

export function Panel({ className, children, hover = false, as = "div", ...rest }) {
  const Tag = as;
  return (
    <Tag
      {...rest}
      className={cn("border-[3px] border-ink bg-white shadow-[6px_6px_0_0_#101010]", hover && "brut-hover", className)}
    >
      {children}
    </Tag>
  );
}

export function Badge({ children, tone = "paper", className, dot }) {
  const tones = {
    blue: "bg-gblue-light text-ink", red: "bg-gred-light text-ink", yellow: "bg-gyellow-light text-ink",
    green: "bg-ggreen-light text-ink", purple: "bg-gpurple-light text-ink",
    ink: "bg-ink text-paper", paper: "bg-paper-2 text-ink",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border-2 border-ink px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider",
        tones[tone], className,
      )}
    >
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-ink" />}
      {children}
    </span>
  );
}

export function StatusBadge({ status, className }) {
  const t = statusTone(status);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 border-2 border-ink px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider",
        t.bg, t.text, className,
      )}
    >
      {statusLabel(status)}
    </span>
  );
}

export function Chip({ active, children, onClick, className }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "whitespace-nowrap border-2 border-ink px-3 py-1.5 font-mono text-[11px] font-bold uppercase tracking-wider transition-all",
        active
          ? "bg-ink text-paper shadow-[3px_3px_0_0_#101010]"
          : "bg-white text-ink hover:bg-gyellow-light hover:shadow-[3px_3px_0_0_#101010]",
        className,
      )}
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  form controls                                                      */
/* ------------------------------------------------------------------ */

const fieldBase =
  "w-full border-[3px] border-ink bg-white px-3.5 py-2.5 font-sans text-sm text-ink placeholder:text-ink-soft/50 focus:outline-none focus:shadow-[4px_4px_0_0_#4285F4] focus:-translate-y-0.5 transition-all";

export function Field({ label, hint, error, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="font-display text-xs font-bold uppercase tracking-wider">{label}</span>
        {hint && <span className="font-mono text-[10px] text-ink-soft">{hint}</span>}
      </span>
      {children}
      {error && <span className="mt-1 block font-mono text-[11px] font-bold text-gred">▲ {error}</span>}
    </label>
  );
}

export function Input({ className, ...rest }) {
  return <input {...rest} className={cn(fieldBase, className)} />;
}

export function Textarea({ className, ...rest }) {
  return <textarea {...rest} className={cn(fieldBase, "min-h-24 resize-y", className)} />;
}

export function Select({ className, children, ...rest }) {
  return (
    <select {...rest} className={cn(fieldBase, "cursor-pointer appearance-none pr-8", className)}>
      {children}
    </select>
  );
}

export function Toggle({ checked, onChange, label, description }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b-2 border-dashed border-paper-3 py-3 last:border-0">
      <div>
        <p className="font-display text-sm font-bold">{label}</p>
        {description && <p className="mt-0.5 max-w-md text-xs text-ink-soft">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-7 w-14 shrink-0 border-[3px] border-ink transition-colors",
          checked ? "bg-ggreen" : "bg-paper-3",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 border-2 border-ink bg-white transition-all",
            checked ? "left-[30px]" : "left-0.5",
          )}
        />
      </button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  data display                                                       */
/* ------------------------------------------------------------------ */

export function StatCard({ label, value, sub, tone = "blue" }) {
  const bar = {
    blue: "bg-gblue", red: "bg-gred", yellow: "bg-gyellow", green: "bg-ggreen",
    purple: "bg-gpurple", ink: "bg-ink", paper: "bg-paper-3",
  }[tone];
  return (
    <div className="relative overflow-hidden border-[3px] border-ink bg-white shadow-[5px_5px_0_0_#101010]">
      <div className={cn("h-2 w-full border-b-[3px] border-ink", bar)} />
      <div className="p-4">
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-ink-soft">{label}</p>
        <p className="mt-2 font-display text-2xl font-extrabold leading-none">{value}</p>
        {sub && <p className="mt-2 font-mono text-[11px] text-ink-soft">{sub}</p>}
      </div>
    </div>
  );
}

export function SectionHeading({ title, subtitle, action, id }) {
  return (
    <div id={id} className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-xl font-extrabold uppercase tracking-tight sm:text-2xl">{title}</h2>
        {subtitle && <p className="mt-0.5 max-w-2xl text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function ProgressBar({ value, tone = "bg-ggreen", className }) {
  return (
    <div className={cn("h-4 w-full border-2 border-ink bg-paper-2", className)}>
      <div className={cn("h-full border-r-2 border-ink transition-all", tone)} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
    </div>
  );
}

export function Avatar({ name, src, size = 36, className }) {
  const [broken, setBroken] = useState(false);
  const initials = String(name || "?")
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  const palette = ["bg-gblue-light", "bg-gred-light", "bg-gyellow-light", "bg-ggreen-light", "bg-gpurple-light"];
  const tone = palette[(name || "?").charCodeAt(0) % palette.length];
  const showImage = src && !broken;
  return (
    <span
      style={{ width: size, height: size, fontSize: size * 0.36 }}
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden border-[3px] border-ink font-display font-extrabold text-ink",
        showImage ? "bg-white" : tone, className,
      )}
      title={name}
    >
      {showImage ? (
        <img src={src} alt={name} onError={() => setBroken(true)} className="h-full w-full object-cover" loading="lazy" />
      ) : (
        initials
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  states                                                             */
/* ------------------------------------------------------------------ */

export function Skeleton({ className }) {
  return <div className={cn("animate-pulse border-2 border-ink bg-paper-2", className)} />;
}

export function LoadingBlock({ label = "Loading", rows = 3 }) {
  return (
    <div className="border-[3px] border-ink bg-white p-5 shadow-[6px_6px_0_0_#101010]" role="status" aria-live="polite">
      <div className="mb-4 flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-[3px] border-ink border-t-transparent" />
        {label}…
      </div>
      <div className="space-y-2.5">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={cn("h-12", i === rows - 1 ? "w-2/3" : "w-full")} />
        ))}
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="border-[3px] border-ink bg-gred-light p-6 shadow-[6px_6px_0_0_#101010]" role="alert">
      <p className="font-display text-lg font-extrabold uppercase">▲ Something broke</p>
      <p className="mt-1 font-mono text-xs leading-relaxed text-ink-soft">{message}</p>
      {onRetry && (
        <Button variant="red" size="sm" className="mt-4" onClick={onRetry}>
          Retry request
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, body, action, icon = "∅" }) {
  return (
    <div className="flex flex-col items-center justify-center border-[3px] border-dashed border-ink bg-paper-2/60 px-6 py-12 text-center">
      <span className="mb-3 flex h-14 w-14 items-center justify-center border-[3px] border-ink bg-gyellow font-display text-2xl font-extrabold shadow-[4px_4px_0_0_#101010]">
        {icon}
      </span>
      <p className="font-display text-base font-extrabold uppercase tracking-tight">{title}</p>
      {body && <p className="mt-1.5 max-w-md text-sm text-ink-soft">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  navigation helpers                                                 */
/* ------------------------------------------------------------------ */

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="no-scrollbar flex gap-2 overflow-x-auto border-b-[3px] border-ink pb-2">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            "whitespace-nowrap border-2 border-ink px-3.5 py-1.5 font-display text-xs font-bold uppercase tracking-wide transition-all",
            value === t.key ? "bg-ink text-paper shadow-[3px_3px_0_0_#101010]" : "bg-white hover:bg-gyellow-light",
          )}
        >
          {t.label}
          {t.count !== undefined && <span className="ml-1.5 font-mono opacity-70">({t.count})</span>}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ page, totalPages, onPage }) {
  if (totalPages <= 1) return null;
  const nums = Array.from({ length: totalPages }, (_, i) => i + 1).filter(
    (n) => n === 1 || n === totalPages || Math.abs(n - page) <= 1,
  );
  return (
    <nav className="mt-5 flex flex-wrap items-center justify-center gap-2" aria-label="Pagination">
      <Button size="sm" variant="paper" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Prev</Button>
      {nums.map((n, i) => (
        <span key={n} className="flex items-center gap-2">
          {i > 0 && n - nums[i - 1] > 1 && <span className="font-mono text-xs">…</span>}
          <button
            onClick={() => onPage(n)}
            aria-current={n === page ? "page" : undefined}
            className={cn(
              "h-9 w-9 border-2 border-ink font-display text-sm font-bold transition-all",
              n === page ? "bg-gblue text-white shadow-[3px_3px_0_0_#101010]" : "bg-white hover:bg-gyellow-light",
            )}
          >
            {n}
          </button>
        </span>
      ))}
      <Button size="sm" variant="paper" disabled={page >= totalPages} onClick={() => onPage(page + 1)}>Next →</Button>
    </nav>
  );
}

export function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-ink/60" onClick={onClose} aria-hidden />
      <div className={cn("relative z-10 w-full border-[4px] border-ink bg-white shadow-[10px_10px_0_0_#101010] animate-pop", wide ? "max-w-2xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b-[3px] border-ink bg-gyellow px-4 py-3">
          <h3 className="font-display text-base font-extrabold uppercase">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="border-2 border-ink bg-white px-2 font-display font-extrabold hover:bg-gred hover:text-white">✕</button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

/** Slide-over drawer used for issue / PR detail views. */
export function Drawer({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-ink/50" onClick={onClose} aria-hidden />
      <aside className="absolute inset-y-0 right-0 flex w-[min(94vw,560px)] flex-col border-l-[4px] border-ink bg-paper shadow-[-10px_0_0_0_rgba(16,16,16,0.15)]">
        <div className="flex items-center justify-between border-b-[3px] border-ink bg-gyellow px-4 py-3">
          <h3 className="min-w-0 truncate font-display text-base font-extrabold uppercase">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="border-2 border-ink bg-white px-2 font-display font-extrabold hover:bg-gred hover:text-white">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 sm:p-5">{children}</div>
      </aside>
    </div>
  );
}

export function Callout({ tone = "blue", title, children }) {
  const tones = { blue: "bg-gblue-light", red: "bg-gred-light", yellow: "bg-gyellow-light", green: "bg-ggreen-light" };
  return (
    <div className={cn("border-[3px] border-ink p-4 shadow-[4px_4px_0_0_#101010]", tones[tone])}>
      <p className="font-display text-sm font-extrabold uppercase tracking-wide">{title}</p>
      <div className="mt-1 text-sm leading-relaxed text-ink-soft">{children}</div>
    </div>
  );
}

export function Sticker({ children, tone = "yellow", rotate = "-2" }) {
  return (
    <span
      style={{ transform: `rotate(${rotate}deg)` }}
      className={cn(
        "inline-block border-[3px] border-ink px-3 py-1 font-display text-xs font-extrabold uppercase tracking-wide shadow-[4px_4px_0_0_#101010]",
        VARIANT[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Marquee({ items }) {
  const row = [...items, ...items];
  return (
    <div className="overflow-hidden border-y-[3px] border-ink bg-ink py-2">
      <div className="flex w-max animate-marquee gap-10">
        {row.map((t, i) => (
          <span key={i} className="flex shrink-0 items-center gap-3 font-mono text-[11px] font-bold uppercase tracking-[0.2em] text-paper">
            <span className="text-gyellow">◆</span>
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}
