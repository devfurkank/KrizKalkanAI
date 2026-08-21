import { Avatar } from "@/components/avatar";
import { ChevronDownIcon, ChevronRightIcon, HashIcon, SearchIcon } from "@/components/icons";
import { currentUser, trends } from "@/lib/mock-data";

export function RightRail() {
  return (
    <aside className="sticky top-0 hidden h-dvh w-[298px] shrink-0 flex-col gap-5 overflow-y-auto py-6 no-scrollbar lg:flex">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <SearchIcon className="absolute top-1/2 left-3.5 size-[17px] -translate-y-1/2 text-ns-subtle" />
          <input
            type="search"
            placeholder="Arama yap"
            aria-label="Arama yap"
            className="h-[38px] w-full rounded-full border border-ns-primary/45 bg-transparent pr-4 pl-10 text-[14px] text-ns-ink outline-none placeholder:text-ns-subtle focus:border-ns-primary dark:text-nsd-ink"
          />
        </div>
        <button type="button" className="flex items-center gap-0.5" aria-label="Hesap menüsü">
          <Avatar gradient={currentUser.avatar} size={34} />
          <ChevronDownIcon className="size-4 text-ns-muted dark:text-nsd-subtle" />
        </button>
      </div>

      <section className="rounded-card bg-ns-surface px-4 py-4 card-shadow dark:bg-nsd-surface">
        <header className="flex items-center justify-between px-1">
          <h2 className="text-[16px] font-bold text-ns-ink dark:text-nsd-ink">Popüler</h2>
          <a
            href="#"
            className="flex items-center gap-0.5 text-[12.5px] text-ns-muted hover:text-ns-primary dark:text-nsd-subtle"
          >
            Tümünü gör
            <ChevronRightIcon className="size-3.5" />
          </a>
        </header>

        <ul className="mt-2">
          {trends.map((t) => (
            <li
              key={t.tag}
              className="border-t border-ns-line first:border-t-0 dark:border-nsd-line"
            >
              <a
                href="#"
                className="-mx-1 flex items-center gap-3 rounded-lg px-1 py-3 transition-colors hover:bg-ns-hover dark:hover:bg-nsd-hover"
              >
                <HashIcon className="size-[19px] shrink-0 text-ns-primary" />
                <span className="min-w-0">
                  <span className="block truncate text-[14px] font-semibold text-ns-ink dark:text-nsd-ink">
                    {t.tag}
                  </span>
                  <span className="block text-[12.5px] text-ns-faint">{t.count}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </section>
    </aside>
  );
}
