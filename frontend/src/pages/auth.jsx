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
import { useEffect, useRef, useState } from "react";
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
  const location = useLocation();
  const { user, refreshUser } = useAuth();
  const [step, setStep] = useState(0);
  const [error, setError] = useState(null);

  /* Detect step from state or authenticated user */
  useEffect(() => {
    if (location.state?.step !== undefined) {
      setStep(location.state.step);
    } else if (user && user.role === "student") {
      if (user.verified && user.github_username) {
        setLinked(true);
        setGithubUsername(user.github_username);
        setStep(4);
      } else if (user.verified) {
        setStep(4);
      } else {
        setStep(2);
      }
    }
  }, [user, location.state]);

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
  const [githubUsername, setGithubUsername] = useState(user?.github_username || "");
  const [linkingGithub, setLinkingGithub] = useState(false);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [linked, setLinked] = useState(!!user?.github_username);

  /* password setup */
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordSaved, setPasswordSaved] = useState(false);
  const [passwordError, setPasswordError] = useState(null);
  const [savingPassword, setSavingPassword] = useState(false);

  const doSetPassword = async (e) => {
    if (e) e.preventDefault();
    setPasswordError(null);
    if (password.length < 8) {
      setPasswordError("Password must be at least 8 characters long.");
      return;
    }
    const hasLetter = /[a-zA-Z]/.test(password);
    const hasNonLetter = /[^a-zA-Z]/.test(password);
    if (!hasLetter || !hasNonLetter) {
      setPasswordError("Password must include at least one letter and one number or symbol.");
      return;
    }
    if (password !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setSavingPassword(true);
    try {
      await api.setPassword({ password });
      setPasswordSaved(true);
      setError(null);
    } catch (err) {
      setPasswordError(err?.detail || err?.message || "Failed to set password.");
    } finally {
      setSavingPassword(false);
    }
  };

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
    if (tokenStore.get() && !tokenStore.isExpired()) return true;
    try {
      const session = await api.login({ identifier: signedUpUser?.psit_roll_no ?? form.psit_roll_no.trim() });
      tokenStore.set(session.access_token, session.expires_in);
      await refreshUser().catch(() => {});
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

  const doOAuthConnect = async () => {
    setError(null);
    setOauthLoading(true);
    try {
      const res = await api.githubLoginUrl();
      if (res?.oauth_url) {
        window.location.href = res.oauth_url;
      } else {
        setError("Could not retrieve GitHub OAuth URL.");
      }
    } catch (err) {
      setError(err?.detail || err?.message || "Failed to start GitHub OAuth flow.");
    } finally {
      setOauthLoading(false);
    }
  };

  const doLinkGithub = async (e) => {
    if (e) e.preventDefault();
    const username = githubUsername.trim().replace(/^@/, "");
    if (!username) return setError("Enter your GitHub username.");
    setError(null);
    setLinkingGithub(true);
    try {
      const res = await api.linkGithub({ github_username: username });
      if (res) {
        setLinked(true);
        setGithubUsername(res.github_username || username);
        await refreshUser().catch(() => {});
      }
    } catch (err) {
      setError(err?.detail || err?.message || "Failed to link GitHub account.");
    } finally {
      setLinkingGithub(false);
    }
  };

  const enterDashboard = async () => {
    const updatedUser = await refreshUser().catch(() => null);
    if (updatedUser?.role === "student" && !updatedUser?.github_username && !linked && !githubUsername.trim()) {
      setError("Linking your GitHub account is required before entering the dashboard.");
      return;
    }
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
          <Sticker tone={verifyResult?.verified || user?.verified ? "green" : (verifyResult?.status?.startsWith("duplicate") ? "red" : "yellow")} rotate="-2">
            Step 4 of 5
          </Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">
            {verifyResult?.verified || user?.verified
              ? "You're verified ✓"
              : verifyResult?.status?.startsWith("duplicate")
              ? "ID Card Already Registered"
              : "Verification Required"}
          </h1>

          {verifyResult?.verified || user?.verified ? (
            <div className="mt-5 border-[3px] border-ink bg-ggreen-light p-4 shadow-[5px_5px_0_0_#101010]">
              <p className="font-display text-sm font-extrabold uppercase text-ggreen">{verifyResult?.status || "VERIFIED"}</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-soft">{verifyResult?.message || "Student identity verified successfully."}</p>
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

          {(verifyResult?.verified || user?.verified) && (
            <>
              {/* Account Password Setup */}
              {!passwordSaved ? (
                <div className="mt-6 border-[3px] border-ink bg-white p-5 shadow-[5px_5px_0_0_#101010]">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center bg-gblue text-white font-mono text-xs font-bold border-2 border-ink">
                      🔒
                    </span>
                    <h2 className="font-display text-lg font-extrabold uppercase tracking-tight">Create your account password</h2>
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">
                    Set a strong password so nobody else can log into your account with your roll number.
                  </p>

                  <form onSubmit={doSetPassword} className="mt-4 space-y-3">
                    <Field label="New password" hint="Min. 8 characters with letters & numbers">
                      <div className="relative">
                        <Input
                          type={showPassword ? "text" : "password"}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="Enter strong password"
                          className="font-mono pr-14"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-mono font-bold uppercase text-ink-soft hover:text-ink"
                        >
                          {showPassword ? "Hide" : "Show"}
                        </button>
                      </div>
                    </Field>

                    <Field label="Confirm password">
                      <Input
                        type={showPassword ? "text" : "password"}
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        placeholder="Re-type your password"
                        className="font-mono"
                      />
                    </Field>

                    {passwordError && <p className="font-mono text-xs font-bold text-gred">▲ {passwordError}</p>}

                    <Button type="submit" variant="blue" size="md" loading={savingPassword} className="w-full">
                      Save Password →
                    </Button>
                  </form>
                </div>
              ) : (
                <div className="mt-6 border-[3px] border-ink bg-ggreen-light p-4 shadow-[4px_4px_0_0_#101010] flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 items-center justify-center bg-ggreen text-white font-display text-sm font-extrabold border-2 border-ink">
                      ✓
                    </span>
                    <div>
                      <p className="font-display text-sm font-extrabold uppercase text-ink">Password Protected</p>
                      <p className="text-xs text-ink-soft">Your account is secured with your password.</p>
                    </div>
                  </div>
                  <Badge tone="green" dot>Secured</Badge>
                </div>
              )}

              <div className="mt-8 border-t-2 border-dashed border-paper-3 pt-5">
                <Button variant="green" size="lg" className="w-full" onClick={() => setStep(4)}>
                  Next: Connect GitHub Account →
                </Button>
              </div>
            </>
          )}
        </>
      )}

      {/* ---------------- 4 · GitHub ---------------- */}
      {step === 4 && (
        <>
          <Sticker tone={linked || user?.github_username ? "green" : "yellow"} rotate="1">
            Step 5 of 5
          </Sticker>
          <h1 className="mt-4 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">
            Connect your GitHub account
          </h1>
          <p className="mt-2 text-sm text-ink-soft">
            Required before you can claim issues — PRs and commits are matched to your claims by your GitHub handle.
          </p>

          {linked || user?.github_username ? (
            <div className="mt-6 space-y-4">
              <Panel className="border-ggreen bg-ggreen-light p-5 shadow-[4px_4px_0_0_#101010]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs font-bold uppercase tracking-wider text-ink-soft">GitHub Identity Linked</p>
                    <p className="font-display text-2xl font-extrabold text-ink">@{githubUsername.replace(/^@/, "") || user?.github_username}</p>
                  </div>
                  <Badge tone="green" dot>Verified &amp; Linked</Badge>
                </div>
              </Panel>
              <Button variant="green" size="lg" className="w-full" onClick={enterDashboard}>
                Enter the Dashboard →
              </Button>
            </div>
          ) : (
            <div className="mt-6 space-y-6">
              {/* Option A: OAuth Authorization */}
              <div className="border-[3px] border-ink bg-white p-5 shadow-[4px_4px_0_0_#101010]">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center bg-ink text-white font-mono text-xs font-bold border-2 border-ink">
                    ⚡
                  </span>
                  <h2 className="font-display text-base font-extrabold uppercase">Option A: Authorize via GitHub OAuth</h2>
                </div>
                <p className="mt-1 text-xs text-ink-soft">
                  One-click verification. Authenticate with GitHub to verify your account handle automatically.
                </p>
                <div className="mt-4">
                  <Button variant="blue" size="md" onClick={doOAuthConnect} loading={oauthLoading} className="w-full">
                    Authorize with GitHub ↗
                  </Button>
                </div>
              </div>

              {/* Option B: Manual Username Linking */}
              <div className="border-[3px] border-ink bg-paper-2/40 p-5 shadow-[4px_4px_0_0_#101010]">
                <h2 className="font-display text-base font-extrabold uppercase">Option B: Link Username Manually</h2>
                <p className="mt-1 text-xs text-ink-soft">
                  Enter your GitHub handle directly. We will verify that the account exists on GitHub.
                </p>
                <form onSubmit={doLinkGithub} className="mt-4 space-y-3">
                  <Field label="GitHub handle" hint="e.g. octocat">
                    <Input
                      value={githubUsername}
                      onChange={(e) => setGithubUsername(e.target.value)}
                      placeholder="octocat"
                      className="font-mono"
                    />
                  </Field>
                  {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}
                  <Button type="submit" variant="ink" size="md" loading={linkingGithub} className="w-full">
                    Link Handle Manually →
                  </Button>
                </form>
              </div>
            </div>
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
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [pending, setPending] = useState(false);

  /* Forgot password flow state: 'login' | 'forgot_request' | 'forgot_reset' */
  const [mode, setMode] = useState("login");
  const [resetIdentifier, setResetIdentifier] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [maskedEmail, setMaskedEmail] = useState("");

  /** Where RequireRole bounced us from, so we can send the user back there. */
  const from = useLocation().state?.from;

  const submit = async (e) => {
    e.preventDefault();
    const id = identifier.trim();
    if (!id) return setError("Enter your roll number or email.");
    if (!password.trim()) return setError("Enter your account password.");
    setError(null);
    setSuccessMsg(null);
    setPending(true);
    try {
      const user = await login(id, password.trim());
      if (user && user.role === "student") {
        if (!user.verified) {
          nav("/join", { state: { step: 2 } });
          return;
        }
        if (!user.github_username) {
          nav("/join", { state: { step: 4 } });
          return;
        }
      }
      nav(from && from.startsWith("/dashboard") ? from : "/dashboard");
    } catch (err) {
      const msg = err?.detail || err?.message || "Invalid roll number or password.";
      setError(msg);
    } finally {
      setPending(false);
    }
  };

  const handleRequestOtp = async (e) => {
    e.preventDefault();
    const id = resetIdentifier.trim();
    if (!id) return setError("Enter your roll number or email.");
    setError(null);
    setSuccessMsg(null);
    setPending(true);
    try {
      const res = await api.forgotPassword({ identifier: id });
      setMaskedEmail(res.email);
      setSuccessMsg(res.message);
      setMode("forgot_reset");
    } catch (err) {
      setError(err?.detail || err?.message || "Failed to send reset code. Please check your roll number or email.");
    } finally {
      setPending(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!otp.trim() || otp.trim().length !== 6) return setError("Enter the 6-digit verification code sent to your email.");
    if (newPassword.length < 8) return setError("Password must be at least 8 characters long.");
    const hasLetter = /[a-zA-Z]/.test(newPassword);
    const hasNonLetter = /[^a-zA-Z]/.test(newPassword);
    if (!hasLetter || !hasNonLetter) return setError("Password must include at least one letter and one number or symbol.");
    if (newPassword !== confirmNewPassword) return setError("Passwords do not match.");

    setError(null);
    setSuccessMsg(null);
    setPending(true);
    try {
      const res = await api.resetPassword({
        identifier: resetIdentifier.trim(),
        otp: otp.trim(),
        new_password: newPassword,
      });
      setSuccessMsg(res.message || "Password changed successfully! You can now log in with your new password.");
      setIdentifier(resetIdentifier.trim());
      setPassword("");
      setMode("login");
    } catch (err) {
      setError(err?.detail || err?.message || "Failed to reset password. Please check your verification code.");
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

          {/* ──────────────── MODE: LOGIN ──────────────── */}
          {mode === "login" && (
            <>
              <h1 className="mt-6 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">Log in</h1>
              <p className="mt-2 text-sm text-ink-soft">
                Enter your PSIT roll number and password to access your dashboard.
              </p>

              {successMsg && (
                <div className="mt-4 border-[2px] border-ink bg-ggreen-light p-3 text-xs font-mono font-bold text-ink">
                  ✓ {successMsg}
                </div>
              )}

              <form onSubmit={submit} className="mt-6 space-y-4">
                <Field label="Roll number or email">
                  <Input
                    value={identifier}
                    onChange={(e) => setIdentifier(e.target.value)}
                    placeholder="2200320100001"
                    className="font-mono"
                    autoFocus
                  />
                </Field>

                <Field
                  label="Password"
                  hint={
                    <button
                      type="button"
                      onClick={() => {
                        setError(null);
                        setSuccessMsg(null);
                        setResetIdentifier(identifier);
                        setMode("forgot_request");
                      }}
                      className="font-mono font-bold uppercase text-gblue underline decoration-dotted hover:text-ink"
                    >
                      Forgot password?
                    </button>
                  }
                >
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="font-mono pr-14"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-mono font-bold uppercase text-ink-soft hover:text-ink"
                    >
                      {showPassword ? "Hide" : "Show"}
                    </button>
                  </div>
                </Field>

                {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}

                <Button type="submit" variant="blue" size="lg" loading={pending} className="w-full">
                  Log in →
                </Button>
              </form>

              <p className="mt-5 text-center text-sm text-ink-soft">
                New here?{" "}
                <Link to="/join" className="font-bold underline decoration-gblue decoration-2 underline-offset-2">
                  Create an account
                </Link>
              </p>
            </>
          )}

          {/* ──────────────── MODE: FORGOT_REQUEST ──────────────── */}
          {mode === "forgot_request" && (
            <>
              <h1 className="mt-6 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">Forgot Password</h1>
              <p className="mt-2 text-sm text-ink-soft">
                Enter your registered PSIT roll number or email. We will send a 6-digit verification code to your email.
              </p>

              <form onSubmit={handleRequestOtp} className="mt-6 space-y-4">
                <Field label="Roll number or email">
                  <Input
                    value={resetIdentifier}
                    onChange={(e) => setResetIdentifier(e.target.value)}
                    placeholder="2200320100001 or student@psit.ac.in"
                    className="font-mono"
                    autoFocus
                  />
                </Field>

                {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}

                <Button type="submit" variant="yellow" size="lg" loading={pending} className="w-full">
                  Send Reset Code →
                </Button>

                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode("login");
                  }}
                  className="w-full text-center font-mono text-xs font-bold uppercase text-ink-soft hover:text-ink underline"
                >
                  ← Back to Log in
                </button>
              </form>
            </>
          )}

          {/* ──────────────── MODE: FORGOT_RESET ──────────────── */}
          {mode === "forgot_reset" && (
            <>
              <h1 className="mt-6 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">Set New Password</h1>
              <p className="mt-2 text-sm text-ink-soft">
                Enter the 6-digit verification code sent to your email ({maskedEmail || resetIdentifier}) and your new password.
              </p>

              {successMsg && (
                <div className="mt-4 border-[2px] border-ink bg-gyellow-light p-3 text-xs font-mono font-bold text-ink">
                  ✉ {successMsg}
                </div>
              )}

              <form onSubmit={handleResetPassword} className="mt-6 space-y-4">
                <Field label="6-Digit Verification Code" hint="check your email inbox">
                  <Input
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.trim())}
                    placeholder="123456"
                    maxLength={6}
                    className="font-mono tracking-widest text-center text-lg font-bold"
                    autoFocus
                  />
                </Field>

                <Field label="New Password" hint="min. 8 chars with letters & numbers">
                  <Input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="New password"
                    className="font-mono"
                  />
                </Field>

                <Field label="Confirm New Password">
                  <Input
                    type="password"
                    value={confirmNewPassword}
                    onChange={(e) => setConfirmNewPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="font-mono"
                  />
                </Field>

                {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}

                <Button type="submit" variant="green" size="lg" loading={pending} className="w-full">
                  Update Password &amp; Save →
                </Button>

                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    setSuccessMsg(null);
                    setMode("login");
                  }}
                  className="w-full text-center font-mono text-xs font-bold uppercase text-ink-soft hover:text-ink underline"
                >
                  ← Back to Log in
                </button>
              </form>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  GitHub OAuth Callback Handler (BUG-03)                             */
/* ------------------------------------------------------------------ */

export function GitHubOAuthCallback() {
  const nav = useNavigate();
  const location = useLocation();
  const { isAuthenticated, loading, refreshUser } = useAuth();
  const [status, setStatus] = useState("processing"); // 'processing' | 'success' | 'error'
  const [message, setMessage] = useState("");
  const [linkedUsername, setLinkedUsername] = useState("");
  const processedRef = useRef(false);

  useEffect(() => {
    if (loading) return;

    // Extract authorization code or error parameters from URL query strings
    // Handles hash-query (?code=...#/auth/callback), search routing (?code=...), and hash routing (#/auth/callback?code=...)
    const routerParams = new URLSearchParams(location.search);
    const windowParams = new URLSearchParams(window.location.search);
    const hashQuery = window.location.hash.includes("?") ? window.location.hash.split("?")[1] : "";
    const hashParams = new URLSearchParams(hashQuery);

    const oauthError =
      routerParams.get("error_description") ||
      routerParams.get("error") ||
      windowParams.get("error_description") ||
      windowParams.get("error") ||
      hashParams.get("error_description") ||
      hashParams.get("error");

    if (oauthError) {
      setStatus("error");
      setMessage(oauthError);
      return;
    }

    const code =
      routerParams.get("code") ||
      windowParams.get("code") ||
      hashParams.get("code");
    if (!code) {
      setStatus("error");
      setMessage("No authorization code provided in the GitHub callback URL.");
      return;
    }

    if (!isAuthenticated) {
      setStatus("error");
      setMessage("Please log into your account before connecting your GitHub identity.");
      return;
    }

    if (processedRef.current) return;
    processedRef.current = true;

    async function exchangeCode() {
      try {
        const res = await api.githubCallback({ code });
        setStatus("success");
        setLinkedUsername(res.github_username || "");
        setMessage(res.message || "GitHub identity linked successfully!");
        await refreshUser().catch(() => {});
        setTimeout(() => {
          nav("/dashboard", { replace: true });
        }, 2200);
      } catch (err) {
        setStatus("error");
        setMessage(err?.detail || err?.message || "Failed to exchange GitHub authorization code.");
      }
    }

    exchangeCode();
  }, [loading, isAuthenticated, location.search, nav, refreshUser]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper grid-paper px-4 py-10">
      <div className="w-full max-w-md">
        <Panel className="p-7 text-center">
          <div className="flex justify-center">
            <GdgMark size={44} />
          </div>

          <h1 className="mt-5 font-display text-2xl font-extrabold uppercase tracking-tight">
            GitHub Authorization
          </h1>

          {status === "processing" && (
            <div className="mt-6 flex flex-col items-center gap-3">
              <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink border-t-transparent" />
              <p className="font-mono text-xs uppercase tracking-wider text-ink-soft">
                Exchanging code with GitHub…
              </p>
            </div>
          )}

          {status === "success" && (
            <div className="mt-6 space-y-4">
              <div className="border-[3px] border-ink bg-ggreen-light p-4 shadow-[4px_4px_0_0_#101010]">
                <Badge tone="green" dot>Connected</Badge>
                {linkedUsername && (
                  <p className="mt-2 font-display text-lg font-extrabold">@{linkedUsername}</p>
                )}
                <p className="mt-1 text-xs text-ink-soft">{message}</p>
              </div>
              <p className="font-mono text-[11px] text-ink-soft">Redirecting to dashboard in a moment…</p>
              <Button variant="green" size="md" className="w-full" onClick={() => nav("/dashboard")}>
                Go to Dashboard Now →
              </Button>
            </div>
          )}

          {status === "error" && (
            <div className="mt-6 space-y-4 text-left">
              <div className="border-[3px] border-ink bg-gred-light p-4 shadow-[4px_4px_0_0_#101010]">
                <p className="font-display text-sm font-extrabold uppercase text-gred">Linking Failed</p>
                <p className="mt-1 font-mono text-xs text-ink-soft">{message}</p>
              </div>
              <div className="flex flex-col gap-2 pt-2">
                {!isAuthenticated ? (
                  <Link to="/login" className="w-full">
                    <Button variant="blue" size="md" className="w-full">
                      Log in first →
                    </Button>
                  </Link>
                ) : (
                  <Link to="/join" className="w-full">
                    <Button variant="ink" size="md" className="w-full">
                      Return to Onboarding Wizard
                    </Button>
                  </Link>
                )}
                <Link to="/dashboard" className="w-full">
                  <Button variant="paper" size="md" className="w-full">
                    Continue to Dashboard
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Email Verification Component                                       */
/* ------------------------------------------------------------------ */

function extractTokenFromUrl(location) {
  const routerParams = new URLSearchParams(location.search);
  const hashPart = window.location.hash.includes("?") ? window.location.hash.split("?")[1] : "";
  const hashParams = new URLSearchParams(hashPart);
  const searchParams = new URLSearchParams(window.location.search);
  return routerParams.get("token") || hashParams.get("token") || searchParams.get("token") || "";
}

export function VerifyEmail() {
  const nav = useNavigate();
  const location = useLocation();
  const token = extractTokenFromUrl(location);

  const [status, setStatus] = useState(token ? "verifying" : "request"); // verifying | success | error | request
  const [message, setMessage] = useState("");
  const [emailInput, setEmailInput] = useState("");
  const [requestPending, setRequestPending] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [requestError, setRequestError] = useState(null);
  const processedRef = useRef(false);

  useEffect(() => {
    if (!token) {
      setStatus("request");
      return;
    }
    if (processedRef.current) return;
    processedRef.current = true;

    async function doVerify() {
      try {
        const res = await api.verifyEmail({ token });
        setStatus("success");
        setMessage(res.message || "Email verified successfully!");
      } catch (err) {
        setStatus("error");
        setMessage(err?.detail || err?.message || "Invalid or expired verification token.");
      }
    }

    doVerify();
  }, [token]);

  const handleRequestVerification = async (e) => {
    e.preventDefault();
    if (!emailInput.trim()) {
      setRequestError("Please enter your registered email address.");
      return;
    }
    setRequestError(null);
    setRequestPending(true);
    try {
      const res = await api.sendVerification({ email: emailInput.trim() });
      setRequestSent(true);
      setMessage(res.message || "If the account exists, a verification link has been sent.");
    } catch (err) {
      setRequestError(err?.detail || err?.message || "Failed to send verification email.");
    } finally {
      setRequestPending(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper grid-paper px-4 py-10">
      <div className="w-full max-w-md">
        <Panel className="p-7 text-center">
          <div className="flex justify-center">
            <GdgMark size={44} />
          </div>

          <h1 className="mt-5 font-display text-2xl font-extrabold uppercase tracking-tight">
            Email Verification
          </h1>

          {status === "verifying" && (
            <div className="mt-6 flex flex-col items-center gap-3">
              <span className="h-8 w-8 animate-spin rounded-full border-4 border-ink border-t-transparent" />
              <p className="font-mono text-xs uppercase tracking-wider text-ink-soft">
                Verifying your email address…
              </p>
            </div>
          )}

          {status === "success" && (
            <div className="mt-6 space-y-4">
              <div className="border-[3px] border-ink bg-ggreen-light p-4 shadow-[4px_4px_0_0_#101010] text-left">
                <Badge tone="green" dot>Verified</Badge>
                <p className="mt-2 font-display text-base font-bold text-ink">{message}</p>
                <p className="mt-1 font-mono text-xs text-ink-soft">
                  Your email address is now confirmed. You can log into your account and participate in Hacktoberfest.
                </p>
              </div>
              <Button variant="green" size="md" className="w-full" onClick={() => nav("/login")}>
                Proceed to Login →
              </Button>
            </div>
          )}

          {status === "error" && (
            <div className="mt-6 space-y-4 text-left">
              <div className="border-[3px] border-ink bg-gred-light p-4 shadow-[4px_4px_0_0_#101010]">
                <Badge tone="red">Verification Failed</Badge>
                <p className="mt-2 font-mono text-xs text-ink">{message}</p>
                <p className="mt-1 font-mono text-[11px] text-ink-soft">
                  The link may have expired (valid for 30 minutes) or has already been used.
                </p>
              </div>

              <div className="border-[2px] border-ink bg-white p-4">
                <p className="font-display text-sm font-bold uppercase">Request New Link</p>
                <p className="mt-1 text-xs text-ink-soft">
                  Enter your email address to receive a fresh verification link:
                </p>

                {requestSent ? (
                  <div className="mt-3 border-[2px] border-ink bg-ggreen-light p-2 text-xs font-mono font-bold text-ink">
                    ✓ Check your inbox for the new link!
                  </div>
                ) : (
                  <form onSubmit={handleRequestVerification} className="mt-3 space-y-3">
                    <Input
                      type="email"
                      value={emailInput}
                      onChange={(e) => setEmailInput(e.target.value)}
                      placeholder="student@psit.ac.in"
                      className="font-mono text-xs"
                    />
                    {requestError && (
                      <p className="font-mono text-xs font-bold text-gred">▲ {requestError}</p>
                    )}
                    <Button type="submit" variant="yellow" size="sm" loading={requestPending} className="w-full">
                      Send Verification Email →
                    </Button>
                  </form>
                )}
              </div>

              <Link to="/login" className="block text-center font-mono text-xs font-bold uppercase underline">
                ← Back to Login
              </Link>
            </div>
          )}

          {status === "request" && (
            <div className="mt-6 space-y-4 text-left">
              <p className="text-sm text-ink-soft">
                Enter your registered account email address to receive an email verification link.
              </p>

              {requestSent ? (
                <div className="border-[3px] border-ink bg-ggreen-light p-4 shadow-[4px_4px_0_0_#101010]">
                  <Badge tone="green" dot>Email Sent</Badge>
                  <p className="mt-2 font-display text-sm font-bold text-ink">{message}</p>
                  <p className="mt-1 font-mono text-xs text-ink-soft">
                    Check your inbox and click the verification link within 30 minutes.
                  </p>
                  <Link to="/login" className="mt-4 block">
                    <Button variant="paper" size="sm" className="w-full">
                      Return to Login
                    </Button>
                  </Link>
                </div>
              ) : (
                <form onSubmit={handleRequestVerification} className="space-y-4">
                  <Field label="Email address">
                    <Input
                      type="email"
                      value={emailInput}
                      onChange={(e) => setEmailInput(e.target.value)}
                      placeholder="student@psit.ac.in"
                      className="font-mono"
                      autoFocus
                    />
                  </Field>

                  {requestError && (
                    <p className="font-mono text-xs font-bold text-gred">▲ {requestError}</p>
                  )}

                  <Button type="submit" variant="blue" size="lg" loading={requestPending} className="w-full">
                    Send Verification Email →
                  </Button>

                  <Link to="/login" className="block text-center font-mono text-xs font-bold uppercase underline text-ink-soft hover:text-ink">
                    ← Back to Login
                  </Link>
                </form>
              )}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Reset Password Component                                           */
/* ------------------------------------------------------------------ */

export function ResetPassword() {
  const nav = useNavigate();
  const location = useLocation();
  const token = extractTokenFromUrl(location);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);

  // Fallback mode if no token in URL: request reset link / OTP
  const [emailInput, setEmailInput] = useState("");
  const [linkSent, setLinkSent] = useState(false);
  const [linkSentMsg, setLinkSentMsg] = useState("");
  const [linkPending, setLinkPending] = useState(false);
  const [linkError, setLinkError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!token && (!otpCode.trim() || otpCode.trim().length !== 6)) {
      setError("Enter the 6-digit verification code sent to your email.");
      return;
    }
    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    const hasLetter = /[a-zA-Z]/.test(newPassword);
    const hasNonLetter = /[^a-zA-Z]/.test(newPassword);
    if (!hasLetter || !hasNonLetter) {
      setError("Password must include at least one letter and one number or symbol.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setPending(true);
    try {
      await api.resetPassword(
        token
          ? { token, new_password: newPassword }
          : { identifier: emailInput.trim(), otp: otpCode.trim(), new_password: newPassword }
      );
      setSuccess(true);
    } catch (err) {
      setError(err?.detail || err?.message || "Failed to reset password. Please check your verification code.");
    } finally {
      setPending(false);
    }
  };

  const handleSendResetLink = async (e) => {
    e.preventDefault();
    const clean = emailInput.trim();
    if (!clean) {
      setLinkError("Please enter your roll number or email address.");
      return;
    }
    setLinkError(null);
    setLinkPending(true);
    try {
      const res = await api.forgotPassword({ identifier: clean, email: clean });
      setLinkSentMsg(res.message || "Password reset instructions have been sent.");
      setLinkSent(true);
    } catch (err) {
      setLinkError(err?.detail || err?.message || "Failed to send reset link.");
    } finally {
      setLinkPending(false);
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

          <h1 className="mt-6 font-display text-3xl font-extrabold uppercase leading-none tracking-tight">
            {success ? "Reset Password" : (token || linkSent ? "Set New Password" : "Forgot Password")}
          </h1>

          {success ? (
            <div className="mt-6 space-y-4">
              <div className="border-[3px] border-ink bg-ggreen-light p-4 shadow-[4px_4px_0_0_#101010]">
                <Badge tone="green" dot>Success</Badge>
                <p className="mt-2 font-display text-base font-bold text-ink">
                  Password Reset Complete
                </p>
                <p className="mt-1 font-mono text-xs text-ink-soft">
                  Your password has been updated successfully. You can now log in using your new credentials.
                </p>
              </div>
              <Button variant="green" size="lg" className="w-full" onClick={() => nav("/login")}>
                Log in Now →
              </Button>
            </div>
          ) : (token || linkSent) ? (
            <form onSubmit={handleSubmit} className="mt-6 space-y-4">
              {linkSent && !token && linkSentMsg && (
                <div className="border-[2px] border-ink bg-gyellow-light p-3 text-xs font-mono font-bold text-ink">
                  ✉ {linkSentMsg}
                </div>
              )}

              {!token && (
                <Field label="6-Digit Verification Code" hint="check your email inbox">
                  <Input
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.trim())}
                    placeholder="123456"
                    maxLength={6}
                    className="font-mono tracking-widest text-center text-lg font-bold"
                    autoFocus
                  />
                </Field>
              )}

              <Field label="New Password" hint="min. 8 chars with letters & numbers">
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                    className="font-mono pr-14"
                    autoFocus={!!token}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-mono font-bold uppercase text-ink-soft hover:text-ink"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </Field>

              <Field label="Confirm New Password">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  className="font-mono"
                />
              </Field>

              {error && <p className="font-mono text-xs font-bold text-gred">▲ {error}</p>}

              <Button type="submit" variant="green" size="lg" loading={pending} className="w-full">
                Update Password &amp; Save →
              </Button>

              <p className="text-center">
                <Link to="/login" className="font-mono text-xs font-bold uppercase underline text-ink-soft hover:text-ink">
                  ← Back to Login
                </Link>
              </p>
            </form>
          ) : (
            /* No Token: request a reset link / OTP */
            <div className="mt-6 space-y-4">
              <p className="text-sm text-ink-soft">
                Enter your registered PSIT roll number or email address. We will send a 6-digit verification code to your email.
              </p>

              <form onSubmit={handleSendResetLink} className="space-y-4">
                <Field label="Roll Number or Email Address">
                  <Input
                    type="text"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    placeholder="2200320100001 or student@gmail.com"
                    className="font-mono"
                    autoFocus
                  />
                </Field>

                {linkError && <p className="font-mono text-xs font-bold text-gred">▲ {linkError}</p>}

                <Button type="submit" variant="yellow" size="lg" loading={linkPending} className="w-full">
                  Send Reset Code →
                </Button>

                <p className="text-center">
                  <Link to="/login" className="font-mono text-xs font-bold uppercase underline text-ink-soft hover:text-ink">
                    ← Back to Login
                  </Link>
                </p>
              </form>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

