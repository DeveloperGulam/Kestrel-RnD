"""
Unit and Date Consistency Auditor.
Detects unit of measure variations (viscosity cP vs Pa·s, softness scales, drum vs kg)
and date anomalies (inconsistent date parsing, ambiguous formats, chronological impossibilities).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd


class UnitAndDateAuditor:
    """Audits units of measure, scale normalizations, and date formatting/chronology."""

    EXPORT_TIMESTAMP = "2026-05-20"  # From Export_Info row 2: 'Generated 2026-05-20 08:14'

    def __init__(self, sheets: Dict[str, pd.DataFrame]):
        self.sheets = sheets

    def audit_all(self) -> Dict[str, Any]:
        """Runs all unit and date audits."""
        return {
            "viscosity_units": self.audit_viscosity_units(),
            "softness_scales": self.audit_softness_scales(),
            "uom_packaging_mismatch": self.audit_uom_packaging(),
            "date_formats_tx_softeners": self.audit_dates_tx_softeners(),
            "date_formats_trials_all": self.audit_dates_trials_all(),
            "chronological_anomalies": self.audit_chronological_anomalies(),
        }

    def audit_viscosity_units(self) -> List[Dict[str, Any]]:
        """
        Audits viscosity values in Trials_TX_Softeners.
        Flags non-standard units (e.g. '0.45 Pa·s' vs 'cP') and converts them to standard cP (mPa·s).
        """
        findings = []
        if "Trials_TX_Softeners" not in self.sheets:
            return findings

        df = self.sheets["Trials_TX_Softeners"]
        for _, row in df.iterrows():
            trial_id = str(row.get("trial_id", ""))
            raw_visc = str(row.get("viscosity", "")).strip()

            # Parse unit and value
            match_cp = re.match(r"^([\d.]+)\s*(cP|cp|mPa\.s|mPa·s)?$", raw_visc, re.IGNORECASE)
            match_pas = re.match(r"^([\d.]+)\s*(Pa\.s|Pa·s|Pas)$", raw_visc, re.IGNORECASE)

            normalized_cp = None
            unit_type = "unknown"

            if match_pas:
                val = float(match_pas.group(1))
                normalized_cp = val * 1000.0  # 1 Pa·s = 1000 cP
                unit_type = "Pa·s"
            elif match_cp:
                normalized_cp = float(match_cp.group(1))
                unit_type = "cP"
            else:
                unit_type = "unparsed"

            # Customer target brief: 50–300 cP
            exceeds_target_range = (
                normalized_cp is not None and (normalized_cp < 50 or normalized_cp > 300)
            )

            findings.append({
                "trial_id": trial_id,
                "raw_value": raw_visc,
                "unit_detected": unit_type,
                "normalized_cP": normalized_cp,
                "is_non_standard_unit": unit_type == "Pa·s",
                "exceeds_customer_target": exceeds_target_range,
            })

        return findings

    def audit_softness_scales(self) -> Dict[str, Any]:
        """
        Audits softness scale representations in Trials_TX_Softeners and Panel_Scores.
        Flags discrepancies between 1-5 scale and 1-10 scale.
        """
        findings = {
            "tx_softeners_scales": [],
            "panel_scores_scales": [],
        }

        if "Trials_TX_Softeners" in self.sheets:
            df = self.sheets["Trials_TX_Softeners"]
            for _, row in df.iterrows():
                tid = str(row.get("trial_id", ""))
                val = str(row.get("softness", "")).strip()
                scale_denom = None
                if "/" in val:
                    num, denom = val.split("/", 1)
                    scale_denom = denom.strip()
                findings["tx_softeners_scales"].append({
                    "trial_id": tid,
                    "raw_value": val,
                    "scale_denominator": scale_denom,
                    "is_non_standard_scale": scale_denom != "5",
                })

        if "Panel_Scores" in self.sheets:
            df = self.sheets["Panel_Scores"]
            scale_counts = df["scale"].value_counts().to_dict()
            trials_on_10_scale = df[df["scale"] == "1-10"]["trial_id"].unique().tolist()
            findings["panel_scores_scales"] = {
                "scale_distribution": scale_counts,
                "trials_on_10_scale": trials_on_10_scale,
            }

        return findings

    def audit_uom_packaging(self) -> List[Dict[str, Any]]:
        """
        Audits Unit of Measure in RM_Master and Price_Feed.
        Flags packaging units like 'drum (200 kg)' where naive pricing causes a 200x error.
        """
        findings = []
        if "RM_Master" in self.sheets:
            df = self.sheets["RM_Master"]
            for _, row in df.iterrows():
                uom = str(row.get("uom", "")).strip()
                code = str(row.get("code", "")).strip()
                if uom != "kg":
                    findings.append({
                        "sheet": "RM_Master",
                        "code": code,
                        "name": row.get("name"),
                        "uom": uom,
                        "list_price": row.get("list_price"),
                        "currency": row.get("currency"),
                        "risk": "Unit is not standard per-kg; requires dimensional conversion.",
                    })
        return findings

    def audit_dates_tx_softeners(self) -> List[Dict[str, Any]]:
        """Audits date formatting styles in Trials_TX_Softeners."""
        findings = []
        if "Trials_TX_Softeners" in self.sheets:
            df = self.sheets["Trials_TX_Softeners"]
            for _, row in df.iterrows():
                tid = str(row.get("trial_id", ""))
                date_val = str(row.get("date", "")).strip()
                fmt_type = "unknown"
                if re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                    fmt_type = "ISO (YYYY-MM-DD)"
                elif re.match(r"^\d{2}/\d{2}/\d{4}$", date_val):
                    fmt_type = "Slash (DD/MM/YYYY or MM/DD/YYYY)"
                elif re.match(r"^\d{1,2}-[A-Za-z]{3}-\d{2,4}$", date_val):
                    fmt_type = "Alphanumeric (DD-Mon-YY)"

                findings.append({
                    "trial_id": tid,
                    "date_string": date_val,
                    "format_type": fmt_type,
                    "is_ambiguous_or_non_iso": fmt_type != "ISO (YYYY-MM-DD)",
                })
        return findings

    def audit_dates_trials_all(self) -> Dict[str, Any]:
        """Audits mixed date styles in Trials_All_Projects."""
        if "Trials_All_Projects" not in self.sheets:
            return {}
        df = self.sheets["Trials_All_Projects"]
        created = df["created"].astype(str)
        slash_count = int(created.str.contains("/").sum())
        hyphen_count = int(created.str.contains("-").sum())
        return {
            "total_records": len(df),
            "slash_formatted_dates": slash_count,
            "hyphen_formatted_dates": hyphen_count,
            "risk": "Mixed DD/MM/YYYY and YYYY-MM-DD prevents native lexical sort or date arithmetic.",
        }

    def audit_chronological_anomalies(self) -> List[Dict[str, Any]]:
        """
        Audits chronological impossibilities against the export generation date (2026-05-20):
        1. Trial T-12 (created 2026-05-13) has 4-week stability measurements logged before export.
        2. Lab_Schedule has future dates (e.g. 2026-05-21, 2026-05-27) already marked as 'Completed'.
        """
        anomalies = []

        # Check Stability_Log for T-12
        if "Stability_Log" in self.sheets and "Trials_TX_Softeners" in self.sheets:
            df_stab = self.sheets["Stability_Log"]
            t12_stab = df_stab[df_stab["sample_id"] == "T-12"]
            weeks_logged = t12_stab["week"].unique().tolist()
            if 4 in weeks_logged or "4" in weeks_logged:
                anomalies.append({
                    "entity": "Stability_Log",
                    "sample_id": "T-12",
                    "trial_date": "2026-05-13",
                    "export_date": self.EXPORT_TIMESTAMP,
                    "weeks_logged": weeks_logged,
                    "anomaly": (
                        "Trial T-12 was formulated on 2026-05-13 (7 days before export), "
                        "yet Stability_Log contains Week 2, Week 3, and Week 4 measurements. "
                        "Apparent chronology/status inconsistency requiring protocol and LIMS verification."
                    ),
                    "classification": "Apparent chronology/status inconsistency requiring verification",
                })

        # Check Lab_Schedule future 'Completed' bookings
        if "Lab_Schedule" in self.sheets:
            df_ls = self.sheets["Lab_Schedule"]
            future_completed = df_ls[
                (df_ls["date"].astype(str) > self.EXPORT_TIMESTAMP)
                & (df_ls["status"] == "Completed")
            ]
            for _, row in future_completed.iterrows():
                anomalies.append({
                    "entity": "Lab_Schedule",
                    "booking_id": row.get("booking_id"),
                    "date": str(row.get("date")),
                    "export_date": self.EXPORT_TIMESTAMP,
                    "equipment_id": row.get("equipment_id"),
                    "status": row.get("status"),
                    "anomaly": f"Booking scheduled for date {row.get('date')} after export {self.EXPORT_TIMESTAMP} is marked as 'Completed'. Apparent chronology/status inconsistency requiring verification.",
                    "classification": "Apparent chronology/status inconsistency requiring verification",
                })

        return anomalies
