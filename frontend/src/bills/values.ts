export function parseAmount(value: string): number {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(value.trim());
  if (!match) throw new Error('Enter a positive amount with at most two decimal places.');
  const minor = BigInt(match[1]) * 100n + BigInt((match[2] ?? '').padEnd(2, '0'));
  if (minor <= 0n) throw new Error('Amount must be greater than zero.');
  if (minor > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Amount is too large.');
  return Number(minor);
}
export function formatMoney(minor: number, currency: string): string {
  if (!Number.isSafeInteger(minor) || minor < 0) return 'Amount unavailable';
  const digits = String(minor).padStart(3, '0');
  const prefix = currency === 'CNY' ? '¥' : `${currency} `;
  return `${prefix}${digits.slice(0, -2)}.${digits.slice(-2)}`;
}
export function toPaidAt(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value);
  const date = new Date(value);
  if (!match || !Number.isFinite(date.getTime()) ||
      date.getFullYear() !== Number(match[1]) || date.getMonth() + 1 !== Number(match[2]) ||
      date.getDate() !== Number(match[3]) || date.getHours() !== Number(match[4]) ||
      date.getMinutes() !== Number(match[5])) {
    throw new Error('Enter a valid paid date and time.');
  }
  return date.toISOString();
}
