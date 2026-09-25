import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from './auth';
import { createBill, getBill, getBills, getHouseholdMembers } from './bills';
const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => vi.unstubAllGlobals());
it.each([
  [() => getHouseholdMembers('token', 'home'), '/api/households/home/members'],
  [() => getBills('token', 'home'), '/api/households/home/bills'],
  [() => getBill('token', 'home', 'bill'), '/api/households/home/bills/bill'],
] as const)('uses the exact authenticated GET path', async (operation, path) => {
  fetchMock.mockResolvedValue(new Response('[]'));
  await operation();
  expect(fetchMock.mock.calls[0][0]).toBe(path);
  expect(fetchMock.mock.calls[0][1].method).toBe('GET');
  expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer token');
});
it('posts only the actual bill creation contract', async () => {
  const body = { description: 'Internet', amount_minor: 10000, payer_membership_id: 'alex', participant_membership_ids: ['blair'], paid_at: '2026-09-25T00:00:00Z' };
  fetchMock.mockResolvedValue(new Response('{}', { status: 201 }));
  await createBill('token', 'home', body);
  expect(fetchMock.mock.calls[0][0]).toBe('/api/households/home/bills');
  expect(fetchMock.mock.calls[0][1].method).toBe('POST');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(body);
  expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer token');
});
it('normalizes errors without server detail', async () => {
  fetchMock.mockResolvedValue(new Response('SQL secret', { status: 422 }));
  await expect(getBills('token', 'home')).rejects.toEqual(new ApiError(422));
});
