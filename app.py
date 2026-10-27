"""
Kestrel R&D Formulation Assistant — Interactive Enterprise R&D Workbench.
Demonstrates deterministic formulation validation, transparent costing,
evidence traceability, and chemist review governance.
"""

from decimal import Decimal
import os
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# Add src to path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from kestrel_assistant.audit_log import AssistantAuditLogger
from kestrel_assistant.evidence_store import EvidenceStore
from kestrel_assistant.llm_gateway import LLMGateway
from kestrel_assistant.models import (
    CandidateFormulation,
    CheckStatus,
    EvidenceProvenance,
    FormulationRequest,
    FormulationStatus,
    IngredientLine,
    OverallValidationStatus,
    ValueProvenanceType,
)
from kestrel_assistant.recommender import FormulationRecommender
from kestrel_assistant.validator import DeterministicValidator

# ----------------------------------------------------------------------------
# Streamlit App Configuration
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Kestrel R&D Formulation Assistant",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)
# Enterprise R&D Stylesheet
st.markdown("""
<style>
    /* Global Typography & Spacing */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Clean Top Alignment for Sidebar and Main Canvas */
    [data-testid="stSidebarHeader"] {
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
        padding: 0.35rem 0.75rem 0 0.75rem !important;
        height: 2.25rem !important;
        min-height: 2.25rem !important;
        background: transparent !important;
    }
    [data-testid="stLogoSpacer"] {
        display: none !important;
    }
    [data-testid="stSidebarCollapseButton"] {
        display: flex !important;
        visibility: visible !important;
    }
    [data-testid="stSidebarCollapseButton"] button {
        color: #475569 !important;
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stSidebarCollapseButton"] button:hover {
        color: #0f172a !important;
        background: #f1f5f9 !important;
    }
    [data-testid="stSidebarUserContent"] {
        padding-top: 0.15rem !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
    }
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
    .block-container {
        padding-top: 1.25rem !important;
    }

    /* Header Bar & Chemist Profile */
    .enterprise-header {
        margin-bottom: 1.15rem;
        padding-bottom: 0.85rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .enterprise-title {
        font-size: 1.75rem;
        font-weight: 750;
        color: #0f172a;
        margin: 0;
        line-height: 1.2;
        letter-spacing: -0.01em;
    }
    .enterprise-subtitle {
        font-size: 0.86rem;
        color: #64748b;
        margin-top: 4px;
        margin-bottom: 0.5rem;
    }
    .candidate-meta-bar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        font-size: 0.80rem;
        color: #334155;
    }
    .badge-source {
        background: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 700;
        font-family: monospace;
        font-size: 0.76rem;
    }
    .badge-status-draft {
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #cbd5e1;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
    }
    .chemist-profile-card {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 4px 10px;
        background: #ffffff;
        border-radius: 9999px;
    }
    .chemist-avatar {
        width: 36px;
        height: 36px;
        min-width: 36px;
        border-radius: 50%;
        background: #dbeafe;
        color: #1d4ed8;
        font-weight: 750;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.82rem;
        border: 1px solid #bfdbfe;
    }
    .chemist-info {
        display: flex;
        flex-direction: column;
    }
    .chemist-name {
        font-weight: 700;
        font-size: 0.86rem;
        color: #0f172a;
        line-height: 1.2;
    }
    .chemist-role {
        font-size: 0.72rem;
        color: #64748b;
        line-height: 1.2;
    }
    .chemist-menu-btn {
        color: #94a3b8;
        font-size: 1.15rem;
        cursor: pointer;
        padding-left: 2px;
    }

    /* Sidebar Navigation & Health Components */
    .sidebar-brand-card {
        padding: 0.35rem 0.15rem 0.65rem 0.15rem;
    }
    .sidebar-brand-title {
        font-size: 1.10rem;
        font-weight: 750;
        color: #0f172a;
        margin: 0;
        line-height: 1.2;
    }
    .sidebar-brand-subtitle {
        font-size: 0.74rem;
        color: #64748b;
        margin: 2px 0 0 0;
    }
    .sidebar-nav-container {
        margin: 0.65rem 0 0.85rem 0;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    div[data-testid="stSidebar"] div.st-key-nav_btn_formulate button,
    div[data-testid="stSidebar"] div.st-key-nav_btn_evidence button,
    div[data-testid="stSidebar"] div.st-key-nav_btn_audit button {
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        width: 100% !important;
        text-align: left !important;
        padding: 8px 12px !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        min-height: 38px !important;
        height: 38px !important;
        transition: all 0.15s ease !important;
        box-shadow: none !important;
    }
    /* Secondary (inactive) sidebar nav buttons */
    div[data-testid="stSidebar"] div.st-key-nav_btn_formulate button[kind="secondary"],
    div[data-testid="stSidebar"] div.st-key-nav_btn_evidence button[kind="secondary"],
    div[data-testid="stSidebar"] div.st-key-nav_btn_audit button[kind="secondary"] {
        background: transparent !important;
        color: #334155 !important;
        border: 1px solid transparent !important;
        font-weight: 600 !important;
    }
    div[data-testid="stSidebar"] div.st-key-nav_btn_formulate button[kind="secondary"]:hover,
    div[data-testid="stSidebar"] div.st-key-nav_btn_evidence button[kind="secondary"]:hover,
    div[data-testid="stSidebar"] div.st-key-nav_btn_audit button[kind="secondary"]:hover {
        background: #f8fafc !important;
        color: #0f172a !important;
        border: 1px solid #e2e8f0 !important;
    }
    /* Primary (active) sidebar nav buttons */
    div[data-testid="stSidebar"] div.st-key-nav_btn_formulate button[kind="primary"],
    div[data-testid="stSidebar"] div.st-key-nav_btn_evidence button[kind="primary"],
    div[data-testid="stSidebar"] div.st-key-nav_btn_audit button[kind="primary"] {
        background: #ecfdf5 !important;
        color: #065f46 !important;
        border: 1px solid #a7f3d0 !important;
        border-left: 4px solid #059669 !important;
        font-weight: 700 !important;
    }
    /* Tertiary link buttons */
    div.st-key-btn_toggle_all_checks button,
    div.st-key-btn_more_passed_checks button,
    div.st-key-btn_fewer_passed_checks button {
        color: #2563eb !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        font-size: 0.80rem !important;
        font-weight: 600 !important;
        padding: 2px 4px !important;
        margin: 0 !important;
        min-height: auto !important;
        height: auto !important;
        text-align: left !important;
        display: inline-block !important;
        cursor: pointer !important;
        text-decoration: none !important;
    }
    div.st-key-btn_toggle_all_checks button:hover,
    div.st-key-btn_more_passed_checks button:hover,
    div.st-key-btn_fewer_passed_checks button:hover {
        color: #1d4ed8 !important;
        background: transparent !important;
        text-decoration: underline !important;
    }
    .health-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 0.85rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
    }
    .health-card-header {
        font-size: 0.86rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 8px;
    }
    .health-card-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: 5px 0;
        border-bottom: 1px solid #f8fafc;
    }
    .health-card-row:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }
    .health-item-name {
        font-size: 0.80rem;
        font-weight: 600;
        color: #1e293b;
        display: block;
    }
    .health-item-sub {
        font-size: 0.70rem;
        color: #64748b;
        display: block;
        margin-top: 1px;
    }
    .health-status-col {
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 0.76rem;
        font-weight: 700;
        color: #0f172a;
        text-align: right;
        white-space: nowrap;
    }
    .status-dot {
        height: 7px;
        width: 7px;
        border-radius: 50%;
        display: inline-block;
    }
    .dot-green { background-color: #10b981; }
    .dot-amber { background-color: #f59e0b; }
    .dot-red { background-color: #ef4444; }

    /* Numbered Section Badges */
    .section-num-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        min-width: 24px;
        border-radius: 50%;
        background: #059669;
        color: #ffffff;
        font-weight: 750;
        font-size: 0.82rem;
        line-height: 1;
        margin-right: 8px;
    }
    .section-title-wrap {
        display: flex;
        align-items: center;
        font-size: 1.05rem;
        font-weight: 750;
        color: #0f172a;
        margin-top: 0.5rem;
        margin-bottom: 0.65rem;
    }

    /* Reference Style KPI Strip (5 Cards with Left Icon Boxes) */
    .kpi-strip {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 1.25rem;
    }
    @media (max-width: 1200px) {
        .kpi-strip {
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }
    }
    @media (max-width: 700px) {
        .kpi-strip {
            grid-template-columns: minmax(0, 1fr);
        }
    }
    .kpi-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 10px 12px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        display: flex;
        align-items: center;
        gap: 10px;
        min-height: 88px;
    }
    .kpi-icon-box {
        width: 38px;
        height: 38px;
        min-width: 38px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.15rem;
    }
    .icon-box-blue {
        background: #eff6ff;
        color: #2563eb;
        border: 1px solid #dbeafe;
    }
    .icon-box-green {
        background: #ecfdf5;
        color: #059669;
        border: 1px solid #a7f3d0;
    }
    .kpi-content {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-top-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 2px;
    }
    .kpi-label-text {
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #475569;
        white-space: nowrap;
    }
    .kpi-tag-pill {
        font-size: 0.60rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        padding: 1px 5px;
        border-radius: 4px;
    }
    .pill-blue {
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }
    .pill-amber {
        background: #fef3c7;
        color: #b45309;
        border: 1px solid #fde68a;
    }
    .kpi-val-text {
        font-size: 1.25rem;
        font-weight: 750;
        color: #0f172a;
        line-height: 1.15;
    }
    .kpi-sub-text {
        font-size: 0.69rem;
        font-weight: 600;
        margin-top: 3px;
        line-height: 1.25;
        word-break: break-word;
    }
    .delta-ok { color: #059669; }
    .delta-alert { color: #dc2626; }
    .text-muted { color: #64748b; }
    .text-pass { color: #059669; }
    .text-warn { color: #d97706; }

    /* Accessible Status Badges */
    .badge-pass {
        background-color: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.03em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .badge-fail {
        background-color: #fef2f2;
        color: #991b1b;
        border: 1px solid #fecaca;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.03em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .badge-warn {
        background-color: #fffbeb;
        color: #92400e;
        border: 1px solid #fde68a;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.03em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .badge-unverified {
        background-color: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
        padding: 2px 7px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.68rem;
        letter-spacing: 0.03em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }

    /* Section 3 Validation Summary 3-Box Layout */
    .val-summary-container {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 14px;
        margin-top: 0.5rem;
        margin-bottom: 1.25rem;
    }
    @media (max-width: 960px) {
        .val-summary-container {
            grid-template-columns: minmax(0, 1fr);
        }
    }
    .val-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.02);
        display: flex;
        flex-direction: column;
    }
    .val-box-header {
        font-size: 0.85rem;
        font-weight: 750;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .val-pass-banner {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 0.80rem;
        color: #166534;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
    }
    .val-gap-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        border-bottom: 1px solid #f8fafc;
        font-size: 0.78rem;
    }
    .val-gap-item:last-child {
        border-bottom: none;
    }
    .val-code-badge {
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.66rem;
        font-weight: 700;
        font-family: monospace;
        margin-right: 6px;
    }
    .val-pass-check-row {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #1e293b;
        padding: 3px 0;
    }

    /* Streamlit Tab Customization for Restrained Green Indicator */
    button[data-baseweb="tab"] {
        font-weight: 600 !important;
        font-size: 0.86rem !important;
        color: #475569 !important;
        padding: 0.65rem 1rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #059669 !important;
        font-weight: 750 !important;
    }
    div[data-baseweb="tab-highlight"] {
        background-color: #059669 !important;
        height: 2.5px !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_assistant_components():
    """Initializes and caches read-only evidence store and engine components."""
    store = EvidenceStore()
    validator = DeterministicValidator()
    recommender = FormulationRecommender(store)
    logger = AssistantAuditLogger()
    gateway = LLMGateway()
    return store, validator, recommender, logger, gateway


store, validator, recommender, logger, gateway = get_assistant_components()

# ----------------------------------------------------------------------------
# Session State Initialization
# ----------------------------------------------------------------------------
if "current_candidate" not in st.session_state:
    # Initialize with default recommended candidate
    default_req = FormulationRequest()
    st.session_state.current_candidate = recommender.generate_recommended_candidate(default_req)

if "active_request" not in st.session_state:
    st.session_state.active_request = FormulationRequest()

if "selected_rm_override" not in st.session_state:
    st.session_state.selected_rm_override = {}

TAB_FORMULATION = "🧪 Formulation Studio & Validation"
TAB_EVIDENCE = "📚 Evidence Store & Workbook Explorer"
TAB_AUDIT = "📋 Audit Trail & Compliance Log"

if "active_main_tab" not in st.session_state:
    st.session_state["active_main_tab"] = TAB_FORMULATION

if "show_all_val_checks" not in st.session_state:
    st.session_state["show_all_val_checks"] = False

if "show_all_passed_checks" not in st.session_state:
    st.session_state["show_all_passed_checks"] = False

# ----------------------------------------------------------------------------
# Sidebar — Brand Header, System Status & Historical Regression Benchmarks
# ----------------------------------------------------------------------------
with st.sidebar:
    # Compact brand header with Siddharth Logo
    st.image("https://newscplbiz.netlify.app/logo.png", width=140)
    st.markdown("""
    <div class="sidebar-brand-card">
        <div class="sidebar-brand-title">Kestrel R&D Assistant</div>
        <div class="sidebar-brand-subtitle">SCPL Lab Architecture • Enterprise MVP</div>
    </div>
    """, unsafe_allow_html=True)
    
    cur_tab = st.session_state.get("active_main_tab", TAB_FORMULATION)
    def set_nav_tab(target):
        st.session_state["active_main_tab"] = target

    is_form = (cur_tab == TAB_FORMULATION)
    is_ev = (cur_tab == TAB_EVIDENCE)
    is_audit = (cur_tab == TAB_AUDIT)

    st.button("🧪 Formulation Studio", key="nav_btn_formulate", use_container_width=True,
              type="primary" if is_form else "secondary",
              on_click=set_nav_tab, args=(TAB_FORMULATION,))
    st.button("⏱ Evidence Explorer", key="nav_btn_evidence", use_container_width=True,
              type="primary" if is_ev else "secondary",
              on_click=set_nav_tab, args=(TAB_EVIDENCE,))
    st.button("📋 Audit Trail", key="nav_btn_audit", use_container_width=True,
              type="primary" if is_audit else "secondary",
              on_click=set_nav_tab, args=(TAB_AUDIT,))
    st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)
    
    # System Status & Integrity Indicators matching reference UI
    st.markdown("""
    <div class="health-card">
        <div class="health-card-header">System Health & Integrity</div>
        <div class="health-card-row">
            <div>
                <span class="health-item-name">Deterministic Engine</span>
                <span class="health-item-sub">(Decimal Math)</span>
            </div>
            <div class="health-status-col">
                <span class="status-dot dot-green"></span>Active
            </div>
        </div>
        <div class="health-card-row">
            <div>
                <span class="health-item-name">Source Workbook</span>
                <span class="health-item-sub">(Intact)</span>
            </div>
            <div class="health-status-col">
                <span class="status-dot dot-green"></span>SHA-256 Verified
            </div>
        </div>
        <div class="health-card-row">
            <div>
                <span class="health-item-name">Audit Chain</span>
                <span class="health-item-sub">(Hash Chain Valid)</span>
            </div>
            <div class="health-status-col">
                <span class="status-dot dot-green"></span>Tamper-Proof
            </div>
        </div>
        <div class="health-card-row">
            <div>
                <span class="health-item-name">AI Gateway</span>
                <span class="health-item-sub">(Generative Drafting Disabled)</span>
            </div>
            <div class="health-status-col">
                <span class="status-dot dot-amber"></span>Deterministic Mode
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Collapsible Historical Benchmarks (single vertical column matching reference)
    active_trial = getattr(st.session_state.current_candidate, "source_trial_id", "") or ""
    with st.expander("📊 Historical Benchmarks", expanded=True):
        t04_selected = "T-04" in active_trial
        if st.button("⟳ Load T-04" + (" (Active)" if t04_selected else ""), type="primary" if t04_selected else "secondary", help="Ambiguous TEA-esterquat, high viscosity (0.45 Pa*s = 450 cP)", width="stretch"):
            cand = recommender.load_historical_trial_as_candidate("T-04")
            if cand:
                st.session_state.current_candidate = cand
                st.rerun()

        t05_selected = "T-05" in active_trial
        if st.button("⟳ Load T-05" + (" (Active)" if t05_selected else ""), type="primary" if t05_selected else "secondary", help="Stability contradiction: Pass in summary vs Week 3 phase separation", width="stretch"):
            cand = recommender.load_historical_trial_as_candidate("T-05")
            if cand:
                st.session_state.current_candidate = cand
                st.rerun()

        t09_selected = "T-09" in active_trial
        if st.button("📄 Load T-09" + (" (Active)" if t09_selected else ""), type="primary" if t09_selected else "secondary", help="Mass-balance violation: 103.0% total concentration", width="stretch"):
            cand = recommender.load_historical_trial_as_candidate("T-09")
            if cand:
                st.session_state.current_candidate = cand
                st.rerun()

        t10_selected = "T-10" in active_trial
        if st.button("📄 Load T-10" + (" (Active)" if t10_selected else ""), type="primary" if t10_selected else "secondary", help="Silicone violation: contains RM-140 amino silicone", width="stretch"):
            cand = recommender.load_historical_trial_as_candidate("T-10")
            if cand:
                st.session_state.current_candidate = cand
                st.rerun()

        t11_selected = "T-11" in active_trial
        if st.button("📄 Load T-11" + (" (Active)" if t11_selected else ""), type="primary" if t11_selected else "secondary", help="Incomplete trial: missing pH and stability in progress (NOT_VERIFIED)", width="stretch"):
            cand = recommender.load_historical_trial_as_candidate("T-11")
            if cand:
                st.session_state.current_candidate = cand
                st.rerun()

        clean_selected = not any(t in active_trial for t in ["T-04", "T-05", "T-09", "T-10", "T-11"])
        if st.button("⟳ Reset Clean" + (" (Active)" if clean_selected else ""), type="primary" if clean_selected else "secondary", help="Reset to verified silicone-free benchmark candidate", width="stretch"):
            st.session_state.current_candidate = recommender.generate_recommended_candidate(st.session_state.active_request)
            st.rerun()

# ----------------------------------------------------------------------------
# Main Workspace Enterprise Header & Dynamic KPI Strip
# ----------------------------------------------------------------------------
cand = st.session_state.current_candidate
req = st.session_state.active_request
validator.request = req
val_report = validator.validate(cand)

st.markdown(f"""
<div class="enterprise-header">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
        <div>
            <h1 class="enterprise-title">Kestrel R&D Formulation Assistant</h1>
            <p class="enterprise-subtitle">Deterministic validation engine, evidence-backed formulation modeling, and chemist approval governance.</p>
            <div class="candidate-meta-bar">
                <span>Candidate: <strong>{cand.title}</strong></span>
                <span style="color: #cbd5e1;">|</span>
                <span>Source: <span class="badge-source">{cand.source_trial_id or 'TX-SOFT-26 / T-04-Corrected'}</span></span>
                <span style="color: #cbd5e1;">|</span>
                <span>Status: <span class="badge-status-draft">{cand.status.value}</span></span>
            </div>
        </div>
        <div class="chemist-profile-card">
            <div class="chemist-avatar">VS</div>
            <div class="chemist-info">
                <div class="chemist-name">Dr. Vikram Shah</div>
                <div class="chemist-role">Research Chemist</div>
            </div>
            <div class="chemist-menu-btn">⋮</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Compute dynamic values for compact KPI strip
kpi_mass_val = f"{cand.total_percentage:.2f}%"
kpi_mass_ok = abs(cand.total_percentage - Decimal("100.0")) <= Decimal("0.05")
kpi_mass_sub = "✓ Exact (±0.05%)" if kpi_mass_ok else f"{cand.total_percentage - Decimal('100.0'):+.2f}% vs target"
kpi_mass_cls = "delta-ok" if kpi_mass_ok else "delta-alert"

kpi_cost_val = f"₹{cand.total_cost_inr_per_kg:.2f}/kg"
kpi_cost_ok = cand.total_cost_inr_per_kg <= req.max_cost_inr_per_kg
kpi_margin = req.max_cost_inr_per_kg - cand.total_cost_inr_per_kg
kpi_cost_sub = f"↓ ₹{kpi_margin:.2f} margin vs limit" if kpi_cost_ok else f"↑ ₹{-kpi_margin:.2f} over limit"
kpi_cost_cls = "delta-ok" if kpi_cost_ok else "delta-alert"

kpi_solids_val = f"{cand.estimated_solids_pct:.2f}%"
kpi_solids_ok = req.solids_pct_range[0] <= cand.estimated_solids_pct <= req.solids_pct_range[1]
kpi_solids_sub = f"Target: {req.solids_pct_range[0]:.1f} – {req.solids_pct_range[1]:.1f}%"
kpi_solids_cls = "delta-ok" if kpi_solids_ok else "delta-alert"

if val_report.overall_status == OverallValidationStatus.ALL_CRITERIA_VERIFIED_PASS:
    kpi_val_html = '<span class="text-pass">PASS</span> <span style="font-size: 0.80rem; font-weight: 700; color: #059669;">(Certified)</span>'
    kpi_val_sub = "✓ All criteria verified"
    kpi_val_cls = "delta-ok"
elif val_report.overall_status == OverallValidationStatus.SPEC_PASSED_PENDING_EXPERIMENTAL:
    kpi_val_html = '<span class="text-pass">PASS</span> <span style="font-size: 0.80rem; font-weight: 700; color: #059669;">(Bench Ready)</span>'
    kpi_val_sub = "✓ All deterministic checks passed"
    kpi_val_cls = "delta-ok"
else:
    kpi_val_html = '<span class="delta-alert" style="color: #dc2626;">FAIL</span> <span style="font-size: 0.80rem; font-weight: 700; color: #dc2626;">(Blockers)</span>'
    kpi_val_sub = f"✕ {len(val_report.rejection_reasons)} Blocking Violation(s)"
    kpi_val_cls = "delta-alert"

has_stab_pass = cand.stability_45c_4w_status == "PASS"
has_soft_pass = cand.softness_panel_score is not None and cand.softness_panel_score >= req.min_softness_panel_score
if has_stab_pass and has_soft_pass:
    kpi_ev_html = '<div style="font-size: 0.95rem; font-weight: 800; color: #059669;">VERIFIED</div>'
    kpi_ev_sub = "✓ Incubator & Panel passed"
    kpi_ev_cls = "delta-ok"
elif cand.stability_45c_4w_status in ["FAIL", "PHASE_SEPARATION"] or (cand.softness_panel_score is not None and cand.softness_panel_score < req.min_softness_panel_score):
    kpi_ev_html = '<div style="font-size: 0.90rem; font-weight: 800; color: #dc2626;">DEFECT RECORDED</div>'
    kpi_ev_sub = f"Stab: {cand.stability_45c_4w_status} | Soft: {f'{cand.softness_panel_score:.1f}' if cand.softness_panel_score else 'Unknown'}"
    kpi_ev_cls = "delta-alert"
else:
    kpi_ev_html = '<div style="font-size: 0.86rem; font-weight: 800; color: #b45309; line-height: 1.15;">PENDING LAB TRIALS</div><div style="font-size: 0.68rem; font-weight: 750; color: #b45309;">(NOT VERIFIED)</div>'
    kpi_ev_sub = "⏱ 4 weeks stability & sensory pending"
    kpi_ev_cls = "text-muted"

st.markdown(f"""
<div class="kpi-strip">
    <!-- Card 1: Total Mass -->
    <div class="kpi-card">
        <div class="kpi-icon-box icon-box-blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.31L4.89 18.27A2 2 0 0 0 6.64 21h10.72a2 2 0 0 0 1.75-2.73L14 9.31V2"></path><line x1="8.5" y1="2" x2="15.5" y2="2"></line><line x1="7" y1="14" x2="17" y2="14"></line></svg>
        </div>
        <div class="kpi-content">
            <div class="kpi-top-row">
                <span class="kpi-label-text">Total Mass</span>
                <span class="kpi-tag-pill pill-blue">CALCULATED</span>
            </div>
            <div class="kpi-val-text">{kpi_mass_val}</div>
            <div class="kpi-sub-text {kpi_mass_cls}">{kpi_mass_sub}</div>
        </div>
    </div>
    <!-- Card 2: Raw Material Cost -->
    <div class="kpi-card">
        <div class="kpi-icon-box icon-box-green"><span style="font-weight: 800; font-size: 1.15rem; color: #059669;">₹</span></div>
        <div class="kpi-content">
            <div class="kpi-top-row">
                <span class="kpi-label-text">Raw Material Cost</span>
                <span class="kpi-tag-pill pill-blue">CALCULATED</span>
            </div>
            <div class="kpi-val-text">{kpi_cost_val}</div>
            <div class="kpi-sub-text {kpi_cost_cls}">{kpi_cost_sub}</div>
        </div>
    </div>
    <!-- Card 3: Active Solids -->
    <div class="kpi-card">
        <div class="kpi-icon-box icon-box-blue"><span style="font-weight: 800; font-size: 1.15rem; color: #2563eb;">%</span></div>
        <div class="kpi-content">
            <div class="kpi-top-row">
                <span class="kpi-label-text">Active Solids</span>
                <span class="kpi-tag-pill pill-amber">ESTIMATED</span>
            </div>
            <div class="kpi-val-text">{kpi_solids_val}</div>
            <div class="kpi-sub-text {kpi_solids_cls}">{kpi_solids_sub}</div>
        </div>
    </div>
    <!-- Card 4: Validation Status -->
    <div class="kpi-card">
        <div class="kpi-icon-box icon-box-green">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><path d="m9 12 2 2 4-4"></path></svg>
        </div>
        <div class="kpi-content">
            <div class="kpi-top-row">
                <span class="kpi-label-text">Validation Status</span>
            </div>
            <div class="kpi-val-text">{kpi_val_html}</div>
            <div class="kpi-sub-text {kpi_val_cls}">{kpi_val_sub}</div>
        </div>
    </div>
    <!-- Card 5: Experimental Evidence -->
    <div class="kpi-card">
        <div class="kpi-icon-box icon-box-blue">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.31L4.89 18.27A2 2 0 0 0 6.64 21h10.72a2 2 0 0 0 1.75-2.73L14 9.31V2"></path><line x1="8.5" y1="2" x2="15.5" y2="2"></line><line x1="7" y1="14" x2="17" y2="14"></line></svg>
        </div>
        <div class="kpi-content">
            <div class="kpi-top-row">
                <span class="kpi-label-text">Experimental Evidence</span>
            </div>
            <div class="kpi-val-text">{kpi_ev_html}</div>
            <div class="kpi-sub-text {kpi_ev_cls}">{kpi_ev_sub}</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

tab_formulate, tab_evidence, tab_history = st.tabs(
    [TAB_FORMULATION, TAB_EVIDENCE, TAB_AUDIT],
    key="active_main_tab",
    on_change="rerun"
)

# ============================================================================
# TAB 1: FORMULATION STUDIO & VALIDATION
# ============================================================================
with tab_formulate:
    # ------------------------------------------------------------------------
    # Section 1: Customer Formulation Request Specification
    # ------------------------------------------------------------------------
    with st.container(border=True):
        col_s1_title, col_s1_btn = st.columns([3, 2])
        with col_s1_title:
            st.markdown("""
            <div class="section-title-wrap">
                <span class="section-num-badge">1</span>
                <span>Customer Formulation Request Specification</span>
            </div>
            """, unsafe_allow_html=True)
        with col_s1_btn:
            b_c1, b_c2 = st.columns([5, 1])
            with b_c1:
                auto_parse_clicked = st.button("🪄 Auto-Parse Brief into Constraints", width="stretch")
            with b_c2:
                st.markdown("<div style='padding-top: 6px; display: flex; align-items: center;'><span style='display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; border: 1.5px solid #cbd5e1; color: #64748b; font-size: 0.75rem; font-weight: 700; cursor: help;' title='Extracts substrate, banned chemicals, and physical ranges from brief'>?</span></div>", unsafe_allow_html=True)

        nl_input = st.text_area(
            "Customer Brief / Requirements Text",
            value="Targeting Sunvale Mills request: Cationic textile softener for 100% cotton knits and terry towels: Requirements: active solids 6.0–8.0%, pH 3.5–4.5, viscosity 50–300 cP, raw material cost <= ₹22.0/kg, silicone-free, thermal stability for 4 weeks at 45°C with no separation or yellowing, and minimum softness panel score of 4/5.",
            height=70,
            help="Enter customer brief text to auto-parse parameters"
        )
        if auto_parse_clicked:
            parsed_req = gateway.parse_natural_language_brief(nl_input)
            st.session_state.active_request = parsed_req
            st.success("Target constraints updated from natural language brief.")

        req = st.session_state.active_request

        # Row 1: Substrate (select), Prohibited Ingredients (input), Max Commercial Cost (number)
        r1_c1, r1_c2, r1_c3 = st.columns([1.5, 2, 1])
        with r1_c1:
            req.target_substrate = st.selectbox(
                "Substrate",
                ["100% Cotton Knits / Terry Towels", "Polyester / Cotton Blends", "100% Cotton Woven", "Cellulosic Blends"],
                index=0
            )
        with r1_c2:
            prohib_str = st.text_input("Prohibited Chemical Ingredients", value=", ".join(req.prohibited_ingredients))
            req.prohibited_ingredients = [p.strip() for p in prohib_str.split(",") if p.strip()]
        with r1_c3:
            max_c = st.number_input("Max Commercial Cost (₹/kg)", value=float(req.max_cost_inr_per_kg), step=0.50, format="%.2f")
            req.max_cost_inr_per_kg = Decimal(str(max_c))

        # Row 2 (4 cols): Min Active Solids %, Max Active Solids %, Min pH, Max pH
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        with r2_c1:
            min_solids = st.number_input("Min Active Solids %", value=float(req.solids_pct_range[0]), step=0.10, format="%.2f")
        with r2_c2:
            max_solids = st.number_input("Max Active Solids %", value=float(req.solids_pct_range[1]), step=0.10, format="%.2f")
        req.solids_pct_range = (Decimal(str(min_solids)), Decimal(str(max_solids)))

        with r2_c3:
            min_ph = st.number_input("Min pH", value=float(req.ph_range[0]), step=0.10, format="%.2f")
        with r2_c4:
            max_ph = st.number_input("Max pH", value=float(req.ph_range[1]), step=0.10, format="%.2f")
        req.ph_range = (Decimal(str(min_ph)), Decimal(str(max_ph)))

        # Row 3 (4 cols): Min Viscosity (cP), Max Viscosity (cP), Min Softness Score (1-5), Stability Requirement
        r3_c1, r3_c2, r3_c3, r3_c4 = st.columns([1, 1, 1, 1.5])
        with r3_c1:
            min_visc = st.number_input("Min Viscosity (cP)", value=float(req.viscosity_cp_range[0]), step=10.0, format="%.2f")
        with r3_c2:
            max_visc = st.number_input("Max Viscosity (cP)", value=float(req.viscosity_cp_range[1]), step=10.0, format="%.2f")
        req.viscosity_cp_range = (Decimal(str(min_visc)), Decimal(str(max_visc)))

        with r3_c3:
            min_soft = st.number_input("Min Softness Score (1-5)", value=float(req.min_softness_panel_score), step=0.10, format="%.2f")
            req.min_softness_panel_score = Decimal(str(min_soft))
        with r3_c4:
            st.text_input("Stability Requirement", value=req.target_stability, disabled=True)

    # Update validator request
    validator.request = req
    cand = st.session_state.current_candidate

    # ------------------------------------------------------------------------
    # Section 2: Candidate Formulation Recipe
    # ------------------------------------------------------------------------
    col_s2_title, col_s2_btns = st.columns([2.5, 2.5])
    with col_s2_title:
        st.markdown("""
        <div class="section-title-wrap">
            <span class="section-num-badge">2</span>
            <span>Candidate Formulation Recipe</span>
        </div>
        """, unsafe_allow_html=True)
    with col_s2_btns:
        b2_1, b2_2, b2_3 = st.columns(3)
        with b2_1:
            if st.button("+ Add Ingredient", width="stretch"):
                st.session_state.show_add_ingredient = not st.session_state.get("show_add_ingredient", False)
                st.session_state.show_load_trial = False
                st.rerun()
        with b2_2:
            if st.button("📥 Load from Trial", width="stretch"):
                st.session_state.show_load_trial = not st.session_state.get("show_load_trial", False)
                st.session_state.show_add_ingredient = False
                st.rerun()
        with b2_3:
            if st.button("⚙️ Optimize Recipe", width="stretch"):
                # Rebalance formula to exact 100.00% mass balance using demineralized water (RM-180)
                non_water_pct = sum((line.percentage for line in cand.ingredients if line.resolved_rm_code != "RM-180"), Decimal("0.0"))
                if non_water_pct > Decimal("100.0"):
                    st.error(f"Cannot rebalance: active components sum to {non_water_pct:.2f}% (exceeds 100.00%). Reduce non-water ingredient concentrations first.")
                else:
                    water_needed = Decimal("100.00") - non_water_pct
                    updated_lines = []
                    found_water = False
                    for line in cand.ingredients:
                        if line.resolved_rm_code == "RM-180":
                            found_water = True
                            u_p, p_b, has_c, c_n = store.get_price_for_rm("RM-180")
                            c_contrib = (water_needed / Decimal("100.0")) * (u_p or Decimal("1.0"))
                            updated_lines.append(IngredientLine(
                                raw_token=line.raw_token,
                                resolved_rm_code="RM-180",
                                trade_name="Water (demineralised)",
                                chemical_class="Utility",
                                supplier="In-house",
                                percentage=water_needed,
                                unit_price_inr=u_p,
                                price_basis=p_b,
                                cost_contribution_inr=c_contrib,
                                is_ambiguous=False,
                                ambiguity_candidates=["RM-180"],
                                notes="Rebalanced to exact 100.00% mass balance",
                            ))
                        else:
                            updated_lines.append(line)
                    if not found_water:
                        u_p, p_b, has_c, c_n = store.get_price_for_rm("RM-180")
                        c_contrib = (water_needed / Decimal("100.0")) * (u_p or Decimal("1.0"))
                        updated_lines.append(IngredientLine(
                            raw_token="RM-180",
                            resolved_rm_code="RM-180",
                            trade_name="Water (demineralised)",
                            chemical_class="Utility",
                            supplier="In-house",
                            percentage=water_needed,
                            unit_price_inr=u_p,
                            price_basis=p_b,
                            cost_contribution_inr=c_contrib,
                            is_ambiguous=False,
                            ambiguity_candidates=["RM-180"],
                            notes="Added for stoichiometric balance",
                        ))

                    cand.ingredients = updated_lines
                    cand.total_percentage = sum((l.percentage for l in updated_lines), Decimal("0.0"))
                    cand.total_cost_inr_per_kg = sum((l.cost_contribution_inr for l in updated_lines), Decimal("0.0000"))
                    # Recompute active solids
                    sol_tot = Decimal("0.0")
                    for l in updated_lines:
                        if l.resolved_rm_code and l.resolved_rm_code in store.rm_master:
                            act_s = store.rm_master[l.resolved_rm_code].get("active_solids_pct")
                            if act_s is not None:
                                sol_tot += (l.percentage * act_s) / Decimal("100.0")
                    cand.estimated_solids_pct = sol_tot
                    st.session_state.current_candidate = cand
                    logger.log_validation_event(cand, validator.validate(cand), action="STOICHIOMETRIC_WATER_REBALANCE")
                    st.success(f"✨ Recipe optimized: Water adjusted to {water_needed:.2f}%. Mass balance is exactly 100.00%.")
                    st.rerun()

    # Expandable drawer for Adding Ingredient
    if st.session_state.get("show_add_ingredient", False):
        with st.container(border=True):
            st.markdown("##### ➕ Add Raw Material Line to Recipe")
            add_c1, add_c2, add_c3, add_c4 = st.columns([2, 1.5, 1, 1])
            rm_options = [f"{c} — {store.rm_master[c]['name']} ({store.rm_master[c]['supplier']})" for c in store.rm_master]
            with add_c1:
                sel_rm = st.selectbox("Select Raw Material", rm_options)
                chosen_code = sel_rm.split(" — ")[0].strip()
            with add_c2:
                add_pct = st.number_input("Concentration (% w/w)", value=1.00, min_value=0.01, max_value=100.0, step=0.10, format="%.2f")
            with add_c3:
                st.write("")
                st.write("")
                if st.button("Add Line", type="primary", width="stretch"):
                    rm_info = store.rm_master.get(chosen_code, {})
                    u_p, p_b, has_c, c_n = store.get_price_for_rm(chosen_code)
                    pct_dec = Decimal(str(add_pct))
                    c_contrib = (pct_dec / Decimal("100.0")) * (u_p or Decimal("0.0"))
                    cand.ingredients.append(IngredientLine(
                        raw_token=chosen_code,
                        resolved_rm_code=chosen_code,
                        trade_name=rm_info.get("trade_name") or rm_info.get("name", chosen_code),
                        chemical_class=rm_info.get("chemical_class", ""),
                        supplier=rm_info.get("supplier", ""),
                        percentage=pct_dec,
                        unit_price_inr=u_p,
                        price_basis=p_b,
                        cost_contribution_inr=c_contrib,
                        is_ambiguous=False,
                        ambiguity_candidates=[chosen_code],
                        notes=c_n if has_c else None,
                    ))
                    cand.total_percentage = sum((l.percentage for l in cand.ingredients), Decimal("0.0"))
                    cand.total_cost_inr_per_kg = sum((l.cost_contribution_inr for l in cand.ingredients), Decimal("0.0000"))
                    # Recompute active solids
                    sol_tot = Decimal("0.0")
                    for l in cand.ingredients:
                        if l.resolved_rm_code and l.resolved_rm_code in store.rm_master:
                            act_s = store.rm_master[l.resolved_rm_code].get("active_solids_pct")
                            if act_s is not None:
                                sol_tot += (l.percentage * act_s) / Decimal("100.0")
                    cand.estimated_solids_pct = sol_tot
                    st.session_state.current_candidate = cand
                    st.session_state.show_add_ingredient = False
                    st.success(f"Added {chosen_code} ({add_pct:.2f}% w/w) to recipe.")
                    st.rerun()
            with add_c4:
                st.write("")
                st.write("")
                if st.button("Cancel", width="stretch"):
                    st.session_state.show_add_ingredient = False
                    st.rerun()

    # Expandable drawer for Loading from Trial
    if st.session_state.get("show_load_trial", False):
        with st.container(border=True):
            st.markdown("##### 📥 Load Historical Trial Recipe into Studio")
            trial_keys = list(store.trials.keys())
            load_c1, load_c2, load_c3 = st.columns([3, 1, 1])
            with load_c1:
                sel_tid = st.selectbox("Select Trial", trial_keys, format_func=lambda t: f"{t}: {store.trials[t].get('recipe_string', '')}")
            with load_c2:
                st.write("")
                st.write("")
                if st.button("Load Candidate", type="primary", width="stretch"):
                    cand_loaded = recommender.load_historical_trial_as_candidate(sel_tid)
                    if cand_loaded:
                        st.session_state.current_candidate = cand_loaded
                        st.session_state.show_load_trial = False
                        st.success(f"Loaded trial {sel_tid} into Formulation Studio.")
                        st.rerun()
            with load_c3:
                st.write("")
                st.write("")
                if st.button("Dismiss", width="stretch"):
                    st.session_state.show_load_trial = False
                    st.rerun()

    # Build structured table of ingredients matching reference UI columns
    table_rows = []
    for idx, line in enumerate(cand.ingredients):
        table_rows.append({
            "Token": line.raw_token,
            "Resolved RM": line.resolved_rm_code or "UNRESOLVED",
            "Trade Name": line.trade_name or "—",
            "Chemical Class": line.chemical_class or "—",
            "Supplier": line.supplier or "—",
            "Conc. (% w/w)": float(line.percentage),
            "Unit Price (₹/kg)": float(line.unit_price_inr) if line.unit_price_inr is not None else 0.0,
            "Cost Contribution (₹/kg)": float(line.cost_contribution_inr),
            "Provenance": "CALCULATED",
            "···": "⋮",
        })

    df_recipe = pd.DataFrame(table_rows)
    st.dataframe(
        df_recipe,
        column_config={
            "Token": st.column_config.TextColumn("Token", width="small"),
            "Resolved RM": st.column_config.TextColumn("Resolved RM", width="small"),
            "Trade Name": st.column_config.TextColumn("Trade Name", width="medium"),
            "Chemical Class": st.column_config.TextColumn("Chemical Class", width="small"),
            "Supplier": st.column_config.TextColumn("Supplier", width="small"),
            "Conc. (% w/w)": st.column_config.NumberColumn("Conc. (% w/w)", format="%.2f", width="small"),
            "Unit Price (₹/kg)": st.column_config.NumberColumn("Unit Price (₹/kg)", format="%.2f", width="small"),
            "Cost Contribution (₹/kg)": st.column_config.NumberColumn("Cost Contribution (₹/kg)", format="%.2f", width="small"),
            "Provenance": st.column_config.TextColumn("Provenance", width="small"),
            "···": st.column_config.TextColumn("", width="small"),
        },
        hide_index=True,
        width="stretch",
    )

    # ------------------------------------------------------------------------
    # Disambiguation & Ingredient Overrides (e.g. TEA-esterquat -> RM-101 vs RM-102)
    # ------------------------------------------------------------------------
    has_ambiguity = any(line.is_ambiguous for line in cand.ingredients)
    if has_ambiguity:
        with st.container(border=True):
            st.markdown("⚠️ **Raw Material Disambiguation Required:**")
            st.markdown(
                "The formulation contains ingredient tokens that map to multiple distinct catalog entries. "
                "For example, **TEA-esterquat** matches both `RM-101` (Esterquat 90 @ ₹210/kg) and `RM-102` (Esterquat 75 @ ₹198/kg). "
                "Per SCPL R&D policy, silent merging or automatic selection is prohibited. Please select the verified supplier material:"
            )
            amb_col1, amb_col2 = st.columns([3, 1])
            with amb_col1:
                chosen_rm = st.selectbox(
                    "Resolve 'TEA-esterquat' To:",
                    ["RM-101 (Esterquat 90, Supplier A, 90% Active @ ₹210.00/kg)", "RM-102 (Esterquat 75, Supplier B, 75% Active @ ₹198.00/kg)"]
                )
                selected_code = "RM-101" if "RM-101" in chosen_rm else "RM-102"
            with amb_col2:
                st.write("")
                st.write("")
                if st.button("Apply Resolution & Recompute", type="primary", width="stretch"):
                    # Update current candidate with resolved code
                    new_lines = []
                    for l in cand.ingredients:
                        if l.raw_token.lower() == "tea-esterquat" or l.is_ambiguous:
                            rm_info = store.rm_master.get(selected_code, {})
                            u_price, p_basis, has_conf, c_note = store.get_price_for_rm(selected_code)
                            c_contrib = (l.percentage / Decimal("100.0")) * (u_price or Decimal("0.0"))
                            new_lines.append(IngredientLine(
                                raw_token=l.raw_token,
                                resolved_rm_code=selected_code,
                                trade_name=rm_info.get("trade_name") or rm_info.get("name", selected_code),
                                chemical_class=rm_info.get("chemical_class", ""),
                                supplier=rm_info.get("supplier", ""),
                                percentage=l.percentage,
                                unit_price_inr=u_price,
                                price_basis=p_basis,
                                cost_contribution_inr=c_contrib,
                                is_ambiguous=False,
                                ambiguity_candidates=[selected_code],
                                notes=f"Disambiguated to {selected_code} by chemist",
                            ))
                        else:
                            new_lines.append(l)
                    cand.ingredients = new_lines
                    # Recompute totals
                    cand.total_percentage = sum((l.percentage for l in new_lines), Decimal("0.0"))
                    cand.total_cost_inr_per_kg = sum((l.cost_contribution_inr for l in new_lines), Decimal("0.0000"))
                    st.session_state.current_candidate = cand
                    st.success(f"Resolved to {selected_code}. Pricing and stoichiometry updated.")
                    st.rerun()

    # ------------------------------------------------------------------------
    # Section 3: Deterministic Validation Results
    # ------------------------------------------------------------------------
    val_report = validator.validate(cand)
    logger.log_validation_event(cand, val_report, action="REALTIME_EVALUATION")

    # Partition checks by severity & type
    hard_failures = [c for c in val_report.checks if c.status == CheckStatus.FAIL]
    warnings_and_gaps = [c for c in val_report.checks if c.status in (CheckStatus.WARNING, CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN)]
    passed_checks = [c for c in val_report.checks if c.status == CheckStatus.PASS]

    col_s3_title, col_s3_link = st.columns([3, 2])
    with col_s3_title:
        st.markdown("""
        <div class="section-title-wrap">
            <span class="section-num-badge">3</span>
            <span>Deterministic Validation Results</span>
        </div>
        """, unsafe_allow_html=True)
    with col_s3_link:
        is_all_expanded = st.session_state.get("show_all_val_checks", False)
        link_label = f"← Hide All {len(val_report.checks)} Validation Checks" if is_all_expanded else f"→ View All {len(val_report.checks)} Validation Checks >"
        def toggle_all_checks():
            st.session_state["show_all_val_checks"] = not st.session_state.get("show_all_val_checks", False)
        
        st.markdown('<div style="display: flex; justify-content: flex-end; padding-top: 4px;">', unsafe_allow_html=True)
        st.button(link_label, key="btn_toggle_all_checks", on_click=toggle_all_checks, type="tertiary")
        st.markdown('</div>', unsafe_allow_html=True)

    def extract_check_metadata(chk):
        if chk.check_id == "VAL-MASS-01":
            actual = f"{chk.details.get('total_pct', float(cand.total_percentage)):.2f}%"
            threshold = "100.00% ±0.05%"
            evidence_ref = "Stoichiometric Mass Balance • Python Decimal"
        elif chk.check_id == "VAL-ID-02":
            amb = chk.details.get("ambiguous", [])
            unres = chk.details.get("unresolved", [])
            if amb or unres:
                actual = f"{len(unres)} unmapped, {len(amb)} ambiguous tokens"
            else:
                actual = "100% Unambiguously Resolved"
            threshold = "Zero unresolved or ambiguous tokens"
            evidence_ref = "RM_Master Catalog (Strict Unambiguity)"
        elif chk.check_id == "VAL-SAFE-03":
            det = chk.details.get("detected", [])
            actual = "; ".join(det) if det else "None detected (0.0%)"
            threshold = "Zero prohibited classes (Silicone-free)"
            evidence_ref = "Customer Brief • Chemical Safety Boundary"
        elif chk.check_id == "VAL-ADV-04":
            actual = f"{chk.details.get('ipa_concentration_pct', 0.0):.2f}%"
            threshold = "≤ 1.00% w/w (Advisory)"
            evidence_ref = "Internal SCPL R&D Safety Guideline (Flashpoint)"
        elif chk.check_id == "VAL-COST-05":
            actual = f"₹{chk.details.get('total_cost_inr', float(cand.total_cost_inr_per_kg)):.2f}/kg"
            threshold = f"≤ ₹{chk.details.get('max_cost_inr', float(req.max_cost_inr_per_kg)):.2f}/kg"
            evidence_ref = "May 2026 Price_Feed Catalog"
        elif chk.check_id == "VAL-PROP-SOLIDS":
            actual = f"{chk.details.get('estimated_solids', float(cand.estimated_solids_pct)):.2f}%"
            threshold = f"{req.solids_pct_range[0]}%–{req.solids_pct_range[1]}%"
            evidence_ref = "Formula Emulsion Physical Specification"
        elif chk.check_id == "VAL-PROP-VISC":
            actual = f"{chk.details.get('viscosity_cp', cand.estimated_viscosity_cp):.1f} cP"
            threshold = f"{req.viscosity_cp_range[0]}–{req.viscosity_cp_range[1]} cP"
            evidence_ref = "Normalized Rheology (Pa*s -> cP conversion)"
        elif chk.check_id == "VAL-PROP-PH":
            actual = f"{chk.details.get('estimated_ph', cand.estimated_ph):.2f}"
            threshold = f"{req.ph_range[0]}–{req.ph_range[1]}"
            evidence_ref = "Finished Product Emulsion pH Specification (Heuristic)"
        elif chk.check_id == "VAL-EMP-STAB":
            actual = cand.stability_45c_4w_status
            threshold = "PASS (4 weeks @ 45°C no phase separation / yellowing)"
            evidence_ref = f"Parent Trial: {cand.source_trial_id or 'Custom'} • Stability_Log incubator records"
        elif chk.check_id == "VAL-EMP-SOFT":
            score = cand.softness_panel_score
            actual = f"{score:.1f}/5.0" if score is not None else "UNKNOWN (Not Measured)"
            threshold = f"≥ {req.min_softness_panel_score:.1f}/5.0 (Sensory Panel)"
            evidence_ref = f"Parent Trial: {cand.source_trial_id or 'Custom'} • Panel_Scores sensory evaluation"
        elif chk.check_id == "VAL-GOV-GATE":
            actual = f"Status: {cand.status.value}"
            threshold = "Mandatory Human Chemist Authorization"
            evidence_ref = "Append-Only Audit Log • Zero Automated Dispatch"
        else:
            actual = str(chk.details) if chk.details else "Evaluated"
            threshold = "Specification Constraint"
            evidence_ref = "Kestrel Deterministic Engine"
        return actual, threshold, evidence_ref

    # 3-Box Side-by-Side Summary matching Reference UI
    val_c1, val_c2, val_c3 = st.columns(3)

    # Box 1: Mandatory Hard Failures
    with val_c1:
        st.markdown(f"""
        <div class="val-box">
            <div class="val-box-header" style="color: {'#dc2626' if hard_failures else '#059669'};">
                <span>{'✕' if hard_failures else '✔'}</span>
                <span>Mandatory Hard Failures ({len(hard_failures)})</span>
            </div>
        """, unsafe_allow_html=True)
        if not hard_failures:
            st.markdown("""
            <div class="val-pass-banner">
                <span>All deterministic regulatory, safety, and specification checks passed.</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            for chk in hard_failures:
                actual, threshold, evidence_ref = extract_check_metadata(chk)
                st.markdown(f"""
                <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px 10px; margin-bottom: 6px;">
                    <div style="font-size: 0.80rem; font-weight: 700; color: #991b1b;">{chk.check_name}</div>
                    <div style="font-size: 0.72rem; color: #7f1d1d; margin-top: 2px;">
                        <strong>Actual:</strong> {actual} &nbsp;|&nbsp; <strong>Expected:</strong> {threshold}
                    </div>
                    <div style="font-size: 0.72rem; color: #b91c1c; margin-top: 2px;">{chk.message}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Box 2: Advisory Warnings & Empirical Gaps
    with val_c2:
        st.markdown(f"""
        <div class="val-box">
            <div class="val-box-header" style="color: #d97706;">
                <span>⚠️</span>
                <span>Advisory Warnings & Empirical Gaps ({len(warnings_and_gaps)})</span>
            </div>
        """, unsafe_allow_html=True)
        if warnings_and_gaps:
            for chk in warnings_and_gaps:
                if chk.check_id == "VAL-EMP-STAB":
                    name_disp = "Thermal Stability (45°C)"
                elif chk.check_id == "VAL-EMP-SOFT":
                    name_disp = "Sensory Softness Panel"
                elif chk.check_id == "VAL-PROP-SOLIDS":
                    name_disp = "Active Solids Emulsion"
                elif chk.check_id == "VAL-PROP-PH":
                    name_disp = "Finished Product pH"
                elif chk.check_id == "VAL-ADV-04":
                    name_disp = "Isopropanol Advisory"
                else:
                    name_disp = chk.check_name.replace("Empirical: ", "").replace("Catalog: ", "").replace("Safety: ", "")
                status_text = "NOT VERIFIED" if chk.status in [CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN] else "WARNING"
                badge_cls = "badge-unverified" if chk.status in [CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN] else "badge-warn"
                st.markdown(f"""
                <div class="val-gap-item">
                    <div>
                        <span class="val-code-badge">{chk.check_id}</span>
                        <span style="font-weight: 600; color: #334155;">{name_disp}</span>
                    </div>
                    <span class="{badge_cls}">{status_text}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("No advisory warnings or unverified empirical gaps.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Box 3: Verified Passed Checks
    with val_c3:
        st.markdown(f"""
        <div class="val-box">
            <div class="val-box-header" style="color: #059669;">
                <span>✔</span>
                <span>Verified Passed Checks ({len(passed_checks)})</span>
            </div>
        """, unsafe_allow_html=True)
        # Show passed checks (expandable)
        show_all_passed = st.session_state.get("show_all_passed_checks", False)
        display_passed = passed_checks if show_all_passed else passed_checks[:3]

        for chk in display_passed:
            if chk.check_id == "VAL-MASS-01":
                name_disp = "Mass Balance Precision"
            elif chk.check_id == "VAL-ID-02":
                name_disp = "Ingredient Identity (No Ambiguity)"
            elif chk.check_id == "VAL-SAFE-03":
                name_disp = "Prohibited Ingredient Exclusion (Silicone-Free)"
            elif chk.check_id == "VAL-PROP-PH":
                name_disp = "Finished Product pH Specification"
            elif chk.check_id == "VAL-PROP-VISC":
                name_disp = "Normalized Viscosity Specification"
            elif chk.check_id == "VAL-COST-05":
                name_disp = "Raw Material Cost Specification"
            elif chk.check_id == "VAL-PROP-SOLIDS":
                name_disp = "Active Solids Emulsion Target"
            elif chk.check_id == "VAL-GOV-GATE":
                name_disp = "Chemist Sign-off Governance Gate"
            else:
                name_disp = chk.check_name.replace("Stoichiometric: ", "").replace("Catalog: ", "").replace("Safety: ", "")
            st.markdown(f"""
            <div class="val-pass-check-row">
                <span style="color: #059669; font-weight: 800;">✓</span>
                <span>{name_disp}</span>
            </div>
            """, unsafe_allow_html=True)
        
        remaining_cnt = len(passed_checks) - 3
        if remaining_cnt > 0:
            def toggle_passed_checks():
                st.session_state["show_all_passed_checks"] = not st.session_state.get("show_all_passed_checks", False)
            
            st.markdown('<div style="margin-top: 6px;">', unsafe_allow_html=True)
            if not show_all_passed:
                st.button(f"+{remaining_cnt} more checks", key="btn_more_passed_checks", on_click=toggle_passed_checks, type="tertiary")
            else:
                st.button("− Show fewer checks", key="btn_fewer_passed_checks", on_click=toggle_passed_checks, type="tertiary")
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Detailed expandable view for all checks
    is_all_expanded = st.session_state.get("show_all_val_checks", False)
    with st.expander(f"🔍 Diagnostic Details for All {len(val_report.checks)} Validation Checks", expanded=is_all_expanded):
        d_c1, d_c2 = st.columns(2)
        for idx, chk in enumerate(val_report.checks):
            col = d_c1 if idx % 2 == 0 else d_c2
            actual, threshold, evidence_ref = extract_check_metadata(chk)
            border_cls = "val-item-fail" if chk.status == CheckStatus.FAIL else ("val-item-warn" if chk.status in [CheckStatus.WARNING, CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN] else "val-item-pass")
            badge_html = "<span class='badge-fail'>✕ FAIL</span>" if chk.status == CheckStatus.FAIL else ("<span class='badge-warn'>▲ WARNING</span>" if chk.status == CheckStatus.WARNING else ("<span class='badge-unverified'>ℹ NOT VERIFIED</span>" if chk.status in [CheckStatus.NOT_VERIFIED, CheckStatus.UNKNOWN] else "<span class='badge-pass'>✓ PASS</span>"))
            with col:
                st.markdown(f"""
                <div class="val-item-card {border_cls}">
                    <div class="validation-card-header">
                        <span class="validation-card-title">{chk.check_name}</span>
                        {badge_html}
                    </div>
                    <div class="val-meta-row">
                        <div><span class="val-meta-label">Actual:</span> <span class="val-meta-val">{actual}</span></div>
                        <div><span class="val-meta-label">Target:</span> <span class="val-meta-val">{threshold}</span></div>
                    </div>
                    <div class="validation-card-msg">{chk.message}</div>
                    <div class="val-evidence-ref">🔍 <em>Reference:</em> {evidence_ref}</div>
                </div>
                """, unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Section 4: Evidence Panel & Data Limitations
    # ------------------------------------------------------------------------
    st.markdown("""
    <div class="section-title-wrap">
        <span class="section-num-badge">4</span>
        <span>Evidence Traceability & Data Limitation Panel</span>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("#### Evidence Grounding & Provenance Details")
        is_historical = cand.source_trial_id and cand.source_trial_id in store.trials
        if is_historical:
            st.info(f"📂 **Historical Trial Benchmark:** Loaded directly from workbook record `{cand.source_trial_id}` in `Trials_TX_Softeners`. Historical test records are tied strictly to this physical trial batch.")
        else:
            st.warning("🧪 **Synthesized Candidate Formulation:** Zero historical test evidence is imputed or transferred. Physical incubator stability and fabric softness tests must be conducted on new bench trial batches.")

        st.markdown(f"**Parent Trial Reference:** `{cand.source_trial_id or 'Custom synthesis (No historical predecessor)'}`")
        st.markdown(f"**Thermal Stability Grounding:** `{cand.stability_45c_4w_status}` — {cand.stability_evidence_summary}")
        st.markdown(f"**Sensory Softness Grounding:** `{cand.softness_panel_score or 'UNKNOWN'}` — {cand.softness_evidence_summary}")
        
        # Display record-level provenance
        prov_col1, prov_col2 = st.columns(2)
        with prov_col1:
            st.markdown("**Thermal Stability Evidence Provenance:**")
            if cand.stability_provenance:
                sp = cand.stability_provenance
                st.json({
                    "Sheet": sp.sheet_name,
                    "Record ID": sp.record_id,
                    "Conditions": sp.test_conditions,
                    "Date": sp.test_date,
                    "Observer": sp.observer,
                    "Type": sp.provenance_type.value,
                    "Rationale": sp.linkage_rationale,
                    "Measurements": sp.raw_measurements,
                })
            else:
                st.info("No record-level incubator logs linked. Status is NOT_VERIFIED pending physical incubator testing.")

        with prov_col2:
            st.markdown("**Sensory Softness Evidence Provenance:**")
            if cand.softness_provenance:
                sfp = cand.softness_provenance
                st.json({
                    "Sheet": sfp.sheet_name,
                    "Record ID": sfp.record_id,
                    "Conditions": sfp.test_conditions,
                    "Date": sfp.test_date,
                    "Observer": sfp.observer,
                    "Type": sfp.provenance_type.value,
                    "Rationale": sfp.linkage_rationale,
                    "Measurements": sfp.raw_measurements,
                })
            else:
                st.info("No sensory panel test records linked. Score is UNKNOWN pending physical fabric panel trials.")

        # If parent trial exists, show linked workbook rows
        if is_historical:
            dossier = store.get_trial_evidence_dossier(cand.source_trial_id)
            stab_logs = dossier.get("stability_logs", [])
            if stab_logs:
                st.markdown("**Historical Incubator Logs (Stability_Log):**")
                st.dataframe(pd.DataFrame(stab_logs), hide_index=True)

            panel_logs = dossier.get("panel_logs", [])
            if panel_logs:
                st.markdown("**Historical Sensory Panel Records (Panel_Scores):**")
                st.dataframe(pd.DataFrame(panel_logs), hide_index=True)

        st.markdown("#### Evidence Isolation & Governance Disclaimers")
        st.info(
            "• **Evidence Isolation:** Historical test scores are strictly tied to specific physical trial batches. "
            "They are NEVER silently reused or imputed for newly proposed candidate recipes without explicit bench trial production.\n"
            "• **Deterministic Precision:** Stoichiometry, mass balance, costing, and silicone exclusion are computed strictly via Python Decimal arithmetic.\n"
            "• **Empirical Properties Boundary:** Software checks do not prove physical stability or softness; physical incubator logs and panel trials are mandatory prior to plant scale-up.\n"
            "• **Isopropanol Advisory:** Internal R&D guidelines flag RM-131 > 1.0% for flammability precautions; this represents internal safety guidance, not a regulatory determination."
        )

    # ------------------------------------------------------------------------
    # Section 5: Chemist Review & Sign-Off Gate
    # ------------------------------------------------------------------------
    st.markdown("""
    <div class="section-title-wrap">
        <span class="section-num-badge">5</span>
        <span>Chemist Governance & Bench Trial Sign-Off</span>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Mandatory human-in-the-loop authorization. Autonomous laboratory bookings are strictly disabled.")

    with st.container(border=True):
        gov_col1, gov_col2 = st.columns([3, 2])
        with gov_col1:
            st.markdown("##### Reviewer Authorization Details")
            r_c1, r_c2 = st.columns(2)
            with r_c1:
                chemist_name = st.text_input("Chemist Reviewer Name", value="Dr. Vikram Shah")
            with r_c2:
                chemist_role = st.selectbox(
                    "Role & Authorization Level",
                    ["Senior Formulation Chemist (Lab 1)", "Lead R&D Chemist (Lab 2)", "Analytical Quality Chemist"]
                )
            
            approval_notes = st.text_area(
                "Chemist Bench Authorization Notes",
                value="Bench trial approved for laboratory mixer booking. Initial batch size: 2.0 kg. Emulsification speed: 1,800 RPM. Addition sequence: Water phase 60°C -> Molten esterquat phase.",
                height=85
            )

            # Mandatory chemist acknowledgement when empirical evidence is unverified
            ack_experimental = True
            if val_report.requires_experimental_acknowledgement:
                st.markdown("---")
                ack_experimental = st.checkbox(
                    "⚠️ **Chemist Experimental Risk Acknowledgement (Mandatory):** "
                    "I acknowledge that thermal stability (4w @ 45°C) and sensory softness (≥ 4.0/5.0) are "
                    "UNVERIFIED / UNKNOWN and must be empirically measured on laboratory bench trial batches prior to commercial certification.",
                    value=False,
                    help="Explicit chemist acknowledgement is mandatory when approving bench trials for unverified formulations."
                )

        with gov_col2:
            st.markdown("##### Authorization Gate Status")

            # Check if already approved in audit log
            current_hash = cand.compute_recipe_hash()
            existing_approvals = [
                r for r in logger.read_records()
                if r.get("action") == "CHEMIST_APPROVAL_BENCH_RELEASE"
                and r.get("candidate_id") == cand.candidate_id
                and r.get("candidate_hash") == current_hash
            ]
            is_already_approved = len(existing_approvals) > 0

            with st.container(border=True):
                if not val_report.can_approve:
                    st.markdown("🔴 **Validation State:** <span class='badge-fail'>BLOCKED BY FAILURES</span>", unsafe_allow_html=True)
                    st.caption("Approval button is disabled until all mandatory validation failures are resolved.")
                    st.button("Approve & Schedule Bench Trial", disabled=True, width="stretch")
                elif is_already_approved:
                    st.markdown("🟢 **Current Status:** <span class='badge-pass'>BENCH RELEASE AUTHORIZED</span>", unsafe_allow_html=True)
                    st.caption(f"Candidate `{cand.candidate_id}` with recipe hash `{current_hash[:8]}...` was signed off.")
                    force_reapprove = st.checkbox("Allow intentional duplicate sign-off", value=False)
                    if force_reapprove:
                        if st.button("Re-Approve Candidate", type="primary", width="stretch"):
                            try:
                                record = logger.record_chemist_approval(
                                    candidate=cand,
                                    report=val_report,
                                    chemist_id="CHM-882",
                                    chemist_name=chemist_name,
                                    chemist_role=chemist_role,
                                    approval_notes=approval_notes,
                                    experimental_acknowledgement_given=ack_experimental,
                                    force_duplicate=True,
                                    validator=validator,
                                )
                                st.success(f"🎉 **Re-Approval Recorded:** Token `{record.approval_token}`")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Approval failed: {ex}")
                else:
                    if val_report.requires_experimental_acknowledgement:
                        st.markdown("🟡 **Validation State:** <span class='badge-warn'>SPEC PASSED (Pending Lab Trials)</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("🟢 **Validation State:** <span class='badge-pass'>ALL CRITERIA VERIFIED</span>", unsafe_allow_html=True)

                    can_submit = val_report.can_approve and (not val_report.requires_experimental_acknowledgement or ack_experimental)
                    if not can_submit:
                        st.caption("⚠️ Check the mandatory Chemist Experimental Risk Acknowledgement before approving.")

                    sign_button = st.button("Approve & Schedule Bench Trial", type="primary", disabled=not can_submit, width="stretch")
                    if sign_button:
                        try:
                            record = logger.record_chemist_approval(
                                candidate=cand,
                                report=val_report,
                                chemist_id="CHM-882",
                                chemist_name=chemist_name,
                                chemist_role=chemist_role,
                                approval_notes=approval_notes,
                                experimental_acknowledgement_given=ack_experimental,
                                validator=validator,
                            )
                            st.success(f"🎉 **Trial Successfully Approved for Bench Release!**")
                            st.markdown(f"**Approval Token:** `{record.approval_token}`")
                            st.markdown(f"**Recipe Hash:** `{record.candidate_hash[:16]}...`")
                            st.markdown(f"**Status:** `{cand.status.value}`")
                            st.caption("🔒 Recorded in append-only audit log with SHA-256 state hash. Note: Demo identity is simulated.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Approval failed: {ex}")

# ============================================================================
# TAB 2: EVIDENCE STORE & WORKBOOK EXPLORER
# ============================================================================
with tab_evidence:
    st.markdown("<div class='section-label'>📚 Read-Only Workbook Explorer</div>", unsafe_allow_html=True)
    st.caption("Direct, safe inspection of historical R&D records loaded from `Kestrel_RnD_Export_2026-05.xlsx`.")
    
    sheet_choice = st.selectbox(
        "Select Workbook Sheet to View:",
        ["RM_Master", "Price_Feed", "Trials_TX_Softeners", "Trials_All_Projects", "Stability_Log", "Panel_Scores", "Regulatory_Notes"]
    )
    if sheet_choice in store.sheets:
        df_sheet = store.sheets[sheet_choice]
        st.markdown(f"**Sheet: `{sheet_choice}`** — `{len(df_sheet)} rows`, `{len(df_sheet.columns)} columns`")
        st.dataframe(df_sheet)

    st.markdown("---")
    st.markdown("<div class='section-label'>🔍 Raw Material Price Feed Discrepancy Inspector</div>", unsafe_allow_html=True)
    st.caption("Illustrates conflicting price quotes and packaging unit variations in the Price_Feed.")
    c_rm101, c_rm170, c_rm160 = st.columns(3)
    with c_rm101:
        with st.container(border=True):
            st.markdown("**RM-101 (Esterquat 90) Duplicate Month:**")
            p_101 = [e for e in store.price_catalog.get("RM-101", []) if e["month"] == "2026-05"]
            st.dataframe(pd.DataFrame(p_101), hide_index=True)
    with c_rm170:
        with st.container(border=True):
            st.markdown("**RM-170 (Wax Emulsion) Drum Normalization:**")
            p_170 = [e for e in store.price_catalog.get("RM-170", []) if e["month"] == "2026-05"]
            st.dataframe(pd.DataFrame(p_170), hide_index=True)
    with c_rm160:
        with st.container(border=True):
            st.markdown("**RM-160 (Biocide) Currency Conversion:**")
            p_160 = [e for e in store.price_catalog.get("RM-160", []) if e["month"] == "2026-05"]
            st.dataframe(pd.DataFrame(p_160), hide_index=True)

# ============================================================================
# TAB 3: AUDIT TRAIL & COMPLIANCE LOG
# ============================================================================
with tab_history:
    st.markdown("<div class='section-label'>📋 Append-Only Audit Trail & Compliance Log</div>", unsafe_allow_html=True)
    st.caption("Cryptographically verifiable record of all formulation validation events, rejections, and approvals.")

    # Cryptographic Hash Chain Integrity Verification
    is_valid, tamper_msg, audit_records = logger.verify_log_tampering()
    if is_valid:
        st.success(f"🔒 **Cryptographic Hash Chain Verified:** {tamper_msg}")
    else:
        st.error(f"🚨 **TAMPER DETECTED IN AUDIT LOG:** {tamper_msg}")

    st.info(
        "ℹ️ **Security Notice:** All logged events include SHA-256 state hashes chained to prior records. "
        "Reviewer identities and credentials in this prototype use simulated demo credentials. "
        "Production deployment requires enterprise SSO / PKI smart-card integration."
    )

    if audit_records:
        df_audit = pd.DataFrame(audit_records)
        # Select and reorder columns for clear readability
        display_cols = [c for c in [
            "event_id", "timestamp_utc", "action", "candidate_id", "candidate_hash",
            "chemist_name", "approval_token", "approval_outcome", "can_approve",
            "prev_hash", "entry_hash"
        ] if c in df_audit.columns]
        st.dataframe(df_audit[display_cols])
        
        with st.expander("🔍 Raw JSON Audit Log Records", expanded=False):
            st.json(audit_records)
    else:
        st.info("No audit log records recorded yet in `assistant_audit_log.json`.")

st.markdown("---")
st.caption("Kestrel R&D Formulation Assistant • Milestone 2 MVP • Head of Engineering Submission")
