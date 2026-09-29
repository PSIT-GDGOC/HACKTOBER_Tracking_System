import { useEffect, useState } from "react";
import { cn } from "@/utils/cn";

let toastIdCounter = 0;

/**
 * Trigger a toast notification from anywhere in the app.
 * @param {string} message - Text to display (untrusted strings will be rendered as text only)
 * @param {{ tone?: "yellow" | "green" | "red" | "blue", duration?: number }} options
 */
export function toast(message, { tone = "yellow", duration = 4000 } = {}) {
  const id = ++toastIdCounter;
  window.dispatchEvent(
    new CustomEvent("gdgoc-toast", {
      detail: { id, message: String(message ?? ""), tone, duration },
    }),
  );
  return id;
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const handleToast = (e) => {
      const { id, message, tone, duration } = e.detail;
      setToasts((prev) => [...prev, { id, message, tone }]);

      if (duration > 0) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, duration);
      }
    };

    window.addEventListener("gdgoc-toast", handleToast);
    return () => window.removeEventListener("gdgoc-toast", handleToast);
  }, []);

  const dismiss = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="Notifications"
      className="fixed bottom-5 right-5 z-50 flex max-w-sm flex-col gap-2.5 pointer-events-none"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.tone === "red" ? "alert" : "status"}
          aria-live={t.tone === "red" ? "assertive" : "polite"}
          className={cn(
            "pointer-events-auto flex items-center justify-between gap-3 border-[3px] border-ink p-3 shadow-[5px_5px_0_0_#101010] animate-pop",
            t.tone === "red" && "bg-gred-light text-ink",
            t.tone === "green" && "bg-ggreen-light text-ink",
            t.tone === "yellow" && "bg-gyellow text-ink",
            t.tone === "blue" && "bg-gblue-light text-ink",
          )}
        >
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-bold">
              {t.tone === "red" ? "▲" : t.tone === "green" ? "✓" : "⚑"}
            </span>
            <p className="font-mono text-xs font-bold leading-tight">{t.message}</p>
          </div>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            aria-label="Dismiss notification"
            className="ml-2 shrink-0 border-2 border-ink bg-white px-1.5 py-0.5 font-mono text-[10px] font-bold text-ink hover:bg-ink hover:text-white"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

export default ToastContainer;
