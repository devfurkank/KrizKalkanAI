import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell";
import { ModeratorPanel } from "@/components/moderator-panel";

export const metadata: Metadata = {
  title: "Moderatör Paneli · KrizKalkan AI",
};

export default function ModeratorPage() {
  return (
    <AppShell rail={null}>
      <ModeratorPanel />
    </AppShell>
  );
}
