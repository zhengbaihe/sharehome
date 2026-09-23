export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  updated_at: string;
}
export interface LoginRequest { email: string; password: string }
export interface RegisterRequest extends LoginRequest { display_name: string }
export interface TokenResponse { access_token: string; token_type: 'bearer' }

// Reuse the existing Vite /api proxy. Production hosting must route /api to the backend.
const API_BASE_URL = '/api';
export class ApiError extends Error {
  constructor(public readonly status: number) {
    super('The request could not be completed.');
  }
}
export async function apiRequest<T>(
  path: string, options: RequestInit = {}, token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0);
  }
  if (!response.ok) throw new ApiError(response.status);
  try { return await response.json() as T; }
  catch { throw new ApiError(0); }
}
export const register = (body: RegisterRequest) =>
  apiRequest<User>('/auth/register', { method: 'POST', body: JSON.stringify(body) });
export const login = (body: LoginRequest) =>
  apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify(body) });
export const getCurrentUser = (token: string) => apiRequest<User>('/users/me', {}, token);

export function authError(error: unknown, action: 'login' | 'register'): string {
  if (error instanceof ApiError) {
    if (error.status === 401 && action === 'login') return 'Invalid email or password.';
    if (error.status === 409 && action === 'register') return 'This email is already registered. Please log in.';
    if (error.status === 422) return 'Please check your details and try again.';
    if (error.status === 0) return 'Unable to connect. Please try again.';
  }
  return 'Something went wrong. Please try again.';
}
