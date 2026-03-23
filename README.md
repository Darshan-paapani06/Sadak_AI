<div align="center">

<img src="main/logo-animated" width="100%" alt="SADAK AI — Smart Road Guardian"/>
 
<br/>

<!-- TECH BADGES -->
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-AI_Engine-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://ultralytics.com)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org)
[![Supabase](https://img.shields.io/badge/Supabase-Cloud_DB-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com)
[![SQLite](https://img.shields.io/badge/SQLite-Local_DB-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8?style=for-the-badge&logo=pwa&logoColor=white)](https://web.dev/pwa)
[![JWT](https://img.shields.io/badge/JWT-Secured-000000?style=for-the-badge&logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![Leaflet](https://img.shields.io/badge/Leaflet.js-Live_Map-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

<br/>

<!-- STAT PILLS -->
<table>
<tr>
<td align="center"><b>🌍 36</b><br/><sub>States</sub></td>
<td align="center"><b>🏘️ 782</b><br/><sub>Districts</sub></td>
<td align="center"><b>🗺️ 7,075+</b><br/><sub>Localities</sub></td>
<td align="center"><b>🌐 22</b><br/><sub>Languages</sub></td>
<td align="center"><b>🤖 YOLOv8</b><br/><sub>AI Engine</sub></td>
<td align="center"><b>☁️ Supabase</b><br/><sub>Cloud Sync</sub></td>
<td align="center"><b>📡 35+</b><br/><sub>API Routes</sub></td>
<td align="center"><b>📝 8,000+</b><br/><sub>Lines of Code</sub></td>
</tr>
</table>

<br/>

> ### *"A pothole reported is a life saved."*
> SADAK AI empowers every Indian citizen to report road damage using real AI —
> the right authority gets notified instantly, and every complaint is tracked to resolution.

</div>

---

<br/>

## 🛣️ How It Works

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  📱 CITIZEN ──► 📷 AI SCAN ──► 📍 GPS ROUTE ──► ✉️  FILE           │
│       │                                               │              │
│       │                             ┌─────────────────┘              │
│       │                             ▼                                │
│       │                 🏛️  Gram Panchayat  (Village Roads)          │
│       │                 🏗️  PWD             (State Roads)            │
│       │                 🛣️  NHAI            (National Highways)      │
│       │                             │                                │
│       └──── 📊 LIVE UPDATES ◄───────┘◄──── ☁️  SUPABASE CLOUD       │
│                                                                      │
│  FILED ──► ACKNOWLEDGED ──► IN PROGRESS ──► ✅ RESOLVED             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

<br/>

---

## ✨ Complete Feature Set

### 🤖 AI Detection Engine

| Feature | Detail |
|---------|--------|
| **YOLOv8 Model** | Custom-trained on Indian road datasets — real pothole detection |
| **Confidence Gate** | 55% minimum confidence — eliminates every weak/false guess |
| **Size Filter** | Min 1,200px² bounding box — rejects pebbles, dust, noise |
| **Aspect Ratio Filter** | Max 5.0 ratio — rejects road markings, shadows, elongated shapes |
| **7-Stage OpenCV Fallback** | No GPU/model? Edge detection → contours → Otsu thresholding |
| **Real-Time Scanner** | Live camera feed with frame-by-frame AI analysis |
| **Severity Engine** | CRITICAL / HIGH / MEDIUM / LOW — auto-calculated |
| **Road Quality Index** | District-level RQI 0–100 with grade, trend, worst-spot analysis |

---

### ☁️ Cloud Architecture (NEW)

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   LOCAL (SQLite)           CLOUD (Supabase PostgreSQL)      │
│   ─────────────            ───────────────────────────      │
│   Primary DB ──────────────────────► Mirror DB              │
│   Fast reads               Real-time dashboard              │
│   Offline safe             Live analytics                   │
│   Zero latency             Accessible anywhere              │
│                                                             │
│   SYNC EVENTS:                                              │
│   ✅ User registers    ──► users table                      │
│   ✅ Complaint filed   ──► complaints table                 │
│   ✅ Status updated    ──► complaints table                 │
│   ✅ User deleted      ──► removed from cloud               │
│   ✅ Role changed      ──► synced instantly                 │
│                                                             │
│   CLOUD VIEWS:                                              │
│   📊 sadak_stats   → total, resolved, critical counts      │
│   🗺️  state_stats  → per-state resolution percentage       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

| Feature | Detail |
|---------|--------|
| **Supabase PostgreSQL** | Free tier — 500MB cloud DB, unlimited API calls |
| **Background Sync** | Fire-and-forget threads — zero latency added to requests |
| **Full Snapshot** | One command syncs all existing data to cloud |
| **Real-Time Dashboard** | Watch complaints appear live in Supabase Table Editor |
| **Graceful Fallback** | App works 100% if cloud is down — SQLite is always primary |
| **Service Role Auth** | SHA-256 secured service key, never exposed to frontend |
| **Analytics Views** | `sadak_stats` and `state_stats` SQL views built-in |

---

### 📍 Location Intelligence

| Feature | Detail |
|---------|--------|
| **All 36 States** | Complete India — J&K to Tamil Nadu, Gujarat to Arunachal Pradesh |
| **782 Districts** | District routing with correct authority codes and helplines |
| **7,075+ Localities** | Village-level precision for rural India |
| **NH Detection** | Detects National Highways — auto-routes to NHAI with NH code |
| **Auto Deadlines** | Response deadline calculated by severity × authority type |
| **Geocoding** | GPS coordinates → responsible authority in milliseconds |

---

### 🛡️ Admin Command Centre

```
╔════════════════════════════════════════════════════════════════╗
║  🛡️  ADMIN COMMAND CENTRE                           LIVE 🟢   ║
║  ────────────────────────────────────────────────────────────║
║   📧 Email  +  🔢 4-digit PIN  ──► No citizen login needed!  ║
║                                                              ║
║  ┌── 📋 COMPLAINTS ──────────────┐ ┌── 👥 USERS ──────────┐ ║
║  │ 🗺️  Live Leaflet dark map     │ │ 📊 Total/Active/Susp  │ ║
║  │ 🔴 Color-coded severity pins  │ │ 👑 Grant/revoke admin  │ ║
║  │ ⚙️  One-click status updates   │ │ ⛔ Suspend accounts    │ ║
║  │ 📝 Resolution notes           │ │ 🗑️  Delete + wipe data  │ ║
║  │ 📄 PDF per complaint          │ │ 🔍 Search name/email   │ ║
║  │ ⬇️  CSV export                 │ └──────────────────────┘ ║
║  │ ⚡ SSE live — zero refresh     │                          ║
║  └────────────────────────────── ┘                          ║
╚════════════════════════════════════════════════════════════════╝
```

---

### 👤 Citizen Features

| Feature | Detail |
|---------|--------|
| **OTP Registration** | Gmail SMTP email OTP — verified accounts only |
| **Terms Gate** | Must accept T&C before registration form appears |
| **Forgot Password** | 6-digit reset code, 15-minute expiry, 3-step flow |
| **Road Animation** | 7 SVG vehicles (trucks, cars, bikes, auto rickshaw) on login |
| **Complaint History** | Full timeline, progress bar, authority details, helpline |
| **Edit / Withdraw** | Editable while FILED — locked once authority acknowledges |
| **PDF Download** | Official complaint letter — fpdf2 + pure Python fallback |
| **22 Languages** | Hindi, Tamil, Telugu, Kannada, Malayalam + 17 more |
| **PWA** | Installs as native app, Service Worker for offline support |
| **Dark Theme** | High contrast UI for outdoor field use in any lighting |

<br/>

---

## 🏗️ Project Architecture

```
sadak_ai/
│
├── 🚀 app.py                37KB  ── Flask core, 35+ API routes
├── 🤖 detector.py           14KB  ── YOLOv8 + 7-stage OpenCV fallback
├── ☁️  cloud_sync.py          4KB  ── Supabase background sync (NEW)
├── 🗃️  database.py            22KB  ── SQLite operations + auto-migrations
├── 🔐 auth_manager.py         6KB  ── JWT + live DB role verification
├── 📍 location_router.py    10KB  ── GPS → Authority (all 36 states)
├── 🏗️  complaint_engine.py    6KB  ── Complaint lifecycle management
├── 📄 pdf_generator.py      24KB  ── fpdf2 + pure Python fallback
├── 📧 otp_manager.py          9KB  ── Email OTP + password reset
├── 📊 road_quality.py         7KB  ── Road Quality Index 0–100
├── 🌐 language_support.py     7KB  ── 22 Indian languages
├── 🌍 location_api.py         2KB  ── States / Districts / Localities
├── 🗺️  location.db           320KB  ── 36 states, 782 districts, 7,075+ places
├── 📋 supabase_setup.sql      3KB  ── Cloud DB schema (NEW)
├── 🔧 requirements.txt             ── All dependencies
├── 🔒 .env.example                 ── Environment template (NEW)
├── 🚫 .gitignore                   ── Keeps secrets safe (NEW)
│
├── templates/
│   ├── 🔐 login.html         71KB  ── Dark UI, road animation, OTP
│   ├── 🏠 home.html          39KB  ── Dashboard, stats, RQI, SSE, PWA
│   ├── 📋 history.html       43KB  ── Complaints, timeline, edit, PDF
│   ├── 📷 scanner.html       31KB  ── Real-time AI camera scanner
│   ├── 📝 auto_report.html   24KB  ── Complaint filing with map
│   └── 🛡️  admin.html         53KB  ── Command Centre + PIN gate
│
└── static/
    ├── logo.svg              ── SADAK AI animated shield logo
    ├── manifest.json         ── PWA manifest
    └── sw.js                 ── Service Worker (offline support)
```

<br/>

---

## ⚙️ Complete Tech Stack

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer           │  Technology                                  │
├─────────────────────────────────────────────────────────────────┤
│  Backend         │  Python 3.12  +  Flask 3.0                  │
│  AI / ML         │  YOLOv8 (Ultralytics)  +  OpenCV 4.x        │
│  Primary DB      │  SQLite 3  (WAL mode, foreign keys)         │
│  Cloud DB  🆕    │  Supabase PostgreSQL  (free tier)           │
│  Cloud Sync 🆕   │  Background threads — zero latency          │
│  Auth            │  JWT (PyJWT)  +  Email OTP (Gmail SMTP)     │
│  Frontend        │  Vanilla HTML5 / CSS3 / JavaScript ES6+     │
│  Maps            │  Leaflet.js  +  CartoDB Dark tiles           │
│  PDF             │  fpdf2  +  Pure Python stdlib fallback      │
│  Real-Time       │  Server-Sent Events (SSE)                   │
│  PWA             │  Service Worker  +  Web App Manifest        │
│  Security        │  SHA-256 PIN  +  Rate limiting  +  RLS      │
│  Config 🆕       │  python-dotenv  (.env file management)      │
└─────────────────────────────────────────────────────────────────┘
```

<br/>

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/sadak-ai.git
cd sadak-ai

# 2. Install all dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials

# 4. Run the app
python app.py
```

| URL | Page |
|-----|------|
| `http://127.0.0.1:5000` | 🔐 Citizen Login / Register |
| `http://127.0.0.1:5000/home` | 🏠 Citizen Dashboard |
| `http://127.0.0.1:5000/scanner` | 📷 AI Pothole Scanner |
| `http://127.0.0.1:5000/history` | 📋 My Complaints |
| `http://127.0.0.1:5000/admin` | 🛡️ Admin Command Centre |

**Make yourself Admin**
```python
import sqlite3
conn = sqlite3.connect("sadak_ai.db")
conn.execute("UPDATE users SET role='admin' WHERE email='your@email.com'")
conn.commit(); conn.close()
```

**Sync data to Supabase cloud**
```bash
python -c "from cloud_sync import sync_full_snapshot; sync_full_snapshot()"
```

<br/>

---

## ☁️ Supabase Cloud Setup

```bash
# 1. Create free project at supabase.com
# 2. Run supabase_setup.sql in SQL Editor
# 3. Get your service_role key from Settings → API
# 4. Add to .env file:

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# 5. Sync all existing data
python -c "from cloud_sync import sync_full_snapshot; sync_full_snapshot()"
```

**View live data in Supabase Dashboard:**

| View | Location |
|------|----------|
| 👥 All users | Table Editor → users |
| 📋 All complaints | Table Editor → complaints |
| 📊 Global stats | Table Editor → Views → sadak_stats |
| 🗺️ Per-state stats | Table Editor → Views → state_stats |
| 🔴 Real-time feed | Table Editor → Realtime ON |

<br/>

---

## 🔐 Security

```
✅  JWT — 30-day sessions with role-aware tokens
✅  Live DB role check — stale tokens cannot access admin
✅  SHA-256 hashed admin PINs with secret application salt
✅  5-attempt PIN lockout
✅  Email OTP for every new registration
✅  Rate limiting on all sensitive endpoints
✅  Input sanitization — XSS prevention
✅  Audit log — every admin action with timestamp + IP
✅  File upload validation — MIME type + size enforced
✅  Supabase Row Level Security (RLS) on cloud tables
✅  .env file — secrets never hardcoded or committed
✅  .gitignore — sadak_ai.db and .env excluded from git
```

<br/>

---

## 📡 API Reference

<details>
<summary><b>🔐 Authentication — 7 endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/send-otp` | Send email OTP |
| `POST` | `/api/auth/register` | Register with OTP |
| `POST` | `/api/auth/login` | Citizen login → JWT |
| `GET` | `/api/auth/me` | Profile + stats |
| `GET` | `/api/auth/verify` | Verify JWT (live DB role) |
| `POST` | `/api/auth/forgot-password` | Send reset OTP |
| `POST` | `/api/auth/reset-password` | Reset with OTP |

</details>

<details>
<summary><b>📋 Complaints — 7 endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/report/pothole` | File complaint with AI + GPS |
| `GET` | `/api/complaints` | List (filtered by role) |
| `GET` | `/api/complaints/<id>` | Single + full timeline |
| `PUT` | `/api/complaints/<id>/status` | Update status *(admin)* |
| `POST` | `/api/complaints/<id>/edit` | Edit description *(FILED)* |
| `POST` | `/api/complaints/<id>/withdraw` | Withdraw *(FILED)* |
| `GET` | `/api/complaints/<id>/pdf` | Download official PDF |

</details>

<details>
<summary><b>🛡️ Admin — 9 endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/admin/login` | Direct admin login (email + PIN) |
| `GET` | `/api/admin/check-email` | Verify admin email |
| `GET` | `/api/admin/has-pin` | PIN configured? |
| `POST` | `/api/admin/verify-pin` | Verify PIN |
| `POST` | `/api/admin/set-pin` | Set / change PIN |
| `GET` | `/api/admin/users` | All users with stats |
| `POST` | `/api/admin/users/<id>/delete` | Delete user + data |
| `POST` | `/api/admin/users/<id>/toggle` | Suspend / reactivate |
| `POST` | `/api/admin/users/<id>/make-admin` | Grant / revoke admin |

</details>

<details>
<summary><b>📍 Location + AI + Live — 8 endpoints</b></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/location/states` | All 36 states |
| `GET` | `/api/location/districts` | Districts by state |
| `GET` | `/api/location/localities` | Villages and localities |
| `GET` | `/api/geocode` | GPS → authority |
| `POST` | `/api/detect-frame` | Real-time AI detection |
| `GET` | `/api/road-quality` | Road Quality Index |
| `GET` | `/api/stats` | Statistics |
| `GET` | `/api/stream` | SSE live stream |

</details>

<br/>

---

## 🛣️ Development Journey

> *100+ iterations. Every feature engineered, broken, debugged, and polished.*

```
Phase 1 ── Foundation
          Flask architecture · SQLite schema · JWT auth
          Gmail OTP · Location DB (36 states, 782 districts)

Phase 2 ── AI Core
          YOLOv8 integration · 7-stage OpenCV fallback
          Real-time scanner · GPS → Authority routing
          Severity scoring · Road Quality Index (0–100)

Phase 3 ── Citizen App
          Login: dark theme + road animation + 7 SVG vehicles
          OTP registration · Terms gate · Forgot password
          Dashboard · Scanner · Complaint filing with map
          History: timeline · edit · withdraw · PDF download

Phase 4 ── Admin Command Centre
          Direct admin login (email + PIN — no citizen session)
          PIN gate: SHA-256 · 5-attempt lockout · first-time setup
          Live Leaflet map · Status management · User management
          SSE live updates · CSV export · PDF per complaint

Phase 5 ── Production Hardening
          Live DB role checking · Pure Python PDF fallback
          Rate limiting · Audit logging · Security headers
          22 Indian languages · PWA · Offline Service Worker
          AI precision: 0.55+ conf · size filter · aspect ratio

Phase 6 ── Cloud Integration 🆕
          Supabase PostgreSQL cloud database
          Background sync engine (zero latency)
          Full snapshot migration command
          sadak_stats + state_stats analytics views
          Row Level Security · .env secrets management
          .gitignore · requirements.txt finalized
```

---

## 💪 By The Numbers

<div align="center">

| | |
|:--|--:|
| 🐍 Python backend files | **14** |
| 🎨 Frontend HTML pages | **6** |
| 🔌 API endpoints | **35+** |
| 🗃️ Database functions | **27+** |
| ☁️ Cloud sync events | **5** |
| 🌍 States covered | **36 / 36** |
| 🏘️ Districts mapped | **782** |
| 🗺️ Localities in DB | **7,075+** |
| 🌐 Languages | **22** |
| 📝 Lines of code | **8,500+** |
| 🐛 Bugs hunted & fixed | **55+** |
| 🔄 Build iterations | **100+** |
| ☕ Late night sessions | **Countless** |

</div>

<br/>

---

## 🌟 What Makes SADAK AI Different

```
🇮🇳  Built for Indian roads, governance & infrastructure — not generic
🤖  Real computer vision AI — not a form with dropdowns
📍  GPS routes to the EXACT responsible authority
⚡  Real-time SSE — admin sees complaints as citizens file them
☁️  Supabase cloud sync — data safe, accessible anywhere   🆕
🔒  Govt-grade security: OTP + JWT + PIN + RLS + audit log
📱  PWA — installs as native app on Android and iOS
🌐  22 languages — accessible to every Indian
📄  Legally formatted PDF complaint letters, auto-generated
🌙  Dark UI for outdoor field use in any lighting
♾️   Multiple fallbacks — AI, PDF, auth, cloud all fail-safe
🛡️  Admin completely separated — different login flow
📊  sadak_stats view — live analytics in cloud dashboard  🆕
```

<br/>

---

<div align="center">

## Built with 🧡 for India's 1.4 Billion People

**Developed by Darshan Paapani** — making Indian roads safer, one complaint at a time.

*Every bug fixed, every iteration, every late night that went into this
project was worth it — because roads save lives.*

<br/>

> *"Roads are the veins of a nation.*
> *SADAK AI is the heartbeat that keeps them healthy."*

<br/>

---

**⭐ Star this repo if it inspires you · 🍴 Fork it · 🛠️ Build on it**

**🇮🇳 Jai Hind. Safer roads for everyone.**

---

*SADAK AI v3.0 · National Road Intelligence System*
*Inspired by the Ministry of Road Transport & Highways · Government of India*

</div>   
