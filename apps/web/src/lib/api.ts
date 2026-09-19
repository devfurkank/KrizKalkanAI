/**
 * KrizKalkan API istemcisi.
 *
 * Sunum güvenliği: API erişilemezse istekler hata fırlatmaz, `ApiError`
 * döndürür ve arayüz "çevrimdışı" durumunu gösterir. Demo hiçbir koşulda
 * boş beyaz ekranla kalmaz.
 */

import type {
  AnalysisResult,
  Appeal,
  AuditEntry,
  ModerationItem,
  Post,
  RadarSnapshot,
  SystemMetrics,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // FormData gövdesinde içerik türünü (sınır dizesiyle birlikte) tarayıcı
  // kendisi yazar; elle JSON başlığı eklemek yüklemeyi bozar.
  const isForm = init?.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: isForm ? init?.headers : { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Analiz servisine ulaşılamıyor. API çalışıyor mu? (make dev-api)");
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

/** Sunucunun hata ayrıntısını (FastAPI `detail`) varsa kullanıcıya taşır. */
async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Gövde JSON değil; durum koduyla yetinilir.
  }
  return `Servis ${response.status} döndürdü: ${response.statusText}`;
}

// ─────────────────────────── akış ───────────────────────────

export const getPosts = () => request<Post[]>("/api/posts");

export const getPost = (id: string) => request<Post>(`/api/posts/${id}`);

export interface AnalyzePayload {
  body: string;
  media_kind?: "yok" | "grid" | "video" | "image";
  media_fingerprint?: string | null;
}

export const analyze = (payload: AnalyzePayload) =>
  request<AnalysisResult>("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ media_kind: "yok", ...payload }),
  });

export interface CreatePostPayload extends AnalyzePayload {
  audience?: "herkes" | "takipciler" | "belirli";
}

export const createPost = (payload: CreatePostPayload) =>
  request<Post>("/api/posts", {
    method: "POST",
    body: JSON.stringify({ media_kind: "yok", audience: "herkes", ...payload }),
  });

// ─────────────────────────── gerçek medya ───────────────────────────
// Medya modülleri (M1 köken, M2 sahne–iddia, M4 sentetik görüntü/video) yalnızca
// gerçek dosyada çalışır. Dosya iki istekte de yeniden gönderilir: sunucu onu
// analiz biter bitmez siler, arada saklamaz.

/** Kabul edilen biçimler ve boyut sınırları — sunucudakiyle (media.py) aynı. */
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
export const MAX_IMAGE_BYTES = 15 * 1024 * 1024;
export const VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/webm", "video/x-m4v"];
export const MAX_VIDEO_BYTES = 100 * 1024 * 1024;

function mediaForm(file: File, fields: Record<string, string>): FormData {
  const form = new FormData();
  form.append("file", file);
  for (const [key, value] of Object.entries(fields)) form.append(key, value);
  return form;
}

export const analyzeMedia = (body: string, file: File) =>
  request<AnalysisResult>("/api/analyze/media", {
    method: "POST",
    body: mediaForm(file, { body }),
  });

export const createPostWithMedia = (
  body: string,
  file: File,
  audience: NonNullable<CreatePostPayload["audience"]> = "herkes",
) =>
  request<Post>("/api/posts/media", {
    method: "POST",
    body: mediaForm(file, { body, audience }),
  });

// ─────────────────────────── moderasyon ───────────────────────────

export const getModerationQueue = () => request<ModerationItem[]>("/api/moderation/queue");

export const decideModeration = (
  postId: string,
  decision: "onayla" | "baglam_ekle" | "mercie_bildir",
  note?: string,
) =>
  request<AuditEntry>("/api/moderation/decide", {
    method: "POST",
    body: JSON.stringify({ post_id: postId, decision, note }),
  });

export const getAppeals = () => request<Appeal[]>("/api/moderation/appeals");

export const createAppeal = (postId: string, reason: string, note?: string) =>
  request<Appeal>("/api/moderation/appeals", {
    method: "POST",
    body: JSON.stringify({ post_id: postId, reason, note }),
  });

export const resolveAppeal = (appealId: string, accepted: boolean, note?: string) =>
  request<Appeal>(
    `/api/moderation/appeals/${appealId}/resolve?accepted=${accepted}` +
      (note ? `&note=${encodeURIComponent(note)}` : ""),
    { method: "POST" },
  );

export const getAudit = (limit = 50) =>
  request<AuditEntry[]>(`/api/moderation/audit?limit=${limit}`);

// ─────────────────────────── radar & metrikler ───────────────────────────

export const getRadar = (windowMinutes = 30) =>
  request<RadarSnapshot>(`/api/radar?window_minutes=${windowMinutes}`);

export const getMetrics = () => request<SystemMetrics>("/api/metrics");

export const resetDemo = () =>
  request<{ durum: string; gönderi: number }>("/api/demo/reset", { method: "POST" });
