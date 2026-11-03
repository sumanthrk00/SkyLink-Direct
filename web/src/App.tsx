import { useCallback, useEffect, useState } from 'react';
import AdminModule from './components/AdminModule';
import D2DDashboard from './components/D2DDashboard';
import { Activity, Antenna, ArrowDownToLine, ArrowUpFromLine, Bell, ChevronDown, CircleHelp, Clock3, Command, Download, FileText, Gauge, LogOut, MapPin, Menu, Orbit, Play, Radio, RefreshCw, Satellite, Settings, ShieldCheck, Signal, Square, UserRound, Wifi, X } from 'lucide-react';

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';
type User = { id: string; name: string; email: string; role: string };
type SatelliteInfo = { id: string; name: string; orbit_type: string; altitude_km: number; status: string; inclination_deg: number };
type Simulation = { id: string; status: string; latitude_deg: number; longitude_deg: number; satellite_name?: string; elevation_deg: number; distance_km: number; signal_strength: number; latency_ms: number; packet_loss: number; download_mbps: number; upload_mbps: number; result_type: string; created_at: string };
type Connection = { id: string; status: string; satellite_name?: string; started_at: string; ended_at?: string };
type NetworkEvent = { id: string; event_type: string; description: string; created_at: string };
type GroundStation = { id: string; name: string; latitude_deg: number; longitude_deg: number; status: string };
type PassPrediction = { satellite_name: string; aos_utc: string; tca_utc: string; los_utc: string; max_elevation_deg: number; duration_seconds: number; tca_distance_km: number; tca_azimuth_deg: number };
type SatelliteTelemetry = { satellite_id: string; name: string; altitude_km: number; subsatellite_latitude_deg: number; subsatellite_longitude_deg: number; orbital_velocity_km_s: number; orbital_period_minutes: number; timestamp_utc: string };
type SimulationReport = { simulation_id: string; created_at: string; observer_location: { latitude_deg: number; longitude_deg: number }; satellite?: { name: string; altitude_km: number }; rf_link_budget: { free_space_path_loss_db: number; atmospheric_absorption_db: number; total_path_loss_db: number; carrier_frequency_mhz: number; c_n0_db_hz: number; snr_db: number; apparent_elevation_deg: number; rx_power_dbm: number }; throughput_capacity: { download_mbps: number; upload_mbps: number; latency_ms: number; packet_loss_percent: number }; channel_status: string; prototype_disclaimer: string };
type Page<T> = { items: T[]; total: number };

async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const url = path.startsWith('http') ? path : `${API}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch (networkError) {
    throw new Error(
      `Cannot connect to backend server at ${url}. Please ensure the backend is running on port 8000.`
    );
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    let detail: string | null = null;
    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed?.detail)) {
        detail = parsed.detail.map((d: any) => (typeof d === 'object' && d?.msg ? d.msg : String(d))).join('; ');
      } else if (typeof parsed?.detail === 'object' && parsed?.detail !== null) {
        detail = JSON.stringify(parsed.detail);
      } else if (parsed?.detail) {
        detail = String(parsed.detail);
      }
    } catch {
      if (text.includes('ECONNREFUSED')) {
        detail = 'Cannot connect to backend server. Please verify the backend is running on port 8000 (start.bat or start-backend.bat).';
      }
    }
    if (!detail) {
      if (response.status === 500) {
        detail = 'Backend server on port 8000 is not reachable. Please start the backend using start.bat or start-backend.bat.';
      } else {
        detail = `Request failed (${response.status})`;
      }
    }
    const err = new Error(detail);
    (err as any).status = response.status;
    throw err;
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const fmt = (n: number, digits = 1) => (Number.isFinite(n) ? n.toFixed(digits) : '—');

function getSavedToken(): string | null {
  try {
    const saved = localStorage.getItem('skylink-token');
    if (!saved) return null;
    const parts = saved.split('.');
    if (parts.length !== 3) {
      localStorage.removeItem('skylink-token');
      localStorage.removeItem('skylink-user');
      return null;
    }
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    if (payload.exp && typeof payload.exp === 'number') {
      if (Date.now() / 1000 >= payload.exp - 5) {
        // Token has expired; silently clear it
        localStorage.removeItem('skylink-token');
        localStorage.removeItem('skylink-user');
        return null;
      }
    }
    return saved;
  } catch {
    localStorage.removeItem('skylink-token');
    localStorage.removeItem('skylink-user');
    return null;
  }
}

function getSavedUser(): User | null {
  try {
    const raw = localStorage.getItem('skylink-user');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const PRESET_LOCATIONS = [
  { name: 'Bangalore', lat: 12.9716, lon: 77.5946 },
  { name: 'London', lat: 51.5074, lon: -0.1278 },
  { name: 'San Francisco', lat: 37.7749, lon: -122.4194 },
  { name: 'Tokyo', lat: 35.6762, lon: 139.6503 },
  { name: 'Sydney', lat: -33.8688, lon: 151.2093 },
];

export default function App() {
  const [token, setToken] = useState<string | null>(getSavedToken);
  const [user, setUser] = useState<User | null>(() => (getSavedToken() ? getSavedUser() : null));
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [page, setPage] = useState('Overview');
  const [mobileNav, setMobileNav] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [busy, setBusy] = useState(false);
  const [satellites, setSatellites] = useState<SatelliteInfo[]>([]);
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [latestSim, setLatestSim] = useState<Simulation | null>(null);
  const [showNewSimModal, setShowNewSimModal] = useState(false);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [events, setEvents] = useState<NetworkEvent[]>([]);
  const [groundStations, setGroundStations] = useState<GroundStation[]>([]);
  const [newStationName, setNewStationName] = useState('');
  const [newStationLat, setNewStationLat] = useState('13.0827');
  const [newStationLon, setNewStationLon] = useState('80.2707');
  const [predictedPasses, setPredictedPasses] = useState<PassPrediction[]>([]);
  const [telemetry, setTelemetry] = useState<SatelliteTelemetry | null>(null);
  const [selectedReport, setSelectedReport] = useState<SimulationReport | null>(null);
  const [admin, setAdmin] = useState<Record<string, number> | null>(null);
  const [latitude, setLatitude] = useState('12.9716');
  const [longitude, setLongitude] = useState('77.5946');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [editing, setEditing] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const load = useCallback(async (activeToken: string) => {
    try {
      // Step 1: Validate session identity first. If token is invalid or expired, stops immediately without firing 5 parallel queries
      const me = await request<User>('/users/me', activeToken);
      setUser(me);
      localStorage.setItem('skylink-user', JSON.stringify(me));

      // Step 2: Session is confirmed valid; load workspace datasets in parallel
      const [sats, sims, conns, eventPage, stations] = await Promise.all([
        request<Page<SatelliteInfo>>('/satellites?limit=100', activeToken),
        request<Page<Simulation>>('/simulations?limit=8', activeToken),
        request<Page<Connection>>('/connections?limit=8', activeToken),
        request<Page<NetworkEvent>>('/events?limit=20', activeToken),
        request<Page<GroundStation>>('/ground-stations?limit=50', activeToken).catch(() => ({ items: [], total: 0 })),
      ]);
      setSatellites(sats.items);
      setSimulations(sims.items);
      setConnections(conns.items);
      setEvents(eventPage.items);
      setGroundStations(stations.items);
      if (me.role === 'admin') setAdmin(await request<Record<string, number>>('/admin/dashboard', activeToken).catch(() => null));
      else setAdmin(null);
      setError('');
    } catch (e: any) {
      if (e?.status === 401 || (e instanceof Error && e.message.toLowerCase().includes('authentication required'))) {
        localStorage.removeItem('skylink-token');
        localStorage.removeItem('skylink-user');
        setToken(null);
        setUser(null);
        setError('');
      } else {
        setError(e instanceof Error ? e.message : 'Could not sync with backend server on port 8000');
      }
    }
  }, []);

  useEffect(() => {
    if (token) {
      void load(token);
    } else {
      setUser(null);
    }
  }, [token, load]);

  async function authenticate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setSuccess('');
    try {
      if (authMode === 'register') {
        await request('/auth/register', null, {
          method: 'POST',
          body: JSON.stringify({ name: name.trim(), email: email.trim(), password }),
        });
      }
      const data = await request<{ access_token: string }>('/auth/login', null, {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password }),
      });
      localStorage.setItem('skylink-token', data.access_token);
      setToken(data.access_token);
      await load(data.access_token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed');
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    if (token) await request('/auth/logout', token, { method: 'POST' }).catch(() => undefined);
    localStorage.removeItem('skylink-token');
    localStorage.removeItem('skylink-user');
    setToken(null);
    setUser(null);
    setError('');
    setSuccess('');
    setAuthMode('login');
  }

  function useCurrentLocation() {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => {
          setLatitude(pos.coords.latitude.toFixed(4));
          setLongitude(pos.coords.longitude.toFixed(4));
          setSuccess('Updated coordinates from device GPS.');
        },
        () => {
          setError('Could not access device GPS. Please input coordinates manually.');
        }
      );
    } else {
      setError('Geolocation is not supported by your browser.');
    }
  }

  async function autoFindVisibleSatellite() {
    if (!token) {
      setError('Please sign in to locate an active satellite.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const data = await request<{ latitude_deg: number; longitude_deg: number; satellite_name: string }>('/simulations/find-visible', token);
      setLatitude(String(data.latitude_deg));
      setLongitude(String(data.longitude_deg));
      setSuccess(`Located ${data.satellite_name} directly overhead at (${data.latitude_deg}°, ${data.longitude_deg}°). Running simulation…`);
      await runSimulation(data.latitude_deg, data.longitude_deg);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not locate satellite position');
    } finally {
      setBusy(false);
    }
  }

  async function runSimulation(overrideLat?: number, overrideLon?: number) {
    if (!token) {
      setError('Please sign in to run a simulation.');
      return;
    }
    const latNum = overrideLat !== undefined ? overrideLat : parseFloat(latitude);
    const lonNum = overrideLon !== undefined ? overrideLon : parseFloat(longitude);

    if (isNaN(latNum) || latNum < -90 || latNum > 90) {
      setError('Please provide a valid latitude between -90 and 90 degrees.');
      return;
    }
    if (isNaN(lonNum) || lonNum < -180 || lonNum > 180) {
      setError('Please provide a valid longitude between -180 and 180 degrees.');
      return;
    }

    setBusy(true);
    setError('');
    try {
      const res = await request<Simulation>('/simulations', token, {
        method: 'POST',
        body: JSON.stringify({ latitude_deg: latNum, longitude_deg: lonNum }),
      });
      setLatestSim(res);
      if (res.status === 'visible') {
        setSuccess(`Simulation complete: Connected to ${res.satellite_name} at ${res.elevation_deg}° elevation (${fmt(res.distance_km)} km away, ${fmt(res.download_mbps)} Mbps throughput).`);
      } else {
        setSuccess(`Simulation complete: No satellite above horizon currently at (${latNum.toFixed(2)}°, ${lonNum.toFixed(2)}°). Highest elevation: ${res.elevation_deg}°.`);
      }
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Simulation failed');
    } finally {
      setBusy(false);
    }
  }

  async function startSession() {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      const targetSim = (latestSim?.status === 'visible' ? latestSim : null) || simulations.find(s => s.status === 'visible') || latestSim || simulations[0];
      const body = targetSim
        ? { simulation_id: targetSim.id }
        : { latitude_deg: parseFloat(latitude) || 12.9716, longitude_deg: parseFloat(longitude) || 77.5946 };
      await request('/connections', token, { method: 'POST', body: JSON.stringify(body) });
      setSuccess('Demo connection session initiated.');
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start session');
    } finally {
      setBusy(false);
    }
  }

  async function endSession(id: string) {
    if (!token) return;
    setBusy(true);
    try {
      await request(`/connections/${id}/end`, token, { method: 'POST' });
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not end session');
    } finally {
      setBusy(false);
    }
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    try {
      await request('/users/me', token, { method: 'PUT', body: JSON.stringify({ name }) });
      setEditing(false);
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save profile');
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    try {
      await request('/users/me/password', token, {
        method: 'PUT',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword('');
      setNewPassword('');
      setShowPassword(false);
      setError('');
      setSuccess('Password updated successfully.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update password');
    } finally {
      setBusy(false);
    }
  }

  async function predictPassesForLocation() {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      const res = await request<{ passes: PassPrediction[] }>(
        `/simulations/passes?latitude_deg=${latitude}&longitude_deg=${longitude}&duration_hours=12`,
        token
      );
      setPredictedPasses(res.passes);
      setSuccess(`Computed ${res.passes.length} overhead satellite passes for the next 12 hours.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Pass prediction failed');
    } finally {
      setBusy(false);
    }
  }

  async function viewTelemetry(satelliteId: string) {
    if (!token) return;
    try {
      const data = await request<SatelliteTelemetry>(`/satellites/${satelliteId}/telemetry`, token);
      setTelemetry(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to retrieve telemetry');
    }
  }

  async function viewSimulationReport(simId: string) {
    if (!token) return;
    try {
      const data = await request<SimulationReport>(`/simulations/${simId}/report`, token);
      setSelectedReport(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to retrieve report');
    }
  }

  async function addGroundStation(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      await request('/ground-stations', token, {
        method: 'POST',
        body: JSON.stringify({
          name: newStationName.trim(),
          latitude_deg: parseFloat(newStationLat),
          longitude_deg: parseFloat(newStationLon),
          status: 'active',
        }),
      });
      setNewStationName('');
      setSuccess('Ground station registered successfully.');
      await load(token);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create ground station');
    } finally {
      setBusy(false);
    }
  }

  if (token && !user) {
    return (
      <div className="auth-shell">
        <div style={{ display: 'grid', placeItems: 'center', height: '100%', color: '#90a5bc', gap: '14px', width: '100%' }}>
          <div className="tag-orb" style={{ width: '42px', height: '42px' }}>
            <Orbit size={28} />
          </div>
          <b style={{ color: '#dce6f1', fontSize: '13px', letterSpacing: '0.05em' }}>Resuming satellite workspace…</b>
          {error && (
            <div className="alert error" style={{ maxWidth: 360, marginTop: 12 }}>
              <span>{error}</span>
              <button
                type="button"
                className="btn secondary sm"
                style={{ marginTop: 8 }}
                onClick={() => {
                  localStorage.removeItem('skylink-token');
                  localStorage.removeItem('skylink-user');
                  setToken(null);
                  setUser(null);
                  setError('');
                }}
              >
                Return to Login
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <div className="auth-shell">
        <div className="auth-art">
          <div className="brand">
            <span className="brand-icon"><Satellite size={22} /></span>
            <span>SKYLINK<span className="brand-light"> DIRECT</span></span>
          </div>
          <div className="orbit-art">
            <div className="planet"></div>
            <div className="orbit orbit-one"></div>
            <div className="orbit orbit-two"></div>
            <div className="orbit-satellite"><Satellite size={24} /></div>
            <span className="star s1">✦</span>
            <span className="star s2">·</span>
            <span className="star s3">✦</span>
          </div>
          <div className="auth-copy">
            <div className="eyebrow"><span className="pulse-dot" /> SATELLITE CONNECTIVITY SIMULATOR</div>
            <h1>Connectivity,<br />without boundaries.</h1>
            <p>Explore direct-to-device satellite connectivity through a transparent, interactive prototype.</p>
            <div className="auth-note"><ShieldCheck size={16} /> Simulation only · No real satellite connection</div>
          </div>
          <div className="auth-foot">ENGINEERED FOR EVERYWHERE <span>© 2026 SKYLINK DIRECT</span></div>
        </div>
        <div className="auth-panel">
          <form className="auth-form" onSubmit={authenticate}>
            <div className="mobile-brand">
              <span className="brand-icon"><Satellite size={20} /></span> SKYLINK DIRECT
            </div>
            <span className="eyebrow">WELCOME TO THE NETWORK</span>
            <h2>{authMode === 'login' ? 'Sign in to your account' : 'Create your account'}</h2>
            <p className="muted">
              {authMode === 'login' ? 'Access your connectivity dashboard.' : 'Get started with your personal dashboard.'}
            </p>
            {authMode === 'register' && (
              <label>
                Full name
                <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" required minLength={1} />
              </label>
            )}
            <label>
              Email address
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" required autoComplete="email" />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="At least 10 characters"
                required
                minLength={authMode === 'register' ? 10 : 1}
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
              />
            </label>
            {error && <div className="error-box">{error}</div>}
            <button className="primary wide" disabled={busy}>
              {busy ? 'Please wait…' : authMode === 'login' ? 'Sign in' : 'Create account'}
              <span>→</span>
            </button>
            <div className="auth-switch">
              {authMode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                  setError('');
                  setSuccess('');
                }}
              >
                {authMode === 'login' ? 'Create one' : 'Sign in'}
              </button>
            </div>
            {authMode === 'login' && (
              <div className="demo-credentials">
                <span>Demo Admin:</span>
                <button
                  type="button"
                  className="demo-fill-btn"
                  onClick={() => {
                    setEmail('admin@skylink.direct');
                    setPassword('AdminSecure2026!');
                    setError('');
                  }}
                >
                  admin@skylink.direct / AdminSecure2026!
                </button>
              </div>
            )}
            <div className="trust-line">
              <ShieldCheck size={15} /> Secure, encrypted access
            </div>
          </form>
        </div>
      </div>
    );
  }

  const active = connections.find(c => c.status === 'connected');
  const latest = simulations[0];
  const signalPoints = [...simulations].reverse().map((item, index, list) => ({
    x: list.length === 1 ? 300 : (index * 600) / (list.length - 1),
    y: Math.max(10, Math.min(150, 150 - ((item.signal_strength + 160) / 120) * 140)),
  }));
  const title = page === 'Overview' ? 'Network overview' : page;
  const nav = [
    {
      section: 'WORKSPACE',
      items: [
        ['Overview', Gauge],
        ['Direct-to-Device', Wifi],
        ['Satellite network', Orbit],
        ['Simulation', Activity],
        ['Ground stations', Antenna],
        ['Sessions', Radio],
        ['Network events', Bell],
      ] as const,
    },
    { section: 'ACCOUNT', items: [['Profile', UserRound], ['Settings', Settings]] as const },
  ];
  const metric = (Icon: typeof Signal, label: string, value: string, unit: string, caption: string, tone = 'blue') => (
    <article className="metric-card">
      <div className={`metric-icon ${tone}`}><Icon size={18} /></div>
      <span className="metric-label">{label}</span>
      <div className="metric-value">{value}<small>{unit}</small></div>
      <div className="metric-caption">{caption}</div>
    </article>
  );

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? 'show' : ''}`}>
        <div className="brand">
          <span className="brand-icon"><Satellite size={21} /></span>
          <span>SKYLINK<span className="brand-light"> DIRECT</span></span>
          <button className="close-nav" onClick={() => setMobileNav(false)}><X size={18} /></button>
        </div>
        <div className="workspace-tag">
          <span className="tag-orb"><Orbit size={15} /></span>
          <span><b>Direct-to-device</b><small>Simulation workspace</small></span>
          <ChevronDown size={14} />
        </div>
        <nav>
          {nav.map(group => (
            <div className="nav-group" key={group.section}>
              <div className="nav-caption">{group.section}</div>
              {group.items.map(([label, Icon]) => (
                <button
                  key={label}
                  className={`nav-item ${page === label ? 'selected' : ''}`}
                  onClick={() => { setPage(label); setMobileNav(false); }}
                >
                  <Icon size={17} />{label}
                  {label === 'Sessions' && active && <span className="nav-live" />}
                </button>
              ))}
              {group.section === 'WORKSPACE' && user.role === 'admin' && (
                <button
                  className={`nav-item ${page === 'Administration' ? 'selected' : ''}`}
                  onClick={() => setPage('Administration')}
                >
                  <ShieldCheck size={17} />Administration
                </button>
              )}
            </div>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><CircleHelp size={16} /></div>
            <div><b>Need a hand?</b><small>Read the prototype guide</small></div>
            <span>↗</span>
          </div>
          <div className="user-mini">
            <div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div>
            <span><b>{user.name}</b><small>{user.role === 'admin' ? 'Administrator' : 'Personal workspace'}</small></span>
            <button title="Sign out" onClick={signOut}><LogOut size={16} /></button>
          </div>
        </div>
      </aside>
      <main className="main-area">
        <header className="topbar">
          <button className="menu-button" onClick={() => setMobileNav(true)}><Menu size={20} /></button>
          <div className="breadcrumbs">Workspace <span>/</span> <b>{title}</b></div>
          <div className="top-actions">
            <div className="status-pill"><span className="pulse-dot" /> SIMULATION MODE</div>
            <button className="icon-button" title="Refresh" onClick={() => void load(token)}><RefreshCw size={17} /></button>
            <button className="icon-button notification" title="Network events" onClick={() => setPage('Network events')}><Bell size={17} /><i /></button>
            <div className="top-user"><div className="avatar">{user.name.slice(0, 1).toUpperCase()}</div><ChevronDown size={14} /></div>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{new Date().toLocaleDateString('en-IN', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).toUpperCase()} <span className="heading-divider">/</span> {user.role.toUpperCase()} ACCOUNT</div>
              <h1>{title}</h1>
              <p>Monitor your simulated network and explore satellite connectivity.</p>
            </div>
            <div className="heading-actions">
              <button className="secondary" onClick={() => setPage('Satellite network')}><Orbit size={16} /> View satellites</button>
              <button className="primary" onClick={() => setShowNewSimModal(true)} disabled={busy}><Play size={15} fill="currentColor" /> {busy ? 'Calculating…' : 'New simulation'}</button>
            </div>
          </div>
          {error && <div className="error-banner"><span>{error}</span><button onClick={() => setError('')}><X size={16} /></button></div>}
          {success && <div className="success-banner"><span>{success}</span><button onClick={() => setSuccess('')}><X size={16} /></button></div>}
          {page === 'Overview' && (
            <>
              <section className="status-banner">
                <div className="status-symbol"><Antenna size={21} /></div>
                <div className="status-text">
                  <div>
                    <span className={`status-dot ${active ? 'green' : 'amber'}`} />
                    <b>{active ? 'Demo session active' : 'No active connection'}</b>
                    <span className="status-separator">·</span>
                    <span>{active ? `Connected to ${active.satellite_name || 'demo satellite'}` : 'Run a simulation to check satellite visibility'}</span>
                  </div>
                  <small>{active ? `Session started ${new Date(active.started_at).toLocaleTimeString()}` : 'This workspace uses illustrative orbital and link estimates.'}</small>
                </div>
                <button className={active ? 'secondary' : 'light-button'} onClick={() => (active ? endSession(active.id) : startSession())} disabled={busy}>
                  {active ? <><Square size={14} fill="currentColor" /> End session</> : <><Wifi size={15} /> Start demo session</>}
                </button>
              </section>
              <section className="metric-grid">
                {metric(Signal, 'Signal strength', latest ? fmt(latest.signal_strength) : '—', ' dBm', latest ? `${latest.elevation_deg}° elevation` : 'Awaiting simulation')}
                {metric(Clock3, 'Round-trip latency', latest ? fmt(latest.latency_ms) : '—', ' ms', 'Illustrative estimate', 'violet')}
                {metric(ArrowDownToLine, 'Download speed', latest ? fmt(latest.download_mbps) : '—', ' Mbps', 'Modelled throughput', 'green')}
                {metric(ArrowUpFromLine, 'Upload speed', latest ? fmt(latest.upload_mbps) : '—', ' Mbps', 'Modelled throughput', 'orange')}
              </section>
              <section className="dashboard-grid">
                <article className="panel performance-panel">
                  <div className="panel-head">
                    <div>
                      <h3>Saved signal estimates</h3>
                      <p>History from your recent simulation runs</p>
                    </div>
                    <span className="estimate-chip"><span /> ESTIMATED</span>
                  </div>
                  {latest ? (
                    <>
                      <div className="chart-area">
                        <div className="chart-y">
                          <span>−40 dBm</span>
                          <span>−80 dBm</span>
                          <span>−120 dBm</span>
                          <span>−160 dBm</span>
                        </div>
                        <div className="chart-plot">
                          <div className="chart-gridline one" />
                          <div className="chart-gridline two" />
                          <div className="chart-gridline three" />
                          <svg viewBox="0 0 600 180" preserveAspectRatio="none" aria-label="Saved illustrative signal estimates">
                            <polyline points={signalPoints.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="#55c1ff" strokeWidth="2.5" vectorEffect="non-scaling-stroke" />
                            {signalPoints.map((point, index) => (
                              <circle key={index} cx={point.x} cy={point.y} r="4" fill="#55c1ff" stroke="#0f1a27" strokeWidth="2" vectorEffect="non-scaling-stroke" />
                            ))}
                          </svg>
                          <div className="chart-x">
                            {signalPoints.length === 1 ? <span>ONLY RUN</span> : <><span>EARLIER</span><span>RECENT</span></>}
                          </div>
                        </div>
                      </div>
                      <div className="chart-foot">
                        <span><i className="legend-dot" /> Saved estimates</span>
                        <span>{new Date(latest.created_at).toLocaleString()}</span>
                      </div>
                    </>
                  ) : (
                    <div className="empty-chart">
                      <Activity size={24} />
                      <b>No performance data yet</b>
                      <span>Run your first simulation to see estimated link metrics.</span>
                      <button className="secondary" onClick={() => setPage('Simulation')}>Start a simulation</button>
                    </div>
                  )}
                </article>
                <article className="panel network-panel">
                  <div className="panel-head">
                    <div>
                      <h3>Network status</h3>
                      <p>Prototype environment</p>
                    </div>
                    <span className="network-icon"><Satellite size={18} /></span>
                  </div>
                  <div className="network-map">
                    <div className="map-lines"></div>
                    <div className="map-earth">
                      <div className="map-continent c1" />
                      <div className="map-continent c2" />
                      <div className="map-continent c3" />
                      <div className="map-orbit orbit-a" />
                      <div className="map-orbit orbit-b" />
                      <div className="map-sat sat-a"><Satellite size={14} /></div>
                      <div className="map-sat sat-b"><Satellite size={13} /></div>
                      <div className="map-pin"><MapPin size={15} fill="currentColor" /></div>
                    </div>
                    <div className="map-label label-top">DEMO ORBIT <span>ILLUSTRATIVE</span></div>
                    <div className="map-label label-bottom">
                      <span className="pulse-dot" /> {latest?.status === 'visible' ? 'SATELLITE VISIBLE' : 'AWAITING SIMULATION'}
                    </div>
                  </div>
                  <div className="network-facts">
                    <div><span>DEMO SATELLITES</span><b>{satellites.length.toString().padStart(2, '0')} <small>active</small></b></div>
                    <div><span>LAST ESTIMATE</span><b>{latest ? new Date(latest.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</b></div>
                    <div><span>PACKET LOSS</span><b>{latest ? `${fmt(latest.packet_loss)}%` : '—'}</b></div>
                  </div>
                </article>
              </section>
              <section className="panel bottom-panel">
                <div className="panel-head">
                  <div>
                    <h3>Recent simulations</h3>
                    <p>Your latest satellite visibility and link estimates</p>
                  </div>
                  <button className="text-button" onClick={() => setPage('Simulation')}>View all <span>→</span></button>
                </div>
                {simulations.length ? (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>STATUS</th><th>SATELLITE</th><th>LOCATION</th><th>ELEVATION</th><th>LATENCY</th><th>DATE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simulations.slice(0, 5).map(s => (
                          <tr key={s.id}>
                            <td>
                              <span className={`table-status ${s.status === 'visible' ? 'visible' : 'hidden'}`}><i />{s.status === 'visible' ? 'Visible' : 'No visibility'}</span>
                            </td>
                            <td><div className="sat-cell"><Satellite size={15} />{s.satellite_name || 'No satellite'}</div></td>
                            <td>{fmt(s.latitude_deg, 2)}°, {fmt(s.longitude_deg, 2)}°</td>
                            <td>{fmt(s.elevation_deg)}°</td>
                            <td>{fmt(s.latency_ms)} ms</td>
                            <td>{new Date(s.created_at).toLocaleDateString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-row">Your simulation history will appear here.</div>
                )}
              </section>
            </>
          )}
          {page === 'Simulation' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Connectivity simulation</h3>
                  <p>Estimate visibility and illustrative link performance from a location.</p>
                </div>
                <span className="estimate-chip"><span /> SIMULATION ONLY</span>
              </div>
              <div className="city-presets">
                <span style={{ fontSize: '11px', color: '#74899d', alignSelf: 'center', marginRight: '4px' }}>Quick locations:</span>
                {PRESET_LOCATIONS.map(p => (
                  <button
                    key={p.name}
                    type="button"
                    className="preset-chip"
                    onClick={() => {
                      setLatitude(String(p.lat));
                      setLongitude(String(p.lon));
                      void runSimulation(p.lat, p.lon);
                    }}
                  >
                    {p.name}
                  </button>
                ))}
                <button type="button" className="preset-chip" onClick={useCurrentLocation}>
                  <MapPin size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '3px' }} /> My GPS
                </button>
                <button type="button" className="preset-chip" style={{ background: '#1c3857', color: '#68c2f8', borderColor: '#306497' }} onClick={autoFindVisibleSatellite}>
                  <Orbit size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '3px' }} /> Auto-Find Satellite
                </button>
              </div>
              <div className="sim-form">
                <label>Latitude (°)<input type="number" min="-90" max="90" step="any" value={latitude} onChange={e => setLatitude(e.target.value)} /></label>
                <label>Longitude (°)<input type="number" min="-180" max="180" step="any" value={longitude} onChange={e => setLongitude(e.target.value)} /></label>
                <button className="primary" disabled={busy} onClick={() => void runSimulation()}>
                  <Play size={15} fill="currentColor" />{busy ? 'Calculating…' : 'Run simulation'}
                </button>
                <button className="secondary" disabled={busy} onClick={predictPassesForLocation} type="button">
                  <Clock3 size={15} /> Predict passes (12h)
                </button>
              </div>
              <div className="notice">
                <ShieldCheck size={18} />
                <span><b>Illustrative estimates only.</b> Orbital positions use simplified demo elements. Signal, latency and throughput are not measured RF performance or a real satellite service.</span>
              </div>
              {(latestSim || simulations[0]) && (
                <div className="result-card">
                  <div className="result-card-header">
                    <div>
                      <h4>Latest Simulation: {(latestSim || simulations[0]).satellite_name || 'LEO Constellation'}</h4>
                      <span style={{ fontSize: '11px', color: '#7d94aa' }}>
                        Location: {fmt((latestSim || simulations[0]).latitude_deg, 2)}°, {fmt((latestSim || simulations[0]).longitude_deg, 2)}° · {new Date((latestSim || simulations[0]).created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <span className={`table-status ${(latestSim || simulations[0]).status === 'visible' ? 'visible' : 'hidden'}`}>
                      <i /> {(latestSim || simulations[0]).status === 'visible' ? 'Satellite Visible' : 'No Direct Visibility'}
                    </span>
                  </div>
                  <div className="result-grid">
                    <div className="result-metric"><span>Elevation Angle</span><b>{fmt((latestSim || simulations[0]).elevation_deg)}°</b></div>
                    <div className="result-metric"><span>Slant Range</span><b>{fmt((latestSim || simulations[0]).distance_km)} km</b></div>
                    <div className="result-metric"><span>Signal Power</span><b>{fmt((latestSim || simulations[0]).signal_strength)} dBm</b></div>
                    <div className="result-metric"><span>RTT Latency</span><b>{fmt((latestSim || simulations[0]).latency_ms)} ms</b></div>
                    <div className="result-metric"><span>Download Rate</span><b>{fmt((latestSim || simulations[0]).download_mbps)} Mbps</b></div>
                    <div className="result-metric"><span>Packet Loss</span><b>{fmt((latestSim || simulations[0]).packet_loss)}%</b></div>
                  </div>
                  <div className="result-actions">
                    {(latestSim || simulations[0]).status === 'visible' && (
                      <button className="primary" onClick={startSession} disabled={busy}>
                        <Wifi size={14} /> Start demo session with {(latestSim || simulations[0]).satellite_name}
                      </button>
                    )}
                    <button className="secondary" onClick={() => viewSimulationReport((latestSim || simulations[0]).id)}>
                      <FileText size={14} /> View 3GPP Link Budget Report
                    </button>
                    <a className="secondary" style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '5px' }} href={`${API}/simulations/${(latestSim || simulations[0]).id}/export.csv`} download>
                      <Download size={14} /> Download CSV
                    </a>
                  </div>
                </div>
              )}
              {predictedPasses.length > 0 && (
                <>
                  <div className="section-title">
                    <div><h3>Predicted overhead passes</h3><p>{predictedPasses.length} contact windows within 12h</p></div>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr><th>SATELLITE</th><th>AOS (START)</th><th>TCA (PEAK)</th><th>LOS (END)</th><th>MAX EL</th><th>DURATION</th><th>DISTANCE</th></tr>
                      </thead>
                      <tbody>
                        {predictedPasses.map((p, idx) => (
                          <tr key={idx}>
                            <td><b>{p.satellite_name}</b></td>
                            <td>{new Date(p.aos_utc).toLocaleTimeString()}</td>
                            <td>{new Date(p.tca_utc).toLocaleTimeString()}</td>
                            <td>{new Date(p.los_utc).toLocaleTimeString()}</td>
                            <td><span className="table-status visible"><i />{p.max_elevation_deg}°</span></td>
                            <td>{Math.round(p.duration_seconds / 60)} min</td>
                            <td>{fmt(p.tca_distance_km)} km</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              <div className="section-title">
                <div><h3>Simulation history</h3><p>{simulations.length} recent runs</p></div>
              </div>
              {simulations.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>RESULT</th><th>SATELLITE</th><th>LOCATION</th><th>RANGE</th><th>SIGNAL</th><th>LATENCY</th><th>TIME</th><th>ACTIONS</th></tr>
                    </thead>
                    <tbody>
                      {simulations.map(s => (
                        <tr key={s.id}>
                          <td><span className={`table-status ${s.status === 'visible' ? 'visible' : 'hidden'}`}><i />{s.status === 'visible' ? 'Visible' : 'No visibility'}</span></td>
                          <td>{s.satellite_name || '—'}</td>
                          <td>{fmt(s.latitude_deg, 2)}, {fmt(s.longitude_deg, 2)}</td>
                          <td>{fmt(s.distance_km)} km</td>
                          <td>{fmt(s.signal_strength)} dBm</td>
                          <td>{fmt(s.latency_ms)} ms</td>
                          <td>{new Date(s.created_at).toLocaleString()}</td>
                          <td>
                            <div className="action-buttons">
                              <button className="btn-sm" onClick={() => viewSimulationReport(s.id)} title="View RF Report"><FileText size={11} /> Report</button>
                              <a className="btn-sm" href={`${API}/simulations/${s.id}/export.csv`} download title="Download CSV"><Download size={11} /> CSV</a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-row">No simulations yet. Choose a location and run one above.</div>
              )}
            </section>
          )}
          {page === 'Satellite network' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Demo satellite inventory</h3>
                  <p>Reference satellites for the simplified orbital model.</p>
                </div>
                <span className="count-chip">{satellites.length} satellites</span>
              </div>
              <div className="satellite-grid">
                {satellites.map(s => (
                  <article className="satellite-card" key={s.id}>
                    <div className="sat-card-top">
                      <div className="sat-large-icon"><Satellite size={21} /></div>
                      <span className="table-status visible"><i /> {s.status}</span>
                    </div>
                    <h3>{s.name}</h3>
                    <span className="satellite-sub">{s.orbit_type} · illustrative orbit</span>
                    <div className="sat-stats">
                      <div><span>ALTITUDE</span><b>{s.altitude_km.toLocaleString()} km</b></div>
                      <div><span>INCLINATION</span><b>{s.inclination_deg}°</b></div>
                    </div>
                    <button className="btn-sm" style={{ marginTop: '12px', width: '100%' }} onClick={() => viewTelemetry(s.id)}>
                      <Activity size={12} /> View live telemetry
                    </button>
                  </article>
                ))}
              </div>
              <div className="notice">
                <Orbit size={18} />
                <span>Satellite catalogue entries are synthetic demo objects. They are not operational spacecraft or live orbital data.</span>
              </div>
            </section>
          )}
          {page === 'Sessions' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Connection sessions</h3>
                  <p>Manage your simulated demo sessions.</p>
                </div>
                <button className="primary" onClick={startSession} disabled={busy}><Wifi size={15} /> Start demo session</button>
              </div>
              {connections.length ? (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>STATUS</th><th>SATELLITE</th><th>STARTED</th><th>ENDED</th><th>ACTION</th></tr>
                    </thead>
                    <tbody>
                      {connections.map(c => (
                        <tr key={c.id}>
                          <td><span className={`table-status ${c.status === 'connected' ? 'visible' : 'hidden'}`}><i />{c.status}</span></td>
                          <td>{c.satellite_name || '—'}</td>
                          <td>{new Date(c.started_at).toLocaleString()}</td>
                          <td>{c.ended_at ? new Date(c.ended_at).toLocaleString() : '—'}</td>
                          <td>
                            {c.status === 'connected' && (
                              <button className="text-button danger-text" onClick={() => endSession(c.id)}>End session</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-row">No sessions yet. Run a visible simulation to start a demo session.</div>
              )}
            </section>
          )}
          {page === 'Ground stations' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Ground station infrastructure</h3>
                  <p>Terrestrial tracking gateways and feeder-link coordination.</p>
                </div>
                <span className="count-chip">{groundStations.length} stations</span>
              </div>
              <form className="sim-form" onSubmit={addGroundStation}>
                <label>Station name<input value={newStationName} onChange={e => setNewStationName(e.target.value)} placeholder="e.g. Bangalore Gateway" required /></label>
                <label>Latitude (°)<input type="number" min="-90" max="90" step="any" value={newStationLat} onChange={e => setNewStationLat(e.target.value)} required /></label>
                <label>Longitude (°)<input type="number" min="-180" max="180" step="any" value={newStationLon} onChange={e => setNewStationLon(e.target.value)} required /></label>
                <button className="primary" disabled={busy} type="submit">
                  <Antenna size={15} /> Add station
                </button>
              </form>
              <div className="station-grid">
                {groundStations.map(gs => (
                  <article className="station-card" key={gs.id}>
                    <div className="station-card-top">
                      <div className="sat-large-icon"><Antenna size={21} /></div>
                      <span className="table-status visible"><i /> {gs.status}</span>
                    </div>
                    <h3>{gs.name}</h3>
                    <span className="satellite-sub">Terrestrial gateway feeder</span>
                    <div className="sat-stats">
                      <div><span>LATITUDE</span><b>{fmt(gs.latitude_deg, 4)}°</b></div>
                      <div><span>LONGITUDE</span><b>{fmt(gs.longitude_deg, 4)}°</b></div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}
          {page === 'Profile' && (
            <section className="panel page-panel profile-panel">
              <div className="panel-head">
                <div>
                  <h3>Profile details</h3>
                  <p>Manage your workspace identity.</p>
                </div>
                <button className="secondary" onClick={() => { setName(user.name); setEditing(!editing); }}>
                  {editing ? 'Cancel' : 'Edit profile'}
                </button>
              </div>
              <form onSubmit={saveProfile} className="profile-form">
                <label>Full name<input value={editing ? name : user.name} disabled={!editing} onChange={e => setName(e.target.value)} /></label>
                <label>Email address<input value={user.email} disabled /></label>
                <label>Account role<input value={user.role} disabled /></label>
                {editing && <button className="primary" disabled={busy}>Save changes</button>}
              </form>
              <div className="profile-security">
                <div><b>Password</b><small>Update your account password</small></div>
                <button className="secondary" onClick={() => setShowPassword(!showPassword)}>
                  {showPassword ? 'Cancel' : 'Change password'}
                </button>
              </div>
              {showPassword && (
                <form className="profile-form password-form" onSubmit={savePassword}>
                  <label>Current password<input type="password" autoComplete="current-password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} required /></label>
                  <label>New password<input type="password" autoComplete="new-password" minLength={10} value={newPassword} onChange={e => setNewPassword(e.target.value)} required /></label>
                  <button className="primary" disabled={busy}>Update password</button>
                </form>
              )}
              <div className="notice">
                <ShieldCheck size={18} />
                <span>Passwords are stored using server-side Argon2 hashing.</span>
              </div>
              <button className="signout-button" onClick={signOut}><LogOut size={16} /> Sign out</button>
            </section>
          )}
          {page === 'Settings' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Workspace settings</h3>
                  <p>Configuration for this prototype workspace.</p>
                </div>
              </div>
              <div className="settings-row">
                <div className="setting-symbol"><Command size={18} /></div>
                <div><b>API endpoint</b><small>Backend service URL configured for this web client</small></div>
                <code>{API}</code>
              </div>
              <div className="settings-row">
                <div className="setting-symbol"><ShieldCheck size={18} /></div>
                <div><b>Environment</b><small>Simulation mode is always active</small></div>
                <span className="status-pill"><span className="pulse-dot" /> DEMO</span>
              </div>
              <div className="notice">
                <CircleHelp size={18} />
                <span>Configure <code>VITE_API_BASE_URL</code> when deploying the web client to point at your backend.</span>
              </div>
            </section>
          )}
          {page === 'Network events' && (
            <section className="panel page-panel">
              <div className="panel-head">
                <div>
                  <h3>Network events</h3>
                  <p>Recent activity for your account.</p>
                </div>
                <span className="count-chip">{events.length} events</span>
              </div>
              {events.length ? (
                <div className="event-list">
                  {events.map(event => (
                    <article className="event-row" key={event.id}>
                      <span className="event-icon"><Activity size={16} /></span>
                      <div>
                        <b>{event.event_type.replace(/\./g, ' ')}</b>
                        <p>{event.description}</p>
                      </div>
                      <time>{new Date(event.created_at).toLocaleString()}</time>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="empty-row">Events from simulations and demo sessions will appear here.</div>
              )}
            </section>
          )}
          {page === 'Direct-to-Device' && (
            <D2DDashboard
              token={token!}
              latitude={latitude}
              longitude={longitude}
              onUpdateCoordinates={(lat, lon) => {
                setLatitude(lat);
                setLongitude(lon);
              }}
            />
          )}
          {page === 'Administration' && (
            <AdminModule
              token={token!}
              adminOverview={admin as any}
              onRefreshOverview={async () => {
                if (token) {
                  const data = await request<Record<string, number>>('/admin/dashboard', token).catch(() => null);
                  setAdmin(data);
                }
              }}
              metricRenderer={metric}
            />
          )}
          {telemetry && (
            <div className="modal-backdrop" onClick={() => setTelemetry(null)}>
              <div className="modal-dialog" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Live Telemetry: {telemetry.name}</h3>
                  <button className="close-nav" onClick={() => setTelemetry(null)}><X size={18} /></button>
                </div>
                <p style={{ fontSize: '11px', color: '#8aa2b8', margin: '0 0 14px' }}>Real-time orbital telemetry computed on WGS-84 reference ellipsoid.</p>
                <div className="modal-grid">
                  <div className="modal-item"><span>Sub-satellite Latitude</span><b>{fmt(telemetry.subsatellite_latitude_deg, 4)}°</b></div>
                  <div className="modal-item"><span>Sub-satellite Longitude</span><b>{fmt(telemetry.subsatellite_longitude_deg, 4)}°</b></div>
                  <div className="modal-item"><span>Altitude</span><b>{fmt(telemetry.altitude_km)} km</b></div>
                  <div className="modal-item"><span>Orbital Velocity</span><b>{fmt(telemetry.orbital_velocity_km_s, 2)} km/s</b></div>
                  <div className="modal-item"><span>Orbital Period</span><b>{fmt(telemetry.orbital_period_minutes, 1)} min</b></div>
                  <div className="modal-item"><span>Timestamp (UTC)</span><b>{new Date(telemetry.timestamp_utc).toLocaleTimeString()}</b></div>
                </div>
                <button className="secondary wide" onClick={() => setTelemetry(null)}>Close</button>
              </div>
            </div>
          )}
          {selectedReport && (
            <div className="modal-backdrop" onClick={() => setSelectedReport(null)}>
              <div className="modal-dialog" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>3GPP NTN Link Budget Report</h3>
                  <button className="close-nav" onClick={() => setSelectedReport(null)}><X size={18} /></button>
                </div>
                <p style={{ fontSize: '11px', color: '#8aa2b8', margin: '0 0 14px' }}>
                  Satellite: <b>{selectedReport.satellite?.name || 'Unknown'}</b> · Observer: {fmt(selectedReport.observer_location.latitude_deg, 2)}°, {fmt(selectedReport.observer_location.longitude_deg, 2)}°
                </p>
                <div className="modal-grid">
                  <div className="modal-item"><span>Free Space Path Loss</span><b>{fmt(selectedReport.rf_link_budget.free_space_path_loss_db)} dB</b></div>
                  <div className="modal-item"><span>Atmospheric Loss</span><b>{fmt(selectedReport.rf_link_budget.atmospheric_absorption_db)} dB</b></div>
                  <div className="modal-item"><span>Total Path Loss</span><b>{fmt(selectedReport.rf_link_budget.total_path_loss_db)} dB</b></div>
                  <div className="modal-item"><span>Carrier Frequency</span><b>{selectedReport.rf_link_budget.carrier_frequency_mhz} MHz</b></div>
                  <div className="modal-item"><span>Carrier-to-Noise (C/N0)</span><b>{fmt(selectedReport.rf_link_budget.c_n0_db_hz)} dB-Hz</b></div>
                  <div className="modal-item"><span>Signal-to-Noise (SNR)</span><b>{fmt(selectedReport.rf_link_budget.snr_db)} dB</b></div>
                  <div className="modal-item"><span>Download Throughput</span><b>{fmt(selectedReport.throughput_capacity.download_mbps)} Mbps</b></div>
                  <div className="modal-item"><span>Round Trip Latency</span><b>{fmt(selectedReport.throughput_capacity.latency_ms)} ms</b></div>
                </div>
                <div className="notice" style={{ margin: '14px 0' }}>
                  <CircleHelp size={16} />
                  <span>{selectedReport.prototype_disclaimer}</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <a className="primary wide" style={{ textAlign: 'center', textDecoration: 'none' }} href={`${API}/simulations/${selectedReport.simulation_id}/export.csv`} download>
                    <Download size={14} /> Download CSV
                  </a>
                  <button className="secondary wide" onClick={() => setSelectedReport(null)}>Close</button>
                </div>
              </div>
            </div>
          )}
          {showNewSimModal && (
            <div className="modal-backdrop" onClick={() => setShowNewSimModal(false)}>
              <div className="modal-dialog" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>Run New Simulation</h3>
                  <button className="close-nav" onClick={() => setShowNewSimModal(false)}><X size={18} /></button>
                </div>
                <p style={{ fontSize: '11px', color: '#8aa2b8', margin: '0 0 12px' }}>
                  Estimate orbital satellite visibility, elevation angle, and RF link performance from any observer coordinates.
                </p>
                <div className="city-presets">
                  <span style={{ fontSize: '11px', color: '#74899d', alignSelf: 'center', marginRight: '4px' }}>Quick presets:</span>
                  {PRESET_LOCATIONS.map(p => (
                    <button
                      key={p.name}
                      type="button"
                      className="preset-chip"
                      onClick={() => {
                        setLatitude(String(p.lat));
                        setLongitude(String(p.lon));
                        void runSimulation(p.lat, p.lon);
                      }}
                    >
                      {p.name}
                    </button>
                  ))}
                  <button type="button" className="preset-chip" onClick={useCurrentLocation}>
                    <MapPin size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '3px' }} /> GPS
                  </button>
                  <button type="button" className="preset-chip" style={{ background: '#1c3857', color: '#68c2f8', borderColor: '#306497' }} onClick={autoFindVisibleSatellite}>
                    <Orbit size={11} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '3px' }} /> Auto-Find Satellite
                  </button>
                </div>
                <div className="sim-form" style={{ gridTemplateColumns: '1fr 1fr', margin: '10px 0 16px' }}>
                  <label>Latitude (°)<input type="number" min="-90" max="90" step="any" value={latitude} onChange={e => setLatitude(e.target.value)} /></label>
                  <label>Longitude (°)<input type="number" min="-180" max="180" step="any" value={longitude} onChange={e => setLongitude(e.target.value)} /></label>
                </div>
                <button className="primary wide" disabled={busy} onClick={() => void runSimulation()}>
                  <Play size={15} fill="currentColor" /> {busy ? 'Calculating orbital link…' : 'Run simulation now'}
                </button>

                {latestSim && (
                  <div className="result-card" style={{ marginTop: '16px' }}>
                    <div className="result-card-header">
                      <h4>Result: {latestSim.satellite_name || 'LEO Orbit'}</h4>
                      <span className={`table-status ${latestSim.status === 'visible' ? 'visible' : 'hidden'}`}>
                        <i /> {latestSim.status === 'visible' ? 'Satellite Visible' : 'No Visibility'}
                      </span>
                    </div>
                    <div className="result-grid">
                      <div className="result-metric"><span>Elevation</span><b>{fmt(latestSim.elevation_deg)}°</b></div>
                      <div className="result-metric"><span>Distance</span><b>{fmt(latestSim.distance_km)} km</b></div>
                      <div className="result-metric"><span>Signal</span><b>{fmt(latestSim.signal_strength)} dBm</b></div>
                      <div className="result-metric"><span>Latency</span><b>{fmt(latestSim.latency_ms)} ms</b></div>
                    </div>
                    <div className="result-actions">
                      {latestSim.status === 'visible' && (
                        <button className="primary" onClick={() => { startSession(); setShowNewSimModal(false); }}>
                          <Wifi size={14} /> Start demo session
                        </button>
                      )}
                      <button className="secondary" onClick={() => { viewSimulationReport(latestSim.id); setShowNewSimModal(false); }}>
                        <FileText size={14} /> View link report
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        <footer className="main-footer">
          <span>SKYLINK DIRECT <i>·</i> PROTOTYPE ENVIRONMENT</span>
          <span>Simulated estimates only <span className="footer-dot" /> API operational</span>
        </footer>
      </main>
    </div>
  );
}
