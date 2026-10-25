"""
Command-line interface to execute the full deterministic audit suite.
Usage: python -m kestrel_audit.cli [path_to_excel]
"""

import argparse
import json
import sys
from pathlib import Path
from kestrel_audit.loader import ReadOnlyWorkbookLoader
from kestrel_audit.schema_inspector import SchemaInspector
from kestrel_audit.integrity_auditor import IntegrityAuditor
from kestrel_audit.formula_auditor import FormulationAuditor
from kestrel_audit.unit_date_auditor import UnitAndDateAuditor
from kestrel_audit.pricing_auditor import PricingAuditor
from kestrel_audit.cross_sheet_auditor import CrossSheetAuditor
from kestrel_audit.report_generator import AuditReportGenerator


def compute_sha256(file_path: Path) -> str:
    import hashlib
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_full_audit(workbook_path: str | Path, output_report_path: str | Path = "audit_report.md"):
    wb_file = Path(workbook_path).resolve()
    if not wb_file.exists():
        raise FileNotFoundError(f"Workbook not found at {wb_file}")

    # Step 1: Pre-audit SHA-256 hash
    hash_before = compute_sha256(wb_file)

    # Step 2: Load workbook read-only
    loader = ReadOnlyWorkbookLoader(wb_file)
    sheets = loader.load_all_sheets()

    # Step 3: Run all auditors
    schema_inspector = SchemaInspector(sheets)
    schemas = schema_inspector.audit_all_sheets()

    integrity_auditor = IntegrityAuditor(sheets)
    integrity = integrity_auditor.audit_all()

    formula_auditor = FormulationAuditor(sheets)
    formulations = {
        "tx_softeners": formula_auditor.audit_tx_softeners(),
    }

    unit_date_auditor = UnitAndDateAuditor(sheets)
    units_and_dates = unit_date_auditor.audit_all()

    pricing_auditor = PricingAuditor(sheets)
    pricing = pricing_auditor.audit_all()

    cross_sheet_auditor = CrossSheetAuditor(sheets)
    cross_sheet = cross_sheet_auditor.audit_all()

    # Step 4: Post-audit SHA-256 hash verification
    hash_after = compute_sha256(wb_file)
    assert hash_before == hash_after, f"Source workbook mutated during audit! Before: {hash_before}, After: {hash_after}"

    provenance = {
        "source_file": Path(workbook_path).name,
        "sha256_hash": hash_before,
        "source_unchanged_during_execution": (hash_before == hash_after),
        "execution_integrity_note": "Matching pre- and post-audit SHA-256 hashes confirm the source workbook was unchanged during execution.",
    }

    audit_payload = {
        "provenance": provenance,
        "schemas": schemas,
        "integrity": integrity,
        "formulations": formulations,
        "units_and_dates": units_and_dates,
        "pricing": pricing,
        "cross_sheet": cross_sheet,
    }

    generator = AuditReportGenerator(audit_payload)
    markdown_report = generator.generate_markdown_report()

    report_file = Path(output_report_path)
    report_file.write_text(markdown_report, encoding="utf-8")

    # Also save structured JSON
    json_path = report_file.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_payload, f, indent=2, default=str)

    print(f"Audit completed successfully.")
    print(f"Source file SHA-256 (unchanged during execution): {hash_before}")
    print(f"Markdown report generated at: {report_file.name}")
    print(f"Structured JSON output generated at: {json_path.name}")
    return audit_payload, markdown_report


def main():
    parser = argparse.ArgumentParser(description="Deterministic Audit Suite for Kestrel R&D Excel Exports")
    parser.add_argument("workbook", nargs="?", default="Kestrel_RnD_Export_2026-05.xlsx", help="Path to Excel export")
    parser.add_argument("--output", "-o", default="audit_report.md", help="Output path for markdown audit report")
    args = parser.parse_args()

    run_full_audit(args.workbook, args.output)


if __name__ == "__main__":
    main()
