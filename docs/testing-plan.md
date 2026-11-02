# Testing plan

The API test suite exercises registration, duplicate accounts, login, invalid credentials, bearer authentication, logout revocation, profile, satellite listing, simulation persistence, connection start/end, user ownership, administrator authorization and ORM relationships.

Run in PowerShell from the repository root:

```powershell
$env:PYTHONPATH = "backend"
python -m pytest backend\tests -q
```

Tests use a temporary SQLite database and FastAPI `TestClient`; no PostgreSQL or external orbital feed is required.

Web bundle check:

```powershell
cd web
npm install
npm run build
npm test
```

Flutter checks require Flutter SDK and generated platform files: `cd mobile; flutter analyze; flutter test`.

Future coverage should add pagination boundaries, migrations, PostgreSQL integration and session transition conflicts. Report results only for commands actually run.
