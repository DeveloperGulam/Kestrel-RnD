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
├── requirements.txt                    # Pinned dependencies (pandas, openpyxl, pytest, streamlit)
├── Kestrel_RnD_Export_2026-05.xlsx     # Source workbook (12 worksheets, READ-ONLY)
│
├── audit_workbook.py                   # Top-level executable audit script
├── audit_report.md                     # Comprehensive Markdown audit report (Milestone 1)
├── audit_report.json                   # Structured JSON audit output (Milestone 1)
│
├── milestone2_system_design.md         # System Architecture & Technical Specifications
├── milestone2_system_design.pdf        # Verified Compiled PDF Deliverable (6 pages)
├── milestone2_draft_design_critique.md # Architectural Critique of 6-Agent Draft
├── milestone2_draft_design_critique.pdf# Verified Compiled PDF Deliverable (2 pages)
├── milestone2_decision_log.md          # Architectural Decision Records (ADRs)
├── milestone2_evaluation_plan.md       # Quality Metrics, Tripwires & Golden Regressions
├── system_workflow.svg                 # Semantic vector sequence workflow diagram
├── render_deliverables_pdf.py          # Automated offline Chrome PDF compilation & page verifier
├── FINAL_REVIEW_REPORT.md              # Comprehensive multi-tier verification report
│
├── app.py                              # Interactive Streamlit R&D Formulation Workbench
├── assistant_audit_log.json            # Cryptographic SHA-256 chained audit trail
├── .streamlit/
│   └── config.toml                     # Streamlit server and theme configuration
│
├── src/
│   ├── kestrel_audit/                  # Milestone 1 audit engine modules
│   │   ├── __init__.py
│   │   ├── loader.py                   # Safe, read-only openpyxl/pandas loader
│   │   ├── schema_inspector.py         # Dimensions, columns, null value auditor
│   │   ├── integrity_auditor.py        # Primary/foreign key uniqueness auditor
│   │   ├── formula_auditor.py          # Stoichiometry, unmapped tokens, ambiguity auditor
│   │   ├── unit_date_auditor.py        # Viscosity (cP vs Pa·s), softness scales, chronology
│   │   ├── pricing_auditor.py          # Pricing feed conflicts, FX conversions, UOM
│   │   ├── cross_sheet_auditor.py      # Cross-sheet contradictions (T-05 stability, T-04 approval)
│   │   ├── report_generator.py         # Formatted Markdown & JSON reporting
│   │   └── cli.py                      # CLI entry point
│   └── kestrel_assistant/              # Milestone 2 assistant core modules
│       ├── __init__.py
│       ├── models.py                   # Pydantic v2 domain schemas & provenance models
│       ├── validator.py                # Deterministic validation engine (Decimal math)
│       ├── evidence_store.py           # Read-only workbook store & indexer
│       ├── recommender.py              # Candidate generation & historical trial loader
│       ├── audit_log.py                # Tamper-evident SHA-256 hash-chained logger
│       └── llm_gateway.py              # LLM gateway & offline fallback parser
└── tests/
    ├── conftest.py                     # Read-only fixtures & hash checks
    ├── test_schema_and_keys.py         # Duplicate keys & missing values
    ├── test_formulations.py            # T-09 103% sum, TEA-esterquat disambiguation
    ├── test_units_and_dates.py         # Viscosity 0.45 Pa·s = 450 cP, softness scales
    ├── test_pricing_integrity.py       # Price_Feed duplicates, RM-170 drum UOM, T-04 costing
    ├── test_cross_sheet_integrity.py   # T-05 stability contradiction, T-11 incomplete trial
    ├── test_rule_level_auditors.py     # Rule-level boundary & synthetic fixture tests
    └── test_assistant_mvp.py           # Formulation assistant MVP regression tests
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
*Executes all **74** automated unit and regression tests (23 workbook-specific assertions + 27 rule-level tests + 24 assistant MVP regression tests), validating data integrity findings, stability criteria, softness scoring, approval semantics, provenance isolation, duplicate prevention, and cryptographic tamper detection in ~0.42 seconds.*

### 6. Compile and Verify Deliverables PDFs
```bash
python render_deliverables_pdf.py
```
*Compiles both `milestone2_draft_design_critique.pdf` (2 pages) and `milestone2_system_design.pdf` (6 pages) with embedded vector SVG diagrams, verifying that both deliverables strictly satisfy the assignment page limits.*

### 7. Launch the Formulation Assistant Web Application (Streamlit MVP)
```bash
streamlit run app.py
```
*Launches the browser-based interactive formulation assistant on `http://localhost:8501`. Enables interactive brief intake, historical trial exploration, live recipe rebalancing with Decimal costing, real-time deterministic validation, provenance inspection, and authenticated chemist bench trial authorization.*

---

## Working MVP: Architecture, Sections & Implementation Boundaries

The repository includes a fully operational browser-based MVP (`app.py`) built with **Streamlit**, **Pydantic v2**, and Python **`Decimal`** fixed-point arithmetic:

### Core Application Sections & Validated Behavior:

1. **Formulation Request Specification:** Natural-language brief intake parser and structured constraint controls (Substrate, active solids 6.0–8.0%, pH 3.5–4.5, viscosity 50–300 cP, cost ceiling $\le \text{₹}22.0/\text{kg}$, prohibited silicones, 4w @ 45°C stability, and softness score $\ge 4.0/5.0$).
2. **Evidence Search & Workbook Explorer:** Read-only inspection of raw workbook records (`RM_Master`, `Price_Feed`, `Trials_TX_Softeners`, `Stability_Log`, `Panel_Scores`, `Regulatory_Notes`). Includes one-click loading of regression trials (`T-04`, `T-05`, `T-09`, `T-10`, `T-11`) to demonstrate failure detection.
3. **Candidate Formulation Studio:** Real-time recipe composition table detailing raw tokens, resolved master codes, trade names, suppliers, concentrations (% w/w), authoritative normalized unit prices, and line cost contributions. Provides interactive disambiguation controls (e.g. resolving `TEA-esterquat` explicitly between `RM-101` and `RM-102`).
4. **Physical & Commercial Metrics [Provenance-Tagged]:**
   - **Total Mass [CALCULATED]:** Stoichiometric sum ($\sum w_i = 100.0\% \pm 0.05\%$) via Python `Decimal`.
   - **Raw Material Cost [CALCULATED]:** Authoritative formula costing from normalized price catalog.
   - **Active Solids [ESTIMATED]:** Component active solids contribution calculated from raw material specs.
   - **Viscosity [ESTIMATED HEURISTIC]:** Brookfield viscosity estimate at 25°C. Physical validation required.
   - **Softness Panel Score [EXPERIMENTALLY MEASURED / UNKNOWN]:** Direct sensory panel rating (1-5 scale). Unmeasured candidates remain `UNKNOWN`.
   - **4-Week 45°C Stability [EXPERIMENTALLY MEASURED / NOT_VERIFIED]:** Incubator test evidence. Unmeasured candidates remain `NOT_VERIFIED`.
5. **Deterministic Validation Engine & Explicit Approval Semantics:**
   - **Status Hierarchy:**
     * `ALL_CRITERIA_VERIFIED_PASS`: All mathematical specifications AND empirical test requirements (stability + softness) verified.
     * `SPEC_PASSED_PENDING_EXPERIMENTAL`: Mathematical, stoichiometric, safety, and costing checks pass, but physical stability and/or softness remain `NOT_VERIFIED` or `UNKNOWN`. Displays: *"READY FOR BENCH TRIAL (Pending Experimental Verification)"*. **Never displays "All validation checks passed".**
     * `REJECTED_WITH_FAILURES`: Active violation of mass balance, prohibited ingredient, cost ceiling, or viscosity interval.
   - **Bench Trial Release vs. Performance Certification:** Approval to conduct a bench trial (`APPROVED_FOR_BENCH`) is explicitly distinguished from commercial performance certification. A candidate can be released for laboratory bench trial testing only with mandatory chemist risk acknowledgement.
   - **Backend Revalidation & Stale Check:** Backend strictly revalidates candidate composition and constraints upon approval request. If candidate composition changes after validation, approval is rejected with a stale report error.
6. **Evidence Traceability & Provenance Isolation:**
   - Every verified empirical result links to its workbook source sheet (`Stability_Log`, `Panel_Scores`), record ID, test conditions, date, and observer.
   - **Evidence Isolation:** Historical test scores (such as `T-06` softness or `T-04` viscosity) are strictly isolated and cannot be silently attributed to newly proposed candidates. New candidates always start with stability `NOT_VERIFIED` and softness `UNKNOWN`.
   - **Visible Price Conflicts:** Multiple price feeds for the same month (e.g. `RM-101` ₹210 vs ₹228) remain visible in warnings and cannot be silently resolved or averaged.
7. **Chemist Review Governance & Tamper-Evident Audit Trail:**
   - **Mandatory Human-in-the-Loop:** Automated physical lab booking is strictly disabled. Requires chemist reviewer identity, role, and authorization notes.
   - **Mandatory Experimental Acknowledgement:** If empirical stability or softness is unverified, chemist must explicitly check the risk acknowledgement checkbox before the approval button unlocks.
   - **Idempotency & Duplicate Prevention:** Detects existing approvals for the same candidate hash and chemist ID to prevent accidental multiple submissions. Legitimate intentional re-approvals require explicit confirmation.
   - **Cryptographic Hash Chaining:** Every log entry computes `entry_hash = SHA-256(canonical_payload)` linked to `prev_hash` of the preceding record. `verify_log_tampering()` verifies chain integrity and detects any file edits or payload modifications.

---

## Known MVP Limitations & Production Readiness

> [!WARNING]
> **Automated Test Passes Do Not Equal Production Readiness**
> While all 74 automated regression tests pass, this repository is an MVP prototype built for technical evaluation. The following boundaries and limitations must be resolved before enterprise deployment:

1. **Simulated Authentication & Credentials:** Chemist identities and sign-offs use simulated local role profiles (`Dr. Vikram Shah`, `CHM-882`). Production deployment requires integration with corporate Identity Providers (IdP) via OIDC/SAML and PKI cryptographic smart-cards (e.g., FIPS 140-2 hardware security modules).
2. **Local File-Based Audit Trail:** The audit log resides in `assistant_audit_log.json`. While protected by SHA-256 hash chaining, an enterprise production deployment must use an immutable, append-only database (e.g., AWS QLDB, Oracle Blockchain Tables, or PostgreSQL with append-only WAL archiving) to prevent filesystem-level tampering.
3. **Static Workbook Data Ingestion:** The current store loads data from `Kestrel_RnD_Export_2026-05.xlsx` in read-only mode. Production deployment requires live, event-driven connectors to SAP/Oracle ERP for real-time purchase prices and LIMS/ELN systems for live bench trial logs.
4. **Heuristic Property Estimations:** Physical property estimates (solids, pH, viscosity) use empirical linear mixing approximations. They serve as pre-screening filters and cannot replace rigorous Quantitative Structure-Property Relationship (QSPR) models or empirical rheological testing.

---

## Disclosure of AI Tool Usage

In compliance with the assignment instructions (*"Use any AI tools you like, and tell us which ones you used and for what"*):
- **Tools Used:** Antigravity AI pair programming assistant (powered by Google DeepMind advanced coding models).
- **Scope of Use:**
  1. *Scaffolding & Drafting:* Generated initial document structures for the system design, critique, decision log, and evaluation plan from human architectural briefs.
  2. *Automated Test Authoring:* Authored synthetic test fixtures (`tests/test_rule_level_auditors.py`, `tests/test_assistant_mvp.py`) to validate boundary conditions, edge cases, and tamper detection.
  3. *Audit & Consistency Verification:* Used for cross-document consistency auditing, formula re-verification, and schema inspection.
- **Engineering Governance:** All calculations, workbook interpretations, safety gates, and architectural decisions were verified against the original workbook `Kestrel_RnD_Export_2026-05.xlsx` using deterministic Python scripts. No external APIs were invoked, and no unverified AI recommendations were accepted without deterministic verification.

