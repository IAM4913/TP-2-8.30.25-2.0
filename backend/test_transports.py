"""Test script to verify dbo.transports field mapping"""
import sys
from dotenv import load_dotenv
from app.db_config import DataSourceAdapter, SQLServerConfig
from app.field_mappings import apply_field_mapping

load_dotenv()

config = SQLServerConfig()

print("\n" + "="*60)
print("Testing dbo.transports Field Mapping")
print("="*60)

try:
    # Fetch sample data
    print("\n[*] Querying dbo.transports...")
    df = DataSourceAdapter.from_sql_server(
        config, table_name="dbo.transports", limit=3)
    print(f"   [+] Fetched {len(df)} rows with {len(df.columns)} columns")

    # Apply field mapping
    print("\n[*] Applying field mapping...")
    mapped_df = apply_field_mapping(df)

    # Check required columns
    required = ["SO", "Line", "Customer", "shipping_city", "shipping_state",
                "Ready Weight", "RPcs", "Grd", "Size", "Width",
                "Earliest Due", "Latest Due"]

    present = [col for col in required if col in mapped_df.columns]
    missing = [col for col in required if col not in mapped_df.columns]

    print(f"\n[*] Required Columns Status: {len(present)}/{len(required)}")

    if present:
        print(f"\n   [+] Present:")
        for col in present:
            print(f"      [+] {col}")

    if missing:
        print(f"\n   [!] Missing:")
        for col in missing:
            print(f"      [-] {col}")
    else:
        print(f"\n   [+] ALL REQUIRED COLUMNS PRESENT!")

    # Show sample data
    if not missing:
        print(f"\n[*] Sample Data (first 2 rows):")
        print(mapped_df[required].head(2).to_string())

    print("\n" + "="*60)
    print("[+] Test Complete!")
    print("="*60)

except Exception as e:
    print(f"\n   [-] Error: {e}")
    import traceback
    traceback.print_exc()
