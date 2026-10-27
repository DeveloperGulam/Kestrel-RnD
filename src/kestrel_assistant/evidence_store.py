"""
Evidence Store for Kestrel R&D Formulation Assistant.
Provides safe, read-only extraction and indexing of historical R&D workbook records.
Never mutates the underlying workbook file.
"""

from decimal import Decimal
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from kestrel_audit.loader import ReadOnlyWorkbookLoader
from .models import IngredientLine


class EvidenceStore:
    """Read-only workbook cache and evidence indexing engine."""

    FX_USD_TO_INR = Decimal("84.00")  # Historical workbook basis as of 2026-05-01
    DRUM_KG_CONVERSION = Decimal("200.0")  # RM-170 packaging: 200 kg drum

    def __init__(self, workbook_path: Optional[str | Path] = None):
        if workbook_path is None:
            # Default to root workbook
            workbook_path = Path(__file__).resolve().parent.parent.parent / "Kestrel_RnD_Export_2026-05.xlsx"
        self.workbook_path = Path(workbook_path).resolve()
        self.loader = ReadOnlyWorkbookLoader(self.workbook_path)
        self.sheets: Dict[str, pd.DataFrame] = {}
        
        # Catalogs
        self.rm_master: Dict[str, Dict[str, Any]] = {}
        self.synonym_index: Dict[str, List[str]] = {}
        self.price_catalog: Dict[str, List[Dict[str, Any]]] = {}
        self.trials: Dict[str, Dict[str, Any]] = {}
        self.stability_records: Dict[str, List[Dict[str, Any]]] = {}
        self.panel_records: Dict[str, List[Dict[str, Any]]] = {}
        self.regulatory_notes: Dict[str, List[str]] = {}
        
        self.load_and_index()

    def load_and_index(self) -> None:
        """Loads all workbook sheets in read-only mode and indexes cross-sheet relationships."""
        self.sheets = self.loader.load_all_sheets()
        self._index_rm_master()
        self._index_price_feed()
        self._index_trials()
        self._index_stability_log()
        self._index_panel_scores()
        self._index_regulatory_notes()

    def _index_rm_master(self) -> None:
        if "RM_Master" not in self.sheets:
            return
        df = self.sheets["RM_Master"]
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            if not code or code == "nan":
                continue
            
            raw_notes = str(row.get("notes", ""))
            solids_dec = None
            m_sol = re.search(r"(\d+(?:\.\d+)?)%\s*(?:active|solids)", raw_notes)
            if m_sol:
                solids_dec = Decimal(m_sol.group(1))
            elif "water" in str(row.get("name", "")).lower():
                solids_dec = Decimal("0.0")
            elif "70%" in str(row.get("name", "")):
                solids_dec = Decimal("70.0")
            elif "40%" in str(row.get("name", "")):
                solids_dec = Decimal("40.0")
            elif "15%" in str(row.get("name", "")):
                solids_dec = Decimal("15.0")
            
            raw_list_price = row.get("list_price")
            price_dec = Decimal(str(raw_list_price)) if pd.notna(raw_list_price) else None

            entry = {
                "code": code,
                "name": str(row.get("name", "")).strip(),
                "trade_name": str(row.get("name", "")).strip(),
                "supplier": str(row.get("supplier", "")).strip(),
                "chemical_class": str(row.get("category", "")).strip(),
                "category": str(row.get("category", "")).strip(),
                "function": str(row.get("function", "")).strip(),
                "active_solids_pct": solids_dec,
                "list_price": price_dec,
                "currency": str(row.get("currency", "INR")).strip(),
                "uom": str(row.get("uom", "kg")).strip(),
                "notes": raw_notes,
                "synonyms": [],
            }
            
            syn_str = str(row.get("synonyms", ""))
            if syn_str and syn_str != "nan":
                for s in syn_str.split(";"):
                    s_clean = s.strip()
                    if s_clean and s_clean != "nan":
                        entry["synonyms"].append(s_clean)
                        # Index exact lower
                        self.synonym_index.setdefault(s_clean.lower(), []).append(code)
                        # Index hyphen-normalized
                        norm_s = s_clean.lower().replace("-", " ")
                        if norm_s != s_clean.lower():
                            self.synonym_index.setdefault(norm_s, []).append(code)

            # Also index code and name
            self.synonym_index.setdefault(code.lower(), []).append(code)
            name_clean = entry["name"].lower().replace("-", " ")
            self.synonym_index.setdefault(name_clean, []).append(code)
            self.synonym_index.setdefault(entry["name"].lower(), []).append(code)

            self.rm_master[code] = entry

    def _index_price_feed(self) -> None:
        if "Price_Feed" not in self.sheets:
            return
        df = self.sheets["Price_Feed"].sort_values(by="month")
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            if not code or code == "nan":
                continue
            
            raw_price = row.get("price")
            price_dec = Decimal(str(raw_price)) if pd.notna(raw_price) else Decimal("0.0")

            entry = {
                "code": code,
                "month": str(row.get("month", "")).strip(),
                "price": price_dec,
                "currency": str(row.get("currency", "INR")).strip(),
                "source": str(row.get("source", "")).strip(),
                "entry_type": str(row.get("entry_type", "")).strip(),
            }
            self.price_catalog.setdefault(code, []).append(entry)

    def _index_trials(self) -> None:
        # Index Trials_TX_Softeners
        if "Trials_TX_Softeners" in self.sheets:
            df = self.sheets["Trials_TX_Softeners"]
            for _, row in df.iterrows():
                tid = str(row.get("trial_id", "")).strip()
                if not tid or tid == "nan":
                    continue
                
                recipe_raw = str(row.get("formulation_pct") or row.get("recipe") or "").strip()
                
                visc_raw = str(row.get("viscosity", "")).strip()
                visc_cp = None
                if visc_raw and visc_raw != "nan":
                    # Check if Pa*s (e.g. 0.45 Pa*s = 450 cP)
                    if "pa" in visc_raw.lower():
                        m_v = re.search(r"(\d+(?:\.\d+)?)", visc_raw)
                        if m_v:
                            visc_cp = float(m_v.group(1)) * 1000.0
                    else:
                        m_v = re.search(r"(\d+(?:\.\d+)?)", visc_raw)
                        if m_v:
                            visc_cp = float(m_v.group(1))

                # Softness score
                soft_raw = str(row.get("softness", "")).strip()
                soft_dec = None
                if soft_raw and soft_raw != "nan":
                    try:
                        s_val = soft_raw.split("/")[0].strip()
                        soft_dec = Decimal(s_val)
                    except Exception:
                        soft_dec = None

                self.trials[tid] = {
                    "trial_id": tid,
                    "sheet": "Trials_TX_Softeners",
                    "project_name": str(row.get("project", "")).strip(),
                    "customer_request_id": str(row.get("customer_request_id", "")).strip(),
                    "recipe_string": recipe_raw,
                    "solids_pct": float(row.get("solids_pct")) if pd.notna(row.get("solids_pct")) else None,
                    "ph": float(row.get("ph")) if pd.notna(row.get("ph")) else None,
                    "viscosity_raw": visc_raw,
                    "viscosity_cp": visc_cp,
                    "softness_score": soft_dec,
                    "stability_label": str(row.get("stability_45c_4wk", "")).strip(),
                    "approved_by": None if pd.isna(row.get("approved_by")) or str(row.get("approved_by")).strip() in ("", "nan", "None") else str(row.get("approved_by")).strip(),
                    "date": str(row.get("date", "")).strip(),
                }

    def _index_stability_log(self) -> None:
        if "Stability_Log" not in self.sheets:
            return
        df = self.sheets["Stability_Log"]
        for _, row in df.iterrows():
            sid = str(row.get("sample_id", "")).strip()
            if not sid or sid == "nan":
                continue
            entry = {
                "sample_id": sid,
                "week": int(row.get("week")) if pd.notna(row.get("week")) else None,
                "temp_c": int(row.get("temp_c")) if pd.notna(row.get("temp_c")) else None,
                "appearance": str(row.get("appearance", "")).strip(),
                "phase_sep": str(row.get("phase_sep", "")).strip().upper(),
                "colour_b_star": float(row.get("colour_b_star")) if pd.notna(row.get("colour_b_star")) else None,
                "observer": str(row.get("observer", "")).strip(),
            }
            self.stability_records.setdefault(sid, []).append(entry)

    def _index_panel_scores(self) -> None:
        if "Panel_Scores" not in self.sheets:
            return
        df = self.sheets["Panel_Scores"]
        for _, row in df.iterrows():
            sid = str(row.get("trial_id") or row.get("sample_id") or "").strip()
            if not sid or sid == "nan":
                continue
            
            raw_score = row.get("score") if "score" in row and pd.notna(row.get("score")) else row.get("softness_score")
            score_dec = None
            if pd.notna(raw_score):
                try:
                    s_str = str(raw_score).split("/")[0].strip()
                    score_dec = Decimal(s_str)
                except Exception:
                    score_dec = None

            entry = {
                "trial_id": sid,
                "panelist": str(row.get("panelist", "")).strip(),
                "test_date": str(row.get("test_date", "")).strip(),
                "softness_score": score_dec,
                "scale": str(row.get("scale", "1-5")).strip(),
                "substrate": str(row.get("substrate", "")).strip(),
                "raw_score_str": str(raw_score).strip(),
                "hand_feel": str(row.get("hand_feel", "")).strip(),
                "comments": str(row.get("comments", "")).strip(),
            }
            self.panel_records.setdefault(sid, []).append(entry)


    def _index_regulatory_notes(self) -> None:
        if "Regulatory_Notes" not in self.sheets:
            return
        df = self.sheets["Regulatory_Notes"]
        for _, row in df.iterrows():
            rm = str(row.get("raw_material", "")).strip()
            cas = str(row.get("cas_number", "")).strip()
            note = str(row.get("notes", "")).strip()
            if rm:
                self.regulatory_notes.setdefault(rm.lower(), []).append(note)
            if cas:
                self.regulatory_notes.setdefault(cas.lower(), []).append(note)

    # ------------------------------------------------------------------------
    # Retrieval & Resolution APIs
    # ------------------------------------------------------------------------

    def resolve_ingredient_token(self, token: str) -> Tuple[Optional[str], bool, List[str], str]:
        """
        Resolves a chemical token to master RM code.
        Never silently merges ambiguous synonyms like TEA-esterquat (RM-101 vs RM-102).
        """
        t = token.strip()
        t_lower = t.lower()
        t_norm = t_lower.replace("-", " ")

        # 1. Exact match on master code
        if t in self.rm_master:
            return t, False, [t], f"Exact match on master RM code: {t}"

        # 2. Check synonym index (both exact and hyphen-normalized)
        matches_exact = self.synonym_index.get(t_lower, [])
        matches_norm = self.synonym_index.get(t_norm, [])
        unique_matches = list(dict.fromkeys(matches_exact + matches_norm))

        if len(unique_matches) == 1:
            code = unique_matches[0]
            return code, False, unique_matches, f"Resolved '{t}' -> {code} ({self.rm_master[code]['name']})"
        elif len(unique_matches) > 1:
            cands_desc = [f"{c} ({self.rm_master[c]['name']})" for c in unique_matches]
            return None, True, unique_matches, f"Ambiguous synonym '{t}' maps to multiple raw materials: {', '.join(cands_desc)}. Explicit chemist selection required."
        else:
            return None, False, [], f"Unmapped ingredient token '{t}' not found in RM_Master."

    def get_price_for_rm(
        self,
        rm_code: str,
        preferred_month: Optional[str] = "2026-05",
        allow_manual_quote: bool = False
    ) -> Tuple[Optional[Decimal], str, bool, str]:
        """
        Retrieves authoritative normalized price in INR/kg for an RM code.
        Handles:
            - Currency conversion (USD -> INR using FX 84.00)
            - Unit normalization (drum -> kg using 200 kg drum factor)
            - Conflict detection (flags multiple entries in same month, e.g. RM-101 210 vs 228)
        """
        if rm_code not in self.rm_master:
            return None, "Unregistered RM", False, f"Raw material {rm_code} not registered in master catalog."

        master_entry = self.rm_master[rm_code]
        master_uom = master_entry["uom"].lower()
        is_drum_rm = "drum" in master_uom or "200 kg" in master_uom

        feed_entries = self.price_catalog.get(rm_code, [])
        if not feed_entries:
            # Fall back to master catalog list price
            list_p = master_entry["list_price"]
            curr = master_entry["currency"]
            if list_p is not None:
                unit_price = list_p
                basis = f"RM_Master list price ({list_p} {curr})"
                if is_drum_rm and unit_price > Decimal("1000.0"):
                    unit_price = unit_price / self.DRUM_KG_CONVERSION
                    basis += f" [Normalized from drum ÷ 200 kg = ₹{unit_price:.2f}/kg]"
                if curr.upper() == "USD":
                    unit_price = unit_price * self.FX_USD_TO_INR
                    basis += f" [Converted from USD @ {self.FX_USD_TO_INR} FX]"
                return unit_price, basis, False, "Stale list price from RM_Master (no recent feed available)."
            return None, "No Price Available", False, "No price in Price_Feed or RM_Master."

        # Filter by month if specified, else use latest
        month_entries = [e for e in feed_entries if e["month"] == preferred_month] if preferred_month else []
        if not month_entries:
            month_entries = [feed_entries[-1]]

        # Check for duplicate conflicting price entries in the target month
        has_conflict = len(month_entries) > 1
        conflict_note = ""
        if has_conflict:
            prices_str = ", ".join([f"₹{e['price']} ({e['source']} - {e['entry_type']})" for e in month_entries])
            conflict_note = f"Multiple conflicting price records for {rm_code} in {preferred_month}: [{prices_str}]."

        # Determine chosen entry
        chosen = None
        if allow_manual_quote:
            for e in month_entries:
                if "quote" in e["entry_type"].lower() or "manual" in e["entry_type"].lower():
                    chosen = e
                    break
        if chosen is None:
            # Prefer PurchaseOne auto feed
            for e in month_entries:
                if "auto" in e["entry_type"].lower() or "purchaseone" in e["source"].lower():
                    chosen = e
                    break
            if chosen is None:
                chosen = month_entries[0]

        raw_price = chosen["price"]
        source_str = chosen["source"].lower()
        curr = chosen["currency"].upper()
        basis = f"Price_Feed ({chosen['month']} {chosen['source']})"

        # Unit normalization
        unit_price = raw_price
        if is_drum_rm:
            # If price is drum price (e.g. 32,800), normalize by 200 kg
            if raw_price > Decimal("1000.0") and "kg" not in source_str:
                unit_price = raw_price / self.DRUM_KG_CONVERSION
                basis += f" [Normalized from ₹{raw_price}/drum ÷ 200kg = ₹{unit_price:.2f}/kg]"
            else:
                basis += f" [Verified quote per kg = ₹{unit_price:.2f}/kg]"

        # Currency conversion
        if curr == "USD":
            unit_price = unit_price * self.FX_USD_TO_INR
            basis += f" [Converted from ${raw_price} USD @ {self.FX_USD_TO_INR} FX = ₹{unit_price:.2f}/kg]"

        return unit_price, basis, has_conflict, conflict_note

    def parse_recipe_string(
        self,
        recipe_str: str,
        overrides: Optional[Dict[str, str]] = None
    ) -> List[IngredientLine]:
        """
        Parses chemical recipe string into typed IngredientLine models with Decimal calculations.
        """
        lines: List[IngredientLine] = []
        if not recipe_str or pd.isna(recipe_str) or str(recipe_str).strip() in ("", "nan"):
            return lines

        overrides = overrides or {}
        parts = [p.strip() for p in str(recipe_str).split(";") if p.strip()]

        for part in parts:
            if ":" not in part:
                continue
            token, pct_str = part.split(":", 1)
            token = token.strip()
            pct_str = pct_str.strip()
            
            try:
                pct = Decimal(pct_str)
            except Exception:
                pct = Decimal("0.0")

            # Check override first
            resolved_code = overrides.get(token)
            is_ambiguous = False
            candidates = []
            note = ""

            if resolved_code:
                note = f"Manually resolved by chemist to {resolved_code}"
            else:
                resolved_code, is_ambiguous, candidates, note = self.resolve_ingredient_token(token)

            trade_name = ""
            chem_class = ""
            supplier = ""
            unit_price = None
            price_basis = "Unresolved"
            cost_contribution = Decimal("0.0000")

            if resolved_code and resolved_code in self.rm_master:
                rm_info = self.rm_master[resolved_code]
                trade_name = rm_info["trade_name"] or rm_info["name"]
                chem_class = rm_info["chemical_class"]
                supplier = rm_info["supplier"]
                
                # Retrieve price
                unit_price, price_basis, has_conflict, conflict_note = self.get_price_for_rm(resolved_code)
                if has_conflict:
                    note = f"{note} | {conflict_note}" if note else conflict_note
                
                if unit_price is not None:
                    # Decimal exact costing: (percentage / 100) * unit_price
                    cost_contribution = (pct / Decimal("100.0")) * unit_price

            lines.append(IngredientLine(
                raw_token=token,
                resolved_rm_code=resolved_code,
                trade_name=trade_name,
                chemical_class=chem_class,
                supplier=supplier,
                percentage=pct,
                unit_price_inr=unit_price,
                price_basis=price_basis,
                cost_contribution_inr=cost_contribution,
                is_ambiguous=is_ambiguous,
                ambiguity_candidates=candidates,
                notes=note if note else None,
            ))

        return lines

    def get_trial_evidence_dossier(self, trial_id: str) -> Dict[str, Any]:
        """
        Aggregates complete empirical evidence for a historical trial:
        - Recipe and measured specs
        - Linked stability incubator records (4w @ 45°C check)
        - Linked panel softness scores
        - Approval governance status
        - Identified workbook defects / contradictions
        """
        trial = self.trials.get(trial_id)
        if not trial:
            return {"error": f"Trial {trial_id} not found in workbook."}

        stability_logs = self.stability_records.get(trial_id, [])
        panel_logs = self.panel_records.get(trial_id, [])

        # Evaluate 4-week 45C stability evidence
        logs_45c = [l for l in stability_logs if l.get("temp_c") == 45]
        weeks_present = {l.get("week") for l in logs_45c}
        has_phase_sep = any(l.get("phase_sep") == "Y" or "separated" in l.get("appearance", "").lower() for l in logs_45c)
        has_yellowing = any("yellow" in l.get("appearance", "").lower() for l in logs_45c)
        has_full_4w = 4 in weeks_present

        stability_eval = "NOT_VERIFIED"
        stability_issues = []
        if has_phase_sep:
            stability_eval = "FAIL"
            stability_issues.append("Phase separation observed at 45°C")
        if has_yellowing:
            stability_eval = "FAIL"
            stability_issues.append("Yellowing observed during thermal stability")
        if not has_full_4w and stability_eval != "FAIL":
            stability_eval = "NOT_VERIFIED"
            stability_issues.append(f"Incomplete stability duration (weeks recorded: {sorted(list(weeks_present)) or 'None'})")
        elif has_full_4w and stability_eval != "FAIL":
            stability_eval = "PASS"

        # Check for contradiction with trial sheet summary status
        sheet_status = trial.get("stability_label", "")
        is_contradiction = (sheet_status.lower() == "pass" and stability_eval == "FAIL")

        # Evaluate panel softness score
        panel_score = trial.get("softness_score")
        if not panel_score and panel_logs:
            panel_score = panel_logs[-1]["softness_score"]

        # Approval check
        approved_by = trial.get("approved_by")
        is_approved = approved_by is not None and approved_by != ""

        return {
            "trial": trial,
            "stability_logs": stability_logs,
            "panel_logs": panel_logs,
            "stability_eval": stability_eval,
            "stability_issues": stability_issues,
            "is_stability_contradiction": is_contradiction,
            "panel_score": panel_score,
            "is_approved": is_approved,
            "approved_by": approved_by,
        }
