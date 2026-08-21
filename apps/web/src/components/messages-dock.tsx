"use client";

import { useState } from "react";

import { ChevronUpIcon, ComposeIcon, MessageIcon } from "@/components/icons";

/** Sağ altta sabit duran mesajlar çubuğu. */
export function MessagesDock() {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed right-6 bottom-0 z-40 hidden w-[300px] overflow-hidden rounded-t-2xl bg-ns-surface shadow-[0_-4px_30px_-6px_rgb(16_24_40/0.16)] lg:block dark:bg-nsd-surface">
      <div className="flex items-center gap-2 px-4 py-3.5">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex flex-1 items-center gap-2 text-left"
        >
          <MessageIcon className="size-[19px] text-ns-muted dark:text-nsd-subtle" />
          <span className="text-[14.5px] font-medium text-ns-ink dark:text-nsd-ink">Mesajlar</span>
          <ChevronUpIcon
            className={`size-4 text-ns-muted transition-transform dark:text-nsd-subtle ${
              open ? "rotate-180" : ""
            }`}
          />
        </button>
        <button
          type="button"
          aria-label="Yeni mesaj"
          className="flex size-8 items-center justify-center rounded-full text-ns-primary transition-colors hover:bg-ns-hover dark:hover:bg-nsd-hover"
        >
          <ComposeIcon className="size-[19px]" />
        </button>
      </div>

      {open ? (
        <div className="border-t border-ns-line px-4 py-8 text-center text-[13.5px] text-ns-subtle dark:border-nsd-line">
          Henüz mesajınız yok.
        </div>
      ) : null}
    </div>
  );
}
