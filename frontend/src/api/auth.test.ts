import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError, register, login, getCurrentUser } from './auth';
const fetchMock = vi.fn();
beforeEach(() => { vi.stubGlobal('fetch', fetchMock); fetchMock.mockReset(); });
afterEach(() => vi.unstubAllGlobals());

it.each([
  ['register', register, '/api/auth/register', { email: 'alex@example.com', password: 'secret', display_name: 'Alex' }],
  ['login', login, '/api/auth/login', { email: 'alex@example.com', password: 'secret', display_name: 'Alex' }],
] as const)('%s posts the expected JSON', async (_, operation, path, body) => {
  fetchMock.mockResolvedValue(new Response(JSON.stringify({ id: 'user' }), { status: 200 }));
  await operation(body);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe(path);
  expect(options.method).toBe('POST');
  expect(JSON.parse(options.body)).toEqual(body);
  expect(options.headers.get('Content-Type')).toBe('application/json');
  expect(options.headers.has('Authorization')).toBe(false);
});
it('sends the Bearer token only in the header', async () => {
  fetchMock.mockResolvedValue(new Response('{}'));
  await getCurrentUser('test-token');
  expect(fetchMock.mock.calls[0][0]).toBe('/api/users/me');
  expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer test-token');
});
it.each([401, 422, 500])('sanitizes HTTP %s errors', async status => {
  fetchMock.mockResolvedValue(new Response('private SQL error', { status }));
  await expect(getCurrentUser('token')).rejects.toEqual(new ApiError(status));
});
it('normalizes network errors', async () => {
  fetchMock.mockRejectedValue(new Error('private network details'));
  await expect(getCurrentUser('token')).rejects.toEqual(new ApiError(0));
});
