import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { TOKEN_KEY } from '../auth/AuthContext';
const home = { id: 'home', name: 'Alex Home', currency: 'CNY', timezone: 'Asia/Kuala_Lumpur', created_at: '', updated_at: '' };
const members = [
  { membership_id: 'alex-member', user_id: 'alex-user', display_name: 'Alex', role: 'OWNER', status: 'ACTIVE' },
  { membership_id: 'blair-member', user_id: 'blair-user', display_name: 'Blair', role: 'MEMBER', status: 'ACTIVE' },
];
const bill = {
  id: 'bill', household_id: 'home', description: 'Internet', amount_minor: 10000,
  payer_membership_id: 'alex-member', paid_at: '2026-09-25T00:00:00Z', split_method: 'EQUAL', created_at: '', updated_at: '',
  allocations: [
    { id: 'a', membership_id: 'alex-member', amount_minor: 3334, created_at: '' },
    { id: 'b', membership_id: 'blair-member', amount_minor: 3333, created_at: '' },
    { id: 'c', membership_id: 'departed-member', amount_minor: 3333, created_at: '' },
  ],
};
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const fetchMock = vi.fn();
let bills: typeof bill[];
let post: (body: unknown) => Promise<Response>;
beforeEach(() => {
  sessionStorage.clear(); sessionStorage.setItem(TOKEN_KEY, 'token');
  window.history.replaceState({}, '', '/households/home/bills');
  bills = [];
  post = async () => reply(bill, 201);
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: string, options: RequestInit = {}) => {
    if (url === '/api/users/me') return reply({ id: 'alex-user', display_name: 'Alex', email: 'alex@example.com' });
    if (url === '/api/households/home') return reply(home);
    if (url === '/api/households/home/members') return reply(members);
    if (url === '/api/households/home/bills') return options.method === 'POST' ? post(JSON.parse(options.body as string)) : reply(bills);
    if (url === '/api/households/home/bills/bill') return reply(bill);
    throw new Error('Unexpected test URL');
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
async function form() {
  render(<App />);
  await screen.findByRole('heading', { name: 'Create an EQUAL bill' });
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Internet' } });
  fireEvent.change(screen.getByLabelText('Amount (CNY)'), { target: { value: '100.00' } });
  fireEvent.change(screen.getByLabelText('Paid date and time'), { target: { value: '2026-09-25T14:30' } });
  fireEvent.change(screen.getByLabelText('Payer'), { target: { value: 'alex-member' } });
}
const posts = () => fetchMock.mock.calls.filter(([, options]) => options?.method === 'POST');
it('shows loading and an empty list with member controls', async () => {
  let resolve!: (response: Response) => void;
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url, options) => url.endsWith('/members') ? new Promise<Response>(done => { resolve = done; }) : original(url, options));
  render(<App />);
  expect(await screen.findByText('Loading bills and members…')).toBeInTheDocument();
  await act(async () => resolve(reply(members)));
  expect(await screen.findByText('No bills yet.')).toBeInTheDocument();
  expect(within(screen.getByLabelText('Payer')).getByRole('option', { name: 'Alex' })).toHaveValue('alex-member');
  expect(screen.getAllByRole('checkbox')).toHaveLength(2);
  expect(screen.getByRole('checkbox', { name: 'Blair' })).not.toBeChecked();
  expect(screen.getAllByRole('textbox')).toHaveLength(2);
});
it('preserves backend list ordering and formats amounts', async () => {
  bills = [{ ...bill, id: 'second', description: 'Water' }, bill];
  render(<App />);
  const link = await screen.findByRole('link', { name: 'Internet' });
  expect(link).toHaveAttribute('href', '/households/home/bills/bill');
  expect(screen.getAllByText('¥100.00')).toHaveLength(2);
  const list = screen.getByRole('list');
  expect(within(list).getAllByRole('link').map(item => item.textContent)).toEqual(['Water', 'Internet']);
  expect(fetchMock).toHaveBeenCalledTimes(4);
});
it.each(['/members', '/bills'])('shows a clean loading failure for %s', async suffix => {
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url, options) => url.endsWith(suffix) ? Promise.resolve(reply({ detail: 'SQL secret' }, 500)) : original(url, options));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load bills and members.');
  expect(screen.queryByText('SQL secret')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Create bill' })).not.toBeInTheDocument();
});
it('submits exact IDs, amount and zoned time without adding payer, then reads authoritative detail', async () => {
  let resolve!: (response: Response) => void;
  post = () => new Promise<Response>(done => { resolve = done; });
  await form();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Blair' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create bill' }));
  expect(screen.getByRole('button', { name: 'Creating bill…' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Creating bill…' }));
  expect(posts()).toHaveLength(1);
  const body = JSON.parse(posts()[0][1].body);
  expect(body).toEqual({ description: 'Internet', amount_minor: 10000, payer_membership_id: 'alex-member', participant_membership_ids: ['blair-member'], paid_at: new Date(2026, 8, 25, 14, 30).toISOString() });
  await act(async () => resolve(reply(bill, 201)));
  expect(await screen.findByRole('heading', { name: 'Allocations' })).toBeInTheDocument();
  expect(window.location.pathname).toBe('/households/home/bills/bill');
  expect(screen.getByText('¥33.34')).toBeInTheDocument();
  expect(screen.getAllByText('¥33.33')).toHaveLength(2);
});
it('rejects empty participants before a POST', async () => {
  await form();
  fireEvent.click(screen.getByRole('button', { name: 'Create bill' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Select at least one participant.');
  expect(posts()).toHaveLength(0);
});
it('rejects invalid amount before a POST', async () => {
  await form();
  fireEvent.change(screen.getByLabelText('Amount (CNY)'), { target: { value: '1.001' } });
  fireEvent.click(screen.getByRole('checkbox', { name: 'Alex' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create bill' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('at most two decimal places');
  expect(posts()).toHaveLength(0);
});
it.each([422, 500])('sanitizes creation error %s', async status => {
  post = async () => reply({ detail: 'SQL secret' }, status);
  await form();
  fireEvent.click(screen.getByRole('checkbox', { name: 'Alex' }));
  fireEvent.click(screen.getByRole('button', { name: 'Create bill' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(status === 422 ? 'Please check the bill details' : 'Unable to create bill.');
  expect(screen.getByRole('button', { name: 'Create bill' })).toBeEnabled();
});
it('shows persisted detail with exact allocations, names and historical fallback without balances', async () => {
  window.history.replaceState({}, '', '/households/home/bills/bill');
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Internet' })).toBeInTheDocument();
  expect(screen.getByText('¥100.00')).toBeInTheDocument();
  expect(screen.getAllByText('Alex')).toHaveLength(2);
  const rows = screen.getAllByRole('listitem');
  expect(rows.map(row => row.textContent)).toEqual(['Alex¥33.34', 'Blair¥33.33', 'Member departed¥33.33']);
  expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain('/api/households/home/balances');
  expect(screen.getByRole('link', { name: 'Back to bills' })).toHaveAttribute('href', '/households/home/bills');
});
it('shows a safe 404 detail error', async () => {
  window.history.replaceState({}, '', '/households/home/bills/bill');
  const original = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url, options) => url.endsWith('/bills/bill') ? Promise.resolve(reply({}, 404)) : original(url, options));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Bill or household not found, or you do not have access.');
});
it.each(['/households/home/bills', '/households/home/bills/bill'])('protects %s', async path => {
  sessionStorage.clear(); window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
it('links Household detail to Bills', async () => {
  window.history.replaceState({}, '', '/households/home');
  render(<App />);
  expect(await screen.findByRole('link', { name: 'Bills' })).toHaveAttribute('href', '/households/home/bills');
});
