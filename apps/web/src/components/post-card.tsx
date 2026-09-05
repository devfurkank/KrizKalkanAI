"use client";

import { AnalysisCard, FootnoteBar } from "@/components/analysis-card";
import { Avatar } from "@/components/avatar";
import {
  BookmarkIcon,
  ChartIcon,
  CommentIcon,
  ExternalIcon,
  MoreIcon,
  PipIcon,
  QuoteIcon,
  RocketIcon,
  ShareIcon,
  VerifiedIcon,
} from "@/components/icons";
import type { MediaRef, Post } from "@/lib/types";

/** Gövde metnindeki #etiketleri bağlantı rengine boyar. */
function RichText({ text }: { text: string }) {
  return (
    <p className="text-[15px] leading-[1.5] whitespace-pre-wrap text-ns-body dark:text-nsd-body">
      {text.split(/(#[\p{L}\p{N}_]+)/gu).map((part, i) =>
        part.startsWith("#") ? (
          <a key={i} href="#" className="text-ns-link hover:underline">
            {part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

function StatPill({
  Icon,
  count,
}: {
  Icon: (p: React.SVGProps<SVGSVGElement>) => React.ReactElement;
  count: number;
}) {
  return (
    <button
      type="button"
      className="flex items-center gap-2 rounded-full border border-ns-line px-3.5 py-1.5 text-[13px] text-ns-muted transition-colors hover:border-ns-primary/30 hover:text-ns-primary dark:border-nsd-line dark:text-nsd-subtle"
    >
      <Icon className="size-[17px]" />
      <span className="tabular-nums">{count}</span>
    </button>
  );
}

function Media({ media }: { media: MediaRef }) {
  if (media.kind === "grid") {
    return (
      <div className="mt-3 grid grid-cols-2 gap-[3px] overflow-hidden rounded-xl">
        {media.tiles.map((tile, i) => (
          <div key={i} className={`aspect-[4/3] bg-gradient-to-br ${tile}`} />
        ))}
      </div>
    );
  }
  return (
    <div className="relative mt-3 overflow-hidden rounded-xl bg-black">
      <div className="mx-auto flex aspect-[16/10] w-full items-center justify-center">
        <div
          className={`size-full bg-gradient-to-br ${media.poster ?? "from-slate-600 to-slate-900"}`}
        />
      </div>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="flex size-14 items-center justify-center rounded-full bg-black/45 backdrop-blur-sm">
          <svg viewBox="0 0 24 24" className="ml-1 size-7 fill-white" aria-hidden="true">
            <path d="M8 5.2v13.6L19 12z" />
          </svg>
        </span>
      </div>
      {media.label ? (
        <span className="absolute bottom-3 left-3 rounded bg-black/60 px-2 py-0.5 text-[11px] text-white">
          {media.label}
        </span>
      ) : null}
      <div className="absolute top-3 right-3 flex gap-3 text-white/90">
        <button type="button" aria-label="Küçük ekran">
          <PipIcon className="size-[18px]" />
        </button>
        <button type="button" aria-label="Yeni sekmede aç">
          <ExternalIcon className="size-[18px]" />
        </button>
      </div>
    </div>
  );
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.max(1, Math.round(diff / 60_000));
  if (minutes < 60) return `${minutes}dk`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}sa`;
  return `${Math.round(hours / 24)}g`;
}

export function PostCard({ post, onAppeal }: { post: Post; onAppeal?: (postId: string) => void }) {
  const analysis = post.analysis;
  const level = analysis?.intervention.level;
  const ruleZero = analysis?.intervention.protected_by_rule_zero ?? false;

  return (
    <article className="border-t border-ns-line px-5 py-4 first:border-t-0 dark:border-nsd-line">
      <header className="flex items-center gap-2.5">
        <Avatar gradient={post.author.avatar} size={36} />
        <div className="flex min-w-0 flex-1 items-center gap-1.5 text-[14.5px]">
          <span className="font-semibold text-ns-ink dark:text-nsd-ink">{post.author.name}</span>
          {post.author.verified ? <VerifiedIcon className="size-[15px] shrink-0" /> : null}
          <span className="truncate text-ns-subtle">@{post.author.handle}</span>
          <span className="text-ns-subtle">·</span>
          <span className="shrink-0 text-ns-subtle">{relativeTime(post.created_at)}</span>
        </div>
        <button
          type="button"
          aria-label="Daha fazla"
          className="flex size-8 items-center justify-center rounded-full text-ns-subtle transition-colors hover:bg-ns-hover dark:hover:bg-nsd-hover"
        >
          <MoreIcon className="size-[18px]" />
        </button>
      </header>

      <div className="mt-2 pl-[46px]">
        <RichText text={post.body} />
        {post.media ? <Media media={post.media} /> : null}

        {/* Analiz katmanı — seviyeye göre farklı yoğunlukta gösterilir. */}
        {analysis && ruleZero ? (
          <AnalysisCard analysis={analysis} />
        ) : analysis && level === "SEVIYE_1" ? (
          <FootnoteBar analysis={analysis} />
        ) : analysis && level && level !== "SEVIYE_0" ? (
          <AnalysisCard
            analysis={analysis}
            onAppeal={onAppeal ? () => onAppeal(post.id) : undefined}
          />
        ) : null}

        <footer className="mt-3.5 flex items-center gap-2">
          <StatPill Icon={CommentIcon} count={post.stats.replies ?? 0} />
          <StatPill Icon={QuoteIcon} count={post.stats.quotes ?? 0} />
          <StatPill Icon={RocketIcon} count={post.stats.boosts ?? 0} />
          <StatPill Icon={ChartIcon} count={post.stats.views ?? 0} />
          <div className="ml-auto flex items-center gap-1">
            <button
              type="button"
              aria-label="Kaydet"
              className="flex size-9 items-center justify-center rounded-full text-ns-muted transition-colors hover:bg-ns-hover hover:text-ns-primary dark:text-nsd-subtle dark:hover:bg-nsd-hover"
            >
              <BookmarkIcon className="size-[18px]" />
            </button>
            <button
              type="button"
              aria-label="Paylaş"
              className="flex size-9 items-center justify-center rounded-full text-ns-muted transition-colors hover:bg-ns-hover hover:text-ns-primary dark:text-nsd-subtle dark:hover:bg-nsd-hover"
            >
              <ShareIcon className="size-[18px]" />
            </button>
          </div>
        </footer>
      </div>
    </article>
  );
}
