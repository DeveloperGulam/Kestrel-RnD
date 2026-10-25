# System Design: Kestrel R&D Formulation Assistant

**Document Status:** Proposed Engineering Architecture (Draft for Review)  
**Author:** Candidate for Head of Engineering  
**Target System:** Kestrel Specialty Chemicals R&D Platform  
**Scope Limit:** Maximum 6 Pages Rendered (Strict Brief Constraint)

---

## 1. Problem Definition & Requirements

### 1.1 Context & Problem Statement
Kestrel Specialty Chemicals manufactures performance chemicals across textiles, home care, and paper. Its R&D organization comprises 8 formulation chemists operating across two physical laboratories. Today, customer-driven formulation projects require 3–4 weeks of manual desk research: searching fragmented network drives, cross-referencing raw material (RM) price sheets, conducting ad-hoc literature searches, and manually calculating active solids and stoichiometry in spreadsheets.

Kestrel requires an **AI-Assisted R&D Formulation Assistant** to compress desk-research cycle time from **weeks to days**, guiding chemists from an unconstrained customer brief to an approved initial trial plan.

### 1.2 Requirements Breakdown
* **Business & User Requirements:**
  - *Interactive Intake:* Transform unstructured briefs into structured targets (e.g. solids 6.0–8.0%, pH 3.5–4.5, viscosity 50–300 cP, max cost ₹22.0/kg, silicone-free, 4-week 45°C stability with no separation/yellowing, softness panel score ≥ 4/5).
  - *Evidence Retrieval:* Surface relevant historical trials and literature with explicit record-level provenance.
  - *Candidate Proposal:* Generate 2–3 candidate recipes with technical rationale and auditable cost schedules.
  - *Draft Trial Plan:* Output actionable lab protocols (equipment, addition order, mixing speeds) ready for bench execution.
  - *Chemist Governance:* **Strict human-in-the-loop authorization; zero automated physical lab bookings.**
* **Functional Requirements:**
  - *Deterministic vs. Empirical Boundary:* Enforce mass balance (100.0% ± 0.05%), unit normalization, hard constraints, and raw material costing in pure Python using `Decimal` fixed-point arithmetic—**never in LLM text generation or binary float math**. Distinguish deterministic formulation constraints from empirical properties (thermal stability, sensory softness) requiring laboratory testing. Missing/incomplete measurements must remain `UNKNOWN` or `NOT_VERIFIED`; generative LLMs must never assert empirical passes without physical lab records.
  - *Identity Resolution:* Resolve chemical synonym tokens (`TEA-esterquat`) to primary supplier codes (`RM-101` vs `RM-102`), flagging ambiguous mappings rather than silently merging them.
  - *Data Cross-Referencing:* Ingest trial data, monthly price feeds, and regulatory notes while quarantining unapproved (`T-04`), physically contradicted (`T-05`), or incomplete (`T-11`) trials.
* **Non-Functional Requirements:**
  - *Traceability:* Every suggested component percentage must trace to a specific trial ID, price feed record, or citation.
  - *Latency Target (Proposed):* End-to-end response ≤ 15s (p95 ≤ 12s; unmeasured in prototype); internal deterministic rules execute in < 50ms.
  - *Security & IP:* Strict tenant isolation; zero proprietary chemical formulations used for public LLM training.
  - *Cost Ceiling:* Departmental model API budget strictly < $1.00 per chemist/month (< $8.00/month for 8 chemists).

### 1.3 Scope Boundaries & Design Assumptions
* **In Scope:** Structured request parsing, candidate recipe generation, deterministic validation, cost calculation, audit logging, and chemist approval workflow.
* **Out of Scope:** Direct machine execution, automatic ERP purchase orders, autonomous instrument scheduling.
* **Core Assumption:** Historical workbooks represent noisy legacy data requiring validation barriers; regulatory notes represent internal guidance flags requiring chemist confirmation, not definitive legal conclusions.

---

## 2. System Architecture: The Modular Monolith

Rather than deploying an over-engineered multi-agent microservice architecture for 8 chemists, the platform is designed as a **Modular Monolith with Deterministic Safety Gates**. Probabilistic LLMs handle linguistic parsing and creative recipe hypothesis drafting, while deterministic Python services govern stoichiometry, unit conversions, costing, and safety enforcement.

| Architectural Layer | Core Technology | Primary Responsibility |
| :--- | :--- | :--- |
| **Chemist Web Workspace** | React / TypeScript SPA | Brief intake, evidence inspection, recipe adjustment, role-based digital sign-off. |
| **Orchestration Layer** | FastAPI (Python 3.11+) | Workflow state machine, prompt assembly, bounded retry loops, diagnostic reporting. |
| **Inference Gateway** | Tiered Model Router | Structured JSON parsing (lightweight model) & candidate drafting (prompt-cached model). |
| **Deterministic Barrier** | Python `Decimal` Engine | Mass balance (± 0.05%), unit conversion, constraint enforcement, and price joins. |
| **Data & Evidence Store** | PostgreSQL / SQLite | Relational storage for 12 ingested workbook sheets, BM25 text index for notes/patents. |
| **Audit & Governance** | Append-Only Table | Tamper-evident session logging with SHA-256 state hashes and chemist approval tokens. |

---

## 3. End-to-End Formulation Workflow

The workflow enforces a strict boundary between generative drafting and physical lab execution. Retries on deterministic failure are bounded (maximum 2 attempts) before graceful pipeline termination.

<div align="center">
  <img src="system_workflow.svg" alt="System Workflow Sequence Diagram" width="100%" style="max-height: 320px; margin: 4px 0;" />
</div>

### Operational Workflow Stages
1. **Intake & Target Structuring:** Natural language requests are parsed into quantitative ranges: solids [6.0, 8.0]%, pH [3.5, 4.5], viscosity [50, 300] cP, max cost ₹22.0/kg, silicone prohibited, 4-week 45°C stability (zero phase separation/yellowing), and softness panel score ≥ 4/5.
2. **Bidirectional Evidence Retrieval:** Simultaneously queries passing project benchmarks (`TX-SOFT-26`) and failed/contradictory trials (`T-05` phase separation at Week 3; `T-11` missing data) with defect causes attached, preventing the model from re-exploring documented chemical failures.
3. **Evidence-Conditioned Synthesis:** LLMs generate candidate recipes containing only valid raw material tokens, explicitly prohibited from imputing unmeasured properties.
4. **Deterministic Validation Boundary:** Enforces the 6 automated safety checks. Flags unmeasured empirical properties as `NOT_VERIFIED` / `UNKNOWN`. If validation fails after 2 retries, the pipeline terminates and displays diagnostic logs; unconditional fallback to historical recipes is prohibited.
5. **Chemist Review & Sign-Off:** Chemist inspects ingredient provenance, adjusts active ratios, and provides authenticated digital authorization. Autonomous equipment booking is strictly locked out.

---

## 4. Evidence Strategy & Data Contracts

### 4.1 Data Contracts (Pydantic v2)
```python
from decimal import Decimal
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field

class TargetSpecification(BaseModel):
    project_code: str; target_substrate: str; silicone_allowed: bool = False
    solids_pct_range: Tuple[Decimal, Decimal] = (Decimal("6.0"), Decimal("8.0"))
    ph_range: Tuple[Decimal, Decimal] = (Decimal("3.5"), Decimal("4.5"))
    viscosity_cp_range: Tuple[Decimal, Decimal] = (Decimal("50.0"), Decimal("300.0"))
    max_cost_inr_per_kg: Decimal = Decimal("22.0")
    min_softness_panel_score: Decimal = Decimal("4.0")  # Sensory panel scale 1-5
    target_stability_weeks_at_45c: int = 4              # 4w @ 45C: no separation/yellowing

class FormulationComponent(BaseModel):
    raw_token: str; resolved_rm_code: Optional[str] = None
    percentage: Decimal; effective_price_inr_per_kg: Decimal
    cost_contribution_inr: Decimal; is_ambiguous_synonym: bool = False

class CandidateFormulation(BaseModel):
    candidate_id: str; recipe: List[FormulationComponent]
    total_percentage: Decimal; total_rm_cost_inr: Decimal
    estimated_solids_pct: Decimal  # Authoritative solids mass balance (Decimal)
    estimated_ph: float            # Heuristic estimate (float, QSAR out of scope)
    estimated_viscosity_cp: float  # Heuristic estimate (float, bench validation needed)
    # Empirical properties (require physical testing; never LLM-hallucinated):
    stability_45c_4w_status: str = "NOT_VERIFIED"  # "PASS", "FAIL", "NOT_VERIFIED" (no separation/yellowing)
    softness_panel_score: Optional[Decimal] = None  # Scale 1-5; None/UNKNOWN if unmeasured
    evidence_citations: List[str]; compliance_flags: List[str]
    is_approved_by_chemist: bool = False
    approving_chemist_id: Optional[str] = None
```
*Data Type & Empirical Property Architecture:* All stoichiometry, active solids, formulation percentages, raw material prices, cost contributions, total recipe costs, and mass-balance checks operate strictly via Python `Decimal` fixed-point math without intermediate binary float rounding. Non-authoritative heuristic property estimates (`estimated_ph`, `estimated_viscosity_cp`) remain typed as `float`. Empirical properties (`stability_45c_4w_status`, `softness_panel_score`) require physical incubator and sensory panel test data; missing or incomplete measurements remain explicitly `UNKNOWN` or `NOT_VERIFIED` and cannot be claimed passed by generative text.

### 4.2 Retrieval Strategy: Relational SQL + BM25 vs. Vector DB
The draft proposal's nightly vector database is rejected for Kestrel's workload:
* **Small Data Corpus & Exact Filtering:** 28 raw materials and 12 project softener trials require strict numerical interval filtering (viscosity in [50, 300] cP, pH in [3.5, 4.5]) where vector embeddings degrade.
* **Relational Integrity:** Queries require exact joins across physical incubator logs (`Stability_Log`) and monthly pricing feeds (`Price_Feed`).
* **Selected Architecture:** Relational **PostgreSQL/SQLite** tables with **BM25 full-text indexing** over regulatory notes and chemical literature.

---

## 5. Validation, Safety & Governance Gates

| Gate | Validation Scope | Rule & Tolerance | Failure Mode Action |
| :--- | :--- | :--- | :--- |
| **Gate 1: Mass Balance** | Active solids & total formula sum | Σ w_i = 100.0% ± 0.05% (fixed-point `Decimal`) | Rejects malformed formulations (e.g. `T-09` 103.0% sum). |
| **Gate 2: Ingredient Resolution** | Chemical identity & supplier code | Primary key `RM-xxx`; flag synonym ambiguities | Disambiguates `RM-101` vs `RM-102` (`TEA-esterquat` in `T-04`). |
| **Gate 3: Hard Constraints** | Regulated & prohibited compounds | Silicone = 0.0% (strict ban); Isopropanol ≤ 1.0% | Hard block on prohibited compounds; advisory warnings. |
| **Gate 4: Cost Normalization** | Commercial pricing & packaging units | Active `Price_Feed` join on `RM-xxx`; FX ₹84.00/USD | Normalizes drum units (`RM-170` ₹32,000/200kg = ₹160/kg). |
| **Gate 5: Evidence Trust** | Historical trial & empirical validation | Ingest incubator logs & sensory panel records | Quarantines unapproved (`T-04`), phase-separated/yellowed (`T-05`), incomplete (`T-11`), and unmeasured softness cases as `NOT_VERIFIED` / `UNKNOWN`. |
| **Gate 6: Chemist Sign-Off** | Human governance barrier | Authenticated role-based digital signature | Mandatory chemist authorization; zero automated lab booking. |

1. **Mass Balance Gate:** Enforces Σ w_i = 100.0% ± 0.05% using fixed-point `Decimal` math; rejects malformed formulations (`T-09` 103.0%).
2. **Ingredient Resolution Guard:** Maps raw tokens to master IDs; flags ambiguous synonyms (`RM-101` Supplier A vs `RM-102` Supplier B for `TEA-esterquat`).
3. **Hard Constraint Filter:** Blocks recipes with prohibited compounds (silicone = 0.0%); raises warnings on advisory limits (`RM-131` isopropanol ≤ 1.0%).
4. **Deterministic Costing Engine:** Evaluates active prices from `Price_Feed`, normalizing packaging units (₹32,000 / 200 kg = ₹160/kg for `RM-170` on drum basis) and currency ($1 USD = ₹84.00 historical basis); rejects unverified static scalar claims (`Summary_Apr` ₹16.90/kg).
5. **Evidence Trust & Empirical Quarantine:** The assistant is strictly prohibited from claiming thermal stability or sensory softness without supporting empirical test records. Stability requires verified 4-week 45°C logs with zero phase separation and zero yellowing; incomplete (`T-11`) or contradicted (`T-05`) trials are quarantined as `NOT_VERIFIED`. Softness requires verified panel testing (≥ 4/5); missing panel scores remain `UNKNOWN`. Generative imputation of physical or sensory pass labels is forbidden.
6. **Chemist Sign-Off Gate:** State transition to `APPROVED_FOR_BENCH` requires authenticated role-based digital signature; autonomous lab instrument scheduling is strictly prohibited.

---

## 6. Integration, Security & Production Operations

### 6.1 Proposed System Interfaces
* **LabTrack LIMS Interface (Proposed):** REST API / Read-Only Replica. Reads historical trials and equipment schedules; emits approved draft protocols for bench execution.
* **PurchaseOne ERP Interface (Proposed):** Read-only webhook / daily export. Pulls active supplier price feeds and currency exchange rates.
* **Literature Gateway (Proposed):** Caching wrapper over Crossref / arXiv / PubMed APIs for textile chemistry research.

### 6.2 Security, Governance & Role-Based Access Control
* **Role-Based Permissions:**
  - *Bench Chemist:* Submit briefs, inspect evidence, modify recipe proportions, sign off trial plans.
  - *Lead Chemist / Lab Manager:* Update advisory tolerances, resolve alias ambiguities, adjust list prices.
  - *System Administrator:* Manage API credentials, inspect audit trails, monitor telemetry.
  - *Strict Governance Boundaries:* No user role (including Lab Manager or Admin) can bypass prohibited chemical exclusions (silicone ban), unresolved ingredient collisions, invalid mass balance, or mandatory chemist sign-off.
* **Data Protection & Privacy (Proposed):** Enterprise Zero Data Retention agreements with LLM vendors. Encrypted in transit (TLS 1.3) and at rest (AES-256).

### 6.3 Observability, Telemetry & Audit Trail
* **Tamper-Evident Session Log:** Records brief inputs, retrieved trial IDs, candidate recipes, deterministic validation metrics, active configuration version hashes, and approving chemist ID in an append-only relational audit table with SHA-256 session integrity checks.
* **Telemetry & Drift Alerting:** Prometheus + Grafana dashboard tracking request latency, token consumption, and validation rejection rates. Triggers alert if rejection rate exceeds 15% in a rolling 1-hour window.

### 6.4 Operational Rollback & Incident Recovery Protocol
When production anomalies or safety regressions occur, the platform follows an explicit 6-step recovery protocol:
1. **Detection:** Automated monitors detect safety-barrier breaches (e.g. mass-balance breach > 0.05%, silicone leakage, corrupted price/raw-material ingestion), severe model extraction regression, or application faults.
2. **Immediate Containment (Circuit Breaker):** If deterministic safety checks or pricing/evidence data cannot be trusted, the orchestrator immediately **shuts down candidate generation** and places the system in a **safe, read-only state**. Chemists can query historical records, but new recipe drafting and export endpoints are hard-blocked.
3. **Version Reversion:** Application and model gateway configurations revert to the last known-good immutable release tag; data indices roll back to the previous verified relational snapshot and BM25 index.
4. **Evidence & Audit Preservation:** Immutable audit logs, failed inputs, validation diagnostics, active model/data version hashes, and incident timestamps are preserved in tamper-evident storage for root-cause analysis.
5. **Engineering Verification:** Candidate generation remains disabled until engineering executes the full golden regression suite (REG-01 through REG-11) and achieves 100% deterministic pass in staging.
6. **Governance Review & Re-Activation:** Normal operation resumes only after joint sign-off by Lead Systems Engineer and Lead Formulation Chemist. Rolling back a model or configuration **can never override or bypass deterministic validation gates or mandatory chemist approval**.

*Incident Trigger Matrix:*
* **Immediate Generation Shutdown (Circuit Breaker):** Triggered by deterministic barrier bypass, prohibited chemical leakage, unverified data corruption in `Price_Feed`/`RM_Master`, or mass-balance failure. Candidate generation halted immediately.
* **Warning & Ordinary Rollback:** Triggered by elevated latency (p95 > 15s), minor prompt extraction schema retry spikes, or non-breaking UI defects. Addressed via standard blue-green rollback without disabling read-only workspace functions.

---

## 7. Cost Analysis & 8-Week Implementation Roadmap

### 7.1 Operating Cost Model (8 Chemists) & Target Reconciliation

*Model pricing reflects published cloud developer benchmarks. Baseline workload assumes structured customer formulation briefs.*

| Cost Parameter | Option A: Tiered Routing (Recommended) | Option B: Un-Tiered Frontier Model |
| :--- | :--- | :--- |
| **Pipeline Step 1 (Intake)** | GPT-4o-mini / Haiku ($0.15/$0.60 per M) → **$0.00041/req** | Frontier ($3.00/$15.00 per M) → **$0.01200/req** |
| **Pipeline Step 2 & 4 (Rules)** | Python Deterministic Code → **$0.00000/req** | Python Deterministic Code → **$0.00000/req** |
| **Pipeline Step 3 (Synthesis)** | Prompt-Cached GPT-4o / Haiku → **$0.01175/req** | Un-cached Frontier Model → **$0.02250/req** |
| **Composite Request Cost** | **$0.01216 ≈ $0.0122 / request** | **$0.03450 / request** |
| **Monthly Cost (352 req/mo)** | **352 requests/month × $0.0122/request ≈ $4.29/month** | 352 requests/month × $0.0345/request ≈ $12.14/month |
| **Cost per Chemist / Month** | **$4.29 ÷ 8 ≈ $0.537 / chemist/month** | $12.14 ÷ 8 ≈ $1.52 / chemist/month |
| **Baseline Budget Status** | **SATISFIED (Meets < $1.00/chemist/month target; 46.3% margin)** | **FAILED ($0.52 over budget ceiling; +52% overrun)** |
| **Higher-Volume Scenario (1,760 req)** | **1,760 requests/month × $0.0122/request ≈ $21.47/month** | 1,760 requests/month × $0.0345/request ≈ $60.72/month |
| **Higher-Volume Cost / Chemist** | **$21.47 ÷ 8 ≈ $2.68 / chemist/month** | $60.72 ÷ 8 ≈ $7.59 / chemist/month |
| **Higher-Volume Budget Status** | **EXCEEDS BUDGET TARGET ($2.68 vs $1.00 target; +168% overrun)** | **EXCEEDS BUDGET TARGET ($7.59 vs $1.00 target; +659% overrun)** |
| **Departmental Infrastructure (Hosting)** | AWS ECS / DigitalOcean container + DB: **≈ $60–$100 / month** | Same infrastructure: **≈ $60–$100 / month** |
| **Total Departmental Spend (Baseline + Infra)** | **≈ $65–$105 / month total departmental spend** | **≈ $72–$160 / month total departmental spend** |

* **Cost Assumptions & Estimates:** Token counts (Intake: ~800 in / 350 out; Synthesis: ~3,500 in / 1,200 out), model unit prices, request volumes (352 baseline vs 1,760 higher-volume), and prompt caching hit rates are engineering estimates rather than measured production figures.
* **Separation of API vs. Infrastructure:** Variable LLM API costs ($4.29/month baseline) are tracked separately from fixed cloud infrastructure ($60–$100/month hosting & database).
* **Budget Target Reconciliation:** The baseline workload of 352 requests/month (44 requests/chemist/month across 8 chemists) achieves $0.537/chemist/month, successfully satisfying the departmental < $1.00/chemist/month API budget target. The higher-volume scenario of 1,760 requests/month (220 requests/chemist/month) reaches $2.68/chemist/month, which **exceeds the $1.00/chemist/month budget ceiling** and requires query rate-limiting or prompt token caps if sustained.

<div style="page-break-before: always;"></div>

### 7.2 8-Week Phased Implementation Roadmap (Team of 3 Engineers)

| Sprint | Timeline | Key Engineering Deliverables | Milestones & Success Criteria |
| :---: | :---: | :--- | :--- |
| **Sprint 1** | Weeks 1–2 | Relational schema migration (12 sheets), Python deterministic engine (`Decimal` stoichiometry, UOM/FX converters). | Zero mass-balance leaks; 100% pass on historical integrity suite. |
| **Sprint 2** | Weeks 3–4 | Request intake parser, SQL/BM25 retrieval engine, tiered LLM gateway with constrained Pydantic output schemas. | Validated JSON extraction; bidirectional retrieval operational. |
| **Sprint 3** | Weeks 5–6 | Chemist web workspace, candidate comparison UI, append-only audit logging, authenticated sign-off workflow. | Complete end-to-end flow; zero automated lab bookings. |
| **Sprint 4** | Weeks 7–8 | Week 7: Shadow pilot with 2 senior chemists (Lab 1) & formal exit-gate review. Week 8: Target rollout across all 8 chemists ONLY IF all exit criteria pass; otherwise dedicated to remediation, regression testing & retesting. | Target schedule contingent on exit gate; 100% exit criteria met & 2-chemist sign-off before wider rollout; unresolved critical defects defer rollout (safety never bypassed for schedule). |

#### Sprint 4 Pilot Exit Gate & Remediation Protocol
The 8-week implementation plan serves as a **target engineering schedule**, not an unconditional rollout deadline. Organization-wide rollout to all 8 chemists across both laboratories is permitted only after every documented acceptance criterion passes and both pilot senior chemists provide documented sign-off:
1. **Critical Safety & Prohibited Ingredients:** 100% pass rate on silicone exclusion and advisory threshold regression suites (`RM-140` block, `RM-131` warning).
2. **Deterministic Calculation Integrity:** 100% pass rate on `Decimal` mass-balance (100.0% ± 0.05%), unit conversion, and costing reference benchmarks.
3. **Evidence Integrity & Quarantine:** Missing (`T-11`), ambiguous (`RM-101/102`), and contradictory (`T-05`) evidence correctly flagged and quarantined rather than silently accepted.
4. **Empirical Property Grounding:** 100% pass rate on stability (4w @ 45°C: zero phase separation/yellowing) and softness (panel score ≥ 4/5) regression suites; unverified or incomplete records quarantined as `UNKNOWN` / `NOT_VERIFIED`.
5. **Chemist Governance Enforcement:** Mandatory authenticated role-based digital signature enforced on every recommendation; zero autonomous lab bookings emitted.
6. **Pilot User Acceptance Sign-Off:** Both pilot senior chemists formally review and sign off on recommendation quality and UI workflow usability; unresolved critical defects block wider rollout.

**Remediation, Retest & Deferral Policy:** Week 7 is strictly dedicated to the 2-chemist shadow pilot and formal exit-gate evaluation. Week 8 is held available for remediation, regression testing, and retesting against the 50-test regression suite (spanning the 11 named golden regression scenarios, REG-01 through REG-11) if any acceptance criterion fails or critical defects emerge. Rollout to all 8 chemists proceeds if and only if remediation achieves 100% exit-gate compliance. If critical defects remain unresolved at the end of Week 8, organization-wide rollout is deferred until remediation and retesting are complete. Safety checks, validation gates, and chemist approval requirements will never be waived or bypassed to meet calendar deadlines.

---

## 8. Summary of Engineering Rationale
By establishing a **deterministic safety barrier around the generative model**, the Kestrel assistant captures the productivity benefits of AI while eliminating the operational hazards of hallucinated stoichiometry, unnormalized packaging costs, unapproved trial scale-ups, and unauthorized lab bookings. This delivers an auditable, cost-effective ($0.537/chemist/month baseline) platform built for practical R&D bench adoption.

