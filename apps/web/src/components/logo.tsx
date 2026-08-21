/** NSosyal "N" logosu — degrade dolgulu, altında BETA etiketi. */
export function Logo({ tone = "dark" }: { tone?: "dark" | "light" }) {
  return (
    <div className="flex w-fit flex-col items-center gap-1">
      <svg width="46" height="46" viewBox="0 0 100 100" aria-label="NSosyal">
        <defs>
          <linearGradient id="ns-logo" x1="0" y1="0" x2="1" y2="0.35">
            <stop offset="0%" stopColor="#61B9DE" />
            <stop offset="52%" stopColor="#4F86E8" />
            <stop offset="100%" stopColor="#4467EF" />
          </linearGradient>
        </defs>
        <path d="M8 92V8h23l38 55V8h23v84H69L31 37v55z" fill="url(#ns-logo)" />
      </svg>
      <span
        className={`text-[10px] font-medium tracking-[0.32em] ${
          tone === "dark" ? "text-ns-ink dark:text-nsd-ink" : "text-white"
        }`}
      >
        BETA
      </span>
    </div>
  );
}
