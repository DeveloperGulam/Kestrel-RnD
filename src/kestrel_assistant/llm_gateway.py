"""
LLM Gateway & Request Intake Parser for Kestrel R&D Formulation Assistant.
Provides natural-language request extraction and hypothesis drafting.
Enforces strict boundaries: LLMs are non-authoritative; all outputs are validated
against Pydantic schemas and deterministic calculation barriers.
"""

from decimal import Decimal
import os
import re
from typing import Any, Dict, List, Optional

from .models import FormulationRequest


class LLMGateway:
    """Gateway for AI-assisted linguistic parsing and drafting."""

    def __init__(self):
        # Inspect environment for LLM credentials
        self.api_key = (
            os.getenv("GEMINI_API_KEY") or
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_API_KEY")
        )
        self.is_connected = bool(self.api_key)
        self.provider = "Unconfigured"
        if os.getenv("GEMINI_API_KEY"):
            self.provider = "Google Gemini"
        elif os.getenv("OPENAI_API_KEY"):
            self.provider = "OpenAI"
        elif os.getenv("ANTHROPIC_API_KEY"):
            self.provider = "Anthropic"

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns the operational status of the generative LLM gateway."""
        if self.is_connected:
            return {
                "active": True,
                "provider": self.provider,
                "status_text": f"Connected to {self.provider}. Generative hypothesis drafting active.",
                "is_authoritative": False,  # Never authoritative
            }
        return {
            "active": False,
            "provider": None,
            "status_text": "AI generative drafting disabled (no API key configured). Deterministic rules, evidence search, and formulation validation remain 100% operational.",
            "is_authoritative": False,
        }

    def parse_natural_language_brief(self, brief_text: str) -> FormulationRequest:
        """
        Parses unstructured natural language customer briefs into a structured FormulationRequest.
        Uses deterministic heuristic extraction (offline-capable, zero API required).
        """
        req = FormulationRequest()
        text = brief_text.lower()

        # Substrate detection
        if "cotton" in text or "towel" in text or "knit" in text:
            req.target_substrate = "100% Cotton Knits / Terry Towels"
        elif "polyester" in text or "poly" in text:
            req.target_substrate = "100% Polyester / Synthetic Blend"

        # Solids % detection (e.g., "solids 6-8%", "6 to 8 percent solids")
        solids_match = re.search(r"solids?\s*(?:of|at|:)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)%?", text)
        if solids_match:
            try:
                min_s = Decimal(solids_match.group(1))
                max_s = Decimal(solids_match.group(2))
                req.solids_pct_range = (min_s, max_s)
            except Exception:
                pass

        # pH range detection (e.g., "pH 3.5-4.5", "ph 3.5 to 4.5")
        ph_match = re.search(r"ph\s*(?:of|at|:)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", text)
        if ph_match:
            try:
                min_ph = Decimal(ph_match.group(1))
                max_ph = Decimal(ph_match.group(2))
                req.ph_range = (min_ph, max_ph)
            except Exception:
                pass

        # Viscosity range detection (e.g., "viscosity 50-300 cP", "50 to 300 cp")
        visc_match = re.search(r"viscosity\s*(?:of|at|:)?\s*(\d+)\s*(?:-|to)\s*(\d+)\s*(?:cp)?", text)
        if visc_match:
            try:
                min_v = Decimal(visc_match.group(1))
                max_v = Decimal(visc_match.group(2))
                req.viscosity_cp_range = (min_v, max_v)
            except Exception:
                pass

        # Cost ceiling detection (e.g., "max cost ₹22/kg", "cost <= 22", "below 22")
        cost_match = re.search(r"(?:cost|price)\s*(?:of|below|under|at|<=|≤|max)?\s*(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)", text)
        if cost_match:
            try:
                max_c = Decimal(cost_match.group(1))
                req.max_cost_inr_per_kg = max_c
            except Exception:
                pass

        # Prohibited ingredients
        if "silicone-free" in text or "no silicone" in text or "silicone free" in text:
            if "silicone" not in req.prohibited_ingredients:
                req.prohibited_ingredients.append("silicone")
            if "RM-140" not in req.prohibited_ingredients:
                req.prohibited_ingredients.append("RM-140")

        # Softness score
        soft_match = re.search(r"softness\s*(?:score|panel)?\s*(?:of|at|>=|≥|at least)?\s*(\d+(?:\.\d+)?)\s*/?\s*5?", text)
        if soft_match:
            try:
                score = Decimal(soft_match.group(1))
                if score <= Decimal("5.0"):
                    req.min_softness_panel_score = score
            except Exception:
                pass

        return req
