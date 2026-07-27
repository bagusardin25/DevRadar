import type {
  AdminAIOfferInput,
  AdminAIOfferRecord,
  AdminHackathonInput,
  AdminHackathonRecord,
} from '../../api/adminCatalogue';
import type {
  EffortEstimate,
  HackathonMode,
  OfferType,
  VerificationStatus,
} from '../../types';

export const VERIFICATION_OPTIONS: Array<{ value: VerificationStatus; label: string }> = [
  { value: 'verified_active', label: 'Verified active' },
  { value: 'likely_active', label: 'Likely active' },
  { value: 'needs_review', label: 'Needs review' },
  { value: 'registration_closed', label: 'Registration closed' },
  { value: 'expired', label: 'Expired' },
  { value: 'cancelled', label: 'Cancelled' },
];

export const MODE_OPTIONS: Array<{ value: HackathonMode; label: string }> = [
  { value: 'online', label: 'Online' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'in_person', label: 'In person' },
];

export const EFFORT_OPTIONS: Array<{ value: EffortEstimate; label: string }> = [
  { value: '1-2 Days', label: '1-2 Days' },
  { value: '1 Week', label: '1 Week' },
  { value: '1-2 Weeks', label: '1-2 Weeks' },
  { value: '2-3 Weeks', label: '2-3 Weeks' },
  { value: '1 Month+', label: '1 Month+' },
];

export const OFFER_TYPE_OPTIONS: Array<{ value: OfferType; label: string }> = [
  { value: 'free_credits', label: 'Free credits' },
  { value: 'free_tier', label: 'Free tier' },
  { value: 'trial', label: 'Trial' },
  { value: 'student_program', label: 'Student program' },
  { value: 'open_source_program', label: 'Open source program' },
  { value: 'hackathon_credits', label: 'Hackathon credits' },
  { value: 'promo_code', label: 'Promo code' },
  { value: 'free_model', label: 'Free model' },
  { value: 'self_hosted_weights', label: 'Self-hosted weights' },
];

export type HackathonFormState = {
  title: string;
  slug: string;
  description: string;
  verificationStatus: VerificationStatus;
  confidenceScore: string;
  organizer: string;
  organizerLogo: string;
  registrationOpenAt: string;
  registrationDeadline: string;
  submissionDeadline: string;
  mode: HackathonMode;
  location: string;
  eligibleCountries: string;
  eligibility: string;
  teamMin: string;
  teamMax: string;
  prizeValue: string;
  prizeCurrency: string;
  prizeLabel: string;
  technologies: string;
  officialUrl: string;
  suitableReasons: string;
  effortEstimate: EffortEstimate | '';
};

export type AIOfferFormState = {
  title: string;
  slug: string;
  description: string;
  verificationStatus: VerificationStatus;
  confidenceScore: string;
  productName: string;
  provider: string;
  providerLogo: string;
  offerType: OfferType;
  offerValue: string;
  targetUsers: string;
  requirements: string;
  startsAt: string;
  expiresAt: string;
  supportedRegions: string;
  officialTermsUrl: string;
  claimUrl: string;
  tags: string;
  suitableReasons: string;
};

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function toDateTimeInput(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIso(value: string): string | null {
  if (!value.trim()) return null;
  return new Date(value).toISOString();
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed || null;
}

export function makeHackathonForm(record?: AdminHackathonRecord): HackathonFormState {
  if (!record) {
    return {
      title: '',
      slug: '',
      description: '',
      verificationStatus: 'needs_review',
      confidenceScore: '0.80',
      organizer: '',
      organizerLogo: '',
      registrationOpenAt: '',
      registrationDeadline: '',
      submissionDeadline: '',
      mode: 'online',
      location: '',
      eligibleCountries: 'Worldwide',
      eligibility: '',
      teamMin: '1',
      teamMax: '1',
      prizeValue: '0',
      prizeCurrency: 'USD',
      prizeLabel: '',
      technologies: '',
      officialUrl: '',
      suitableReasons: '',
      effortEstimate: '',
    };
  }
  return {
    title: record.listing.title,
    slug: record.listing.slug,
    description: record.listing.description,
    verificationStatus: record.listing.verificationStatus,
    confidenceScore: String(record.listing.confidenceScore),
    organizer: record.hackathon.organizer,
    organizerLogo: record.hackathon.organizerLogo ?? '',
    registrationOpenAt: toDateTimeInput(record.hackathon.registrationOpenAt),
    registrationDeadline: toDateTimeInput(record.hackathon.registrationDeadline),
    submissionDeadline: toDateTimeInput(record.hackathon.submissionDeadline),
    mode: record.hackathon.mode,
    location: record.hackathon.location ?? '',
    eligibleCountries: record.hackathon.eligibleCountries.join(', '),
    eligibility: record.hackathon.eligibility.join(', '),
    teamMin: String(record.hackathon.teamMin),
    teamMax: String(record.hackathon.teamMax),
    prizeValue: String(record.hackathon.prizeValue),
    prizeCurrency: record.hackathon.prizeCurrency,
    prizeLabel: record.hackathon.prizeLabel,
    technologies: record.hackathon.technologies.join(', '),
    officialUrl: record.hackathon.officialUrl,
    suitableReasons: record.hackathon.suitableReasons.join(', '),
    effortEstimate: record.hackathon.effortEstimate ?? '',
  };
}

export function makeAIOfferForm(record?: AdminAIOfferRecord): AIOfferFormState {
  if (!record) {
    return {
      title: '',
      slug: '',
      description: '',
      verificationStatus: 'needs_review',
      confidenceScore: '0.80',
      productName: '',
      provider: '',
      providerLogo: '',
      offerType: 'free_credits',
      offerValue: '',
      targetUsers: '',
      requirements: '',
      startsAt: '',
      expiresAt: '',
      supportedRegions: 'Worldwide',
      officialTermsUrl: '',
      claimUrl: '',
      tags: '',
      suitableReasons: '',
    };
  }
  return {
    title: record.listing.title,
    slug: record.listing.slug,
    description: record.listing.description,
    verificationStatus: record.listing.verificationStatus,
    confidenceScore: String(record.listing.confidenceScore),
    productName: record.aiOffer.productName,
    provider: record.aiOffer.provider,
    providerLogo: record.aiOffer.providerLogo ?? '',
    offerType: record.aiOffer.offerType,
    offerValue: record.aiOffer.offerValue,
    targetUsers: record.aiOffer.targetUsers.join(', '),
    requirements: record.aiOffer.requirements.join(', '),
    startsAt: toDateTimeInput(record.aiOffer.startsAt),
    expiresAt: toDateTimeInput(record.aiOffer.expiresAt),
    supportedRegions: record.aiOffer.supportedRegions.join(', '),
    officialTermsUrl: record.aiOffer.officialTermsUrl,
    claimUrl: record.aiOffer.claimUrl,
    tags: record.aiOffer.tags.join(', '),
    suitableReasons: record.aiOffer.suitableReasons.join(', '),
  };
}

export function hackathonFormToInput(form: HackathonFormState): AdminHackathonInput {
  return {
    listing: {
      title: form.title.trim(),
      slug: form.slug.trim(),
      description: form.description.trim(),
      verificationStatus: form.verificationStatus,
      confidenceScore: Number(form.confidenceScore),
    },
    hackathon: {
      organizer: form.organizer.trim(),
      organizerLogo: emptyToNull(form.organizerLogo),
      registrationOpenAt: toIso(form.registrationOpenAt),
      registrationDeadline: toIso(form.registrationDeadline),
      submissionDeadline: toIso(form.submissionDeadline),
      mode: form.mode,
      location: emptyToNull(form.location),
      eligibleCountries: splitList(form.eligibleCountries),
      eligibility: splitList(form.eligibility),
      teamMin: Number(form.teamMin),
      teamMax: Number(form.teamMax),
      prizeValue: Number(form.prizeValue),
      prizeCurrency: form.prizeCurrency.trim() || 'USD',
      prizeLabel: form.prizeLabel.trim(),
      technologies: splitList(form.technologies),
      officialUrl: form.officialUrl.trim(),
      suitableReasons: splitList(form.suitableReasons),
      effortEstimate: form.effortEstimate || null,
    },
  };
}

export function aiOfferFormToInput(form: AIOfferFormState): AdminAIOfferInput {
  return {
    listing: {
      title: form.title.trim(),
      slug: form.slug.trim(),
      description: form.description.trim(),
      verificationStatus: form.verificationStatus,
      confidenceScore: Number(form.confidenceScore),
    },
    aiOffer: {
      productName: form.productName.trim(),
      provider: form.provider.trim(),
      providerLogo: emptyToNull(form.providerLogo),
      offerType: form.offerType,
      offerValue: form.offerValue.trim(),
      targetUsers: splitList(form.targetUsers),
      requirements: splitList(form.requirements),
      startsAt: toIso(form.startsAt),
      expiresAt: toIso(form.expiresAt),
      supportedRegions: splitList(form.supportedRegions),
      officialTermsUrl: form.officialTermsUrl.trim(),
      claimUrl: form.claimUrl.trim(),
      tags: splitList(form.tags),
      suitableReasons: splitList(form.suitableReasons),
    },
  };
}
