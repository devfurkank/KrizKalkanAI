"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Logo } from "@/components/logo";
import {
  BellIcon,
  BookmarkIcon,
  CompassIcon,
  GavelIcon,
  HomeFilledIcon,
  MessageIcon,
  MoonIcon,
  NodIcon,
  PenIcon,
  PlayCircleIcon,
  RadarIcon,
  RocketIcon,
  SettingsIcon,
  StarIcon,
  TeknofestIcon,
} from "@/components/icons";
import { useDarkMode } from "@/lib/use-dark-mode";

interface NavItem {
  label: string;
  href: string;
  Icon: (p: { className?: string }) => React.ReactElement;
  badge?: string;
}

const NAV: NavItem[] = [
  { label: "Ana Sayfa", href: "/", Icon: HomeFilledIcon },
  { label: "Kriz Radar", href: "/radar", Icon: RadarIcon },
  { label: "Moderatör", href: "/moderator", Icon: GavelIcon },
  { label: "Bildirimler", href: "#", Icon: BellIcon, badge: "99+" },
  { label: "Mesajlar", href: "#", Icon: MessageIcon },
  { label: "Keşfet", href: "#", Icon: CompassIcon },
  { label: "Nod Oyna", href: "#", Icon: NodIcon },
  { label: "Topluluklar", href: "#", Icon: StarIcon },
  { label: "Kaydedilenler", href: "#", Icon: BookmarkIcon },
  { label: "Beğeniler", href: "#", Icon: RocketIcon },
  { label: "Ayarlar", href: "#", Icon: SettingsIcon },
  { label: "TEKNOFEST Kayıt", href: "#", Icon: TeknofestIcon },
];

function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
        checked ? "bg-ns-primary" : "bg-ns-field dark:bg-nsd-line"
      }`}
    >
      <span
        className={`absolute top-0.5 size-5 rounded-full bg-white shadow-sm transition-all ${
          checked ? "left-[22px]" : "left-0.5"
        }`}
      />
    </button>
  );
}

export function Sidebar({ onNewPost }: { onNewPost: () => void }) {
  const [lowBandwidth, setLowBandwidth] = useState(false);
  const [dark, setDark] = useDarkMode();
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-dvh w-[262px] shrink-0 flex-col gap-1 overflow-y-auto py-7 no-scrollbar">
      <div className="mb-6 pl-3">
        <Link href="/" aria-label="Ana sayfa">
          <Logo />
        </Link>
      </div>

      <nav className="flex flex-col gap-0.5">
        {NAV.map(({ label, href, Icon, badge }) => {
          const active = href !== "#" && pathname === href;
          return (
            <Link
              key={label}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`group flex items-center gap-3 rounded-full py-2 pr-4 pl-2.5 text-[15px] transition-colors ${
                active
                  ? "bg-ns-hover font-semibold text-ns-ink dark:bg-nsd-hover dark:text-nsd-ink"
                  : "font-normal text-ns-ink hover:bg-ns-hover dark:text-nsd-body dark:hover:bg-nsd-hover"
              }`}
            >
              <span className="relative">
                <span
                  className={`flex size-9 items-center justify-center rounded-xl ${
                    active ? "bg-ns-primary-soft dark:bg-ns-primary/20" : ""
                  }`}
                >
                  <Icon
                    className={`size-[22px] ${
                      active ? "text-ns-primary" : "text-ns-ink dark:text-nsd-body"
                    }`}
                  />
                </span>
                {badge ? (
                  <span className="absolute -top-0.5 left-0 rounded-full bg-ns-primary px-1 text-[9px] leading-[14px] font-semibold text-white">
                    {badge}
                  </span>
                ) : null}
              </span>
              {label}
            </Link>
          );
        })}
      </nav>

      <button
        type="button"
        onClick={onNewPost}
        className="mt-3 flex h-[42px] w-[212px] items-center justify-center gap-2 rounded-full bg-gradient-to-r from-ns-grad-from to-ns-grad-to text-[15px] font-semibold text-white shadow-sm transition-opacity hover:opacity-92"
      >
        <PenIcon className="size-[18px]" />
        Yeni Gönderi
      </button>

      <div className="mt-6 w-[212px] border-t border-ns-line pt-5 dark:border-nsd-line" />

      <div className="flex w-[212px] flex-col gap-1">
        {/* Düşük bant genişliği modu: afet bölgesinde şebeke çökebilir. */}
        <div className="flex items-center justify-between rounded-full py-2 pr-2 pl-2.5">
          <span className="flex items-center gap-3 text-[15px] text-ns-ink dark:text-nsd-body">
            <PlayCircleIcon className="size-[22px]" />
            Düşük bant modu
          </span>
          <Switch
            checked={lowBandwidth}
            onChange={setLowBandwidth}
            label="Düşük bant genişliği modu"
          />
        </div>
        <div className="flex items-center justify-between rounded-full py-2 pr-2 pl-2.5">
          <span className="flex items-center gap-3 text-[15px] text-ns-ink dark:text-nsd-body">
            <MoonIcon className="size-[22px]" />
            Karanlık mod
          </span>
          <Switch checked={dark} onChange={setDark} label="Karanlık mod" />
        </div>
      </div>
    </aside>
  );
}
