/**
 * Auth Wizard — one route, step-based:
 *   0 landing → 1 signup (name/email/roll) → 2 ID upload (QR verification)
 *   → 3 result (auto-verified or pending-review) → 4 GitHub connect → dashboard
 *
 * Endpoints (backendd/app/routers/auth.py):
 *   POST /auth/signup { name, email, psit_roll_no }
 *   POST /auth/verify-id { psit_roll_no, id_card_image_base64 }   (JWT required)
 *   POST /auth/login { identifier }
 *   GET  /auth/github/login  → { oauth_url }
 *   POST /auth/github/link { github_username }
 */
import { useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, tokenStore } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useMutation } from "@/lib/hooks";
import { cn } from "@/utils/cn";
import {
  Badge, Button, Callout, Field, GdgMark, Input, Panel, Sticker,
} from "@/components/ui";

const STEPS = ["Intro", "Sign up", "ID check", "Result", "GitHub"];

/* ------------------------------------------------------------------ */
/*  wizard shell                                                       */
/* ------------------------------------------------------------------ */

function WizardShell({ step, children }) {
  return (
    <div className="min-h-screen bg-paper dot-paper">
      <header className="border-b-[3px] border-ink bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <GdgMark size={34} />
            <span className="font-display text-xl font-extrabold">
              <span className="text-gblue">G</span><span className="text-gred">D</span><span className="text-gyellow">G</span>
              <span className="ml-1.5 text-[10px] font-bold uppercase tracking-[0.18em] text-ink-soft">Hacktoberfest · PSIT</span>
            </span>
          </Link>
          <Link to="/login" className="font-mono text-[11px] font-bold uppercase underline decoration-dotted">
            log in instead →
          </Link>
        </div>
      </header>

      {/* stepper */}
      <div className="border-b-[3px] border-ink bg-gyellow">
        <div className="mx-auto flex max-w-5xl items-center gap-0 overflow-x-auto px-4 py-3">
          {STEPS.map((l, i) => (
            <div key={l} className="flex shrink-0 items-center">
              <div
                className={cn(
                  "flex h-8 w-8 items-center justify-center border-[3px] border-ink font-display text-sm font-extrabold",
                  i < step ? "bg-ggreen text-white" : i === step ? "bg-ink text-gyellow" : "bg-white text-ink-soft",
                )}
              >
                {i < step ? "✓" : i + 1}
              </div>
              <span className={cn("ml-2 font-mono text-[10px] font-bold uppercase tracking-wider", i === step ? "text-ink" : "text-ink-soft")}>
                {l}
              </span>
              {i < STEPS.length - 1 && <span className="mx-3 h-[3px] w-8 shrink-0 bg-ink/40 sm:w-14" />}
            </div>
          ))}
        </div>
      </div>

      <main className="mx-auto grid max-w-5xl gap-6 px-4 py-10 lg:grid-cols-[1.2fr_0.8fr]">
        <Panel className="p-6 sm:p-8">{children}</Panel>
        <div className="space-y-4">
          <Callout tone="blue" title="Verification is server-side">
            Your ID card is decoded and cross-checked against the PSIT portal record on the
            backend — the client never asserts its own "verified" flag.
          </Callout>
          <Callout tone="yellow" title="Manual fallback">
            Unreadable QR or a name mismatch? Your account lands in the admin's manual-approval
            queue instead of being rejected. Typical turnaround: under 24 hours.
          </Callout>
        </div>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  the wizard                                                         */
/* ------------------------------------------------------------------ */

export function AuthWizard() {
  const nav = useNavigate();
  const { refreshUser } = useAuth();
  const [step, setStep] = useState(0);
  const [error, setError] = useState(null);

  /* signup form */
  const [form, setForm] = useState({ name: "", email: "", psit_roll_no: "", agree: false });
  const signup = useMutation(api.signup);
  const [signedUpUser, setSignedUpUser] = useState(null);

  /* ID upload */
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploadPct, setUploadPct] = useState(0);
  const [qrStatus, setQrStatus] = useState("idle"); // idle | reading | uploading | verifying
  const verifyId = useMutation(api.verifyId);
  const [verifyResult, setVerifyResult] = useState(null); // { verified, status, message }

  /* github */
  const [githubUsername, setGithubUsername] = useState("");
  const linkGithub = useMutation(api.linkGithub);
  const [linked, setLinked] = useState(false);

  const doSignup = async (e) => {
    e.preventDefault();
    const roll = form.psit_roll_no.trim();
    if (form.name.trim().length < 2) return setError("Enter your full name as it appears on your PSIT ID card.");
    if (!/^\S+@\S+\.\S+$/.test(form.email)) return setError("Enter a valid email address.");
    if (roll.length !== 13) return setError("PSIT roll number must be exactly 13 characters (e.g. 2200320100001).");
    if (!form.agree) return setError("You need to accept the code of conduct to continue.");
    setError(null);
    try {
      const res = await api.signup({
        name: form.name.trim(),
        email: form.email.trim(),
        psit_roll_no: roll,
      });
      setSignedUpUser(res);
      setStep(2);
    } catch (err) {
      const msg = err?.detail || err?.message || "Failed to create account. Please check your details.";
      setError(msg);
    }
  };

  const pickFile = (f) => {
    if (!f) return;
    if (!["image/jpeg", "image/png"].includes(f.type)) {
      setError("Only JPEG or PNG photos of your ID card are accepted.");
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      setError("Image is over the 5MB limit — crop or compress it and try again.");
      return;
    }
    setError(null);
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  const doVerify = async () => {
    if (!file) return setError("Choose a photo of your ID card first.");
    setError(null);
    setQrStatus("reading");
    setUploadPct(15);

    try {
      // Preserve sharp image clarity for QR matrix decoding
      const dataUrl = await compressImage(file, 2000, 0.90);
      setUploadPct(45);
      setQrStatus("uploading");

      const res = await api.verifyId({
        psit_roll_no: signedUpUser?.psit_roll_no ?? form.psit_roll_no.trim(),
        id_card_image_base64: dataUrl,
      });
      setUploadPct(100);
      setQrStatus("idle");

      if (res) {
        setVerifyResult(res);
        setStep(3);
      }
    } catch (err) {
      setUploadPct(0);
      setQrStatus("idle");
      const msg = err?.detail || err?.message || "Failed to verify ID card. Please try again.";
      setError(msg);
    }
  };

  /* verify-id needs a JWT — the backend attaches the upload to the session user.
     Right after signup there is no session, so we log in first (identifier = roll). */
  const ensureSession = async () => {
    try {
      const session = await api.login({ identifier: signedUpUser?.psit_roll_no ?? form.psit_roll_no.trim() });
      tokenStore.set(session.access_token, session.expires_in);
      return true;
    } catch {
      return false;
    }
  };

  const startVerification = async () => {
    setQrStatus("uploading");
    const ok = await ensureSession();
    if (!ok) {
      setQrStatus("idle");
      setError("Could not start a session for your account — try logging in with your roll number.");
      return;
    }
    setQrStatus("verifying");
    await doVerify();
  };

  const doLinkGithub = async (e) => {
    e.preventDefault();
    const username = githubUsername.trim().replace(/^@/, "");
    if (!username) return setError("Enter your GitHub username.");
    setError(null);
    const res = await linkGithub.mutate({ github_username: username });
    if (res) {
      setLinked(true);
    } else if (linkGithub.error) {
      setError(linkGithub.error);
    }
  };

  const enterDashboard = async () => {
    await refreshUser().catch(() => {});
    nav("/dashboard");
  };

  return (
    <WizardShell step={step}>
      {/* ---------------- 0 · landing ---------------- */}
      {step === 0 && (
        <>
          <Sticker tone="red" rotate="-2">Open Source Sprint</Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-[0.95] tracking-tight">
            Join the contribution program
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-ink-soft">
            One verified PSIT account gets you everything: claim issues across the Web and Android
            repos, open pull requests, and track your contributions end-to-end on the leaderboard.
          </p>
          <ol className="mt-6 space-y-3">
            {[
              ["Sign up", "Name, email and your official PSIT roll number."],
              ["Upload your ID card", "We decode the QR server-side and match it against the portal record."],
              ["Connect GitHub", "Claims are matched to PRs by your GitHub username."],
            ].map(([t, b], i) => (
              <li key={t} className="flex gap-3 border-[3px] border-ink bg-paper-2/50 p-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-ink bg-white font-display text-sm font-extrabold">
                  {i + 1}
                </span>
                <div>
                  <p className="font-display text-sm font-bold">{t}</p>
                  <p className="text-xs text-ink-soft">{b}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="blue" size="lg" onClick={() => setStep(1)}>Start signup →</Button>
            <Link
              to="/login"
              className="inline-flex items-center border-[3px] border-ink bg-white px-6 py-3.5 font-display text-base font-bold uppercase shadow-[4px_4px_0_0_#101010] hover:-translate-y-0.5"
            >
              I have an account
            </Link>
          </div>
        </>
      )}

      {/* ---------------- 1 · signup ---------------- */}
      {step === 1 && (
        <>
          <Sticker tone="blue" rotate="-1">Step 1 of 3</Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">Sign up</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Use your name and roll number exactly as they appear on your PSIT ID card — the verification
            match depends on it.
          </p>
          <form onSubmit={doSignup} className="mt-6 space-y-4">
            <Field label="Full name" hint="as on your ID card">
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Aarav Sharma"
                autoFocus
              />
            </Field>
            <Field label="Email">
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="you@psit.ac.in"
              />
            </Field>
            <Field label="PSIT roll number" hint="official roll number">
              <Input
                value={form.psit_roll_no}
                onChange={(e) => setForm({ ...form, psit_roll_no: e.target.value })}
                placeholder="2200320100001"
                className="font-mono tracking-widest"
              />
            </Field>
            <label className="flex cursor-pointer items-start gap-3 border-[3px] border-ink bg-paper-2/50 p-3">
              <input
                type="checkbox"
                checked={form.agree}
                onChange={(e) => setForm({ ...form, agree: e.target.checked })}
                className="mt-0.5 h-5 w-5 shrink-0 accent-[#4285F4]"
              />
              <span className="text-sm leading-relaxed">
                I agree to the Code of Conduct and the program rules (max active claims enforced per
                student, original work only).
              </span>
            </label>
            {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}
            <Button type="submit" variant="blue" size="lg" loading={signup.pending} className="w-full">
              Create account →
            </Button>
          </form>
        </>
      )}

      {/* ---------------- 2 · ID upload ---------------- */}
      {step === 2 && (
        <>
          <Sticker tone="yellow" rotate="1">Step 2 of 3</Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">
            Verify your ID card
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            {signedUpUser
              ? `Account created for ${signedUpUser.name} (${signedUpUser.psit_roll_no}).`
              : "Upload the front of your PSIT ID card."}{" "}
            The backend scans the QR code and cross-checks the portal record server-side.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-[1fr_1fr]">
            <label
              className={cn(
                "flex min-h-44 cursor-pointer flex-col items-center justify-center gap-2 border-[3px] border-dashed border-ink bg-paper-2/50 p-4 text-center hover:bg-gyellow-light",
                preview && "border-solid bg-white",
              )}
            >
              {preview ? (
                <img src={preview} alt="ID card preview" className="max-h-40 w-full object-contain" />
              ) : (
                <>
                  <span className="text-3xl">🪪</span>
                  <span className="font-display text-sm font-extrabold uppercase">Choose ID photo</span>
                  <span className="font-mono text-[10px] text-ink-soft">JPEG or PNG · under 5MB</span>
                </>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                onChange={(e) => pickFile(e.target.files?.[0])}
              />
            </label>

            <div className="space-y-3">
              {[
                ["Photo selected", !!file],
                ["Uploading to private storage", qrStatus === "uploading" || uploadPct >= 45],
                ["Scanning QR & matching portal", qrStatus === "verifying"],
              ].map(([label, active], i) => (
                <div key={i} className={cn("flex items-center gap-3 border-[3px] border-ink p-3", active ? "bg-ggreen-light" : "bg-paper-2/40")}>
                  <span className={cn("flex h-7 w-7 items-center justify-center border-2 border-ink font-display text-sm font-extrabold", active ? "bg-ggreen text-white" : "bg-white text-ink-soft")}>
                    {active ? "✓" : i + 1}
                  </span>
                  <span className="font-mono text-xs font-bold uppercase tracking-wider">{label}</span>
                  {qrStatus !== "idle" && active && (
                    <span className="ml-auto h-4 w-4 animate-spin rounded-full border-[3px] border-ink border-t-transparent" />
                  )}
                </div>
              ))}
              {uploadPct > 0 && (
                <div className="h-4 w-full border-2 border-ink bg-paper-2">
                  <div className="h-full bg-gblue transition-all" style={{ width: `${uploadPct}%` }} />
                </div>
              )}
            </div>
          </div>

          {error && <p className="mt-3 font-mono text-xs font-bold text-gred">▲ {error}</p>}

          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="green" size="lg" onClick={startVerification} loading={qrStatus !== "idle"} disabled={!file}>
              Scan &amp; verify →
            </Button>
          </div>
          <p className="mt-3 font-mono text-[10px] leading-relaxed text-ink-soft">
            Make sure the entire QR code and text are clearly visible, in focus, and without glare.
          </p>
        </>
      )}

      {/* ---------------- 3 · result ---------------- */}
      {step === 3 && (
        <>
          <Sticker tone={verifyResult?.verified ? "green" : (verifyResult?.status?.startsWith("duplicate") ? "red" : "yellow")} rotate="-2">
            Step 3 of 3
          </Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">
            {verifyResult?.verified
              ? "You're verified ✓"
              : verifyResult?.status?.startsWith("duplicate")
              ? "ID Card Already Registered"
              : "Verification Required"}
          </h1>

          {verifyResult?.verified ? (
            <div className="mt-5 border-[3px] border-ink bg-ggreen-light p-4 shadow-[5px_5px_0_0_#101010]">
              <p className="font-display text-sm font-extrabold uppercase text-ggreen">{verifyResult.status || "AUTO_VERIFIED"}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-soft">{verifyResult.message}</p>
            </div>
          ) : (
            <div className={`mt-5 border-[3px] border-ink p-5 shadow-[5px_5px_0_0_#101010] ${verifyResult?.status?.startsWith("duplicate") ? "bg-red-50" : "bg-gyellow-light"}`}>
              <p className={`font-display text-sm font-extrabold uppercase ${verifyResult?.status?.startsWith("duplicate") ? "text-gred" : "text-ink"}`}>
                {verifyResult?.status === "qr_unreadable"
                  ? "QR Code Unreadable"
                  : verifyResult?.status === "duplicate_verified_card"
                  ? "PSIT ID Card Already Registered"
                  : verifyResult?.status === "duplicate_verified_roll"
                  ? "Roll Number Already Verified"
                  : "Pending Admin Verification"}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-ink">
                {verifyResult?.message || "Your ID card could not be verified automatically. Access to the dashboard is locked until your student identity is verified."}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  variant="blue"
                  size="md"
                  onClick={() => {
                    setFile(null);
                    setPreview(null);
                    setError(null);
                    setStep(2);
                  }}
                >
                  {verifyResult?.status?.startsWith("duplicate") ? "↺ Upload Different ID Card" : "↺ Try Re-uploading Clearer Photo"}
                </Button>
                <Link
                  to="/login"
                  className="inline-flex items-center border-[3px] border-ink bg-white px-4 py-2 font-display text-sm font-bold uppercase shadow-[3px_3px_0_0_#101010] hover:-translate-y-0.5"
                >
                  Log in later
                </Link>
              </div>
            </div>
          )}

          {verifyResult?.verified && (
            <>
              <h2 className="mt-8 font-display text-xl font-extrabold uppercase tracking-tight">Connect your GitHub</h2>
              <p className="mt-1 text-sm text-ink-soft">
                Required before you can claim issues — PRs and commits are matched to your claims by
                GitHub username.
              </p>

              {linked ? (
                <Panel className="mt-4 border-ggreen p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="font-display text-lg font-extrabold">@{githubUsername.replace(/^@/, "")}</p>
                    <Badge tone="green" dot>Linked</Badge>
                  </div>
                </Panel>
              ) : (
                <form onSubmit={doLinkGithub} className="mt-4 space-y-3">
                  <Field label="GitHub username" hint="or use the OAuth redirect">
                    <Input
                      value={githubUsername}
                      onChange={(e) => setGithubUsername(e.target.value)}
                      placeholder="octocat"
                      className="font-mono"
                    />
                  </Field>
                  {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}
                  <div className="flex flex-wrap gap-3">
                    <Button type="submit" variant="ink" loading={linkGithub.pending}>Link account</Button>
                    <Button
                      type="button"
                      variant="paper"
                      onClick={async () => {
                        try {
                          const { oauth_url } = await api.githubLoginUrl();
                          window.open(oauth_url, "_blank", "noopener");
                        } catch {
                          setError("Could not start the GitHub OAuth flow — link your username manually instead.");
                        }
                      }}
                    >
                      Use GitHub OAuth ↗
                    </Button>
                  </div>
                </form>
              )}

              <div className="mt-8 border-t-2 border-dashed border-paper-3 pt-5">
                <Button variant="green" size="lg" className="w-full" onClick={enterDashboard}>
                  Enter the dashboard →
                </Button>
              </div>
            </>
          )}
        </>
      )}
    </WizardShell>
  );
}

/** Downscale + re-encode an image file to a JPEG data URL. Preserves full resolution if under 4.5MB. */
function compressImage(file, maxSide = 2200, quality = 0.90) {
  // If file is already <= 4.5MB, don't downscale so the QR finder patterns remain crisp and readable!
  if (file.size <= 4.5 * 1024 * 1024) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Could not read the file"));
      reader.onload = () => resolve(reader.result);
      reader.readAsDataURL(file);
    });
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Could not read the file"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Could not decode the image"));
      img.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", quality));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

/* ------------------------------------------------------------------ */
/*  login                                                              */
/* ------------------------------------------------------------------ */

export function Login() {
  const nav = useNavigate();
  const { login, logout } = useAuth();
  const [identifier, setIdentifier] = useState("");
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);

  /** Where RequireRole bounced us from, so we can send the user back there. */
  const from = useLocation().state?.from;

  const submit = async (e) => {
    e.preventDefault();
    const id = identifier.trim();
    if (!id) return setError("Enter your roll number or email.");
    setError(null);
    setPending(true);
    try {
      const user = await login(id);
      if (user && user.role === "student" && !user.verified) {
        logout();
        setError("Your account is not verified. You must complete ID card verification before logging into the system.");
        return;
      }
      nav(from && from.startsWith("/dashboard") ? from : "/dashboard");
    } catch (err) {
      const msg = err?.detail || err?.message || "No account found for that roll number or email.";
      setError(msg);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper grid-paper px-4 py-10">
      <div className="w-full max-w-md">
        <Panel className="p-7">
          <div className="flex items-center gap-3">
            <GdgMark size={40} />
            <div>
              <p className="font-display text-2xl font-extrabold leading-none">
                <span className="text-gblue">G</span><span className="text-gred">D</span><span className="text-gyellow">G</span>
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-soft">Hacktoberfest · PSIT</p>
            </div>
          </div>

          <h1 className="mt-6 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">Log in</h1>
          <p className="mt-2 text-sm text-ink-soft">
            Roll number or email in, JWT out. No passwords in this app — ever.
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Field label="Roll number or email" error={error}>
              <Input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="2200320100001"
                className="font-mono"
                autoFocus
              />
            </Field>
            <Button type="submit" variant="blue" size="lg" loading={pending} className="w-full">
              Continue →
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-ink-soft">
            New here?{" "}
            <Link to="/join" className="font-bold underline decoration-gblue decoration-2 underline-offset-2">
              Create an account
            </Link>
          </p>
        </Panel>
      </div>
    </div>
  );
}
