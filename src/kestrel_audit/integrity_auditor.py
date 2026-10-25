"""
Key Integrity and Identifier Auditor.
Detects duplicate primary keys, duplicate business identifiers, and orphan references.
"""

from typing import Any, Dict, List
import pandas as pd


class IntegrityAuditor:
    """Audits unique identifiers, duplicate records, and foreign key relationships."""

    def __init__(self, sheets: Dict[str, pd.DataFrame]):
        self.sheets = sheets

    def audit_all(self) -> Dict[str, Any]:
        """Runs all identifier and integrity audits."""
        return {
            "duplicate_primary_keys": self.audit_duplicate_primary_keys(),
            "duplicate_batch_codes": self.audit_duplicate_batch_codes(),
            "duplicate_price_feed_entries": self.audit_duplicate_price_feed(),
            "duplicate_customer_requests": self.audit_duplicate_customer_requests(),
            "cross_sheet_orphans": self.audit_cross_sheet_references(),
        }

    def audit_duplicate_primary_keys(self) -> Dict[str, List[Any]]:
        """Audits expected primary keys in major tables."""
        duplicates: Dict[str, List[Any]] = {}

        # 1. RM_Master (code)
        if "RM_Master" in self.sheets:
            df = self.sheets["RM_Master"]
            if "code" in df.columns:
                dups = df[df.duplicated(subset=["code"], keep=False)]["code"].tolist()
                if dups:
                    duplicates["RM_Master.code"] = dups

        # 2. Trials_TX_Softeners (trial_id)
        if "Trials_TX_Softeners" in self.sheets:
            df = self.sheets["Trials_TX_Softeners"]
            if "trial_id" in df.columns:
                dups = df[df.duplicated(subset=["trial_id"], keep=False)]["trial_id"].tolist()
                if dups:
                    duplicates["Trials_TX_Softeners.trial_id"] = dups

        # 3. Trials_All_Projects (lims_id)
        if "Trials_All_Projects" in self.sheets:
            df = self.sheets["Trials_All_Projects"]
            if "lims_id" in df.columns:
                dups = df[df.duplicated(subset=["lims_id"], keep=False)]["lims_id"].tolist()
                if dups:
                    duplicates["Trials_All_Projects.lims_id"] = dups

        # 4. Customer_Requests (request_id)
        if "Customer_Requests" in self.sheets:
            df = self.sheets["Customer_Requests"]
            if "request_id" in df.columns:
                dups = df[df.duplicated(subset=["request_id"], keep=False)]["request_id"].tolist()
                if dups:
                    duplicates["Customer_Requests.request_id"] = dups

        # 5. Lab_Schedule (booking_id)
        if "Lab_Schedule" in self.sheets:
            df = self.sheets["Lab_Schedule"]
            if "booking_id" in df.columns:
                dups = df[df.duplicated(subset=["booking_id"], keep=False)]["booking_id"].tolist()
                if dups:
                    duplicates["Lab_Schedule.booking_id"] = dups

        return duplicates

    def audit_duplicate_batch_codes(self) -> List[Dict[str, Any]]:
        """
        Audits batch_code uniqueness in Trials_TX_Softeners.
        A batch code should represent a unique chemical manufacture batch.
        """
        findings = []
        if "Trials_TX_Softeners" in self.sheets:
            df = self.sheets["Trials_TX_Softeners"]
            if "batch_code" in df.columns and "trial_id" in df.columns:
                dups = df[df.duplicated(subset=["batch_code"], keep=False)]
                for code, group in dups.groupby("batch_code"):
                    findings.append({
                        "batch_code": code,
                        "trial_ids": group["trial_id"].tolist(),
                        "chemists": group["chemist"].tolist() if "chemist" in group else [],
                        "equipment": group["equipment_id"].tolist() if "equipment_id" in group else [],
                        "dates": group["date"].astype(str).tolist() if "date" in group else [],
                    })
        return findings

    def audit_duplicate_price_feed(self) -> List[Dict[str, Any]]:
        """Audits Price_Feed for multiple price entries for the same (code, month)."""
        findings = []
        if "Price_Feed" in self.sheets:
            df = self.sheets["Price_Feed"]
            dups = df[df.duplicated(subset=["code", "month"], keep=False)]
            for (code, month), group in dups.groupby(["code", "month"]):
                entries = []
                for _, row in group.iterrows():
                    entries.append({
                        "price": row.get("price"),
                        "currency": row.get("currency"),
                        "source": row.get("source"),
                        "entry_type": row.get("entry_type"),
                    })
                findings.append({
                    "code": code,
                    "month": str(month),
                    "conflicting_entries": entries,
                })
        return findings

    def audit_duplicate_customer_requests(self) -> List[Dict[str, Any]]:
        """Audits Customer_Requests for duplicate request_id records with conflicting metadata."""
        findings = []
        if "Customer_Requests" in self.sheets:
            df = self.sheets["Customer_Requests"]
            dups = df[df.duplicated(subset=["request_id"], keep=False)]
            for req_id, group in dups.groupby("request_id"):
                records = []
                for _, row in group.iterrows():
                    records.append({
                        "date": str(row.get("date")),
                        "customer": row.get("customer"),
                        "bu": row.get("bu"),
                        "need": row.get("need"),
                        "status": row.get("status"),
                        "owner": row.get("owner"),
                    })
                findings.append({
                    "request_id": req_id,
                    "records": records,
                })
        return findings

    def audit_cross_sheet_references(self) -> Dict[str, Any]:
        """Audits foreign keys between trials, stability logs, and panel scores."""
        orphans = {}
        if "Trials_TX_Softeners" in self.sheets and "Stability_Log" in self.sheets:
            tx_trials = set(self.sheets["Trials_TX_Softeners"]["trial_id"].dropna())
            stab_samples = set(self.sheets["Stability_Log"]["sample_id"].dropna())
            # Samples with T- prefix that are not in Trials_TX_Softeners
            t_orphans = [s for s in stab_samples if s.startswith("T-") and s not in tx_trials]
            if t_orphans:
                orphans["Stability_Log_unmatched_T_samples"] = t_orphans

        if "Trials_TX_Softeners" in self.sheets and "Panel_Scores" in self.sheets:
            tx_trials = set(self.sheets["Trials_TX_Softeners"]["trial_id"].dropna())
            panel_trials = set(self.sheets["Panel_Scores"]["trial_id"].dropna())
            t_orphans = [s for s in panel_trials if s not in tx_trials]
            if t_orphans:
                orphans["Panel_Scores_unmatched_trials"] = t_orphans

        return orphans
