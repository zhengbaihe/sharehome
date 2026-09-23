import { ApiError, apiRequest } from './auth';

export interface Household {
  id: string;
  name: string;
  currency: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}
export interface HouseholdCreate { name: string }
export const getHouseholds = (token: string) =>
  apiRequest<Household[]>('/households', { method: 'GET' }, token);
export const createHousehold = (token: string, body: HouseholdCreate) =>
  apiRequest<Household>('/households', { method: 'POST', body: JSON.stringify(body) }, token);
export const getHousehold = (token: string, id: string) =>
  apiRequest<Household>(`/households/${encodeURIComponent(id)}`, { method: 'GET' }, token);

export function householdError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "Household not found or you don't have access.";
    if (error.status === 401) return 'Your session has expired. Please log out and log in again.';
    if (error.status === 422) return 'Please check the household details and try again.';
    if (error.status === 0) return 'Unable to connect. Please try again.';
  }
  return 'Unable to complete the household request. Please try again.';
}
