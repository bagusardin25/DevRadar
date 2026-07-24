import { apiRequest } from './client';

export type AlertCreateInput = {
  email: string;
  targetType: 'hackathon' | 'ai_offer' | 'all';
  filters?: Record<string, unknown>;
  frequency?: 'daily' | 'weekly' | 'instant';
};

export type AlertCreateResponse = {
  id: string;
  status: string;
  emailMasked: string;
  verificationSent: boolean;
};

export async function createAlert(input: AlertCreateInput): Promise<AlertCreateResponse> {
  return apiRequest<AlertCreateResponse>('/alerts', {
    method: 'POST',
    body: input,
  });
}

export async function unsubscribeAlert(token: string): Promise<void> {
  await apiRequest('/alerts/unsubscribe', {
    method: 'POST',
    query: { token },
  });
}
