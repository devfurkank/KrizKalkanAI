"use client";

import { useCallback, useEffect, useState } from "react";

import { AppealDialog } from "@/components/appeal-dialog";
import { InlineComposer, type AttachedMedia } from "@/components/composer";
import { DemoScenarios, type Scenario } from "@/components/demo-scenarios";
import { FeedTabs } from "@/components/feed-tabs";
import { OfflineNotice } from "@/components/offline-notice";
import { PostCard } from "@/components/post-card";
import { StoriesRow } from "@/components/stories-row";
import { getPosts } from "@/lib/api";
import type { Post } from "@/lib/types";
import { useAsyncData } from "@/lib/use-async-data";

export function Feed() {
  const fetchPosts = useCallback(() => getPosts(), []);
  const { data, error, loading, reload } = useAsyncData(fetchPosts);

  /** Yeni paylaşılan gönderiler sunucudan gelenlerin önüne eklenir. */
  const [fresh, setFresh] = useState<Post[]>([]);
  const [attached, setAttached] = useState<AttachedMedia | null>(null);
  const [scenarioText, setScenarioText] = useState<string | null>(null);
  const [appealPostId, setAppealPostId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const serverPosts = data ?? [];
  const freshIds = new Set(fresh.map((p) => p.id));
  const posts = [...fresh, ...serverPosts.filter((p) => !freshIds.has(p.id))];

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  function pickScenario(s: Scenario) {
    setScenarioText(s.body);
    setAttached(s.media);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <>
      <FeedTabs />

      <div className="mt-4 flex flex-col gap-4">
        <DemoScenarios onPick={pickScenario} />

        {error ? <OfflineNotice message={error} onRetry={reload} /> : null}

        <InlineComposer
          key={scenarioText ?? "bos"}
          initialBody={scenarioText ?? ""}
          attached={attached}
          onClearAttached={() => setAttached(null)}
          onPosted={(post) => {
            setFresh((p) => [post, ...p]);
            setScenarioText(null);
            setAttached(null);
            setToast(
              post.analysis?.intervention.protected_by_rule_zero
                ? "Gönderi paylaşıldı — Kural 0 ile korundu, hiçbir etiket uygulanmadı."
                : "Gönderi paylaşıldı. İçerik kaldırılmadı.",
            );
          }}
        />

        <div className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
          <StoriesRow />

          {loading ? (
            <p className="px-5 py-10 text-center text-[13.5px] text-ns-subtle">Akış yükleniyor…</p>
          ) : posts.length === 0 ? (
            <p className="px-5 py-10 text-center text-[13.5px] text-ns-subtle">
              Henüz gönderi yok.
            </p>
          ) : (
            posts.map((post) => <PostCard key={post.id} post={post} onAppeal={setAppealPostId} />)
          )}
        </div>
      </div>

      {appealPostId ? (
        <AppealDialog
          postId={appealPostId}
          onClose={() => setAppealPostId(null)}
          onSubmitted={() => {
            setAppealPostId(null);
            setToast("İtirazınız moderatör kuyruğuna eklendi.");
          }}
        />
      ) : null}

      {toast ? (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-[70] -translate-x-1/2 rounded-full bg-ns-ink px-5 py-2.5 text-[13px] text-white shadow-lg dark:bg-nsd-surface dark:text-nsd-ink"
        >
          {toast}
        </div>
      ) : null}
    </>
  );
}
