import { AppShell } from "@/components/app-shell";
import { Feed } from "@/components/feed";
import { RightRail } from "@/components/right-rail";

export default function HomePage() {
  return (
    <AppShell rail={<RightRail />}>
      <Feed />
    </AppShell>
  );
}
