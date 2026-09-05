"use client";

import { useId, useState } from "react";

import {
  BanIcon,
  CheckCircleIcon,
  ChevronDownIcon,
  ClockRewindIcon,
  LifeBuoyIcon,
  MegaphoneIcon,
  QuestionIcon,
  ScissorsIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/icons";
import { EvidenceList } from "@/components/evidence-list";
import type { AnalysisResult } from "@/lib/types";
import { LEVEL_LABEL, VERDICT_STYLE, confidencePercent } from "@/lib/verdict";
import type { VerdictIcon } from "@/lib/verdict";

const ICONS: Record<VerdictIcon, (p: { className?: string }) => React.ReactElement> = {
  context: ClockRewindIcon,
  unverified: QuestionIcon,
  synthetic: SparkIcon,
  manipulated: ScissorsIcon,
  provocative: MegaphoneIcon,
  clean: CheckCircleIcon,
  unknown: QuestionIcon,
};

/**
 * Analiz kartı — kullanıcıya gösterilen bağlam kartı.
 *
 * Varsayılan görünüm tek cümlelik özettir; "Neden?" ile kanıt paneli açılır.
 * Bu, bilgi yükünü yönetirken şeffaflıktan ödün vermez (rapor 3.3).
 */
export function AnalysisCard({
  analysis,
  onAppeal,
  compact = false,
}: {
  analysis: AnalysisResult;
  onAppeal?: () => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  const { intervention: iv } = analysis;

  // ── Kural 0: yardım çağrısı koruması ──
  if (iv.protected_by_rule_zero) {
    return (
      <div className="mt-3 rounded-xl border border-emerald-300 bg-emerald-50/70 px-4 py-3 dark:border-emerald-500/40 dark:bg-emerald-500/10">
        <div className="flex items-start gap-2.5">
          <LifeBuoyIcon className="mt-0.5 size-[18px] shrink-0 text-emerald-700 dark:text-emerald-400" />
          <div className="min-w-0">
            <p className="text-[13.5px] font-semibold text-emerald-800 dark:text-emerald-300">
              Yardım çağrısı — Kural 0 ile korundu
            </p>
            <p className="mt-0.5 text-[12.5px] leading-relaxed text-emerald-800/80 dark:text-emerald-300/80">
              {iv.detail}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const style = VERDICT_STYLE[analysis.verdict];
  const Icon = ICONS[style.icon];

  return (
    <div className={`mt-3 overflow-hidden rounded-xl border ${style.ring} ${style.chip}`}>
      <div className="flex items-start gap-2.5 px-4 py-3">
        <Icon className={`mt-0.5 size-[18px] shrink-0 ${style.text}`} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {/* Renk tek gösterge değildir: ikon + metin etiketi zorunlu. */}
            <span className={`text-[13.5px] font-semibold ${style.text}`}>{style.short}</span>
            <span className="text-[11.5px] text-ns-muted dark:text-nsd-subtle">
              güven {confidencePercent(analysis.confidence)} · {analysis.confidence_label}
            </span>
            <span className="text-[11.5px] text-ns-faint">{LEVEL_LABEL[iv.level]}</span>
          </div>

          <p className="mt-1 text-[13.5px] leading-relaxed text-ns-body dark:text-nsd-body">
            {iv.headline}
          </p>

          {!compact && iv.detail ? (
            <p className="mt-1 text-[12.5px] leading-relaxed text-ns-muted dark:text-nsd-subtle">
              {iv.detail}
            </p>
          ) : null}

          <div className="mt-2 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-controls={panelId}
              className={`flex items-center gap-1 text-[12.5px] font-semibold ${style.text} hover:underline`}
            >
              Neden?
              <ChevronDownIcon
                className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`}
              />
            </button>

            {onAppeal ? (
              <button
                type="button"
                onClick={onAppeal}
                className="text-[12.5px] text-ns-muted underline-offset-2 hover:underline dark:text-nsd-subtle"
              >
                İtiraz et
              </button>
            ) : null}

            <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-ns-faint">
              <BanIcon className="size-3.5" />
              İçerik kaldırılmadı
            </span>
          </div>
        </div>
      </div>

      {open ? (
        <div
          id={panelId}
          className="border-t border-black/5 bg-white/70 px-4 py-3 dark:border-white/10 dark:bg-black/20"
        >
          <EvidenceList analysis={analysis} />
        </div>
      ) : null}
    </div>
  );
}

/** Seviye 1 — yalnızca alt bilgi satırı. */
export function FootnoteBar({ analysis }: { analysis: AnalysisResult }) {
  return (
    <div className="mt-2 flex items-center gap-2 text-[12.5px] text-ns-muted dark:text-nsd-subtle">
      <ShieldIcon className="size-4 shrink-0 text-ns-primary" />
      <span>{analysis.intervention.headline}</span>
    </div>
  );
}
