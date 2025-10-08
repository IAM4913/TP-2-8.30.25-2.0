# SQL Server Direct Integration Guide

This document describes the SQL Server direct query integration for the Truck Planner application.

## Overview

The application now supports **two data source modes**:
1. **File Upload** - Upload `.xlsx` files (existing functionality)
2. **Database Query** - Query MS SQL Server directly (new functionality)

Both modes feed into the same optimization engine, so the results are consistent.

## Architecture

### Components

```
┌─────────────────┐
│   Frontend      │
│  (React/TS)     │
└────────┬────────┘
         │
         ├─────────────────┬─────────────────┐
         │                 │                 │
    File Upload      DB Query Status    DB Optimize
         │                 │                 │
         ▼                 ▼                 ▼
┌──────────────────────────────────────────────┐
│           FastAPI Backend                    │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │  DataSourceAdapter                   │   │
│  │  ├─ from_file()                      │   │
│  │  └─ from_sql_server()                │   │
│  └──────────────────────────────────────┘   │
│                    │                         │
│                    ▼                         │
│  ┌──────────────────────────────────────┐   │
│  │  Field Mapping                       │   │
│  │  (SQL columns → Internal names)      │   │
│  └──────────────────────────────────────┘   │
│                    │                         │
│                    ▼                         │
│  ┌──────────────────────────────────────┐   │
│  │  Optimization Engine                 │   │
│  │  (naive_grouping)                    │   │
│  └──────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
                    │
                    ▼
            ┌───────────────┐
            │  MS SQL Server│
            │  (10.0.1.50)  │
            └───────────────┘
```

## Configuration

### Environment Variables

Add these to `backend/.env`:

```env
# MS SQL Server Configuration
MSSQL_SERVER=10.0.1.50
MSSQL_PORT=1433
MSSQL_DATABASE=Planning
MSSQL_USERNAME=sa
MSSQL_PASSWORD=your_password_here
MSSQL_TIMEOUT=30

# Optional: Default table/view name
MSSQL_DEFAULT_TABLE=dbo.vTruckPlanner
```

### Python Dependencies

The following package was added to `requirements.txt`:
- `pymssql==2.3.1` - Pure-Python MS SQL Server driver

Install with:
```bash
cd backend
pip install -r requirements.txt
```

## New API Endpoints

### 1. Check SQL Server Status
**GET** `/db/mssql/status`

Returns configuration status and tests the connection.

**Response:**
```json
{
  "configured": true,
  "connected": true,
  "server": "10.0.1.50",
  "database": "Planning",
  "port": 1433
}
```

### 2. Preview SQL Server Data
**GET** `/db/mssql/preview?table_name=dbo.vTruckPlanner&limit=100`

Fetches sample data from SQL Server and shows column mapping results.

**Parameters:**
- `table_name` (string) - Table or view name (default: `dbo.vTruckPlanner`)
- `limit` (int) - Number of rows to fetch (default: 100)

**Response:** Same as `/upload/preview` endpoint

### 3. Optimize from Database
**POST** `/optimize/from-db`

Runs optimization directly on SQL Server data.

**Form Parameters:**
- `table_name` (string) - Table or view name (default: `dbo.vTruckPlanner`)
- `where_clause` (string, optional) - SQL WHERE clause for filtering
- `planningWhse` (string) - Planning warehouse filter (default: `ZAC`)

**Response:** Same as `/optimize` endpoint

## Field Mapping

The system maps SQL Server column names to internal column names used by the optimization engine.

### How It Works

1. Data is fetched from SQL Server with original column names
2. `apply_field_mapping()` renames columns based on `SQL_SERVER_FIELD_MAP`
3. Mapped data is processed by the optimization engine

### Configuration File

Edit `backend/app/field_mappings.py` to customize mappings:

```python
SQL_SERVER_FIELD_MAP = {
    # SQL Server Column : Internal Column
    "SalesOrderNumber": "SO",
    "LineNumber": "Line",
    "CustomerName": "Customer",
    "ShipCity": "shipping_city",
    # ... etc
}
```

### Required Internal Columns

The optimization engine requires these columns:
- `SO` - Sales Order Number
- `Line` - Line Number
- `Customer` - Customer Name
- `shipping_city` - Shipping City
- `shipping_state` - Shipping State
- `Ready Weight` - Weight in pounds
- `RPcs` - Ready Pieces (quantity)
- `Grd` - Material Grade
- `Size` - Material Thickness
- `Width` - Material Width
- `Earliest Due` - Earliest Due Date
- `Latest Due` - Latest Due Date

## Testing

### 1. Test Connection

Run the test script:
```bash
cd backend
python test_mssql_connection.py
```

This will:
- Test the SQL Server connection
- List available tables
- Show column names and sample data
- Verify field mapping
- Identify missing required columns

### 2. Test API Endpoints

Start the FastAPI server:
```bash
cd backend
uvicorn app.main:app --reload
```

Test the endpoints:
```bash
# Check status
curl http://localhost:8000/db/mssql/status

# Preview data
curl "http://localhost:8000/db/mssql/preview?table_name=dbo.vTruckPlanner&limit=10"

# Test optimization (use a tool like Postman for POST requests)
```

## SQL Server Recommendations

### Option 1: Create a View (Recommended)

Create a SQL Server view with pre-mapped column names:

```sql
CREATE VIEW dbo.vTruckPlanner AS
SELECT
    SalesOrderNumber AS [SO],
    LineNumber AS [Line],
    CustomerName AS [Customer],
    ShipCity AS [shipping_city],
    ShipState AS [shipping_state],
    ReadyWeightLbs AS [Ready Weight],
    ReadyPieces AS [RPcs],
    Grade AS [Grd],
    Thickness AS [Size],
    WidthInches AS [Width],
    EarliestDueDate AS [Earliest Due],
    LatestDueDate AS [Latest Due],
    MaterialForm AS [Frm],
    Length AS [Lgth],
    BalanceWeight AS [Bal Weight],
    Type AS [Type],
    WarehouseCode AS [Planning Whse],
    TrttavNo AS [trttav_no],
    RNumber AS [R]
FROM dbo.OrderLines
WHERE 
    ReadyWeightLbs > 0
    AND ShipState IS NOT NULL
    AND LatestDueDate IS NOT NULL
```

**Benefits:**
- No Python field mapping needed (columns already correct)
- Can add business logic/filtering in the view
- Easier to maintain than Python mapping
- Better performance (SQL Server can optimize)

### Option 2: Use Python Field Mapping

If you can't create a view, update `SQL_SERVER_FIELD_MAP` in `field_mappings.py` to match your table structure.

### Option 3: Use Column Aliases in Query

You can also provide a custom query with aliases:

```python
query = """
SELECT
    SalesOrderNumber AS [SO],
    LineNumber AS [Line],
    ...
FROM dbo.OrderLines
WHERE LatestDueDate >= GETDATE() - 30
"""
```

## Security Considerations

1. **Read-Only User**: Create a dedicated SQL Server user with SELECT-only permissions:
   ```sql
   CREATE LOGIN truck_planner_ro WITH PASSWORD = 'strong_password';
   CREATE USER truck_planner_ro FOR LOGIN truck_planner_ro;
   GRANT SELECT ON dbo.vTruckPlanner TO truck_planner_ro;
   ```

2. **SQL Injection Protection**: The system includes basic protection, but always validate inputs

3. **Connection String Security**: Never commit `.env` file to version control

## Troubleshooting

### Connection Fails

1. Check that SQL Server allows remote connections
2. Verify firewall rules allow port 1433
3. Ensure SQL Server authentication is enabled (not just Windows auth)
4. Test connection from the server running FastAPI:
   ```bash
   telnet 10.0.1.50 1433
   ```

### Column Mapping Issues

1. Run `test_mssql_connection.py` to see actual column names
2. Update `SQL_SERVER_FIELD_MAP` in `field_mappings.py`
3. Or create a view with correct column names (recommended)

### Missing Data

1. Check the `where_clause` parameter isn't filtering too much
2. Verify `planningWhse` filter matches your data
3. Check that the table has data: `SELECT COUNT(*) FROM dbo.vTruckPlanner`

## Next Steps

1. ✅ Install dependencies (`pip install -r requirements.txt`)
2. ✅ Configure `.env` file with SQL Server credentials
3. ⏳ Run `test_mssql_connection.py` to verify setup
4. ⏳ Update field mappings if needed
5. ⏳ Create SQL Server view (optional but recommended)
6. ⏳ Update frontend to add "Query Database" option
7. ⏳ Test end-to-end workflow

## Frontend Integration (Future)

The frontend will need:
1. Data source toggle (File Upload vs Database Query)
2. Table/View selector dropdown
3. Optional WHERE clause input
4. Same optimization results display

API calls will use the new endpoints instead of file upload when in "Database Query" mode.


