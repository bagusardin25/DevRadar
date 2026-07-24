import type { Hackathon } from '../types';

/**
 * Display-ready prize pool string.
 * Prefer explicit prizeLabel when set; fall back to formatted currency;
 * never show bare "$0" for unknown pools.
 */
export function formatPrizePool(
  hackathon: Pick<Hackathon, 'prizeValue' | 'prizeCurrency' | 'prizeLabel'>,
  options?: { compact?: boolean },
): string {
  const label = (hackathon.prizeLabel || '').trim();
  if (label) return label;

  const value = Number(hackathon.prizeValue);
  const currency = (hackathon.prizeCurrency || 'USD').toUpperCase();

  if (!Number.isFinite(value) || value <= 0) {
    return 'Prize TBA';
  }

  if (options?.compact && value >= 1_000_000) {
    const m = value / 1_000_000;
    const s = Number.isInteger(m) ? String(m) : m.toFixed(1).replace(/\.0$/, '');
    return `$${s}M ${currency}`;
  }
  if (options?.compact && value >= 10_000) {
    const k = value / 1_000;
    const s = Number.isInteger(k) ? String(k) : k.toFixed(1).replace(/\.0$/, '');
    return `$${s}K ${currency}`;
  }

  return `$${value.toLocaleString()} ${currency}`;
}
