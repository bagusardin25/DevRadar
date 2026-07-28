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

process.stdout.write('extension concurrency/storage stress checks passed\n');
