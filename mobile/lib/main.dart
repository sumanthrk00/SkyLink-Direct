import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

// Override with --dart-define=API_BASE_URL=http://YOUR_HOST:8000/api/v1
const apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000/api/v1');
const ink = Color(0xFF09111C), panel = Color(0xFF101B29), blue = Color(0xFF55BFFF), muted = Color(0xFF91A2B6);

class Api {
  String? token;

  Future<dynamic> call(String path, {String method = 'GET', Map<String, dynamic>? body, Duration timeout = const Duration(seconds: 15)}) async {
    final uri = Uri.parse('$apiBaseUrl$path');
    final headers = <String, String>{
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
    final request = http.Request(method, uri)..headers.addAll(headers);
    if (body != null) request.body = jsonEncode(body);

    final streamed = await request.send().timeout(timeout);
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      var message = 'Request failed (${response.statusCode})';
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map && decoded['detail'] != null) {
          if (decoded['detail'] is List) {
            message = (decoded['detail'] as List)
                .map((e) => e is Map ? (e['msg'] ?? e.toString()) : e.toString())
                .join('; ');
          } else {
            message = decoded['detail'].toString();
          }
        }
      } catch (_) {}
      throw Exception(message);
    }
    if (response.statusCode == 204 || response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  // Network Connectivity: Ping
  Future<Map<String, dynamic>> ping() async {
    final sw = Stopwatch()..start();
    final res = await call('/network/ping', timeout: const Duration(seconds: 5));
    sw.stop();
    return {
      'status': res['status'] ?? 'online',
      'client_ip': res['client_ip'] ?? 'unknown',
      'latency_ms': sw.elapsedMilliseconds.toDouble(),
    };
  }

  // Network Connectivity: Download Speed Test (256 KB controlled payload)
  Future<double> testDownloadSpeed({int bytes = 262144}) async {
    final uri = Uri.parse('$apiBaseUrl/network/speedtest/download?size_bytes=$bytes');
    final sw = Stopwatch()..start();
    final response = await http.get(uri).timeout(const Duration(seconds: 15));
    sw.stop();
    if (response.statusCode != 200) throw Exception('Download test failed');
    final seconds = max(sw.elapsedMilliseconds / 1000.0, 0.01);
    return (response.bodyBytes.length * 8.0) / (seconds * 1000000.0);
  }

  // Network Connectivity: Upload Speed Test (128 KB controlled payload)
  Future<double> testUploadSpeed({int bytes = 131072}) async {
    final uri = Uri.parse('$apiBaseUrl/network/speedtest/upload');
    final dummyData = List<int>.filled(bytes, 65);
    final sw = Stopwatch()..start();
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/octet-stream'},
      body: dummyData,
    ).timeout(const Duration(seconds: 15));
    sw.stop();
    if (response.statusCode != 200) throw Exception('Upload test failed');
    final data = jsonDecode(response.body);
    return (data['upload_speed_mbps'] as num).toDouble();
  }
}

void main() => runApp(const SkyLinkApp());

class SkyLinkApp extends StatelessWidget {
  const SkyLinkApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'SkyLink Direct',
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(useMaterial3: true).copyWith(
          scaffoldBackgroundColor: ink,
          colorScheme: const ColorScheme.dark(primary: blue, surface: panel),
          appBarTheme: const AppBarTheme(backgroundColor: ink, foregroundColor: Colors.white),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: panel,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF2A3A4C))),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: const BorderSide(color: Color(0xFF2A3A4C))),
          ),
        ),
        home: const BootScreen(),
      );
}

class BootScreen extends StatefulWidget {
  const BootScreen({super.key});
  @override
  State<BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<BootScreen> {
  final api = Api();
  bool ready = false;

  @override
  void initState() {
    super.initState();
    _boot();
  }

  Future<void> _boot() async {
    final prefs = await SharedPreferences.getInstance();
    api.token = prefs.getString('token');
    if (mounted) setState(() => ready = true);
  }

  @override
  Widget build(BuildContext context) => !ready
      ? const Scaffold(body: Center(child: CircularProgressIndicator()))
      : api.token == null
          ? AuthScreen(
              api: api,
              onLogin: (token) async {
                final prefs = await SharedPreferences.getInstance();
                await prefs.setString('token', token);
                api.token = token;
                if (mounted) setState(() {});
              },
            )
          : HomeScreen(
              api: api,
              onLogout: () async {
                try {
                  await api.call('/auth/logout', method: 'POST');
                } catch (_) {}
                final prefs = await SharedPreferences.getInstance();
                await prefs.remove('token');
                api.token = null;
                if (mounted) setState(() {});
              },
            );
}

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key, required this.api, required this.onLogin});
  final Api api;
  final ValueChanged<String> onLogin;
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final form = GlobalKey<FormState>();
  final email = TextEditingController(), password = TextEditingController(), name = TextEditingController();
  bool registering = false, busy = false;
  String? error;

  Future<void> submit() async {
    if (!form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (registering) {
        await widget.api.call('/auth/register', method: 'POST', body: {
          'name': name.text.trim(),
          'email': email.text.trim(),
          'password': password.text,
        });
      }
      final result = await widget.api.call('/auth/login', method: 'POST', body: {
        'email': email.text.trim(),
        'password': password.text,
      });
      widget.onLogin(result['access_token']);
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: form,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Icon(Icons.satellite_alt, color: blue, size: 45),
                    const SizedBox(height: 12),
                    const Text('SKYLINK DIRECT', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 2)),
                    const SizedBox(height: 36),
                    Text(registering ? 'Create your account' : 'Welcome back', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    const Text('Satellite connectivity simulation prototype', style: TextStyle(color: muted)),
                    const SizedBox(height: 24),
                    if (registering) ...[
                      TextFormField(
                        controller: name,
                        decoration: const InputDecoration(labelText: 'Full name'),
                        validator: (v) => v == null || v.trim().isEmpty ? 'Enter your name' : null,
                      ),
                      const SizedBox(height: 14),
                    ],
                    TextFormField(
                      controller: email,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(labelText: 'Email address'),
                      validator: (v) => v == null || !v.contains('@') ? 'Enter a valid email' : null,
                    ),
                    const SizedBox(height: 14),
                    TextFormField(
                      controller: password,
                      obscureText: true,
                      decoration: const InputDecoration(labelText: 'Password'),
                      validator: (v) => v == null || v.length < (registering ? 10 : 1) ? (registering ? 'Use at least 10 characters' : 'Enter your password') : null,
                    ),
                    if (error != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(error!, style: const TextStyle(color: Colors.redAccent)),
                      ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: busy ? null : submit,
                      child: Text(busy ? 'Please wait…' : (registering ? 'Create account' : 'Sign in')),
                    ),
                    TextButton(
                      onPressed: () => setState(() {
                        registering = !registering;
                        error = null;
                      }),
                      child: Text(registering ? 'Already registered? Sign in' : 'Create an account'),
                    ),
                    const SizedBox(height: 12),
                    const Text('Simulation only · No real satellite connection', textAlign: TextAlign.center, style: TextStyle(color: muted, fontSize: 12)),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.api, required this.onLogout});
  final Api api;
  final VoidCallback onLogout;
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int tab = 0;
  bool loading = true, busy = false;
  String? error;
  bool isOnline = false;
  double lastPingMs = 0.0;

  Map<String, dynamic>? me, d2dData, latestSim;
  List<dynamic> satellites = [], simulations = [], connections = [], gateways = [], speedTests = [];

  final lat = TextEditingController(text: '12.9716'), lon = TextEditingController(text: '77.5946');

  // Speed test progress
  bool testingSpeed = false;
  String speedStatus = '';
  double currentDownload = 0.0, currentUpload = 0.0;

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    try {
      // 1. Connectivity check
      try {
        final pingData = await widget.api.ping();
        isOnline = true;
        lastPingMs = pingData['latency_ms'];
      } catch (_) {
        isOnline = false;
        lastPingMs = 0.0;
      }

      // 2. Fetch main workspace and D2D datasets
      final values = await Future.wait([
        widget.api.call('/users/me'),
        widget.api.call('/satellites?limit=50'),
        widget.api.call('/simulations?limit=10'),
        widget.api.call('/connections?limit=10'),
        widget.api.call('/gateways?limit=20').catchError((_) => {'items': []}),
        widget.api.call('/network/tests?limit=10').catchError((_) => {'items': []}),
        widget.api.call('/network/d2d-dashboard?latitude_deg=${double.tryParse(lat.text) ?? 12.9716}&longitude_deg=${double.tryParse(lon.text) ?? 77.5946}').catchError((_) => null),
      ]);

      if (!mounted) return;
      setState(() {
        me = values[0];
        satellites = values[1]['items'] ?? [];
        simulations = values[2]['items'] ?? [];
        connections = values[3]['items'] ?? [];
        gateways = values[4]['items'] ?? [];
        speedTests = values[5]['items'] ?? [];
        d2dData = values[6];
        latestSim = simulations.isEmpty ? null : simulations.first;
        loading = false;
        error = null;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  // Interactive Controlled Speedtest
  Future<void> runSpeedTest() async {
    setState(() {
      testingSpeed = true;
      speedStatus = 'Pinging backend gateway…';
      error = null;
    });

    try {
      final pingRes = await widget.api.ping();
      final pingMs = pingRes['latency_ms'] as double;

      setState(() => speedStatus = 'Testing download throughput…');
      final downMbps = await widget.api.testDownloadSpeed(bytes: 262144);
      currentDownload = downMbps;

      setState(() => speedStatus = 'Testing upload throughput…');
      final upMbps = await widget.api.testUploadSpeed(bytes: 131072);
      currentUpload = upMbps;

      setState(() => speedStatus = 'Recording performance record…');
      await widget.api.call('/network/tests', method: 'POST', body: {
        'client_platform': 'mobile_android',
        'ping_latency_ms': pingMs,
        'download_speed_mbps': downMbps,
        'upload_speed_mbps': upMbps,
        'packet_loss_percent': 0.0,
        'test_type': 'internet_speedtest',
        'status': 'completed',
        'server_location': 'Local Gateway Teleport',
      });

      await refresh();
      setState(() => speedStatus = 'Completed: ${downMbps.toStringAsFixed(1)} Mbps down / ${upMbps.toStringAsFixed(1)} Mbps up');
    } catch (e) {
      setState(() => error = 'Speed test failed: ${e.toString().replaceFirst("Exception: ", "")}');
    } finally {
      if (mounted) setState(() => testingSpeed = false);
    }
  }

  Future<void> simulate() async {
    setState(() => busy = true);
    try {
      await widget.api.call('/simulations', method: 'POST', body: {
        'latitude_deg': double.tryParse(lat.text) ?? 12.9716,
        'longitude_deg': double.tryParse(lon.text) ?? 77.5946,
      });
      await refresh();
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> startSession() async {
    setState(() => busy = true);
    try {
      final Map<String, dynamic> body = (latestSim != null && latestSim!['status'] == 'visible')
          ? {'simulation_id': latestSim!['id']}
          : {'latitude_deg': double.tryParse(lat.text) ?? 12.9716, 'longitude_deg': double.tryParse(lon.text) ?? 77.5946};
      await widget.api.call('/connections', method: 'POST', body: body);
      await refresh();
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> endSession(String id) async {
    setState(() => busy = true);
    try {
      await widget.api.call('/connections/$id/end', method: 'POST');
      await refresh();
    } catch (e) {
      setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String v(dynamic value, [int digits = 1]) => value is num ? value.toStringAsFixed(digits) : '—';

  @override
  Widget build(BuildContext context) {
    final titles = ['Direct-to-Device', 'Speed Test', 'Gateways', 'Simulation', 'Satellites', 'Profile'];

    if (loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            const Icon(Icons.satellite_alt, color: blue),
            const SizedBox(width: 8),
            Text(titles[tab], style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
            const Spacer(),
            // Online/Offline Status Indicator
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: isOnline ? const Color(0xFF112E21) : const Color(0xFF331A1F),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: isOnline ? Colors.greenAccent : Colors.redAccent),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(isOnline ? Icons.wifi : Icons.wifi_off, size: 12, color: isOnline ? Colors.greenAccent : Colors.redAccent),
                  const SizedBox(width: 4),
                  Text(
                    isOnline ? '${lastPingMs.toStringAsFixed(0)} ms' : 'Offline',
                    style: TextStyle(fontSize: 10, color: isOnline ? Colors.greenAccent : Colors.redAccent, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ],
        ),
        actions: [
          IconButton(onPressed: refresh, icon: const Icon(Icons.refresh)),
          IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout)),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (error != null)
              Card(
                color: const Color(0xFF3B2027),
                child: ListTile(
                  leading: const Icon(Icons.error_outline, color: Colors.redAccent),
                  title: Text(error!),
                  trailing: IconButton(onPressed: () => setState(() => error = null), icon: const Icon(Icons.close)),
                ),
              ),
            if (tab == 0) ...d2dDashboardView(),
            if (tab == 1) ...speedTestView(),
            if (tab == 2) ...gatewaysView(),
            if (tab == 3) ...simulationPage(),
            if (tab == 4) ...satellitePage(),
            if (tab == 5) ...profilePage(),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.phone_android), label: 'D2D'),
          NavigationDestination(icon: Icon(Icons.speed), label: 'Speed Test'),
          NavigationDestination(icon: Icon(Icons.cell_tower), label: 'Gateways'),
          NavigationDestination(icon: Icon(Icons.insights), label: 'Simulate'),
          NavigationDestination(icon: Icon(Icons.satellite_alt), label: 'Satellites'),
          NavigationDestination(icon: Icon(Icons.person_outline), label: 'Profile'),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // VIEW 1: Direct-to-Device (D2D) Dashboard
  // ---------------------------------------------------------------------------
  List<Widget> d2dDashboardView() {
    final devStatus = d2dData?['mobile_device_status'] ?? {};
    final netAvail = d2dData?['internet_availability'] ?? {};
    final sat = d2dData?['selected_satellite'];
    final vis = d2dData?['satellite_visibility'];
    final gw = d2dData?['gateway_status'];
    final path = d2dData?['simulated_routing_path'] as List<dynamic>? ?? [];
    final metrics = d2dData?['metrics'] ?? {};

    return [
      // Device Status Banner
      Card(
        color: const Color(0xFF132233),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              const Icon(Icons.smartphone, color: blue, size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Mobile Device: ${devStatus['platform'] ?? 'Android'}', style: const TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 2),
                    Text(netAvail['active_link_mode'] ?? 'Direct-to-Device Link Active', style: TextStyle(color: netAvail['d2d_satellite_available'] == true ? Colors.greenAccent : Colors.amber, fontSize: 11)),
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('Battery: ${devStatus['battery_level_percent'] ?? 88}%', style: const TextStyle(fontSize: 11, color: muted)),
                  const SizedBox(height: 2),
                  Text('${lat.text}°N, ${lon.text}°E', style: const TextStyle(fontSize: 10, color: muted)),
                ],
              ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 12),

      // Performance Metrics Grid
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [
          metric('LATENCY', '${v(metrics['latency_ms'])} ms', Icons.timer_outlined),
          metric('DOWNLOAD', '${v(metrics['download_speed_mbps'])} Mbps', Icons.download),
          metric('UPLOAD', '${v(metrics['upload_speed_mbps'])} Mbps', Icons.upload),
          metric('PACKET LOSS', '${v(metrics['packet_loss_percent'])}%', Icons.leak_remove),
        ],
      ),
      const SizedBox(height: 14),

      // Active Satellite & Gateway Cards
      Row(
        children: [
          Expanded(
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(children: [Icon(Icons.satellite_alt, size: 16, color: blue), SizedBox(width: 6), Text('SATELLITE', style: TextStyle(fontSize: 10, color: muted, fontWeight: FontWeight.bold))]),
                    const SizedBox(height: 6),
                    Text(sat?['name'] ?? 'Constellation', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    Text('Elevation: ${v(vis?['elevation_deg'])}°', style: const TextStyle(fontSize: 11, color: muted)),
                    Text('Range: ${v(vis?['slant_range_km'])} km', style: const TextStyle(fontSize: 11, color: muted)),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(children: [Icon(Icons.cell_tower, size: 16, color: Colors.orangeAccent), SizedBox(width: 6), Text('GATEWAY', style: TextStyle(fontSize: 10, color: muted, fontWeight: FontWeight.bold))]),
                    const SizedBox(height: 6),
                    Text(gw?['name'] ?? 'Bangalore Gateway', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13), overflow: TextOverflow.ellipsis),
                    Text('Feeder: ${v(gw?['feeder_frequency_ghz'])} GHz', style: const TextStyle(fontSize: 11, color: muted)),
                    Text('Status: ${gw?['status'] ?? 'Operational'}', style: const TextStyle(fontSize: 11, color: Colors.greenAccent)),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
      const SizedBox(height: 16),

      // Simulated Routing Path Diagram
      const Text('SIMULATED D2D ROUTING PATH', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: muted, letterSpacing: 1)),
      const SizedBox(height: 8),
      ...path.map((step) => Card(
            margin: const EdgeInsets.only(bottom: 6),
            child: ListTile(
              dense: true,
              leading: CircleAvatar(
                radius: 12,
                backgroundColor: const Color(0xFF172C40),
                child: Text('${step['step']}', style: const TextStyle(fontSize: 11, color: blue, fontWeight: FontWeight.bold)),
              ),
              title: Text(step['node'] ?? '', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              subtitle: Text('${step['role']} · ${step['details']}', style: const TextStyle(fontSize: 10, color: muted)),
              trailing: Icon(step['status'] == 'connected' || step['status'] == 'active' || step['status'] == 'operational' || step['status'] == 'online' ? Icons.check_circle : Icons.radio_button_checked, size: 14, color: Colors.greenAccent),
            ),
          )),
      const SizedBox(height: 10),
      const Text('Simulation only. Does not claim real satellite hardware routing.', textAlign: TextAlign.center, style: TextStyle(color: muted, fontSize: 11)),
    ];
  }

  // ---------------------------------------------------------------------------
  // VIEW 2: Mobile Speed Test
  // ---------------------------------------------------------------------------
  List<Widget> speedTestView() => [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                const Icon(Icons.speed, size: 40, color: blue),
                const SizedBox(height: 10),
                const Text('Internet Connectivity & Speed Test', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                const Text('Measures live HTTP response time, download and upload throughput.', textAlign: TextAlign.center, style: TextStyle(color: muted, fontSize: 11)),
                const SizedBox(height: 16),
                if (testingSpeed) ...[
                  const CircularProgressIndicator(),
                  const SizedBox(height: 12),
                  Text(speedStatus, style: const TextStyle(color: blue, fontSize: 12)),
                  const SizedBox(height: 12),
                ],
                FilledButton.icon(
                  onPressed: testingSpeed ? null : runSpeedTest,
                  icon: const Icon(Icons.play_arrow),
                  label: Text(testingSpeed ? 'Testing…' : 'Start Connectivity Test'),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        const Text('TEST HISTORY', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: muted, letterSpacing: 1)),
        const SizedBox(height: 8),
        if (speedTests.isEmpty)
          card('No Tests Recorded', 'Run a connectivity test above to record speed and latency.', Icons.history)
        else
          ...speedTests.map((t) => Card(
                child: ListTile(
                  leading: const Icon(Icons.network_check, color: blue),
                  title: Text('${v(t['download_speed_mbps'])} Mbps ↓   ${v(t['upload_speed_mbps'])} Mbps ↑'),
                  subtitle: Text('Ping: ${v(t['ping_latency_ms'])} ms · ${t['server_location']}'),
                  trailing: Text(
                    DateTime.parse(t['created_at']).toLocal().toString().substring(11, 19),
                    style: const TextStyle(fontSize: 11, color: muted),
                  ),
                ),
              )),
      ];

  // ---------------------------------------------------------------------------
  // VIEW 3: Satellite Gateways
  // ---------------------------------------------------------------------------
  List<Widget> gatewaysView() => [
        card('Satellite Gateway Stations', 'Ground teleports relaying satellite feeder links to terrestrial backhaul.', Icons.cell_tower),
        const SizedBox(height: 8),
        if (gateways.isEmpty)
          card('No Gateways Found', 'No ground teleports registered in the system.', Icons.warning)
        else
          ...gateways.map((g) => Card(
                child: ListTile(
                  leading: const Icon(Icons.podcasts, color: Colors.orangeAccent),
                  title: Text(g['name']),
                  subtitle: Text('Coord: ${v(g['latitude_deg'], 2)}°N, ${v(g['longitude_deg'], 2)}°E\nFeeder: ${v(g['feeder_frequency_ghz'])} GHz Ka-band · Capacity: ${v(g['downlink_capacity_gbps'])} Gbps'),
                  trailing: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(color: const Color(0xFF142B20), borderRadius: BorderRadius.circular(4), border: Border.all(color: Colors.greenAccent)),
                    child: Text(g['status'] ?? 'Operational', style: const TextStyle(color: Colors.greenAccent, fontSize: 10)),
                  ),
                ),
              )),
      ];

  // ---------------------------------------------------------------------------
  // VIEW 4: Simulation
  // ---------------------------------------------------------------------------
  List<Widget> simulationPage() => [
        card('Observer Location', 'Set latitude and longitude coordinates for orbital simulation.', Icons.location_on_outlined),
        const SizedBox(height: 10),
        TextField(controller: lat, keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true), decoration: const InputDecoration(labelText: 'Latitude (°)')),
        const SizedBox(height: 10),
        TextField(controller: lon, keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: true), decoration: const InputDecoration(labelText: 'Longitude (°)')),
        const SizedBox(height: 14),
        FilledButton.icon(onPressed: busy ? null : simulate, icon: const Icon(Icons.play_arrow), label: Text(busy ? 'Calculating…' : 'Run Simulation')),
        const SizedBox(height: 16),
        if (latestSim != null)
          card(
            'Latest Result',
            '${latestSim!['status']} · ${latestSim!['satellite_name'] ?? 'No satellite'}\nRange ${v(latestSim!['distance_km'])} km · Signal ${v(latestSim!['signal_strength'])} dBm\nLatency ${v(latestSim!['latency_ms'])} ms · Loss ${v(latestSim!['packet_loss'])}%',
            Icons.insights,
          ),
      ];

  // ---------------------------------------------------------------------------
  // VIEW 5: Satellites
  // ---------------------------------------------------------------------------
  List<Widget> satellitePage() => [
        card('Demo Satellite Inventory', 'Constellation catalogue evaluated on WGS-84 ellipsoid.', Icons.public),
        const SizedBox(height: 8),
        ...satellites.map((s) => Card(
              child: ListTile(
                leading: const Icon(Icons.satellite_alt, color: blue),
                title: Text(s['name']),
                subtitle: Text('${s['orbit_type']} · ${s['altitude_km']} km · ${s['inclination_deg']}° inc'),
                trailing: Text(s['status'] ?? 'active', style: const TextStyle(color: Colors.greenAccent, fontSize: 11)),
              ),
            )),
      ];

  // ---------------------------------------------------------------------------
  // VIEW 6: Profile
  // ---------------------------------------------------------------------------
  List<Widget> profilePage() => [
        card('Profile', me?['name'] ?? 'User', Icons.person),
        card('Email', me?['email'] ?? '', Icons.email_outlined),
        card('Account Role', me?['role'] ?? 'user', Icons.verified_user),
        const SizedBox(height: 16),
        OutlinedButton.icon(onPressed: widget.onLogout, icon: const Icon(Icons.logout), label: const Text('Sign out')),
      ];

  Widget metric(String label, String value, IconData icon) => SizedBox(
        width: (MediaQuery.sizeOf(context).width - 42) / 2,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, color: blue, size: 20),
                const SizedBox(height: 8),
                Text(label, style: const TextStyle(color: muted, fontSize: 10)),
                const SizedBox(height: 4),
                Text(value, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              ],
            ),
          ),
        ),
      );

  Widget card(String title, String body, IconData icon) => Card(
        child: ListTile(
          leading: Icon(icon, color: blue),
          title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          subtitle: Padding(padding: const EdgeInsets.only(top: 4), child: Text(body, style: const TextStyle(fontSize: 11, color: muted))),
        ),
      );
}
