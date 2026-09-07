import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { RadarPanel } from "@/components/radar-panel";

export const metadata: Metadata = {
  title: "Kriz Radar · KrizKalkan AI",
};

export default function RadarPage() {
  return (
    <AppShell rail={null}>
      <RadarPanel />
    </AppShell>
  );
}
