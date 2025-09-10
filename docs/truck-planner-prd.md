# Product Requirements Document (PRD) — Truck Planner

Version: 1.0  
Date: 2025-09-02  
Status: MVP feature-complete for optimization, exports, and manual route management

## 1. Executive summary
- Problem: Scheduling trucks from a daily order spreadsheet is manual and error-prone; trucks often run underweight or late.
- Solution: A web app that ingests Excel orders, optimizes truck loads by constraints and priorities, visualizes results, enables manual combination of underweight loads, and exports planning Excel files.
- Outcomes:
  - Increase average utilization while respecting state weight limits.
  - Prioritize and clear Late and NearDue orders.
  - Reduce planner time and mistakes.

## 2. Goals and non-goals
- Goals
  - Import and validate Excel order data (Planning Whse filtering).
  - Auto-generate truck loads by Customer and destination, with state-specific weight limits and priorities.
  - Visualize loads by priority and utilization.
  - Manually combine underweight loads with guardrails.
  - Export: optimized trucks and a DH Load List with specific formatting.
- Non-goals (for MVP)
  - Real routing optimization (distance/time).
  - Persistent storage, auth/roles, multi-user concurrency.
  - Dispatch integration, telematics, or carrier tendering.

## 3. Users and personas
- Logistics planner: Uploads daily spreadsheet, runs optimization, reviews results, manually fixes underweight loads, exports final sheets.
- Operations lead (secondary): Reviews KPIs, spot-checks Late/NearDue.

## 4. Key user flows
- Upload and preview
  - Drag-and-drop .xlsx → backend reads headers, reports row count, missing required columns, and a small sample.
  - Optional filter by Planning Whse (default “ZAC”).
- Optimize
  - Run optimization → trucks grouped by Zone/Route/Customer/City/State with weight limits (TX vs Other).
  - Sections by priority bucket (Late, NearDue, WithinWindow).
- Review results
  - Truck cards: weight utilization, pieces, lines, late/overwidth indicators; drill into assignments.
- Route management (manual combination)
  - Focus list of underweight trucks (≤94% utilization).
  - Select lines across trucks; app validates same state and weight limit before combining into a single target truck.
- Export
  - Export optimized trucks (summary + details).
  - Export DH Load List (two sheets with required column layout, info rows, date formatting).

## 5. Functional requirements

### 5.1 Data import and validation
- Supported file: .xlsx only; openpyxl engine.
- Required columns (exact names expected, case sensitive on preview; optimizer has normalization for Zone/Route):
  - SO, Line, Customer, shipping_city, shipping_state, Ready Weight, RPcs, Grd, Size, Width, Earliest Due, Latest Due
- Planning Whse filter:
  - Column auto-detected across variants (e.g., “Planning Whse”, “Planning Warehouse”, etc.).
  - Default allowed value: “ZAC” (configurable via form field).
- Calculated fields:
  - Weight Per Piece = Ready Weight / RPcs
  - Is Late = Latest Due < today (UTC, normalized)
  - Days Until Late
  - Is Overwidth = Width > 96
  - Priority bucket: Late | NearDue (<= 3 days) | WithinWindow | NotDue (fallback)

Acceptance criteria
- If file extension isn’t .xlsx → 400 with helpful message.
- Preview returns headers, rowCount, missingRequiredColumns, and up to 5 sample rows.
- If Planning Whse column isn’t found, filter is a no-op.

### 5.2 Optimization engine
- Grouping
  - Group by Zone (if present) → Route (if present) → Customer → shipping_state → shipping_city.
  - Single-customer per truck (no mixing customers).
  - Sort by priority bucket, then Zone/Route/Customer/State/City.
- Weight constraints (defaults)
  - Texas (TX/TEXAS): min 47,000; max 52,000 lbs
  - Other states: min 44,000; max 48,000 lbs
- Splitting
  - Lines can be split by pieces to fit capacity (using Weight Per Piece).
- Cross-bucket top-off (heuristic)
  - Fill Late trucks from NearDue/WithinWindow of the exact same group (Zone, Route, Customer, City, State), then fill NearDue from WithinWindow.
  - Don’t split assignment fragments further during fill.
- Output
  - Truck summaries: weights, pieces, lines, utilization, late/overwidth flags, zone/route, bucket.
  - Line assignments: truckNumber, SO/Line, pieces on transport, total weight, width, isLate, earliest/latest due, zone/route.

Acceptance criteria
- No truck exceeds max weight.
- Underweight trucks (below min) may remain if no valid donors exist.
- State limits selected by destination state (TX vs Other).
- Output data is JSON-serializable and aligns with schemas.

### 5.3 Route management (manual combination)
- Scope
  - Focus on underweight trucks (≤94% utilization in UI).
  - Select lines across different trucks to combine into one target truck.
- Guardrails
  - Lines must be from the same state (no cross-state combinations).
  - Resulting weight must not exceed state max.
- Behavior
  - Target truck auto-selected as the lightest among involved.
  - Reassigns selected lines to the target; source trucks emptied by the move are removed from the result.
- Output
  - Returns success/message, newTruck summary, updatedAssignments for changed trucks, and removedTruckIds.

Acceptance criteria
- 400 for invalid payloads (bad JSON, missing fields).
- Combining across states is rejected.
- Combining that would exceed max is rejected.
- On success, UI can re-render changed trucks using updated assignments.

### 5.4 Export — optimized trucks
- Input: the same .xlsx source (the backend re-optimizes to produce export).
- Output: Excel with two sheets:
  - Truck Summary
  - Order Details
- Planning Whse filter applied if provided.

Acceptance criteria
- Download is a valid .xlsx; column widths reasonable; headers present.

### 5.5 Export — DH Load List
- Input: .xlsx source; re-optimizes internally.
- Output: Excel with two sheets:
  - “Late + NearDue”
  - “WithinWindow”
- Columns (data rows): Actual Ship, TR#, Carrier, Loaded, Shipped, Ship Date, Customer, Type, SO#, SO Line, R#, WHSE, Zone, Route, BPCS, RPCS, Bal Weight, Ready Weight, Frm, Grd, Size, Width, Lgth, D, PRV
- Per-load “info row” inserted between loads (shaded light blue, italic), showing:
  - RPCS: Late/On time
  - Ready Weight: total weight
  - Frm: Max weight
  - Grd: Utilization %
  - Width: Overwidth/Not Overwidth
- Formatting
  - Hidden blank column C
  - Header bold; date format “mm/dd/yyy” for Actual Ship and Ship Date
  - Separator row shading (DCE6F1), italics
  - Utilization coloring in info rows (>=90% green, >=84% yellow, else red)
  - Calibri 11 font, left-aligned; basic auto-fit widths with min widths
- Actual Ship date:
  - If any line in load is Late → next business day (skip Sat/Sun).
  - Else → next business day after the latest “Earliest Due” among lines; if result is in the past, push 3 business days from today.
- Sorting
  - Loads sorted by utilization (desc) within each sheet.

Acceptance criteria
- Both sheets exist with specified headers and formatting.
- Info rows appear after each truck’s data lines, with correct shading/italics and utilization color.
- Date formats applied on date columns only.

## 6. Business rules
1. Do not exceed state max weight (TX vs Other).
2. Prefer at/above min weights; underweights allowed if no valid donors.
3. One customer per truck; do not mix customers.
4. Group by City/State; prefer same Zone/Route when available.
5. Prioritize Late, then NearDue, then WithinWindow.
6. Allow line splitting by pieces to fit capacity.
7. No-multi-stop customers list is supported; current algorithm already enforces one-customer-per-truck.

## 7. Data model (API contracts)
- TruckSummary
  - truckNumber: int
  - customerName, customerAddress?, customerCity, customerState
  - zone?, route?
  - totalWeight: float, minWeight: int, maxWeight: int
  - totalOrders, totalLines, totalPieces: int
  - maxWidth: float, percentOverwidth: float
  - containsLate: bool, priorityBucket: string
- LineAssignment
  - truckNumber: int, so: string, line: string
  - customerName, customerAddress?, customerCity, customerState
  - piecesOnTransport, totalReadyPieces: int
  - weightPerPiece, totalWeight, width: number
  - isOverwidth, isLate: bool
  - earliestDue?, latestDue?: string (ISO or None)
- WeightConfig
  - texas_max_lbs, texas_min_lbs, other_max_lbs, other_min_lbs: int

## 8. API specification
Base URL (frontend): /api (proxied to backend)

- GET /health
  - 200: { status: "ok" }
- POST /upload/preview (multipart/form-data)
  - file: .xlsx
  - 200: UploadPreviewResponse { headers[], rowCount, missingRequiredColumns[], sample[] }
- POST /optimize (multipart/form-data)
  - file: .xlsx
  - planningWhse?: string (default “ZAC”)
  - 200: OptimizeResponse { trucks[], assignments[], sections{ bucketKey: number[] } }
- POST /export/trucks (multipart/form-data)
  - file: .xlsx
  - planningWhse?: string (default “ZAC”)
  - 200: Excel (blob)
- POST /export/dh-load-list (multipart/form-data)
  - file: .xlsx
  - plannedDeliveryCol?: string (optional hint; current logic uses rule-based dates)
  - planningWhse?: string (default “ZAC”)
  - 200: Excel (blob)
- GET /no-multi-stop-customers
  - 200: { customers: string[] }
- POST /no-multi-stop-customers (application/json)
  - Body: string[] (overwrites in-memory list)
  - 200: { message: string }
- POST /combine-trucks (multipart/form-data)
  - file: .xlsx
  - request: stringified JSON CombineTrucksRequest
  - planningWhse?: string
  - 200: CombineTrucksResponse { success, message, newTruck?, updatedAssignments[], removedTruckIds[] }

## 9. UI/UX requirements
- Upload/preview
  - Show headers, row count, missing required columns, sample rows.
  - Clear error state for bad files.
- Dashboard/results
  - Sections: Late, NearDue, WithinWindow.
  - Truck card: truck #, customer, city/state, total/min/max weight, orders/lines/pieces, max width, % utilization, badges for late/overwidth.
- Route Management
  - Group by Route → Zone → Customer.
  - Emphasize underweight trucks (≤94% utilization).
  - Multi-select lines; show aggregate selected weight and truck count.
  - Combine button enabled only when valid (same state + within max).
  - Inline validation messages (overweight, cross-state not allowed).
- Export
  - Buttons for both exports; show progress/errors; download .xlsx.

Accessibility
- Color and text indicators for status.
- Keyboard-navigation friendly lists and buttons.

## 10. Non-functional requirements
- Performance
  - Preview typical files in a few seconds.
  - Optimization suitable for small-to-medium daily spreadsheets.
- Availability
  - Single-node dev setup; no persistent storage.
- Security
  - No auth in MVP; local/dev use. Do not log uploaded file contents.
- Compatibility
  - Modern Chromium-based browsers. Windows-friendly exports.
- Observability
  - Minimal server logs; surface user-facing error messages.

## 11. Constraints and assumptions
- Input spreadsheet adheres to required columns; data types may need coercion.
- Planning Whse default is “ZAC”; missing column yields no filter.
- Zone/Route columns may be variably named; optimizer normalizes common variants.
- No persistent DB; no shared session state.

## 12. Success metrics (KPIs)
- Average truck utilization (% of max) per day.
- Count of trucks below min weight post-optimization and post-manual combine.
- Late orders cleared vs. total late orders in input.
- Time to produce plan (upload → export).

## 13. Risks and mitigations
- Inconsistent column naming → Robust header detection for Planning Whse, Zone, Route; explicit required columns for core fields.
- Over-splitting/underfilling → Heuristic thresholds (98% cap buffer), cross-bucket fill.
- User errors during combine → Guardrails (state match, capacity checks) and clear validation.

## 14. Release plan and future enhancements
- Near-term
  - Wire UI weight config to backend for all endpoints.
  - Persist no-multi-stop customers.
  - Per-truck export options and re-numbering stability across edits.
- Mid-term
  - Auth/roles; history and audit via DB.
  - Smarter routing (distance/time windows).
  - Configurable business rules in UI.
- Long-term
  - Integration with TMS/telematics; containerization and CI/CD.

## 15. Acceptance test scenarios (sample)
- Upload invalid file type → error 400.
- Upload valid file missing “Width” → preview shows it in missingRequiredColumns.
- Optimize typical file → trucks appear in three sections with correct weights and no over-max.
- Combine lines from different states → rejected with message.
- Combine within one state exceeding max → rejected.
- Combine valid selection → success; target truck updated; emptied trucks appear in removedTruckIds.
- Export trucks → .xlsx with two sheets; data matches current optimization.
- Export DH Load List → two sheets with correct headers, blue info rows, date format, utilization color coding, and hidden column C.
