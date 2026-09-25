import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { TOKEN_KEY } from '../auth/AuthContext';

const home = { id: 'home', name: 'Alex Home', currency: 'CNY', timezone: 'Asia/Kuala_Lumpur' };
const balances = [
  { membership_id: 'alex', user_id: 'a', display_name: 'Alex', role: 'OWNER', status: 'ACTIVE', paid_minor: 10000, allocated_minor: 5000, balance_minor: 5000 },
  { membership_id: 'blair', user_id: 'b', display_name: 'Blair', role: 'MEMBER', status: 'ACTIVE', paid_minor: 0, allocated_minor: 5000, balance_minor: -5000 },
  { membership_id: 'casey', user_id: 'c', display_name: 'Casey', role: 'MEMBER', status: 'DEPARTED', paid_minor: 0, allocated_minor: 0, balance_minor: 0 },
];
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const fetchMock = vi.fn();
beforeEach(() => {
  sessionStorage.clear();
  sessionStorage.setItem(TOKEN_KEY, 'token');
  window.history.replaceState({}, '', '/households/home/balances');
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: string) => {
    if (url === '/api/users/me') return reply({ id: 'a', display_name: 'Alex', email: 'alex@example.com' });
    if (url === '/api/households/home') return reply(home);
    if (url === '/api/households/home/balances') return reply(balances);
    throw new Error('Unexpected URL');
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
it('shows loading then paid, allocated and signed balances including departed zero members', async () => {
  let resolve!: (response: Response) => void;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(url => url.endsWith('/balances') ? new Promise<Response>(done => { resolve = done; }) : original(url));
  render(<App />);
  expect(await screen.findByRole('status')).toHaveTextContent(/Restoring|Loading/);
  await screen.findByText('Loading balances…');
  await act(async () => resolve(reply(balances)));
  const rows = screen.getAllByRole('listitem');
  expect(rows).toHaveLength(3);
  expect(within(rows[0]).getAllByRole('definition').map(node => node.textContent)).toEqual(['¥100.00', '¥50.00', '¥50.00 — Owed to this member']);
  expect(within(rows[1]).getAllByRole('definition').map(node => node.textContent)).toEqual(['¥0.00', '¥50.00', '-¥50.00 — Owed by this member']);
  expect(rows[2]).toHaveTextContent('Casey');
  expect(rows[2]).toHaveTextContent('DEPARTED');
  expect(rows[2]).toHaveTextContent('¥0.00 — Nothing owed');
  expect(fetchMock).toHaveBeenCalledTimes(3);
});
it('renders returned balance without recomputing it and uses real household currency', async () => {
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(url => url.endsWith('/balances') ? Promise.resolve(reply([{ ...balances[0], balance_minor: 123 }])) : url === '/api/households/home' ? Promise.resolve(reply({ ...home, currency: 'MYR' })) : original(url));
  render(<App />);
  expect(await screen.findByText('MYR 1.23 — Owed to this member')).toBeInTheDocument();
});
it.each([401, 404, 500])('shows a safe error for HTTP %s', async status => {
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation(url => url.endsWith('/balances') ? Promise.resolve(reply({ detail: 'SQL secret' }, status)) : original(url));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent(status === 401 ? 'Your session has expired' : status === 404 ? "Household not found or you don't have access" : 'Unable to load balances');
  expect(screen.queryByText(/SQL secret/)).not.toBeInTheDocument();
});
it('protects the route without an authenticated session', async () => {
  sessionStorage.clear();
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
it('keeps Bills navigation and opens Balances from Household detail', async () => {
  window.history.replaceState({}, '', '/households/home');
  render(<App />);
  const link = await screen.findByRole('link', { name: 'Balances' });
  expect(link).toHaveAttribute('href', '/households/home/balances');
  expect(screen.getByRole('link', { name: 'Bills' })).toHaveAttribute('href', '/households/home/bills');
  fireEvent.click(link);
  expect(await screen.findByRole('heading', { name: 'Alex Home — Balances' })).toBeInTheDocument();
});
