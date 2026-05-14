/**
 * TypeScript types matching backend Pydantic models.
 * Keep in sync with backend/models.py.
 */

// --- API models ---

export interface RunRequest {
  domain_description: string;
  search_terms: string[];
  include_domains?: string[];
  exclude_domains?: string[];
  max_results_per_term: number;
  max_article_chars: number;
  dedup_title_similarity: number;
  dedup_snippet_similarity: number;
}

export interface Stage {
  name: 'search' | 'dedup' | 'group' | 'extract' | 'synthesize';
  status: 'pending' | 'active' | 'done' | 'failed';
  detail: string;
  elapsed_ms: number | null;
}

export interface Run {
  id: string;
  status: 'queued' | 'running' | 'complete' | 'failed';
  created_at: string;
  request: RunRequest;
  stages: Stage[];
  brief: Brief | null;
  error: string | null;
}

// --- Structured brief models ---

export interface Highlight {
  rank: number;
  headline: string;
  why_matters: string;
  pointer_section: string;
}

export interface Story {
  id: string;
  headline: string;
  tldr: string;
  pm_angle: string;
  supporting: string | null;
  source_domain: string;
  source_url: string;
  additional_coverage: string[];
  filter_tags: string[];
}

export interface WatchlistItem {
  topic: string;
  signal: string;
  source_domain: string;
}

export interface ActionItem {
  rank: number;
  text: string;
  pointer_section: string;
  pointer_story_id: string | null;
}

export interface Source {
  domain: string;
  url: string;
  referenced_in: string[];
}

export type SectionType = 'summary' | 'list' | 'callout' | 'quote';

export interface Section {
  type: SectionType;
  title: string;
  content_md: string | null;
  stories: Story[];
  source_urls: string[];
}

export interface Brief {
  title: string;
  date: string;
  source_count: number;
  story_count: number;
  search_term_count: number;
  raw_markdown: string;
  highlights: Highlight[];
  executive_summary: string;
  sections: Section[];
  watchlist: WatchlistItem[];
  action_items: ActionItem[];
  sources: Source[];
}
