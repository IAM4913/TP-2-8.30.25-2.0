## Update Log

Chronological summary of changes by commit (most recent at bottom). This file is maintained alongside pushes to `main`.

### Add Vercel Analytics and wire into app
- Installed `@vercel/analytics` and injected `<Analytics />` into the app layout.
- Files:
  - frontend/src/main.tsx
  - frontend/package.json, package-lock.json

### Plan Loads: multi-truck selection, select-none, CSV export
- Added per-line checkboxes and a global “Plan Loads” CSV export on the Results page.
- Supported multi-truck selections and a “Select none” control.
- CSV columns: Truck #, trttav_no, SO, Line, Pieces, Weight.
- Files:
  - frontend/src/components/TruckResults.tsx
  - frontend/src/types.ts (added optional `trttav_no`)

### Include trttav_no from source into LineAssignment and API
- Propagated transport identifier from source Excel into backend responses.
- Updated schema and optimization pipeline; combine-trucks now returns `trttav_no` too.
- Files:
  - backend/app/schemas.py
  - backend/app/optimizer_simple.py
  - backend/app/main.py

### Frontend: add axios timeout to prevent stuck upload spinner
- Added a 45s timeout to API calls to avoid indefinite “Processing file…” states.
- Files:
  - frontend/src/api.ts

### Plan Loads: show unique truck count and date in CSV filename
- Button label shows number of unique trucks selected.
- CSV filename now includes date and truck count: `planned_loads_YYYY-MM-DD_{N}trucks.csv`.
- Files:
  - frontend/src/components/TruckResults.tsx

### Truck summary: show earliest/latest ship date ranges
- On each truck card, display min→max of earliestDue and latestDue across its lines.
- Files:
  - frontend/src/components/TruckResults.tsx

### Truck summary: split counts and date ranges into separate rows
- Prevented overlap by placing counts (orders/lines/pieces) on row 1 and date ranges on row 2.
- Files:
  - frontend/src/components/TruckResults.tsx


