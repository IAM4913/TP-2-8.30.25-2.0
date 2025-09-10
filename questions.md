Actual Ship source: Is the exact column name in the input “Planned delivery date” (case/spaces as written), or should I locate it by fuzzy match (e.g., “planned deliver…”)?
    Prompt user before running
    
Ship Date: “Latest Date” = the “Latest Due” column from the input, correct? Or a different column?
    Yes, Latest DUe
BPCS vs RPCS on this transport:
In your source, are there columns named “BPcs” and “RPcs”?
Should both BPCS and RPCS reflect the quantity actually placed on the truck (i.e., per line assignment), or should one of them be the order-level totals?
    Let BPcs be totals for the input line.  RPcs should be Quantities on truck only
If BPcs exists in source, how do we compute “BPCS on this transport” from it when we split lines by pieces? (e.g., piecesOnTransport_B vs piecesOnTransport_R?)
    changed logic on this in previous question.  just use the input line level totals for BPcs.
Bal Weight and Ready Weight “on this Transport”:
    Bal Weight should be totals from the input line
    Ready Weight should be just the weight on the truck.
Should both be computed as WeightPerPiece × pieces on the truck for that line, or is “Bal Weight” derived from a separate input column?
    Bal Weight is from the input file.
R# (“Route” index): When there are multiple customers on one transport, do you want:
R# = 1 for all rows of the first customer on that truck, R# = 2 for all rows of the second customer, etc., in the order they appear?
    correct.
Carrier default: Use the literal “Jordan Carriers” for all rows unless you later override per-transport?
    Yes
D = trttav_no: Please confirm the exact input column name/casing to read (e.g., “trttav_no”).
    trttav_no
WHSE source: Use the “Planning Whse” column (case-insensitive/fuzzy match), right?
    Yes
Zone vs Route: Use the input columns “Zone” and “Route” (fuzzy match okay), and write exactly those values.
    exact
Output columns: Do you want ONLY the fields listed in your mapping (ending at D), or should I include any additional columns visible in the PNG (e.g., Paid/Late/Cost/etc.)?
    Just the columns I've mentioned for now.  It does look like there is a hidden column C that I missed in the orginal mapping
Excel styling specifics: Is a light blue like hex AADCEE (or you can provide a hex) acceptable? Any header bolding/freeze panes needed?
    DCE6F1
Filename: OK to download as dh_load_list.xlsx?
    Yes