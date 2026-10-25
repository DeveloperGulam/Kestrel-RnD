"""
Schema and Nullability Inspector for all workbook sheets.
Reports columns, total rows, non-empty rows, null distributions, and unstructured sheets.
"""

from typing import Any, Dict, List
import pandas as pd


class SchemaInspector:
    """Audits structural integrity, columns, and missingness across all worksheets."""

    def __init__(self, sheets: Dict[str, pd.DataFrame]):
        self.sheets = sheets

    def audit_all_sheets(self) -> Dict[str, Any]:
        """Performs structural audit for every sheet."""
        report: Dict[str, Any] = {}
        for name, df in self.sheets.items():
            report[name] = self.audit_sheet(name, df)
        return report

    def audit_sheet(self, sheet_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Audits a single sheet's dimensions, columns, and missing values."""
        total_rows = len(df)
        total_cols = len(df.columns)
        columns = [str(c) for c in df.columns]

        # Count unnamed / blank columns
        unnamed_cols = [c for c in columns if c.startswith("Unnamed:")]

        # Null analysis per column
        null_counts = df.isnull().sum().to_dict()
        columns_with_nulls = {
            str(col): int(count) for col, count in null_counts.items() if count > 0
        }

        # Check if entirely empty rows exist
        completely_empty_rows = int(df.isnull().all(axis=1).sum())

        is_scratch_or_unstructured = (
            sheet_name in ["Sheet3", "Summary_Apr", "Export_Info"]
            or len(unnamed_cols) >= (total_cols / 2)
        )

        return {
            "sheet_name": sheet_name,
            "row_count": total_rows,
            "column_count": total_cols,
            "columns": columns,
            "unnamed_column_count": len(unnamed_cols),
            "unnamed_columns": unnamed_cols,
            "completely_empty_rows": completely_empty_rows,
            "missing_values": columns_with_nulls,
            "is_unstructured_or_scratch": is_scratch_or_unstructured,
        }
