// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import App from './App';

afterEach(cleanup);

describe('authentication screen', () => {
  it('shows sign in and switches to registration', () => {
    localStorage.clear();
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Sign in to your account' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create one' }));
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
    expect(screen.getByLabelText('Full name')).toBeInTheDocument();
  });
});
