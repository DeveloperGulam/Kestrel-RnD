"""
Safe, read-only data loader for Kestrel R&D Excel exports.
Guarantees source file immutability.
"""

from pathlib import Path
from typing import Dict
import openpyxl
import pandas as pd


class ReadOnlyWorkbookLoader:
    """Loads all worksheets from an Excel workbook in strict read-only mode."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"Workbook not found at {self.file_path}")

    @property
    def sheet_names(self) -> list[str]:
        """Returns the list of worksheet names without reading cell values."""
        wb = openpyxl.load_workbook(self.file_path, read_only=True)
        try:
            return wb.sheetnames
        finally:
            wb.close()

    def load_all_sheets(self) -> Dict[str, pd.DataFrame]:
        """
        Loads all worksheets into a dictionary of DataFrames using openpyxl engine.
        Does not mutate the underlying file.
        """
        excel_file = pd.ExcelFile(self.file_path, engine="openpyxl")
        sheets: Dict[str, pd.DataFrame] = {}
        for name in excel_file.sheet_names:
            sheets[name] = pd.read_excel(excel_file, sheet_name=name)
        return sheets

    def load_sheet(self, sheet_name: str, **kwargs) -> pd.DataFrame:
        """Loads a specific sheet in read-only mode."""
        return pd.read_excel(self.file_path, sheet_name=sheet_name, engine="openpyxl", **kwargs)
