# Final Review Report: Evidence-Based Verification Audit
**Assignment:** Kestrel R&D Formulation Assistant — Head of Engineering Assessment  
**Reviewer Role:** Head of Engineering Reviewer  
**Date:** October 2026  
**Status:** Technical & PDF Verification Complete — Ready for Submission  

---

## 1. Executive Summary & Verification Posture

This audit conducted a rigorous, evidence-based verification across all Milestone 1 and Milestone 2 deliverables, the project README, the original Excel export (`Kestrel_RnD_Export_2026-05.xlsx`), and the compiled PDF documents (`milestone2_draft_design_critique.pdf` and `milestone2_system_design.pdf`).

### Verification Findings Summary:
1. **Strict Page Limit Compliance (VERIFIED):**
   - **System Design (`milestone2_system_design.pdf`):** Compiled to **6 pages** (Assignment ceiling: maximum 6 pages) — **PASS**.
   - **Draft Critique (`milestone2_draft_design_critique.pdf`):** Compiled to **2 pages** (Assignment ceiling: maximum 2 pages) — **PASS**.
2. **Visual Workflow Diagram (VERIFIED):**
   - The end-to-end request-to-formulation workflow renders as an actual high-resolution vector SVG diagram (`system_workflow.svg`) rather than raw Mermaid text.
   - All 6 participants, 13 numbered steps, the Deterministic Safety Barrier region, and the Mandatory Chemist Sign-Off Gate are legibly displayed.
3. **Source Workbook Integrity (VERIFIED):**
   - The SHA-256 hash was calculated before and after all audit and test runs: `d64e01af845b13385076bb3cc6aa94485a9bc56159c990a238e64708bd5d2710`.
   - Loaded strictly read-only; zero modification to source records.
4. **Automated Test Suite (VERIFIED):**
   - All **74 automated tests passed in ~0.42 seconds** (74 collected, 74 passed, 0 failed) with exit status `0`.
   - Includes 23 workbook audit regression tests, 27 synthetic rule-level tests, and 24 assistant MVP regression tests (approval semantics, empirical evidence provenance, duplicate prevention, and cryptographic tamper detection).
5. **API Cost Arithmetic (VERIFIED):**
   - Total Monthly Cost (352 requests): $352 \times \$0.0122 = \mathbf{\$4.2944/\text{month}} \implies \mathbf{\$4.29/\text{month}}$.
   - Per Chemist Monthly Cost: $\frac{\$4.2944}{8} = \mathbf{\$0.5368/\text{chemist/month}} \implies \mathbf{\$0.537/\text{chemist/month}}$ (well below the $< \$1.00$ limit).
6. **T-04 Formulation Costing Parity (VERIFIED):**
   - Verified that the non-esterquat 5 ingredients sum to **exactly ₹5.3760/kg** in both the ₹20.076/kg baseline and the ₹21.336/kg sensitivity scenario.

---

## 2. Four-Tier Evidence Categorization Framework

Every technical finding, calculation, and operational claim is classified into one of four distinct evidence tiers:

```
+----------------------------------------------------------------------------------------------------+
|                                    EVIDENCE TIER CLASSIFICATION                                    |
+----------------------------------------------------------------------------------------------------+
| Tier 1: Verified by Executed Commands       | Direct execution of pytest, python scripts, SHA-256  |
| Tier 2: Verified by Manual Source Inspection | Cell-level extraction from original Excel workbook  |
| Tier 3: Estimated or Assumed                | Engineering assumptions, public API pricing rates    |
| Tier 4: Prototype Operational Boundaries    | Live ERP/LIMS integrations, legal regulatory review  |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Tier 1: Verified by Executed Commands

All commands below were executed live during this verification audit within the project's Python 3.13 virtual environment (`.venv/bin/python`).

### 3.1 Physical PDF Compilation & Strict Page Counts
* **Execution Command:** `.venv/bin/python render_deliverables_pdf.py`
* **Execution Engine:** Headless Google Chrome (`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`) rendering Markdown + embedded vector SVG diagrams with professional print typography (A4, 12mm/14mm margins, 8.5pt/1.32 line height, bordered tables, page-break controls).
* **Page Verification Results:**
  * `milestone2_draft_design_critique.pdf`: **2 pages** (Assignment ceiling: 1–2 pages) $\implies$ **PASS**.
  * `milestone2_system_design.pdf`: **6 pages** (Assignment ceiling: $\le 6$ pages) $\implies$ **PASS**.
* **Visual Inspection:** Inspected rendered thumbnails and PDF page streams:
  * No text clipping or overflowing containers.
  * Typography is clean, sharp, and highly legible.
  * All tables fit comfortably within margins.
  * Workflow sequence diagram renders as an actual SVG diagram with color-coded boundaries and crisp vector lines.

### 3.2 Workbook Integrity (Before and After Execution)
* **Pre-Execution Checksum Command:** `shasum -a 256 Kestrel_RnD_Export_2026-05.xlsx`
  * Pre-Run SHA-256: `d64e01af845b13385076bb3cc6aa94485a9bc56159c990a238e64708bd5d2710`
* **Audit Execution Command:** `.venv/bin/python audit_workbook.py`
  * Exit Status: `0`
  * Output: Successfully generated `audit_report.md` and `audit_report.json`.
* **Post-Execution Checksum Command:** `shasum -a 256 Kestrel_RnD_Export_2026-05.xlsx`
  * Post-Run SHA-256: `d64e01af845b13385076bb3cc6aa94485a9bc56159c990a238e64708bd5d2710`
* **Verification Finding:** Pre-run and post-run hashes are **identical**. The source workbook remained strictly unmodified.

### 3.3 Automated Test Suite Execution
* **Execution Command:** `shasum -a 256 Kestrel_RnD_Export_2026-05.xlsx && .venv/bin/pytest -v && shasum -a 256 Kestrel_RnD_Export_2026-05.xlsx`
* **Exit Status:** `0` (Success)
* **Test Count & Results:** **74 passed in ~0.42 seconds** (74 collected, 74 passed, 0 failed, 0 skipped, 0 warnings).
  * 23 workbook-specific regression tests (`test_schema_and_keys.py`, `test_formulations.py`, `test_units_and_dates.py`, `test_pricing_integrity.py`, `test_cross_sheet_integrity.py`).
  * 27 rule-level boundary, edge-case, stability, and softness tests (`test_rule_level_auditors.py`).
  * 24 assistant MVP regression tests (`test_assistant_mvp.py`) covering approval semantics, empirical evidence provenance, duplicate prevention, and cryptographic tamper detection.

### 3.4 Workbook Sheet Inventory Verification
* **Execution Command:** Python `openpyxl.load_workbook("Kestrel_RnD_Export_2026-05.xlsx", read_only=True).sheetnames`
* **Verified Sheet Count:** Exactly **12 worksheets**: `Export_Info`, `RM_Master`, `Price_Feed`, `Trials_TX_Softeners`, `Trials_All_Projects`, `Stability_Log`, `Panel_Scores`, `Customer_Requests`, `Lab_Schedule`, `Regulatory_Notes`, `Summary_Apr`, `Sheet3`.

### 3.5 API Cost Arithmetic Verification
* **Executed Python Decimal Calculation:**
  ```python
  from decimal import Decimal
  requests = Decimal("352")
  cost_per_request = Decimal("0.0122")
  chemists = Decimal("8")

  monthly_total = requests * cost_per_request # Decimal('4.2944')
  monthly_rounded = round(monthly_total, 2)   # Decimal('4.29')
  per_chemist = monthly_total / chemists       # Decimal('0.5368')
  per_chemist_approx = round(per_chemist, 3)  # Decimal('0.537')
  ```
* **Findings:**
  * Total Monthly Cost (352 requests): $352 \times \$0.0122 = \mathbf{\$4.2944/\text{month}}$, which rounds to **$4.29/month**.
  * Cost per Chemist: $\frac{\$4.2944}{8} = \mathbf{\$0.5368/\text{chemist/month}}$, approximately **$0.537/chemist/month** (well below the brief's < $1.00/chemist/month ceiling).
  * High-Volume Scenario (1,760 requests): $1,760 \times \$0.0122 = \mathbf{\$21.472/\text{month}} \to \mathbf{\$21.47/\text{month}}$ total, or $\mathbf{\$2.684/\text{chemist/month}} \approx \mathbf{\$2.68/chemist/month}$.

---

## 4. Tier 2: Verified by Manual Source Inspection

Every workbook finding below was independently verified by directly extracting raw cell values from `Kestrel_RnD_Export_2026-05.xlsx`.

### 4.1 T-04 Costing Re-Verification (₹21.34/kg Sensitivity vs. ₹20.076/kg Baseline)
Inspection of `Trials_TX_Softeners` row 5 (Trial `T-04`) reveals the exact formula composition:
$$\text{TEA-esterquat: } 7.0\%, \quad \text{RM-170: } 1.5\%, \quad \text{RM-120: } 1.0\%, \quad \text{RM-150: } 0.2\%, \quad \text{RM-160: } 0.1\%, \quad \text{RM-180: } 90.2\%$$
Total mass: $7.0 + 1.5 + 1.0 + 0.2 + 0.1 + 90.2 = \mathbf{100.0\%}$.

The table below details the exact ingredient quantities, unit prices, units, conversion rules, and line-item contributions for the **₹21.34/kg sensitivity scenario** (`scenario_4_feed_latest_manual_rm101`) and proves that the **₹20.076/kg baseline** (`scenario_3_feed_latest_auto_rm101`) uses the **exact same price assumptions for all other five ingredients**:

| Ingredient Token | Resolved RM & Description | Qty (% / kg per kg) | Workbook Price & Source | Workbook UOM & Conversion Rule | Effective Price (INR/kg) | Scenario 3 Baseline Line Total (INR/kg) | Scenario 4 Manual Line Total (INR/kg) | Line Delta (INR/kg) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TEA-esterquat** | `RM-101` (Esterquat 90) | **7.0%** (0.070 kg) | Baseline: 210.00 INR (Row 223 auto)<br>Manual: 228.00 INR (Row 179 quote) | kg<br>Direct per kg | Baseline: ₹210.00<br>Manual: ₹228.00 | **₹14.7000**<br>($0.070 \times 210$) | **₹15.9600**<br>($0.070 \times 228$) | **+₹1.2600**<br>($7\% \times 18$) |
| **RM-170** | Polyethylene wax emulsion | **1.5%** (0.015 kg) | 164.00 INR quote (Row 222) / 32,800 INR drum (Row 221) | kg / drum (200 kg)<br>$32,800 / 200 = \text{₹}164/\text{kg}$ | ₹164.00 | **₹2.4600**<br>($0.015 \times 164$) | **₹2.4600**<br>($0.015 \times 164$) | **₹0.0000** (Identical) |
| **RM-120** | Fatty alcohol ethoxylate 7EO | **1.0%** (0.010 kg) | 143.00 INR (Row 193 auto) | kg<br>Direct per kg | ₹143.00 | **₹1.4300**<br>($0.010 \times 143$) | **₹1.4300**<br>($0.010 \times 143$) | **₹0.0000** (Identical) |
| **RM-150** | Acetic acid (glacial) | **0.2%** (0.002 kg) | 61.00 INR (Row 238 auto) | kg<br>Direct per kg | ₹61.00 | **₹0.1220**<br>($0.002 \times 61$) | **₹0.1220**<br>($0.002 \times 61$) | **₹0.0000** (Identical) |
| **RM-160** | Isothiazolinone blend (CMIT/MIT) | **0.1%** (0.001 kg) | 5.50 USD (Row 192 auto) | kg<br>FX Basis: $5.50 \times 84.00$ | ₹462.00 | **₹0.4620**<br>($0.001 \times 462$) | **₹0.4620**<br>($0.001 \times 462$) | **₹0.0000** (Identical) |
| **RM-180** | Water (demineralised) | **90.2%** (0.902 kg) | 1.00 INR (`RM_Master` Row 8) | kg<br>Direct per kg | ₹1.00 | **₹0.9020**<br>($0.902 \times 1.00$) | **₹0.9020**<br>($0.902 \times 1.00$) | **₹0.0000** (Identical) |
| **SUBTOTAL (5 Other Ingredients)** | *Identical across Scenarios 3 & 4* | **93.0%** (0.930 kg) | — | — | — | **₹5.3760** | **₹5.3760** | **₹0.0000** (Exact Parity) |
| **TOTAL FORMULATION COST** | **Trial T-04 Total** | **100.0%** (1.000 kg) | — | — | — | **₹20.0760/kg**<br>(Rounds to **₹20.08/kg**) | **₹21.3360/kg**<br>(Rounds to **₹21.34/kg**) | **+₹1.2600/kg** |

#### Reconciliation Findings:
1. **Identical Baseline Assumptions Confirmed:** The subtotal of the other 5 ingredients is **exactly ₹5.3760/kg** in both Scenario 3 and Scenario 4.
2. **Exact Delta Traced:** The difference between Scenario 3 and Scenario 4 is solely the price difference of `RM-101` (₹228 vs ₹210 = +₹18/kg) multiplied by its verified 7.0% concentration:
   $$0.070 \times \text{₹}18.00 = \mathbf{+\text{₹}1.2600/\text{kg}}$$
   $$\text{₹}20.0760 + \text{₹}1.2600 = \mathbf{21.3360 \text{ INR/kg}} \quad (\to \mathbf{₹21.34/\text{kg}})$$
3. **Rejection of Erroneous ₹22.68/kg Figure:** The previously reported figure of ₹22.68/kg was proven to be an error that mistakenly applied a 15% dosage ($15\% \times 18 = 2.70 \to 19.98 + 2.70 = 22.68$). It is eliminated from all documents.

---

## 5. Tier 3: Estimated or Assumed

1. **Model API Pricing Rates:** Model pricing ($0.15/$0.60 per M tokens for lightweight synthesis; $1.50/$10.00 for prompt-cached models) reflects **public cloud developer rates** and does not reflect negotiated enterprise volume discounts.
2. **Chemist Workload Volume:** The 352 requests/month baseline assumes 1–2 structured customer requests per chemist per day (8 chemists). High-intensity usage (10 queries/day) scales to 1,760 requests/month.
3. **Predicted Physical Properties:** Values in proposed candidate schemas (`estimated_solids_pct`, `estimated_ph`, `estimated_viscosity_cp`) are **engineering heuristics** derived from historical trial averages; formal quantitative structure-property relationship (QSPR) models are out of scope.
4. **Infrastructure Sizing & Hosting Cost:** Modular monolith container hosting (2 vCPU, 4GB RAM) + managed SQLite/PostgreSQL is estimated at $\approx \$60\text{--}\$100/\text{month}$.

---

## 6. Tier 4: Prototype Operational Boundaries

The following items are documented architectural boundaries appropriate for this prototype milestone:
1. **Enterprise Integration Endpoints:** REST connectors to `LabTrack` (LIMS) and `PurchaseOne` (ERP) are proposed architectural contracts; live enterprise endpoints do not exist in the prototype.
2. **Legal Interpretation of Regulatory Notes:** Notes in `Regulatory_Notes` are internal R&D guidance flags and require formal review by SCPL/Kestrel regulatory counsel before commercial dispatch.

---

## 7. Consistency and Verification Checklist

| Target Item | Evidence Checked | Verification Result | Status |
| :--- | :--- | :--- | :---: |
| **Physical PDF Page Limits** | Executed `render_deliverables_pdf.py` | Critique: **2 pages** (limit $\le 2$). System Design: **6 pages** (limit $\le 6$). | **PASS** |
| **Vector Workflow Diagram** | Embedded `system_workflow.svg` in PDF | Renders as crisp visual vector diagram; zero raw Mermaid code. | **PASS** |
| **README Links** | Inspected all links in `README.md` | All 4 links are relative Markdown links (`milestone2_system_design.md`, etc.) and point to existing local files. | **PASS** |
| **Document Status Consistency** | Inspected status headers across all M2 documents | All documents consistently declare "Draft for Review" or "Proposed Architecture". | **PASS** |
| **AI Tool Disclosure** | Inspected `README.md` §6 | Complete and transparent disclosure of Antigravity AI pair programming assistant, detailing scaffolding, test authoring, and deterministic governance. | **PASS** |
| **Workbook Immutability Claim** | Inspected `README.md` and audit scripts | Accurately describes SHA-256 session integrity checks before and after execution; avoids claiming permanent immutability. | **PASS** |
| **Mass-Balance Tolerance** | Cross-checked across design and evaluation plan | Standardized to $100.0\% \pm 0.05\%$ ($[99.95\%, 100.05\%]$) throughout. | **PASS** |
| **USD/INR FX Basis** | Cross-checked across audit engine and M2 docs | Anchored to historical workbook basis of ₹84.00/USD as of 2026-05-01. | **PASS** |

---

## 8. Summary of Changed Files

The following files were updated, synchronized, and compiled during this verification pass:

1. [`milestone2_draft_design_critique.md`](milestone2_draft_design_critique.md): Condensed repetitive prose to fit within exactly 2 rendered pages while preserving all findings, rankings, and workbook evidence.
2. [`milestone2_system_design.md`](milestone2_system_design.md): Structured into an exhaustive, 6-page architectural specification; embedded `system_workflow.svg` for native vector diagram rendering; preserved all Pydantic contracts, Decimal arithmetic, empirical property grounding (4-week 45°C stability and softness panel score ≥ 4/5), validation barrier rules, operational rollback protocol, approval gates, cost models, and 8-week rollout milestones.
3. [`system_workflow.svg`](system_workflow.svg): Clean, semantic vector SVG diagram illustrating the 13-step formulation workflow across all 6 participants.
4. [`render_deliverables_pdf.py`](render_deliverables_pdf.py): Automated, offline-resilient PDF compilation script using headless Google Chrome with strict page limit assertions.
5. [`milestone2_draft_design_critique.pdf`](milestone2_draft_design_critique.pdf): Compiled PDF deliverable (**2 pages**, fully compliant).
6. [`milestone2_system_design.pdf`](milestone2_system_design.pdf): Compiled PDF deliverable (**6 pages**, fully compliant).
7. [`README.md`](README.md): Updated deliverables index table and reproduction instructions with PDF compilation step.
8. [`FINAL_REVIEW_REPORT.md`](FINAL_REVIEW_REPORT.md): Re-structured with verified PDF page counts, four-tier evidence framework, and final submission sign-off.

---

## 9. Final Submission Status

All requirements from the brief and consistency review have been met:
- System Design PDF is **6 pages** ($\le 6$ pages ceiling).
- Critique PDF is **2 pages** (1–2 pages ceiling).
- Workflow sequence diagram is rendered visually as a vector SVG.
- Deterministic validation barrier and chemist sign-off gate are fully documented.
- All 74 tests pass, workbook SHA-256 is unchanged, and cost arithmetic is verified.

**Submission Status: READY FOR SUBMISSION**
