"""Field mappings for SQL Server database columns to optimization engine columns."""

from typing import Dict

# Map SQL Server column names to internal optimization column names
SQL_SERVER_FIELD_MAP: Dict[str, str] = {
    # Sales Order
    'so_num': 'SO',

    # Line Number
    'so_line': 'Line',

    # Customer Name
    'customer_name': 'Customer',

    # Shipping City
    'shipping_city': 'shipping_city',

    # Shipping State
    'shipping_state': 'shipping_state',

    # Ready Weight (from balance_weight)
    'balance_weight': 'Ready Weight',

    # Ready Pieces (from balance_pcs)
    'balance_pcs': 'RPcs',

    # Material Grade
    'grade': 'Grd',

    # Material Size
    'size': 'Size',

    # Material Width
    'width': 'Width',

    # Earliest Due Date
    'due_dt': 'Earliest Due',

    # Latest Due Date
    'due_dt2': 'Latest Due',

    # Transport identifier (optional)
    'trttav_no': 'trttav_no',

    # Form (optional)
    'form': 'form',

    # Length (optional)
    'length': 'length',

    # Type (optional)
    'type': 'type',

    # Planning Warehouse (optional)
    'planning_whse': 'Planning Whse',

    # Zone (optional)
    'transport_zone': 'Zone',

    # Route (optional)
    'final_modified_route': 'Route',

    # Customer State (optional) - avoid conflict with shipping_state
    'state': 'customer_state',

    # Weight per piece (optional)
    'weight': 'Weight Per Piece',
}


def apply_field_mapping(df) -> None:
    """
    Apply field mapping in-place to rename columns to match optimization engine expectations.

    Args:
        df: DataFrame to modify in-place
    """
    # Rename columns based on mapping
    for sql_col, internal_col in SQL_SERVER_FIELD_MAP.items():
        if sql_col in df.columns:
            df.rename(columns={sql_col: internal_col}, inplace=True)

    # Ensure required columns exist
    required_cols = [
        'SO', 'Line', 'Customer', 'Ready Weight', 'RPcs',
        'Grd', 'Size', 'Width', 'Earliest Due', 'Latest Due'
    ]

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Missing required columns after field mapping: {', '.join(missing_cols)}")


def get_planning_whse_column(df) -> str:
    """
    Find the planning warehouse column name in the DataFrame.

    Args:
        df: DataFrame to search

    Returns:
        Column name for planning warehouse, or None if not found
    """
    whse_candidates = ['planning_whse', 'Planning Whse', 'warehouse', 'whse']
    for col in whse_candidates:
        if col in df.columns:
            return col
    return None
