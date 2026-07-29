import assert from 'node:assert/strict';
import { createServer } from 'vite';

const server = await createServer({
  appType: 'custom',
  logLevel: 'silent',
  server: { middlewareMode: true },
});

try {
  const bookmarks = await server.ssrLoadModule('/src/api/bookmarks.ts');
  const {
    MAX_BOOKMARK_IDS,
    parseBookmarkImport,
    parseShareIdsFromSearch,
    sanitizeBookmarkIds,
  } = bookmarks;

  assert.deepEqual(parseBookmarkImport({ ids: ['a', 'a', 'b'] }), ['a', 'b']);
  assert.throws(
    () => parseBookmarkImport({ ids: [{ malicious: true }] }),
    /invalid or oversized id/,
  );
  assert.throws(
    () => parseBookmarkImport({ ids: ['x'.repeat(129)] }),
    /invalid or oversized id/,
  );
  assert.throws(
    () => parseBookmarkImport({ ids: Array.from({ length: MAX_BOOKMARK_IDS + 1 }, (_, i) => `id-${i}`) }),
    /more than 500 ids/,
  );

  const many = Array.from({ length: MAX_BOOKMARK_IDS + 100 }, (_, i) => `id-${i}`);
  assert.equal(sanitizeBookmarkIds(many).length, MAX_BOOKMARK_IDS);
  assert.deepEqual(parseShareIdsFromSearch('?bm=one,two,two,%5Bbad%5D'), ['one', 'two']);
  assert.deepEqual(parseShareIdsFromSearch(`?bm=${'x'.repeat(20_000)}`), []);

  process.stdout.write('frontend adversarial storage/import checks passed\n');
} finally {
  await server.close();
}
