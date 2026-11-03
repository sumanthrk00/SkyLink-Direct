// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import AdminModule, { AdminOverview } from './AdminModule';

afterEach(cleanup);

const mockOverview: AdminOverview = {
  total_users: 42,
  total_satellites: 18,
  total_simulations: 156,
  active_sessions: 3,
  network_events: 89,
};

function renderMetric(
  Icon: any,
  label: string,
  value: string,
  unit: string,
  caption: string,
  _color?: string
) {
  return (
    <div key={label} data-testid={`metric-${label}`}>
      <span>{label}</span>
      <b>{value} {unit}</b>
      <small>{caption}</small>
    </div>
  );
}

describe('AdminModule component', () => {
  it('renders system overview metrics and subnav tabs', () => {
    // mock fetch
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], total: 0 }),
      })
    ) as any;

    render(
      <AdminModule
        token="mock-jwt-token"
        adminOverview={mockOverview}
        onRefreshOverview={vi.fn()}
        metricRenderer={renderMetric}
      />
    );

    // Overview cards
    expect(screen.getByText('Registered users')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Demo satellites')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(screen.getByText('Simulation runs')).toBeInTheDocument();
    expect(screen.getByText('156')).toBeInTheDocument();
    expect(screen.getByText('Active sessions')).toBeInTheDocument();

    // 8 Subnav tabs
    expect(screen.getByRole('button', { name: /User Management/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Satellite Management/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ground Stations/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Simulation History/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Demo Sessions/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Network Events/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /System Monitoring/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Audit Logs/i })).toBeInTheDocument();
  });

  it('switches between administration subtabs and renders active controls', () => {
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ items: [], total: 0 }),
      })
    ) as any;

    render(
      <AdminModule
        token="mock-jwt-token"
        adminOverview={mockOverview}
        onRefreshOverview={vi.fn()}
        metricRenderer={renderMetric}
      />
    );

    // Click Satellites tab
    fireEvent.click(screen.getByRole('button', { name: /Satellite Management/i }));
    expect(screen.getByRole('button', { name: /Add Satellite Record/i })).toBeInTheDocument();

    // Click Ground Stations tab
    fireEvent.click(screen.getByRole('button', { name: /Ground Stations/i }));
    expect(screen.getByRole('button', { name: /Add Ground Station/i })).toBeInTheDocument();

    // Click Audit Logs tab
    fireEvent.click(screen.getByRole('button', { name: /Audit Logs/i }));
    expect(screen.getByText(/Administrator/i)).toBeInTheDocument();
  });
});

