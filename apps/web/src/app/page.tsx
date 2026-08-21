import { AppShell } from "@/components/app-shell";
import { InlineComposer } from "@/components/composer";
import { FeedTabs } from "@/components/feed-tabs";
import { PostCard } from "@/components/post-card";
import { RightRail } from "@/components/right-rail";
import { StoriesRow } from "@/components/stories-row";
import { posts } from "@/lib/mock-data";

export default function HomePage() {
  return (
    <AppShell rail={<RightRail />}>
      <FeedTabs />

      <div className="mt-4 flex flex-col gap-4">
        <InlineComposer />

        <div className="overflow-hidden rounded-card bg-ns-surface card-shadow dark:bg-nsd-surface">
          <StoriesRow />
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      </div>
    </AppShell>
  );
}
