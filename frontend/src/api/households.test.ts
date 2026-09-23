import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ApiError } from './auth';
import { createHousehold, getHousehold, getHouseholds } from './households';
const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => vi.unstubAllGlobals());
it('lists households with a Bearer header', async () => {
  fetchMock.mockResolvedValue(new Response('[]'));
  expect(await getHouseholds('token')).toEqual([]);
  const [path, options] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/households');
  expect(options.method).toBe('GET');
  expect(options.headers.get('Authorization')).toBe('Bearer token');
});
it('creates with only the supported name field', async () => {
  fetchMock.mockResolvedValue(new Response('{}', { status: 201 }));
  await createHousehold('token', { name: 'Alex Home' });
  const [path, options] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/households');
  expect(options.method).toBe('POST');
  expect(options.body).toBe(JSON.stringify({ name: 'Alex Home' }));
  expect(options.headers.get('Authorization')).toBe('Bearer token');
});
it('reads the requested household', async () => {
  fetchMock.mockResolvedValue(new Response('{}'));
  await getHousehold('token', 'home-id');
  const [path, options] = fetchMock.mock.calls[0];
  expect(path).toBe('/api/households/home-id');
  expect(options.method).toBe('GET');
  expect(options.headers.get('Authorization')).toBe('Bearer token');
});
it('uses predictable sanitized errors', async () => {
  fetchMock.mockResolvedValue(new Response('private SQL detail', { status: 500 }));
  await expect(getHouseholds('token')).rejects.toEqual(new ApiError(500));
});
