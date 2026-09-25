import { expect, it } from 'vitest';
import { formatMoney, parseAmount, toPaidAt } from './values';
it.each([['100.00', 10000], ['50', 5000], ['0.01', 1], ['1.1', 110], [' 01.05 ', 105], ['90071992547409.91', Number.MAX_SAFE_INTEGER]])('parses %s exactly', (input, expected) => {
  expect(parseAmount(input as string)).toBe(expected);
});
it.each(['', '0', '0.00', '-1', '1.001', 'abc', '1e2', '1,000', 'Infinity', '90071992547409.92'])('rejects %s', input => {
  expect(() => parseAmount(input)).toThrow();
});
it.each([[10000, '¥100.00'], [5000, '¥50.00'], [1, '¥0.01'], [0, '¥0.00']])('formats %s minor units', (minor, expected) => {
  expect(formatMoney(minor as number, 'CNY')).toBe(expected);
});
it('does not present unsafe integers as exact money', () => {
  expect(formatMoney(Number.MAX_SAFE_INTEGER + 1, 'CNY')).toBe('Amount unavailable');
});
it('converts device-local datetime to UTC ISO with a timezone', () => {
  const iso = toPaidAt('2026-09-25T14:30');
  expect(iso).toBe(new Date(2026, 8, 25, 14, 30).toISOString());
  expect(iso).toMatch(/Z$/);
});
it.each(['', 'nonsense', '2026-02-30T12:00', '2026-09-25'])('rejects invalid datetime %s', input => {
  expect(() => toPaidAt(input)).toThrow();
});

it.each(['MYR', 'USD', 'XYZ'])('keeps %s identifiable instead of relabelling it CNY', currency => {
  expect(formatMoney(10000, currency)).toBe(`${currency} 100.00`);
});
