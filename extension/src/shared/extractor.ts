import type {
  PageData, ExtractionResult, ListingKind,
  HackathonFields, AIOfferFields,
} from './types';
import {
  PRIZE_RE, CREDITS_RE, TEAM_RE, TEAM_SINGLE_RE,
  HACKATHON_SIGNALS, AI_OFFER_SIGNALS,
  MODE_PATTERNS, OFFER_TYPE_PATTERNS,
  TECH_KEYWORDS, KNOWN_PLATFORMS,
} from './constants';

function parseDate(raw: string): Date | null {
  const trimmed = raw.trim();
  const d = new Date(trimmed);
  if (!isNaN(d.getTime())) return d;

  const monthNames: Record<string, number> = {
    jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
    jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
  };
  const m = trimmed.match(/(\w+)\s+(\d{1,2}),?\s+(20\d{2})/);
  if (m) {
    const month = monthNames[m[1].slice(0, 3).toLowerCase()];
    if (month !== undefined) {
      return new Date(Date.UTC(parseInt(m[3]), month, parseInt(m[2])));
    }
  }
  return null;
}

function parseDates(rawDates: string[]): Date[] {
  return rawDates
    .map(parseDate)
    .filter((d): d is Date => d !== null)
    .sort((a, b) => a.getTime() - b.getTime());
}

function classifyPage(data: PageData): ListingKind {
  const text = `${data.title || ''} ${data.metaDescription || ''} ${data.visibleText}`;
  let hackScore = 0;
  let offerScore = 0;

  for (const re of HACKATHON_SIGNALS) {
    if (re.test(text)) hackScore++;
  }
  for (const re of AI_OFFER_SIGNALS) {
    if (re.test(text)) offerScore++;
  }

  if (data.moneyAmounts.length > 0 && /prize|pool|award|bounty/i.test(text)) {
    hackScore += 2;
  }
  if (/free\s+credits|free\s+tier/i.test(text)) {
    offerScore += 2;
  }

  try {
    const host = new URL(data.url).hostname.replace(/^www\./, '');
    if (host.includes('devpost.com') || host.includes('mlh.io') || host.includes('dorahacks.io')) {
      hackScore += 3;
    }
  } catch { /* invalid URL */ }

  if (hackScore >= 2 && hackScore > offerScore) return 'hackathon';
  if (offerScore >= 2 && offerScore > hackScore) return 'ai_offer';
  if (hackScore >= 1) return 'hackathon';
  if (offerScore >= 1) return 'ai_offer';
  return 'unknown';
}

function detectMode(text: string): 'online' | 'hybrid' | 'in_person' | null {
  for (const [pattern, mode] of MODE_PATTERNS) {
    if (pattern.test(text)) return mode as 'online' | 'hybrid' | 'in_person';
  }
  return null;
}

function detectTechnologies(text: string): string[] {
  const lower = text.toLowerCase();
  return TECH_KEYWORDS.filter((tech) => lower.includes(tech.toLowerCase()));
}

function detectPrize(text: string): { value: number | null; currency: string | null; label: string | null } {
  const m = text.match(PRIZE_RE);
  if (!m) return { value: null, currency: null, label: null };

  const num = parseFloat(m[1].replace(/,/g, ''));
  if (isNaN(num)) return { value: null, currency: null, label: null };

  const suffix = (m[2] || '').toLowerCase();
  let value = num;
  if (suffix === 'k') value *= 1000;
  if (suffix === 'm') value *= 1_000_000;

  return { value, currency: 'USD', label: m[0].trim() };
}

function detectOfferType(text: string): string | null {
  for (const [pattern, type] of OFFER_TYPE_PATTERNS) {
    if (pattern.test(text)) return type;
  }
  return null;
}

function detectOfferValue(text: string, offerType: string | null): string | null {
  const cm = text.match(CREDITS_RE);
  if (cm) return `$${cm[1].replace(/,/g, '')} free credits`;
  if (offerType === 'free_tier') return 'Free tier';
  return null;
}

function detectOrganizer(text: string): string | null {
  const m = text.match(/(?:organized|hosted|presented|powered)\s+by\s+([A-Z][\w &.+\-]{1,60})/i);
  return m ? m[1].trim() : null;
}

function detectEligibility(text: string): string[] {
  const labels: string[] = [];
  if (/\bstudents?\b/i.test(text)) labels.push('Student');
  if (/\bdevelopers?\b/i.test(text)) labels.push('Developer');
  if (/\bstartups?\b/i.test(text)) labels.push('Startup');
  return labels;
}

function getPlatformName(url: string): string | null {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    for (const [domain, name] of Object.entries(KNOWN_PLATFORMS)) {
      if (host.includes(domain)) return name;
    }
  } catch { /* */ }
  return null;
}

function firstLine(text: string): string | null {
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.length >= 8) return trimmed.slice(0, 200);
  }
  return null;
}

function extractHackathon(data: PageData): HackathonFields {
  const text = data.visibleText;
  const title = data.ogTags['og:title'] || data.title || firstLine(text);
  const dates = parseDates(data.dates);
  const prize = detectPrize(text);
  const sources: Record<string, string> = {};

  let teamMin = 1, teamMax = 1;
  const tm = text.match(TEAM_RE);
  if (tm) {
    teamMin = parseInt(tm[1]);
    teamMax = parseInt(tm[2]);
  } else {
    const ts = text.match(TEAM_SINGLE_RE);
    if (ts) teamMax = parseInt(ts[1]);
  }

  let registrationOpenAt: string | null = null;
  let registrationDeadline: string | null = null;
  let submissionDeadline: string | null = null;

  if (dates.length >= 3) {
    registrationOpenAt = dates[0].toISOString();
    registrationDeadline = dates[1].toISOString();
    submissionDeadline = dates[dates.length - 1].toISOString();
    sources.registrationOpenAt = sources.registrationDeadline = sources.submissionDeadline = 'date_heuristic';
  } else if (dates.length === 2) {
    registrationDeadline = dates[0].toISOString();
    submissionDeadline = dates[1].toISOString();
    sources.registrationDeadline = sources.submissionDeadline = 'date_heuristic';
  } else if (dates.length === 1) {
    submissionDeadline = dates[0].toISOString();
    sources.submissionDeadline = 'date_heuristic';
  }

  const worldwide = /\bworldwide\b|\bglobal\b|\banyone\b/i.test(text);

  return {
    kind: 'hackathon',
    title,
    organizer: detectOrganizer(text) || getPlatformName(data.url),
    description: (data.metaDescription || text.slice(0, 500)) || null,
    registrationOpenAt,
    registrationDeadline,
    submissionDeadline,
    mode: detectMode(text),
    technologies: detectTechnologies(text),
    prizeValue: prize.value,
    prizeCurrency: prize.currency,
    prizeLabel: prize.label,
    teamMin,
    teamMax: Math.max(teamMax, teamMin),
    officialUrl: data.url,
    eligibleCountries: worldwide ? ['Worldwide'] : [],
    eligibility: detectEligibility(text),
  };
}

function extractAIOffer(data: PageData): AIOfferFields {
  const text = data.visibleText;
  const title = data.ogTags['og:title'] || data.title || firstLine(text);
  const offerType = detectOfferType(text);
  const dates = parseDates(data.dates);

  let startsAt: string | null = null;
  let expiresAt: string | null = null;
  if (dates.length >= 2) {
    startsAt = dates[0].toISOString();
    expiresAt = dates[dates.length - 1].toISOString();
  } else if (dates.length === 1) {
    if (offerType === 'free_tier') {
      startsAt = dates[0].toISOString();
    } else {
      expiresAt = dates[0].toISOString();
    }
  }
  if (offerType === 'free_tier' && !/expir|until|ends?\b/i.test(text)) {
    expiresAt = null;
  }

  let provider: string | null = null;
  if (title) {
    const parts = title.split(/\s+/);
    if (parts.length > 0) provider = parts[0];
  }

  let claimUrl: string | null = null;
  let termsUrl: string | null = null;
  for (const link of data.links) {
    const low = link.href.toLowerCase();
    if (!claimUrl && (low.includes('claim') || low.includes('signup') || low.includes('register'))) {
      claimUrl = link.href;
    }
    if (!termsUrl && (low.includes('terms') || low.includes('pricing'))) {
      termsUrl = link.href;
    }
  }

  const worldwide = /\bworldwide\b|\bglobal\b/i.test(text);

  return {
    kind: 'ai_offer',
    title,
    productName: title,
    provider,
    description: (data.metaDescription || text.slice(0, 500)) || null,
    offerType,
    offerValue: detectOfferValue(text, offerType),
    startsAt,
    expiresAt,
    supportedRegions: worldwide ? ['Worldwide'] : [],
    officialTermsUrl: termsUrl || data.url,
    claimUrl: claimUrl || data.url,
    targetUsers: detectEligibility(text).length > 0 ? detectEligibility(text) : ['Developer'],
    tags: detectTechnologies(text),
  };
}

function computeConfidence(data: PageData, kind: ListingKind, fields: HackathonFields | AIOfferFields): number {
  let score = 0;

  if (fields.title) score += 10;
  if (data.techKeywords.length > 0) score += 10;
  if (data.dates.length > 0) score += 15;
  if (data.jsonLd.length > 0) score += 10;
  if (data.registrationLinks.length > 0) score += 10;

  try {
    const host = new URL(data.url).hostname.replace(/^www\./, '');
    if (Object.keys(KNOWN_PLATFORMS).some((d) => host.includes(d))) score += 10;
  } catch { /* */ }

  if (kind === 'hackathon') {
    const hf = fields as HackathonFields;
    if (hf.prizeValue !== null) score += 10;
    if (hf.mode) score += 5;
    if (hf.organizer) score += 5;
    if (hf.submissionDeadline) {
      const dl = new Date(hf.submissionDeadline);
      if (dl.getTime() > Date.now()) score += 15;
    }
  } else if (kind === 'ai_offer') {
    const af = fields as AIOfferFields;
    if (af.offerType) score += 10;
    if (af.offerValue) score += 10;
    if (af.provider) score += 5;
    if (af.expiresAt) {
      const exp = new Date(af.expiresAt);
      if (exp.getTime() > Date.now()) score += 15;
    } else if (af.offerType === 'free_tier') {
      score += 15;
    }
  }

  return Math.min(score, 100);
}

export function extract(data: PageData): ExtractionResult {
  const kind = classifyPage(data);

  if (kind === 'unknown') {
    return {
      listingKind: 'unknown',
      confidence: 0,
      fields: extractHackathon(data),
      method: 'heuristic',
      fieldSources: {},
    };
  }

  const fields = kind === 'hackathon' ? extractHackathon(data) : extractAIOffer(data);
  const confidence = computeConfidence(data, kind, fields);

  return {
    listingKind: kind,
    confidence,
    fields,
    method: 'heuristic',
    fieldSources: {},
  };
}
