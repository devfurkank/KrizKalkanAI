"use client";

import { useEffect, useRef, useState } from "react";

import { AudienceMenu } from "@/components/audience-menu";
import { Avatar } from "@/components/avatar";
import {
  CalendarIcon,
  CloseIcon,
  GifIcon,
  GlobeIcon,
  ImageIcon,
  InfoIcon,
  PenIcon,
  PollIcon,
  SmileIcon,
} from "@/components/icons";
import { audienceOptions, currentUser, type Audience } from "@/lib/mock-data";

const MAX = 10000;
const TOOLS = [
  { Icon: ImageIcon, label: "Görsel ekle" },
  { Icon: PollIcon, label: "Anket ekle" },
  { Icon: InfoIcon, label: "Bilgi" },
  { Icon: SmileIcon, label: "Emoji" },
  { Icon: CalendarIcon, label: "Zamanla" },
  { Icon: GifIcon, label: "GIF ekle" },
];

function Toolbar({
  value,
  audience,
  onAudience,
  expanded,
}: {
  value: string;
  audience: Audience;
  onAudience: (v: Audience) => void;
  expanded: boolean;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const current = audienceOptions.find((o) => o.value === audience)!;
  const canSend = value.trim().length > 0;

  return (
    <div className="flex items-center gap-1">
      {TOOLS.map(({ Icon, label }) => (
        <button
          key={label}
          type="button"
          title={label}
          aria-label={label}
          className="flex size-8 items-center justify-center rounded-full text-ns-muted transition-colors hover:bg-ns-hover hover:text-ns-primary dark:text-nsd-subtle dark:hover:bg-nsd-hover"
        >
          <Icon className="size-[19px]" />
        </button>
      ))}

      {expanded ? (
        <>
          <span className="mx-2 h-5 w-px bg-ns-line dark:bg-nsd-line" />
          <span className="text-[13px] text-ns-subtle tabular-nums">
            {value.length}/{MAX}
          </span>
        </>
      ) : null}

      <div className="ml-auto flex items-center gap-2">
        {expanded ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[13.5px] text-ns-body transition-colors hover:bg-ns-hover dark:text-nsd-body dark:hover:bg-nsd-hover"
            >
              <GlobeIcon className="size-[17px] text-ns-muted dark:text-nsd-subtle" />
              {current.label}
            </button>
            {menuOpen ? (
              <AudienceMenu
                value={audience}
                onSelect={onAudience}
                onClose={() => setMenuOpen(false)}
              />
            ) : null}
          </div>
        ) : null}

        <button
          type="button"
          disabled={!canSend}
          className={`flex items-center gap-1.5 rounded-full px-4 py-[7px] text-[13.5px] font-medium transition-all ${
            canSend
              ? "bg-gradient-to-r from-ns-grad-from to-ns-grad-to text-white hover:opacity-92"
              : "cursor-default bg-ns-field text-ns-muted dark:bg-nsd-line dark:text-nsd-subtle"
          }`}
        >
          <PenIcon className="size-[15px]" />
          Gönder
        </button>
      </div>
    </div>
  );
}

/** Akış içindeki gönderi oluşturma kartı: odaklanınca genişler. */
export function InlineComposer() {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const [audience, setAudience] = useState<Audience>("herkes");
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const expanded = focused || value.length > 0;

  return (
    <div className="rounded-card bg-ns-surface px-5 pt-4 pb-3.5 card-shadow dark:bg-nsd-surface">
      <div className="flex gap-3">
        <Avatar gradient={currentUser.avatar} size={38} />
        <textarea
          ref={areaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onFocus={() => setFocused(true)}
          maxLength={MAX}
          rows={expanded ? 3 : 1}
          placeholder="Gönderi oluşturmak için..."
          className="mt-1.5 min-w-0 flex-1 resize-none bg-transparent text-[15px] text-ns-ink outline-none placeholder:text-ns-subtle dark:text-nsd-ink"
        />
        {expanded ? (
          <button
            type="button"
            aria-label="Kapat"
            onClick={() => {
              setValue("");
              setFocused(false);
              areaRef.current?.blur();
            }}
            className="flex size-6 shrink-0 items-center justify-center self-start rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
          >
            <CloseIcon className="size-3.5" />
          </button>
        ) : null}
      </div>

      <div className="mt-3">
        <Toolbar value={value} audience={audience} onAudience={setAudience} expanded={expanded} />
      </div>
    </div>
  );
}

/** "Yeni Gönderi" düğmesiyle açılan kip (modal). */
export function ComposerModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [value, setValue] = useState("");
  const [audience, setAudience] = useState<Audience>("herkes");

  // Kip açıkken Escape kapatır ve arka plan kaydırması durdurulur.
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#8E93A3]/45 px-4 backdrop-blur-[2px]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Gönderi Oluştur"
        className="w-full max-w-[712px] rounded-[18px] bg-ns-surface px-6 pt-5 pb-4 shadow-[0_24px_70px_-12px_rgb(16_24_40/0.3)] dark:bg-nsd-surface"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-[19px] font-bold text-ns-ink dark:text-nsd-ink">Gönderi Oluştur</h2>
          <button
            type="button"
            aria-label="Kapat"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
          >
            <CloseIcon className="size-[17px]" />
          </button>
        </div>

        <div className="mt-5 flex gap-3">
          <Avatar gradient={currentUser.avatar} size={38} />
          <textarea
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            maxLength={MAX}
            rows={3}
            placeholder="Gönderi oluşturmak için..."
            className="mt-1.5 min-w-0 flex-1 resize-none bg-transparent text-[15px] text-ns-ink outline-none placeholder:text-ns-subtle dark:text-nsd-ink"
          />
        </div>

        <div className="mt-4">
          <Toolbar value={value} audience={audience} onAudience={setAudience} expanded />
        </div>
      </div>
    </div>
  );
}
