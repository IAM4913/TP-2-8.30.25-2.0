# 📘 Truck Planner - Technical Overview for New Developers

*Welcome to the team! This document will get you up to speed on the Truck Planner application architecture, codebase, and key systems.*

---

## 🎯 What This Application Does

**Truck Planner** is a logistics optimization platform that helps schedule and route delivery trucks efficiently. It:

1. **Ingests** Excel files with customer orders (pieces, weights, destinations, due dates)
2. **Optimizes** truck loading based on weight limits, priorities, and geographic routing
3. **Generates** optimized delivery routes using professional VRP (Vehicle Routing Problem) algorithms
4. **Exports** results to Excel for logistics coordinators

**Business Value**: Reduces truck count, balances loads, ensures on-time deliveries, and optimizes driver routes.

---

## 🏗️ Architecture Overview

This is a **3-tier web application**:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT TIER                              │
│  React 18 + TypeScript + Tailwind CSS + Leaflet Maps        │
│              Running on Vite Dev Server                      │
│                    Port: 3001                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST (axios)
                       │ Proxied via /api → :8010
┌──────────────────────▼──────────────────────────────────────┐
│                    APPLICATION TIER                          │
│  FastAPI + Pandas + OR-Tools + Pydantic                     │
│              Running on Uvicorn                              │
│                    Port: 8010                                │
└──────────────────────┬──────────────────────────────────────┘
                       │ psycopg3
                       │ PostgreSQL Protocol
┌──────────────────────▼──────────────────────────────────────┐
│                     DATA TIER                                │
│               Supabase (PostgreSQL)                          │
│  Tables: address_cache, distance_cache, depot_config        │
│              Optional - for caching only                     │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

| Decision | Why | Trade-offs |
|----------|-----|------------|
| **FastAPI** (not Flask/Django) | Auto-generated API docs, async support, type validation | Newer, smaller ecosystem |
| **Pandas** (not SQL) | Excel files are the primary data source | Memory-intensive for huge datasets |
| **OR-Tools VRP** (not custom) | Industrial-grade routing algorithms | Black-box optimization, less control |
| **Supabase** (not raw PostgreSQL) | Managed hosting, built-in auth/storage | Vendor lock-in |
| **Vite** (not Create React App) | 10x faster builds, modern ESM | Less documentation for React |
| **Tailwind CSS** (not Material UI) | Utility-first, smaller bundle size | Verbose HTML classes |

---

## 📂 Project Structure

```
Truck Planner 2 8.30.25/
│
├── backend/                          # Python FastAPI application
│   ├── app/
│   │   ├── main.py                   # 🔥 API endpoints (2000+ lines)
│   │   ├── schemas.py                # Pydantic models for validation
│   │   ├── excel_utils.py            # Excel parsing and field calculations
│   │   ├── optimizer_simple.py       # 🧠 Core truck grouping algorithm
│   │   ├── optimizer.py              # Alternative optimizer (not used)
│   │   ├── vrp_solver.py             # 🚀 OR-Tools VRP integration
│   │   ├── geocode_service.py        # 🌍 Google Geocoding API wrapper
│   │   ├── distance_service.py       # 📏 Distance/duration calculations
│   │   └── route_optimizer.py        # [DEPRECATED] Old routing logic
│   ├── requirements.txt              # Python dependencies
│   ├── run_dev.ps1                   # Start script (Windows)
│   ├── env.template                  # Environment variable template
│   └── OR_TOOLS_MIGRATION.md         # OR-Tools migration notes
│
├── frontend/                         # React TypeScript application
│   ├── src/
│   │   ├── main.tsx                  # App entry point
│   │   ├── App.tsx                   # 🔥 Main routing component
│   │   ├── api.ts                    # 🔌 Backend API client
│   │   ├── types.ts                  # TypeScript interfaces
│   │   ├── index.css                 # Tailwind imports
│   │   └── components/
│   │       ├── Dashboard.tsx         # File upload & optimization UI
│   │       ├── TruckResults.tsx      # Results table
│   │       ├── RouteManagement.tsx   # Truck combination UI
│   │       ├── RoutingPhase1.tsx     # 🗺️ Geocoding & routing UI
│   │       ├── RouteMap.tsx          # Leaflet map visualization
│   │       ├── FileUpload.tsx        # Drag & drop component
│   │       ├── AddressValidation.tsx # [UNUSED]
│   │       └── RouteSetup.tsx        # [UNUSED]
│   ├── package.json                  # Node.js dependencies
│   ├── vite.config.ts                # Vite configuration (proxy setup)
│   ├── tailwind.config.js            # Tailwind CSS configuration
│   └── run_dev.ps1                   # Start script (Windows)
│
├── docs/                             # Product requirements & specs
│   ├── truck-routing-logic.md        # 📖 Detailed business rules
│   ├── truck-planner-prd.md          # Product requirements
│   └── ROUTING_PHASE1_TODO.md        # Phase 1 tasks
│
├── DEVELOPMENT_STATUS.md             # 📍 Current dev status snapshot
├── README.md                         # Setup instructions
└── UPDATE.md                         # Recent changes log
```

---

## 🔧 Technology Stack

### Backend

| Library | Version | Purpose |
|---------|---------|---------|
| **FastAPI** | 0.115.0 | REST API framework |
| **Uvicorn** | 0.30.6 | ASGI server |
| **Pandas** | 2.2.2 | Excel data manipulation |
| **Pydantic** | 2.8.2 | Data validation & serialization |
| **OR-Tools** | 9.10+ | Vehicle routing optimization |
| **psycopg3** | 3.2.9 | PostgreSQL database adapter |
| **requests** | 2.32.3 | HTTP client (Google Maps API) |
| **openpyxl** | 3.1.5 | Excel file reading/writing |
| **python-dotenv** | 1.0.1 | Environment variable management |

### Frontend

| Library | Version | Purpose |
|---------|---------|---------|
| **React** | 18.2.0 | UI framework |
| **TypeScript** | 5.5.4 | Type safety |
| **Vite** | 5.4.2 | Build tool & dev server |
| **Axios** | 1.5.0 | HTTP client |
| **React Router** | 6.15.0 | Client-side routing |
| **Tailwind CSS** | 3.3.3 | Utility-first CSS |
| **Leaflet** | 1.9.4 | Interactive maps |
| **react-leaflet** | 4.2.1 | React bindings for Leaflet |
| **lucide-react** | 0.263.1 | Icon library |
| **react-dropzone** | 14.2.3 | File upload UI |

### External Services

- **Supabase**: PostgreSQL database (optional, for caching)
- **Google Maps API**: Geocoding & Distance Matrix API

---

## 🔥 Critical Components ("The Engines")

### 1. **Truck Grouping Engine** (`optimizer_simple.py`)

**What it does**: Groups customer order lines into trucks based on weight, priority, and business rules.

**Key function**: `naive_grouping(df, weight_config) → (trucks_df, assigns_df)`

**Business Rules**:
- ✅ One customer per truck (no multi-stop by default)
- ✅ Weight limits: TX=52k lbs, Other=48k lbs
- ✅ Priority: Late orders ship first
- ✅ Line splitting: Partial shipments if weight exceeds truck capacity
- ✅ Cross-bucket filling: Moves items between trucks to meet minimums

**Input**: Pandas DataFrame with order lines  
**Output**: Two DataFrames (truck summaries + line assignments)

---

### 2. **VRP Route Optimizer** (`vrp_solver.py`)

**What it does**: Calculates optimal stop sequences for delivery routes using Google OR-Tools.

**Key function**: `solve_vrp(stops, depot_lat/lng, distance_matrix, ...) → List[Route]`

**Constraints**:
- ✅ Max weight per truck (52,000 lbs default)
- ✅ Max drive time per truck (12 hours default)
- ✅ Service time per stop (30 min default)
- ✅ Node dropping with high penalty (impossible locations)

**Algorithm**: Guided Local Search with 30-second time limit

**Input**: Geocoded stops + distance/duration matrices  
**Output**: Optimized routes with stop sequences

---

### 3. **Geocoding Service** (`geocode_service.py`)

**What it does**: Converts addresses to lat/lng coordinates using Google Geocoding API.

**Key functions**:
- `google_geocode_query(address, api_key)` - API call
- `cache_lookup_address(dsn, normalized)` - Database cache check
- `cache_upsert_address(...)` - Save to cache

**Caching Strategy**:
- **Table**: `address_cache` (Supabase)
- **Key**: Normalized address string (lowercase, trimmed)
- **Benefit**: Avoid repeat API calls (saves $$)

**Performance**: Now uses **batch queries** (100x faster than individual lookups)

---

### 4. **Distance Matrix Service** (`distance_service.py` + `main.py`)

**What it does**: Calculates driving distances and durations between all address pairs.

**Sources**:
1. **Google Distance Matrix API** (accurate, costs $)
2. **Haversine formula** (free fallback for huge datasets)

**Caching Strategy**:
- **Table**: `distance_cache` (Supabase)
- **Key**: `(origin_lat_lng, dest_lat_lng, provider)`
- **Optimization**: Batch lookups, batch writes, intelligent fallback

**Performance Logic**:
```python
if n > 100 addresses:
    use haversine_matrix() + cache results
else:
    use google_distance_matrix() for cache misses
```

---

### 5. **Excel Processing Pipeline** (`excel_utils.py`)

**What it does**: Parses uploaded Excel files and computes derived fields.

**Key functions**:
- `compute_calculated_fields(df)` - Adds `Weight Per Piece`, `Is Late`, `Is Overwidth`, etc.
- `build_priority_bucket(row)` - Assigns Late/NearDue/WithinWindow
- `extract_unique_addresses(df)` - Gets distinct city/state/zip combinations
- `filter_by_planning_whse(df, allowed_values)` - Filters by warehouse

**Critical Derived Fields**:
- `Weight Per Piece = Ready Weight / RPcs`
- `Is Late = Latest Due < today()`
- `Days Until Late = (Latest Due - today).days`
- `priorityBucket` = Late | NearDue | WithinWindow

---

## 🔌 API Endpoints

### Optimization APIs

| Method | Endpoint | Purpose | Key Parameters |
|--------|----------|---------|----------------|
| POST | `/optimize` | Run truck grouping optimization | `file`, `planningWhse` |
| POST | `/route/optimize-phase2` | Run VRP route optimization | `file`, `maxWeightPerTruck`, `maxTrucks`, `maxDriveTimeMinutes` |
| POST | `/route/plan` | Phase 1 routing (simple grouping) | `file`, `deliveryDate`, `truckHours` |
| POST | `/combine-trucks` | Manually combine truck lines | `file`, `request{lineIds}` |

### Geocoding & Mapping APIs

| Method | Endpoint | Purpose | Key Parameters |
|--------|----------|---------|----------------|
| POST | `/geocode/validate` | Geocode addresses from file | `file`, `planningWhse` |
| POST | `/distance-matrix` | Calculate distance/duration matrix | `origins`, `destinations` (pipe-separated lat,lng) |
| GET | `/depot/location` | Get depot coordinates | - |
| PUT | `/depot/location` | Set depot coordinates | `name`, `address`, `latitude`, `longitude` |

### Export APIs

| Method | Endpoint | Purpose | Key Parameters |
|--------|----------|---------|----------------|
| POST | `/export/trucks` | Download optimized trucks as Excel | `file`, `planningWhse` |
| POST | `/export/dh-load-list` | Export DH Load List format | `file`, `plannedDeliveryCol` |

### Configuration APIs

| Method | Endpoint | Purpose | Key Parameters |
|--------|----------|---------|----------------|
| GET | `/health` | Health check | - |
| POST | `/upload/preview` | Preview Excel data | `file` |
| GET | `/no-multi-stop-customers` | Get restricted customer list | - |
| POST | `/no-multi-stop-customers` | Update restricted customers | `customers[]` |

**API Documentation**: Auto-generated at `http://localhost:8010/docs` (Swagger UI)

---

## 💾 Database Schema (Supabase)

### Tables

#### `address_cache`
```sql
CREATE TABLE address_cache (
    id SERIAL PRIMARY KEY,
    normalized TEXT UNIQUE NOT NULL,  -- "123 main st,dallas,tx,75001,usa"
    street TEXT,
    suite TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    latitude FLOAT,
    longitude FLOAT,
    confidence FLOAT,            -- 0.0-1.0 quality score
    provider TEXT,                -- "google" | "manual"
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `distance_cache`
```sql
CREATE TABLE distance_cache (
    id SERIAL PRIMARY KEY,
    origin_normalized TEXT NOT NULL,     -- "32.7955,-97.2814"
    dest_normalized TEXT NOT NULL,       -- "32.8013,-96.7697"
    provider TEXT NOT NULL,              -- "google" | "haversine"
    distance_miles FLOAT,
    duration_minutes FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(origin_normalized, dest_normalized, provider)
);
```

#### `depot_config`
```sql
CREATE TABLE depot_config (
    id INTEGER PRIMARY KEY,
    name TEXT,
    address TEXT,
    latitude FLOAT,
    longitude FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Note**: Database is **optional** - app works without it (no caching, but functional).

---

## 🎨 Frontend Architecture

### Routing Structure

```typescript
// App.tsx - React Router v6
<Route path="/" element={<Dashboard />} />           // Main optimization page
<Route path="/results" element={<TruckResults />} /> // Results table
<Route path="/routes" element={<RouteManagement />} /> // Manual truck combining
<Route path="/routing-phase1" element={<RoutingPhase1 />} /> // Geocoding & VRP
```

### State Management

**No Redux/Zustand** - Uses React component state + prop drilling.

**Data Flow**:
1. User uploads file in `Dashboard.tsx`
2. Call `api.optimizeRoutes(file)` → backend
3. Backend returns `{trucks: [], assignments: []}`
4. Store in component state
5. Pass to `TruckResults.tsx` via props

**File Upload Flow**:
```
FileUpload.tsx
  ↓ (drag & drop)
Dashboard.tsx
  ↓ (FormData)
api.ts → axios.post('/api/optimize')
  ↓ (HTTP)
Backend main.py → /optimize endpoint
  ↓ (Pandas + optimizer_simple.py)
Response {trucks, assignments, sections}
```

### Map Integration (Leaflet)

**Component**: `RouteMap.tsx`

**Features**:
- Interactive map with zoom/pan
- Depot marker (red pin)
- Stop markers (blue pins with numbers)
- Route polylines (colored by truck)
- Stop popups with address/weight details

**Tile Provider**: OpenStreetMap (free, no API key needed)

---

## 🔐 Environment Variables

Create `backend/.env` from `backend/env.template`:

```bash
# Required for geocoding & routing
GOOGLE_MAPS_API_KEY=your_api_key_here

# Optional - for caching (leave blank to run without database)
SUPABASE_DB_URL=postgresql://user:pass@host:5432/postgres

# OR individual params:
# SUPABASE_DB_HOST=db.xxx.supabase.co
# SUPABASE_DB_USER=postgres
# SUPABASE_DB_PASSWORD=your_password
# SUPABASE_DB_NAME=postgres
# SUPABASE_DB_PORT=5432
```

**Fallback Behavior**: If no database URL, app runs in **memory-only mode** (no caching).

---

## 🚀 Development Workflow

### 1. Local Setup

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
copy env.template .env        # Create .env and add your API keys

# Frontend
cd frontend
npm install
```

### 2. Running Dev Servers

```bash
# Terminal 1 - Backend (port 8010)
cd backend
.\run_dev.ps1                # Windows
# OR manually:
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload

# Terminal 2 - Frontend (port 3001)
cd frontend
npm run dev
```

### 3. Accessing the App

- **Frontend**: http://localhost:3001
- **Backend API Docs**: http://localhost:8010/docs
- **Health Check**: http://localhost:8010/health

### 4. Typical Development Flow

1. Make changes to backend (`app/*.py`)
2. Uvicorn auto-reloads (watch console)
3. Make changes to frontend (`src/*.tsx`)
4. Vite hot-reloads (instant in browser)
5. Test via UI or Swagger docs
6. Commit changes

---

## 📚 Important Business Rules

### Weight Constraints

```python
# optimizer_simple.py
WEIGHT_CONFIG = {
    "texas_max_lbs": 52000,
    "texas_min_lbs": 47000,
    "other_max_lbs": 48000,
    "other_min_lbs": 44000,
}
```

### Priority Buckets

| Bucket | Condition | Behavior |
|--------|-----------|----------|
| **Late** | `Latest Due < today()` | Ship immediately, highest priority |
| **NearDue** | `0 <= days_until_late <= 3` | Ship soon, medium priority |
| **WithinWindow** | `days_until_late > 3` | Ship normally, low priority |

### No-Multi-Stop Customers

**Hardcoded list** (in `main.py`):
```python
NO_MULTI_STOP_CUSTOMERS = [
    "84 LUMBER",
    "HOME DEPOT",
    # ... (can be managed via API)
]
```

**Rule**: These customers must be alone on their truck (no other customers).

### Line Splitting

If a line's weight exceeds truck capacity:
```python
if needed_weight > available_capacity:
    take_pieces = int(available_capacity / weight_per_piece)
    # Ship partial, remainder stays in queue
```

**Example**: 1000-piece order, 600 lbs each, 52k truck limit:
- Truck 1: Ships 86 pieces (51,600 lbs)
- Remainder: 914 pieces go on next truck

---

## 🛠️ Where to Start

### For Frontend Developers

**Start Here**:
1. Read `frontend/src/App.tsx` - understand routing structure
2. Read `frontend/src/api.ts` - see all backend calls
3. Read `frontend/src/types.ts` - learn data models
4. Pick a component: `Dashboard.tsx` or `RoutingPhase1.tsx`

**Common Tasks**:
- Add a new UI component → `src/components/YourComponent.tsx`
- Add a new API call → update `api.ts` + `types.ts`
- Style changes → Tailwind classes in components
- Map changes → `RouteMap.tsx` (Leaflet)

### For Backend Developers

**Start Here**:
1. Read `backend/app/main.py` (lines 1-100) - understand FastAPI setup
2. Read `docs/truck-routing-logic.md` - understand business rules
3. Read `backend/app/optimizer_simple.py` - understand grouping logic
4. Read `backend/app/vrp_solver.py` - understand routing logic

**Common Tasks**:
- Add a new endpoint → `main.py` + `schemas.py`
- Modify optimization logic → `optimizer_simple.py`
- Add caching → update `geocode_service.py` or `distance_service.py`
- Change business rules → `excel_utils.py` or `optimizer_simple.py`

### For Full-Stack Developers

**Start Here**:
1. Run both servers locally
2. Upload a test Excel file (`Input Truck Planner.xlsx`)
3. Step through the entire flow with browser DevTools + backend logs
4. Read `DEVELOPMENT_STATUS.md` - understand current state

---

## 🐛 Debugging Tips

### Backend Debugging

```bash
# Enable verbose logging
uvicorn app.main:app --log-level debug

# Check database connection
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('SUPABASE_DB_URL'))"

# Test OR-Tools import
python -c "from ortools.constraint_solver import routing_enums_pb2; print('OR-Tools OK')"
```

### Frontend Debugging

```bash
# Check proxy configuration
cat frontend/vite.config.ts

# Test backend connection
curl http://localhost:8010/health

# Check for port conflicts
netstat -ano | findstr :3001
netstat -ano | findstr :8010
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| "localhost refused to connect" | Frontend server not running | `cd frontend && npm run dev` |
| "Network Error" | Backend not running | `cd backend && .\run_dev.ps1` |
| "CORS error" | Proxy misconfigured | Check `vite.config.ts` proxy settings |
| "ModuleNotFoundError: ortools" | OR-Tools not installed | `pip install ortools` |
| "Geocoding failed" | Missing Google API key | Add `GOOGLE_MAPS_API_KEY` to `.env` |

---

## 📖 Additional Resources

### Documentation

- `README.md` - Setup instructions
- `DEVELOPMENT_STATUS.md` - Current development state
- `docs/truck-routing-logic.md` - Detailed business logic
- `backend/OR_TOOLS_MIGRATION.md` - OR-Tools integration notes
- `docs/truck-planner-prd.md` - Product requirements

### External Docs

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [OR-Tools VRP Guide](https://developers.google.com/optimization/routing)
- [Leaflet Documentation](https://leafletjs.com/)
- [Tailwind CSS](https://tailwindcss.com/docs)

---

## 🎓 Learning Path for New Hires

### Week 1: Setup & Orientation
- ✅ Get local environment running
- ✅ Upload a test file and see results
- ✅ Read this document + PRD
- ✅ Step through code in debugger

### Week 2: First Contribution
- ✅ Pick a small bug or feature from backlog
- ✅ Make changes to frontend OR backend
- ✅ Test locally
- ✅ Submit PR with tests

### Week 3: Deep Dive
- ✅ Understand `optimizer_simple.py` line-by-line
- ✅ Understand `vrp_solver.py` VRP constraints
- ✅ Read Google OR-Tools documentation
- ✅ Propose one optimization improvement

### Week 4: Ownership
- ✅ Own a feature end-to-end (frontend + backend)
- ✅ Write tests
- ✅ Update documentation
- ✅ Present to team

---

## 🤝 Code Conventions

### Python (Backend)

- **Style**: PEP 8 (mostly enforced by formatter)
- **Type Hints**: Use Pydantic models for API schemas
- **Docstrings**: Use for public functions
- **Error Handling**: Raise `HTTPException` with descriptive messages

```python
# Good
def geocode_addresses(df: pd.DataFrame, api_key: str) -> List[Dict[str, Any]]:
    """Geocode unique addresses from DataFrame.
    
    Args:
        df: DataFrame with address columns
        api_key: Google Maps API key
        
    Returns:
        List of geocoded address dicts with lat/lng
    """
    ...
```

### TypeScript (Frontend)

- **Style**: ESLint config in `frontend/.eslintrc.js`
- **Types**: Prefer interfaces over types
- **Components**: Use functional components + hooks
- **Props**: Destructure in function params

```typescript
// Good
interface TruckCardProps {
    truck: TruckSummary;
    onClick: (id: number) => void;
}

export const TruckCard: React.FC<TruckCardProps> = ({ truck, onClick }) => {
    ...
};
```

---

## ❓ FAQ for New Devs

**Q: Why are there two optimizer files?**  
A: `optimizer_simple.py` is the current production optimizer. `optimizer.py` is an older/alternative version kept for reference. Use `optimizer_simple.py`.

**Q: Why is `route_optimizer.py` still in the codebase?**  
A: It's deprecated (replaced by `vrp_solver.py` with OR-Tools). Kept for historical reference but not used.

**Q: Do I need a Supabase account to develop?**  
A: No! The app works without a database (just no caching). For production, you'll want caching to save API costs.

**Q: How do I get a Google Maps API key?**  
A: Ask your team lead. It's a paid service (~$5-20/day depending on usage).

**Q: Why is the frontend on port 3001 not 3000?**  
A: To avoid conflicts with other common dev servers. Configurable in `vite.config.ts`.

**Q: Can I use Python 3.12?**  
A: Yes, but 3.10-3.11 recommended. Some libraries (OR-Tools) may lag on newest Python versions.

**Q: Where are tests?**  
A: There are no automated tests yet 😅. This is a great first contribution! Add `tests/` directories.

---

## 🚀 Next Steps

1. **Clone the repo** (if you haven't already)
2. **Run both servers** and test the UI
3. **Pick a ticket** from the backlog (ask your manager)
4. **Join the team chat** for questions
5. **Update this doc** if you find anything confusing!

---

**Welcome to the team! 🎉**

*Last Updated: October 13, 2025*  
*Document Maintainer: Founding Team*

