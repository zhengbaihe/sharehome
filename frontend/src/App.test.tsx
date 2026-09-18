import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import App from './App';

it('shows the project shell without claiming expense tracking is implemented', () => {
  render(<App />);
  expect(screen.getByRole('heading', { name: 'ShareHome' })).toBeInTheDocument();
  expect(screen.getByText(/Expense tracking is coming next/)).toBeInTheDocument();
});
