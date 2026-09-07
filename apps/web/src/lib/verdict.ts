/**
 * Sınıf ve müdahale seviyelerinin görsel sunumu.
 *
 * Erişilebilirlik kuralı (rapor 3.3): risk asla yalnızca renkle gösterilmez.
 * Her sınıfın bir ikonu ve metin etiketi vardır; renk yalnızca destekleyicidir.
 */

import type { InterventionLevel, Verdict } from "@/lib/types";

export type VerdictIcon =
  "context" | "unverified" | "synthetic" | "manipulated" | "provocative" | "clean" | "unknown";

export interface VerdictStyle {
  icon: VerdictIcon;
  /** Kısa etiket — rozet içinde görünür. */
  short: string;
  ring: string;
  chip: string;
  text: string;
  dot: string;
}

export const VERDICT_STYLE: Record<Verdict, VerdictStyle> = {
  YANLIŞ_BAĞLAM: {
    icon: "context",
    short: "Yanlış bağlam",
    ring: "border-amber-300 dark:border-amber-500/40",
    chip: "bg-amber-50 dark:bg-amber-500/10",
    text: "text-amber-700 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  DOĞRULANMAMIŞ_İDDİA: {
    icon: "unverified",
    short: "Doğrulanmamış",
    ring: "border-sky-300 dark:border-sky-500/40",
    chip: "bg-sky-50 dark:bg-sky-500/10",
    text: "text-sky-700 dark:text-sky-400",
    dot: "bg-sky-500",
  },
  SENTETİK_MEDYA: {
    icon: "synthetic",
    short: "Sentetik medya",
    ring: "border-red-300 dark:border-red-500/40",
    chip: "bg-red-50 dark:bg-red-500/10",
    text: "text-red-700 dark:text-red-400",
    dot: "bg-red-500",
  },
  MANİPÜLE_MEDYA: {
    icon: "manipulated",
    short: "Manipüle medya",
    ring: "border-red-300 dark:border-red-500/40",
    chip: "bg-red-50 dark:bg-red-500/10",
    text: "text-red-700 dark:text-red-400",
    dot: "bg-red-500",
  },
  PROVOKATİF_ÇERÇEVELEME: {
    icon: "provocative",
    short: "Provokatif dil",
    ring: "border-orange-300 dark:border-orange-500/40",
    chip: "bg-orange-50 dark:bg-orange-500/10",
    text: "text-orange-700 dark:text-orange-400",
    dot: "bg-orange-500",
  },
  TEMİZ: {
    icon: "clean",
    short: "Sorun yok",
    ring: "border-emerald-300 dark:border-emerald-500/40",
    chip: "bg-emerald-50 dark:bg-emerald-500/10",
    text: "text-emerald-700 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
  YETERSİZ_KANIT: {
    icon: "unknown",
    short: "Yetersiz kanıt",
    ring: "border-slate-300 dark:border-slate-500/40",
    chip: "bg-slate-100 dark:bg-slate-500/10",
    text: "text-slate-600 dark:text-slate-400",
    dot: "bg-slate-400",
  },
};

export const LEVEL_LABEL: Record<InterventionLevel, string> = {
  SEVIYE_0: "Seviye 0 · müdahale yok",
  SEVIYE_1: "Seviye 1 · alt bilgi",
  SEVIYE_2: "Seviye 2 · bağlam kartı",
  SEVIYE_3: "Seviye 3 · paylaşım öncesi sürtünme",
  SEVIYE_4: "Seviye 4 · insan moderatör",
};

/** Analiz kartı gösterilmeli mi? Seviye 0 sessizdir. */
export function shouldShowCard(level: InterventionLevel, ruleZero: boolean): boolean {
  return ruleZero || level !== "SEVIYE_0";
}

export function confidencePercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}
