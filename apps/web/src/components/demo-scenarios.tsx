"use client";

import {
  ClockRewindIcon,
  LifeBuoyIcon,
  QuestionIcon,
  ShieldIcon,
  SparkIcon,
} from "@/components/icons";
import type { AttachedMedia } from "@/components/composer";

/**
 * Sunum yardımcısı — rapordaki senaryoları tek tıkla composer'a yükler.
 *
 * Demo sırasında uzun metinleri elle yazmak zaman kaybı ve hata kaynağıdır.
 * Bu panel yalnızca metni ve medya parmak izini doldurur; analiz her zaman
 * gerçek boru hattından geçer.
 */

export interface Scenario {
  id: string;
  title: string;
  expected: string;
  body: string;
  media: AttachedMedia | null;
  Icon: (p: { className?: string }) => React.ReactElement;
}

export const SCENARIOS: Scenario[] = [
  {
    id: "yanlis-baglam",
    title: "Yanlış bağlam",
    expected: "Seviye 2 · bağlam kartı",
    body:
      "Şanlıurfa'da az önce çekildi! Bina tamamen yıkıldı, durum çok vahim. " +
      "Hemen paylaşın, herkes bilsin!",
    media: {
      kind: "video",
      fingerprint: "deprem-yikim-hatay-2023",
      label: "video · arşiv görüntüsü",
    },
    Icon: ClockRewindIcon,
  },
  {
    id: "kurum-taklidi",
    title: "Kurum taklidi",
    expected: "Seviye 1 · alt bilgi",
    body:
      "AFAD açıkladı: ikinci büyük deprem bekleniyor. Kesin bilgi, " +
      "önümüzdeki 6 saat içinde olacak. Herkes bilsin!",
    media: null,
    Icon: ShieldIcon,
  },
  {
    id: "yardim-cagrisi",
    title: "Yardım çağrısı",
    expected: "Kural 0 · müdahale yok",
    body:
      "ACİL! Kardeşim enkaz altında, hâlâ ses geliyor. " +
      "Adres: Bahçelievler Mah. 12. Sokak No:4. Yardım edin, ekip gönderin lütfen!",
    media: null,
    Icon: LifeBuoyIcon,
  },
  {
    id: "sentetik",
    title: "Sentetik medya",
    expected: "Seviye 3 · sürtünme ekranı",
    body: "Vali konuşma yaptı, şehir tahliye ediliyor. Herkes güvenli bölgeye gitsin.",
    media: {
      kind: "video",
      fingerprint: "ai-klon-yetkili-ses",
      label: "video · klonlanmış ses",
    },
    Icon: SparkIcon,
  },
  {
    id: "yetersiz-kanit",
    title: "Yetersiz kanıt",
    expected: "Çekinme · karar yok",
    body: "Bir şeyler oluyor galiba, net göremedim.",
    media: {
      kind: "video",
      fingerprint: "dusuk-cozunurluk-kisa-klip",
      label: "video · düşük çözünürlük",
    },
    Icon: QuestionIcon,
  },
];

export function DemoScenarios({ onPick }: { onPick: (scenario: Scenario) => void }) {
  return (
    <section
      aria-label="Demo senaryoları"
      className="rounded-card border border-dashed border-ns-line bg-ns-surface px-5 py-4 dark:border-nsd-line dark:bg-nsd-surface"
    >
      <div className="flex items-baseline justify-between">
        <h2 className="text-[12.5px] font-semibold tracking-wide text-ns-muted dark:text-nsd-subtle">
          DEMO SENARYOLARI
        </h2>
        <span className="text-[11px] text-ns-faint">
          metni doldurur · analiz gerçek motordan geçer
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => onPick(s)}
            className="group flex items-center gap-2 rounded-full border border-ns-line px-3 py-1.5 text-left transition-colors hover:border-ns-primary/40 hover:bg-ns-hover dark:border-nsd-line dark:hover:bg-nsd-hover"
          >
            <s.Icon className="size-4 shrink-0 text-ns-primary" />
            <span className="text-[12.5px] font-medium text-ns-ink dark:text-nsd-ink">
              {s.title}
            </span>
            <span className="text-[11px] text-ns-faint">{s.expected}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
