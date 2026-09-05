"use client";

import { useEffect } from "react";

import { EvidenceList } from "@/components/evidence-list";
import { BanIcon, CloseIcon, SparkIcon } from "@/components/icons";
import type { AnalysisResult } from "@/lib/types";
import { VERDICT_STYLE, confidencePercent } from "@/lib/verdict";

/**
 * Akış 2 — paylaşım öncesi sürtünme ekranı (Seviye 3).
 *
 * Paylaşım hiçbir koşulda engellenmez; yalnızca bir adım eklenir. "Yine de
 * paylaş" düğmesi her zaman etkindir ve görsel olarak bastırılmaz — karar
 * kullanıcınındır (rapor 3.3).
 */
export function FrictionScreen({
  analysis,
  onProceed,
  onCancel,
}: {
  analysis: AnalysisResult;
  onProceed: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onCancel]);

  const style = VERDICT_STYLE[analysis.verdict];

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#8E93A3]/50 px-4 backdrop-blur-[2px]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="surtunme-baslik"
        className="max-h-[88vh] w-full max-w-[600px] overflow-y-auto rounded-[18px] bg-ns-surface px-6 pt-5 pb-5 shadow-[0_24px_70px_-12px_rgb(16_24_40/0.3)] dark:bg-nsd-surface"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className={`mt-0.5 rounded-lg p-2 ${style.chip}`}>
              <SparkIcon className={`size-[20px] ${style.text}`} />
            </span>
            <div>
              <h2
                id="surtunme-baslik"
                className="text-[18px] font-bold text-ns-ink dark:text-nsd-ink"
              >
                Paylaşmadan önce bir saniye
              </h2>
              <p className="mt-1 text-[14px] leading-relaxed text-ns-body dark:text-nsd-body">
                {analysis.intervention.headline}
              </p>
              <p className="mt-1 text-[12.5px] text-ns-muted dark:text-nsd-subtle">
                {style.short} · güven {confidencePercent(analysis.confidence)} (
                {analysis.confidence_label})
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Kapat"
            onClick={onCancel}
            className="flex size-8 shrink-0 items-center justify-center rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
          >
            <CloseIcon className="size-[17px]" />
          </button>
        </div>

        <div className="mt-4 rounded-xl bg-ns-hover px-4 py-3 dark:bg-nsd-hover">
          <EvidenceList analysis={analysis} />
        </div>

        <div className="mt-4 flex items-center gap-2 text-[12px] text-ns-muted dark:text-nsd-subtle">
          <BanIcon className="size-4 shrink-0" />
          <span>
            Bu ekran paylaşımı engellemez. İçerik kaldırılmadı ve kaldırılmayacak; karar sizindir.
          </span>
        </div>

        <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onProceed}
            className="h-11 rounded-full border border-ns-line px-5 text-[14px] font-medium text-ns-body transition-colors hover:bg-ns-hover dark:border-nsd-line dark:text-nsd-body dark:hover:bg-nsd-hover"
          >
            Yine de paylaş
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="h-11 rounded-full bg-gradient-to-r from-ns-grad-from to-ns-grad-to px-6 text-[14px] font-semibold text-white transition-opacity hover:opacity-92"
          >
            Vazgeç
          </button>
        </div>
      </div>
    </div>
  );
}
