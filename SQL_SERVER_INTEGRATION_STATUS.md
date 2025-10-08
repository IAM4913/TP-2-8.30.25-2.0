# SQL Server Integration - Implementation Status

## ✅ Completed Steps

### Step 1: Install MS SQL Server Driver
- ✅ Added `pymssql==2.3.1` to `requirements.txt`
- ✅ Pure-Python driver (no compilation required)

### Step 2: Create Configuration Modules
- ✅ Created `backend/app/db_config.py`
  - `SQLServerConfig` class for connection management
  - `DataSourceAdapter` class for unified data loading
  - Connection testing functionality
  
- ✅ Created `backend/app/field_mappings.py`
  - `SQL_SERVER_FIELD_MAP` dictionary for column mapping
  - `apply_field_mapping()` function
  - Helper functions for query generation

### Step 3: Add API Endpoints
- ✅ Added 3 new endpoints to `backend/app/main.py`:
  - `GET /db/mssql/status` - Check SQL Server connection
  - `GET /db/mssql/preview` - Preview SQL Server data
  - `POST /optimize/from-db` - Run optimization from SQL Server

### Additional Files Created
- ✅ `backend/test_mssql_connection.py` - Test script for verification
- ✅ `docs/sql-server-integration.md` - Complete documentation

## 📋 Your Current Configuration

Based on your database connection screenshot:
```
Server: 10.0.1.50
Port: 1433
Database: Planning
Username: sa
```

## 🔧 Next Steps to Complete

### 1. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Test the Connection
```bash
cd backend
python test_mssql_connection.py
```

This will:
- ✅ Verify SQL Server connection
- 📋 List all available tables
- 🔍 Show column names from your table
- 🔀 Test field mapping
- ⚠️ Identify any missing required columns

### 3. Update Field Mappings (if needed)

After running the test script, you may need to update `backend/app/field_mappings.py` to match your actual SQL Server column names.

**Your actual table columns** → **Required internal columns**

### 4. Create SQL Server View (Optional but Recommended)

Instead of Python mapping, create a view with pre-mapped column names:

```sql
CREATE VIEW dbo.vTruckPlanner AS
SELECT
    YourOrderColumn AS [SO],
    YourLineColumn AS [Line],
    YourCustomerColumn AS [Customer],
    -- etc...
FROM YourActualTable
WHERE ReadyWeight > 0
```

### 5. Start the Backend Server
```bash
cd backend
uvicorn app.main:app --reload
```

### 6. Test the New Endpoints

Visit these URLs in your browser:
- http://localhost:8000/docs (FastAPI auto-generated API docs)
- http://localhost:8000/db/mssql/status (Check connection)
- http://localhost:8000/db/mssql/preview?table_name=dbo.vTruckPlanner&limit=10

## 🎯 What You Can Do Now

### Keep File Upload (Existing)
Your existing file upload workflow continues to work exactly as before.

### Add Direct SQL Query (New)
You can now query SQL Server directly:

**API Usage Example:**
```bash
# Check status
curl http://localhost:8000/db/mssql/status

# Preview data
curl "http://localhost:8000/db/mssql/preview?table_name=dbo.YourTable"

# Run optimization from database
curl -X POST "http://localhost:8000/optimize/from-db" \
  -F "table_name=dbo.YourTable" \
  -F "planningWhse=ZAC"
```

## 🚀 Future Steps (Not Yet Implemented)

### Frontend Integration
To add the UI for database querying:
1. Create a data source selector component (File vs Database)
2. Add table/view name input
3. Add WHERE clause builder (optional)
4. Wire up to new `/optimize/from-db` endpoint

We can tackle this next if you'd like!

## 📝 Important Notes

### Security
- Currently using `sa` account (admin) - consider creating a read-only user
- `.env` file should not be committed to git
- Basic SQL injection protection is in place

### Performance
- Queries are limited to avoid overloading the server
- Consider adding indexes on frequently queried columns
- The view approach is faster than Python mapping

### Column Mapping Strategy
**Option 1 (Recommended):** Create a SQL Server view with correct column names
**Option 2:** Update `SQL_SERVER_FIELD_MAP` in `field_mappings.py`
**Option 3:** Provide custom SQL query with column aliases

## 📚 Documentation

See `docs/sql-server-integration.md` for complete documentation including:
- Architecture diagrams
- API endpoint details
- Field mapping configuration
- SQL Server view examples
- Troubleshooting guide

## ❓ Questions to Resolve

1. **What is your table/view name?** (Default is set to `dbo.vTruckPlanner`)
2. **What are the actual column names in your SQL Server table?**
3. **Would you like help creating a SQL Server view?**
4. **Should we proceed with frontend integration next?**

---

**Ready to Test?** Run `python backend/test_mssql_connection.py` and share the output!


