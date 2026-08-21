"use client";

import { useSyncExternalStore } from "react";

/**
 * Karanlık mod durumu <html> üzerindeki .dark sınıfında tutulur; bu sınıf
 * hidrasyondan önce layout'taki satır içi betikle uygulanır.
 *
 * DOM harici bir kaynak olduğu için durum useSyncExternalStore ile okunur:
 * effect içinde setState çağırmadan sunucu/istemci tutarlılığı sağlanır.
 */
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function useDarkMode() {
  const dark = useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains("dark"),
    () => false,
  );

  function setDark(next: boolean) {
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("ns-theme", next ? "dark" : "light");
    } catch {
      // Depolama erişilemiyorsa tema yalnızca bu oturumda geçerli olur.
    }
    for (const cb of listeners) cb();
  }

  return [dark, setDark] as const;
}
