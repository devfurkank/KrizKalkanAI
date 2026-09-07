/**
 * API sözleşmesinin TypeScript karşılığı.
 * Python eşleniği: libs/krizkalkan-core/src/krizkalkan_core/schemas.py
 */

export type Verdict =
  | "SENTETİK_MEDYA"
  | "MANİPÜLE_MEDYA"
  | "YANLIŞ_BAĞLAM"
  | "DOĞRULANMAMIŞ_İDDİA"
  | "PROVOKATİF_ÇERÇEVELEME"
  | "TEMİZ"
  | "YETERSİZ_KANIT";

export type InterventionLevel = "SEVIYE_0" | "SEVIYE_1" | "SEVIYE_2" | "SEVIYE_3" | "SEVIYE_4";

export type KnowledgeVerdict = "DESTEKLİYOR" | "ÇELİŞİYOR" | "İLGİSİZ" | "RESMÎ_KAYNAK_SESSİZ";

export type ModuleCode = "M1" | "M2" | "M3" | "M4" | "M5" | "M6" | "M7";

export interface Evidence {
  kind: "kare" | "zaman_araligi" | "metin_araligi" | "kayit" | "ustveri";
  label: string;
  locator: string | null;
  detail: string | null;
  url: string | null;
}

export interface Signal {
  module: ModuleCode;
  key: string;
  label: string;
  score: number;
  raw_score: number;
  abstained: boolean;
  abstain_reason: string | null;
  evidence: Evidence[];
}

export interface ProvenanceMatch {
  matched: boolean;
  similarity: number;
  first_published: string | null;
  source: string | null;
  original_event: string | null;
  original_location: string | null;
  matched_frame: string | null;
  corpus_id: string | null;
}

export interface ExtractedClaim {
  claim_type: string;
  text: string;
  location: string | null;
  magnitude: string | null;
  time_expr: string | null;
  alleged_source: string | null;
  certainty: string;
}

export interface TextAnalysis {
  claims: ExtractedClaim[];
  labels: Record<string, number>;
  dominant_label: string;
  help_call_score: number;
  debunk_score: number;
}

export interface KnowledgeMatch {
  verdict: KnowledgeVerdict;
  matched_claim: string | null;
  official_statement: string | null;
  source: string | null;
  published_at: string | null;
  similarity: number;
}

export interface Intervention {
  level: InterventionLevel;
  label: string;
  automatic: boolean;
  headline: string;
  detail: string | null;
  protected_by_rule_zero: boolean;
  content_removed: boolean;
}

export interface AnalysisResult {
  analysis_id: string;
  content_id: string;
  verdict: Verdict;
  verdict_meaning: string;
  confidence: number;
  confidence_label: "düşük" | "orta" | "yüksek";
  intervention: Intervention;
  signals: Signal[];
  provenance: ProvenanceMatch | null;
  text: TextAnalysis | null;
  knowledge: KnowledgeMatch | null;
  modalities: string[];
  modules_run: ModuleCode[];
  modules_skipped: ModuleCode[];
  skip_reason: string | null;
  latency_ms: number;
  cache_hit: boolean;
  created_at: string;
}

export interface Author {
  handle: string;
  name: string;
  verified: boolean;
  avatar: string;
}

export interface MediaRef {
  kind: "grid" | "video" | "image";
  tiles: string[];
  poster: string | null;
  label: string | null;
}

export interface Post {
  id: string;
  author: Author;
  body: string;
  created_at: string;
  audience: "herkes" | "takipciler" | "belirli";
  media: MediaRef | null;
  stats: Record<string, number>;
  analysis: AnalysisResult | null;
  shared_despite_warning: boolean;
}

export interface ModerationItem {
  post_id: string;
  analysis_id: string;
  verdict: Verdict;
  confidence: number;
  spread_per_minute: number;
  body_preview: string;
  created_at: string;
  appeal_id: string | null;
}

export interface Appeal {
  id: string;
  post_id: string;
  analysis_id: string;
  reason: string;
  note: string | null;
  status: "bekliyor" | "kabul" | "ret";
  created_at: string;
  resolved_at: string | null;
  moderator_note: string | null;
}

export interface AuditEntry {
  id: string;
  at: string;
  actor: "sistem" | "moderatör" | "kullanıcı";
  action: string;
  post_id: string | null;
  detail: string | null;
}

export interface ClaimCluster {
  id: string;
  claim: string;
  post_count: number;
  spread_per_minute: number;
  acceleration: number;
  verdict: Verdict;
  official_status: KnowledgeVerdict;
  locations: string[];
}

export interface RadarSnapshot {
  window_minutes: number;
  analyzed_count: number;
  labelled_count: number;
  high_confidence_synthetic: number;
  wrong_context: number;
  unverified: number;
  protected_help_calls: number;
  removed_content: number;
  clusters: ClaimCluster[];
  generated_at: string;
}

export interface SystemMetrics {
  total_analyses: number;
  cache_hits: number;
  cache_hit_rate: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  throughput_per_minute: number;
  human_review_rate: number;
  protected_help_calls: number;
  removed_content: number;
  uptime_seconds: number;
}
