# Architectural Critique: 6-Agent Formulation Platform

**Document Status:** Architectural Evaluation & Review (Milestone 2) | **Scope Limit:** Maximum 2 Pages Rendered  
**Target Proposal:** AI-Generated Draft Design ("Proposed Architecture: Multi-Agent Formulation Platform")

---

## 1. Executive Summary & Prioritized Scorecard

The draft proposal outlines a distributed 6-agent microservice architecture coordinated by an autonomous orchestrator. While it correctly maps the functional workflow of chemical R&D (literature intake, drafting, costing, scheduling), it suffers from **fundamental safety risks, unvalidated data assumptions, and severe operational over-engineering** for an 8-chemist team. Crucially, the draft delegates deterministic calculations, safety determinations, and physical lab bookings to stochastic LLMs.

| Component / Proposal | Priority Rank | Decision | Core Engineering Rationale |
| :--- | :---: | :---: | :--- |
| **Agent 6: Autonomous Lab Booking** | **1 (Critical Safety)** | **REJECT** | Uncalibrated LLM confidence cannot book physical lab assets; risks hazard and lab gridlock. |
| **Agent 3: Synthesizing Missing Data** | **2 (Critical Regulatory)** | **REJECT** | Inventing missing stability creates serious safety & compliance risks; requires data quarantine. |
| **Agent 2: Fuzzy-Merging RM Names** | **3 (Critical Traceability)** | **REJECT** | Conflates distinct chemical grades & suppliers (`RM-101` vs `RM-102` Esterquats); destroys provenance. |
| **Agent 5: LLM Stoichiometry & Costing** | **4 (Critical Quality)** | **REJECT** | Stochastic LLMs fail arithmetic; causes mass-balance failure (`T-09` 103%) & UOM errors (`RM-170`). |
| **Agent 4: Trusting Summary 'Pass' Labels** | **5 (High Operational)** | **CHANGE** | Promotes unapproved (`T-04`) & contradicted (`T-05` phase separation) trials; hides negative data. |
| **Agent 2: Vector DB for Tabular Data** | **6 (Medium Overhead)** | **CHANGE** | Vector embeddings degrade numerical filtering on tiny tabular sets (28 raw materials, 12 trials). |
| **6 Microservices for 8 Chemists** | **7 (Medium Overhead)** | **CHANGE** | Distributed tracing and network latency overhead; replace with a bounded Modular Monolith. |
| **Big-Bang Rollout & Thumbs-Up Loop** | **8 (Low Signal)** | **CHANGE** | Coarse feedback fails to catch silent drift; replace with phased rollout & technical telemetry. |
| **Core Assistant & Literature Search** | **—** | **KEEP** | Structured prompt synthesis and semantic literature retrieval remain valuable accelerators. |

---

## 2. Detailed Technical Findings & Mandated Architectural Changes

### Finding 1: Autonomous Lab Scheduling on Heuristic Confidence (Agent 6) — REJECT
* **Draft Flaw:** Agent 6 books physical incubator/mixer slots when candidate confidence exceeds 0.8, placing the cancellation burden on chemists. Model confidence has zero correlation with physical bench safety.
* **Workbook Evidence:** Lab slots are scarce and cancellations frequent (`BK-2623` cancelled; `BK-2601` corrupted). Automated booking risks physical gridlock, wasted technician prep, and chemical hazards.
* **Mandated Action:** **Eliminate autonomous booking.** The assistant outputs a *draft trial plan*. Instrument reservation is permitted solely after explicit, role-based digital sign-off from an authenticated chemist.

### Finding 2: Synthesizing Missing Stability and Safety Data (Agent 3) — REJECT
* **Draft Flaw:** Agent 3 infers missing stability and skin-safety properties from parametric LLM knowledge to prevent blocked pipeline runs. Inventing missing stability or safety data creates serious safety, compliance, and traceability risks.
* **Workbook Evidence:** Trial `T-11` has missing pH and ongoing stability. For skin-contact softeners containing known sensitizers (`RM-160` isothiazolinones), unverified or fabricated safety properties jeopardize product safety and audit integrity.
* **Mandated Action:** **Enforce strict missing-data quarantine.** Missing measurements must remain explicitly unknown and be quarantined for qualified chemist review. LLMs must never invent synthetic safety passes.

### Finding 3: Fuzzy-Merging Raw Materials and Synonyms (Agent 2) — REJECT
* **Draft Flaw:** Agent 2 automatically merges similar ingredient names via fuzzy matching to produce "one clean list," erasing critical chemical, grade, and supplier distinctions.
* **Workbook Evidence:** In `RM_Master`, `RM-101` (Supplier A, 90% active @ ₹210/kg) and `RM-102` (Supplier B, alternate @ ₹198/kg) share the synonym `TEA-esterquat`. Fuzzy-merging obscures pricing variance, supplier contracts, and active solids content.
* **Mandated Action:** **Prohibit silent merging.** Enforce relational primary keys (`RM-xxx`). When unmapped tokens occur (e.g. `TEA-esterquat` in `T-04`), generate an ambiguity warning requiring explicit chemist disambiguation.

### Finding 4: LLM-Driven Mass Balance and Costing (Agent 5) — REJECT
* **Draft Flaw:** Agent 5 asks the LLM to calculate formulation cost per kg and rebalance ingredient percentages to 100%. Autoregressive token models cannot perform reliable multidimensional arithmetic.
* **Workbook Evidence:** `T-09` already exhibits human error (103.0% sum). LLMs easily miss packaging unit conversions (calculating `RM-170` at ₹32,000/kg instead of ₹160/kg drum basis) or FX rates.
* **Mandated Action:** **Transfer all math to a deterministic Python barrier.** Formulation percentages must be validated using `Decimal` fixed-point math (Σ w_i = 100.0% ± 0.05%). Costs must be computed via relational joins with `Price_Feed` records and historical FX rates (₹84.00/USD).

### Finding 5: Trusting Summary 'Pass' Labels & Suppressing Negative Evidence (Agent 4) — CHANGE
* **Draft Flaw:** Agent 4 promotes candidate formulations by using historical trials marked `Pass` as positive exemplars, completely ignoring negative or failed experiments.
* **Workbook Evidence:** `T-05` is marked `Pass` in `Trials_TX_Softeners`, but raw incubator logs in `Stability_Log` record phase separation at Week 3. `T-04` is ranked #1 in `Summary_Apr` despite zero chemist sign-off (`approved_by = NULL`) and exceeding target viscosity (0.45 Pa·s = 450 cP > 300 cP).
* **Mandated Action:** **Implement Bidirectional Retrieval with Log-Level Verification.** Ground truth must be derived from raw measurement tables, not unverified summary fields. The engine must actively retrieve negative/failed trials (`T-05`), annotating failure boundaries to guide chemists away from dead ends.

### Finding 6: Microservice Architecture & Vector DB for 8 Chemists — CHANGE
* **Draft Flaw:** Running 6 independent microservices and nightly vector DB ingestion for 8 chemists generating ~15 queries/day introduces severe network latency, deployment overhead, and fuzzy numerical retrieval.
* **Workbook Evidence:** Kestrel's dataset comprises only 28 raw materials and 12 trials. Vector embeddings degrade filtering on precise chemical parameters (solids %, pH ranges).
* **Mandated Action:** **Adopt a Modular Monolith.** Deploy a single FastAPI service backed by relational SQLite/PostgreSQL with BM25 keyword search, eliminating microservice RPC and container sprawl.

### Finding 7: Big-Bang Rollout & Coarse Feedback Loops — CHANGE
* **Draft Flaw:** Launching 6 microservices simultaneously with monthly thumbs-up/down feedback creates high integration risk and fails to detect dangerous recipe drift or silent costing errors.
* **Mandated Action:** **Execute a Phased 8-Week Rollout.** Deploy ingestion and deterministic validation gates first. Shadow-pilot with 2 senior chemists in Lab 1, instrumenting granular telemetry on every run.

---

## 3. Architectural Recommendation Summary

The 6-agent draft treats deterministic chemical and mathematical problems as generative text tasks. By replacing distributed microservices with a **Modular Monolith**, enforcing **deterministic Python validation barriers**, and instituting **mandatory human chemist sign-off**, Kestrel establishes an auditable, cost-effective platform ($0.537/chemist/month baseline) ready for reliable laboratory adoption.
