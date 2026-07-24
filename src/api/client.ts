import { API_V1 } from './config';

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly traceId?: string;
  readonly body?: unknown;

  constructor(
    status: number,
    detail: string,
    options?: { traceId?: string; body?: unknown },
  ) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.traceId = options?.traceId;
    this.body = options?.body;
  }
}

export type RequestOptions = {
  method?: string;
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  headers?: Record<string, string>;
  /** Send cookies (admin session). Default false for public GETs. */
  credentials?: RequestCredentials;
  signal?: AbortSignal;
  /** Optional Idempotency-Key for POST submissions */
  idempotencyKey?: string;
};

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = path.startsWith('http') ? path : `${API_V1}${path.startsWith('/') ? path : `/${path}`}`;
  if (!query) return base;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = 'GET',
    query,
    body,
    headers = {},
    credentials = 'omit',
    signal,
    idempotencyKey,
  } = options;

  const reqHeaders: Record<string, string> = { Accept: 'application/json', ...headers };
  if (body !== undefined) {
    reqHeaders['Content-Type'] = 'application/json';
  }
  if (idempotencyKey) {
    reqHeaders['Idempotency-Key'] = idempotencyKey;
  }
  const response = await fetch(buildUrl(path, query), {
    method,
    headers: reqHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials,
    signal,
  });

  const traceId = response.headers.get('X-Trace-Id') ?? undefined;

  if (response.status === 204 || response.status === 304) {
    return undefined as T;
  }

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text) as unknown;
    } catch {
      parsed = { detail: text };
    }
  }

  if (!response.ok) {
    const problem = parsed as { detail?: string; title?: string } | null;
    const detail =
      problem?.detail ||
      problem?.title ||
      `Request failed (${response.status})`;
    throw new ApiError(response.status, detail, { traceId, body: parsed });
  }

  return parsed as T;
}
