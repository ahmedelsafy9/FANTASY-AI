import { useEffect, useRef, useState, useCallback } from "react";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Runs an async fetcher on mount (and whenever `deps` change), exposing
 * loading/error/data state explicitly. On failure, `data` stays `null` and
 * `error` is set — callers must render an `ErrorState`, never silently
 * substitute fake data.
 */
export function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const run = useCallback(() => {
    const currentId = ++requestId.current;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (requestId.current === currentId) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (requestId.current === currentId) {
          const message =
            (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
            (err instanceof Error ? err.message : "Something went wrong.");
          setError(message);
          setLoading(false);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]);

  return { data, loading, error, refetch: run };
}
