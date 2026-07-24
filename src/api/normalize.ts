import type {
  AIDeal,
  DiscoverySource,
  EffortEstimate,
  FieldCompleteness,
  Hackathon,
  HackathonMode,
  OfferType,
  SourceTier,
  VerificationAudit,
  VerificationStatus,
} from '../types';

const EFFORTS: EffortEstimate[] = [
  '1-2 Days',
  '1 Week',
  '1-2 Weeks',
  '2-3 Weeks',
  '1 Month+',
];

const TIERS: SourceTier[] = [
  'Tier 1 (Official)',
  'Tier 2 (Aggregator)',
  'Tier 3 (Discovery Signal)',
];

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return fallback;
}

function asString(value: unknown, fallback = ''): string {
  if (value == null) return fallback;
  return String(value);
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((v) => String(v));
}

function asIso(value: unknown, fallback = ''): string {
  if (value == null || value === '') return fallback;
  return String(value);
}

function asMode(value: unknown): HackathonMode {
  if (value === 'online' || value === 'hybrid' || value === 'in_person') return value;
  return 'online';
}

function asOfferType(value: unknown): OfferType {
  const allowed: OfferType[] = [
    'free_credits',
    'free_tier',
    'trial',
    'student_program',
    'open_source_program',
    'hackathon_credits',
    'promo_code',
    'free_model',
    'self_hosted_weights',
  ];
  if (typeof value === 'string' && (allowed as string[]).includes(value)) {
    return value as OfferType;
  }
  return 'free_tier';
}

function asStatus(value: unknown): VerificationStatus {
  const allowed: VerificationStatus[] = [
    'verified_active',
    'likely_active',
    'needs_review',
    'registration_closed',
    'expired',
    'cancelled',
  ];
  if (typeof value === 'string' && (allowed as string[]).includes(value)) {
    return value as VerificationStatus;
  }
  return 'likely_active';
}

function asEffort(value: unknown): EffortEstimate {
  if (typeof value === 'string' && (EFFORTS as string[]).includes(value)) {
    return value as EffortEstimate;
  }
  return '1 Week';
}

function asTier(value: unknown): SourceTier {
  if (typeof value === 'string' && (TIERS as string[]).includes(value)) {
    return value as SourceTier;
  }
  // Backend may send tier_1 style
  if (value === 'tier_1') return 'Tier 1 (Official)';
  if (value === 'tier_2') return 'Tier 2 (Aggregator)';
  if (value === 'tier_3') return 'Tier 3 (Discovery Signal)';
  return 'Tier 2 (Aggregator)';
}

function normalizeSource(raw: Record<string, unknown>): DiscoverySource {
  const type = asString(raw.type, 'official_site') as DiscoverySource['type'];
  return {
    type: ['x', 'devpost', 'mlh', 'official_site', 'reddit', 'github'].includes(type)
      ? type
      : 'official_site',
    url: asString(raw.url),
    author: raw.author != null ? asString(raw.author) : undefined,
    postId: raw.postId != null ? asString(raw.postId) : undefined,
    fetchedAt: asIso(raw.fetchedAt, new Date(0).toISOString()),
    tier: asTier(raw.tier),
  };
}

function normalizeCompleteness(raw: unknown): FieldCompleteness | undefined {
  if (!raw || typeof raw !== 'object') return undefined;
  const c = raw as Record<string, unknown>;
  return {
    score: asNumber(c.score),
    missing: asStringList(c.missing),
    flags: asStringList(c.flags),
    hasDeadline: Boolean(c.hasDeadline),
    hasPrize: Boolean(c.hasPrize),
    hasStrongUrl: Boolean(c.hasStrongUrl),
    hasEligibility: Boolean(c.hasEligibility),
    hasDescription: Boolean(c.hasDescription),
  };
}

function normalizeAudit(raw: unknown, confidence: number, lastChecked: string): VerificationAudit {
  const a = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
  const sb = (a.scoreBreakdown && typeof a.scoreBreakdown === 'object'
    ? a.scoreBreakdown
    : {}) as Record<string, unknown>;
  const step = asString(a.pipelineStep, 'verified');
  return {
    lastCheckedAt: asIso(a.lastCheckedAt, lastChecked),
    confidenceScore: asNumber(a.confidenceScore, confidence),
    scoreBreakdown: {
      statusAndDeadline: asNumber(sb.statusAndDeadline),
      keywordMatch: asNumber(sb.keywordMatch),
      sourceCredibility: asNumber(sb.sourceCredibility),
      freshness: asNumber(sb.freshness),
      completeness: asNumber(sb.completeness),
    },
    verifierNotes: asString(a.verifierNotes),
    checkedUrls: asStringList(a.checkedUrls),
    pipelineStep:
      step === 'fetched' || step === 'parsed' || step === 'extracted' || step === 'verified'
        ? step
        : 'verified',
  };
}

export function normalizeHackathon(
  raw: Record<string, unknown>,
  flags?: { bookmarked?: boolean; alertEnabled?: boolean },
): Hackathon {
  const confidence = asNumber(raw.confidenceScore);
  const lastChecked = asIso(raw.lastCheckedAt, new Date().toISOString());
  const sources = Array.isArray(raw.discoverySources)
    ? raw.discoverySources.map((s) =>
        normalizeSource((s && typeof s === 'object' ? s : {}) as Record<string, unknown>),
      )
    : [];

  return {
    id: asString(raw.id),
    title: asString(raw.title),
    organizer: asString(raw.organizer),
    organizerLogo: raw.organizerLogo != null ? asString(raw.organizerLogo) : undefined,
    description: asString(raw.description),
    registrationOpenAt: asIso(raw.registrationOpenAt),
    registrationDeadline: asIso(raw.registrationDeadline),
    submissionDeadline: asIso(raw.submissionDeadline),
    mode: asMode(raw.mode),
    location: raw.location != null ? asString(raw.location) : undefined,
    eligibleCountries: asStringList(raw.eligibleCountries),
    eligibility: asStringList(raw.eligibility),
    teamMin: asNumber(raw.teamMin, 1),
    teamMax: asNumber(raw.teamMax, 1),
    prizeValue: asNumber(raw.prizeValue),
    prizeCurrency: asString(raw.prizeCurrency, 'USD'),
    prizeLabel: asString(raw.prizeLabel, ''),
    technologies: asStringList(raw.technologies),
    officialUrl: asString(raw.officialUrl),
    discoverySources: sources,
    verificationStatus: asStatus(raw.verificationStatus),
    confidenceScore: confidence,
    lastCheckedAt: lastChecked,
    suitableReasons: asStringList(raw.suitableReasons),
    effortEstimate: asEffort(raw.effortEstimate),
    audit: normalizeAudit(raw.audit, confidence, lastChecked),
    completeness: normalizeCompleteness(raw.completeness),
    bookmarked: flags?.bookmarked ?? false,
    alertEnabled: flags?.alertEnabled ?? false,
  };
}

export function normalizeAIDeal(
  raw: Record<string, unknown>,
  flags?: { bookmarked?: boolean; alertEnabled?: boolean },
): AIDeal {
  const confidence = asNumber(raw.confidenceScore);
  const lastChecked = asIso(raw.lastCheckedAt, new Date().toISOString());
  const sources = Array.isArray(raw.discoverySources)
    ? raw.discoverySources.map((s) =>
        normalizeSource((s && typeof s === 'object' ? s : {}) as Record<string, unknown>),
      )
    : [];

  return {
    id: asString(raw.id),
    productName: asString(raw.productName),
    provider: asString(raw.provider),
    providerLogo: raw.providerLogo != null ? asString(raw.providerLogo) : undefined,
    offerType: asOfferType(raw.offerType),
    offerValue: asString(raw.offerValue),
    targetUsers: asStringList(raw.targetUsers),
    requirements: asStringList(raw.requirements),
    startsAt: asIso(raw.startsAt),
    expiresAt: raw.expiresAt == null ? null : asIso(raw.expiresAt),
    supportedRegions: asStringList(raw.supportedRegions),
    officialTermsUrl: asString(raw.officialTermsUrl),
    claimUrl: asString(raw.claimUrl),
    verificationStatus: asStatus(raw.verificationStatus),
    confidenceScore: confidence,
    lastCheckedAt: lastChecked,
    description: asString(raw.description),
    tags: asStringList(raw.tags),
    discoverySources: sources,
    suitableReasons: asStringList(raw.suitableReasons),
    audit: normalizeAudit(raw.audit, confidence, lastChecked),
    completeness: normalizeCompleteness(raw.completeness),
    bookmarked: flags?.bookmarked ?? false,
    alertEnabled: flags?.alertEnabled ?? false,
  };
}
