# Blood SOS – Smart Blood Donation & Emergency Response System

**Blood SOS** is a full-stack, real-time web application engineered to bridge emergency blood patients and hospitals with compatible, nearby, eligible blood donors. Powered by automated ABO/Rh red blood cell compatibility matching, Haversine geospatial radius filtering, and an immutable points rewards ledger.

---

## 🌟 Key Features

1. **Emergency SOS Broadcast**: Prominent red SOS button on patient dashboard broadcasts alerts to all compatible donors within a configurable radius.
2. **Medical ABO/Rh Compatibility Engine**: Evaluates red blood cell transfusion compatibility across all 8 ABO/Rh blood groups (`A+`, `A-`, `B+`, `B-`, `AB+`, `AB-`, `O+`, `O-`).
3. **Looping Video Hero & Modern Dark UI**: Home page features high-impact looped background video (`home_bg.mp4`), glowing neon red emergency accents, and consistent branding with the Blood SOS logo.
4. **Donor Availability Management**: Real-time availability toggle (`available`, `unavailable`, `temporarily_unavailable`) with auditable state history.
5. **Interactive Map Discovery (Leaflet.js + OSM)**: Interactive dark-themed map displaying hospital emergencies and nearby donors with privacy-safe coordinate masking. Includes one-click external directions in Google Maps.
6. **Reward Points & Achievements Ledger**: Donors earn +100 LifePoints per verified completed donation. Features achievement badges (*"First Responder"*, *"Guardian Angel"*, *"Silver Hero"*, *"Legendary Life Saver"*), milestones, and duplicate-award prevention.
7. **Administrative Command Center**: KPI metrics, live Chart.js graphs, user moderation (suspend/reactivate, verify donors), and a 1-click donation verification queue.
8. **Cloud Database (Neon PostgreSQL)**: Seamless support for Neon PostgreSQL with SSL connection pooling, parameterization, and Alembic migrations.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 ORM, Pydantic v2, Python-Jose (JWT), Passlib (Bcrypt).
- **Database**: Neon PostgreSQL (with SQLite zero-config fallback for testing and development).
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System with Dark Navy & Neon Glow), Modern JavaScript (ES6+), Fetch API.
- **Geospatial & Visuals**: Leaflet.js, OpenStreetMap, Chart.js.
- **Testing**: Pytest with in-memory SQLite isolation.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure Python 3.10+ is installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Database
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
To connect to **Neon PostgreSQL**, paste your connection string into `.env`:
```env
DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-cool-fog-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
```
*(If left empty or as default, it automatically uses SQLite `blood_sos.db` so the system works immediately out of the box).*

### 4. Run Migrations & Seed Data
```bash
cd backend
python -m app.utils.seed
```
This automatically initializes all 10 tables and populates:
- **Default Administrator**: `admin@bloodsos.org` / `Admin@12345`
- **Verified Donors across blood groups**: `sarah.connor@example.com` (O-), `david.miller@example.com` (O+), etc. (Password: `Donor@12345`)
- **Sample Patient**: `patient@example.com` / `Patient@12345`
- **Initial Emergency SOS Request & Verified Donation**

### 5. Launch the Server
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```
Open your browser at **`http://localhost:8000`** to experience the full application.
API documentation is available at **`http://localhost:8000/docs`**.

---

## 🧪 Running Automated Tests

Run the complete pytest test suite:
```bash
cd backend
pytest -v
```
All 13 test suites covering ABO/Rh compatibility, distance calculation, JWT authentication, role access control, request lifecycle, and reward ledger idempotency will execute with 100% pass rate.

---

## 🔒 Security & Medical Privacy Highlights

- **Server-Side Authorization**: Roles are never trusted from the client and are strictly verified against authenticated database records.
- **Masked Donor Privacy**: Donors' exact home addresses and precise coordinates are never published publicly. Only approximate vicinity and verified statuses are shown.
- **Medical Disclaimer**: Automated matching filters serve as initial clinical filters; clinical cross-matching must always be performed by licensed healthcare professionals.
