import { stories } from "@/lib/mock-data";

/** Composer altındaki hikâye/öne çıkan hesaplar şeridi. */
export function StoriesRow() {
  return (
    <div className="flex gap-4 px-5 py-4">
      {stories.map((s) => (
        <button key={s.id} type="button" className="flex w-[68px] flex-col items-center gap-1.5">
          <span className="rounded-full bg-gradient-to-tr from-ns-grad-to to-ns-grad-from p-[2px]">
            <span className="block rounded-full bg-ns-surface p-[2px] dark:bg-nsd-surface">
              <span className={`block size-[54px] rounded-full bg-gradient-to-br ${s.avatar}`} />
            </span>
          </span>
          <span className="w-full truncate text-center text-[11.5px] text-ns-body dark:text-nsd-subtle">
            {s.label}
          </span>
        </button>
      ))}
    </div>
  );
}
