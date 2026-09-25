/**
 * Auth state management — JWT session + role-based protected routes.
 * The login endpoint returns { access_token, token_type, expires_in, user }.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, tokenStore } from "./api";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  /** True while a saved JWT is being re-validated on mount. */
  const [bootstrapping, setBootstrapping] = useState(true);

  /**
   * Session restore: a page refresh would otherwise wipe the in-memory user and
   * bounce a legitimately logged-in student back to /login.
   */
  useEffect(() => {
    const token = tokenStore.get();
    if (!token || tokenStore.isExpired()) {
      tokenStore.clear();
      setBootstrapping(false);
      return;
    }
    let alive = true;
    api
      .me()
      .then((u) => {
        if (alive) setUser(u);
      })
      .catch(() => {
        tokenStore.clear();
      })
      .finally(() => {
        if (alive) setBootstrapping(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (identifier) => {
    const session = await api.login({ identifier });
    tokenStore.set(session.access_token, session.expires_in);
    setUser(session.user);
    return session.user;
  }, []);

  const setSessionUser = useCallback((u) => setUser(u), []);
  const refreshUser = useCallback(async () => {
    const u = await api.me();
    setUser(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      role: user?.role ?? null,
      isAuthenticated: !!user,
      loading: bootstrapping,
      login,
      logout,
      refreshUser,
      setSessionUser,
    }),
    [user, bootstrapping, login, logout, refreshUser, setSessionUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Shown while a saved JWT is re-validated, so we never redirect a logged-in user. */
function AuthBootLoader() {
  return (
    <div className="grid-paper flex min-h-screen flex-col items-center justify-center gap-4 bg-paper">
      <span className="h-9 w-9 animate-spin rounded-full border-4 border-ink border-t-transparent" />
      <p className="font-mono text-[11px] font-bold uppercase tracking-[0.2em]">Restoring session…</p>
    </div>
  );
}

/** Role-based protected route. Redirects to /login when needed. */
export function RequireRole({ roles, children }) {
  const { isAuthenticated, user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <AuthBootLoader />;
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && user && !roles.includes(user.role)) return <Navigate to="/dashboard/403" replace />;
  return <>{children}</>;
}
