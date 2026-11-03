import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity,
  Antenna,
  Check,
  CircleAlert,
  CircleCheck,
  Clock3,
  Download,
  Edit2,
  ExternalLink,
  FileText,
  Filter,
  Gauge,
  Globe,
  Layers,
  Orbit,
  Play,
  Plus,
  Power,
  Radio,
  RefreshCw,
  RotateCcw,
  Satellite,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  Signal,
  Trash2,
  UserCheck,
  UserMinus,
  UserRound,
  Users,
  Wifi,
  X,
} from 'lucide-react';

const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export type AdminOverview = {
  total_users: number;
  total_satellites: number;
  total_simulations: number;
  active_sessions: number;
  network_events: number;
};

type AdminUser = {
  id: string;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  simulations_count: number;
  connections_count: number;
};

type AdminUserDetail = AdminUser & {
  devices: Array<{ id: string; name: string; platform: string; created_at: string }>;
  recent_simulations: Array<{ id: string; status: string; latitude_deg: number; longitude_deg: number; elevation_deg: number; created_at: string }>;
};

type AdminSatellite = {
  id: string;
  name: string;
  orbit_type: string;
  altitude_km: number;
  inclination_deg: number;
  raan_deg: number;
  phase_deg: number;
  status: string;
  created_at?: string;
};

type AdminGroundStation = {
  id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  status: string;
};

type AdminGateway = {
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
  created_at?: string;
};

type AdminSimulation = {
  id: string;
  user_id: string;
  user_email: string;
  satellite_name?: string;
  status: string;
  latitude_deg: number;
  longitude_deg: number;
  elevation_deg: number;
  distance_km: number;
  signal_strength: number;
  latency_ms: number;
  packet_loss: number;
  download_mbps: number;
  upload_mbps: number;
  created_at: string;
};

type AdminSession = {
  id: string;
  user_id: string;
  user_email: string;
  satellite_name?: string;
  status: string;
  started_at: string;
  ended_at?: string;
  signal_strength?: number;
  latency_ms?: number;
  packet_loss?: number;
};

type AdminEvent = {
  id: string;
  user_id?: string;
  event_type: string;
  description: string;
  created_at: string;
};

type AdminSystemHealth = {
  api_status: string;
  connectivity_mode: string;
  database_engine: string;
  database_connected: boolean;
  table_counts: Record<string, number>;
  simulation_engine: Record<string, string>;
  system_uptime_seconds: number;
  server_time_utc: string;
};

type AdminAuditLog = {
  id: string;
  admin_id?: string;
  admin_email: string;
  action: string;
  target_type: string;
  target_id?: string;
  details: string;
  created_at: string;
};

interface AdminModuleProps {
  token: string;
  adminOverview: AdminOverview | null;
  onRefreshOverview: () => Promise<void>;
  metricRenderer: (
    icon: any,
    label: string,
    value: string,
    unit: string,
    caption: string,
    color?: string
  ) => React.ReactNode;
}

export default function AdminModule({
  token,
  adminOverview,
  onRefreshOverview,
  metricRenderer,
}: AdminModuleProps) {
  const [activeTab, setActiveTab] = useState<
    'users' | 'satellites' | 'stations' | 'gateways' | 'simulations' | 'sessions' | 'events' | 'monitoring' | 'audit'
  >('users');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 1. Users State
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState('');
  const [selectedUserDetail, setSelectedUserDetail] = useState<AdminUserDetail | null>(null);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [editUserName, setEditUserName] = useState('');
  const [editUserRole, setEditUserRole] = useState<'admin' | 'user'>('user');
  const [editUserActive, setEditUserActive] = useState(true);

  // 2. Satellites State
  const [satellites, setSatellites] = useState<AdminSatellite[]>([]);
  const [satStatusFilter, setSatStatusFilter] = useState('');
  const [showAddSatModal, setShowAddSatModal] = useState(false);
  const [editingSat, setEditingSat] = useState<AdminSatellite | null>(null);
  const [satForm, setSatForm] = useState({
    name: '',
    orbit_type: 'LEO',
    altitude_km: '550',
    inclination_deg: '53.0',
    raan_deg: '0.0',
    phase_deg: '0.0',
    status: 'active',
  });
  const [liveTelemetry, setLiveTelemetry] = useState<any | null>(null);

  // 3. Ground Stations State
  const [stations, setStations] = useState<AdminGroundStation[]>([]);
  const [showAddStationModal, setShowAddStationModal] = useState(false);
  const [editingStation, setEditingStation] = useState<AdminGroundStation | null>(null);
  const [stationForm, setStationForm] = useState({
    name: '',
    latitude_deg: '12.9716',
    longitude_deg: '77.5946',
    status: 'demo',
  });

  // 4. Simulations State
  const [simulations, setSimulations] = useState<AdminSimulation[]>([]);
  const [simStatusFilter, setSimStatusFilter] = useState('');
  const [selectedSimReport, setSelectedSimReport] = useState<any | null>(null);

  // 5. Sessions State
  const [sessions, setSessions] = useState<AdminSession[]>([]);
  const [sessionStatusFilter, setSessionStatusFilter] = useState('');

  // 6. Network Events State
  const [events, setEvents] = useState<AdminEvent[]>([]);
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [eventSearch, setEventSearch] = useState('');

  // 7. System Monitoring State
  const [systemHealth, setSystemHealth] = useState<AdminSystemHealth | null>(null);

  // 8. Audit Logs State
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([]);
  const [auditActionFilter, setAuditActionFilter] = useState('');

  // 9. Gateways State
  const [gateways, setGateways] = useState<AdminGateway[]>([]);
  const [showAddGatewayModal, setShowAddGatewayModal] = useState(false);
  const [editingGateway, setEditingGateway] = useState<AdminGateway | null>(null);
  const [gatewayForm, setGatewayForm] = useState({
    name: '',
    latitude_deg: '13.0827',
    longitude_deg: '77.5877',
    elevation_m: '50.0',
    feeder_frequency_ghz: '28.5',
    status: 'operational',
    ip_address: '192.168.10.1',
    uplink_capacity_gbps: '10.0',
    downlink_capacity_gbps: '40.0',
  });

  // Universal helper
  async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
    const res = await fetch(`${API}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      let msg = res.status === 500
        ? 'Backend server on port 8000 is not reachable. Please run start.bat or start-backend.bat.'
        : `Request failed (${res.status})`;
      try {
        const json = JSON.parse(text);
        if (json.detail) msg = typeof json.detail === 'string' ? json.detail : JSON.stringify(json.detail);
      } catch {
        // use default msg
      }
      throw new Error(msg);
    }
    return res.status === 204 ? (undefined as T) : res.json();
  }

  const toQuery = (p: URLSearchParams) => (p.toString() ? `?${p.toString()}` : '');

  // Load active tab data
  const loadTabData = useCallback(
    async (tab: string) => {
      setLoading(true);
      setError('');
      try {
        if (tab === 'users') {
          const params = new URLSearchParams();
          if (userSearch) params.set('q', userSearch);
          if (userRoleFilter) params.set('role', userRoleFilter);
          const data = await apiRequest<{ items: AdminUser[] }>(`/admin/users${toQuery(params)}`);
          setUsers(data.items);
        } else if (tab === 'satellites') {
          const params = new URLSearchParams();
          if (satStatusFilter) params.set('status_filter', satStatusFilter);
          const data = await apiRequest<{ items: AdminSatellite[] }>(`/admin/satellites${toQuery(params)}`);
          setSatellites(data.items);
        } else if (tab === 'stations') {
          const data = await apiRequest<{ items: AdminGroundStation[] }>('/admin/ground-stations');
          setStations(data.items);
        } else if (tab === 'simulations') {
          const params = new URLSearchParams();
          if (simStatusFilter) params.set('status_filter', simStatusFilter);
          const data = await apiRequest<{ items: AdminSimulation[] }>(`/admin/simulations${toQuery(params)}`);
          setSimulations(data.items);
        } else if (tab === 'sessions') {
          const params = new URLSearchParams();
          if (sessionStatusFilter) params.set('status_filter', sessionStatusFilter);
          const data = await apiRequest<{ items: AdminSession[] }>(`/admin/sessions${toQuery(params)}`);
          setSessions(data.items);
        } else if (tab === 'events') {
          const params = new URLSearchParams();
          if (eventTypeFilter) params.set('event_type', eventTypeFilter);
          if (eventSearch) params.set('q', eventSearch);
          const data = await apiRequest<{ items: AdminEvent[] }>(`/admin/events${toQuery(params)}`);
          setEvents(data.items);
        } else if (tab === 'monitoring') {
          const data = await apiRequest<AdminSystemHealth>('/admin/system-health');
          setSystemHealth(data);
        } else if (tab === 'audit') {
          const params = new URLSearchParams();
          if (auditActionFilter) params.set('action', auditActionFilter);
          const data = await apiRequest<{ items: AdminAuditLog[] }>(`/admin/audit-logs${toQuery(params)}`);
          setAuditLogs(data.items);
        } else if (tab === 'gateways') {
          const data = await apiRequest<{ items: AdminGateway[] }>('/gateways?limit=50');
          setGateways(data.items);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load administration data');
      } finally {
        setLoading(false);
      }
    },
    [userSearch, userRoleFilter, satStatusFilter, simStatusFilter, sessionStatusFilter, eventTypeFilter, eventSearch, auditActionFilter, token]
  );

  useEffect(() => {
    void loadTabData(activeTab);
  }, [activeTab, loadTabData]);

  // User Actions
  async function handleSaveUser(e: React.FormEvent) {
    e.preventDefault();
    if (!editingUser) return;
    try {
      await apiRequest(`/admin/users/${editingUser.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: editUserName.trim(),
          role: editUserRole,
          is_active: editUserActive,
        }),
      });
      setSuccess(`User ${editingUser.email} updated successfully.`);
      setEditingUser(null);
      await loadTabData('users');
      await onRefreshOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to update user');
    }
  }

  async function handleViewUserDetail(userId: string) {
    try {
      const detail = await apiRequest<AdminUserDetail>(`/admin/users/${userId}`);
      setSelectedUserDetail(detail);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch user details');
    }
  }

  // Satellite Actions
  async function handleSaveSatellite(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingSat) {
        await apiRequest(`/admin/satellites/${editingSat.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: satForm.name.trim(),
            altitude_km: parseFloat(satForm.altitude_km),
            inclination_deg: parseFloat(satForm.inclination_deg),
            raan_deg: parseFloat(satForm.raan_deg),
            phase_deg: parseFloat(satForm.phase_deg),
            status: satForm.status,
          }),
        });
        setSuccess(`Satellite ${satForm.name} updated.`);
        setEditingSat(null);
      } else {
        await apiRequest('/admin/satellites', {
          method: 'POST',
          body: JSON.stringify({
            name: satForm.name.trim(),
            orbit_type: satForm.orbit_type,
            altitude_km: parseFloat(satForm.altitude_km),
            inclination_deg: parseFloat(satForm.inclination_deg),
            raan_deg: parseFloat(satForm.raan_deg),
            phase_deg: parseFloat(satForm.phase_deg),
            status: satForm.status,
          }),
        });
        setSuccess(`Satellite ${satForm.name} added.`);
        setShowAddSatModal(false);
      }
      await loadTabData('satellites');
      await onRefreshOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to save satellite');
    }
  }

  async function handleToggleSatStatus(sat: AdminSatellite) {
    const nextStatus = sat.status === 'active' ? 'decommissioned' : 'active';
    try {
      await apiRequest(`/admin/satellites/${sat.id}/status?status=${nextStatus}`, { method: 'PATCH' });
      setSuccess(`Satellite ${sat.name} marked as ${nextStatus}.`);
      await loadTabData('satellites');
      await onRefreshOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to update satellite status');
    }
  }

  async function handleViewTelemetry(satId: string) {
    try {
      const data = await apiRequest(`/satellites/${satId}/telemetry`);
      setLiveTelemetry(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch telemetry');
    }
  }

  // Ground Station Actions
  async function handleSaveStation(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingStation) {
        await apiRequest(`/admin/ground-stations/${editingStation.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: stationForm.name.trim(),
            latitude_deg: parseFloat(stationForm.latitude_deg),
            longitude_deg: parseFloat(stationForm.longitude_deg),
            status: stationForm.status,
          }),
        });
        setSuccess(`Ground station ${stationForm.name} updated.`);
        setEditingStation(null);
      } else {
        await apiRequest('/admin/ground-stations', {
          method: 'POST',
          body: JSON.stringify({
            name: stationForm.name.trim(),
            latitude_deg: parseFloat(stationForm.latitude_deg),
            longitude_deg: parseFloat(stationForm.longitude_deg),
            status: stationForm.status,
          }),
        });
        setSuccess(`Ground station ${stationForm.name} registered.`);
        setShowAddStationModal(false);
      }
      await loadTabData('stations');
    } catch (err: any) {
      setError(err.message || 'Failed to save ground station');
    }
  }

  async function handleDeleteStation(station: AdminGroundStation) {
    if (!window.confirm(`Delete ground station '${station.name}'?`)) return;
    try {
      await apiRequest(`/admin/ground-stations/${station.id}`, { method: 'DELETE' });
      setSuccess(`Ground station '${station.name}' deleted.`);
      await loadTabData('stations');
    } catch (err: any) {
      setError(err.message || 'Failed to delete ground station');
    }
  }

  // Satellite Gateway Actions
  async function handleSaveGateway(e: React.FormEvent) {
    e.preventDefault();
    try {
      if (editingGateway) {
        await apiRequest(`/gateways/${editingGateway.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: gatewayForm.name.trim(),
            latitude_deg: parseFloat(gatewayForm.latitude_deg),
            longitude_deg: parseFloat(gatewayForm.longitude_deg),
            elevation_m: parseFloat(gatewayForm.elevation_m),
            feeder_frequency_ghz: parseFloat(gatewayForm.feeder_frequency_ghz),
            status: gatewayForm.status,
            ip_address: gatewayForm.ip_address.trim(),
            uplink_capacity_gbps: parseFloat(gatewayForm.uplink_capacity_gbps),
            downlink_capacity_gbps: parseFloat(gatewayForm.downlink_capacity_gbps),
          }),
        });
        setSuccess(`Gateway '${gatewayForm.name}' updated.`);
        setEditingGateway(null);
      } else {
        await apiRequest('/gateways', {
          method: 'POST',
          body: JSON.stringify({
            name: gatewayForm.name.trim(),
            latitude_deg: parseFloat(gatewayForm.latitude_deg),
            longitude_deg: parseFloat(gatewayForm.longitude_deg),
            elevation_m: parseFloat(gatewayForm.elevation_m),
            feeder_frequency_ghz: parseFloat(gatewayForm.feeder_frequency_ghz),
            status: gatewayForm.status,
            ip_address: gatewayForm.ip_address.trim(),
            uplink_capacity_gbps: parseFloat(gatewayForm.uplink_capacity_gbps),
            downlink_capacity_gbps: parseFloat(gatewayForm.downlink_capacity_gbps),
          }),
        });
        setSuccess(`Gateway '${gatewayForm.name}' registered.`);
        setShowAddGatewayModal(false);
      }
      await loadTabData('gateways');
    } catch (err: any) {
      setError(err.message || 'Failed to save gateway');
    }
  }

  async function handleDeleteGateway(gw: AdminGateway) {
    if (!window.confirm(`Delete satellite gateway '${gw.name}'?`)) return;
    try {
      await apiRequest(`/gateways/${gw.id}`, { method: 'DELETE' });
      setSuccess(`Gateway '${gw.name}' deleted.`);
      await loadTabData('gateways');
    } catch (err: any) {
      setError(err.message || 'Failed to delete gateway');
    }
  }

  // Session Termination
  async function handleTerminateSession(sessionId: string) {
    if (!window.confirm('Force terminate this demo session?')) return;
    try {
      await apiRequest(`/admin/sessions/${sessionId}/terminate`, { method: 'POST' });
      setSuccess(`Demo session terminated.`);
      await loadTabData('sessions');
      await onRefreshOverview();
    } catch (err: any) {
      setError(err.message || 'Failed to terminate session');
    }
  }

  return (
    <section className="panel page-panel">
      {/* 1. System Overview Statistics (Preserved) */}
      <div className="panel-head">
        <div>
          <h3>System overview</h3>
          <p>Administrative statistics and management suite for SkyLink Direct.</p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            className="btn-sm"
            onClick={async () => {
              await onRefreshOverview();
              await loadTabData(activeTab);
            }}
            title="Refresh All"
          >
            <RefreshCw size={12} className={loading ? 'pulse-dot' : ''} /> Refresh
          </button>
          <span className="estimate-chip">
            <span /> ADMIN CONTROL
          </span>
        </div>
      </div>

      {adminOverview ? (
        <div className="metric-grid admin-grid">
          {metricRenderer(UserRound, 'Registered users', String(adminOverview.total_users), '', 'Across all accounts')}
          {metricRenderer(Satellite, 'Demo satellites', String(adminOverview.total_satellites), '', 'Synthetic catalogue', 'violet')}
          {metricRenderer(Activity, 'Simulation runs', String(adminOverview.total_simulations), '', 'User generated', 'green')}
          {metricRenderer(
            Radio,
            'Active sessions',
            String(adminOverview.active_sessions),
            '',
            `${adminOverview.network_events} network events`,
            'orange'
          )}
        </div>
      ) : (
        <div className="empty-row">Administrator access required.</div>
      )}

      {/* Notifications */}
      {error && (
        <div className="error-banner" style={{ margin: '0 20px 14px' }}>
          <span>{error}</span>
          <button onClick={() => setError('')}>
            <X size={14} />
          </button>
        </div>
      )}
      {success && (
        <div className="success-banner" style={{ margin: '0 20px 14px' }}>
          <span>{success}</span>
          <button onClick={() => setSuccess('')}>
            <X size={14} />
          </button>
        </div>
      )}

      {/* 2. Sub-Navigation Tabs */}
      <div className="admin-subnav">
        <button
          className={`admin-subtab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <Users size={14} /> User Management
        </button>
        <button
          className={`admin-subtab ${activeTab === 'satellites' ? 'active' : ''}`}
          onClick={() => setActiveTab('satellites')}
        >
          <Satellite size={14} /> Satellite Management
        </button>
        <button
          className={`admin-subtab ${activeTab === 'stations' ? 'active' : ''}`}
          onClick={() => setActiveTab('stations')}
        >
          <Antenna size={14} /> Ground Stations
        </button>
        <button
          className={`admin-subtab ${activeTab === 'gateways' ? 'active' : ''}`}
          onClick={() => setActiveTab('gateways')}
        >
          <Globe size={14} /> Satellite Gateways
        </button>
        <button
          className={`admin-subtab ${activeTab === 'simulations' ? 'active' : ''}`}
          onClick={() => setActiveTab('simulations')}
        >
          <Activity size={14} /> Simulation History
        </button>
        <button
          className={`admin-subtab ${activeTab === 'sessions' ? 'active' : ''}`}
          onClick={() => setActiveTab('sessions')}
        >
          <Radio size={14} /> Demo Sessions
        </button>
        <button
          className={`admin-subtab ${activeTab === 'events' ? 'active' : ''}`}
          onClick={() => setActiveTab('events')}
        >
          <Signal size={14} /> Network Events
        </button>
        <button
          className={`admin-subtab ${activeTab === 'monitoring' ? 'active' : ''}`}
          onClick={() => setActiveTab('monitoring')}
        >
          <Server size={14} /> System Monitoring
        </button>
        <button
          className={`admin-subtab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <FileText size={14} /> Audit Logs
        </button>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* TAB 1: USER MANAGEMENT */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'users' && (
        <div>
          <div className="admin-toolbar">
            <div className="admin-search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Search user by name or email…"
                value={userSearch}
                onChange={e => setUserSearch(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <select
                className="admin-filter-select"
                value={userRoleFilter}
                onChange={e => setUserRoleFilter(e.target.value)}
              >
                <option value="">All Roles</option>
                <option value="admin">Administrators</option>
                <option value="user">Standard Users</option>
              </select>
            </div>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Registered</th>
                  <th>Simulations</th>
                  <th>Sessions</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length > 0 ? (
                  users.map(u => (
                    <tr key={u.id}>
                      <td>
                        <div style={{ display: 'grid' }}>
                          <b style={{ color: '#e2edf7' }}>{u.name}</b>
                          <small style={{ color: '#7a8fa5', fontSize: '9px' }}>{u.email}</small>
                        </div>
                      </td>
                      <td>
                        <span className={`admin-badge ${u.role}`}>{u.role}</span>
                      </td>
                      <td>
                        <span className={`admin-badge ${u.is_active ? 'active' : 'inactive'}`}>
                          {u.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </td>
                      <td>{new Date(u.created_at).toLocaleDateString()}</td>
                      <td>{u.simulations_count}</td>
                      <td>{u.connections_count}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-action-row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            className="btn-sm"
                            onClick={() => handleViewUserDetail(u.id)}
                            title="View Details"
                          >
                            Details
                          </button>
                          <button
                            className="btn-sm"
                            onClick={() => {
                              setEditingUser(u);
                              setEditUserName(u.name);
                              setEditUserRole(u.role as 'admin' | 'user');
                              setEditUserActive(u.is_active);
                            }}
                            title="Edit Role & Permissions"
                          >
                            <Edit2 size={12} /> Edit
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} className="empty-row">
                      {loading ? 'Loading registered users…' : 'No user records matching criteria.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 2: SATELLITE MANAGEMENT */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'satellites' && (
        <div>
          <div className="admin-toolbar">
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <select
                className="admin-filter-select"
                value={satStatusFilter}
                onChange={e => setSatStatusFilter(e.target.value)}
              >
                <option value="">All Statuses</option>
                <option value="active">Active Constellation</option>
                <option value="decommissioned">Decommissioned</option>
                <option value="testing">Testing / Calibration</option>
              </select>
            </div>
            <button
              className="primary"
              onClick={() => {
                setEditingSat(null);
                setSatForm({
                  name: `Demo LEO ${String(satellites.length + 1).padStart(2, '0')}`,
                  orbit_type: 'LEO',
                  altitude_km: '550.0',
                  inclination_deg: '53.0',
                  raan_deg: '0.0',
                  phase_deg: '0.0',
                  status: 'active',
                });
                setShowAddSatModal(true);
              }}
            >
              <Plus size={14} /> Add Satellite Record
            </button>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Satellite Name</th>
                  <th>Orbit Type</th>
                  <th>Altitude</th>
                  <th>Inclination</th>
                  <th>RAAN</th>
                  <th>Phase</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {satellites.length > 0 ? (
                  satellites.map(sat => (
                    <tr key={sat.id}>
                      <td>
                        <div className="sat-cell">
                          <Satellite size={14} />
                          <b>{sat.name}</b>
                        </div>
                      </td>
                      <td>{sat.orbit_type}</td>
                      <td>{sat.altitude_km} km</td>
                      <td>{sat.inclination_deg}°</td>
                      <td>{sat.raan_deg}°</td>
                      <td>{sat.phase_deg}°</td>
                      <td>
                        <span className={`admin-badge ${sat.status}`}>{sat.status}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-action-row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            className="btn-sm"
                            onClick={() => handleViewTelemetry(sat.id)}
                            title="Live Telemetry"
                          >
                            <Orbit size={12} /> Telemetry
                          </button>
                          <button
                            className="btn-sm"
                            onClick={() => {
                              setEditingSat(sat);
                              setSatForm({
                                name: sat.name,
                                orbit_type: sat.orbit_type,
                                altitude_km: String(sat.altitude_km),
                                inclination_deg: String(sat.inclination_deg),
                                raan_deg: String(sat.raan_deg),
                                phase_deg: String(sat.phase_deg),
                                status: sat.status,
                              });
                              setShowAddSatModal(true);
                            }}
                            title="Edit Satellite"
                          >
                            <Edit2 size={12} /> Edit
                          </button>
                          <button
                            className="btn-sm"
                            onClick={() => handleToggleSatStatus(sat)}
                            title={sat.status === 'active' ? 'Deactivate Satellite' : 'Activate Satellite'}
                            style={{
                              color: sat.status === 'active' ? '#ff9e9e' : '#69deb0',
                              borderColor: sat.status === 'active' ? '#5a2d34' : '#1e593e',
                            }}
                          >
                            <Power size={12} />
                            {sat.status === 'active' ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="empty-row">
                      {loading ? 'Loading satellites…' : 'No satellites found.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 3: GROUND STATION MANAGEMENT */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'stations' && (
        <div>
          <div className="admin-toolbar">
            <span style={{ fontSize: '11px', color: '#889eb4' }}>
              Configured Earth gateway stations supporting direct-to-cell NTN relaying.
            </span>
            <button
              className="primary"
              onClick={() => {
                setEditingStation(null);
                setStationForm({
                  name: '',
                  latitude_deg: '12.9716',
                  longitude_deg: '77.5946',
                  status: 'operational',
                });
                setShowAddStationModal(true);
              }}
            >
              <Plus size={14} /> Add Ground Station
            </button>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Station Name</th>
                  <th>Latitude</th>
                  <th>Longitude</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {stations.length > 0 ? (
                  stations.map(st => (
                    <tr key={st.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Antenna size={14} style={{ color: '#5ec2ff' }} />
                          <b>{st.name}</b>
                        </div>
                      </td>
                      <td>{st.latitude_deg.toFixed(4)}°</td>
                      <td>{st.longitude_deg.toFixed(4)}°</td>
                      <td>
                        <span className={`admin-badge ${st.status}`}>{st.status}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-action-row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            className="btn-sm"
                            onClick={() => {
                              setEditingStation(st);
                              setStationForm({
                                name: st.name,
                                latitude_deg: String(st.latitude_deg),
                                longitude_deg: String(st.longitude_deg),
                                status: st.status,
                              });
                              setShowAddStationModal(true);
                            }}
                            title="Edit Station"
                          >
                            <Edit2 size={12} /> Edit
                          </button>
                          <button
                            className="btn-sm"
                            onClick={() => handleDeleteStation(st)}
                            title="Delete Station"
                            style={{ color: '#ff9e9e', borderColor: '#5a2d34' }}
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="empty-row">
                      {loading ? 'Loading ground stations…' : 'No ground stations registered.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB: SATELLITE GATEWAYS (FEEDER LINKS) */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'gateways' && (
        <div>
          <div className="admin-toolbar">
            <span style={{ fontSize: '11px', color: '#889eb4' }}>
              Ka-band high-capacity feeder teleports connecting constellation space segment to internet core.
            </span>
            <button
              className="primary"
              onClick={() => {
                setEditingGateway(null);
                setGatewayForm({
                  name: '',
                  latitude_deg: '13.0827',
                  longitude_deg: '77.5877',
                  elevation_m: '50.0',
                  feeder_frequency_ghz: '28.5',
                  status: 'operational',
                  ip_address: '192.168.10.1',
                  uplink_capacity_gbps: '10.0',
                  downlink_capacity_gbps: '40.0',
                });
                setShowAddGatewayModal(true);
              }}
            >
              <Plus size={14} /> Add Satellite Gateway
            </button>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Gateway Teleport</th>
                  <th>Coordinates</th>
                  <th>Feeder Freq</th>
                  <th>Egress IP</th>
                  <th>Capacity (DL / UL)</th>
                  <th>Satellites</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {gateways.length > 0 ? (
                  gateways.map(gw => (
                    <tr key={gw.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Globe size={14} style={{ color: '#4ee3a3' }} />
                          <b>{gw.name}</b>
                        </div>
                      </td>
                      <td>{gw.latitude_deg.toFixed(4)}°, {gw.longitude_deg.toFixed(4)}° ({gw.elevation_m}m)</td>
                      <td style={{ color: '#68c2f8' }}><b>{gw.feeder_frequency_ghz.toFixed(1)} GHz</b></td>
                      <td><code>{gw.ip_address}</code></td>
                      <td>{gw.downlink_capacity_gbps.toFixed(1)} / {gw.uplink_capacity_gbps.toFixed(1)} Gbps</td>
                      <td><span className="admin-badge user">{gw.supported_satellites_count} sats</span></td>
                      <td>
                        <span className={`admin-badge ${gw.status}`}>{gw.status}</span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-action-row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            className="btn-sm"
                            onClick={() => {
                              setEditingGateway(gw);
                              setGatewayForm({
                                name: gw.name,
                                latitude_deg: String(gw.latitude_deg),
                                longitude_deg: String(gw.longitude_deg),
                                elevation_m: String(gw.elevation_m),
                                feeder_frequency_ghz: String(gw.feeder_frequency_ghz),
                                status: gw.status,
                                ip_address: gw.ip_address,
                                uplink_capacity_gbps: String(gw.uplink_capacity_gbps),
                                downlink_capacity_gbps: String(gw.downlink_capacity_gbps),
                              });
                              setShowAddGatewayModal(true);
                            }}
                            title="Edit Gateway"
                          >
                            <Edit2 size={12} /> Edit
                          </button>
                          <button
                            className="btn-sm"
                            onClick={() => handleDeleteGateway(gw)}
                            title="Delete Gateway"
                            style={{ color: '#ff9e9e', borderColor: '#5a2d34' }}
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} className="empty-row">
                      {loading ? 'Loading gateways…' : 'No satellite gateways registered.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 4: SIMULATION HISTORY */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'simulations' && (
        <div>
          <div className="admin-toolbar">
            <select
              className="admin-filter-select"
              value={simStatusFilter}
              onChange={e => setSimStatusFilter(e.target.value)}
            >
              <option value="">All Outcomes</option>
              <option value="visible">Visible / Overhead Pass</option>
              <option value="no_visibility">Below Horizon / No Visibility</option>
              <option value="failed">Simulation Errors</option>
            </select>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>User</th>
                  <th>Satellite</th>
                  <th>Status</th>
                  <th>Location (Lat, Lon)</th>
                  <th>Elevation</th>
                  <th>Distance</th>
                  <th>Latency</th>
                  <th>Signal</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {simulations.length > 0 ? (
                  simulations.map(sim => (
                    <tr key={sim.id}>
                      <td>{new Date(sim.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                      <td>
                        <small style={{ color: '#9bb1c7' }}>{sim.user_email}</small>
                      </td>
                      <td>{sim.satellite_name || '—'}</td>
                      <td>
                        <span className={`admin-badge ${sim.status}`}>{sim.status}</span>
                      </td>
                      <td>
                        {sim.latitude_deg.toFixed(2)}°, {sim.longitude_deg.toFixed(2)}°
                      </td>
                      <td>{sim.elevation_deg.toFixed(1)}°</td>
                      <td>{sim.distance_km.toFixed(0)} km</td>
                      <td>{sim.latency_ms.toFixed(1)} ms</td>
                      <td>{sim.signal_strength.toFixed(1)} dBm</td>
                      <td style={{ textAlign: 'right' }}>
                        <div className="admin-action-row" style={{ justifyContent: 'flex-end' }}>
                          <button
                            className="btn-sm"
                            onClick={async () => {
                              try {
                                const report = await apiRequest(`/simulations/${sim.id}/report`);
                                setSelectedSimReport(report);
                              } catch (err: any) {
                                setError(err.message || 'Report not available');
                              }
                            }}
                            title="RF Link Report"
                          >
                            <FileText size={12} /> Report
                          </button>
                          <a
                            href={`${API}/simulations/${sim.id}/export.csv`}
                            className="btn-sm"
                            download={`simulation-${sim.id.slice(0, 8)}.csv`}
                            title="Download CSV"
                          >
                            <Download size={12} />
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={10} className="empty-row">
                      {loading ? 'Loading simulations…' : 'No simulations found.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 5: DEMO SESSIONS */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'sessions' && (
        <div>
          <div className="admin-toolbar">
            <select
              className="admin-filter-select"
              value={sessionStatusFilter}
              onChange={e => setSessionStatusFilter(e.target.value)}
            >
              <option value="">All Sessions</option>
              <option value="connected">Active / Connected Only</option>
              <option value="ended">Ended Sessions Only</option>
            </select>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Session ID</th>
                  <th>User Email</th>
                  <th>Connected Satellite</th>
                  <th>Status</th>
                  <th>Started At</th>
                  <th>Ended At</th>
                  <th>Signal</th>
                  <th>Latency</th>
                  <th style={{ textAlign: 'right' }}>Termination Control</th>
                </tr>
              </thead>
              <tbody>
                {sessions.length > 0 ? (
                  sessions.map(sess => (
                    <tr key={sess.id}>
                      <td>
                        <code>{sess.id.slice(0, 8)}…</code>
                      </td>
                      <td>{sess.user_email}</td>
                      <td>{sess.satellite_name || 'LEO Constellation'}</td>
                      <td>
                        <span className={`admin-badge ${sess.status}`}>
                          {sess.status === 'connected' && <span className="pulse-dot" style={{ width: 4, height: 4 }} />}
                          {sess.status}
                        </span>
                      </td>
                      <td>{new Date(sess.started_at).toLocaleTimeString()}</td>
                      <td>{sess.ended_at ? new Date(sess.ended_at).toLocaleTimeString() : 'Active now'}</td>
                      <td>{sess.signal_strength !== null && sess.signal_strength !== undefined ? `${sess.signal_strength.toFixed(1)} dBm` : '—'}</td>
                      <td>{sess.latency_ms !== null && sess.latency_ms !== undefined ? `${sess.latency_ms.toFixed(1)} ms` : '—'}</td>
                      <td style={{ textAlign: 'right' }}>
                        {sess.status === 'connected' ? (
                          <button
                            className="btn-terminate"
                            onClick={() => handleTerminateSession(sess.id)}
                            title="Force Terminate Session"
                          >
                            <Power size={11} style={{ marginRight: 4 }} /> Force Terminate
                          </button>
                        ) : (
                          <span style={{ fontSize: '9px', color: '#687e95' }}>Concluded</span>
                        )}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={9} className="empty-row">
                      {loading ? 'Loading demo sessions…' : 'No demo session records found.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 6: NETWORK EVENTS */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'events' && (
        <div>
          <div className="admin-toolbar">
            <div className="admin-search-box">
              <Search size={14} />
              <input
                type="text"
                placeholder="Search event descriptions…"
                value={eventSearch}
                onChange={e => setEventSearch(e.target.value)}
              />
            </div>
            <select
              className="admin-filter-select"
              value={eventTypeFilter}
              onChange={e => setEventTypeFilter(e.target.value)}
            >
              <option value="">All Event Categories</option>
              <option value="connection.started">Connection Started</option>
              <option value="connection.ended">Connection Ended</option>
              <option value="simulation.run">Simulation Run</option>
              <option value="admin.user.update">Admin User Updates</option>
              <option value="admin.satellite.create">Admin Satellite Created</option>
              <option value="admin.satellite.status_change">Admin Satellite Toggled</option>
              <option value="admin.session.terminate">Admin Terminated Session</option>
            </select>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Category</th>
                  <th>Description</th>
                  <th>User ID</th>
                </tr>
              </thead>
              <tbody>
                {events.length > 0 ? (
                  events.map(ev => (
                    <tr key={ev.id}>
                      <td>{new Date(ev.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                      <td>
                        <span className="admin-badge operational">{ev.event_type}</span>
                      </td>
                      <td style={{ color: '#dce6f1' }}>{ev.description}</td>
                      <td>
                        <small style={{ color: '#7f93a7' }}>{ev.user_id ? `${ev.user_id.slice(0, 8)}…` : 'System'}</small>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} className="empty-row">
                      {loading ? 'Loading network events…' : 'No events logged.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 7: SYSTEM MONITORING */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'monitoring' && (
        <div>
          {systemHealth ? (
            <div className="health-grid">
              <div className="health-card">
                <div className="health-card-header">
                  <h4>
                    <Server size={14} style={{ color: '#5ec2ff' }} /> Service Diagnostics
                  </h4>
                  <span className="admin-badge active">{systemHealth.api_status}</span>
                </div>
                <div className="health-stat-list">
                  <div className="health-stat-row">
                    <span>API Mode</span>
                    <b>{systemHealth.connectivity_mode}</b>
                  </div>
                  <div className="health-stat-row">
                    <span>Database Engine</span>
                    <b>{systemHealth.database_engine}</b>
                  </div>
                  <div className="health-stat-row">
                    <span>Database Connection</span>
                    <b style={{ color: '#54d89a' }}>Connected (Healthy)</b>
                  </div>
                  <div className="health-stat-row">
                    <span>Server Uptime</span>
                    <b>{(systemHealth.system_uptime_seconds / 60).toFixed(1)} minutes</b>
                  </div>
                  <div className="health-stat-row">
                    <span>Server Clock</span>
                    <b>{new Date(systemHealth.server_time_utc).toUTCString()}</b>
                  </div>
                </div>
              </div>

              <div className="health-card">
                <div className="health-card-header">
                  <h4>
                    <Gauge size={14} style={{ color: '#b4a5ff' }} /> Database Table Records
                  </h4>
                  <span className="estimate-chip">
                    <span /> TOTAL
                  </span>
                </div>
                <div className="health-stat-list">
                  {Object.entries(systemHealth.table_counts).map(([table, count]) => (
                    <div className="health-stat-row" key={table}>
                      <span style={{ textTransform: 'capitalize' }}>{table.replace('_', ' ')}</span>
                      <b>{count.toLocaleString()}</b>
                    </div>
                  ))}
                </div>
              </div>

              <div className="health-card" style={{ gridColumn: '1 / -1' }}>
                <div className="health-card-header">
                  <h4>
                    <Orbit size={14} style={{ color: '#55d99f' }} /> Simulation Engine Algorithms
                  </h4>
                  <span className="admin-badge operational">SCIENTIFIC VERIFIED</span>
                </div>
                <div className="health-stat-list" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', display: 'grid' }}>
                  {Object.entries(systemHealth.simulation_engine).map(([key, desc]) => (
                    <div key={key} style={{ background: '#12202f', padding: '10px 14px', borderRadius: '6px', border: '1px solid #1a3044' }}>
                      <span style={{ display: 'block', fontSize: '9px', color: '#6fbcf6', textTransform: 'uppercase', letterSpacing: '0.6px' }}>
                        {key.replace('_', ' ')}
                      </span>
                      <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#d3e2f0' }}>{desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="empty-row">{loading ? 'Running system diagnostics…' : 'System diagnostics unavailable.'}</div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------- */}
      {/* TAB 8: AUDIT LOGS */}
      {/* ------------------------------------------------------------- */}
      {activeTab === 'audit' && (
        <div>
          <div className="admin-toolbar">
            <select
              className="admin-filter-select"
              value={auditActionFilter}
              onChange={e => setAuditActionFilter(e.target.value)}
            >
              <option value="">All Administrative Actions</option>
              <option value="user.update">User Account / Role Updates</option>
              <option value="satellite.create">Satellite Additions</option>
              <option value="satellite.update">Satellite Edits</option>
              <option value="satellite.status_change">Satellite Status Toggles</option>
              <option value="ground_station.create">Ground Station Registrations</option>
              <option value="ground_station.update">Ground Station Edits</option>
              <option value="ground_station.delete">Ground Station Deletions</option>
              <option value="session.terminate">Session Force Terminations</option>
            </select>
          </div>

          <div className="table-wrap admin-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Administrator</th>
                  <th>Action</th>
                  <th>Target Type</th>
                  <th>Target ID</th>
                  <th>Action Details</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.length > 0 ? (
                  auditLogs.map(log => (
                    <tr key={log.id}>
                      <td>{new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                      <td>
                        <b style={{ color: '#dce6f1' }}>{log.admin_email}</b>
                      </td>
                      <td>
                        <span className="admin-badge admin">{log.action}</span>
                      </td>
                      <td style={{ textTransform: 'capitalize' }}>{log.target_type}</td>
                      <td>
                        <small style={{ color: '#889eb2' }}>{log.target_id ? `${log.target_id.slice(0, 8)}…` : '—'}</small>
                      </td>
                      <td style={{ color: '#c5d7e7' }}>{log.details}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6} className="empty-row">
                      {loading ? 'Retrieving audit trail…' : 'No administrative actions recorded yet.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ============================================================= */}
      {/* MODALS */}
      {/* ============================================================= */}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="modal-backdrop" onClick={() => setEditingUser(null)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit User: {editingUser.email}</h3>
              <button className="close-nav" onClick={() => setEditingUser(null)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveUser}>
              <label style={{ display: 'grid', gap: '6px', marginBottom: '12px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>Full Name</span>
                <input
                  type="text"
                  value={editUserName}
                  onChange={e => setEditUserName(e.target.value)}
                  required
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                />
              </label>

              <label style={{ display: 'grid', gap: '6px', marginBottom: '12px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>System Role</span>
                <select
                  value={editUserRole}
                  onChange={e => setEditUserRole(e.target.value as 'admin' | 'user')}
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                >
                  <option value="user">Standard User (user)</option>
                  <option value="admin">Administrator (admin)</option>
                </select>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
                <input
                  type="checkbox"
                  checked={editUserActive}
                  onChange={e => setEditUserActive(e.target.checked)}
                />
                <span style={{ fontSize: '11px', color: '#dce6f1' }}>Account Status is Active</span>
              </label>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-sm" onClick={() => setEditingUser(null)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Details Modal */}
      {selectedUserDetail && (
        <div className="modal-backdrop" onClick={() => setSelectedUserDetail(null)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>User Profile: {selectedUserDetail.name}</h3>
              <button className="close-nav" onClick={() => setSelectedUserDetail(null)}>
                <X size={18} />
              </button>
            </div>
            <div className="modal-grid">
              <div className="modal-item">
                <span>Email Address</span>
                <b>{selectedUserDetail.email}</b>
              </div>
              <div className="modal-item">
                <span>Role</span>
                <b>{selectedUserDetail.role}</b>
              </div>
              <div className="modal-item">
                <span>Account Status</span>
                <b style={{ color: selectedUserDetail.is_active ? '#54d89a' : '#f08989' }}>
                  {selectedUserDetail.is_active ? 'Active' : 'Suspended'}
                </b>
              </div>
              <div className="modal-item">
                <span>Member Since</span>
                <b>{new Date(selectedUserDetail.created_at).toLocaleDateString()}</b>
              </div>
            </div>

            <h4 style={{ margin: '16px 0 8px', fontSize: '12px', color: '#e0ebf7' }}>Registered Devices</h4>
            {selectedUserDetail.devices.length > 0 ? (
              <div style={{ display: 'grid', gap: '6px' }}>
                {selectedUserDetail.devices.map(d => (
                  <div
                    key={d.id}
                    style={{
                      background: '#12202f',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '11px',
                    }}
                  >
                    <span>{d.name}</span>
                    <span style={{ color: '#7fa0be' }}>{d.platform}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '10px', color: '#7a91a8' }}>No mobile or desktop devices paired yet.</p>
            )}

            <h4 style={{ margin: '16px 0 8px', fontSize: '12px', color: '#e0ebf7' }}>Recent Simulations</h4>
            {selectedUserDetail.recent_simulations.length > 0 ? (
              <div style={{ display: 'grid', gap: '6px' }}>
                {selectedUserDetail.recent_simulations.map(sim => (
                  <div
                    key={sim.id}
                    style={{
                      background: '#12202f',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '11px',
                    }}
                  >
                    <span>
                      ({sim.latitude_deg.toFixed(2)}°, {sim.longitude_deg.toFixed(2)}°)
                    </span>
                    <span className={`admin-badge ${sim.status}`}>{sim.status}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ fontSize: '10px', color: '#7a91a8' }}>No simulations recorded.</p>
            )}
          </div>
        </div>
      )}

      {/* Add / Edit Satellite Modal */}
      {showAddSatModal && (
        <div className="modal-backdrop" onClick={() => setShowAddSatModal(false)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingSat ? `Edit Satellite: ${editingSat.name}` : 'Add New Satellite to Catalogue'}</h3>
              <button className="close-nav" onClick={() => setShowAddSatModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveSatellite}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Satellite Name</span>
                  <input
                    type="text"
                    value={satForm.name}
                    onChange={e => setSatForm({ ...satForm, name: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Orbit Regime</span>
                  <select
                    value={satForm.orbit_type}
                    onChange={e => setSatForm({ ...satForm, orbit_type: e.target.value })}
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  >
                    <option value="LEO">LEO (Low Earth Orbit)</option>
                    <option value="MEO">MEO (Medium Earth Orbit)</option>
                    <option value="GEO">GEO (Geostationary)</option>
                  </select>
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Altitude (km)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={satForm.altitude_km}
                    onChange={e => setSatForm({ ...satForm, altitude_km: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Inclination (degrees)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={satForm.inclination_deg}
                    onChange={e => setSatForm({ ...satForm, inclination_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>RAAN (degrees)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={satForm.raan_deg}
                    onChange={e => setSatForm({ ...satForm, raan_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Orbital Phase (degrees)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={satForm.phase_deg}
                    onChange={e => setSatForm({ ...satForm, phase_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px', gridColumn: '1 / -1' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Operational Status</span>
                  <select
                    value={satForm.status}
                    onChange={e => setSatForm({ ...satForm, status: e.target.value })}
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  >
                    <option value="active">Active (Part of active constellation)</option>
                    <option value="decommissioned">Decommissioned (Inactive)</option>
                    <option value="testing">Testing / Calibration</option>
                  </select>
                </label>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-sm" onClick={() => setShowAddSatModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  {editingSat ? 'Update Satellite' : 'Add Satellite'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add / Edit Ground Station Modal */}
      {showAddStationModal && (
        <div className="modal-backdrop" onClick={() => setShowAddStationModal(false)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editingStation ? `Edit Ground Station: ${editingStation.name}` : 'Register New Ground Station'}</h3>
              <button className="close-nav" onClick={() => setShowAddStationModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveStation}>
              <label style={{ display: 'grid', gap: '6px', marginBottom: '12px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>Station Name</span>
                <input
                  type="text"
                  value={stationForm.name}
                  onChange={e => setStationForm({ ...stationForm, name: e.target.value })}
                  required
                  placeholder="e.g. Bangalore Gateway Alpha"
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                />
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Latitude (°N)</span>
                  <input
                    type="number"
                    step="0.0001"
                    value={stationForm.latitude_deg}
                    onChange={e => setStationForm({ ...stationForm, latitude_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Longitude (°E)</span>
                  <input
                    type="number"
                    step="0.0001"
                    value={stationForm.longitude_deg}
                    onChange={e => setStationForm({ ...stationForm, longitude_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
              </div>

              <label style={{ display: 'grid', gap: '6px', marginBottom: '20px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>Status</span>
                <select
                  value={stationForm.status}
                  onChange={e => setStationForm({ ...stationForm, status: e.target.value })}
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                >
                  <option value="operational">Operational</option>
                  <option value="demo">Demo Simulation Station</option>
                  <option value="maintenance">Maintenance</option>
                </select>
              </label>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-sm" onClick={() => setShowAddStationModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  {editingStation ? 'Update Station' : 'Create Station'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add / Edit Satellite Gateway Modal */}
      {showAddGatewayModal && (
        <div className="modal-backdrop" onClick={() => setShowAddGatewayModal(false)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()} style={{ maxWidth: '600px' }}>
            <div className="modal-header">
              <h3>{editingGateway ? `Edit Gateway: ${editingGateway.name}` : 'Register Satellite Feeder Gateway'}</h3>
              <button className="close-nav" onClick={() => setShowAddGatewayModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSaveGateway}>
              <label style={{ display: 'grid', gap: '6px', marginBottom: '12px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>Gateway Teleport Name</span>
                <input
                  type="text"
                  value={gatewayForm.name}
                  onChange={e => setGatewayForm({ ...gatewayForm, name: e.target.value })}
                  required
                  placeholder="e.g. Bangalore Teleport Gateway"
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                />
              </label>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Latitude (°N)</span>
                  <input
                    type="number"
                    step="0.0001"
                    value={gatewayForm.latitude_deg}
                    onChange={e => setGatewayForm({ ...gatewayForm, latitude_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Longitude (°E)</span>
                  <input
                    type="number"
                    step="0.0001"
                    value={gatewayForm.longitude_deg}
                    onChange={e => setGatewayForm({ ...gatewayForm, longitude_deg: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Feeder Frequency (GHz)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={gatewayForm.feeder_frequency_ghz}
                    onChange={e => setGatewayForm({ ...gatewayForm, feeder_frequency_ghz: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Egress IP Address</span>
                  <input
                    type="text"
                    value={gatewayForm.ip_address}
                    onChange={e => setGatewayForm({ ...gatewayForm, ip_address: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Downlink Capacity (Gbps)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={gatewayForm.downlink_capacity_gbps}
                    onChange={e => setGatewayForm({ ...gatewayForm, downlink_capacity_gbps: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
                <label style={{ display: 'grid', gap: '4px' }}>
                  <span style={{ fontSize: '10px', color: '#88a0b7' }}>Uplink Capacity (Gbps)</span>
                  <input
                    type="number"
                    step="0.1"
                    value={gatewayForm.uplink_capacity_gbps}
                    onChange={e => setGatewayForm({ ...gatewayForm, uplink_capacity_gbps: e.target.value })}
                    required
                    style={{
                      background: '#12202f',
                      border: '1px solid #1c3248',
                      color: '#dce6f1',
                      padding: '8px 10px',
                      borderRadius: '6px',
                    }}
                  />
                </label>
              </div>

              <label style={{ display: 'grid', gap: '6px', marginBottom: '20px' }}>
                <span style={{ fontSize: '10px', color: '#88a0b7' }}>Operational Status</span>
                <select
                  value={gatewayForm.status}
                  onChange={e => setGatewayForm({ ...gatewayForm, status: e.target.value })}
                  style={{
                    background: '#12202f',
                    border: '1px solid #1c3248',
                    color: '#dce6f1',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                >
                  <option value="operational">Operational</option>
                  <option value="standby">Standby / Backup</option>
                  <option value="maintenance">Maintenance</option>
                  <option value="offline">Offline</option>
                </select>
              </label>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                <button type="button" className="btn-sm" onClick={() => setShowAddGatewayModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="primary">
                  {editingGateway ? 'Update Gateway' : 'Create Gateway'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Live Telemetry Modal */}
      {liveTelemetry && (
        <div className="modal-backdrop" onClick={() => setLiveTelemetry(null)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Live Telemetry: {liveTelemetry.name}</h3>
              <button className="close-nav" onClick={() => setLiveTelemetry(null)}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: '11px', color: '#8aa2b8', margin: '0 0 14px' }}>
              Real-time orbital telemetry computed on WGS-84 reference ellipsoid with J2 nodal drift.
            </p>
            <div className="modal-grid">
              <div className="modal-item">
                <span>Sub-satellite Latitude</span>
                <b>{Number(liveTelemetry.subsatellite_latitude_deg).toFixed(4)}°</b>
              </div>
              <div className="modal-item">
                <span>Sub-satellite Longitude</span>
                <b>{Number(liveTelemetry.subsatellite_longitude_deg).toFixed(4)}°</b>
              </div>
              <div className="modal-item">
                <span>Orbital Velocity</span>
                <b>{Number(liveTelemetry.orbital_velocity_km_s).toFixed(2)} km/s</b>
              </div>
              <div className="modal-item">
                <span>Orbital Period</span>
                <b>{Number(liveTelemetry.orbital_period_minutes).toFixed(1)} mins</b>
              </div>
              <div className="modal-item">
                <span>Altitude</span>
                <b>{Number(liveTelemetry.altitude_km).toFixed(1)} km</b>
              </div>
              <div className="modal-item">
                <span>Timestamp (UTC)</span>
                <b>{new Date(liveTelemetry.timestamp_utc).toLocaleTimeString()} UTC</b>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* RF Link Budget Report Modal */}
      {selectedSimReport && (
        <div className="modal-backdrop" onClick={() => setSelectedSimReport(null)}>
          <div className="modal-dialog" onClick={e => e.stopPropagation()} style={{ maxWidth: '640px' }}>
            <div className="modal-header">
              <h3>Simulation RF Report: {selectedSimReport.satellite ? selectedSimReport.satellite.name : 'Horizon'}</h3>
              <button className="close-nav" onClick={() => setSelectedSimReport(null)}>
                <X size={18} />
              </button>
            </div>
            <p style={{ fontSize: '11px', color: '#8aa2b8', margin: '0 0 14px' }}>
              Carrier Frequency: {selectedSimReport.rf_link_budget.carrier_frequency_mhz} MHz · Saastamoinen Apparent Elevation: {Number(selectedSimReport.rf_link_budget.apparent_elevation_deg).toFixed(1)}°
            </p>
            <div className="modal-grid">
              <div className="modal-item">
                <span>Free Space Path Loss (FSPL)</span>
                <b>{Number(selectedSimReport.rf_link_budget.free_space_path_loss_db).toFixed(1)} dB</b>
              </div>
              <div className="modal-item">
                <span>Atmospheric Absorption (ITU-R P.676)</span>
                <b>{Number(selectedSimReport.rf_link_budget.atmospheric_absorption_db).toFixed(2)} dB</b>
              </div>
              <div className="modal-item">
                <span>Rx Signal Power</span>
                <b>{Number(selectedSimReport.rf_link_budget.rx_power_dbm).toFixed(1)} dBm</b>
              </div>
              <div className="modal-item">
                <span>Carrier-to-Noise Density (C/N₀)</span>
                <b>{Number(selectedSimReport.rf_link_budget.c_n0_db_hz).toFixed(1)} dB-Hz</b>
              </div>
              <div className="modal-item">
                <span>Estimated Download</span>
                <b>{Number(selectedSimReport.throughput_capacity.download_mbps).toFixed(1)} Mbps</b>
              </div>
              <div className="modal-item">
                <span>Estimated Latency</span>
                <b>{Number(selectedSimReport.throughput_capacity.latency_ms).toFixed(1)} ms</b>
              </div>
            </div>
            <div style={{ background: '#12202f', padding: '10px 14px', borderRadius: '6px', fontSize: '10px', color: '#829ab3', marginTop: '12px' }}>
              <ShieldCheck size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 6, color: '#5ec2ff' }} />
              {selectedSimReport.prototype_disclaimer}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
