# Truck Routing Logic (Backend v0.1.0)

This document explains, in detail, how the backend builds trucks (“routing”) from an uploaded Excel file. It reflects the code paths currently used by the API (notably `backend/app/optimizer_simple.py`, plus helpers in `excel_utils.py` and FastAPI endpoints in `main.py`).

If you want stricter or different rules, see the “Next steps and toggles” section at the end.

---

## High‑level data flow

1. Client uploads an `.xlsx` file to `/optimize`.
2. The server reads the file (openpyxl), optionally filters rows by Planning Whse, and computes derived fields (see below).
3. The optimizer (`naive_grouping`) assigns lines to trucks, possibly splitting lines by pieces to fit weight limits.
4. A post‑pass “cross‑bucket fill” optionally moves assignment rows from less urgent trucks to more urgent ones to reach min weights.
5. The API returns two tables:
   - Truck summaries (one row per truck)
   - Line assignments (one row per fragment placed on a truck)

---

## Required input columns

The backend expects these exact columns to exist (case‑sensitive, see `main.py`):

- `SO` (Sales Order)
- `Line` (Line number)
- `Customer`
- `shipping_city`
- `shipping_state`
- `Ready Weight` (lbs)
- `RPcs` (Ready Pieces)
- `Grd`
- `Size`
- `Width` (inches)
- `Earliest Due` (date/time)
- `Latest Due` (date/time)

Optional but supported for grouping/sorting if present (case-insensitive detection):
- `Zone`
- `Route`
- Any Planning Warehouse column (various header spellings; used only for upstream filtering)

---

## Derived fields (`excel_utils.compute_calculated_fields`)

For each row:
- Ensures numeric types for `Ready Weight`, `RPcs`, and `Width`.
- Computes `Weight Per Piece = Ready Weight / RPcs` (safe divide; blanks become NaN).
- Converts `Earliest Due` and `Latest Due` to timezone‑aware pandas timestamps (UTC).
- Sets lateness flags using `Latest Due` vs today (UTC midnight):
  - `Is Late = Latest Due < today`
  - `Days Until Late = (Latest Due - today).days`
- Sets `Is Overwidth = Width > 96`.

All “today” comparisons normalize to midnight (`now.normalize()`), which avoids time‑of‑day edge cases.

---

## Priority buckets (`excel_utils.build_priority_bucket`)

Each row is assigned a priority bucket based on `Latest Due` relative to today (UTC midnight):
- `Late` if `Latest Due < today`
- `NearDue` if `0 <= days_until_due <= 3`
- `WithinWindow` otherwise (or if due date is missing)

A numeric `priorityRank` is also created for sorting: `Late:0`, `NearDue:1`, `WithinWindow:2`, `NotDue:3`.

---

## Weight configuration and state rules

Max/min truck weights depend on destination state (by `shipping_state`):
- Texas (`TX` or `TEXAS`): `max=52,000`, `min=47,000`
- Other states: `max=48,000`, `min=44,000`

These values come from the request’s weight config in the API. Defaults are set in `main.py` and may also be provided at runtime by `/combine-trucks` requests.

---

## Zone/Route normalization

`optimizer_simple` accepts zone/route even if the headers aren’t exact (e.g., `route`, `Route`, `ROUTE`). It:
- Normalizes all headers (`lower`, trim, strip non‑alphanumerics)
- Copies the first match for `zone` and `route` into canonical `Zone`/`Route` columns if missing

---

## Sorting and grouping strategy

1. Rows are sorted by: `priorityRank`, then `Zone` (if present), `Route` (if present), then `Customer`, `shipping_state`, `shipping_city`.
2. Grouping columns are: `[Zone?, Route?, Customer, shipping_state, shipping_city]`.
   - This means: one customer per destination (city/state) per Zone/Route group.
   - The current optimizer does not mix multiple customers on the same truck. The static `NO_MULTI_STOP_CUSTOMERS` list exists, but is effectively redundant here because grouping already enforces one-customer-per-truck.

---

## Building trucks inside each group

Inside each grouped set, the optimizer walks rows and fills trucks subject to weight and width rules.

Key mechanics:

- Capacity by weight only; piece count is just used to split loads.
- A line can be split by pieces to respect max weight (using `Weight Per Piece`).
- If a line does not fit and the current truck already has weight, the current truck is finalized and a new one starts.
- A truck is auto‑finalized when it reaches ≥ 98% of `maxWeight` (buffer allows minor rounding variance).
- Flags are tracked per truck: `containsLate` (any Late lines), and `has_near_due` (any NearDue lines).
- Each assignment row records due dates (serialized), weight/width, and split state (`isPartial`, `remainingPieces`).

Pseudo‑code (simplified):

```python
for group in df.groupby([Zone?, Route?, Customer, State, City]):
    reset_truck()
    pending_remainders = []

    for row in group:
        calc take_pieces based on (maxWeight - current_weight) and weight_per_piece
        if take_pieces == 0 and current_weight > 0:
            finalize_truck()
            recalc take_pieces
        place take_pieces on current truck (may be full line)
        if remainder exists: push to pending_remainders
        if current_weight >= 0.98 * maxWeight: finalize_truck()

    # Iteratively place all remainders with safety bound
    while pending_remainders:
        for r in sorted_by_priority(pending_remainders):
            try place; if still remainder, carry over
            if current_weight >= 0.98 * maxWeight: finalize_truck()

    finalize_truck()
```

Finalizing a truck computes:
- `percentOverwidth = (sum of assignment weights with width>96) / totalWeight`
- `priorityBucket` for the truck:
  - `Late` if any assignment is Late
  - Else `NearDue` if any assignment is NearDue
  - Else `WithinWindow`

Assignments created during this pass include useful metadata:
- `so`, `line` (remainders get suffixes `-R1`, `-R2`, …)
- `customerName/City/State`, `zone`, `route`
- `piecesOnTransport`, `totalReadyPieces`, `weightPerPiece`, `totalWeight`
- `width`, `isOverwidth`, `isLate`, `priorityBucket`
- `earliestDue`, `latestDue` (ISO strings or null)
- `isPartial`, `remainingPieces`, `isRemainder`, `parentLine`

---

## Cross‑bucket fill pass (topping off trucks)

After the initial pass, the optimizer may move WHOLE assignment rows (no further splitting) from less urgent trucks to more urgent trucks to help them reach minimum weight, with strict constraints:

- Group key must match exactly between trucks: `(Zone, Route, Customer, State, City)`.
- Capacity: target’s `totalWeight + rowWeight <= maxWeight * 1.0001`.
- Stop conditions per target: once it reaches `minWeight` or ≥ `0.98 * maxWeight`.
- Donor trucks can be emptied; if they become empty, they’re effectively removed.
- Two passes are executed in order:
  1. Fill `Late` trucks using donors from `NearDue` and `WithinWindow`.
     - Guard: DO NOT move a row into a `Late` truck if that row’s `earliestDue > today` (UTC). This prevents placing too‑early items onto a Late truck during the fill and complements the initial packing rule.
  2. Fill `NearDue` trucks using donors from `WithinWindow`.

Important nuance (updated Sep 10, 2025): During the initial per‑group pass, Late lines can only be combined with orders already within the shipping window (today or earlier). If a Late line would mix with a non‑Late whose `Earliest Due` is after today, the current truck is finalized first; likewise, adding a Late line to a truck whose current earliest `Earliest Due` is after today will finalize that truck before placing the Late line.

---

## What the API returns

The `/optimize` endpoint returns:

- `trucks`: array of truck summaries with fields like `truckNumber`, `customerName`, `customerCity/State`, `zone/route`, `totalWeight`, `minWeight`, `maxWeight`, `totalOrders`, `totalLines`, `totalPieces`, `maxWidth`, `percentOverwidth`, `containsLate`, `priorityBucket`.
- `assignments`: array of line fragments with all placement details (see above).
- `sections`: a map from priority bucket to list of `truckNumber`s, built from the truck summaries.

Truck numbers are 1‑based and assigned in the order trucks are created.

---

## Export logic (brief)

The `/export/trucks` and `/export/dh-load-list` endpoints re‑run the optimizer and write Excel files. The DH Load List sheet also computes per‑truck “Actual Ship” dates:
- If any line on a truck is Late → next business day.
- Else → next business day after the maximum `Earliest Due` across the truck’s lines.
- If the computed date is somehow in the past, it’s bumped three business days from today.

These rules affect export scheduling only, not the truck routing itself.

---

## Edge cases and safeguards

- Missing `Zone`/`Route`: treated as absent; grouping still works.
- Non‑numeric weights/pieces/width: coerced to numeric; rows with `RPcs<=0` are skipped.
- Remainders are processed iteratively with a safety cap to avoid infinite loops.
- Time zone: “today” uses UTC midnight; source Excel dates are converted to UTC.
- Overwidth is a flag; it doesn’t block placement—just tracked and reported.

---

## Known limitations (current behavior)

- One‑customer‑per‑truck grouping: the optimizer does not build multi‑stop trucks today.
- Late + future‑dated mixing is now blocked during initial packing by `Earliest Due` (UTC today) checks; however, the rule uses UTC midnight and relies on `Earliest Due` being present and parseable.
- Weight is the only capacity constraint (no length, axle, stop‑count, or distance modeling).

---

## Next steps and toggles (if you want different behavior)

- Enforce “Late cannot share with items whose `Earliest Due` is after tomorrow” at placement time (not just during fill). This would require a small enhancement in `optimizer_simple`’s inner loop.
- Support true multi‑stop logic with a data‑driven exclusion list, so some customers can be combined and others not.
- Add a tunable buffer (98%) for finalization and expose weights (min/max) as UI inputs.
- Consider prioritizing by `Earliest Due` (or both) if business rules shift.

---

## Pseudocode summary

```text
1) Preprocess rows → numeric fields, dates (UTC), derived flags
2) Assign priority buckets from Latest Due (Late / NearDue / WithinWindow)
3) Sort by priority, zone, route, customer, destination
4) Group by (Zone?, Route?, Customer, State, City)
5) Within each group → pack trucks by weight, split lines by pieces, finalize at ~98% max
6) Process all remainders until placed
7) Cross-bucket fill: Late <- NearDue/WithinWindow (earliestDue <= today), then NearDue <- WithinWindow
8) Return truck summaries + assignments + sections
```

---

## File references

- Optimizer: `backend/app/optimizer_simple.py`
- Helpers: `backend/app/excel_utils.py`
- API: `backend/app/main.py`
- Types / models: `backend/app/schemas.py`
