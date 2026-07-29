import type { ApiProxyOptions } from '../shared/messages';
import { getSettings } from '../shared/storage';

const MAX_API_RESPONSE_BYTES = 2_097_152;
const MAX_API_REQUEST_BYTES = 1_048_576;
const DEFAULT_API_TIMEOUT_MS = 15_000;

interface ApiProxyRuntime {
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export async function handleApiProxy(
  path: string,
  options: ApiProxyOptions,
  runtime: ApiProxyRuntime = {},
): Promise<unknown> {
  const settings = await getSettings();
  const base = settings.apiBaseUrl.replace(/\/+$/, '');
  if (path.length > 256 || path.includes('://') || path.includes('..')) {
    throw new Error('Invalid API path');
  }
  const apiPath = path.startsWith('/') ? path : `/${path}`;

  let url = `${base}/api/v1${apiPath}`;
  if (options.query) {
    const entries = Object.entries(options.query);
    if (entries.length > 20) throw new Error('Too many API query parameters');
    const params = new URLSearchParams();
    for (const [key, value] of entries) {
      if (value !== undefined && value !== null && value !== '') {
        const text = String(value);
        if (key.length > 64 || text.length > 512) {
          throw new Error('API query parameter is too long');
        }
        params.set(key, text);
      }
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  const requestedHeaders = Object.entries(options.headers ?? {});
  if (
    requestedHeaders.length > 1 ||
    requestedHeaders.some(([name]) => name.toLowerCase() !== 'idempotency-key')
  ) {
    throw new Error('Unsupported API header');
  }
  const idempotencyKey = requestedHeaders[0]?.[1];
  if (requestedHeaders.length === 1) {
    if (!idempotencyKey) throw new Error('Idempotency-Key is invalid');
    if (idempotencyKey.length > 200) throw new Error('Idempotency-Key is too long');
    if (idempotencyKey.trim() !== idempotencyKey || /[\r\n]/.test(idempotencyKey)) {
      throw new Error('Idempotency-Key is invalid');
    }
    headers['Idempotency-Key'] = idempotencyKey;
  }

  const method = (options.method || 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'POST') throw new Error('Unsupported API method');
  let serializedBody: string | undefined;
  if (options.body !== undefined) {
    if (method === 'GET') throw new Error('GET requests cannot include a body');
    headers['Content-Type'] = 'application/json';
    serializedBody = JSON.stringify(options.body);
    if (serializedBody === undefined) throw new Error('API request body is not JSON serializable');
    if (new TextEncoder().encode(serializedBody).byteLength > MAX_API_REQUEST_BYTES) {
      throw new Error('API request body is too large');
    }
  }

  const timeoutMs = runtime.timeoutMs ?? DEFAULT_API_TIMEOUT_MS;
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 60_000) {
    throw new Error('Invalid API timeout');
  }
  const controller = new AbortController();
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const resp = await (runtime.fetchImpl ?? fetch)(url, {
      method,
      headers,
      body: serializedBody,
      signal: controller.signal,
    });

    // Keep the same deadline active while the response stream is consumed;
    // receiving headers alone must not let a stalled body pin the MV3 worker.
    const text = await readBoundedResponse(resp, MAX_API_RESPONSE_BYTES);
    if (!resp.ok) {
      throw new Error(`API ${resp.status}: ${text.slice(0, 200)}`);
    }

    if (resp.status === 204 || !text) return null;
    try {
      return JSON.parse(text) as unknown;
    } catch {
      throw new Error('API returned invalid JSON');
    }
  } catch (error) {
    if (timedOut) throw new Error(`API request timed out after ${timeoutMs}ms`);
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function readBoundedResponse(response: Response, maxBytes: number): Promise<string> {
  const declared = Number(response.headers.get('content-length') || 0);
  if (Number.isFinite(declared) && declared > maxBytes) {
    throw new Error('API response is too large');
  }
  if (!response.body) return response.text();

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let received = 0;
  let text = '';
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      received += value.byteLength;
      if (received > maxBytes) throw new Error('API response is too large');
      text += decoder.decode(value, { stream: true });
    }
    return text + decoder.decode();
  } finally {
    if (received > maxBytes) await reader.cancel();
    reader.releaseLock();
  }
}
