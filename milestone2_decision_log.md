# Architecture Decision Log — Kestrel R&D Formulation Assistant

**Document Status:** Proposed Architecture Decision Records  
**Author:** Head of Engineering Candidate  
**Project:** Kestrel R&D Formulation Assistant Platform  

---

## Decision ADR-001: Architecture Pattern & Workflow Orchestration

### Context
Kestrel's formulation assistant must orchestrate a multi-stage workflow: taking chemist input, parsing structured targets, querying historical trials, generating candidate formulations via LLM, validating candidates against deterministic constraints, and capturing human sign-off. We must choose an architecture pattern that balances developer velocity, operational simplicity, auditability, and safety for an 8-chemist team.

### Options Considered
1. **Option A: Modular Monolith with Deterministic Safety Gates (FastAPI + Internal Pipeline)**
2. **Option B: Workflow-Orchestration Platform (e.g., Unmeshed.io with code steps, LLM calls, and approval gates)**
3. **Option C: Custom Multi-Agent Framework (e.g., LangGraph, AutoGen, CrewAI with distributed agent services)**

### Evaluation & Trade-off Matrix

| Evaluation Criteria | Option A: Modular Monolith | Option B: Workflow Engine (Unmeshed.io) | Option C: Custom Multi-Agent |
| :--- | :---: | :---: | :---: |
| **Operational Overhead** | **Lowest** (Single application container, no separate orchestrator or agent cluster) | **Moderate** (Requires external/hosted orchestration engine) | **Highest** (Multiple services, distributed coordination) |
| **Suitability for Kestrel Scale (8 Chemists)** | **Optimal** (350 req/mo runs on minimal resources) | **Excessive for prototype** (Adds unnecessary platform dependency) | **Grossly Over-Engineered** (Microservices for 15 queries/day) |
| **Portability & Vendor Lock-in** | **Complete Portability** (Pure Python 3.11+, runs anywhere) | **Vendor Lock-in** (Proprietary DSL / platform workflow contracts) | **Framework Lock-in** (Dependent on agent framework abstractions) |
| **Observability & Auditability** | **High** (Deterministic logging to relational database) | **High** (Built-in step visualization and execution traces) | **Low / Fragmented** (Stochastic inter-agent chatter is opaque) |
| **Security & Air-Gapped Feasibility** | **High** (Self-contained, easy on-premise deployment) | **Questionable** (SaaS orchestrator risks exposing internal R&D data) | **Moderate** (More network endpoints to secure) |
| **Time-to-Prototype (6-Hour Budget)** | **Fastest** (Direct Python modules, simple pytest coverage) | **Slower** (Workflow onboarding, account setup, external config) | **Slowest** (Prompt tuning inter-agent protocols) |

### Chosen Decision: Option A (Modular Monolith with Deterministic Safety Gates)
We select **Option A** for the current implementation and 8-week production rollout.

#### Architectural Rationale
- For Kestrel's 8 chemists and two laboratories, the entire workload is ~15 requests per day. A clean, modular Python application with well-defined service boundaries (Intake, Retrieval, Generation, Validation, Approval) delivers sub-50ms deterministic internal operations and maintains end-to-end user request latency well under the required $\le 15$ seconds (targeting p95 $\le 12$s), without network serialization or distributed system failure modes.
- External workflow engines like **Unmeshed.io** provide valuable visual tracing and durable human-in-the-loop task pausing, but introducing an external SaaS orchestrator during initial development adds unnecessary operational overhead, third-party network egress risks for confidential chemical formulas, and vendor lock-in.

#### Conditions That Could Change This Decision
- If Kestrel's R&D operations scale to 100+ chemists across multiple global divisions with complex multi-day physical lab workflows (e.g. automated robotics workcells, parallel analytical testing queues spanning weeks), adopting a durable orchestration platform like Unmeshed.io or Temporal would become justified to manage asynchronous long-running task states.

---

## Decision ADR-002: Retrieval Engine Strategy (Relational + Lexical vs. Pure Vector DB)

### Context
The AI assistant must ground candidate formulation proposals in past successful trials, valid raw materials, active purchasing prices, and compliance notes. We must choose an appropriate storage and retrieval strategy for Kestrel's raw export data.

### Options Considered
1. **Option A: Pure Vector Database (e.g., Pinecone, Qdrant, Chroma)**
   - Converting all rows across all 12 spreadsheets into vector embeddings and querying via cosine similarity.
2. **Option B: Hybrid Relational Database (PostgreSQL / SQLite) + BM25 Lexical Search**
   - Ingesting tabular trials, logs, and prices into structured relational tables with SQL query filtering; indexing regulatory notes and scientific literature with BM25 keyword search.
3. **Option C: Knowledge Graph (Neo4j)**
   - Modeling chemical entities, functional groups, and trial recipes as an ontology graph.

### Evaluation & Trade-off Matrix

| Evaluation Criteria | Option A: Pure Vector DB | Option B: Relational + BM25 (Hybrid) | Option C: Knowledge Graph |
| :--- | :---: | :---: | :---: |
| **Numerical Precision & Range Filtering** | **Poor** (Vector similarity cannot reliably filter $\text{pH} \in [3.5, 4.5]$) | **Flawless** (Native SQL `WHERE ph BETWEEN 3.5 AND 4.5`) | **Moderate** (Requires graph query cypher filters) |
| **Data Size Appropriateness** | **Mismatched** (Only 28 materials and 12 softener trials) | **Optimal** (Fits in memory; sub-millisecond relational queries) | **Over-Engineered** (Graph maintenance overhead for small catalog) |
| **Foreign Key & Log Cross-Referencing**| **Infeasible** (Cannot join `Stability_Log` rows to `Trial` IDs) | **Native** (Relational `JOIN` across trials and stability logs) | **High** (Native graph relationships) |
| **Operational Simplicity** | **Requires extra database service** | **Zero/minimal overhead** (Built-in SQLite / existing PostgreSQL) | **High setup and maintenance complexity** |

### Chosen Decision: Option B (Hybrid Relational + BM25 Full-Text Search)
We select **Option B**.

#### Architectural Rationale
- Chemical formulation datasets are fundamentally tabular and quantitative: solids percentages, viscosity in cP, pH, temperature, and cost per kg. Vector embeddings compress text into semantic representations that destroy exact numerical thresholds.
- Verifying that Trial `T-05` failed stability requires joining `Trials_TX_Softeners` with `Stability_Log` where `phase_sep = 'Y'`. Relational databases handle this natively via deterministic SQL queries.
- **Bidirectional Evidence Retrieval:** In contrast to architectures that query only "Pass" trials, the relational engine actively retrieves failed, incomplete, negative, and contradictory historical trials. Preserving failure reasons (e.g. thermal phase separation or precipitation) prevents chemists from unknowingly re-exploring failed formulation paths.
- Unstructured narrative data (`Regulatory_Notes`, scientific literature abstracts) are indexed via BM25 lexical search, providing exact chemical keyword matching (e.g., matching "nonylphenol" or "sensitiser") without embedding drift. Regulatory notes are treated strictly as unverified internal guidance flags, not legal compliance conclusions.

#### Risks & Mitigations
- *Risk:* Chemists may query using colloquial terms not present in table column names.
- *Mitigation:* The Intake Engine uses the LLM to translate informal user briefs into structured SQL filter parameters before querying the relational store.

---

## Decision ADR-003: Calculation & Constraint Enforcement Responsibility

### Context
Formulation recipes require mass balance summation ($100.0\% \pm 0.05\%$), active solids calculations, packaging unit conversions (drum to kg), foreign exchange conversions ($1\text{ USD} = 84.00\text{ INR}$ historical basis as of 2026-05-01), and adherence to customer restrictions (e.g. silicone-free, alcohol flammability limits). We must establish where calculation and constraint verification takes place.

### Options Considered
1. **Option A: LLM-Driven Calculation via Prompt Engineering**
   - Instructing the LLM via detailed system prompt to sum percentages to 100%, perform multiplications, and apply cost formulas.
2. **Option B: LLM Proposes Concepts $\to$ Deterministic Python Safety Barrier Enforces & Recalculates**
   - The LLM drafts chemical hypotheses and relative proportions; deterministic Python code verifies mass balance, recalculates exact prices from purchasing tables, and blocks constraint violations.
3. **Option C: Pure Deterministic Heuristics (Zero LLM Involvement in Formulation)**
   - Traditional rules-based formulation lookup from a hardcoded decision tree.

### Evaluation & Trade-off Matrix

| Evaluation Criteria | Option A: LLM-Driven Calculation | Option B: LLM Draft + Deterministic Barrier | Option C: Pure Rules Engine |
| :--- | :---: | :---: | :---: |
| **Mathematical Reliability** | **Unacceptable** (Prone to floating-point hallucination) | **100% Deterministic** (Python `Decimal` fixed-point arithmetic) | **100% Deterministic** |
| **Safety & Constraint Guarantee** | **Probabilistic** (Can leak prohibited chemicals) | **Absolute Gate** (Python code throws validation error) | **Absolute Gate** |
| **Novelty & Scientific Synthesis** | **High** (Explores novel additive combinations) | **High** (LLM proposes; code validates) | **Zero** (Cannot adapt to novel customer briefs) |
| **Auditability & Traceability** | **Opaque** (Cannot explain arithmetic derivation) | **Full Line-Item Schedule** (Reconciled to price sources) | **High** |

### Chosen Decision: Option B (LLM Proposal + Deterministic Code Barrier)
We select **Option B**.

#### Architectural Rationale
- In physical specialty chemical manufacturing, arithmetic error is an operational non-negotiable. Allowing an LLM to balance stoichiometries or calculate product costs replaces exact math with probabilistic guessing.
- All authoritative calculations (mass balance, active solids, unit normalization, costing) are implemented using Python `Decimal` fixed-point arithmetic. Ordinary Python floating-point arithmetic is explicitly rejected for safety-critical checks due to binary floating-point representation drift.
- By placing an automated **Deterministic Validation Engine** in Python between the LLM and the chemist, the system combines the creative reasoning of generative models with the rigor of deterministic software engineering. If an LLM returns a recipe totaling 103% (like legacy trial `T-09`) or containing silicone on a silicone-free brief (like legacy trial `T-10`), the deterministic barrier catches it, rejects it, and re-prompts the model with specific error telemetry.
- **Strict Override Governance:** Ordinary user overrides **cannot bypass prohibited ingredients, unresolved raw material identities, invalid mass balance ($100.0\% \pm 0.05\%$), or mandatory chemist sign-off**. Any permitted operational exception (e.g. relaxing an advisory target like target viscosity range) requires explicit supervisor authorization, recorded justification, and an immutable audit log entry.

#### Risks & Mitigations
- *Risk:* LLM may get stuck in a re-prompting validation loop if its proposed chemistry repeatedly violates constraints.
- *Mitigation:* Enforce a bounded retry policy (maximum 2 automated re-prompt attempts with structured diagnostic error feedback). If the LLM candidate still fails deterministic validation after 2 retries, the pipeline stops safely and surfaces an explicit failure report detailing the exact constraint breaches. Unconditional fallback to historical recipes is prohibited; a historical baseline recipe may only be recommended if its records are verified (no stability failures or unapproved statuses) and it independently passes every active constraint and validation gate of the current brief.

---

## Decision ADR-004: Laboratory Booking & Approval Governance

### Context
Once a formulation plan is drafted, physical laboratory resources (mixers, heating vessels, stability incubators) must be scheduled for execution. The draft architecture proposed autonomous booking when model confidence $> 0.8$.

### Options Considered
1. **Option A: Autonomous Lab Booking by AI Agent**
   - Scheduling agent books slots directly in LabTrack LIMS when confidence threshold is met; chemist can retroactively cancel.
2. **Option B: Mandatory Human-in-the-Loop Sign-Off (Draft Plan Only)**
   - The assistant outputs an unapproved trial proposal. A physical booking and trial release requires explicit authenticated, role-based digital sign-off from an authorized chemist with audit logging.
3. **Option C: Lead Chemist Dual Approval Workflow**
   - Requiring both the bench chemist and the R&D director to sign off on every initial lab trial.

### Evaluation & Trade-off Matrix

| Evaluation Criteria | Option A: Autonomous Agent Booking | Option B: Mandatory Chemist Sign-Off | Option C: Dual Approval |
| :--- | :---: | :---: | :---: |
| **Physical Safety & Hazard Prevention**| **Severe Hazard** (Can schedule unverified chemistry) | **High** (Chemist verifies bench readiness) | **Highest** |
| **Lab Resource Efficiency** | **Poor** (High phantom booking & cancellation rate) | **Optimal** (Bookings reflect true human intent) | **Slight Bottleneck** (Director sign-off delays desk work) |
| **Chemist Approval Requirement** | **Violates requirement** (Violates the assignment's mandatory approval requirement; unverified automated bench release) | **Meets requirement** (Meets the stated mandatory chemist-approval requirement; explicit human accountability) | **Meets requirement** (Meets the stated mandatory chemist-approval requirement; adds second sign-off) |
| **Chemist Adoption & Trust** | **Low** (Chemists resent fighting automated bookings) | **High** (Empowers chemist; respects professional role) | **Moderate** |

### Chosen Decision: Option B (Mandatory Human-in-the-Loop Sign-Off)
We select **Option B**.

#### Architectural Rationale
- The brief explicitly states: *"No formulation goes to the lab without a chemist's approval."* Autonomous agent booking violates this core business constraint and creates physical lab chaos.
- In Kestrel's raw export, equipment like `STAB-CH1` is heavily utilized and cancellations already happen manually (`BK-2623`). Inverting the workflow so that AI books and humans must cancel creates phantom reservations and technician friction.
- The assistant is strictly an advisor: it drafts the complete trial protocol (batch size, addition order, mixing speed, safety caveats), but the final submission to the lab system requires the authenticated chemist to click "Approve & Submit Trial".

---

## 5. Summary of Decision Governance

| Decision ID | Area | Selected Choice | Rejected Alternatives | Primary Justification |
| :--- | :--- | :--- | :--- | :--- |
| **ADR-001** | Architecture | **Modular Monolith** | Microservices, Unmeshed SaaS | Proportional to 8 chemists; zero distributed complexity or third-party data egress. |
| **ADR-002** | Retrieval | **Relational SQL + BM25** | Pure Vector Database | Tabular chemical numerical filters require SQL precision; small dataset size. |
| **ADR-003** | Calculations | **Deterministic Python Gate** | LLM-based arithmetic | Stoichiometry and costing require zero-tolerance floating point precision. |
| **ADR-004** | Governance | **Mandatory Chemist Sign-Off** | Autonomous Agent Booking | Meets the stated mandatory chemist-approval requirement; prevents physical lab hazards. |
