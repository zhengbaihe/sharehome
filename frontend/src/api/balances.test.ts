import { afterEach, expect, it, vi } from 'vitest';
import { getBalances } from './balances';

afterEach(() => vi.unstubAllGlobals());
it('uses the Household balance endpoint with Bearer authentication', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('[]'));
  vi.stubGlobal('fetch', fetchMock);
  expect(await getBalances('token', 'home')).toEqual([]);
  expect(fetchMock.mock.calls[0][0]).toBe('/api/households/home/balances');
  expect(fetchMock.mock.calls[0][1].method).toBe('GET');
  expect(fetchMock.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer token');
});
