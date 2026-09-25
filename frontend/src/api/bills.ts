import { ApiError, apiRequest } from './auth';

export interface HouseholdMember {
  membership_id: string;
  user_id: string;
  display_name: string;
  role: 'OWNER' | 'MEMBER';
  status: 'ACTIVE' | 'DEPARTED';
}
export interface BillAllocation {
  id: string;
  membership_id: string;
  amount_minor: number;
  created_at: string;
}
export interface Bill {
  id: string;
  household_id: string;
  payer_membership_id: string;
  description: string;
  amount_minor: number;
  paid_at: string;
  split_method: 'EQUAL';
  created_at: string;
  updated_at: string;
  allocations: BillAllocation[];
}
export interface BillCreateRequest {
  description: string;
  amount_minor: number;
  payer_membership_id: string;
  participant_membership_ids: string[];
  paid_at: string;
}
const householdPath = (id: string) => `/households/${encodeURIComponent(id)}`;
export const getHouseholdMembers = (token: string, id: string) =>
  apiRequest<HouseholdMember[]>(`${householdPath(id)}/members`, { method: 'GET' }, token);
export const getBills = (token: string, id: string) =>
  apiRequest<Bill[]>(`${householdPath(id)}/bills`, { method: 'GET' }, token);
export const getBill = (token: string, id: string, billId: string) =>
  apiRequest<Bill>(`${householdPath(id)}/bills/${encodeURIComponent(billId)}`, { method: 'GET' }, token);
export const createBill = (token: string, id: string, body: BillCreateRequest) =>
  apiRequest<Bill>(`${householdPath(id)}/bills`, { method: 'POST', body: JSON.stringify(body) }, token);

export function billError(error: unknown, action: string): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return 'Bill or household not found, or you do not have access.';
    if (error.status === 401) return 'Your session has expired. Please log out and log in again.';
    if (error.status === 422) return 'Please check the bill details and selected members, then try again.';
  }
  return `Unable to ${action}. Please try again.`;
}
