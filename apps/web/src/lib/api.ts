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
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Analiz servisine ulaşılamıyor. API çalışıyor mu? (make dev-api)");
  }
  if (!response.ok) {
    throw new ApiError(
      `Servis ${response.status} döndürdü: ${response.statusText}`,
      response.status,
    );
  }
  return (await response.json()) as T;
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
