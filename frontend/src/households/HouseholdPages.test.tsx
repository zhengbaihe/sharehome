import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
import { TOKEN_KEY } from '../auth/AuthContext';
const user = { id: 'user', display_name: 'Alex', email: 'alex@example.com', created_at: '2026-01-01', updated_at: '2026-01-01' };
const home = { id: 'home-id', name: 'Alex Home', currency: 'CNY', timezone: 'Asia/Kuala_Lumpur', created_at: '2026-01-01', updated_at: '2026-01-01' };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const fetchMock = vi.fn();
beforeEach(() => {
  sessionStorage.clear();
  sessionStorage.setItem(TOKEN_KEY, 'token');
  window.history.replaceState({}, '', '/households');
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
  fetchMock.mockResolvedValueOnce(reply(user));
});
afterEach(() => vi.unstubAllGlobals());
it('shows list loading then empty state and the name-only creation form', async () => {
  let resolve!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }));
  render(<App />);
  expect(await screen.findByText('Loading households…')).toBeInTheDocument();
  await act(async () => resolve(reply([])));
  expect(await screen.findByText("You don't have a household yet.")).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Create household' })).toBeInTheDocument();
  expect(screen.getAllByRole('textbox')).toHaveLength(1);
  expect(screen.getByLabelText('Household name')).toBeRequired();
});
it('lists public household fields and navigates to fetched detail and back', async () => {
  fetchMock.mockResolvedValueOnce(reply([home])).mockResolvedValueOnce(reply(home)).mockResolvedValueOnce(reply([home]));
  render(<App />);
  const link = await screen.findByRole('link', { name: home.name });
  expect(link).toHaveAttribute('href', '/households/home-id');
  expect(screen.getByText(home.currency)).toBeInTheDocument();
  expect(screen.getByText(home.timezone)).toBeInTheDocument();
  fireEvent.click(link);
  expect(await screen.findByRole('heading', { name: home.name })).toBeInTheDocument();
  expect(fetchMock.mock.calls[2][0]).toBe('/api/households/home-id');
  expect(screen.queryByText('OWNER')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Back to households' }));
  expect(await screen.findByRole('link', { name: home.name })).toBeInTheDocument();
});
it('shows a clean list failure', async () => {
  fetchMock.mockResolvedValueOnce(reply({ detail: 'private SQL text' }, 500));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to complete the household request. Please try again.');
  expect(screen.queryByText(/private SQL/)).not.toBeInTheDocument();
});
it('creates, blocks repeat submission and navigates to real fetched detail', async () => {
  let resolve!: (response: Response) => void;
  fetchMock.mockResolvedValueOnce(reply([]))
    .mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }))
    .mockResolvedValueOnce(reply(home));
  render(<App />);
  await screen.findByText("You don't have a household yet.");
  fireEvent.change(screen.getByLabelText('Household name'), { target: { value: ' Alex Home ' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create household' }));
  expect(screen.getByRole('button', { name: 'Creating…' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Creating…' }));
  expect(fetchMock).toHaveBeenCalledTimes(3);
  expect(fetchMock.mock.calls[2][0]).toBe('/api/households');
  expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ name: 'Alex Home' });
  await act(async () => resolve(reply(home, 201)));
  expect(await screen.findByRole('heading', { name: home.name })).toBeInTheDocument();
  expect(window.location.pathname).toBe('/households/home-id');
  expect(fetchMock.mock.calls[3][0]).toBe('/api/households/home-id');
});
it.each([422, 500])('shows sanitized creation error %s', async status => {
  fetchMock.mockResolvedValueOnce(reply([])).mockResolvedValueOnce(reply({ detail: 'private SQL text' }, status));
  render(<App />);
  await screen.findByText("You don't have a household yet.");
  fireEvent.change(screen.getByLabelText('Household name'), { target: { value: 'Home' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create household' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(status === 422 ? 'Please check the household details' : 'Unable to complete the household request');
  expect(screen.getByRole('button', { name: 'Create household' })).toBeEnabled();
  expect(window.location.pathname).toBe('/households');
});
it('loads detail directly using route ID and displays its loading state', async () => {
  window.history.replaceState({}, '', '/households/home-id');
  let resolve!: (response: Response) => void;
  fetchMock.mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }));
  render(<App />);
  expect(await screen.findByText('Loading household…')).toBeInTheDocument();
  await act(async () => resolve(reply(home)));
  expect(await screen.findByRole('heading', { name: home.name })).toBeInTheDocument();
  expect(screen.getByText(home.currency)).toBeInTheDocument();
  expect(screen.getByText(home.timezone)).toBeInTheDocument();
});
it('does not distinguish missing and inaccessible households', async () => {
  window.history.replaceState({}, '', '/households/missing');
  fetchMock.mockResolvedValueOnce(reply({ detail: 'private detail' }, 404));
  render(<App />);
  expect(await screen.findByRole('alert')).toHaveTextContent("Household not found or you don't have access.");
  expect(screen.getByRole('link', { name: 'Back to households' })).toBeInTheDocument();
});
it.each(['/households', '/households/home-id'])('protects %s when unauthenticated', async path => {
  sessionStorage.clear();
  window.history.replaceState({}, '', path);
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
it('uses the household workflow as the authenticated landing page and supports logout', async () => {
  window.history.replaceState({}, '', '/');
  fetchMock.mockResolvedValueOnce(reply([]));
  render(<App />);
  await screen.findByText("You don't have a household yet.");
  expect(window.location.pathname).toBe('/households');
  fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
it('does not restore a household screen after logout during pending creation', async () => {
  let resolve!: (response: Response) => void;
  fetchMock.mockResolvedValueOnce(reply([])).mockReturnValueOnce(new Promise<Response>(done => { resolve = done; }));
  render(<App />);
  await screen.findByText("You don't have a household yet.");
  fireEvent.change(screen.getByLabelText('Household name'), { target: { value: 'Home' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create household' }));
  fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
  await act(async () => resolve(reply(home, 201)));
  await waitFor(() => expect(window.location.pathname).toBe('/login'));
  expect(screen.queryByText(home.name)).not.toBeInTheDocument();
});
