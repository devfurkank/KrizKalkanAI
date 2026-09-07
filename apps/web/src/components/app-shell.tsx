"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ComposerModal } from "@/components/composer";
import { MessagesDock } from "@/components/messages-dock";
import { Sidebar } from "@/components/sidebar";

/**
 * Üç sütunlu uygulama kabuğu.
 * "Yeni Gönderi" kipinin durumu burada tutulur; kenar çubuğu ve kip aynı
 * durumu paylaşır.
 */
export function AppShell({
  children,
  rail,
}: {
  children: React.ReactNode;
  rail?: React.ReactNode;
}) {
  const [composerOpen, setComposerOpen] = useState(false);
  const router = useRouter();

  return (
    <div className="mx-auto flex w-full max-w-[1320px] gap-7 px-6">
      <Sidebar onNewPost={() => setComposerOpen(true)} />
      <main className="min-w-0 flex-1 py-6">{children}</main>
      {rail}

      <MessagesDock />
      <ComposerModal
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        onPosted={() => {
          setComposerOpen(false);
          router.push("/");
          router.refresh();
        }}
      />
    </div>
  );
}
