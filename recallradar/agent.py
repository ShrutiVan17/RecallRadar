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
        recalls = fetch_cpsc_recalls()
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
    recalls = _STATE.get("recalls") or demo_recalls()
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
    recalls = fetch_cpsc_recalls() if source == "live" else demo_recalls()
    return scan(products, recalls), products


def run_strands_scan(inventory_path: str, source: str = "demo") -> str:
    """Run the end-to-end workflow through a real Strands agent."""
    _STATE.clear()
    _STATE.update({"inventory_path": inventory_path, "source": source, "matches": []})
    model_id = os.getenv("RECALLRADAR_MODEL_ID")

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
    if model_id:
        from strands.models import BedrockModel
        kwargs["model"] = BedrockModel(model_id=model_id)

    agent = Agent(**kwargs)
    result = agent(
        "Run the household recall scan now. Report only confirmed candidates, "
        "the evidence, immediate safety step, and the decision requiring approval."
    )
    return str(result)
