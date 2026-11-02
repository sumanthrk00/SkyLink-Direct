# SkyLink Direct — Local Setup & Deployment Guide

This document provides step-by-step instructions for running, testing, and developing the SkyLink Direct prototype across backend, web, and mobile environments.

---

## 1. System Requirements & Prerequisites

| Component | Requirement | Version Tested |
|---|---|---|
| **Operating System** | Windows 10/11, Ubuntu 22.04+, or macOS 13+ | Windows 11 Pro 64-bit |
| **Python** | Python 3.11 or 3.12 | 3.12.3 |
| **Node.js** | Node 18 LTS or 20+ | Node v20.x / npm 10.x |
| **Flutter SDK** *(Optional for mobile)* | Flutter 3.19+ with Android Studio / Xcode | Flutter 3.x |
| **Database** | SQLite (default development) or PostgreSQL 15+ | SQLite 3 |

---

## 2. Quick Start (Windows)

Two batch launcher scripts are pre-configured in the repository root for one-click startup:

### Step 1: Start the Backend Service
Double-click `start-backend.bat` or run in PowerShell:
```cmd
.\start-backend.bat
```
- Activates virtual environment in `.venv\`
- Initializes the SQLite database (`skylink.db`)
- Seeds 18 satellites across 6 orbital planes
- Seeds default `user` and `admin` roles, demo ground station, and demo admin credentials:
  - **Email:** `admin@skylink.direct`
  - **Password:** `AdminSecure2026!`
- Launches Uvicorn ASGI server on `http://0.0.0.0:8000`

### Step 2: Start the Web Dashboard
In a separate terminal or by double-clicking `start-web.bat`:
```cmd
.\start-web.bat
```
- Navigates to `web\`
- Launches Vite development server on `http://localhost:5173` (or `http://localhost:5174` if 5173 is occupied)
- Proxies `/api/v1` requests transparently to `http://127.0.0.1:8000`

Open your browser to `http://localhost:5173` (or the printed port).

---

## 3. Manual Step-by-Step Installation

### 3.1. Backend Setup (FastAPI)

1. **Create and activate a virtual environment:**
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables (Optional):**
   Copy `backend/.env.example` to `backend/.env` or specify environment variables:
   ```env
   DATABASE_URL=sqlite:///./skylink.db
   SECRET_KEY=super-secret-jwt-signing-key-for-development-change-in-production
   ACCESS_TOKEN_EXPIRE_MINUTES=1440
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174
   ```

4. **Run database migrations & seed:**
   ```bash
   python -c "from app.database import Base, engine, SessionLocal; from app.services.bootstrap import initialize_reference_data; Base.metadata.create_all(bind=engine); db = SessionLocal(); initialize_reference_data(db); db.close()"
   ```

5. **Start Uvicorn:**
   ```bash
   uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
   ```
   Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

### 3.2. Web Application Setup (React + TypeScript + Vite)

1. **Install dependencies:**
   ```bash
   cd web
   npm install
   ```

2. **Configure API base URL:**
   Inspect `web/.env.local` (or create if absent):
   ```env
   VITE_API_BASE_URL=/api/v1
   ```
   *(Using relative `/api/v1` routes requests through the Vite reverse proxy configured in `vite.config.ts`, avoiding cross-origin issues and network device IP binding problems).*

3. **Run the development server:**
   ```bash
   npm run dev
   ```

4. **Build production bundle:**
   ```bash
   npm run build
   ```

---

### 3.3. Mobile Application Setup (Flutter)

1. **Check Flutter doctor:**
   ```bash
   cd mobile
   flutter doctor
   ```

2. **Fetch packages:**
   ```bash
   flutter pub get
   ```

3. **Configure API endpoint:**
   Open `mobile/lib/main.dart` and verify the `baseUrl` constant:
   - For Android Emulator: `http://10.0.2.2:8000/api/v1`
   - For iOS Simulator: `http://127.0.0.1:8000/api/v1`
   - For Physical Device on Wi-Fi: `http://<YOUR_LAN_IP>:8000/api/v1` (e.g. `http://192.168.31.141:8000/api/v1`)

4. **Run the app:**
   ```bash
   flutter run
   ```

---

## 4. Test Verification

Execute the test suites to ensure zero regressions:

### Backend Pytest Suite
```bash
.\.venv\Scripts\pytest -v
```
Expected output: **5 passed** (auth lifecycle, simulation & connection ownership, admin role guard, ground stations API, relational cascade constraints).

### Web TypeScript and Vitest Suite
```bash
# Type check and production build
npm --prefix web run build

# Vitest unit tests
npm --prefix web test
```
Expected output: **1 passed** (rendering shell, branding, and auth forms).

---

## 5. Troubleshooting & FAQ

### Q: Why do I see `500 Internal Server Error` with `ECONNREFUSED 127.0.0.1:8000`?
**A:** The web app is running, but the Python backend is not running on port 8000. Start the backend by running `.\start-backend.bat` in a terminal.

### Q: Why did starting a connection return `409 Conflict`?
**A:** In the original prototype, this occurred if no satellite was above the horizon or an active session was already open. The current backend automatically archives older active sessions and selects the highest-elevation visible satellite.

### Q: How do I test the Admin dashboard?
**A:** Click the **"Demo Admin"** button on the login screen to auto-fill `admin@skylink.direct` and `AdminSecure2026!`, then click **"Sign in"**. The sidebar will display the **"Administration"** navigation option.

