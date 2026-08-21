"use client";

import { useState } from "react";

const TABS = ["Akış", "Medya"] as const;

export function FeedTabs() {
  const [active, setActive] = useState<(typeof TABS)[number]>("Akış");

  return (
    <div role="tablist" className="mx-auto flex w-[82%] min-w-0">
      {TABS.map((tab) => {
        const selected = tab === active;
        return (
          <button
            key={tab}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => setActive(tab)}
            className={`relative flex-1 pb-3.5 text-[15px] transition-colors ${
              selected
                ? "font-semibold text-ns-primary"
                : "text-ns-subtle hover:text-ns-body dark:hover:text-nsd-body"
            }`}
          >
            {tab}
            <span
              className={`absolute inset-x-0 bottom-0 h-[3px] rounded-full ${
                selected ? "bg-ns-primary" : "bg-transparent"
              }`}
            />
          </button>
        );
      })}
    </div>
  );
}
