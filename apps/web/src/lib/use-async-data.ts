"use client";

import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Sunucudan veri çeken kanca.
 *
 * Durum güncellemeleri yalnızca söz (promise) geri çağrılarında yapılır; effect
 * gövdesinde senkron setState çağrılmaz. Bileşen sökülürse sonuç yok sayılır.
 *
 * `fetcher` kararlı olmalıdır (useCallback ile sarılmış) ve yalnızca veri
 * döndürmelidir — içinde durum güncellemesi yapmamalıdır.
 */
export function useAsyncData<T>(fetcher: () => Promise<T>, options: { intervalMs?: number } = {}) {
  const { intervalMs } = options;
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
  });
  const [token, setToken] = useState(0);

  useEffect(() => {
    let cancelled = false;

    const run = () =>
      fetcher().then(
        (data) => {
          if (!cancelled) setState({ data, error: null, loading: false });
        },
        (err: unknown) => {
          if (!cancelled) {
            setState((prev) => ({
              ...prev,
              loading: false,
              error: err instanceof Error ? err.message : "Veri alınamadı",
            }));
          }
        },
      );

    // İlk çağrı bir mikro görevde yapılır; effect gövdesi senkron olarak
    // durum güncellemez.
    const timer = setTimeout(run, 0);
    const interval = intervalMs ? setInterval(run, intervalMs) : undefined;

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (interval) clearInterval(interval);
    };
  }, [fetcher, token, intervalMs]);

  const reload = useCallback(() => setToken((t) => t + 1), []);

  return { ...state, reload };
}
