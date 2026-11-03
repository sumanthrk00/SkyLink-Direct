// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import D2DDashboard from './D2DDashboard';

afterEach(cleanup);

const mockD2DData = {
  mobile_device_status: {
    platform: 'web',
    online_status: 'online',
    ip_address: '127.0.0.1',
    battery_level_percent: 92,
    coordinates: {
      latitude_deg: 12.9716,
      longitude_deg: 77.5946,
    },
  },
  internet_availability: {
    cellular_online: true,
    d2d_satellite_available: true,
    active_link_mode: '3GPP NTN Direct-to-Device Active',
  },
  selected_satellite: {
    id: 'sat-1',
    name: 'Demo LEO 01',
    orbit_type: 'LEO',
    altitude_km: 550.0,
    orbital_velocity_km_s: 7.6,
    subsatellite_latitude: 12.5,
    subsatellite_longitude: 77.2,
  },
  satellite_visibility: {
    status: 'visible',
    elevation_deg: 42.5,
    azimuth_deg: 180.2,
    slant_range_km: 720.5,
    doppler_shift_khz: 12.4,
  },
  gateway_status: {
    id: 'gw-1',
    name: 'Bangalore Teleport Gateway',
    latitude_deg: 13.0827,
    longitude_deg: 77.5877,
    status: 'operational',
    feeder_frequency_ghz: 28.5,
    egress_ip: '192.168.10.1',
    distance_from_user_km: 12.4,
  },
  simulated_routing_path: [
    {
      step: 1,
      node: 'Mobile User Equipment (UE)',
      role: 'Direct-to-Device Transceiver',
      protocol: '3GPP Rel-17 NTN User Equipment',
      status: 'active',
      details: 'Platform: web',
    },
    {
      step: 2,
      node: 'Satellite Radio Access Link',
      role: 'Service Link (S-Band 2.0 GHz)',
      protocol: 'NR-NTN Orthogonal Frequency Division Multiplexing',
      status: 'active',
      details: 'Elevation: 42.5°',
    },
    {
      step: 3,
      node: 'Satellite Node: Demo LEO 01',
      role: 'LEO Transponder',
      protocol: 'Keplerian Orbit Mesh',
      status: 'orbiting',
      details: 'Altitude: 550.0 km',
    },
    {
      step: 4,
      node: 'Feeder Gateway: Bangalore Teleport',
      role: 'Ka-Band Teleport',
      protocol: 'Feeder Link 28.5 GHz Ka-band',
      status: 'operational',
      details: 'Capacity: 40.0 Gbps',
    },
    {
      step: 5,
      node: 'Global Internet Backbone',
      role: 'Core UPF',
      protocol: 'IPv4 / IPv6 BGP Routing',
      status: 'online',
      details: 'Public Transit',
    },
  ],
  metrics: {
    latency_ms: 28.0,
    upload_speed_mbps: 2.5,
    download_speed_mbps: 12.0,
    packet_loss_percent: 0.0,
    signal_strength_dbm: -92.4,
    carrier_c_n0_db_hz: 47.0,
  },
  last_connectivity_test: null,
  prototype_disclaimer: 'Simulated Direct-to-Device RF architecture.',
};

describe('D2DDashboard component', () => {
  it('renders simulated 5-step routing path and metrics cards', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/network/d2d-dashboard')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockD2DData),
        });
      }
      if (url.includes('/network/tests')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ items: [] }),
        });
      }
      if (url.includes('/gateways')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: 'gw-1',
                  name: 'Bangalore Teleport Gateway',
                  latitude_deg: 13.0827,
                  longitude_deg: 77.5877,
                  elevation_m: 50.0,
                  feeder_frequency_ghz: 28.5,
                  status: 'operational',
                  ip_address: '192.168.10.1',
                  uplink_capacity_gbps: 10.0,
                  downlink_capacity_gbps: 40.0,
                  supported_satellites_count: 6,
                  supported_satellites: ['Demo LEO 01'],
                },
              ],
            }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      });
    }) as any;

    render(
      <D2DDashboard
        token="mock-jwt-token"
        latitude="12.9716"
        longitude="77.5946"
      />
    );

    // Check disclaimer
    expect(
      screen.getByText(/Direct-to-Device \(D2D\) Prototype Simulation/i)
    ).toBeInTheDocument();

    // Check routing path nodes
    await waitFor(() => {
      expect(screen.getByText('Mobile User Equipment (UE)')).toBeInTheDocument();
      expect(screen.getByText('Satellite Radio Access Link')).toBeInTheDocument();
      expect(screen.getByText('Global Internet Backbone')).toBeInTheDocument();
    });

    // Check metrics
    expect(screen.getByText('RTT Latency')).toBeInTheDocument();
    expect(screen.getByText('Download Speed')).toBeInTheDocument();
    expect(screen.getByText('Upload Speed')).toBeInTheDocument();
    expect(screen.getByText('RF Signal Level')).toBeInTheDocument();

    // Check gateways table
    expect(screen.getAllByText('Bangalore Teleport Gateway').length).toBeGreaterThan(0);
  });
});

