import { BanIcon, CheckCircleIcon, QuestionIcon } from "@/components/icons";
import type { AnalysisResult, Signal } from "@/lib/types";

/**
 * Kanıt paneli.
 *
 * Açıklama skordan değil, kanıt grafından üretilir (rapor 2.2 · Y5).
 * Çekinilen sinyaller de gösterilir: sistemin neyi bilmediği, ne bildiği
 * kadar önemlidir (rapor 2.2 · Y2).
 */
export function EvidenceList({ analysis }: { analysis: AnalysisResult }) {
  const active = analysis.signals.filter((s) => !s.abstained);
  const abstained = analysis.signals.filter((s) => s.abstained);

  return (
    <div className="space-y-3">
      <p className="text-[10.5px] font-semibold tracking-[0.14em] text-ns-muted dark:text-nsd-subtle">
        KANITLAR
      </p>

      <ul className="space-y-2.5">
        {active.map((signal) => (
          <SignalRow key={signal.key} signal={signal} />
        ))}
        {abstained.map((signal) => (
          <SignalRow key={signal.key} signal={signal} />
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-black/5 pt-2.5 text-[11px] text-ns-faint dark:border-white/10">
        <span>
          Çalışan modüller:{" "}
          <strong className="font-medium">{analysis.modules_run.join(" · ")}</strong>
        </span>
        {analysis.modules_skipped.length > 0 ? (
          <span>Atlanan: {analysis.modules_skipped.join(" · ")}</span>
        ) : null}
        <span>{analysis.latency_ms.toFixed(1)} ms</span>
        {analysis.cache_hit ? <span>önbellekten</span> : null}
        <span className="inline-flex items-center gap-1">
          <BanIcon className="size-3" />
          kaldırılan içerik: 0
        </span>
      </div>

      {analysis.skip_reason ? (
        <p className="text-[11px] leading-relaxed text-ns-faint">{analysis.skip_reason}</p>
      ) : null}
    </div>
  );
}

function SignalRow({ signal }: { signal: Signal }) {
  const muted = signal.abstained;
  return (
    <li className="flex items-start gap-2.5">
      {muted ? (
        <QuestionIcon className="mt-0.5 size-[15px] shrink-0 text-ns-faint" />
      ) : (
        <CheckCircleIcon className="mt-0.5 size-[15px] shrink-0 text-ns-primary" />
      )}

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span
            className={`text-[12.5px] font-medium ${
              muted ? "text-ns-faint" : "text-ns-ink dark:text-nsd-ink"
            }`}
          >
            {signal.label}
          </span>
          <span className="text-[10.5px] text-ns-faint">{signal.module}</span>
          {!muted ? (
            <span className="text-[10.5px] tabular-nums text-ns-muted dark:text-nsd-subtle">
              {signal.score.toFixed(2)}
            </span>
          ) : null}
        </div>

        {muted ? (
          <p className="text-[12px] leading-relaxed text-ns-faint">{signal.abstain_reason}</p>
        ) : (
          signal.evidence.map((e, i) => (
            <p key={i} className="text-[12px] leading-relaxed text-ns-body dark:text-nsd-subtle">
              {e.label}
              {e.locator ? (
                <span className="ml-1.5 rounded bg-black/5 px-1.5 py-px text-[10.5px] text-ns-muted dark:bg-white/10 dark:text-nsd-subtle">
                  {e.locator}
                </span>
              ) : null}
              {e.detail ? (
                <span className="block text-[11px] text-ns-faint">{e.detail}</span>
              ) : null}
            </p>
          ))
        )}
      </div>
    </li>
  );
}
