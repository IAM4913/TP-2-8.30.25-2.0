"""Test script for SQL Server connection and field mapping.

Run this script to verify your SQL Server connection and see what columns are available.
Usage: python test_mssql_connection.py
"""

import os
from dotenv import load_dotenv
from app.db_config import SQLServerConfig, DataSourceAdapter
from app.field_mappings import apply_field_mapping, create_mapping_from_sample

# Load environment variables
load_dotenv()


def test_connection():
    """Test basic SQL Server connection."""
    print("=" * 60)
    print("Testing SQL Server Connection")
    print("=" * 60)

    config = SQLServerConfig()

    # Check configuration
    print(f"\n[*] Configuration:")
    print(f"   Server: {config.server}")
    print(f"   Database: {config.database}")
    print(f"   Username: {config.username}")
    print(f"   Port: {config.port}")

    if not config.is_configured():
        print("\n[!] ERROR: SQL Server not fully configured!")
        print("   Please set MSSQL_SERVER, MSSQL_DATABASE, MSSQL_USERNAME, and MSSQL_PASSWORD in .env")
        return False

    # Test connection
    print(f"\n[*] Testing connection...")
    try:
        is_connected = config.test_connection()
        if is_connected:
            print("   [+] Connection successful!")
            return True
        else:
            print("   [-] Connection failed!")
            return False
    except Exception as e:
        print(f"   [-] Connection error: {e}")
        return False


def list_tables():
    """List available tables in the database."""
    print("\n" + "=" * 60)
    print("Listing Available Tables")
    print("=" * 60)

    config = SQLServerConfig()

    try:
        # Query to get table names
        query = """
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW')
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """

        df = DataSourceAdapter.from_sql_server(config, query=query)

        if df.empty:
            print("   No tables found.")
            return

        print(f"\n   Found {len(df)} tables/views:\n")

        for _, row in df.iterrows():
            schema = row['TABLE_SCHEMA']
            name = row['TABLE_NAME']
            ttype = row['TABLE_TYPE']
            full_name = f"{schema}.{name}"
            type_icon = "[TABLE]" if ttype == "BASE TABLE" else "[VIEW]"
            print(f"   {type_icon} {full_name}")

    except Exception as e:
        print(f"   [-] Error listing tables: {e}")


def test_query_table(table_name="dbo.vTruckPlanner"):
    """Query a specific table and show column information."""
    print("\n" + "=" * 60)
    print(f"Querying Table: {table_name}")
    print("=" * 60)

    config = SQLServerConfig()

    try:
        # Fetch sample data
        print(f"\n[*] Fetching sample data (top 5 rows)...")
        df = DataSourceAdapter.from_sql_server(
            config, table_name=table_name, limit=5)

        print(f"   [+] Found {len(df)} rows")
        print(f"\n[*] Available Columns ({len(df.columns)}):")
        for i, col in enumerate(df.columns, 1):
            dtype = df[col].dtype
            null_count = df[col].isnull().sum()
            sample_val = df[col].iloc[0] if len(df) > 0 else None
            print(f"   {i:2}. {col:30} ({dtype}) - Sample: {sample_val}")

        # Try field mapping
        print(f"\n[*] Testing Field Mapping...")
        mapped_df = apply_field_mapping(df)

        print(f"   Columns after mapping: {len(mapped_df.columns)}")
        print(f"\n   Mapped columns:")
        for col in mapped_df.columns:
            if col not in df.columns:
                print(f"      [+] {col} (newly mapped)")

        # Check for required columns
        required = ["SO", "Line", "Customer", "shipping_city", "shipping_state",
                    "Ready Weight", "RPcs", "Grd", "Size", "Width",
                    "Earliest Due", "Latest Due"]

        missing = [col for col in required if col not in mapped_df.columns]

        if missing:
            print(f"\n   [!] Missing required columns after mapping:")
            for col in missing:
                print(f"      [-] {col}")
            print(
                f"\n   [i] You may need to update SQL_SERVER_FIELD_MAP in field_mappings.py")
        else:
            print(f"\n   [+] All required columns present!")

        # Show sample data
        print(f"\n[*] Sample Data (first 2 rows):")
        print(mapped_df.head(2).to_string())

    except Exception as e:
        print(f"   [-] Error querying table: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SQL Server Connection Test Script")
    print("=" * 60)

    # Test connection
    if not test_connection():
        print("\n[!] Cannot proceed without a successful connection.")
        return

    # List tables
    list_tables()

    # Test querying a table
    # Update this to match your actual table/view name
    table_name = os.getenv("MSSQL_DEFAULT_TABLE", "dbo.vTruckPlanner")
    test_query_table(table_name)

    print("\n" + "=" * 60)
    print("[+] Test Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. If missing required columns, update SQL_SERVER_FIELD_MAP in field_mappings.py")
    print("2. Start your FastAPI server: uvicorn app.main:app --reload")
    print("3. Test the endpoints:")
    print("   - GET http://localhost:8000/db/mssql/status")
    print("   - GET http://localhost:8000/db/mssql/preview?table_name=dbo.vTruckPlanner")
    print()


if __name__ == "__main__":
    main()
