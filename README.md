# Vidhya Rakshak Reconciliation System

A real‑time student‑behavior reconciliation engine built with **Django** (backend) and **Vite + React** (frontend).  It ingests asynchronous behavioral events from multiple sources, resolves inconsistencies, and feeds a dropout‑prediction AI model.

## Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the Backend](#running-the-backend)
- [Running the Frontend](#running-the-frontend)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [License](#license)

## Features
- Multi‑source event ingestion via a REST API (`/api/events/`).
- Automatic conflict detection and resolution logic (`recon.engine`).
- Timezone handling set to **Indian Standard Time (Asia/Kolkata)**.
- Authenticated API (Django auth) with session & CSRF middleware.
- Modern glass‑morphism UI built with Vite, React, and vanilla CSS.
- Docker‑ready (optional) and easy local development.

## Prerequisites
- **Python 3.11+**
- **Node 20+** and **npm**
- **Git**
- (Optional) **Docker** for containerised deployment

## Setup – Backend
```bash
# Clone the repo (already pushed)
git clone https://github.com/kusalar/reconciliation-system.git
cd reconciliation-system/backend

# Create a virtual environment
python -m venv venv
source venv/Scripts/activate   # on Windows PowerShell
# or: source venv/bin/activate   # on Unix

# Install dependencies
pip install -r requirements.txt

# Apply migrations (creates auth & sessions tables)
python manage.py migrate

# (Optional) Seed sample data
python seed_data.py
```

## Running the Backend
```bash
# Development server (auto‑reload)
python manage.py runserver 8000
```
The API will be available at `http://127.0.0.1:8000/api/`.

## Setup – Frontend
```bash
cd ../frontend
npm install
```

## Running the Frontend
```bash
npm run dev
```
The UI will be served at `http://localhost:5173/`.  It connects to the backend automatically (proxy is configured in `vite.config.js`).

## Configuration
All important settings live in `backend_proj/settings.py`:
- `SECRET_KEY` – replace with a secure key for production.
- `DEBUG` – set to `False` in prod.
- `ALLOWED_HOSTS` – add your domain/IP.
- **Timezone** – already set to `Asia/Kolkata` (IST).
- Database – SQLite by default; switch to Postgres by editing the `DATABASES` dict.

## API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/events/` | POST | Ingest a behavioral event (JSON payload). |
| `/api/audit/`  | GET  | List reconciliation audit logs. |
| `/api/students/`| GET  | Retrieve student details. |

## Contributing
1. Fork the repository.
2. Create a feature branch.
3. Ensure both backend tests (`python manage.py test`) and frontend lint (`npm run lint`) pass.
4. Open a Pull Request.

## License
This project is licensed under the **MIT License** – see `LICENSE` for details.

---
*Created by the Vidhya Rakshak team for the Smart India Hackathon.*
