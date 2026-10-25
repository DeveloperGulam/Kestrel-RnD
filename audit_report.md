# Kestrel R&D Formulation Assistant — Data Governance Audit Report
## Milestone 1: Comprehensive Workbook Inspection & Data Risk Analysis

> **Source Workbook:** `Kestrel_RnD_Export_2026-05.xlsx`  
> **Source File SHA-256 (Verified Read-Only / Unmodified):** `d64e01af845b13385076bb3cc6aa94485a9bc56159c990a238e64708bd5d2710`  
> **Export Metadata:** Generated 2026-05-20 08:14 by `svc_export` (LabTrack v3.2 / PurchaseOne)  

---
## Executive Summary

This data quality audit evaluated the raw export workbook (`Kestrel_RnD_Export_2026-05.xlsx`) to determine whether its historical trial, pricing, and raw material records can safely support an automated R&D formulation assistant. Before developing AI models or autonomous agents, rigorous data governance is required to prevent flawed ingestion from producing unsafe formulations, inaccurate cost projections, or invalid scale-up recommendations.

### Highest-Risk Data Issues Identified
1. **Contradictory Stability Status (`T-05`)**: Worksheet `Trials_TX_Softeners` reports `stability_45c_4wk = 'Pass'`, whereas primary test records in `Stability_Log` document physical phase separation (`phase_sep = 'Y'`, `appearance = 'separated'`) at Week 3 (45 °C).
2. **Premature & Off-Spec Trial Promotion (`T-04`)**: Informal memo `Summary_Apr` recommends `T-04` as Rank #1 for commercial scale-up with an understated cost (₹16.90/kg), despite `T-04` having **no chemist approval** (`approved_by = NULL`), a measured viscosity of **450 cP** (violating customer specification of 50–300 cP), and an unmapped chemical synonym (`TEA-esterquat`).
3. **Stoichiometric Failure (`T-09`)**: Candidate trial `T-09` has recipe percentages summing to **103.00%**, violating mass conservation.
4. **Hard Constraint Violation (`T-10`)**: Trial `T-10` contains silicone emulsion (`RM-140` at 2.0%), directly conflicting with the customer's mandatory *silicone-free* target.
5. **Pricing Ambiguities & Ingestion Traps**: Duplicate active price records for month 2026-05 (`RM-101` @ ₹210 vs ₹228; `RM-170` @ ₹32,800 vs ₹164), unstandardized packaging units (`RM-170` priced per drum rather than per kg, introducing a potential 200x error), and multi-currency mixing (`USD` vs `INR`).
6. **Primary Key Collisions**: Customer request ID `CR-2026-117` is reused across two completely distinct customer briefs (Harbor Knits Textile Softener vs Sunvale Fabrics Paper Detergent); LIMS IDs `L-2025-031` and `L-2025-044` are duplicated in `Trials_All_Projects`.

### Downstream Impact on Assistant Modules
- **Formulation Proposals**: An agent that blindly ingests trials labeled 'Pass' would recommend phase-separating recipes (`T-05`), off-spec high-viscosity recipes (`T-04`), or silicone-contaminated recipes (`T-10`).
- **Cost Calculation**: Relying on unnormalized master list prices produces stale or wildly distorted costs (e.g., treating a ₹32,000 drum price as a per-kg rate, or omitting USD-to-INR conversions).
- **Safety & Regulatory Compliance**: Conflating chemical synonyms (`TEA-esterquat`) obscures raw material sourcing, while failing to cross-reference internal safety notes risks exceeding flammability limits (e.g. `RM-131` isopropanol @ 2.0% in `T-06`).
- **Approval Workflows**: Promoting unapproved trials (`T-04`) undermines LIMS sign-off governance.

### Required Remediation Gates (Pre-requisites for AI Modeling)
The following gates must be enforced in the ingestion pipeline before any automated formulation engine is activated:
1. **Log-Level Truth Gate**: Recipe evaluation must query raw instrument logs (`Stability_Log`, `Panel_Scores`) rather than trusting high-level summary status columns (`stability_45c_4wk`).
2. **Approval Gate**: Any trial where `approved_by` is missing or invalid must be quarantined from positive-exemplar training sets.
3. **Mass-Balance & Unit Validation Gate**: Automatic rejection of recipes not totaling 100.0% ± 0.05% and automated conversion of viscosity (Pa·s to cP) and packaging units (drum to kg).
4. **Deterministic Costing Engine**: Cost calculations must be performed deterministically by code using normalized price feeds, rather than delegating arithmetic to LLM prompts.
5. **No Silent Synonym Merging**: Raw material tokens that match multiple supplier codes (e.g. `TEA-esterquat`) must raise an ambiguous-mapping flag requiring chemist clarification.

---
### 1. Worksheet Inventory, Schema & Completeness

| Worksheet Name | Row Count | Col Count | Missing Values (Nulls) | Status / Classification |
| :--- | :---: | :---: | :--- | :--- |
| `Export_Info` | 18 | 3 | Kestrel Specialty Chemicals - LabTrack / PurchaseOne combined export: 2, Unnamed: 1: 2, Unnamed: 2: 16 | Unstructured Scratchpad |
| `RM_Master` | 28 | 13 | synonyms: 13, notes: 17 | Structured Table |
| `Price_Feed` | 230 | 6 | None (100% complete) | Structured Table |
| `Trials_TX_Softeners` | 12 | 19 | ph: 1, approved_by: 2, notes: 3 | Structured Table |
| `Trials_All_Projects` | 75 | 13 | comments: 39 | Structured Table |
| `Stability_Log` | 111 | 7 | None (100% complete) | Structured Table |
| `Panel_Scores` | 60 | 5 | None (100% complete) | Structured Table |
| `Customer_Requests` | 28 | 8 | constraints: 8 | Structured Table |
| `Lab_Schedule` | 45 | 7 | None (100% complete) | Structured Table |
| `Regulatory_Notes` | 10 | 5 | None (100% complete) | Structured Table |
| `Summary_Apr` | 10 | 5 | TX-SOFT-26 softener project - April review summary: 2, Unnamed: 1: 2, Unnamed: 2: 4, Unnamed: 3: 3, Unnamed: 4: 4 | Unstructured Scratchpad |
| `Sheet3` | 6 | 4 | Unnamed: 0: 6, Unnamed: 1: 3, Unnamed: 2: 5, Unnamed: 3: 5 | Unstructured Scratchpad |

**Key Observations on Workbook Structure:**
- `Sheet3` is an unlabelled scratchpad containing orphaned draft notes (`check`, `7.8`, `T-02?`, `ask MP re batch code`). It must be excluded from automated ingestion.
- `Summary_Apr` is an informal review memo with hardcoded numbers, not a relational table.
- `Export_Info` defines key system provenance and the static FX conversion rate (`1 USD = 84.00 INR`).

---
### 2. Verified Findings (Empirically Confirmed in Source Workbook)

#### A. Duplicate Identifiers & Identifier Collisions
> *Note: Global key uniqueness is evaluated here as a standard relational database assumption.*

- **Table `Trials_All_Projects.lims_id`**: Duplicate identifier values found: `['L-2025-031', 'L-2025-044', 'L-2025-044', 'L-2025-031']`.
- **Table `Customer_Requests.request_id`**: Duplicate identifier values found: `['CR-2026-117', 'CR-2026-117']`.
- **`Customer_Requests` (ID: `CR-2026-117`)**: Key collision across two completely distinct customer projects:
  - Date: `2026-02-18`, Customer: `Harbor Knits`, BU: `Textiles`, Need: `Silicone-free cationic softener for cotton knits`, Status: `Open`, Owner: `Sales-W`
  - Date: `2026-04-23`, Customer: `Sunvale Fabrics`, BU: `Paper`, Need: `Liquid detergent with enzyme stability`, Status: `Closed - lost`, Owner: `Sales-S`
- **`Trials_TX_Softeners` Batch Code Collision**: Batch code `LT-2404-03` was assigned to both trials `['T-07', 'T-08']` with different raw materials (`RM-101` vs `RM-102`), different equipment (`MX-03` vs `MX-05`), and different chemists (`MP` vs `AK`).

#### B. Stoichiometry Failures & Unmapped Ingredient Tokens
- **Trial `T-04`**: Unmapped ingredient string token found: `['TEA-esterquat']`. The token `TEA-esterquat` is a raw text synonym, **not** a recognized primary RM code.
  - **Synonym Ambiguity**: Token `TEA-esterquat` matches multiple raw materials in `RM_Master`: `['RM-101', 'RM-102']` (RM-101 @ 210 INR/kg vs RM-102 @ 198 INR/kg). Silent merging would distort raw material costs and chemical sourcing.
- **Trial `T-06`**: Contains `RM-131` (Isopropanol) at 2.0%, exceeding the 1.0% threshold referenced in internal safety notes (`Regulatory_Notes`).
- **Trial `T-09`**: Stoichiometry percentage sum is **103.0%** (expected 100.00%). Exceeds mass balance tolerance.
- **Trial `T-10`**: Contains `RM-140` (Amino silicone micro-emulsion at 2.0%), directly violating the customer brief target for a 'silicone-free' softener.

#### C. Cross-Sheet Data Contradictions
- **Trial `T-05` Stability Contradiction**:
  - Worksheet `Trials_TX_Softeners` records `stability_45c_4wk` as **`Pass`**.
  - Worksheet `Stability_Log` (Sample `T-05`, Week 3, 45 °C) records `phase_sep = 'Y'` and `appearance = 'separated'`.
  - **Risk**: A naive query relying on `Trials_TX_Softeners` treats `T-05` as a successful baseline despite physical phase separation occurring during incubation.
- **Trial `T-04` Governance & Validation Contradiction**:
  - Worksheet `Summary_Apr` recommends `T-04` as Rank #1: *'Rank 1: Best hand - recommend scale-up (Est RM cost 16.9 INR/kg)'*.
  - Worksheet `Trials_TX_Softeners` reveals `approved_by` is **NULL / Empty** (Unapproved trial).
  - Worksheet `Trials_TX_Softeners` reports viscosity as `0.45 Pa·s` (= **450 cP**), violating the customer target brief of `50–300 cP`.
  - Recipe uses unmapped token `TEA-esterquat` rather than an explicit RM code.

#### D. Pricing Clashes & Packaging Unit Mismatches
- **`Price_Feed` Pricing Conflict for Code `RM-101` in Month `2026-05`**:
  - Price: `228.0 INR`, Source: `email - Supplier A`, Entry Type: `manual`
  - Price: `210.0 INR`, Source: `PurchaseOne`, Entry Type: `auto`
  - Price Delta: **18.0 INR**.
- **`Price_Feed` Pricing Conflict for Code `RM-170` in Month `2026-05`**:
  - Price: `32800.0 INR`, Source: `PurchaseOne`, Entry Type: `auto`
  - Price: `164.0 INR`, Source: `quote per kg`, Entry Type: `manual`
  - Price Delta: **32636.0 INR**.
- **`RM-170` (Polyethylene wax emulsion) Packaging Unit Discrepancy**:
  - In `RM_Master`: `list_price = 32000.0`, `currency = 'INR'`, `uom = 'drum (200 kg)'` (normalized = 160 INR/kg).
  - In `Price_Feed` (2026-05): Entry 1 is `32800.0 INR` (PurchaseOne auto); Entry 2 is `164.0 INR` (manual quote per kg).
  - `Price_Feed` has no UOM column. Ingesting raw price without UOM normalization creates a 200x pricing calculation error.

#### E. Unit of Measure & Date Format Variations
- **Viscosity Units**: Mixed units in `Trials_TX_Softeners` (11 trials in `cP`, 1 trial `T-04` in `0.45 Pa·s`).
- **Softness Scales**: Trial `T-06` uses scale `8/10` in `Trials_TX_Softeners` and scale `1-10` in `Panel_Scores`, whereas all other 11 trials use scale `1-5`.
- **Date Format Mixing**: `Trials_TX_Softeners` mixes ISO (`2026-03-01`), alphanumeric (`12-Apr-26`), and ambiguous slash dates (`04/05/2026`). `Trials_All_Projects` mixes 50 slash dates (`DD/MM/YYYY`) and 25 ISO hyphen dates (`YYYY-MM-DD`).

---
### 3. Auditable Line-Item Cost Breakdown for Trial T-04

`Summary_Apr` (prepared by RS on 2026-04-22) claims that Trial `T-04` has an estimated raw material cost of **₹16.90 / kg**, referencing `RM_Master` list prices. Deterministic recalculation across the five evaluated pricing and sourcing scenarios demonstrates that the actual cost is between **₹19.14 and ₹21.34 / kg**.

#### Line-Item Schedule Across Evaluated Sourcing & Pricing Scenarios

| Component Token | Resolved Code | Ingredient Name | Pct (%) | Baseline Master Price | UOM / Conversion | FX Conversion | Scen 1 (Master + RM-101) | Scen 2 (Master + RM-102) | Scen 3 (Feed Auto + RM-101) | Scen 4 (Feed Quote + RM-101) | Scen 5 (Feed Auto + RM-102) |
| :--- | :---: | :--- | :---: | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `TEA-esterquat` | `RM-101 / RM-102` | Esterquat 90 | 7.0% | ₹210.00 | Direct per kg | None (Already INR) | ₹14.7000 | ₹13.8600 | ₹14.7000 | ₹15.9600 | ₹15.1200 |
| `RM-170` | `RM-170` | Polyethylene wax emulsion | 1.5% | ₹32000.00 | Drum (200 kg) divided by 200 -> per kg | None (Already INR) | ₹2.4000 | ₹2.4000 | ₹2.4600 | ₹2.4600 | ₹2.4600 |
| `RM-120` | `RM-120` | Fatty alcohol ethoxylate 7EO | 1.0% | ₹140.00 | Direct per kg | None (Already INR) | ₹1.4000 | ₹1.4000 | ₹1.4300 | ₹1.4300 | ₹1.4300 |
| `RM-150` | `RM-150` | Acetic acid (glacial) | 0.2% | ₹60.00 | Direct per kg | None (Already INR) | ₹0.1200 | ₹0.1200 | ₹0.1220 | ₹0.1220 | ₹0.1220 |
| `RM-160` | `RM-160` | Isothiazolinone blend | 0.1% | $5.40 USD | Direct per kg | USD 5.40 * 84.00 FX = ₹453.60/kg | ₹0.4536 | ₹0.4536 | ₹0.4620 | ₹0.4620 | ₹0.4620 |
| `RM-180` | `RM-180` | Water (demineralised) | 90.2% | ₹1.00 | Direct per kg | None (Already INR) | ₹0.9020 | ₹0.9020 | ₹0.9020 | ₹0.9020 | ₹0.9020 |

#### Scenario Summary & Reconciliation

| Scenario Identifier | Sourcing & Price Basis | Recalculated Cost | Delta vs Summary_Apr (₹16.90) |
| :--- | :--- | :---: | :---: |
| `scenario_1_rm_master_rm101` | RM_Master list prices resolving TEA-esterquat to RM-101 (Supplier A @ ₹210/kg) | **₹19.98 / kg** | +₹3.08 / kg |
| `scenario_2_rm_master_rm102` | RM_Master list prices resolving TEA-esterquat to RM-102 (Supplier B @ ₹198/kg) | **₹19.14 / kg** | +₹2.24 / kg |
| `scenario_3_feed_latest_auto_rm101` | Price_Feed 2026-05 auto feed with RM-101 (PurchaseOne @ ₹210/kg) | **₹20.08 / kg** | +₹3.18 / kg |
| `scenario_4_feed_latest_manual_rm101` | Price_Feed 2026-05 manual feed with RM-101 (Supplier A email @ ₹228/kg) | **₹21.34 / kg** | +₹4.44 / kg |
| `scenario_5_feed_latest_auto_rm102` | Price_Feed 2026-05 auto feed with RM-102 (PurchaseOne @ ₹216/kg) | **₹20.50 / kg** | +₹3.60 / kg |

#### Detailed Arithmetic Reconciliation Across Evaluated Scenarios
1. **Baseline Scenario 1 (₹19.9756/kg) vs Scenario 3 (₹20.0760/kg, +₹0.1004/kg)**:
   - `RM-101`: Both select ₹210.00/kg (7.0% * 210 = ₹14.7000/kg). No difference.
   - `RM-170` (PE wax): Baseline uses Master ₹160.00/kg (₹32,000/drum / 200). Scenario 3 uses Feed ₹164.00/kg (May 2026 quote per kg / auto drum ₹32,800 / 200). Delta = 1.5% * (164 - 160) = **+₹0.0600/kg**.
   - `RM-120` (Ethoxylate): Baseline uses Master ₹140.00/kg. Scenario 3 uses Feed ₹143.00/kg. Delta = 1.0% * (143 - 140) = **+₹0.0300/kg**.
   - `RM-150` (Acetic acid): Baseline uses Master ₹60.00/kg. Scenario 3 uses Feed ₹61.00/kg. Delta = 0.2% * (61 - 60) = **+₹0.0020/kg**.
   - `RM-160` (Preservative): Baseline uses Master $5.40 USD/kg * 84 = ₹453.60/kg. Scenario 3 uses Feed $5.50 USD/kg * 84 = ₹462.00/kg. Delta = 0.1% * (462.00 - 453.60) = **+₹0.0084/kg**.
   - `RM-180` (Demineralised water): Both use ₹1.00/kg (90.2% * 1.0 = ₹0.9020/kg; water is not tracked in Price_Feed). No difference.
   - **Total Variance**: +₹0.0600 + ₹0.0300 + ₹0.0020 + ₹0.0084 = **+₹0.1004/kg**. Exactly reconciles ₹19.9756 + ₹0.1004 = **₹20.0760/kg (rounds to ₹20.08/kg)**.

2. **Scenario 4 vs Scenario 3 (+₹1.2600/kg)**:
   - `RM-101`: Scenario 4 selects manual Supplier A quote of ₹228.00/kg vs Scenario 3 auto feed of ₹210.00/kg. Delta = 7.0% * (228 - 210) = 7.0% * 18 = **+₹1.2600/kg**.
   - All other 5 ingredients are identical to Scenario 3 (₹5.3760/kg).
   - **Total Variance**: ₹20.0760 + ₹1.2600 = **₹21.3360/kg (rounds to ₹21.34/kg)**.

3. **Scenario 5 vs Scenario 3 (+₹0.4200/kg) and vs Scenario 2 (+₹1.3604/kg)**:
   - `RM-102`: Scenario 5 selects `RM-102` auto feed of ₹216.00/kg vs Scenario 3 `RM-101` auto feed of ₹210.00/kg. Delta = 7.0% * (216 - 210) = 7.0% * 6 = **+₹0.4200/kg** over Scenario 3.
   - Compared to Baseline Scenario 2 (Master `RM-102` @ ₹198.00): `RM-102` increases by ₹18.00/kg (7.0% * 18 = +₹1.2600/kg) plus feed inflation on other ingredients (+₹0.1004/kg) = **+₹1.3604/kg**. Exactly reconciles ₹19.1356 + ₹1.3604 = **₹20.4960/kg (rounds to ₹20.50/kg)**.

**Key Pricing Conflicts & Ambiguities Flagged:**
- **RM-101 Sourcing Conflict**: In `Price_Feed` month `2026-05`, PurchaseOne records ₹210.00/kg (auto), while Supplier A email records ₹228.00/kg (manual quote).
- **RM-102 Sourcing Conflict**: In `RM_Master`, list price is ₹198.00/kg (updated 2025-09-15), while `Price_Feed` month `2026-05` reflects ₹216.00/kg (PurchaseOne auto).
- **RM-170 Packaging Ambiguity**: ₹32,000 / drum in `RM_Master` normalizes to ₹160.00/kg. In `Price_Feed`, row 152 records ₹32,800 without a UOM column, while row 171 records ₹164.00 (quote per kg). Both equate to ₹164.00/kg if drum normalization is applied.
- **RM-160 Currency Conversion**: $5.40 USD/kg converted at 1 USD = 84.00 INR yields ₹453.60/kg, contributing ₹0.4536/kg to the formulation.

**Unresolved Uncertainty (Limitations Requiring Source Clarification):**
> The workbook provides **only the static scalar number ₹16.90** in `Summary_Apr` row 4. It contains **no cell formula, no calculation worksheet, and no line-item reconciliation**. While workbook evidence conclusively proves that across the five evaluated pricing and sourcing scenarios the cost is ₹19.14–₹21.34/kg, the exact reason for the ₹16.90 claim (e.g. whether PE wax was omitted, water was zeroed, or an unrecorded discount was applied) cannot be definitively proven without clarification from the report author (RS).

---
### 4. Suspected Issues & Apparent Inconsistencies Requiring Verification

The following findings represent apparent anomalies or probable system corruptions that require verification with lab managers or IT system owners:

- **Stability_Log (`T-12`)**: Trial T-12 was formulated on 2026-05-13 (7 days before export), yet Stability_Log contains Week 2, Week 3, and Week 4 measurements. Apparent chronology/status inconsistency requiring protocol and LIMS verification.
- **Lab_Schedule (`BK-2601`)**: Booking scheduled for date 2026-05-21 after export 2026-05-20 is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.
- **Lab_Schedule (`BK-2610`)**: Booking scheduled for date 2026-05-21 after export 2026-05-20 is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.
- **Lab_Schedule (`BK-2624`)**: Booking scheduled for date 2026-05-27 after export 2026-05-20 is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.
- **Lab_Schedule (`BK-2636`)**: Booking scheduled for date 2026-06-05 after export 2026-05-20 is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.
- **Lab_Schedule (`BK-2638`)**: Booking scheduled for date 2026-06-05 after export 2026-05-20 is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.

- **SalesDesk CRM Cross-Contamination (`Customer_Requests`)**:
  - Multiple customer requests have mismatched business units (e.g. Bluefield Mills listed under BU `Paper` requesting `Liquid detergent with enzyme stability` [Home Care]; Lotus Paperboard listed under BU `Textiles` requesting `AKD sizing for liner board` [Paper]).
  - *Probable Cause*: SalesDesk export routine corrupted foreign key dropdown mapping.

---
### 5. Analytical Assumptions & Interpretation Boundaries

1. **Regulatory Notes as Internal Guidance, Not Legal Conclusions**:
   - Entries in `Regulatory_Notes` (e.g. `RM-121` restriction under REACH/OEKO-TEX, `RM-160` sensitizer threshold, `RM-131` 1% flammability threshold) are treated strictly as internal guidance notes recorded by Kestrel's regulatory team and safety officer. They are not treated as independently verified external legal conclusions.
2. **Global Key Uniqueness as an Audit Assumption**:
   - Uniqueness of `trial_id` in `Trials_TX_Softeners`, `lims_id` in `Trials_All_Projects`, and `request_id` in `Customer_Requests` is evaluated as an architectural assumption for relational integrity. The workbook itself does not enforce primary key constraints.
3. **FX Conversion Baseline**:
   - All currency conversions assume `1 USD = 84.00 INR` as documented in `Export_Info` row 5.
4. **No Imputation of Missing Data**:
   - Incomplete trials (such as `T-11`, in week 2 with missing pH) are treated strictly as incomplete; no automated assumption of passing is permitted.