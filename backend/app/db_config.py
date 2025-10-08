"""Database configuration and data source adapters for MS SQL Server integration."""

from __future__ import annotations

from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv
import pyodbc
import pandas as pd
from io import BytesIO

load_dotenv()


class SQLServerConfig:
    """MS SQL Server connection configuration."""

    def __init__(self):
        # e.g., "server.database.windows.net"
        self.server = os.getenv("MSSQL_SERVER")
        self.database = os.getenv("MSSQL_DATABASE")
        self.username = os.getenv("MSSQL_USERNAME")
        self.password = os.getenv("MSSQL_PASSWORD")
        self.port = int(os.getenv("MSSQL_PORT", "1433"))
        self.timeout = int(os.getenv("MSSQL_TIMEOUT", "30"))

    def is_configured(self) -> bool:
        """Check if SQL Server is configured with all required parameters."""
        return all([self.server, self.database, self.username, self.password])

    def test_connection(self) -> bool:
        """Test the connection to SQL Server."""
        if not self.is_configured():
            return False

        try:
            # Build pyodbc connection string
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.server},{self.port};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
                f"TrustServerCertificate=yes;"
                f"Timeout={self.timeout};"
            )
            conn = pyodbc.connect(conn_str, timeout=self.timeout)
            conn.close()
            return True
        except Exception:
            return False


class DataSourceAdapter:
    """Unified adapter for both file upload and direct SQL queries."""

    @staticmethod
    def from_file(file_content: bytes) -> pd.DataFrame:
        """
        Load data from uploaded Excel file.

        Args:
            file_content: Raw bytes of the Excel file

        Returns:
            DataFrame with file contents
        """
        buffer = BytesIO(file_content)
        return pd.read_excel(buffer, engine="openpyxl")

    @staticmethod
    def from_sql_server(
        config: SQLServerConfig,
        query: Optional[str] = None,
        table_name: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load data from SQL Server with optional filtering.

        Args:
            config: SQL Server configuration object
            query: Custom SQL query (takes precedence over table_name)
            table_name: Table name to query (used if query not provided)
            filters: Dict of column:value filters to apply
            limit: Optional row limit (uses TOP N in SQL Server)

        Returns:
            DataFrame with query results

        Raises:
            ValueError: If configuration is invalid
            Exception: If connection or query fails
        """
        if not config.is_configured():
            raise ValueError(
                "SQL Server not configured. Set MSSQL_* environment variables.")

        # Build query based on parameters
        if query:
            # Use custom query as-is
            sql = query
        elif table_name:
            # Build SELECT query from table name
            select_clause = f"SELECT TOP {limit}" if limit else "SELECT"
            sql = f"{select_clause} * FROM {table_name}"

            # Add WHERE clause if filters provided
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    # Basic SQL injection protection - only allow alphanumeric column names
                    if not key.replace('_', '').replace('.', '').isalnum():
                        continue

                    if isinstance(value, str):
                        # Escape single quotes
                        safe_value = value.replace("'", "''")
                        where_clauses.append(f"{key} = '{safe_value}'")
                    elif isinstance(value, (int, float)):
                        where_clauses.append(f"{key} = {value}")
                    elif value is None:
                        where_clauses.append(f"{key} IS NULL")

                if where_clauses:
                    sql += " WHERE " + " AND ".join(where_clauses)
        else:
            raise ValueError("Must provide either 'query' or 'table_name'")

        # Connect and fetch data
        try:
            # Build pyodbc connection string
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={config.server},{config.port};"
                f"DATABASE={config.database};"
                f"UID={config.username};"
                f"PWD={config.password};"
                f"TrustServerCertificate=yes;"
                f"Timeout={config.timeout};"
            )
            conn = pyodbc.connect(conn_str, timeout=config.timeout)

            # Use pandas to read SQL
            df = pd.read_sql(sql, conn)
            conn.close()

            return df

        except Exception as exc:
            raise Exception(f"Failed to query SQL Server: {exc}") from exc
