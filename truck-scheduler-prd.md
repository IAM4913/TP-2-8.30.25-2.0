# Product Requirements Document
## Truck Scheduling & Optimization Software

Version: 1.0
Date: August 31, 2025
Status: MVP (in use)

---

## 1. Executive Summary

### 1.1 Purpose
This document captures the current behavior of the Truck Planner MVP. The system groups orders based on zone/route (when provided), customer, destination, weight constraints, and delivery windows. It maximizes utilization, prioritizes late shipments, and supports manual combination of underweight trucks.

### 1.2 Scope
The software handles Excel import and preview, automatic optimization, manual combination of lines across trucks (with guardrails), and Excel export of optimized results.

### 1.3 Key Benefits
- Automated optimization of truck loads based on multiple constraints
- Prioritization of late orders to minimize delivery delays
- Maximization of truck utilization to reduce transportation costs
- Clear visibility into load composition and delivery status
- Manual adjustability with safe guardrails

---

## 2. Functional Requirements (Current)

### 2.1 Data Import Module

#### 2.1.1 File Import Capability
- Supported Format: Excel (.xlsx)
- Import Method: Drag-and-drop file upload
- Validation: Validates file extension, reads with openpyxl, filters by Planning Warehouse, returns preview (headers, rowCount, missing required columns, sample)

#### 2.1.2 Required Columns
The backend expects these columns (exact names):
- SO (Sales Order Number)
- Line (Line Number)
- Customer (Customer Name)
- shipping_city (Shipping City)
- shipping_state (Shipping State)
- Ready Weight (lbs)
- RPcs (Ready Pieces)
- Grd (Material Grade)
- Size (Material Thickness)
- Width (Material Width, inches)
- Earliest Due (Earliest Ship Date)
- Latest Due (Latest Ship Date)

Optional grouping columns (header detection is case-insensitive and tolerant to variants):
- Zone
- Route

Planning Warehouse filter:
- Rows are filtered to Planning Whse values in {"ZAC"}. Column detection is robust to variants like "Planning Whse", "Planning Warehouse". If not found, no filtering is applied.

#### 2.1.3 Calculated Fields (Backend)
- Weight Per Piece = Ready Weight / RPcs
- Is Late = Latest Due < today
- Days Until Late = Latest Due - today
- Is Overwidth = Width > 96
- Priority Bucket = Late | NearDue (<= 3 days) | WithinWindow

### 2.2 Optimization Engine

#### 2.2.1 Grouping Logic (Implemented)
- Customer isolation within grouped context (no mixing customers per truck)
- Location consistency: group by shipping_city + shipping_state
- Zone/Route awareness: if present, group by Zone → Route → Customer → State → City
- Line splitting by pieces to respect weight limits (derive weight per piece; split if needed)
- Sort order: priority bucket, then Zone, Route (if present), then Customer, State, City

#### 2.2.2 Weight Constraints
- Texas: max 52,000 lbs; min 47,000 lbs
- Other states: max 48,000 lbs; min 44,000 lbs
- UI supports editing; backend currently uses defaults (UI-to-backend wiring planned)

#### 2.2.3 Load Indicators (UI)
- Utilization color coding
- Late badge on trucks containing late items
- Percent overwidth metric

### 2.3 User Interface

#### 2.3.1 Upload & Preview
- Drag-and-drop upload
- Shows headers, row count, required column coverage, and sample rows
- Indicates readiness and lists missing required columns

#### 2.3.2 Dashboard
- Weight configuration inputs (Texas/Other min/max, step=1,000)
- Optimize button triggers backend optimization (uses default limits currently)
- Error handling and feedback during optimization

#### 2.3.3 Results
- Sections by priority bucket: Late, NearDue, WithinWindow (others shown if present)
- Truck cards show: number, customer, address, city/state, total/min/max weight, orders, lines, pieces, max width, % overwidth, contains late
- Drill into a truck to view its order assignments
- Export to Excel (two sheets: Truck Summary, Order Details)

#### 2.3.4 Route Management (Manual Combination)
- Groups trucks by Route → Zone → Customer; excludes high-utilization trucks (>94%) for focus on underweight
- Select individual lines or entire trucks to combine
- UI validations: same state, combined weight <= state max; if Zone/Route present, must match
- On combine, creates a new truck, reassigns selected lines, and returns updated assignments and removed truck IDs (if emptied)

---

## 3. Non-Functional (MVP)

### 3.1 Performance Targets
- Import preview for typical files under several seconds
- Optimization completes quickly for small-to-medium datasets (heuristic)

### 3.2 Usability
- Modern, responsive UI (Tailwind CSS)
- Clear error states for upload/optimization/export

### 3.3 Data
- No persistence; operations are stateless per request
- No authentication in MVP (local/dev use)

### 3.4 Integration Notes
- REST API consumed by the frontend
- File upload via multipart/form-data

---

## 4. Business Rules (Implemented)
1. Never exceed weight limits
2. Do not mix customers within a truck
3. Group by city/state; prefer same Zone/Route when provided
4. Prioritize Late, then NearDue, then WithinWindow
5. Allow line splitting by pieces to reach target weights

---

## 5. API (Current)
Base URL (dev): /api

- GET /health
  - Returns { status: "ok" }

- POST /upload/preview (multipart/form-data)
  - Body: file (.xlsx)
  - Response: { headers: string[], rowCount: number, missingRequiredColumns: string[], sample: object[] }

- POST /optimize (multipart/form-data)
  - Body: file (.xlsx)
  - Response: OptimizeResponse { trucks[], assignments[], sections{ bucket: number[] } }

- POST /export/trucks (multipart/form-data)
  - Body: file (.xlsx)
  - Response: Excel blob with sheets: Truck Summary, Order Details

- GET /no-multi-stop-customers
  - Response: { customers: string[] }

- POST /no-multi-stop-customers
  - Body: JSON array of customer names; updates in-memory list

- POST /combine-trucks (multipart/form-data)
  - Body: file (.xlsx), request (JSON string): { truckIds: number[], lineIds: string[], weightConfig }
  - Validations: same state; weight <= state max; if Zone/Route present, Zone and Route must match
  - Response: { success, message, newTruck, updatedAssignments[], removedTruckIds[] }

---

## 6. Technical Architecture (Current)
- Frontend: React 18 + TypeScript, Vite, Tailwind, Axios, Lucide
- Backend: FastAPI, Pandas, Pydantic, Uvicorn
- Optimization: Custom heuristic (naive grouping + piece split)
- Files: Excel via openpyxl
- Dev: run_dev.ps1 scripts for backend/frontend

Known limitations:
- UI weight config not yet passed to backend
- No persistence for no-multi-stop list
- Export is full-results only; no per-truck/batch endpoints yet
- No auth/roles

---

## 7. Future Enhancements
- Wire weight config from UI to backend requests
- Per-truck/batch export endpoints
- Persist and manage no-multi-stop customers
- Advanced routing (distance/time), GPS/telematics
- Formal load grading and alerts
- Database for audit/history; authentication/authorization
- Containerization and CI/CD pipeline

---

## 8. Appendices
- Glossary: SO, Overwidth (>96"), Utilization (totalWeight/maxWeight)
- Sample Input: see Input Truck Planner.xlsx
- Export Format: Truck Summary + Order Details sheets