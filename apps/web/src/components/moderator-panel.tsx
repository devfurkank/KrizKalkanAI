"use client";

import { useCallback, useState } from "react";

import { EvidenceList } from "@/components/evidence-list";
import { BanIcon, GavelIcon, LifeBuoyIcon } from "@/components/icons";
import { OfflineNotice } from "@/components/offline-notice";
import {
  decideModeration,
  getAppeals,
  getAudit,
  getModerationQueue,
  getPost,
  resolveAppeal,
} from "@/lib/api";
import type { Appeal, AuditEntry, ModerationItem, Post } from "@/lib/types";
import { useAsyncData } from "@/lib/use-async-data";
import { VERDICT_STYLE, confidencePercent } from "@/lib/verdict";

/** Akış 4 — moderatör triyajı. Karar insanındır; sistem yalnızca kaydeder. */
export function ModeratorPanel() {
  const fetchAll = useCallback(async (): Promise<{
    queue: ModerationItem[];
    appeals: Appeal[];
    audit: AuditEntry[];
  }> => {
    const [queue, appeals, audit] = await Promise.all([
      getModerationQueue(),
      getAppeals(),
      getAudit(30),
    ]);
    return { queue, appeals, audit };
  }, []);

  const { data, error, reload } = useAsyncData(fetchAll);
  const [selected, setSelected] = useState<Post | null>(null);
  const [busy, setBusy] = useState(false);

  const queue = data?.queue ?? [];
  const appeals = data?.appeals ?? [];
  const audit = data?.audit ?? [];

  async function open(postId: string) {
    try {
      setSelected(await getPost(postId));
    } catch {
      setSelected(null);
    }
  }

  async function decide(postId: string, decision: "onayla" | "baglam_ekle" | "mercie_bildir") {
    setBusy(true);
    try {
      await decideModeration(postId, decision, "Moderatör paneli üzerinden");
      setSelected(null);
      reload();
    } finally {
      setBusy(false);
    }
  }

  const pending = appeals.filter((a) => a.status === "bekliyor");

  return (
    <div className="space-y-5">
      <header>
        <h1 className="flex items-center gap-2 text-[22px] font-bold text-ns-ink dark:text-nsd-ink">
          <GavelIcon className="size-6 text-ns-primary" />
          Moderatör Paneli
        </h1>
        <p className="mt-1 text-[13.5px] text-ns-muted dark:text-nsd-subtle">
          Kuyruk yayılım hızına göre sıralıdır. Sistem içerik silemez; kaldırma yetkisi yalnızca
          yetkili mercidedir.
        </p>
      </header>

      {error ? <OfflineNotice message={error} onRetry={reload} /> : null}

      <div className="flex flex-wrap gap-3">
        <Stat label="Kuyrukta" value={queue.length} />
        <Stat label="Bekleyen itiraz" value={pending.length} />
        <Stat label="Kaldırılan içerik" value={0} accent />
      </div>

      {/* ── Triyaj kuyruğu ── */}
      <section className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
        <h2 className="border-b border-ns-line px-5 py-3 text-[14px] font-semibold text-ns-ink dark:border-nsd-line dark:text-nsd-ink">
          Triyaj kuyruğu
        </h2>
        {queue.length === 0 ? (
          <p className="px-5 py-8 text-center text-[13.5px] text-ns-subtle">Kuyruk boş.</p>
        ) : (
          <ul>
            {queue.map((item) => {
              const style = VERDICT_STYLE[item.verdict];
              return (
                <li
                  key={item.post_id}
                  className="border-t border-ns-line first:border-t-0 dark:border-nsd-line"
                >
                  <button
                    type="button"
                    onClick={() => void open(item.post_id)}
                    className="flex w-full items-start gap-3 px-5 py-3.5 text-left transition-colors hover:bg-ns-hover dark:hover:bg-nsd-hover"
                  >
                    <span className={`mt-1.5 size-2 shrink-0 rounded-full ${style.dot}`} />
                    <span className="min-w-0 flex-1">
                      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className={`text-[12.5px] font-semibold ${style.text}`}>
                          {style.short}
                        </span>
                        <span className="text-[11.5px] text-ns-muted dark:text-nsd-subtle">
                          güven {confidencePercent(item.confidence)}
                        </span>
                        <span className="text-[11.5px] font-medium text-ns-ink dark:text-nsd-ink">
                          {item.spread_per_minute.toFixed(0)} paylaşım/dk
                        </span>
                        {item.appeal_id ? (
                          <span className="rounded-full bg-ns-primary-soft px-2 py-0.5 text-[10.5px] font-medium text-ns-primary dark:bg-ns-primary/20">
                            itiraz var
                          </span>
                        ) : null}
                      </span>
                      <span className="mt-0.5 block truncate text-[13px] text-ns-body dark:text-nsd-body">
                        {item.body_preview}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ── İtirazlar ── */}
      {pending.length > 0 ? (
        <section className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
          <h2 className="border-b border-ns-line px-5 py-3 text-[14px] font-semibold text-ns-ink dark:border-nsd-line dark:text-nsd-ink">
            Bekleyen itirazlar
          </h2>
          <ul>
            {pending.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center gap-3 border-t border-ns-line px-5 py-3 first:border-t-0 dark:border-nsd-line"
              >
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] text-ns-ink dark:text-nsd-ink">
                    {a.reason}
                  </span>
                  {a.note ? (
                    <span className="block text-[12px] text-ns-muted dark:text-nsd-subtle">
                      {a.note}
                    </span>
                  ) : null}
                </span>
                <button
                  type="button"
                  onClick={async () => {
                    await resolveAppeal(a.id, true, "İtiraz haklı bulundu");
                    reload();
                  }}
                  className="rounded-full border border-emerald-400 px-3 py-1 text-[12.5px] font-medium text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
                >
                  Kabul
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await resolveAppeal(a.id, false, "Etiket korundu");
                    reload();
                  }}
                  className="rounded-full border border-ns-line px-3 py-1 text-[12.5px] text-ns-body dark:border-nsd-line dark:text-nsd-body"
                >
                  Reddet
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* ── Denetim kaydı ── */}
      <section className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
        <h2 className="border-b border-ns-line px-5 py-3 text-[14px] font-semibold text-ns-ink dark:border-nsd-line dark:text-nsd-ink">
          Denetim kaydı
        </h2>
        <ul className="max-h-72 overflow-y-auto">
          {audit.map((entry) => (
            <li
              key={entry.id}
              className="flex items-start gap-3 border-t border-ns-line px-5 py-2.5 text-[12.5px] first:border-t-0 dark:border-nsd-line"
            >
              {entry.action === "koruma_kuralı_uygulandı" ? (
                <LifeBuoyIcon className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-ns-faint" />
              )}
              <span className="min-w-0 flex-1">
                <span className="font-medium text-ns-ink dark:text-nsd-ink">{entry.action}</span>
                <span className="ml-2 text-ns-faint">{entry.actor}</span>
                {entry.detail ? (
                  <span className="block text-ns-muted dark:text-nsd-subtle">{entry.detail}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* ── İnceleme kipi ── */}
      {selected?.analysis ? (
        <div
          className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-[#8E93A3]/45 px-4 py-12 backdrop-blur-[2px]"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setSelected(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="İçerik incelemesi"
            className="w-full max-w-[640px] rounded-[18px] bg-ns-surface p-6 shadow-[0_24px_70px_-12px_rgb(16_24_40/0.3)] dark:bg-nsd-surface"
          >
            <h3 className="text-[16px] font-bold text-ns-ink dark:text-nsd-ink">
              İçerik incelemesi
            </h3>
            <p className="mt-2 rounded-xl bg-ns-hover px-4 py-3 text-[13.5px] leading-relaxed text-ns-body dark:bg-nsd-hover dark:text-nsd-body">
              {selected.body}
            </p>

            <div className="mt-4 rounded-xl border border-ns-line px-4 py-3 dark:border-nsd-line">
              <EvidenceList analysis={selected.analysis} />
            </div>

            <p className="mt-4 flex items-center gap-1.5 text-[12px] text-ns-muted dark:text-nsd-subtle">
              <BanIcon className="size-4" />
              Hiçbir karar içeriği kaldırmaz. Kaldırma yetkisi yetkili mercidedir.
            </p>

            <div className="mt-4 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="h-10 rounded-full border border-ns-line px-4 text-[13px] text-ns-body dark:border-nsd-line dark:text-nsd-body"
              >
                Kapat
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void decide(selected.id, "onayla")}
                className="h-10 rounded-full border border-emerald-400 px-4 text-[13px] font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-60 dark:text-emerald-400 dark:hover:bg-emerald-500/10"
              >
                Etiketi onayla
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void decide(selected.id, "baglam_ekle")}
                className="h-10 rounded-full border border-ns-line px-4 text-[13px] text-ns-body disabled:opacity-60 dark:border-nsd-line dark:text-nsd-body"
              >
                Bağlam ekle
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void decide(selected.id, "mercie_bildir")}
                className="h-10 rounded-full bg-gradient-to-r from-ns-grad-from to-ns-grad-to px-5 text-[13px] font-semibold text-white disabled:opacity-60"
              >
                Yetkili mercie bildir
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: number;
  accent?: boolean;
}) {
  return (
    <div
      className={`rounded-card px-5 py-3 card-shadow ${
        accent ? "bg-emerald-50 dark:bg-emerald-500/10" : "bg-ns-surface dark:bg-nsd-surface"
      }`}
    >
      <p className="text-[11.5px] text-ns-muted dark:text-nsd-subtle">{label}</p>
      <p
        className={`text-[22px] font-bold tabular-nums ${
          accent ? "text-emerald-700 dark:text-emerald-400" : "text-ns-ink dark:text-nsd-ink"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
