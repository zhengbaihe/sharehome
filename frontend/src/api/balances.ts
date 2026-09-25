import { ApiError, apiRequest } from './auth';

export interface MembershipBalance {
  membership_id: string;
  user_id: string;
  display_name: string;
  role: 'OWNER' | 'MEMBER';
  status: 'ACTIVE' | 'DEPARTED';
  paid_minor: number;
  allocated_minor: number;
  balance_minor: number;
}

export const getBalances = (token: string, householdId: string) =>
  apiRequest<MembershipBalance[]>(`/households/${encodeURIComponent(householdId)}/balances`, { method: 'GET' }, token);

export function balanceError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Household not found or you don't have access.";
    if (error.status === 401) return 'Your session has expired. Please log out and log in again.';
  }
  return 'Unable to load balances. Please try again.';
}
