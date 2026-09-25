import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "./api";

/**
 * Minimal data hook — handles loading / error / empty states and optional
 * polling (the backend pushes nothing over websockets; real-time is polling).
 *
 *   const q = useData(() => api.issues(filters), [filters], { pollMs: 30000 });
 */
export function useData(fetcher, deps = [], { pollMs, enabled = true } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    fetcherRef
      .current()
      .then((res) => {
        if (!alive) return;
        setData(res);
        setError(null);
        setLastUpdated(Date.now());
      })
      .catch((e) => {
        if (!alive) return;
        setError(
          e instanceof ApiError
            ? `${e.status}: ${e.detail}`
            : e instanceof Error
              ? e.message
              : "Something went wrong",
        );
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, enabled]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const id = setInterval(() => setTick((t) => t + 1), pollMs);
    return () => clearInterval(id);
  }, [pollMs, enabled]);

  const refetch = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refetch, lastUpdated };
}

/** Simple mutation helper with pending + error state. */
export function useMutation(fn) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const mutate = useCallback(
    async (...args) => {
      setPending(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e) {
        setError(
          e instanceof ApiError
            ? e.detail
            : e instanceof Error
              ? e.message
              : "Request failed",
        );
        return null;
      } finally {
        setPending(false);
      }
    },
    [fn],
  );
  return { mutate, pending, error, setError };
}

export function useDebounced(value, ms = 350) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setV(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return v;
}

/** True while the tick is live — used to flash the "live" pill on feeds. */
export function useHeartbeat(ms = 30000) {
  const [beat, setBeat] = useState(true);
  useEffect(() => {
    const id = setInterval(() => {
      setBeat(false);
      setTimeout(() => setBeat(true), 400);
    }, ms);
    return () => clearInterval(id);
  }, [ms]);
  return beat;
}
