"""Inventory loaders and recall-source adapters."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import requests

from .core import Product, Recall


CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall"


def load_inventory(path: str | Path) -> list[Product]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"product_id", "name", "brand", "model", "lot", "purchase_date", "retailer"}
    missing = required - set(rows[0] if rows else [])
    if missing:
        raise ValueError(f"Inventory is missing columns: {', '.join(sorted(missing))}")
    return [Product(**{field: (row.get(field) or "").strip() for field in required}) for row in rows]


def demo_recalls(path: str | Path = "data/demo_recalls.csv") -> list[Recall]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [Recall(**row) for row in csv.DictReader(handle)]


def _join(values: list[dict], *keys: str) -> str:
    found: list[str] = []
    for item in values or []:
        for key in keys:
            if item.get(key):
                found.append(str(item[key]))
    return ", ".join(dict.fromkeys(found))


def fetch_cpsc_recalls(limit: int = 75, timeout: int = 12) -> list[Recall]:
    """Fetch current public CPSC notices. The adapter tolerates sparse fields."""
    response = requests.get(
        CPSC_URL,
        params={
            "format": "json",
            "RecallDateStart": (date.today() - timedelta(days=1095)).strftime("%m/%d/%Y"),
        },
        headers={"User-Agent": "RecallRadar-Hackathon/0.1"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    recalls: list[Recall] = []

    for item in payload[:limit]:
        products = item.get("Products") or [{}]
        product_text = _join(products, "Name", "Description")
        model_text = _join(products, "Model")
        brands = item.get("Manufacturers") or []
        brand_text = _join(brands, "Name")
        hazards = _join(item.get("Hazards") or [], "Name")
        remedies = _join(item.get("Remedies") or [], "Name")
        recall_id = str(item.get("RecallID") or item.get("RecallNumber") or "unknown")
        recalls.append(
            Recall(
                recall_id=recall_id,
                title=str(item.get("Title") or product_text or "CPSC recall"),
                brand=brand_text,
                product_name=product_text,
                models=model_text,
                hazard=hazards,
                remedy=remedies,
                official_url=str(item.get("URL") or ""),
                recall_date=str(item.get("RecallDate") or ""),
            )
        )
    return recalls
