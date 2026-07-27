import type { PageData, ExtractionResult } from './types';

export type Message =
  | { type: 'GET_TAB_INFO' }
  | { type: 'TAB_INFO'; data: { url: string; title: string; favIconUrl?: string } }
  | { type: 'ANALYZE_TAB' }
  | { type: 'ANALYZING' }
  | { type: 'PAGE_DATA'; data: PageData }
  | { type: 'EXTRACTION_RESULT'; data: ExtractionResult }
  | { type: 'ANALYZE_ERROR'; error: string }
  | { type: 'API_REQUEST'; id: string; path: string; options: ApiProxyOptions }
  | { type: 'API_RESPONSE'; id: string; data: unknown; error?: string };

export interface ApiProxyOptions {
  method?: string;
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  headers?: Record<string, string>;
}
