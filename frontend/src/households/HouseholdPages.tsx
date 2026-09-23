import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { createHousehold, getHousehold, getHouseholds, householdError, type Household } from '../api/households';

function HouseholdInfo({ household }: { household: Household }) {
  return <dl><dt>Currency</dt><dd>{household.currency}</dd><dt>Timezone</dt><dd>{household.timezone}</dd></dl>;
}
function CreateHousehold({ token }: { token: string }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const mounted = useRef(true);
  const navigate = useNavigate();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    if (!name.trim()) { setError('Please enter a household name.'); return; }
    pending.current = true;
    setBusy(true);
    setError('');
    try {
      const household = await createHousehold(token, { name: name.trim() });
      if (mounted.current) navigate(`/households/${household.id}`);
    } catch (failure) {
      if (mounted.current) setError(householdError(failure));
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return <section className="auth-card">
    <h3>Create a household</h3>
    {error && <p role="alert">{error}</p>}
    <form onSubmit={submit} aria-busy={busy}>
      <fieldset disabled={busy}>
        <label htmlFor="household-name">Household name</label>
        <input id="household-name" required maxLength={100} value={name} onChange={event => setName(event.target.value)} />
        <button type="submit">{busy ? 'Creating…' : 'Create household'}</button>
      </fieldset>
    </form>
  </section>;
}
export function HouseholdList({ token }: { token: string }) {
  const [households, setHouseholds] = useState<Household[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getHouseholds(token).then(result => {
      if (active) setHouseholds(result);
    }).catch(failure => {
      if (active) setError(householdError(failure));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token]);
  return <section>
    <h2>Households</h2>
    {loading ? <p role="status">Loading households…</p> : error ? <p role="alert">{error}</p> :
      households.length === 0 ? <p>You don't have a household yet.</p> :
      <ul className="household-list">{households.map(household => <li key={household.id} className="auth-card">
        <h3><Link to={`/households/${household.id}`}>{household.name}</Link></h3>
        <HouseholdInfo household={household} />
      </li>)}</ul>}
    <CreateHousehold token={token} />
  </section>;
}
export function HouseholdDetail({ token, householdId }: { token: string; householdId: string }) {
  const [household, setHousehold] = useState<Household | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    getHousehold(token, householdId).then(result => {
      if (active) setHousehold(result);
    }).catch(failure => {
      if (active) setError(householdError(failure));
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, householdId]);
  return <section>
    <p><Link to="/households">Back to households</Link></p>
    {loading ? <p role="status">Loading household…</p> : error ? <p role="alert">{error}</p> : household &&
      <article className="auth-card"><h2>{household.name}</h2><HouseholdInfo household={household} /></article>}
  </section>;
}
