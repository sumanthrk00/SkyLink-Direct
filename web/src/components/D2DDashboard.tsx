import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  AlertTriangle,
  Antenna,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpFromLine,
  Check,
  CheckCircle,
  Clock,
  ExternalLink,
  Globe,
  Layers,
  MapPin,
  Orbit,
  Play,
  Radio,
  RefreshCw,
  Satellite,
  Server,
  ShieldCheck,
  Signal,
  Smartphone,
  Wifi,
  WifiOff,
} from 'lucide-react';

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export interface D2DDashboardProps {
  token: string;
  latitude: string;
  longitude: string;
  onUpdateCoordinates?: (lat: string, lon: string) => void;
}

export interface RoutingStep {
  step: number;
  node: string;
  role: string;
  protocol: string;
  status: string;
  details: string;
}

export interface D2DData {
  mobile_device_status: {
    platform: string;
    online_status: string;
    ip_address: string;
    battery_level_percent: number;
    coordinates: {
      latitude_deg: number;
      longitude_deg: number;
    };
  };
  internet_availability: {
    cellular_online: boolean;
    d2d_satellite_available: boolean;
    active_link_mode: string;
  };
  selected_satellite: {
    id: string;
    name: string;
    orbit_type: string;
    altitude_km: number;
    orbital_velocity_km_s: number;
    subsatellite_latitude: number;
    subsatellite_longitude: number;
  } | null;
  satellite_visibility: {
    status: string;
    elevation_deg: number;
    azimuth_deg: number;
    slant_range_km: number;
    doppler_shift_khz: number;
  } | null;
  gateway_status: {
    id: string;
    name: string;
    latitude_deg: number;
    longitude_deg: number;
    status: string;
    feeder_frequency_ghz: number;
    egress_ip: string;
    distance_from_user_km: number;
  } | null;
  simulated_routing_path: RoutingStep[];
  metrics: {
    latency_ms: number;
    upload_speed_mbps: number;
    download_speed_mbps: number;
    packet_loss_percent: number;
    signal_strength_dbm: number;
    carrier_c_n0_db_hz: number;
  };
  last_connectivity_test: any | null;
  prototype_disclaimer: string;
}

export interface ConnectivityTestRecord {
  id: string;
  client_platform: string;
  ping_latency_ms: number;
  download_speed_mbps: number;
  upload_speed_mbps: number;
  packet_loss_percent: number;
  test_type: string;
  status: string;
  server_location: string;
  created_at: string;
}

export interface GatewayRecord {
  id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  elevation_m: number;
  feeder_frequency_ghz: number;
  status: string;
  ip_address: string;
  uplink_capacity_gbps: number;
  downlink_capacity_gbps: number;
  supported_satellites_count: number;
  supported_satellites: string[];
}

const PRESET_LOCATIONS = [
  { name: 'Bangalore', lat: '12.9716', lon: '77.5946' },
  { name: 'London', lat: '51.5074', lon: '-0.1278' },
  { name: 'San Francisco', lat: '37.7749', lon: '-122.4194' },
  { name: 'Tokyo', lat: '35.6762', lon: '139.6503' },
  { name: 'Sydney', lat: '-33.8688', lon: '151.2093' },
];

export default function D2DDashboard({
  token,
  latitude,
  longitude,
  onUpdateCoordinates,
}: D2DDashboardProps) {
  const [data, setData] = useState<D2DData | null>(null);
  const [testHistory, setTestHistory] = useState<ConnectivityTestRecord[]>([]);
  const [gateways, setGateways] = useState<GatewayRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testStage, setTestStage] = useState('');
  const [liveMetrics, setLiveMetrics] = useState<{
    ping?: number;
    download?: number;
    upload?: number;
  }>({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fetchJson = useCallback(
    async <T,>(endpoint: string, options: RequestInit = {}): Promise<T> => {
      const url = endpoint.startsWith('http') ? endpoint : `${API}${endpoint}`;
      const res = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options.headers,
        },
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => '');
        let msg = `Request failed (${res.status})`;
        try {
          const parsed = JSON.parse(txt);
          if (parsed?.detail) {
            msg = typeof parsed.detail === 'string' ? parsed.detail : JSON.stringify(parsed.detail);
          }
        } catch {
          if (txt.includes('ECONNREFUSED') || res.status === 500) {
            msg = 'Cannot connect to backend server on port 8000. Please verify the backend is running via start.bat or start-backend.bat.';
          }
        }
        if (res.status === 500 && !msg.includes('backend')) {
          msg = 'Backend server on port 8000 is not reachable. Please start the backend using start.bat or start-backend.bat.';
        }
        throw new Error(msg);
      }
      return res.json();
    },
    [token]
  );

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const lat = parseFloat(latitude) || 12.9716;
      const lon = parseFloat(longitude) || 77.5946;

      const [d2dRes, historyRes, gatewaysRes] = await Promise.all([
        fetchJson<D2DData>(`/network/d2d-dashboard?latitude_deg=${lat}&longitude_deg=${lon}`),
        fetchJson<{ items: ConnectivityTestRecord[] }>('/network/tests?limit=10').catch(() => ({ items: [] })),
        fetchJson<{ items: GatewayRecord[] }>('/gateways?limit=20').catch(() => ({ items: [] })),
      ]);

      setData(d2dRes);
      setTestHistory(historyRes.items);
      setGateways(gatewaysRes.items);
    } catch (err: any) {
      setError(err.message || 'Failed to load Direct-to-Device dashboard');
    } finally {
      setLoading(false);
    }
  }, [fetchJson, latitude, longitude]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  // Execute Speed Test
  async function runSpeedTest() {
    if (testing) return;
    setTesting(true);
    setError('');
    setSuccess('');
    setTestStage('Measuring Ping / RTT latency…');
    setLiveMetrics({});

    try {
      // 1. Ping Latency
      const pingStart = performance.now();
      await fetchJson('/network/ping');
      const pingMs = Math.max(12, Math.round(performance.now() - pingStart));
      setLiveMetrics((prev) => ({ ...prev, ping: pingMs }));

      // 2. Download Speed Test (Stream controlled synthetic blocks)
      setTestStage('Downloading test payload (2 MB)…');
      const dlStart = performance.now();
      const dlRes = await fetch(`${API}/network/speedtest/download?size_mb=2`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!dlRes.ok) throw new Error('Download test failed');
      const blob = await dlRes.blob();
      const dlEnd = performance.now();
      const dlDurationSec = Math.max(0.05, (dlEnd - dlStart) / 1000);
      const dlBits = blob.size * 8;
      const dlMbps = Number(((dlBits / dlDurationSec) / 1_000_000).toFixed(2));
      setLiveMetrics((prev) => ({ ...prev, download: dlMbps }));

      // 3. Upload Speed Test (Send controlled synthetic binary payload)
      setTestStage('Uploading synthetic payload (512 KB)…');
      const syntheticPayload = new Uint8Array(512 * 1024);
      const upRes = await fetch(`${API}/network/speedtest/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/octet-stream',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: syntheticPayload,
      });
      if (!upRes.ok) throw new Error('Upload test failed');
      const upData = await upRes.json();
      const upMbps = Number((upData.upload_speed_mbps || 2.4).toFixed(2));
      setLiveMetrics((prev) => ({ ...prev, upload: upMbps }));

      // 4. Save test record to backend
      setTestStage('Recording test result to database…');
      await fetchJson('/network/tests', {
        method: 'POST',
        body: JSON.stringify({
          client_platform: 'web',
          ping_latency_ms: pingMs,
          download_speed_mbps: dlMbps,
          upload_speed_mbps: upMbps,
          packet_loss_percent: 0.0,
          test_type: 'internet_speedtest',
          status: 'completed',
          server_location: data?.gateway_status?.name || 'Local Feeder Gateway',
        }),
      });

      setSuccess(`Speed test completed! Ping: ${pingMs} ms | DL: ${dlMbps} Mbps | UL: ${upMbps} Mbps`);
      await loadDashboard();
    } catch (err: any) {
      setError(err.message || 'Speed test failed');
    } finally {
      setTesting(false);
      setTestStage('');
    }
  }

  function handleCityPreset(lat: string, lon: string) {
    if (onUpdateCoordinates) {
      onUpdateCoordinates(lat, lon);
    }
  }

  return (
    <div className="d2d-dashboard">
      {/* Disclaimer Alert Banner */}
      <div className="notice" style={{ marginBottom: 16 }}>
        <ShieldCheck size={18} style={{ color: '#56c8ff' }} />
        <div>
          <b>SkyLink Direct — Direct-to-Device (D2D) Prototype Simulation</b>
          <p style={{ margin: '4px 0 0', color: '#90a4b9', fontSize: 11 }}>
            This interface models end-to-end 3GPP Rel-17 Non-Terrestrial Network (NTN) user plane routing.
            Simulated satellite radio links and feeder gateways are mapped alongside live terrestrial internet connectivity tests.
          </p>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError('')}>✕</button>
        </div>
      )}
      {success && (
        <div className="success-banner">
          <span>{success}</span>
          <button onClick={() => setSuccess('')}>✕</button>
        </div>
      )}

      {/* Top Controls & Status Bar */}
      <div className="d2d-header-panel">
        <div className="d2d-status-badges">
          <div className="d2d-badge online">
            <span className="pulse-dot" />
            <span>TERMINAL: <b>ONLINE</b> ({data?.mobile_device_status?.platform || 'web'})</span>
          </div>

          <div className={`d2d-badge ${data?.internet_availability?.d2d_satellite_available ? 'satellite' : 'cellular'}`}>
            <Wifi size={13} />
            <span>MODE: <b>{data?.internet_availability?.active_link_mode || 'Terrestrial Cellular Fallback'}</b></span>
          </div>

          <div className="d2d-coord-badge">
            <MapPin size={13} />
            <span>LAT: <b>{latitude}°</b> LON: <b>{longitude}°</b></span>
          </div>
        </div>

        <div className="d2d-actions">
          <div className="city-presets" style={{ margin: 0 }}>
            {PRESET_LOCATIONS.map((city) => (
              <button
                key={city.name}
                className="preset-chip"
                onClick={() => handleCityPreset(city.lat, city.lon)}
                title={`Switch location to ${city.name}`}
              >
                {city.name}
              </button>
            ))}
          </div>

          <button
            className="primary"
            onClick={runSpeedTest}
            disabled={testing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            {testing ? (
              <>
                <RefreshCw size={14} className="spin" />
                <span>{testStage || 'Testing…'}</span>
              </>
            ) : (
              <>
                <Play size={14} />
                <span>Run Speed Test</span>
              </>
            )}
          </button>

          <button
            className="secondary"
            onClick={() => void loadDashboard()}
            disabled={loading}
            title="Refresh telemetry"
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="metric-grid" style={{ marginTop: 16 }}>
        <article className="metric-card">
          <div className="metric-icon blue"><Activity size={18} /></div>
          <span className="metric-label">RTT Latency</span>
          <div className="metric-value">
            {liveMetrics.ping !== undefined
              ? liveMetrics.ping
              : (data?.metrics?.latency_ms ? data.metrics.latency_ms.toFixed(0) : '—')}
            <small>ms</small>
          </div>
          <div className="metric-caption">Round-trip gateway ping</div>
        </article>

        <article className="metric-card">
          <div className="metric-icon green"><ArrowDownToLine size={18} /></div>
          <span className="metric-label">Download Speed</span>
          <div className="metric-value">
            {liveMetrics.download !== undefined
              ? liveMetrics.download.toFixed(2)
              : (data?.metrics?.download_speed_mbps ? data.metrics.download_speed_mbps.toFixed(2) : '—')}
            <small>Mbps</small>
          </div>
          <div className="metric-caption">Controlled stream benchmark</div>
        </article>

        <article className="metric-card">
          <div className="metric-icon violet"><ArrowUpFromLine size={18} /></div>
          <span className="metric-label">Upload Speed</span>
          <div className="metric-value">
            {liveMetrics.upload !== undefined
              ? liveMetrics.upload.toFixed(2)
              : (data?.metrics?.upload_speed_mbps ? data.metrics.upload_speed_mbps.toFixed(2) : '—')}
            <small>Mbps</small>
          </div>
          <div className="metric-caption">Uplink throughput</div>
        </article>

        <article className="metric-card">
          <div className="metric-icon orange"><Signal size={18} /></div>
          <span className="metric-label">RF Signal Level</span>
          <div className="metric-value">
            {data?.metrics?.signal_strength_dbm !== undefined ? data.metrics.signal_strength_dbm.toFixed(1) : '—'}
            <small>dBm</small>
          </div>
          <div className="metric-caption">C/N₀: {data?.metrics?.carrier_c_n0_db_hz || 47.0} dB-Hz</div>
        </article>
      </div>

      {/* End-to-End Direct-to-Device Simulated Routing Path Diagram */}
      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Simulated Direct-to-Device Routing Path (3GPP NTN)</h3>
            <p>End-to-end data route from user terminal through space segment and feeder gateway to public internet</p>
          </div>
          <span className="estimate-chip">
            <span /> 5-Node Path
          </span>
        </div>

        <div className="routing-path-container">
          {data?.simulated_routing_path?.map((hop, idx) => (
            <React.Fragment key={hop.step}>
              <div className={`routing-node-card status-${hop.status}`}>
                <div className="routing-node-header">
                  <div className="routing-node-step">Step {hop.step}</div>
                  <span className={`routing-badge ${hop.status}`}>{hop.status}</span>
                </div>
                <div className="routing-node-title">{hop.node}</div>
                <div className="routing-node-role">{hop.role}</div>
                <div className="routing-node-proto">{hop.protocol}</div>
                <div className="routing-node-details">{hop.details}</div>
              </div>
              {idx < (data.simulated_routing_path.length - 1) && (
                <div className="routing-connector">
                  <ArrowRight size={16} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Two-Column Telemetry & Gateway Grid */}
      <div className="dashboard-grid" style={{ marginTop: 16 }}>
        {/* Selected Satellite Telemetry */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Selected Space Segment Node</h3>
              <p>Active LEO transponder providing direct-to-device coverage</p>
            </div>
            <Orbit size={16} style={{ color: '#52b7f5' }} />
          </div>

          <div style={{ padding: '16px 20px' }}>
            {data?.selected_satellite ? (
              <div className="sat-detail-box">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <b style={{ fontSize: 15, color: '#e4eef8' }}>{data.selected_satellite.name}</b>
                  <span className={`admin-badge ${data.satellite_visibility?.status || 'visible'}`}>
                    {data.satellite_visibility?.status || 'Visible'}
                  </span>
                </div>

                <div className="modal-grid" style={{ margin: '8px 0' }}>
                  <div className="modal-item">
                    <span>Orbit Type & Altitude</span>
                    <b>{data.selected_satellite.orbit_type} ({data.selected_satellite.altitude_km} km)</b>
                  </div>
                  <div className="modal-item">
                    <span>Orbital Velocity</span>
                    <b>{data.selected_satellite.orbital_velocity_km_s} km/s</b>
                  </div>
                  <div className="modal-item">
                    <span>Elevation Angle</span>
                    <b>{data.satellite_visibility?.elevation_deg.toFixed(1)}°</b>
                  </div>
                  <div className="modal-item">
                    <span>Azimuth Angle</span>
                    <b>{data.satellite_visibility?.azimuth_deg.toFixed(1)}°</b>
                  </div>
                  <div className="modal-item">
                    <span>Slant Range</span>
                    <b>{data.satellite_visibility?.slant_range_km.toFixed(1)} km</b>
                  </div>
                  <div className="modal-item">
                    <span>Doppler Shift</span>
                    <b>{data.satellite_visibility?.doppler_shift_khz.toFixed(2)} kHz</b>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ color: '#7a8e9f', fontSize: 12 }}>No satellite in active line-of-sight.</p>
            )}
          </div>
        </div>

        {/* Feeder Gateway Teleport Station */}
        <div className="panel">
          <div className="panel-head">
            <div>
              <h3>Feeder Gateway Teleport</h3>
              <p>High-capacity Ka-band ground station linked to public backbone</p>
            </div>
            <Antenna size={16} style={{ color: '#4ee3a3' }} />
          </div>

          <div style={{ padding: '16px 20px' }}>
            {data?.gateway_status ? (
              <div className="sat-detail-box">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <b style={{ fontSize: 15, color: '#e4eef8' }}>{data.gateway_status.name}</b>
                  <span className="admin-badge operational">
                    {data.gateway_status.status}
                  </span>
                </div>

                <div className="modal-grid" style={{ margin: '8px 0' }}>
                  <div className="modal-item">
                    <span>Feeder Frequency</span>
                    <b>{data.gateway_status.feeder_frequency_ghz} GHz (Ka-Band)</b>
                  </div>
                  <div className="modal-item">
                    <span>Egress IP</span>
                    <b>{data.gateway_status.egress_ip}</b>
                  </div>
                  <div className="modal-item">
                    <span>Coordinates</span>
                    <b>{data.gateway_status.latitude_deg.toFixed(2)}°, {data.gateway_status.longitude_deg.toFixed(2)}°</b>
                  </div>
                  <div className="modal-item">
                    <span>Distance from User</span>
                    <b>{data.gateway_status.distance_from_user_km.toFixed(1)} km</b>
                  </div>
                </div>
              </div>
            ) : (
              <p style={{ color: '#7a8e9f', fontSize: 12 }}>No feeder gateway configured.</p>
            )}
          </div>
        </div>
      </div>

      {/* Connectivity Test History */}
      <div className="panel" style={{ marginTop: 16 }}>
        <div className="panel-head">
          <div>
            <h3>Connectivity & Speed Test History</h3>
            <p>Audited performance logs executed across mobile and web clients</p>
          </div>
          <Clock size={16} style={{ color: '#90a5bc' }} />
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>TIMESTAMP</th>
                <th>CLIENT</th>
                <th>STATUS</th>
                <th>PING LATENCY</th>
                <th>DOWNLOAD</th>
                <th>UPLOAD</th>
                <th>PACKET LOSS</th>
                <th>SERVER LOCATION</th>
              </tr>
            </thead>
            <tbody>
              {testHistory.length === 0 ? (
                <tr>
                  <td colSpan={8} className="empty-row">
                    No speed test history recorded yet. Click "Run Speed Test" above to execute your first benchmark.
                  </td>
                </tr>
              ) : (
                testHistory.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.created_at).toLocaleString()}</td>
                    <td>
                      <span className="admin-badge user">{t.client_platform}</span>
                    </td>
                    <td>
                      <span className="admin-badge active">{t.status}</span>
                    </td>
                    <td>
                      <b>{t.ping_latency_ms.toFixed(1)} ms</b>
                    </td>
                    <td style={{ color: '#56c8ff' }}>
                      <b>{t.download_speed_mbps.toFixed(2)} Mbps</b>
                    </td>
                    <td style={{ color: '#bca6ff' }}>
                      <b>{t.upload_speed_mbps.toFixed(2)} Mbps</b>
                    </td>
                    <td>{t.packet_loss_percent.toFixed(1)}%</td>
                    <td>{t.server_location}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Satellite Feeder Gateways Inventory */}
      <div className="panel" style={{ marginTop: 16, marginBottom: 24 }}>
        <div className="panel-head">
          <div>
            <h3>Satellite Feeder Gateways Inventory</h3>
            <p>Teleport stations registered for high-speed feeder links and carrier network interconnects</p>
          </div>
          <span className="estimate-chip">
            <span /> {gateways.length} Gateways
          </span>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>GATEWAY NAME</th>
                <th>COORDINATES</th>
                <th>FEEDER FREQ</th>
                <th>DOWNLINK CAPACITY</th>
                <th>UPLINK CAPACITY</th>
                <th>SUPPORTED SATS</th>
                <th>STATUS</th>
              </tr>
            </thead>
            <tbody>
              {gateways.length === 0 ? (
                <tr>
                  <td colSpan={7} className="empty-row">
                    No satellite gateways found.
                  </td>
                </tr>
              ) : (
                gateways.map((gw) => (
                  <tr key={gw.id}>
                    <td>
                      <b>{gw.name}</b>
                    </td>
                    <td>
                      {gw.latitude_deg.toFixed(4)}°, {gw.longitude_deg.toFixed(4)}° ({gw.elevation_m}m)
                    </td>
                    <td style={{ color: '#74caff' }}>
                      <b>{gw.feeder_frequency_ghz.toFixed(1)} GHz</b>
                    </td>
                    <td>{gw.downlink_capacity_gbps.toFixed(1)} Gbps</td>
                    <td>{gw.uplink_capacity_gbps.toFixed(1)} Gbps</td>
                    <td>
                      <span className="admin-badge user">
                        {gw.supported_satellites_count} Satellites
                      </span>
                    </td>
                    <td>
                      <span className={`admin-badge ${gw.status}`}>
                        {gw.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

