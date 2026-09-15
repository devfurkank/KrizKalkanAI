"use client";

import { useEffect, useRef, useState } from "react";

import { AnalysisCard } from "@/components/analysis-card";
import { AudienceMenu } from "@/components/audience-menu";
import { Avatar } from "@/components/avatar";
import { FrictionScreen } from "@/components/friction-screen";
import {
  CalendarIcon,
  CloseIcon,
  GifIcon,
  GlobeIcon,
  ImageIcon,
  InfoIcon,
  PenIcon,
  PollIcon,
  SmileIcon,
} from "@/components/icons";
import {
  analyze,
  analyzeMedia,
  createPost,
  createPostWithMedia,
  IMAGE_TYPES,
  MAX_IMAGE_BYTES,
} from "@/lib/api";
import { rememberUpload } from "@/lib/local-media";
import type { AnalysisResult, Post } from "@/lib/types";
import { audienceOptions, currentUser, type Audience } from "@/lib/mock-data";

const MAX = 10000;
/** Görsel dışındaki araçlar demo kabuğudur; yalnızca görsel ekleme çalışır. */
const TOOLS = [
  { Icon: PollIcon, label: "Anket ekle" },
  { Icon: InfoIcon, label: "Bilgi" },
  { Icon: SmileIcon, label: "Emoji" },
  { Icon: CalendarIcon, label: "Zamanla" },
  { Icon: GifIcon, label: "GIF ekle" },
];

export type MediaKind = "yok" | "video" | "image" | "grid";

/** Composer'ın eklenmiş medyası — demo senaryolarında parmak izi taşır. */
export interface AttachedMedia {
  kind: MediaKind;
  fingerprint: string;
  label: string;
}

/** Kullanıcının seçtiği gerçek görsel ve tarayıcı içi önizlemesi. */
interface Upload {
  file: File;
  url: string;
}

const TOOL_CLASS =
  "flex size-8 items-center justify-center rounded-full text-ns-muted transition-colors hover:bg-ns-hover hover:text-ns-primary dark:text-nsd-subtle dark:hover:bg-nsd-hover";

function Toolbar({
  value,
  audience,
  onAudience,
  expanded,
  busy,
  onSubmit,
  mediaLabel,
  onClearMedia,
  onPickImage,
}: {
  value: string;
  audience: Audience;
  onAudience: (v: Audience) => void;
  expanded: boolean;
  busy: boolean;
  onSubmit: () => void;
  mediaLabel: string | null;
  onClearMedia: () => void;
  onPickImage: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const current = audienceOptions.find((o) => o.value === audience)!;
  const canSend = value.trim().length > 0 || mediaLabel !== null;

  return (
    <div className="flex flex-wrap items-center gap-1">
      <button
        type="button"
        title="Görsel ekle"
        aria-label="Görsel ekle"
        onClick={onPickImage}
        className={TOOL_CLASS}
      >
        <ImageIcon className="size-[19px]" />
      </button>
      {TOOLS.map(({ Icon, label }) => (
        <button key={label} type="button" title={label} aria-label={label} className={TOOL_CLASS}>
          <Icon className="size-[19px]" />
        </button>
      ))}

      {mediaLabel ? (
        <button
          type="button"
          onClick={onClearMedia}
          className="ml-1 flex max-w-[220px] items-center gap-1.5 rounded-full bg-ns-primary-soft px-2.5 py-1 text-[11.5px] font-medium text-ns-primary dark:bg-ns-primary/20"
        >
          <span className="truncate">{mediaLabel}</span>
          <CloseIcon className="size-3 shrink-0" />
        </button>
      ) : null}

      {expanded ? (
        <>
          <span className="mx-2 h-5 w-px bg-ns-line dark:bg-nsd-line" />
          <span className="text-[13px] text-ns-subtle tabular-nums">
            {value.length}/{MAX}
          </span>
        </>
      ) : null}

      <div className="ml-auto flex items-center gap-2">
        {expanded ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[13.5px] text-ns-body transition-colors hover:bg-ns-hover dark:text-nsd-body dark:hover:bg-nsd-hover"
            >
              <GlobeIcon className="size-[17px] text-ns-muted dark:text-nsd-subtle" />
              {current.label}
            </button>
            {menuOpen ? (
              <AudienceMenu
                value={audience}
                onSelect={onAudience}
                onClose={() => setMenuOpen(false)}
              />
            ) : null}
          </div>
        ) : null}

        <button
          type="button"
          disabled={!canSend || busy}
          onClick={onSubmit}
          className={`flex items-center gap-1.5 rounded-full px-4 py-[7px] text-[13.5px] font-medium transition-all ${
            canSend && !busy
              ? "bg-gradient-to-r from-ns-grad-from to-ns-grad-to text-white hover:opacity-92"
              : "cursor-default bg-ns-field text-ns-muted dark:bg-nsd-line dark:text-nsd-subtle"
          }`}
        >
          <PenIcon className="size-[15px]" />
          {busy ? "Analiz ediliyor…" : "Gönder"}
        </button>
      </div>
    </div>
  );
}

/**
 * Akış 1 ve 2'yi yürüten paylaşım kutusu.
 *
 * Gönder → içerik analiz edilir → analiz kartı belirir → kullanıcı paylaşır
 * veya vazgeçer. Seviye 3'te önce sürtünme ekranı gösterilir; paylaşım hiçbir
 * koşulda engellenmez.
 */
export function InlineComposer({
  onPosted,
  attached,
  onClearAttached,
  initialBody = "",
}: {
  onPosted: (post: Post) => void;
  attached?: AttachedMedia | null;
  onClearAttached?: () => void;
  /** Demo senaryosu seçildiğinde önceden doldurulan metin. */
  initialBody?: string;
}) {
  const [value, setValue] = useState(initialBody);
  const [focused, setFocused] = useState(initialBody.length > 0);
  const [audience, setAudience] = useState<Audience>("herkes");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<AnalysisResult | null>(null);
  const [friction, setFriction] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [upload, setUpload] = useState<Upload | null>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  /** Henüz yayımlanmamış önizlemenin blob URL'si; bileşen kapanınca serbest bırakılır. */
  const pendingUrl = useRef<string | null>(null);

  useEffect(
    () => () => {
      if (pendingUrl.current) URL.revokeObjectURL(pendingUrl.current);
    },
    [],
  );

  // Gerçek görsel seçildiyse demo senaryosunun parmak izinin yerine geçer.
  const media = upload ? null : (attached ?? null);
  const mediaLabel = upload ? `Görsel · ${upload.file.name}` : (media?.label ?? null);
  const expanded = focused || value.length > 0 || mediaLabel !== null;

  function discardUpload() {
    if (pendingUrl.current) URL.revokeObjectURL(pendingUrl.current);
    pendingUrl.current = null;
    setUpload(null);
  }

  function pickImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // aynı dosya yeniden seçilebilsin
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) {
      setError("Yalnızca JPEG, PNG ve WebP görseller analiz edilebilir");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError(`Görsel ${MAX_IMAGE_BYTES / (1024 * 1024)} MB sınırını aşıyor`);
      return;
    }
    discardUpload();
    const url = URL.createObjectURL(file);
    pendingUrl.current = url;
    setUpload({ file, url });
    setPreview(null);
    setError(null);
    setFocused(true);
    onClearAttached?.();
  }

  function clearMedia() {
    if (upload) discardUpload();
    else onClearAttached?.();
    setPreview(null);
  }

  function reset() {
    discardUpload();
    setValue("");
    setFocused(false);
    setPreview(null);
    setFriction(null);
    setError(null);
    onClearAttached?.();
  }

  async function runAnalysis() {
    setBusy(true);
    setError(null);
    try {
      const result = upload
        ? await analyzeMedia(value, upload.file)
        : await analyze({
            body: value,
            media_kind: media?.kind ?? "yok",
            media_fingerprint: media?.fingerprint ?? null,
          });
      setPreview(result);
      if (result.intervention.level === "SEVIYE_3") setFriction(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analiz başarısız");
    } finally {
      setBusy(false);
    }
  }

  async function publish() {
    setBusy(true);
    setError(null);
    try {
      const post = upload
        ? await createPostWithMedia(value, upload.file, audience)
        : await createPost({
            body: value,
            audience,
            media_kind: media?.kind ?? "yok",
            media_fingerprint: media?.fingerprint ?? null,
          });
      if (upload) {
        // Görsel artık akışa ait: blob URL serbest bırakılmaz.
        rememberUpload(post.id, upload.url);
        pendingUrl.current = null;
      }
      onPosted(post);
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gönderi yayımlanamadı");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="rounded-card bg-ns-surface px-5 pt-4 pb-3.5 card-shadow dark:bg-nsd-surface">
        <div className="flex gap-3">
          <Avatar gradient={currentUser.avatar} size={38} />
          <textarea
            ref={areaRef}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (preview) setPreview(null);
            }}
            onFocus={() => setFocused(true)}
            maxLength={MAX}
            rows={expanded ? 3 : 1}
            placeholder="Gönderi oluşturmak için..."
            aria-label="Gönderi metni"
            className="mt-1.5 min-w-0 flex-1 resize-none bg-transparent text-[15px] text-ns-ink outline-none placeholder:text-ns-subtle dark:text-nsd-ink"
          />
          {expanded ? (
            <button
              type="button"
              aria-label="Kapat"
              onClick={reset}
              className="flex size-6 shrink-0 items-center justify-center self-start rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
            >
              <CloseIcon className="size-3.5" />
            </button>
          ) : null}
        </div>

        {upload ? (
          <div className="mt-3 ml-[50px]">
            <div className="relative w-fit max-w-full">
              {/* eslint-disable-next-line @next/next/no-img-element -- tarayıcı içi blob önizlemesi; next/image blob URL'yi işleyemez */}
              <img
                src={upload.url}
                alt="Yüklenen görselin önizlemesi"
                className="max-h-72 rounded-xl border border-ns-line object-contain dark:border-nsd-line"
              />
              <button
                type="button"
                aria-label="Görseli kaldır"
                onClick={clearMedia}
                className="absolute top-2 right-2 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/75"
              >
                <CloseIcon className="size-3.5" />
              </button>
            </div>
            <p className="mt-1.5 text-[11.5px] text-ns-subtle">
              Görsel yalnızca analiz süresince işlenir; sunucuda saklanmaz.
            </p>
          </div>
        ) : null}

        <input
          ref={fileRef}
          type="file"
          accept={IMAGE_TYPES.join(",")}
          onChange={pickImage}
          className="hidden"
          tabIndex={-1}
          aria-hidden="true"
        />

        <div className="mt-3">
          <Toolbar
            value={value}
            audience={audience}
            onAudience={setAudience}
            expanded={expanded}
            busy={busy}
            mediaLabel={mediaLabel}
            onClearMedia={clearMedia}
            onPickImage={() => fileRef.current?.click()}
            onSubmit={preview ? publish : runAnalysis}
          />
        </div>

        {error ? (
          <p role="alert" className="mt-2 text-[12.5px] text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}

        {preview ? (
          <>
            <AnalysisCard analysis={preview} compact />
            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={reset}
                className="h-9 rounded-full border border-ns-line px-4 text-[13px] text-ns-body dark:border-nsd-line dark:text-nsd-body"
              >
                Vazgeç
              </button>
              <button
                type="button"
                onClick={publish}
                disabled={busy}
                className="h-9 rounded-full bg-gradient-to-r from-ns-grad-from to-ns-grad-to px-5 text-[13px] font-semibold text-white disabled:opacity-60"
              >
                Paylaş
              </button>
            </div>
          </>
        ) : null}
      </div>

      {friction ? (
        <FrictionScreen
          analysis={friction}
          onProceed={() => {
            setFriction(null);
            void publish();
          }}
          onCancel={() => setFriction(null)}
        />
      ) : null}
    </>
  );
}

/** "Yeni Gönderi" düğmesiyle açılan kip. */
export function ComposerModal({
  open,
  onClose,
  onPosted,
}: {
  open: boolean;
  onClose: () => void;
  onPosted: (post: Post) => void;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#8E93A3]/45 px-4 py-16 backdrop-blur-[2px]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Gönderi Oluştur"
        className="w-full max-w-[712px] rounded-[18px] bg-ns-surface px-6 pt-5 pb-4 shadow-[0_24px_70px_-12px_rgb(16_24_40/0.3)] dark:bg-nsd-surface"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[19px] font-bold text-ns-ink dark:text-nsd-ink">Gönderi Oluştur</h2>
          <button
            type="button"
            aria-label="Kapat"
            onClick={onClose}
            className="flex size-8 items-center justify-center rounded-full bg-ns-hover text-ns-muted transition-colors hover:bg-ns-field dark:bg-nsd-hover dark:text-nsd-subtle"
          >
            <CloseIcon className="size-[17px]" />
          </button>
        </div>

        <InlineComposer
          onPosted={(post) => {
            onPosted(post);
            onClose();
          }}
        />
      </div>
    </div>
  );
}
