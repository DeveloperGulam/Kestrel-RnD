"""
Formulation and Stoichiometry Auditor.
Parses chemical recipes, checks percentage totals, flags unmapped ingredient tokens
(e.g., distinguishing 'TEA-esterquat' token from trial ID 'T-04'), and detects synonym clashes.
"""

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd


class FormulationAuditor:
    """Audits chemical recipes in Trials_TX_Softeners and Trials_All_Projects."""

    def __init__(self, sheets: Dict[str, pd.DataFrame]):
        self.sheets = sheets
        self.master_rm_codes: set[str] = set()
        self.master_rm_synonyms: Dict[str, List[str]] = {}
        self._build_master_catalog()

    def _build_master_catalog(self) -> None:
        """Indexes known RM codes and synonyms from RM_Master."""
        if "RM_Master" not in self.sheets:
            return
        df = self.sheets["RM_Master"]
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            if not code or code == "nan":
                continue
            self.master_rm_codes.add(code)
            synonyms_str = str(row.get("synonyms", ""))
            syn_list = [
                s.strip()
                for s in synonyms_str.split(";")
                if s.strip() and s.strip() != "nan"
            ]
            for syn in syn_list:
                # Store exact lower
                self.master_rm_synonyms.setdefault(syn.lower(), []).append(code)
                # Also store normalized (hyphen replaced with space)
                norm_syn = syn.lower().replace("-", " ").strip()
                if norm_syn != syn.lower():
                    self.master_rm_synonyms.setdefault(norm_syn, []).append(code)
            # Also register normalized RM-101/RM-102 names
            name_str = str(row.get("name", "")).lower().replace("-", " ").strip()
            self.master_rm_synonyms.setdefault(name_str, []).append(code)

    def parse_recipe_string(self, recipe_str: str) -> Tuple[List[Dict[str, Any]], float, List[str]]:
        """
        Parses a recipe string formatted as 'code:pct; code:pct; ...'.
        Returns:
            - parsed items: list of dicts with ingredient, pct, is_valid_code, matching_codes
            - total_pct: sum of all percentages
            - parse_errors: any syntax or extraction issues
        """
        items: List[Dict[str, Any]] = []
        total_pct = 0.0
        errors: List[str] = []

        if not recipe_str or pd.isna(recipe_str) or str(recipe_str).strip() == "nan":
            return items, 0.0, ["Empty or missing recipe string"]

        parts = [p.strip() for p in str(recipe_str).split(";") if p.strip()]
        for part in parts:
            if ":" not in part:
                errors.append(f"Invalid format (missing ':'): '{part}'")
                continue
            token, pct_str = part.split(":", 1)
            token = token.strip()
            pct_str = pct_str.strip()
            try:
                pct = float(pct_str)
                total_pct += pct
            except ValueError:
                errors.append(f"Invalid percentage value in '{part}'")
                pct = None

            is_registered_code = token in self.master_rm_codes
            exact_matches = self.master_rm_synonyms.get(token.lower(), [])
            norm_matches = self.master_rm_synonyms.get(token.lower().replace("-", " "), [])
            # Deduplicate preserving order
            synonym_matches = list(dict.fromkeys(exact_matches + norm_matches))

            items.append({
                "raw_token": token,
                "percentage": pct,
                "is_registered_code": is_registered_code,
                "synonym_matches": synonym_matches,
                "is_ambiguous_synonym": len(synonym_matches) > 1,
            })

        return items, round(total_pct, 4), errors

    def audit_tx_softeners(self) -> List[Dict[str, Any]]:
        """
        Audits all recipes in Trials_TX_Softeners.
        Verifies 100% total, flags unmapped tokens (like 'TEA-esterquat'),
        and identifies silicone or sensitizer additions.
        """
        findings: List[Dict[str, Any]] = []
        if "Trials_TX_Softeners" not in self.sheets:
            return findings

        df = self.sheets["Trials_TX_Softeners"]
        for _, row in df.iterrows():
            trial_id = str(row.get("trial_id", ""))
            recipe_str = row.get("formulation_pct", "")
            items, total_pct, errors = self.parse_recipe_string(recipe_str)

            # Check stoichiometry sum
            is_stoichiometry_valid = abs(total_pct - 100.0) <= 0.05

            # Unmapped tokens
            unmapped_tokens = [
                it["raw_token"] for it in items if not it["is_registered_code"]
            ]

            # Ambiguous tokens (e.g., TEA-esterquat mapping to RM-101 and RM-102)
            ambiguous_tokens = [
                {
                    "token": it["raw_token"],
                    "candidate_codes": it["synonym_matches"],
                }
                for it in items
                if it["is_ambiguous_synonym"]
            ]

            # Check for ingredients violating brief constraints (e.g. silicone RM-140)
            used_codes = [it["raw_token"] for it in items if it["is_registered_code"]]
            contains_silicone = "RM-140" in used_codes
            isopropanol_item = next((it for it in items if it["raw_token"] == "RM-131"), None)
            flammable_alcohol_excess = (
                isopropanol_item is not None
                and isopropanol_item["percentage"] is not None
                and isopropanol_item["percentage"] > 1.0
            )

            findings.append({
                "trial_id": trial_id,
                "total_percentage": total_pct,
                "is_stoichiometry_valid": is_stoichiometry_valid,
                "unmapped_tokens": unmapped_tokens,
                "ambiguous_tokens": ambiguous_tokens,
                "contains_silicone": contains_silicone,
                "flammable_alcohol_excess": flammable_alcohol_excess,
                "parse_errors": errors,
                "raw_recipe": recipe_str,
            })

        return findings
