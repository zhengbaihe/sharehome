import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { balanceError, getBalances, type MembershipBalance } from '../api/balances';
import { getHousehold, type Household } from '../api/households';
import { formatMoney } from '../bills/values';

export function BalancePage({ token, householdId }: { token: string; householdId: string }) {
  const [data, setData] = useState<{ household: Household; balances: MembershipBalance[] } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    Promise.all([getHousehold(token, householdId), getBalances(token, householdId)])
      .then(([household, balances]) => { if (active) setData({ household, balances }); })
      .catch(failure => { if (active) setError(balanceError(failure)); });
    return () => { active = false; };
  }, [token, householdId]);
  return <section>
    <p><Link to={`/households/${householdId}`}>Back to household</Link></p>
    <h2>{data ? `${data.household.name} — Balances` : 'Balances'}</h2>
    {error ? <p role="alert">{error}</p> : !data ? <p role="status">Loading balances…</p> : <>
      <p>Positive balances are owed to the member. Negative balances are owed by the member.</p>
      {data.balances.length === 0 ? <p>No members to display.</p> : <ul className="household-list">
        {data.balances.map(member => <li className="auth-card" key={member.membership_id}>
          <h3>{member.display_name}</h3>
          <p>{member.role} · {member.status}</p>
          <dl>
            <dt>Paid</dt><dd>{formatMoney(member.paid_minor, data.household.currency)}</dd>
            <dt>Allocated</dt><dd>{formatMoney(member.allocated_minor, data.household.currency)}</dd>
            <dt>Balance</dt><dd>{formatMoney(member.balance_minor, data.household.currency)}
              {' — '}{member.balance_minor > 0 ? 'Owed to this member' : member.balance_minor < 0 ? 'Owed by this member' : 'Nothing owed'}
            </dd>
          </dl>
        </li>)}
      </ul>}
    </>}
  </section>;
}
