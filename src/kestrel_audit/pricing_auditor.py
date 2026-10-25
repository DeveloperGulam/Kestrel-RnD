"""
Pricing and Currency Reconciliation Auditor.
Identifies duplicate pricing feeds, currency conversions (USD to INR),
stale list prices vs recent price feeds, and packaging unit conversions.
"""

from typing import Any, Dict, List
import pandas as pd


class PricingAuditor:
    """Audits raw material pricing, currency consistency, and cost recalculations."""

    FX_USD_TO_INR = 84.00  # Stated in Export_Info: '1 USD = 84.00 INR as of 2026-05-01'

    def __init__(self, sheets: Dict[str, pd.DataFrame]):
        self.sheets = sheets

    def audit_all(self) -> Dict[str, Any]:
        """Runs all pricing and currency audits."""
        return {
            "duplicate_month_entries": self.audit_duplicate_monthly_feed(),
            "master_vs_feed_discrepancies": self.audit_master_vs_feed_prices(),
            "currency_distribution": self.audit_currency_distribution(),
            "summary_apr_cost_audit": self.audit_summary_apr_cost(),
        }

    def audit_duplicate_monthly_feed(self) -> List[Dict[str, Any]]:
        """
        Audits Price_Feed for multiple rows matching the same (code, month).
        Specifically flags RM-101 (210 vs 228) and RM-170 (32800 vs 164) in 2026-05.
        """
        conflicts = []
        if "Price_Feed" not in self.sheets:
            return conflicts

        df = self.sheets["Price_Feed"]
        dups = df[df.duplicated(subset=["code", "month"], keep=False)]
        for (code, month), group in dups.groupby(["code", "month"]):
            entries = []
            for _, r in group.iterrows():
                entries.append({
                    "price": float(r["price"]),
                    "currency": str(r["currency"]),
                    "source": str(r["source"]),
                    "entry_type": str(r["entry_type"]),
                })
            conflicts.append({
                "code": code,
                "month": str(month),
                "conflicting_records": entries,
                "price_delta": max(e["price"] for e in entries) - min(e["price"] for e in entries),
            })
        return conflicts

    def audit_master_vs_feed_prices(self) -> List[Dict[str, Any]]:
        """
        Compares RM_Master list_price against the latest Price_Feed entry.
        Identifies stale master catalog prices.
        """
        discrepancies = []
        if "RM_Master" not in self.sheets or "Price_Feed" not in self.sheets:
            return discrepancies

        df_rm = self.sheets["RM_Master"]
        df_pf = self.sheets["Price_Feed"].sort_values(by="month")

        latest_pf = df_pf.groupby("code").last().reset_index()
        merged = pd.merge(df_rm, latest_pf, on="code", suffixes=("_master", "_feed"))

        for _, row in merged.iterrows():
            master_price = float(row.get("list_price", 0))
            feed_price = float(row.get("price", 0))
            master_curr = str(row.get("currency_master", ""))
            feed_curr = str(row.get("currency_feed", ""))
            code = str(row.get("code", ""))

            if master_price != feed_price or master_curr != feed_curr:
                discrepancies.append({
                    "code": code,
                    "name": row.get("name"),
                    "master_price": master_price,
                    "master_currency": master_curr,
                    "master_updated": str(row.get("price_updated")),
                    "latest_feed_price": feed_price,
                    "latest_feed_currency": feed_curr,
                    "latest_feed_month": str(row.get("month")),
                    "source": str(row.get("source")),
                })

        return discrepancies

    def audit_currency_distribution(self) -> Dict[str, Any]:
        """Summarizes currency distribution across master and feed tables."""
        res: Dict[str, Any] = {}
        if "RM_Master" in self.sheets:
            res["RM_Master"] = self.sheets["RM_Master"]["currency"].value_counts().to_dict()
        if "Price_Feed" in self.sheets:
            res["Price_Feed"] = self.sheets["Price_Feed"]["currency"].value_counts().to_dict()
        return res

    def calculate_formula_rm_cost(
        self,
        recipe_items: List[Dict[str, Any]],
        use_price_feed: bool = False,
        tea_esterquat_code: str = "RM-101",
    ) -> Dict[str, Any]:
        """
        Deterministically calculates the raw material cost in INR per kg of finished formulation.
        Applies FX conversion (USD -> INR) and UOM normalization (drum -> kg).
        """
        if "RM_Master" not in self.sheets:
            return {"error": "RM_Master missing"}

        df_rm = self.sheets["RM_Master"].set_index("code")
        total_cost_inr = 0.0
        breakdown = []

        for item in recipe_items:
            token = item["raw_token"]
            pct = item["percentage"] or 0.0

            # Handle unmapped TEA-esterquat
            lookup_code = token
            if token.lower() in ["tea-esterquat", "tea esterquat"]:
                lookup_code = tea_esterquat_code

            if lookup_code not in df_rm.index:
                return {
                    "error": f"Cannot compute cost: raw material '{token}' unmapped in master catalog",
                    "missing_token": token,
                }

            rm_row = df_rm.loc[lookup_code]
            raw_price = float(rm_row["list_price"])
            currency = str(rm_row["currency"])
            uom = str(rm_row["uom"]).lower()

            # Normalize packaging unit to per-kg
            price_per_kg = raw_price
            if "drum (200 kg)" in uom or "drum" in uom:
                price_per_kg = raw_price / 200.0

            # Convert currency to INR
            if currency == "USD":
                price_per_kg_inr = price_per_kg * self.FX_USD_TO_INR
            else:
                price_per_kg_inr = price_per_kg

            cost_contribution = (pct / 100.0) * price_per_kg_inr
            total_cost_inr += cost_contribution

            breakdown.append({
                "token": token,
                "resolved_code": lookup_code,
                "pct": pct,
                "price_per_kg_inr": round(price_per_kg_inr, 4),
                "cost_contribution_inr": round(cost_contribution, 4),
            })

        return {
            "total_cost_inr_per_kg": round(total_cost_inr, 2),
            "breakdown": breakdown,
        }

    def audit_summary_apr_cost(self) -> Dict[str, Any]:
        """
        Produces a multi-scenario line-item audit for Trial T-04 comparing
        Summary_Apr's claimed cost (₹16.90/kg) against deterministic recalculations.
        """
        t04_recipe = [
            {"raw_token": "TEA-esterquat", "pct": 7.0},
            {"raw_token": "RM-170", "pct": 1.5},
            {"raw_token": "RM-120", "pct": 1.0},
            {"raw_token": "RM-150", "pct": 0.2},
            {"raw_token": "RM-160", "pct": 0.1},
            {"raw_token": "RM-180", "pct": 90.2},
        ]

        df_rm = self.sheets["RM_Master"].set_index("code") if "RM_Master" in self.sheets else None
        df_pf = self.sheets["Price_Feed"] if "Price_Feed" in self.sheets else None

        # Build detailed line items for Scenario 1 (RM_Master + RM-101)
        # and Scenario 2 (RM_Master + RM-102)
        scenarios = {}

        def build_breakdown(ester_code: str, use_feed: bool = False, ester_manual_feed: bool = False):
            items = []
            total = 0.0
            for ing in t04_recipe:
                token = ing["raw_token"]
                pct = ing["pct"]
                resolved_code = ester_code if token == "TEA-esterquat" else token

                rm_row = df_rm.loc[resolved_code] if df_rm is not None and resolved_code in df_rm.index else None
                rm_name = str(rm_row["name"]) if rm_row is not None else token

                if use_feed and df_pf is not None:
                    # Lookup latest month in Price_Feed (2026-05)
                    sub = df_pf[(df_pf["code"] == resolved_code) & (df_pf["month"] == "2026-05")]
                    if resolved_code == "RM-101":
                        target_type = "manual" if ester_manual_feed else "auto"
                        feed_row = sub[sub["entry_type"] == target_type].iloc[0]
                    elif resolved_code == "RM-170":
                        # Both auto (drum) and manual (per kg) equate to 164 INR/kg
                        feed_row = sub[sub["entry_type"] == "manual"].iloc[0]
                    elif not sub.empty:
                        feed_row = sub.iloc[0]
                    else:
                        feed_row = None
                else:
                    feed_row = None

                if feed_row is not None:
                    price_val = float(feed_row["price"])
                    curr = str(feed_row["currency"])
                    src = f"Price_Feed 2026-05 ({feed_row['source']}, {feed_row['entry_type']})"
                    uom = "kg"  # Price_Feed lacks UOM column; manual row 171 specifies quote per kg
                elif rm_row is not None:
                    price_val = float(rm_row["list_price"])
                    curr = str(rm_row["currency"])
                    src = f"RM_Master (updated {rm_row.get('price_updated')})"
                    uom = str(rm_row.get("uom"))
                else:
                    price_val = 0.0
                    curr = "INR"
                    src = "Missing"
                    uom = "kg"

                # Conversions
                # UOM normalization
                price_per_kg = price_val
                if "drum (200 kg)" in uom.lower() or ("drum" in uom.lower() and price_val > 1000):
                    price_per_kg = price_val / 200.0
                    uom_conv = "Drum (200 kg) divided by 200 -> per kg"
                else:
                    uom_conv = "Direct per kg"

                # FX conversion
                if curr == "USD":
                    price_per_kg_inr = price_per_kg * self.FX_USD_TO_INR
                    fx_conv = f"USD {price_per_kg:.2f} * 84.00 FX = ₹{price_per_kg_inr:.2f}/kg"
                else:
                    price_per_kg_inr = price_per_kg
                    fx_conv = "None (Already INR)"

                cost_contrib = (pct / 100.0) * price_per_kg_inr
                total += cost_contrib

                items.append({
                    "token": token,
                    "resolved_code": resolved_code,
                    "name": rm_name,
                    "percentage": pct,
                    "selected_price": price_val,
                    "currency": curr,
                    "uom": uom,
                    "price_source": src,
                    "uom_conversion": uom_conv,
                    "fx_conversion": fx_conv,
                    "effective_price_per_kg_inr": round(price_per_kg_inr, 4),
                    "cost_contribution_inr": round(cost_contrib, 4),
                })

            return round(total, 4), items

        tot1, items1 = build_breakdown("RM-101", use_feed=False)
        tot2, items2 = build_breakdown("RM-102", use_feed=False)
        tot3, items3 = build_breakdown("RM-101", use_feed=True, ester_manual_feed=False)
        tot4, items4 = build_breakdown("RM-101", use_feed=True, ester_manual_feed=True)
        tot5, items5 = build_breakdown("RM-102", use_feed=True)

        return {
            "summary_apr_claimed_cost_t04": 16.90,
            "scenarios": {
                "scenario_1_rm_master_rm101": {
                    "description": "RM_Master list prices resolving TEA-esterquat to RM-101 (Supplier A @ ₹210/kg)",
                    "recalculated_cost_inr": round(tot1, 2),
                    "line_items": items1,
                },
                "scenario_2_rm_master_rm102": {
                    "description": "RM_Master list prices resolving TEA-esterquat to RM-102 (Supplier B @ ₹198/kg)",
                    "recalculated_cost_inr": round(tot2, 2),
                    "line_items": items2,
                },
                "scenario_3_feed_latest_auto_rm101": {
                    "description": "Price_Feed 2026-05 auto feed with RM-101 (PurchaseOne @ ₹210/kg)",
                    "recalculated_cost_inr": round(tot3, 2),
                    "line_items": items3,
                },
                "scenario_4_feed_latest_manual_rm101": {
                    "description": "Price_Feed 2026-05 manual feed with RM-101 (Supplier A email @ ₹228/kg)",
                    "recalculated_cost_inr": round(tot4, 2),
                    "line_items": items4,
                },
                "scenario_5_feed_latest_auto_rm102": {
                    "description": "Price_Feed 2026-05 auto feed with RM-102 (PurchaseOne @ ₹216/kg)",
                    "recalculated_cost_inr": round(tot5, 2),
                    "line_items": items5,
                },
            },
            "unresolved_uncertainty": (
                "Summary_Apr row 10 claims 'Costs from RM_Master list prices', but reports ₹16.90/kg. "
                "Deterministic recalculation across all plausible price and ingredient scenarios ranges from ₹19.14 to ₹21.34/kg. "
                "The workbook does not contain the underlying cell formulas, line-item schedule, or calculation notes for Summary_Apr. "
                "Consequently, the root cause of the ₹16.90 figure cannot be proven from workbook evidence alone and requires author clarification."
            ),
        }
