"use client";

import { useEffect, useState } from "react";

import { CloseIcon } from "@/components/icons";
import { createAppeal } from "@/lib/api";

const REASONS = [
  "Etiket yanlış — içerik güncel ve doğru",
  "Bu bir yardım çağrısı",
  "Kaynak gösterdim, doğrulanabilir",
  "İçerik alıntı/tekzip amaçlı paylaşıldı",
  "Diğer",
];

/**
 * Akış 3 — itiraz.
 *
 * İtiraz moderatör kuyruğuna düşer; karar verisi aktif öğrenmeye beslenir
 * (rapor 6.2).
 */
export function AppealDialog({
  postId,
  onClose,
  onSubmitted,
}: {
  postId: string;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [reason, setReason] = useState(REASONS[0]!);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await createAppeal(postId, reason, note || undefined);
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "İtiraz gönderilemedi");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[#8E93A3]/45 px-4 backdrop-blur-[2px]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="itiraz-baslik"
        className="w-full max-w-[480px] rounded-[18px] bg-ns-surface px-6 pt-5 pb-5 shadow-[0_24px_70px_-12px_rgb(16_24_40/0.3)] dark:bg-nsd-surface"
      >
        <div className="flex items-center justify-between">
          <h2 id="itiraz-baslik" className="text-[17px] font-bold text-ns-ink dark:text-nsd-ink">
            Etikete itiraz et
          </h2>
          <button
            type="button"
            aria-label="Kapat"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
          >
            <CloseIcon className="size-[17px]" />
          </button>
        </div>

        <p className="mt-1.5 text-[13px] text-ns-muted dark:text-nsd-subtle">
          İtirazınız moderatör kuyruğuna eklenir. Karar, modelin iyileşmesi için geri beslenir.
        </p>

        <fieldset className="mt-4">
          <legend className="text-[12px] font-semibold text-ns-body dark:text-nsd-body">
            Gerekçe
          </legend>
          <div className="mt-2 space-y-1.5">
            {REASONS.map((r) => (
              <label
                key={r}
                className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-[13.5px] text-ns-body transition-colors hover:bg-ns-hover dark:text-nsd-body dark:hover:bg-nsd-hover"
              >
                <input
                  type="radio"
                  name="gerekce"
                  value={r}
                  checked={reason === r}
                  onChange={() => setReason(r)}
                  className="size-4 accent-ns-primary"
                />
                {r}
              </label>
            ))}
          </div>
        </fieldset>

        <label className="mt-3 block">
          <span className="text-[12px] font-semibold text-ns-body dark:text-nsd-body">
            Açıklama (isteğe bağlı)
          </span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            maxLength={500}
            className="mt-1.5 w-full resize-none rounded-xl border border-ns-line bg-transparent px-3 py-2 text-[13.5px] text-ns-ink outline-none focus:border-ns-primary dark:border-nsd-line dark:text-nsd-ink"
          />
        </label>

        {error ? (
          <p role="alert" className="mt-2 text-[12.5px] text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="h-10 rounded-full border border-ns-line px-4 text-[13.5px] text-ns-body dark:border-nsd-line dark:text-nsd-body"
          >
            Vazgeç
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="h-10 rounded-full bg-gradient-to-r from-ns-grad-from to-ns-grad-to px-5 text-[13.5px] font-semibold text-white transition-opacity hover:opacity-92 disabled:opacity-60"
          >
            {busy ? "Gönderiliyor…" : "İtirazı gönder"}
          </button>
        </div>
      </div>
    </div>
  );
}
