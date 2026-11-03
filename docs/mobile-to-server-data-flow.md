# Mobile-to-Server Data Flow & Benchmark Logic

## 1. Sequence Overview

This document illustrates the end-to-end data flow between the user terminals (Flutter mobile application and React web dashboard) and the FastAPI backend service.

```mermaid
sequenceDiagram
    autonumber
    actor Terminal as User Terminal (Mobile / Web)
    participant API as FastAPI Backend (/api/v1)
    participant Sim as RF & Orbit Engine
    participant DB as SQLite / PostgreSQL

    Note over Terminal, API: 1. Health & Ping Latency Check
    Terminal->>API: GET /network/ping
    API-->>Terminal: 200 OK {status: "online", client_ip, server_time_utc, timestamp_ms}
    Terminal->>Terminal: Compute RTT = (t_end - t_start) ms

    Note over Terminal, API: 2. Download Throughput Benchmark
    Terminal->>API: GET /network/speedtest/download?size_mb=2
    activate API
    API-->>Terminal: StreamingResponse (2 MB binary octet stream)
    deactivate API
    Terminal->>Terminal: Compute Download Mbps = (bytes * 8) / (duration_sec * 1e6)

    Note over Terminal, API: 3. Upload Throughput Benchmark
    Terminal->>API: POST /network/speedtest/upload (512 KB payload)
    activate API
    API-->>Terminal: 200 OK {bytes_received: 524288, duration_ms, upload_speed_mbps}
    deactivate API

    Note over Terminal, DB: 4. Record Connectivity Benchmark
    Terminal->>API: POST /network/tests {ping_latency_ms, download_speed_mbps, upload_speed_mbps, ...}
    API->>DB: INSERT INTO connectivity_tests
    DB-->>API: Persisted (UUID)
    API-->>Terminal: 201 Created {id, ...}

    Note over Terminal, Sim: 5. Direct-to-Device Telemetry Query
    Terminal->>API: GET /network/d2d-dashboard?latitude_deg=...&longitude_deg=...
    API->>Sim: Propagate Keplerian orbits (J2 drift)
    Sim->>Sim: Compute FSPL + atmospheric attenuation
    API->>DB: Fetch nearest operational SatelliteGateway
    API-->>Terminal: 200 OK {mobile_device_status, selected_satellite, gateway_status, simulated_routing_path}
```

---

## 2. Latency Measurement Logic

### Client-Side Round-Trip Time (RTT)
The round-trip time measures the elapsed time from socket request dispatch to full header receipt:

$$\text{RTT}_{\text{measured}} = t_{\text{response\_received}} - t_{\text{request\_dispatched}}$$

- **Flutter Implementation (`mobile/lib/main.dart`):**
  ```dart
  final stopwatch = Stopwatch()..start();
  final response = await http.get(Uri.parse('$baseUrl/network/ping'))
      .timeout(const Duration(seconds: 4));
  stopwatch.stop();
  final pingLatencyMs = stopwatch.elapsedMilliseconds.toDouble();
  ```
- **Web Implementation (`web/src/components/D2DDashboard.tsx`):**
  ```typescript
  const t0 = performance.now();
  await fetchJson('/network/ping');
  const pingMs = Math.round(performance.now() - t0);
  ```

### Simulated Satellite One-Way Slant Delay
In the simulation engine, one-way propagation latency across the slant distance $d$ (meters) is computed using the speed of light $c = 299,792,458\text{ m/s}$:

$$\tau_{\text{prop}} = \frac{d}{c} \times 1000\quad (\text{ms})$$

Total modeled satellite round-trip latency includes ground processing overhead $\tau_{\text{proc}} \approx 8.0\text{ ms}$:

$$\text{Latency}_{\text{sat\_rtt}} = 2 \times \tau_{\text{prop}} + \tau_{\text{proc}}$$

For a typical LEO satellite at 550 km altitude with slant range $750\text{ km}$:
$$\tau_{\text{prop}} \approx \frac{750,000}{299,792,458} \times 1000 \approx 2.50\text{ ms} \implies \text{Latency}_{\text{LEO}} \approx 2 \times 2.50 + 8.0 \approx 13.0\text{ ms}$$

---

## 3. Throughput Calculation Logic

### 3.1 Download Throughput
Controlled binary blocks of size $S_{\text{bytes}}$ are streamed using chunked transfer encoding with zero disk overhead:

$$\text{Throughput}_{\text{download}} = \frac{S_{\text{bytes}} \times 8}{(t_{\text{download\_end}} - t_{\text{download\_start}}) \times 10^6}\quad (\text{Mbps})$$

- Controlled block sizes range from $0.5\text{ MB}$ to $10.0\text{ MB}$.
- Default test size is $2.0\text{ MB} = 2,097,152\text{ bytes} = 16,777,216\text{ bits}$.

### 3.2 Upload Throughput
The client dispatches an in-memory synthetic octet array (e.g., $512\text{ KB}$) to `/api/v1/network/speedtest/upload`. Both client and server measure duration independently to eliminate client clock skew:

$$\text{Throughput}_{\text{upload}} = \frac{\text{Bytes Received} \times 8}{\Delta t_{\text{server}} \times 10^6}\quad (\text{Mbps})$$

---

## 4. Error Handling & Offline State Management

1. **Timeout Detection:**
   - Client requests are bound by strict socket timeouts ($4.0\text{ seconds}$ on mobile, $10.0\text{ seconds}$ on web).
   - If an endpoint fails to respond within the timeout interval, the client sets `online_status: "offline"`.
2. **Graceful Fallback:**
   - If the backend is unreachable (`net::ERR_CONNECTION_REFUSED`), the UI flags the server status and retains the last-known satellite coordinates rather than crashing.
3. **Automatic Token Expiry Handling:**
   - Expired JWT tokens (older than 24 hours) are purged silently on app initialization, redirecting the user cleanly to authentication without firing cascade 500/401 errors.

