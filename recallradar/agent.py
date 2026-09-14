"""Strands orchestration for RecallRadar."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from strands import Agent, tool

from .core import Match, build_action_packet, scan
from .sources import demo_recalls, fetch_cpsc_recalls, load_inventory


_STATE: dict = {"inventory_path": "data/demo_inventory.csv", "source": "demo", "matches": []}


@tool
def load_household_inventory() -> str:
    """Load and validate the user's receipt-derived product inventory."""
    products = load_inventory(_STATE["inventory_path"])
    _STATE["products"] = products
    incomplete = [
        item.product_id for item in products if not item.model and not item.lot
    ]
    return json.dumps({
        "loaded_products": len(products),
        "records_missing_model_and_lot": incomplete,
        "privacy_note": "Inventory remains local to this agent run.",
    })


@tool
def retrieve_official_recall_notices() -> str:
    """Retrieve recall notices from the selected demo or live CPSC source."""
    if _STATE["source"] == "live":
        products = _STATE.get("products") or load_inventory(_STATE["inventory_path"])
        recalls = fetch_cpsc_recalls(products)
        source = "U.S. CPSC public recall feed"
    else:
        recalls = demo_recalls()
        source = "synthetic hackathon demonstration feed"
    _STATE["recalls"] = recalls
    return json.dumps({"source": source, "notices_loaded": len(recalls)})


@tool
def verify_exact_recall_matches() -> str:
    """Match inventory against recalls conservatively and suppress weak candidates."""
    products = _STATE.get("products") or load_inventory(_STATE["inventory_path"])
    if "recalls" in _STATE:
        recalls = _STATE["recalls"]
    elif _STATE.get("source") == "live":
        recalls = fetch_cpsc_recalls(products)
    else:
        recalls = demo_recalls()
    matches = scan(products, recalls)
    _STATE["matches"] = matches
    return json.dumps({
        "confirmed_candidates": len(matches),
        "matches": [
            {
                "match_id": item.match_id,
                "product": item.product.name,
                "risk": item.risk,
                "confidence": item.confidence,
                "evidence": list(item.reasons),
            }
            for item in matches
        ],
    })


@tool
def prepare_recall_action(match_id: str) -> str:
    """Prepare, but never submit, the safety and remedy action for a match."""
    match = next(
        (item for item in _STATE.get("matches", []) if item.match_id == match_id),
        None,
    )
    if not match:
        return json.dumps({"error": "Unknown match. Verify matches first."})
    return json.dumps(build_action_packet(match))


def deterministic_scan(inventory_path: str, source: str = "demo") -> tuple[list[Match], list]:
    products = load_inventory(inventory_path)
    recalls = fetch_cpsc_recalls(products) if source == "live" else demo_recalls()
    return scan(products, recalls), products


def run_strands_scan(inventory_path: str, source: str = "demo", provider: str = "gemini") -> str:
    """Run the end-to-end workflow through a real Strands agent."""
    _STATE.clear()
    _STATE.update({"inventory_path": inventory_path, "source": source, "matches": []})
    provider = provider.lower()
    kwargs = {
        "system_prompt": (
            "You are RecallRadar, a cautious product-safety agent. Complete the scan "
            "end to end by calling the inventory, recall, and verification tools in "
            "order. Prepare an action for each confirmed candidate. Never claim that "
            "a candidate is legally confirmed, never submit an external action, and "
            "always state that human approval and official-source verification are required."
        ),
        "tools": [
            load_household_inventory,
            retrieve_official_recall_notices,
            verify_exact_recall_matches,
            prepare_recall_action,
        ],
    }
    if provider == "gemini":
        from strands.models.gemini import GeminiModel
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing. Add it only to your terminal or hosting secrets.")
        kwargs["model"] = GeminiModel(
            client_args={"api_key": api_key},
            model_id=os.getenv("RECALLRADAR_GEMINI_MODEL", "gemini-3.5-flash-lite"),
            params={"temperature": 0.1, "max_output_tokens": 2048},
        )
    elif provider == "bedrock":
        from strands.models import BedrockModel
        kwargs["model"] = BedrockModel(
            model_id=os.getenv("RECALLRADAR_MODEL_ID", "us.amazon.nova-lite-v1:0")
        )
    else:
        raise ValueError("Provider must be 'gemini' or 'bedrock'.")

    agent = Agent(**kwargs)
    result = agent(
        "Run the household recall scan now. Report only confirmed candidates, "
        "the evidence, immediate safety step, and the decision requiring approval."
    )
    return str(result)
