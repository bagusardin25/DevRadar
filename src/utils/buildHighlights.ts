import type { AIDeal, Hackathon } from '../types';
import { formatPrizePool } from './formatPrize';

export type HighlightItem = {
  id: string;
  kind: 'prize' | 'closing' | 'offer' | 'mode';
  label: string;
  emphasis: string;
};

/** Build honest catalogue highlights for the header strip (not a fake live feed). */
export function buildCatalogueHighlights(
  hackathons: Hackathon[],
  deals: AIDeal[],
  limit = 8,
): HighlightItem[] {
  const out: HighlightItem[] = [];
  const now = Date.now();

  const sortedClosing = [...hackathons]
    .filter((h) => h.registrationDeadline)
    .map((h) => {
      const t = new Date(h.registrationDeadline).getTime();
      const days = (t - now) / (1000 * 60 * 60 * 24);
      return { h, days };
    })
    .filter(({ days }) => days >= 0 && days <= 21)
    .sort((a, b) => a.days - b.days);

  for (const { h, days } of sortedClosing.slice(0, 3)) {
    const d = Math.max(0, Math.ceil(days));
    out.push({
      id: `close-${h.id}`,
      kind: 'closing',
      emphasis: d === 0 ? 'Closes today' : `${d}d left`,
      label: h.title,
    });
  }

  const bigPrizes = [...hackathons]
    .filter((h) => (h.prizeValue || 0) >= 10_000)
    .sort((a, b) => (b.prizeValue || 0) - (a.prizeValue || 0));

  for (const h of bigPrizes.slice(0, 3)) {
    out.push({
      id: `prize-${h.id}`,
      kind: 'prize',
      emphasis: formatPrizePool(h, { compact: true }),
      label: h.title,
    });
  }

  for (const d of deals.slice(0, 3)) {
    out.push({
      id: `deal-${d.id}`,
      kind: 'offer',
      emphasis: d.provider,
      label: d.offerValue || d.productName,
    });
  }

  // Dedupe by id, cap
  const seen = new Set<string>();
  const unique: HighlightItem[] = [];
  for (const item of out) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    unique.push(item);
    if (unique.length >= limit) break;
  }

  if (unique.length === 0) {
    return [
      {
        id: 'fallback',
        kind: 'mode',
        emphasis: 'Catalogue',
        label: 'Browse verified hackathons & free AI tiers — no login required',
      },
    ];
  }

  return unique;
}
