import { apiRequest } from './client';

export type SubmissionReceipt = {
  trackingId: string;
  status: string;
  message: string;
  duplicate: boolean;
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
