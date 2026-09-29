import React from "react";
import { cn } from "@/utils/cn";
import { GMAIL_EXAMPLE } from "@/lib/validation/gmail";

/**
 * Pinned notice component for official Gmail requirement.
 *
 * Placed directly above the email input field.
 * Always visible, non-dismissible, rendered as a neo-brutalist pinned sticky note.
 *
 * @param {Object} props
 * @param {string} [props.id="gmail-pin-note"] - Referenced by input aria-describedby
 * @param {"default" | "login"} [props.variant="default"]
 * @param {{ ok: boolean, code?: string, message?: string, suggestion?: string } | null} [props.validation]
 * @param {(suggestion: string) => void} [props.onApplySuggestion]
 * @param {string} [props.className]
 */
export function GmailPin({
  id = "gmail-pin-note",
  variant = "default",
  validation = null,
  onApplySuggestion,
  className,
}) {
  const isTypo = validation && !validation.ok && validation.code === "TYPO" && validation.suggestion;
  const isInvalid = validation && !validation.ok && !isTypo;
  const isValid = validation && validation.ok;
  // On login a non-gmail email is still a valid identifier (roll number OR email),
  // so the note stays an informational, non-blocking hint — never red.
  const isLoginHint = isInvalid && variant === "login";

  // Determine state-based visual styling
  let containerTone = "border-ink bg-gyellow/30 shadow-[3px_3px_0_0_#101010]";
  let pinBadge = "border-ink bg-white text-ink";
  let statusIcon = "📌";

  if (isTypo) {
    containerTone = "border-ink bg-gyellow-light shadow-[3px_3px_0_0_#FBBC04]";
    pinBadge = "border-ink bg-gyellow text-ink";
    statusIcon = "💡";
  } else if (isLoginHint) {
    containerTone = "border-ink bg-gyellow-light shadow-[3px_3px_0_0_#101010]";
    pinBadge = "border-ink bg-gyellow text-ink";
    statusIcon = "ℹ";
  } else if (isInvalid) {
    containerTone = "border-gred bg-gred-light/60 shadow-[3px_3px_0_0_#EA4335]";
    pinBadge = "border-gred bg-white text-gred";
    statusIcon = "✕";
  } else if (isValid) {
    containerTone = "border-ggreen bg-ggreen-light/70 shadow-[3px_3px_0_0_#34A853]";
    pinBadge = "border-ggreen bg-white text-ggreen";
    statusIcon = "✓";
  }

  return (
    <aside
      id={id}
      role="note"
      aria-label="Gmail requirement note"
      className={cn(
        "relative mb-3.5 w-full border-[2.5px] p-3 transition-colors duration-150 motion-reduce:transition-none sm:-rotate-[0.75deg]",
        containerTone,
        className,
      )}
    >
      {/* Overlapping pushpin icon in top-left */}
      <span
        aria-hidden="true"
        className={cn(
          "absolute -left-2.5 -top-2.5 flex h-6 w-6 select-none items-center justify-center rounded-full border-2 text-xs font-bold shadow-[2px_2px_0_0_#101010]",
          pinBadge,
        )}
      >
        {statusIcon}
      </span>

      <div className="pl-4">
        {/* Monospace uppercase micro-label */}
        <div className="flex flex-wrap items-center justify-between gap-1">
          <span className="font-mono text-[10px] font-bold uppercase tracking-widest text-ink">
            PINNED · GMAIL ONLY
          </span>
          {isValid && (
            <span className="font-mono text-[10px] font-bold uppercase text-ink">
              ✓ Verified
            </span>
          )}
        </div>

        {/* Dynamic content & live validation area */}
        <div aria-live="polite" className="mt-1 text-xs text-ink">
          {isTypo ? (
            <div className="space-y-1.5">
              <p className="font-medium text-ink">
                Looks like a typo in your domain: <span className="font-mono font-bold underline">{validation.suggestion}</span>
              </p>
              {onApplySuggestion && (
                <button
                  type="button"
                  onClick={() => onApplySuggestion(validation.suggestion)}
                  className="inline-flex min-h-[44px] items-center gap-1.5 border-2 border-ink bg-white px-3 py-1 font-mono text-[11px] font-bold uppercase text-ink shadow-[2px_2px_0_0_#101010] transition-transform hover:-translate-y-0.5 hover:bg-gyellow-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gblue"
                >
                  <span>Did you mean <strong>{validation.suggestion}</strong>? Click to apply</span>
                </button>
              )}
            </div>
          ) : isInvalid ? (
            isLoginHint ? (
              <p className="leading-snug">
                That address won't end in <strong className="font-bold underline decoration-ink">@gmail.com</strong> — use your roll number, or sign in with your official Google address.
              </p>
            ) : (
              <div className="flex items-start gap-1.5 font-sans font-medium text-ink">
                <span className="font-mono font-bold text-gred" aria-hidden="true">✕</span>
                <span>{validation.message}</span>
              </div>
            )
          ) : (
            <>
              {variant === "login" ? (
                <p className="leading-snug">
                  Signing in with email? It must end in <strong className="font-bold underline decoration-ink">@gmail.com</strong>, e.g.{" "}
                  <code className="break-words font-mono font-bold">{GMAIL_EXAMPLE}</code>. Or use your roll number.
                </p>
              ) : (
                <p className="leading-snug">
                  Use your official Google address ending in{" "}
                  <strong className="font-bold underline decoration-ink">@gmail.com</strong>
                </p>
              )}

              {/* Example chip */}
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-ink-soft">
                  Example:
                </span>
                <span className="inline-block max-w-full break-words border-2 border-ink bg-white px-2 py-0.5 font-mono text-[11px] font-bold text-ink shadow-[2px_2px_0_0_#101010]">
                  rudransh<strong className="text-gblue-dark">@gmail.com</strong>
                </span>
              </div>
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
