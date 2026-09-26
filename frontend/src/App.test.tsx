import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
import { TOKEN_KEY } from './auth/AuthContext';

const user = { id: 'alex-id', email: 'alex@example.com', display_name: 'Alex', created_at: '2026-09-01', updated_at: '2026-09-01' };
const fetchMock = vi.fn();
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  window.history.replaceState({}, '', '/login');
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());
function fillLogin() {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } });
}

it('redirects unauthenticated visitors to login without a network request', async () => {
  window.history.replaceState({}, '', '/');
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText('Email')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/login');
  expect(fetchMock).not.toHaveBeenCalled();
});
it('logs in, retrieves identity, stores only the token and logs out locally', async () => {
  fetchMock.mockResolvedValueOnce(reply({ access_token: 'login-token', token_type: 'bearer' }))
    .mockResolvedValueOnce(reply(user)).mockResolvedValueOnce(reply([]));
  render(<App />);
  fillLogin();
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
  expect(await screen.findByRole('heading', { name: 'Welcome, Alex' })).toBeInTheDocument();
  expect(screen.getByText(user.email)).toBeInTheDocument();
  expect(sessionStorage.getItem(TOKEN_KEY)).toBe('login-token');
  expect(sessionStorage.length).toBe(1);
  expect(localStorage.length).toBe(0);
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  expect(fetchMock.mock.calls[1][0]).toBe('/api/users/me');
  expect(fetchMock.mock.calls[1][1].headers.get('Authorization')).toBe('Bearer login-token');
  fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
  expect(screen.queryByText(user.email)).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(3);
});
it('shows a generic invalid-credentials error and clears the password', async () => {
  fetchMock.mockResolvedValue(reply({ detail: 'private server detail' }, 401));
  render(<App />);
  fillLogin();
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
  expect(screen.getByLabelText('Password')).toHaveValue('');
  expect(sessionStorage.length).toBe(0);
  expect(screen.queryByText('private server detail')).not.toBeInTheDocument();
});
it('blocks duplicate submissions while login is pending', async () => {
  let resolve!: (response: Response) => void;
  fetchMock.mockReturnValue(new Promise<Response>(done => { resolve = done; }));
  render(<App />);
  fillLogin();
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
  const pending = screen.getByRole('button', { name: 'Please wait…' });
  expect(pending).toBeDisabled();
  fireEvent.click(pending);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  await act(async () => resolve(reply({}, 401)));
});
it('registers and returns to login with confirmation without persisting a password', async () => {
  window.history.replaceState({}, '', '/register');
  fetchMock.mockResolvedValue(reply(user, 201));
  render(<App />);
  fillLogin();
  fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Alex' } });
  fireEvent.click(screen.getByRole('button', { name: 'Register' }));
  expect(await screen.findByText('Account created. Please log in.')).toBeInTheDocument();
  expect(window.location.pathname).toBe('/login');
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/register');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ email: user.email, password: 'test-password', display_name: 'Alex' });
  expect(sessionStorage.length).toBe(0);
  expect(localStorage.length).toBe(0);
  expect(screen.getByLabelText('Password')).toHaveValue('');
});
it.each([
  [409, 'This email is already registered. Please log in.'],
  [422, 'Please check your details and try again.'],
  [500, 'Something went wrong. Please try again.'],
])('handles registration HTTP %s safely', async (status, message) => {
  window.history.replaceState({}, '', '/register');
  fetchMock.mockResolvedValue(reply({ detail: 'SQL secret' }, status));
  render(<App />);
  fillLogin();
  fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Alex' } });
  fireEvent.click(screen.getByRole('button', { name: 'Register' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
  expect(screen.getByLabelText('Password')).toHaveValue('');
  expect(sessionStorage.length).toBe(0);
});
it('restores a stored token via users/me and redirects away from login', async () => {
  sessionStorage.setItem(TOKEN_KEY, 'stored-token');
  fetchMock.mockResolvedValueOnce(reply(user)).mockResolvedValueOnce(reply([]));
  render(<App />);
  expect(screen.getByRole('status')).toHaveTextContent('Restoring');
  expect(await screen.findByRole('heading', { name: 'Welcome, Alex' })).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/users/me', expect.objectContaining({ headers: expect.any(Headers) }));
  const restorationRequest = fetchMock.mock.calls.find(([url]) => url === '/api/users/me')!;
  expect(restorationRequest[1].method ?? 'GET').toBe('GET');
  expect(restorationRequest[1].headers.get('Authorization')).toBe('Bearer stored-token');
  // Wait for the destination page's effect, not an incidental fetch-call count.
  expect(await screen.findByText("You don't have a household yet.")).toBeInTheDocument();
  expect(window.location.pathname).toBe('/households');
  expect(screen.queryByRole('heading', { name: 'Log in' })).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  expect(sessionStorage.getItem(TOKEN_KEY)).toBe('stored-token');
});
it('removes an invalid stored token', async () => {
  sessionStorage.setItem(TOKEN_KEY, 'expired');
  fetchMock.mockResolvedValue(reply({}, 401));
  render(<App />);
  expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument();
  expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
});
it('does not authenticate when users/me rejects a login token', async () => {
  fetchMock.mockResolvedValueOnce(reply({ access_token: 'bad', token_type: 'bearer' }))
    .mockResolvedValueOnce(reply({}, 401));
  render(<App />);
  fillLogin();
  fireEvent.click(screen.getByRole('button', { name: 'Log in' }));
  await screen.findByRole('alert');
  expect(sessionStorage.length).toBe(0);
  expect(screen.queryByText('Welcome, Alex')).not.toBeInTheDocument();
});
it('navigates between registration and login', async () => {
  render(<App />);
  fireEvent.click(screen.getByRole('link', { name: 'Create an account' }));
  expect(await screen.findByLabelText('Display name')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('link', { name: 'Already registered? Log in' }));
  await waitFor(() => expect(screen.queryByLabelText('Display name')).not.toBeInTheDocument());
});
