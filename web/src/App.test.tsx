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

  it('restores authenticated session from localStorage without flashing login', () => {
    // Generate valid unexpired JWT payload
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({ sub: 'user-1', exp: futureExp }));
    const fakeToken = `${header}.${payload}.signature`;

    localStorage.setItem('skylink-token', fakeToken);
    localStorage.setItem('skylink-user', JSON.stringify({
      id: 'user-1',
      name: 'Demo Pilot',
      email: 'pilot@skylink.direct',
      role: 'admin'
    }));

    render(<App />);
    // Should NOT show login screen
    expect(screen.queryByRole('heading', { name: 'Sign in to your account' })).not.toBeInTheDocument();
  });
});
