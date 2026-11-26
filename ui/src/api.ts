export type SearchMode = 'keyword' | 'hybrid';

export interface SearchHit {
  id: number;
  title: string;
  description: string;
  category: string;
  tags: string[];
  format: string;
  duration_ms: number;
  score?: number;
}

export interface FacetCount {
  count: number;
  highlighted: string;
  value: string;
}

export interface Facet {
  field_name: string;
  counts: FacetCount[];
}

export interface SearchResponse {
  hits: SearchHit[];
  found: number;
  facet_counts: Facet[];
  search_time_ms: number;
  page: number;
  suggest_generate: boolean;
  mode: SearchMode;
}

export interface GenerateResponse {
  sound_id: number;
  idempotent: boolean;
  indexed: boolean;
  license: string;
}

export interface SignedUrlResponse {
  url: string;
  expires_in: number;
}

export interface SearchParams {
  q: string;
  mode: SearchMode;
  category?: string;
  format?: string;
  tags: string[];
  min_duration?: number;
  max_duration?: number;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    const body: { detail?: string } | null = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function searchSounds(params: SearchParams): Promise<SearchResponse> {
  const query = new URLSearchParams({
    q: params.q,
    mode: params.mode,
    page: '1',
  });

  if (params.category) query.set('category', params.category);
  if (params.format) query.set('format', params.format);
  for (const tag of params.tags) query.append('tags', tag);
  if (params.min_duration !== undefined) query.set('min_duration', String(params.min_duration));
  if (params.max_duration !== undefined) query.set('max_duration', String(params.max_duration));

  return request<SearchResponse>(`/search?${query.toString()}`);
}

export async function generateSound(
  prompt: string,
  durationSeconds: number,
): Promise<GenerateResponse> {
  return request<GenerateResponse>('/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, duration_seconds: durationSeconds }),
  });
}

export async function getPreviewUrl(soundId: number): Promise<string> {
  const result = await request<SignedUrlResponse>(`/sounds/${soundId}/preview`);
  return result.url;
}

export async function getDownloadUrl(soundId: number): Promise<string> {
  const result = await request<SignedUrlResponse>(`/sounds/${soundId}/download`, {
    headers: { 'X-Subscriber': 'true' },
  });
  return result.url;
}
