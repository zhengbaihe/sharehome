import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { billError, getBill, getBills, getHouseholdMembers, type Bill, type HouseholdMember } from '../api/bills';
import { getHousehold, type Household } from '../api/households';
import { CreateBillForm } from './CreateBillForm';
import { formatMoney } from './values';

function memberName(id: string, members: HouseholdMember[]) {
  return members.find(member => member.membership_id === id)?.display_name ?? `Member ${id.slice(0, 8)}`;
}
function BillSummary({ bill, household, members }: { bill: Bill; household: Household; members: HouseholdMember[] }) {
  return <dl>
    <dt>Total</dt><dd>{formatMoney(bill.amount_minor, household.currency)}</dd>
    <dt>Paid at</dt><dd><time dateTime={bill.paid_at}>{new Date(bill.paid_at).toLocaleString()}</time></dd>
    <dt>Split method</dt><dd>{bill.split_method}</dd>
    <dt>Payer</dt><dd>{memberName(bill.payer_membership_id, members)}</dd>
  </dl>;
}
export function BillPage({ token, householdId, billId }: { token: string; householdId: string; billId?: string }) {
  const [data, setData] = useState<{ household: Household; members: HouseholdMember[]; bills: Bill[] } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setData(null);
    setError('');
    Promise.all([
      getHousehold(token, householdId), getHouseholdMembers(token, householdId),
      billId ? getBill(token, householdId, billId).then(bill => [bill]) : getBills(token, householdId),
    ]).then(([household, members, bills]) => {
      if (active) setData({ household, members, bills });
    }).catch(failure => {
      if (active) setError(billError(failure, 'load bills and members'));
    });
    return () => { active = false; };
  }, [token, householdId, billId]);
  const base = `/households/${householdId}`;
  return <section>
    <p><Link to={billId ? `${base}/bills` : base}>{billId ? 'Back to bills' : 'Back to household'}</Link></p>
    {error ? <p role="alert">{error}</p> : !data ? <p role="status">Loading bills and members…</p> : <>
      <h2>{billId ? data.bills[0].description : `${data.household.name} — Bills`}</h2>
      {billId ? <article className="auth-card">
        <BillSummary bill={data.bills[0]} household={data.household} members={data.members} />
        <h3>Allocations</h3>
        <ul className="allocations">{data.bills[0].allocations.map(allocation => <li key={allocation.id}>
          <span>{memberName(allocation.membership_id, data.members)}</span>
          <span>{formatMoney(allocation.amount_minor, data.household.currency)}</span>
        </li>)}</ul>
      </article> : <>
        {data.bills.length === 0 ? <p>No bills yet.</p> : <ul className="household-list">
          {data.bills.map(bill => <li key={bill.id} className="auth-card">
            <h3><Link to={`${base}/bills/${bill.id}`}>{bill.description}</Link></h3>
            <BillSummary bill={bill} household={data.household} members={data.members} />
          </li>)}
        </ul>}
        <CreateBillForm token={token} householdId={householdId} currency={data.household.currency} members={data.members} />
      </>}
    </>}
  </section>;
}
