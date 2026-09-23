import { useRef, useState, type FormEvent } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import { authError, register } from './api/auth';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { HouseholdDetail, HouseholdList } from './households/HouseholdPages';

function AuthForm({ mode }: { mode: 'login' | 'register' }) {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submitting = useRef(false);
  const registration = mode === 'register';
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError('');
    const submittedPassword = password;
    setPassword('');
    try {
      if (registration) {
        await register({ email, display_name: displayName, password: submittedPassword });
        navigate('/login', { replace: true, state: { registered: true } });
      } else {
        await login({ email, password: submittedPassword });
        navigate('/', { replace: true });
      }
    } catch (failure) {
      setError(authError(failure, mode));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return <section className="auth-card">
    <h2>{registration ? 'Create an account' : 'Log in'}</h2>
    {!registration && location.state?.registered && <p role="status">Account created. Please log in.</p>}
    {error && <p role="alert">{error}</p>}
    <form onSubmit={submit} aria-busy={busy}>
      <fieldset disabled={busy}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
        {registration && <>
          <label htmlFor="display-name">Display name</label>
          <input id="display-name" autoComplete="nickname" maxLength={100} required value={displayName} onChange={e => setDisplayName(e.target.value)} />
        </>}
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete={registration ? 'new-password' : 'current-password'} maxLength={1024} required value={password} onChange={e => setPassword(e.target.value)} />
        <button type="submit">{busy ? 'Please wait…' : registration ? 'Register' : 'Log in'}</button>
      </fieldset>
    </form>
    {!busy && <p>{registration ? <Link to="/login">Already registered? Log in</Link> : <Link to="/register">Create an account</Link>}</p>}
  </section>;
}
function HouseholdScreen({ detail = false }: { detail?: boolean }) {
  const { user, logout, getAccessToken } = useAuth();
  const { householdId } = useParams();
  const token = getAccessToken();
  if (!user || !token) return <Navigate to="/login" replace />;
  return <>
    <header className="app-header">
      <div><h2>Welcome, {user.display_name}</h2><p>{user.email}</p></div>
      <nav aria-label="Account"><Link to="/households">Households</Link><button onClick={logout}>Logout</button></nav>
    </header>
    {detail && householdId ? <HouseholdDetail key={householdId} token={token} householdId={householdId} /> : <HouseholdList token={token} />}
  </>;
}
function AuthRoutes() {
  const { user, loading, getAccessToken } = useAuth();
  const authenticated = Boolean(user && getAccessToken());
  if (loading) return <p role="status">Restoring your session…</p>;
  return <Routes>
    <Route path="/login" element={authenticated ? <Navigate to="/" replace /> : <AuthForm key="login" mode="login" />} />
    <Route path="/register" element={authenticated ? <Navigate to="/" replace /> : <AuthForm key="register" mode="register" />} />
    <Route path="/" element={<Navigate to={authenticated ? '/households' : '/login'} replace />} />
    <Route path="/households" element={<HouseholdScreen />} />
    <Route path="/households/:householdId" element={<HouseholdScreen detail />} />
    <Route path="*" element={<Navigate to={authenticated ? '/' : '/login'} replace />} />
  </Routes>;
}
export default function App() {
  return <BrowserRouter><AuthProvider><main>
    <h1>ShareHome</h1>
    <p>Shared household expenses, made clear.</p>
    <AuthRoutes />
  </main></AuthProvider></BrowserRouter>;
}
