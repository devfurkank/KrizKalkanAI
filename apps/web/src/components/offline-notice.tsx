import { RefreshIcon } from "@/components/icons";

/**
 * API erişilemediğinde gösterilir.
 *
 * Sunum güvenliği: arayüz boş beyaz ekranla kalmaz, ne yapılacağını söyler.
 */
export function OfflineNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-card border border-amber-300 bg-amber-50 px-5 py-4 dark:border-amber-500/40 dark:bg-amber-500/10"
    >
      <p className="text-[13.5px] font-semibold text-amber-800 dark:text-amber-300">
        Analiz servisine ulaşılamıyor
      </p>
      <p className="mt-1 text-[12.5px] leading-relaxed text-amber-800/80 dark:text-amber-300/80">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-1.5 rounded-full border border-amber-400 px-3.5 py-1.5 text-[12.5px] font-medium text-amber-800 transition-colors hover:bg-amber-100 dark:border-amber-500/50 dark:text-amber-300 dark:hover:bg-amber-500/10"
      >
        <RefreshIcon className="size-3.5" />
        Yeniden dene
      </button>
    </div>
  );
}
