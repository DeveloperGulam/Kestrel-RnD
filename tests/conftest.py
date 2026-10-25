"""
Pytest configuration and shared fixtures for Kestrel R&D Data Audit.
Strictly loads the source Excel workbook in read-only mode.
"""

import sys
from pathlib import Path
import pytest

# Ensure src/ is on sys.path
root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from kestrel_audit.loader import ReadOnlyWorkbookLoader
from kestrel_audit.schema_inspector import SchemaInspector
from kestrel_audit.integrity_auditor import IntegrityAuditor
from kestrel_audit.formula_auditor import FormulationAuditor
from kestrel_audit.unit_date_auditor import UnitAndDateAuditor
from kestrel_audit.pricing_auditor import PricingAuditor
from kestrel_audit.cross_sheet_auditor import CrossSheetAuditor


@pytest.fixture(scope="session")
def workbook_path() -> Path:
    path = Path(__file__).resolve().parent.parent / "Kestrel_RnD_Export_2026-05.xlsx"
    assert path.exists(), f"Source workbook not found at {path}"
    return path


@pytest.fixture(scope="session")
def sheets(workbook_path: Path):
    loader = ReadOnlyWorkbookLoader(workbook_path)
    return loader.load_all_sheets()


@pytest.fixture(scope="session")
def schema_inspector(sheets):
    return SchemaInspector(sheets)


@pytest.fixture(scope="session")
def integrity_auditor(sheets):
    return IntegrityAuditor(sheets)


@pytest.fixture(scope="session")
def formula_auditor(sheets):
    return FormulationAuditor(sheets)


@pytest.fixture(scope="session")
def unit_date_auditor(sheets):
    return UnitAndDateAuditor(sheets)


@pytest.fixture(scope="session")
def pricing_auditor(sheets):
    return PricingAuditor(sheets)


@pytest.fixture(scope="session")
def cross_sheet_auditor(sheets):
    return CrossSheetAuditor(sheets)
