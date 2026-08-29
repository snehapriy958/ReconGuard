"use client";

import { useEffect, useState, useCallback } from "react";
import { ApiError } from "./api-client";

export type FetchState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError | Error }
  | { status: "success"; data: T };

/**
 * Wraps a single API call with loading/error/success states, matching
 * Phase 6.1's requirement for consistent handling across screens rather
 * than each component managing its own ad-hoc isLoading/error booleans.
 * `deps` works like useEffect's dependency array — refetches when it changes.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList = []
): FetchState<T> & { refetch: () => void } {
  const [state, setState] = useState<FetchState<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);

  const load = useCallback(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: "success", data });
      })
      .catch((error) => {
        if (!cancelled) setState({ status: "error", error });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  useEffect(() => {
    const cancel = load();
    return cancel;
  }, [load]);

  return { ...state, refetch: () => setTick((t) => t + 1) };
}
