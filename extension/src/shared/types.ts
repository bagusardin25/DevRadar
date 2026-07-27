export type ListingKind = 'hackathon' | 'ai_offer' | 'unknown';

export interface PageData {
  url: string;
  title: string | null;
  metaDescription: string | null;
  ogTags: Record<string, string>;
  jsonLd: unknown[];
  visibleText: string;
  dates: string[];
  moneyAmounts: string[];
  techKeywords: string[];
  links: Array<{ href: string; text: string }>;
  registrationLinks: string[];
  scrapedAt: string;
}

export interface ExtractionResult {
  listingKind: ListingKind;
  confidence: number;
  fields: HackathonFields | AIOfferFields;
  method: 'heuristic';
  fieldSources: Record<string, string>;
}

export interface HackathonFields {
  kind: 'hackathon';
  title: string | null;
  organizer: string | null;
  description: string | null;
  registrationOpenAt: string | null;
  registrationDeadline: string | null;
  submissionDeadline: string | null;
  mode: 'online' | 'hybrid' | 'in_person' | null;
  technologies: string[];
  prizeValue: number | null;
  prizeCurrency: string | null;
  prizeLabel: string | null;
  teamMin: number;
  teamMax: number;
  officialUrl: string | null;
  eligibleCountries: string[];
  eligibility: string[];
}

export interface AIOfferFields {
  kind: 'ai_offer';
  title: string | null;
  productName: string | null;
  provider: string | null;
  description: string | null;
  offerType: string | null;
  offerValue: string | null;
  startsAt: string | null;
  expiresAt: string | null;
  supportedRegions: string[];
  officialTermsUrl: string | null;
  claimUrl: string | null;
  targetUsers: string[];
  tags: string[];
}

export interface AnalysisHistory {
  url: string;
  result: ExtractionResult;
  analyzedAt: string;
}

export interface ExtensionSettings {
  apiBaseUrl: string;
  darkMode: 'auto' | 'light' | 'dark';
}
