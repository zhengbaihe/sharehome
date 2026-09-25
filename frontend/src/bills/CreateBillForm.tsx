import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { billError, createBill, type HouseholdMember } from '../api/bills';
import { parseAmount, toPaidAt } from './values';

export function CreateBillForm({ token, householdId, currency, members }: {
  token: string; householdId: string; currency: string; members: HouseholdMember[];
}) {
  const [description, setDescription] = useState('');
  const [amount, setAmount] = useState('');
  const [paidAt, setPaidAt] = useState('');
  const [payer, setPayer] = useState('');
  const [participants, setParticipants] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const mounted = useRef(true);
  const navigate = useNavigate();
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    setError('');
    let amountMinor: number;
    let paidAtIso: string;
    try {
      if (!description.trim()) throw new Error('Enter a description.');
      amountMinor = parseAmount(amount);
      paidAtIso = toPaidAt(paidAt);
      if (!payer) throw new Error('Select a payer.');
      if (participants.length === 0) throw new Error('Select at least one participant.');
    } catch (failure) {
      setError((failure as Error).message);
      return;
    }
    pending.current = true;
    setBusy(true);
    try {
      const created = await createBill(token, householdId, {
        description: description.trim(), amount_minor: amountMinor, paid_at: paidAtIso,
        payer_membership_id: payer, participant_membership_ids: participants,
      });
      if (mounted.current) navigate(`/households/${householdId}/bills/${created.id}`);
    } catch (failure) {
      if (mounted.current) setError(billError(failure, 'create bill'));
    } finally {
      pending.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  if (members.length === 0) return <p>No active members are available for bill creation.</p>;
  return <section className="auth-card">
    <h3>Create an EQUAL bill</h3>
    {error && <p role="alert">{error}</p>}
    <form onSubmit={submit} aria-busy={busy}>
      <fieldset disabled={busy}>
        <label htmlFor="bill-description">Description</label>
        <input id="bill-description" required maxLength={255} value={description} onChange={e => setDescription(e.target.value)} />
        <label htmlFor="bill-amount">Amount ({currency})</label>
        <input id="bill-amount" required inputMode="decimal" placeholder="100.00" value={amount} onChange={e => setAmount(e.target.value)} />
        <label htmlFor="bill-paid-at">Paid date and time</label>
        <input id="bill-paid-at" required type="datetime-local" step="60" value={paidAt} onChange={e => setPaidAt(e.target.value)} />
        <small>Uses your device's local timezone.</small>
        <label htmlFor="bill-payer">Payer</label>
        <select id="bill-payer" required value={payer} onChange={e => setPayer(e.target.value)}>
          <option value="">Select payer</option>
          {members.map(member => <option key={member.membership_id} value={member.membership_id}>{member.display_name}</option>)}
        </select>
        <fieldset className="participants"><legend>Participants</legend>
          {members.map(member => <label key={member.membership_id}>
            <input type="checkbox" checked={participants.includes(member.membership_id)} onChange={e => setParticipants(current => e.target.checked ? [...current, member.membership_id] : current.filter(id => id !== member.membership_id))} /> {member.display_name}
          </label>)}
        </fieldset>
        <button type="submit">{busy ? 'Creating bill…' : 'Create bill'}</button>
      </fieldset>
    </form>
  </section>;
}
