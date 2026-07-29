import assert from 'node:assert/strict';
import { build } from 'esbuild';

async function loadTypeScript(entryPoint) {
  const result = await build({
    entryPoints: [entryPoint],
    bundle: true,
    format: 'esm',
    platform: 'node',
    write: false,
  });
  const source = Buffer.from(result.outputFiles[0].contents).toString('base64');
  return import(`data:text/javascript;base64,${source}`);
}

const { PendingAnalysisRegistry } = await loadTypeScript(
  'src/background/pendingAnalyses.ts',
);
const { sanitizeHistory, sanitizeSettings } = await loadTypeScript('src/shared/storage.ts');
const { handleApiProxy } = await loadTypeScript('src/background/apiProxy.ts');
const { getVisibleText, MAX_TEXT_NODES } = await loadTypeScript('src/content/visibleText.ts');

const registry = new PendingAnalysisRegistry();
const first = registry.start(1, 1000, 'timeout');
assert.throws(() => registry.start(1, 1000, 'timeout'), /already in progress/);
const second = registry.start(2, 1000, 'timeout');
assert.equal(registry.resolve(2, 'tab-two'), true);
assert.equal(registry.resolve(1, 'tab-one'), true);
assert.equal(await first, 'tab-one');
assert.equal(await second, 'tab-two');
assert.equal(registry.resolve(999, 'late'), false);
await assert.rejects(registry.start(3, 5, 'timed out safely'), /timed out safely/);

assert.equal(sanitizeSettings({ apiBaseUrl: 'javascript:alert(1)' }).apiBaseUrl, 'http://localhost:8000');
assert.equal(
  sanitizeSettings({ apiBaseUrl: 'https://api.example.com///', darkMode: 'dark' }).apiBaseUrl,
  'https://api.example.com',
);
assert.deepEqual(sanitizeHistory({ corrupted: true }), []);
assert.equal(
  sanitizeHistory(Array.from({ length: 80 }, (_, i) => ({
    url: `https://example.com/${i}`,
    result: {},
    analyzedAt: new Date(0).toISOString(),
  }))).length,
  50,
);

let aborted = false;
const stalledFetch = (_url, options) => new Promise((_resolve, reject) => {
  options.signal.addEventListener('abort', () => {
    aborted = true;
    reject(new DOMException('aborted', 'AbortError'));
  }, { once: true });
});
await assert.rejects(
  handleApiProxy('/stats', {}, { fetchImpl: stalledFetch, timeoutMs: 5 }),
  /timed out after 5ms/,
);
assert.equal(aborted, true);
await assert.rejects(handleApiProxy('../admin', {}), /Invalid API path/);
await assert.rejects(
  handleApiProxy('/stats', { method: 'GET', body: { invalid: true } }),
  /GET requests cannot include a body/,
);
await assert.rejects(
  handleApiProxy('/submissions', { headers: { Authorization: 'Bearer unsafe' } }),
  /Unsupported API header/,
);
await assert.rejects(
  handleApiProxy('/submissions', {
    headers: { 'Idempotency-Key': 'x'.repeat(201) },
  }),
  /Idempotency-Key is too long/,
);

let responseBodyAborted = false;
const stalledBodyFetch = async (_url, options) => {
  const body = new ReadableStream({
    start(controller) {
      options.signal.addEventListener('abort', () => {
        responseBodyAborted = true;
        controller.error(new DOMException('aborted', 'AbortError'));
      }, { once: true });
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'application/json' } });
};
await assert.rejects(
  handleApiProxy('/stats', {}, { fetchImpl: stalledBodyFetch, timeoutMs: 5 }),
  /timed out after 5ms/,
);
assert.equal(responseBodyAborted, true);

function fakeElement(style = {}) {
  return {
    parentElement: null,
    hasAttribute: () => false,
    getAttribute: () => null,
    closest: () => null,
    style: { display: 'block', visibility: 'visible', opacity: '1', ...style },
  };
}

function fakeDocument(nodes) {
  let cursor = 0;
  return {
    body: {},
    defaultView: { getComputedStyle: (element) => element.style },
    createTreeWalker: () => ({ nextNode: () => nodes[cursor++] ?? null }),
  };
}

const visibleParent = fakeElement();
const blankNodes = Array.from(
  { length: MAX_TEXT_NODES },
  () => ({ textContent: ' '.repeat(100), parentElement: visibleParent }),
);
blankNodes.push({ textContent: 'must-not-be-reached', parentElement: visibleParent });
assert.equal(getVisibleText(fakeDocument(blankNodes)), '');

const cssHiddenParent = fakeElement({ display: 'none' });
assert.equal(
  getVisibleText(fakeDocument([
    { textContent: 'hidden-keyword-stuffing', parentElement: cssHiddenParent },
    { textContent: 'public opportunity', parentElement: visibleParent },
  ])),
  'public opportunity',
);

process.stdout.write('extension concurrency/storage/network/DOM stress checks passed\n');
