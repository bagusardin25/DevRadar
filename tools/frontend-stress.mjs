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

  const countdown = await server.ssrLoadModule('/src/utils/countdown.ts');
  const { countActiveFilters } = countdown;
  assert.equal(
    countActiveFilters({
      activeModule: 'hackathon',
      searchQuery: '',
      mode: 'online',
      region: '',
      eligibility: '',
      technology: '',
      offerType: '',
      verificationStatus: '',
      onlyClosingSoon: false,
      onlyBigPrizes: false,
      onlyFreeNoCard: false,
    }),
    0,
    'default online catalogue should not count as a filter',
  );
  assert.equal(
    countActiveFilters({
      activeModule: 'hackathon',
      searchQuery: '',
      mode: 'hybrid',
      region: '',
      eligibility: '',
      technology: '',
      offerType: '',
      verificationStatus: '',
      onlyClosingSoon: true,
      onlyBigPrizes: false,
      onlyFreeNoCard: false,
    }),
    2,
  );

  const trust = await server.ssrLoadModule('/src/utils/trustCopy.ts');
  assert.equal(trust.offerWindow({ expiresAt: null, offerType: 'free_tier' }).kind, 'ongoing');
  assert.equal(trust.offerWindow({ expiresAt: null, offerType: 'promo_code' }).kind, 'unknown');
  assert.match(trust.publicStatusLabel('verified_active').label, /Checked official/);

  process.stdout.write('frontend adversarial storage/import checks passed\n');
} finally {
  await server.close();
}
