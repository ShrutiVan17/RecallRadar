"""Inventory loaders and recall-source adapters."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

import requests

from .core import Product, Recall


CPSC_URL = "https://www.saferproducts.gov/RestWebServices/Recall"

FIELD_ALIASES = {
    "product": "name", "product_name": "name", "item": "name",
    "manufacturer": "brand", "make": "brand",
    "model_number": "model", "model_no": "model",
    "lot_number": "lot", "lot_no": "lot",
    "purchase": "purchase_date", "date": "purchase_date",
    "store": "retailer", "upc_code": "upc", "barcode": "upc",
}


def load_inventory(path: str | Path) -> list[Product]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError("Inventory is empty. Add at least one product row.")
    if len(rows) > 500:
        raise ValueError("Inventory is limited to 500 products per scan.")

    fields = {
        FIELD_ALIASES.get((name or "").strip().lower(), (name or "").strip().lower())
        for name in (reader.fieldnames or [])
    }
    if "name" not in fields:
        raise ValueError("Inventory needs a 'name' or 'product_name' column.")

    allowed = set(Product.__dataclass_fields__)
    products: list[Product] = []
    for index, raw in enumerate(rows, start=1):
        normalized = {}
        for key, value in raw.items():
            clean_key = (key or "").strip().lower()
            normalized[FIELD_ALIASES.get(clean_key, clean_key)] = str(value or "").strip()
        values = {field: normalized.get(field, "") for field in allowed}
        values["product_id"] = values["product_id"] or f"P{index:03d}"
        if not values["name"]:
            raise ValueError(f"Row {index} has no product name.")
        products.append(Product(**values))
    return products


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


def _parse_cpsc_payload(payload: list[dict], limit: int) -> list[Recall]:
    recalls: list[Recall] = []
    for item in payload[:limit]:
        products = item.get("Products") or [{}]
        product_text = _join(products, "Name", "Description")
        model_text = _join(products, "Model")
        upc_text = _join(item.get("ProductUPCs") or [], "UPC")
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
                upcs=upc_text,
            )
        )
    return recalls


def fetch_cpsc_recalls(products: list[Product] | None = None, limit: int = 75, timeout: int = 12) -> list[Recall]:
    """Query the official CPSC API, targeting known product identifiers."""
    queries: list[dict[str, str]] = []
    for product in (products or [])[:40]:
        if product.model:
            queries.append({"ProductModel": product.model})
        elif product.name:
            queries.append({"ProductName": product.name})
    if not queries:
        queries = [{"RecallDateStart": (date.today() - timedelta(days=1095)).strftime("%m/%d/%Y")}]

    collected: dict[str, Recall] = {}
    for query in queries:
        response = requests.get(
            CPSC_URL,
            params={"format": "json", **query},
            headers={"User-Agent": "RecallRadar-Hackathon/1.0"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("The CPSC API returned an unexpected response.")
        for recall in _parse_cpsc_payload(payload, limit):
            collected[recall.recall_id] = recall
    return list(collected.values())
