import { apiRequest } from './client';

export type SubmissionReceipt = {
  trackingId: string;
  status: string;
  message: string;
  duplicate: boolean;
};

export type SubmissionState =
  | 'received'
  | 'queued'
  | 'fetching'
  | 'reviewing'
  | 'awaiting_admin'
  | 'review_failed'
  | 'processing'
  | 'duplicate'
  | 'accepted'
  | 'rejected';

export type SubmissionReviewPublic = {
  recommendation: 'approve' | 'reject' | 'needs_more_info';
  confidence: number;
  summary: string;
  concerns: Array<{ severity: 'high' | 'medium' | 'low'; message: string }>;
  generatedAt: string | null;
};

export type SubmissionStatus = {
  trackingId: string;
  status: SubmissionState;
  submittedAt: string;
  claimedType: 'hackathon' | 'ai_offer' | null;
  message: string;
  reviewedAt: string | null;
  review: SubmissionReviewPublic | null;
};

export type SubmissionCreateInput = {
  url: string;
  claimedTitle?: string;
  claimedType?: 'hackathon' | 'ai_offer';
  notes?: string;
  email?: string;
  /** Unix seconds when the form was opened (anti-bot min fill time). */
  formOpenedAt: number;
  /** Honeypot — always empty. */
  website?: string;
};

export async function createSubmission(
  input: SubmissionCreateInput,
  idempotencyKey?: string,
): Promise<SubmissionReceipt> {
  return apiRequest<SubmissionReceipt>('/submissions', {
    method: 'POST',
    body: {
      url: input.url,
      claimedTitle: input.claimedTitle,
      claimedType: input.claimedType,
      notes: input.notes,
      email: input.email,
      formOpenedAt: input.formOpenedAt,
      website: input.website ?? '',
    },
    idempotencyKey,
  });
}

export async function fetchSubmissionStatus(
  trackingId: string,
  signal?: AbortSignal,
): Promise<SubmissionStatus> {
  return apiRequest<SubmissionStatus>(`/submissions/${encodeURIComponent(trackingId)}`, {
    signal,
  });
}
