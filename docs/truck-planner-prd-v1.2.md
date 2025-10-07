# Product Requirements Document (PRD) — Truck Planner (v1.2)

Version: 1.2
Date: 2025-09-21
Status: Live; incremental improvements since v1.1 (Plan Loads CSV, multi-truck select, trttav_no, truck date ranges, analytics).

## 1. Executive summary
Optimize daily truck planning from Excel by grouping orders into loads under weight/date constraints, supporting manual adjustments, and exporting planning outputs (Truck Results, DH Load List, and Plan Loads CSV).

## 2. Scope (v1.2 delta)
- Plan Loads CSV from user-selected lines across multiple trucks.
- Multi-truck selection with per-truck "Plan all (x/y)" and global "Select none".
- CSV filename includes date and unique truck count.
- Propagate trttav_no (source column used as DH “D” column) into API and CSV.
- Truck summary cards show Earliest and Latest due date ranges.
- Vercel Analytics wired for page views.
- Frontend API timeout (45s) to avoid stuck spinners.

Out-of-scope (unchanged): persistent auth/roles, distance/time routing, external TMS integration.

## 3. Users
- Logistics Planner (primary)
- Operations Lead (secondary)

## 4. Key flows
- Upload & Preview: .xlsx only; show headers/missing columns; Planning Whse filter (default ZAC).
- Optimize: compute trucks and assignments with TX/Other weight rules; sections by priority bucket.
- Review: truck cards with utilization, counts, date ranges; drill into lines.
- Route Management: see underweight trucks (≤94%); select lines across trucks; combine with guardrails.
- Plan Loads CSV (new): select lines or per-truck "Plan all"; export CSV across trucks.
- Export: Truck Results and DH Load List (formatted).

## 5. Functional requirements
### 5.1 Import & validation
- File: .xlsx (openpyxl). Required columns: SO, Line, Customer, shipping_city, shipping_state, Ready Weight, RPcs, Grd, Size, Width, Earliest Due, Latest Due.
- Planning Whse filter: find column case/spacing variants; default value ZAC.
- Derived: Weight Per Piece, Is Late, Days Until Late, Is Overwidth, Priority Bucket.

### 5.2 Optimization
- Group: Zone? → Route? → Customer → State → City (one customer per truck).
- Weights: TX min/max 47k/52k; Other 44k/48k. Split by pieces; 98% cap buffer.
- Cross-bucket fill: Late ← NearDue/WithinWindow; NearDue ← WithinWindow within exact group.
- Output: TruckSummary and LineAssignment (with trttav_no?).

### 5.3 Route Management
- Focus list: trucks with utilization ≤94%.
- Select lines across trucks; auto-target = lightest involved.
- Guardrails: same state; capacity ≤ max; reject invalid combinations.

### 5.4 Plan Loads CSV (v1.2)
- Selection UI:
  - Per-line checkbox within truck details.
  - Truck card "Plan all (x/y)" toggles all lines for that truck.
  - Global "Select none" clears all selections.
- Button label: "Plan Loads (N trucks)" where N = unique trucks in selection.
- Filename: planned_loads_YYYY-MM-DD_{N}trucks.csv.
- Columns: Truck #, trttav_no, SO, Line, Pieces (on transport), Weight (line total).
- Behavior: includes only selected lines across trucks; trttav_no blank if missing in source.

### 5.5 Exports
- Truck Results: Excel with Truck Summary + Order Details; respects Planning Whse filter.
- DH Load List: two sheets (Late+NearDue, WithinWindow); info rows (late status, totals, utilization, overwidth), hidden col C, bold headers, date formats, utilization color coding; Actual Ship rules (Late→next business day; else next business day after max earliestDue; if past, push +3 business days).

## 6. UI/UX
- Upload: progress and errors; preview panel.
- Results:
  - Sections: Late, NearDue, WithinWindow with counts.
  - Truck card: truck #, customer + city/state, utilization badge, total weight, late indicator, row1 counts (orders/lines/pieces), row2 date ranges (Earliest min→max, Latest min→max), "Plan all".
- Truck details: lines with weights/pieces, late/overwidth badges, per-line planning checkbox.
- Route Management: grouped Route→Zone→Customer; selection totals (lines, total weight, selected truck count); Combine button with validation states.
- Exports: buttons with progress/errors.
- Analytics: <Analytics /> in layout.

## 7. Data contracts (abridged)
- TruckSummary: { truckNumber, customerName, city/state, zone?, route?, totalWeight, minWeight, maxWeight, totalOrders, totalLines, totalPieces, maxWidth, percentOverwidth, containsLate, priorityBucket }
- LineAssignment: { truckNumber, so, line, trttav_no?, customerName, city/state, piecesOnTransport, totalReadyPieces, weightPerPiece, totalWeight, width, isOverwidth, isLate, earliestDue?, latestDue?, zone?, route? }
- CombineTrucksRequest: { truckIds: number[], lineIds: string[], weightConfig }
- CombineTrucksResponse: { success, message, newTruck?, updatedAssignments[], removedTruckIds[] }

## 8. API surface (frontend base /api)
- POST /upload/preview → UploadPreviewResponse
- POST /optimize → OptimizeResponse
- POST /export/trucks → .xlsx
- POST /export/dh-load-list → .xlsx
- GET/POST /no-multi-stop-customers
- POST /combine-trucks → CombineTrucksResponse
- GET /health

## 9. Non-functional
- Performance: preview in seconds; optimization for daily scale.
- Reliability: single-node, stateless.
- Security: no auth; don’t log file contents.
- Observability: Vercel Analytics; minimal server logs; frontend axios timeout 45s.

## 10. Metrics
- Avg utilization; underweight count before/after manual combine; late orders cleared; time from upload → export; CSV usage (download count).

## 11. Risks & mitigations
- Column variability → robust header detection/normalization.
- Over/underfilling → heuristic caps + fill passes.
- User error in manual combine → guardrails and inline validation.

## 12. Release plan
- v1.2 (current): features above shipped.
- v1.3 (next):
  - Wire UI weight-config to all endpoints (optimize, exports, combine).
  - Persist no-multi-stop list (DB or config file) and Planning Whse default.
  - Per-truck export actions and stable truck numbering across edits.
  - Basic auth (single-tenant) and environment-backed API base URL.

## 13. Acceptance tests (selected)
- Plan Loads CSV contains only selected lines and correct columns; filename includes date and unique truck count.
- trttav_no appears in optimize assignments when present in source and in CSV.
- Truck card date ranges reflect min/max of earliestDue/latestDue across its lines.
- Combine cross-state/overweight → rejected with clear message; valid combine updates target truck and removes emptied trucks.
- DH Load List formatting and Actual Ship rules verified visually and by cell formats.
