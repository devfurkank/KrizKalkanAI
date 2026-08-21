"use client";

import { useEffect, useRef } from "react";

import { AtIcon, GlobeIcon, UsersIcon } from "@/components/icons";
import { audienceOptions, type Audience } from "@/lib/mock-data";

const ICONS = { herkes: GlobeIcon, takipciler: UsersIcon, belirli: AtIcon } as const;

export function AudienceMenu({
  value,
  onSelect,
  onClose,
}: {
  value: Audience;
  onSelect: (v: Audience) => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!ref.current?.contains(e.target as Node)) onClose();
    }
    // Yakalama fazında dinlenir: Escape önce menüyü kapatmalı, olayı
    // kipin (modal) dinleyicisine iletmemeli.
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      e.stopPropagation();
      onClose();
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey, true);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      role="menu"
      className="absolute top-[calc(100%+10px)] left-0 z-50 w-[302px] overflow-hidden rounded-2xl bg-white py-2 shadow-[0_8px_40px_-6px_rgb(16_24_40/0.22)] dark:bg-nsd-surface"
    >
      {audienceOptions.map((opt) => {
        const Icon = ICONS[opt.value];
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="menuitemradio"
            aria-checked={selected}
            onClick={() => {
              onSelect(opt.value);
              onClose();
            }}
            className={`flex w-full items-start gap-3 px-4 py-2.5 text-left transition-colors ${
              selected
                ? "bg-[#F1F1FE] dark:bg-ns-primary/15"
                : "hover:bg-ns-hover dark:hover:bg-nsd-hover"
            }`}
          >
            <Icon
              className={`mt-0.5 size-[18px] shrink-0 ${
                selected ? "text-ns-primary" : "text-ns-muted dark:text-nsd-subtle"
              }`}
            />
            <span className="min-w-0">
              <span
                className={`block text-[14px] font-semibold ${
                  selected ? "text-ns-primary" : "text-ns-ink dark:text-nsd-ink"
                }`}
              >
                {opt.label}
              </span>
              <span className="block text-[12.5px] text-ns-subtle">{opt.description}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
