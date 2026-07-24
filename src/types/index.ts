export type VerificationStatus =
  | 'verified_active'
  | 'likely_active'
  | 'needs_review'
  | 'registration_closed'
  | 'expired'
  | 'cancelled';

export type SourceTier = 'Tier 1 (Official)' | 'Tier 2 (Aggregator)' | 'Tier 3 (Discovery Signal)';

export type HackathonMode = 'online' | 'hybrid' | 'in_person';

export type OfferType =
  | 'free_credits'
  | 'free_tier'
  | 'trial'
  | 'student_program'
  | 'open_source_program'
  | 'hackathon_credits'
  | 'promo_code'
  | 'free_model'
  | 'self_hosted_weights';

export type EffortEstimate =
  | '1-2 Days'
  | '1 Week'
  | '1-2 Weeks'
  | '2-3 Weeks'
  | '1 Month+';

export interface DiscoverySource {
  type: 'x' | 'devpost' | 'mlh' | 'official_site' | 'reddit' | 'github';
  url: string;
  author?: string;
  postId?: string;
  fetchedAt: string;
  tier: SourceTier;
}

export interface VerificationAudit {
  lastCheckedAt: string;
  confidenceScore: number; // 0.0 to 1.0
  scoreBreakdown: {
    statusAndDeadline: number; // max 35
    keywordMatch: number;      // max 25
    sourceCredibility: number; // max 20
    freshness: number;         // max 15
    completeness: number;      // max 5
  };
  verifierNotes: string;
  checkedUrls: string[];
  pipelineStep: 'fetched' | 'parsed' | 'extracted' | 'verified';
}

/** Computed on API read — honest data-quality signals for cards. */
export interface FieldCompleteness {
  score: number; // 0–100
  missing: string[];
  flags: string[]; // closing_soon | prize_tba | weak_url | deadline_passed | no_expiry | expired
  hasDeadline: boolean;
  hasPrize: boolean;
  hasStrongUrl: boolean;
  hasEligibility: boolean;
  hasDescription: boolean;
}

export interface Hackathon {
  id: string;
  title: string;
  organizer: string;
  organizerLogo?: string;
  description: string;
  registrationOpenAt: string;
  registrationDeadline: string;
  submissionDeadline: string;
  mode: HackathonMode;
  location?: string;
  eligibleCountries: string[];
  eligibility: string[];
  teamMin: number;
  teamMax: number;
  prizeValue: number;
  prizeCurrency: string;
  /** Human-readable prize summary when numeric pool is 0 or incomplete (e.g. "TBA", "Free + credits"). */
  prizeLabel?: string;
  technologies: string[];
  officialUrl: string;
  discoverySources: DiscoverySource[];
  verificationStatus: VerificationStatus;
  confidenceScore: number;
  lastCheckedAt: string;
  suitableReasons: string[];
  effortEstimate: EffortEstimate;
  audit: VerificationAudit;
  completeness?: FieldCompleteness;
  bookmarked?: boolean;
  alertEnabled?: boolean;
}

export interface AIDeal {
  id: string;
  productName: string;
  provider: string;
  providerLogo?: string;
  offerType: OfferType;
  offerValue: string;
  targetUsers: string[];
  requirements: string[];
  startsAt: string;
  expiresAt: string | null;
  supportedRegions: string[];
  officialTermsUrl: string;
  claimUrl: string;
  verificationStatus: VerificationStatus;
  confidenceScore: number;
  lastCheckedAt: string;
  description: string;
  tags: string[];
  discoverySources: DiscoverySource[];
  suitableReasons: string[];
  audit: VerificationAudit;
  completeness?: FieldCompleteness;
  bookmarked?: boolean;
  alertEnabled?: boolean;
}

export interface UnverifiedSignal {
  id: string;
  sourceType: 'x_post' | 'reddit_post' | 'discord_announcement';
  postId: string;
  author: string;
  rawText: string;
  createdAt: string;
  discoveredUrls: string[];
  candidateType: 'hackathon' | 'ai_deal';
  extractedInfo: Partial<Hackathon> | Partial<AIDeal>;
  verificationStatus: 'needs_review' | 'flagged';
  confidenceScore: number;
}

export interface FilterState {
  searchQuery: string;
  activeModule: 'hackathon' | 'ai_deal' | 'pipeline' | 'admin_queue' | 'sources';
  mode: 'all' | 'online' | 'hybrid' | 'in_person';
  region: string;
  eligibility: string;
  technology: string;
  offerType: string;
  verificationStatus: string;
  onlyClosingSoon: boolean;
  onlyBigPrizes: boolean;
  onlyFreeNoCard: boolean;
  searchExecutionMode: 'indexed' | 'live_discovery';
}
