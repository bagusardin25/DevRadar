/**
 * Card text de-duplication.
 *
 * Listing copy arrives from three independent places — the extracted
 * description, the prize label, and the curated `suitableReasons` — so the same
 * fact often lands on a card two or three times ("$2,000,000 prize pool" as the
 * prize pill, again mid-description, again as a highlight). These helpers drop
 * the restatements at render time so the card only says each thing once.
 *
 * Both helpers are deliberately conservative: they only remove text that is
 * *almost entirely* covered elsewhere, because a wrong drop loses information
 * while a missed drop merely leaves the card slightly wordy.
 */

/** Words too common to signal that two phrases mean the same thing. */
const STOPWORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from', 'in', 'is',
  'it', 'of', 'on', 'or', 'the', 'this', 'to', 'via', 'with', 'you', 'your',
  'plus', 'across', 'through', 'up', 'per', 'all', 'more', 'than', 'that',
  // Words that only name the thing the reward slot is already labelled as.
  // "$20,500 in prizes" says nothing the "VALUE / REWARD" box has not said.
  'prize', 'prizes', 'pool', 'prizepool', 'reward', 'rewards', 'cash',
  'total', 'worth', 'value',
]);

/** Expand short money suffixes so "70k" and "70,000" compare equal. */
function expandMagnitude(text: string): string {
  return text.replace(/(\d+(?:\.\d+)?)([km])\b/g, (_, num: string, unit: string) => {
    const scale = unit === 'k' ? 1_000 : 1_000_000;
    return String(Math.round(parseFloat(num) * scale));
  });
}

/** Lowercase significant words, with punctuation and number formats normalised. */
function significantTokens(text: string): string[] {
  return expandMagnitude(
    text.toLowerCase().replace(/[$€£]/g, ' ').replace(/(\d),(\d)/g, '$1$2'),
  )
    .split(/[^a-z0-9.+-]+/)
    .map((t) => t.replace(/^[.+-]+|[.+-]+$/g, ''))
    .filter((t) => t.length > 1 && !STOPWORDS.has(t));
}

/** Numeric tokens only — used to spot a restated money figure. */
function numericTokens(tokens: string[]): string[] {
  return tokens.filter((t) => /^\d+$/.test(t));
}

/** Fraction of `tokens` that also appear in `pool`. 0 when `tokens` is empty. */
function coverage(tokens: string[], pool: Set<string>): number {
  if (tokens.length === 0) return 0;
  const hits = tokens.filter((t) => pool.has(t)).length;
  return hits / tokens.length;
}

/** A sentence may lose at most this many extra words and still count as a restatement. */
const RESTATEMENT_SLACK = 2;

/**
 * Drop sentences from `description` that only restate the prize.
 *
 * Two things count as a restatement:
 * 1. Every significant word is already in `prizeLabel` — "$2,000,000 prize
 *    pool." next to a "$2,000,000 prize pool" box.
 * 2. The sentence repeats the reward's money figure and adds no more than
 *    `RESTATEMENT_SLACK` other words — "~$30,000 prizes." or "$20,500 in prizes
 *    on Devpost." The figure is already displayed, and the leftover words are
 *    too few to be carrying the sentence.
 *
 * Longer sentences survive even when they mention the figure, so "Major online
 * build challenge on Devpost. $2,000,000 prize pool. Closes August 17 2026."
 * loses only its middle sentence.
 */
export function compactDescription(
  description: string,
  prizeLabel: string | undefined,
): string {
  if (!description) return '';
  if (!prizeLabel) return description;

  const prizeTokens = new Set(significantTokens(prizeLabel));
  if (prizeTokens.size === 0) return description;
  const prizeNumbers = new Set(numericTokens([...prizeTokens]));

  // Keep the delimiter attached to each sentence so spacing survives a rejoin.
  const sentences = description.match(/[^.!?]+[.!?]*\s*/g) ?? [description];
  const kept = sentences.filter((sentence) => {
    const tokens = significantTokens(sentence);
    if (tokens.length === 0) return true;

    const uncovered = tokens.filter((t) => !prizeTokens.has(t));
    if (uncovered.length === 0) return false;

    const echoesFigure =
      prizeNumbers.size > 0 && numericTokens(tokens).some((n) => prizeNumbers.has(n));
    return !(echoesFigure && uncovered.length <= RESTATEMENT_SLACK);
  });

  // Never blank the description out entirely — a wordy card beats an empty one.
  const result = kept.join('').trim();
  return result || description;
}

/**
 * How strictly a surface trims restated highlights.
 *
 * `summary` (cards) trims anything mostly-covered elsewhere, because a card is
 * a glance. `detail` (the modal) drops only highlights whose every word is
 * already on screen — the full view should not quietly withhold a partly-new
 * claim just to look tidy.
 */
export const DEDUPE_THRESHOLD = { summary: 0.8, detail: 1 } as const;

/**
 * Drop highlights whose content is already on the card elsewhere.
 *
 * A highlight is redundant when at least `threshold` of its significant words
 * already appear in the description, prize label or mode — e.g. "Online
 * Devpost" next to a description reading "…online build challenge on Devpost".
 * Highlights that add a genuinely new claim ("Largest public prize pool")
 * survive, because words like "largest" appear nowhere else.
 */
export function dedupeHighlights(
  reasons: string[],
  context: {
    description?: string;
    prizeLabel?: string | undefined;
    mode?: string | undefined;
  },
  threshold: number = DEDUPE_THRESHOLD.summary,
): string[] {
  if (reasons.length === 0) return reasons;

  const pool = new Set(
    significantTokens(
      [context.description, context.prizeLabel, context.mode]
        .filter(Boolean)
        .join(' '),
    ),
  );
  if (pool.size === 0) return reasons;

  const seen = new Set<string>();
  return reasons.filter((reason) => {
    const tokens = significantTokens(reason);
    if (coverage(tokens, pool) >= threshold) return false;

    // Also collapse highlights that duplicate each other.
    const fingerprint = [...tokens].sort().join(' ');
    if (fingerprint && seen.has(fingerprint)) return false;
    seen.add(fingerprint);
    return true;
  });
}
