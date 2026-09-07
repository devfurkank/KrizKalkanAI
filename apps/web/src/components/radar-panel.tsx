"use client";

import { useCallback } from "react";

import { BanIcon, LifeBuoyIcon, RadarIcon, RefreshIcon } from "@/components/icons";
import { OfflineNotice } from "@/components/offline-notice";
import { getMetrics, getRadar } from "@/lib/api";
import type { RadarSnapshot, SystemMetrics } from "@/lib/types";
import { useAsyncData } from "@/lib/use-async-data";
import { VERDICT_STYLE } from "@/lib/verdict";

const OFFICIAL_LABEL: Record<string, string> = {
  ÇELİŞİYOR: "resmî kaynak yalanlıyor",
  DESTEKLİYOR: "resmî kaynak doğruluyor",
  İLGİSİZ: "ilgili kayıt yok",
  RESMÎ_KAYNAK_SESSİZ: "resmî kaynak henüz sessiz",
};

/** Akış 5 — Kriz Radar, kurumsal karar destek paneli (M8). */
export function RadarPanel() {
  const fetchAll = useCallback(async (): Promise<{
    snapshot: RadarSnapshot;
    metrics: SystemMetrics;
  }> => {
    const [snapshot, metrics] = await Promise.all([getRadar(30), getMetrics()]);
    return { snapshot, metrics };
  }, []);

  // Panel canlıdır: 15 saniyede bir kendini tazeler.
  const { data, error, reload } = useAsyncData(fetchAll, { intervalMs: 15_000 });
  const snapshot = data?.snapshot ?? null;
  const metrics = data?.metrics ?? null;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-[22px] font-bold text-ns-ink dark:text-nsd-ink">
            <RadarIcon className="size-6 text-ns-primary" />
            Kriz Radar
          </h1>
          <p className="mt-1 text-[13.5px] text-ns-muted dark:text-nsd-subtle">
            Son {snapshot?.window_minutes ?? 30} dakika · kurumsal karar destek
          </p>
        </div>
        <button
          type="button"
          onClick={reload}
          className="inline-flex items-center gap-1.5 rounded-full border border-ns-line px-3.5 py-1.5 text-[12.5px] text-ns-body transition-colors hover:bg-ns-hover dark:border-nsd-line dark:text-nsd-body dark:hover:bg-nsd-hover"
        >
          <RefreshIcon className="size-3.5" />
          Yenile
        </button>
      </header>

      {error ? <OfflineNotice message={error} onRetry={reload} /> : null}

      {snapshot ? (
        <>
          {/* ── Sayaçlar ── */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <Tile label="Analiz edilen" value={snapshot.analyzed_count} />
            <Tile label="Etiketlenen" value={snapshot.labelled_count} />
            <Tile label="Yanlış bağlam" value={snapshot.wrong_context} />
            <Tile label="Doğrulanmamış" value={snapshot.unverified} />
            <Tile label="Sentetik (yüksek güven)" value={snapshot.high_confidence_synthetic} />
          </div>

          {/* ── İki kalıcı sayaç: panelde her zaman görünür ── */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-3 rounded-card bg-emerald-50 px-5 py-4 card-shadow dark:bg-emerald-500/10">
              <LifeBuoyIcon className="size-6 shrink-0 text-emerald-700 dark:text-emerald-400" />
              <div>
                <p className="text-[22px] font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
                  {snapshot.protected_help_calls}
                </p>
                <p className="text-[12px] text-emerald-800/80 dark:text-emerald-300/80">
                  yardım çağrısı Kural 0 ile korundu — hiçbir kısıtlama uygulanmadı
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-card bg-ns-surface px-5 py-4 card-shadow dark:bg-nsd-surface">
              <BanIcon className="size-6 shrink-0 text-ns-muted dark:text-nsd-subtle" />
              <div>
                <p className="text-[22px] font-bold tabular-nums text-ns-ink dark:text-nsd-ink">
                  {snapshot.removed_content}
                </p>
                <p className="text-[12px] text-ns-muted dark:text-nsd-subtle">
                  içerik kaldırıldı — sistemde silme yetkisi yoktur
                </p>
              </div>
            </div>
          </div>

          {/* ── İddia kümeleri ── */}
          <section className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
            <h2 className="border-b border-ns-line px-5 py-3 text-[14px] font-semibold text-ns-ink dark:border-nsd-line dark:text-nsd-ink">
              En hızlı yayılan iddialar
            </h2>
            {snapshot.clusters.length === 0 ? (
              <p className="px-5 py-8 text-center text-[13.5px] text-ns-subtle">
                Bu pencerede kümelenecek iddia bulunmuyor.
              </p>
            ) : (
              <ul>
                {snapshot.clusters.map((c) => {
                  const style = VERDICT_STYLE[c.verdict];
                  const width = Math.min(100, (c.spread_per_minute / 10) * 100);
                  return (
                    <li
                      key={c.id}
                      className="border-t border-ns-line px-5 py-3.5 first:border-t-0 dark:border-nsd-line"
                    >
                      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                        <span className={`size-2 shrink-0 rounded-full ${style.dot}`} />
                        <span className="text-[13.5px] font-medium text-ns-ink dark:text-nsd-ink">
                          {c.claim}
                        </span>
                        <span className={`text-[11.5px] ${style.text}`}>{style.short}</span>
                        <span className="ml-auto text-[12px] tabular-nums text-ns-body dark:text-nsd-body">
                          {c.post_count} paylaşım · {c.spread_per_minute}/dk
                        </span>
                      </div>

                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ns-hover dark:bg-nsd-hover">
                        <div
                          className={`h-full rounded-full ${style.dot}`}
                          style={{ width: `${width}%` }}
                        />
                      </div>

                      <p className="mt-1.5 text-[11.5px] text-ns-muted dark:text-nsd-subtle">
                        {OFFICIAL_LABEL[c.official_status] ?? c.official_status}
                        {c.locations.length > 0 ? ` · ${c.locations.join(", ")}` : ""}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {/* ── Sistem metrikleri ── */}
          {metrics ? (
            <section className="rounded-card bg-ns-surface px-5 py-4 card-shadow dark:bg-nsd-surface">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-[14px] font-semibold text-ns-ink dark:text-nsd-ink">
                  Sistem metrikleri
                </h2>
                <p className="text-[11px] text-ns-faint">
                  bu sürümde analiz motoru kural tabanlıdır; gecikme ve verim değerleri model
                  çıkarımını içermez
                </p>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-[12.5px] sm:grid-cols-3">
                <Metric label="Toplam analiz" value={String(metrics.total_analyses)} />
                <Metric label="Gecikme p50" value={`${metrics.latency_p50_ms} ms`} />
                <Metric label="Gecikme p95" value={`${metrics.latency_p95_ms} ms`} />
                <Metric
                  label="Verim (kural motoru)"
                  value={`${metrics.throughput_per_minute.toLocaleString("tr-TR", {
                    maximumFractionDigits: 0,
                  })} içerik/dk`}
                />
                <Metric
                  label="Önbellek isabeti"
                  value={`${(metrics.cache_hit_rate * 100).toFixed(0)}%`}
                />
                <Metric
                  label="İnsan incelemesi"
                  value={`${(metrics.human_review_rate * 100).toFixed(0)}%`}
                />
              </dl>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-card bg-ns-surface px-4 py-3 card-shadow dark:bg-nsd-surface">
      <p className="text-[11.5px] text-ns-muted dark:text-nsd-subtle">{label}</p>
      <p className="text-[22px] font-bold tabular-nums text-ns-ink dark:text-nsd-ink">{value}</p>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-ns-line pb-1.5 dark:border-nsd-line">
      <dt className="text-ns-muted dark:text-nsd-subtle">{label}</dt>
      <dd className="font-medium tabular-nums text-ns-ink dark:text-nsd-ink">{value}</dd>
    </div>
  );
}
