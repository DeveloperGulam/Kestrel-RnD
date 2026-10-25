# Kestrel R&D Formulation Assistant — System Architecture & Data Governance

## Overview
This repository contains the complete engineering deliverables for the **Kestrel R&D Formulation Assistant** assignment (Head of Engineering technical review for Siddharth Carbochem Products Limited / SCPL).

The project is structured into two complementary milestones:
1. **Milestone 1 — Data Quality & Integrity Audit**: A reproducible, deterministic Python audit engine that inspects Kestrel's historical R&D export workbook (`Kestrel_RnD_Export_2026-05.xlsx`, containing 12 worksheets across lab, purchasing, and sales systems), catching critical data flaws, mass-balance violations, unit mismatches, and pricing discrepancies before any AI modeling.
2. **Milestone 2 — System Architecture, Governance & Evaluation**: Architectural design, critique of the 6-agent draft, formal decision log (ADRs), and evaluation plan establishing a robust, auditable AI-assisted R&D workflow with strict deterministic safety boundaries.

---

## Milestone 2 Deliverables Index

| Deliverable | Markdown Source | Compiled PDF Deliverable | Strict Page Limit & Verified Result | Key Focus Areas |
| :--- | :--- | :--- | :--- | :--- |
| **System Design Document** | [`milestone2_system_design.md`](milestone2_system_design.md) | [`milestone2_system_design.pdf`](milestone2_system_design.pdf) | Limit: $\le 6$ pages (**VERIFIED: $\le 6$ pages**) | Modular monolith architecture, structured request intake, hybrid BM25/relational retrieval, deterministic validation engine, Pydantic data contracts, operational rollback protocol, authenticated approval gates, 8-week rollout plan. |
| **Draft Design Critique** | [`milestone2_draft_design_critique.md`](milestone2_draft_design_critique.md) | [`milestone2_draft_design_critique.pdf`](milestone2_draft_design_critique.pdf) | Limit: 1–2 pages (**VERIFIED: 2 pages**) | In-depth critique of the 6-agent draft design; highlights failure modes of autonomous agent loops, vector DB over-engineering, unvalidated pricing, and bypassed human approvals; provides actionable Keep/Change/Reject recommendations. |
| **Architecture Decision Log** | [`milestone2_decision_log.md`](milestone2_decision_log.md) | — | Reference ADRs | Formal ADRs evaluating **Modular Monolith vs. Unmeshed.io vs. Multi-Agent Frameworks** (ADR-001), **Relational SQLite/Postgres vs. Vector DB** (ADR-002), **Deterministic Python Barrier vs. LLM Math** (ADR-003), and **Mandatory Chemist Sign-Off vs. Autonomous Scheduling** (ADR-004). |
| **Evaluation Plan** | [`milestone2_evaluation_plan.md`](milestone2_evaluation_plan.md) | — | Verification Framework | Dual-tier metric taxonomy (Zero-tolerance deterministic vs. statistical LLM), hard failure tripwires, golden workbook regression suite (REG-01 to REG-11), 4-layer testing pyramid, CI/CD pipeline, and drift monitoring. |

*\*Note on Page Limits: Physical page compliance is **VERIFIED**. Both deliverables are compiled to PDF via headless Google Chrome using `render_deliverables_pdf.py`. `milestone2_draft_design_critique.pdf` compiles to exactly **2 pages** (ceiling: 1–2 pages), and `milestone2_system_design.pdf` compiles within the strict $\le 6$ pages ceiling, embedding vector SVG diagrams without raw Mermaid text. Both PDFs strictly satisfy the assignment constraints.*

---

## Core Engineering Principles & Guardrails

1. **Deterministic Separation of Concerns**: Probabilistic LLMs are restricted to request interpretation, unstructured literature extraction, and candidate hypothesis drafting. Deterministic Python code using `Decimal` fixed-point arithmetic authoritatively governs stoichiometry, mass balance ($\sum w_i = 100.0\% \pm 0.05\%$), physical unit conversion, pricing arithmetic, and hard negative constraints. Ordinary binary floating-point math is explicitly rejected for safety-critical checks.
2. **Source Workbook Integrity**: The audit loads the source workbook in read-only mode and compares its SHA-256 hash before and after each run. This verifies that the workbook remained unchanged during that execution; it does not claim permanent immutability or prevent external modifications.
3. **No Silent Merging or Imputation**: Raw materials with overlapping synonyms (e.g. `RM-101` and `RM-102` for `TEA-esterquat`) are flagged for human disambiguation. Missing measurements (e.g. `T-11` pH or in-progress stability) are never assumed to pass.
4. **Mandatory Human Chemist Sign-off**: No automated system is authorized to transition a formulation to physical lab trial scheduling (`APPROVED_FOR_BENCH`) without explicit, authenticated chemist sign-off. Ordinary overrides cannot bypass prohibited ingredients, unresolved identities, invalid mass balances, or required approvals.
5. **Traceable Pricing & Provenance**: Raw material costs cite specific price feed record IDs, date stamps, and packaging conversion factors (e.g., resolving the 200x drum vs. kg distortion on `RM-170`), anchored to the documented historical workbook rate of ₹84.00/USD as of 2026-05-01.

---

## Repository Structure

```
.
├── .venv/                              # Isolated Python 3.13 virtual environment
├── pyproject.toml                      # Packaging & pytest configuration
├── requirements.txt                    # Pinned dependencies (pandas, openpyxl, pytest)
├── Kestrel_RnD_Export_2026-05.xlsx     # Source workbook (12 worksheets, READ-ONLY)
│
├── audit_workbook.py                   # Top-level executable audit script
├── audit_report.md                     # Comprehensive Markdown audit report (Milestone 1)
├── audit_report.json                   # Structured JSON audit output (Milestone 1)
│
├── milestone2_system_design.md         # System Architecture & Technical Specifications
├── milestone2_draft_design_critique.md # Architectural Critique of 6-Agent Draft
├── milestone2_decision_log.md          # Architectural Decision Records (ADRs)
├── milestone2_evaluation_plan.md       # Quality Metrics, Tripwires & Golden Regressions
│
├── src/
│   └── kestrel_audit/
│       ├── __init__.py
│       ├── loader.py                   # Safe, read-only openpyxl/pandas loader
│       ├── schema_inspector.py         # Dimensions, columns, null value auditor
│       ├── integrity_auditor.py        # Primary/foreign key uniqueness auditor
│       ├── formula_auditor.py          # Stoichiometry, unmapped tokens, ambiguity auditor
│       ├── unit_date_auditor.py        # Viscosity (cP vs Pa·s), softness scales, chronology
│       ├── pricing_auditor.py          # Pricing feed conflicts, FX conversions, UOM
│       ├── cross_sheet_auditor.py      # Cross-sheet contradictions (T-05 stability, T-04 approval)
│       ├── report_generator.py         # Formatted Markdown & JSON reporting
│       └── cli.py                      # CLI entry point
└── tests/
    ├── conftest.py                     # Read-only fixtures & hash checks
    ├── test_schema_and_keys.py         # Duplicate keys & missing values
    ├── test_formulations.py            # T-09 103% sum, TEA-esterquat disambiguation
    ├── test_units_and_dates.py         # Viscosity 0.45 Pa·s = 450 cP, softness scales
    ├── test_pricing_integrity.py       # Price_Feed duplicates, RM-170 drum UOM, T-04 costing
    ├── test_cross_sheet_integrity.py   # T-05 stability contradiction, T-11 incomplete trial
    └── test_rule_level_auditors.py     # Rule-level tests with synthetic fixtures
```

---

## Reproducible Setup & Execution Instructions

Follow these five steps to set up the environment and execute the verified audit and test suites:

### 1. Create an Isolated Virtual Environment
```bash
python3 -m venv .venv
```

### 2. Activate the Virtual Environment
```bash
source .venv/bin/activate
```

### 3. Install Pinned Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Data Quality Audit Engine
```bash
python audit_workbook.py
```
*Computes SHA-256 before and after execution to verify that the workbook remained unchanged during execution, and outputs `audit_report.md` and `audit_report.json`.*

### 5. Run the Automated Regression Test Suite
```bash
pytest
```
*Executes all 50 automated unit and regression tests (22 workbook-specific assertions + 28 rule-level tests), validating data integrity findings, stability criteria, and softness scoring in ~0.15 seconds.*

### 6. Compile and Verify Deliverables PDFs
```bash
python render_deliverables_pdf.py
```
*Compiles both `milestone2_draft_design_critique.pdf` (2 pages) and `milestone2_system_design.pdf` (6 pages) with embedded vector SVG diagrams, verifying that both deliverables strictly satisfy the assignment page limits.*

---

## Disclosure of AI Tool Usage

In compliance with the assignment instructions (*"Use any AI tools you like, and tell us which ones you used and for what"*):
- **Tools Used:** Antigravity AI pair programming assistant (powered by Google DeepMind advanced coding models).
- **Scope of Use:**
  1. *Scaffolding & Drafting:* Generated initial document structures for the system design, critique, decision log, and evaluation plan from human architectural briefs.
  2. *Automated Test Authoring:* Authored synthetic test fixtures (`tests/test_rule_level_auditors.py`) to validate boundary conditions and edge cases.
  3. *Audit & Consistency Verification:* Used for cross-document consistency auditing, formula re-verification, and schema inspection.
- **Engineering Governance:** All calculations, workbook interpretations, safety gates, and architectural decisions were verified against the original workbook `Kestrel_RnD_Export_2026-05.xlsx` using deterministic Python scripts. No external APIs were invoked, and no unverified AI recommendations were accepted without deterministic verification.
